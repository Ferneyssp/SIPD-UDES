import csv
import io

from audit.models import AuditAction, AuditLog
from config.risk import RiskLevel
from config.testing import SipdAPITestCase
from ml.models import ModelVersion
from predictions.models import Prediction, PredictionStatus
from reports.exporters import safe_cell


def read_csv(response) -> list[list[str]]:
    content = b"".join(response.streaming_content).decode("utf-8")
    assert content.startswith("﻿")
    return list(csv.reader(io.StringIO(content.lstrip("﻿"))))


class ReportApiTests(SipdAPITestCase):
    def setUp(self):
        super().setUp()
        self.client_for(self.admin).post("/api/predictions/run-batch/", {"academic_period": "2026-2"}, format="json")
        self.predictions = Prediction.objects.filter(status=PredictionStatus.CURRENT, academic_period=self.period)

    def test_risk_report_matches_stored_predictions(self):
        data = self.client_for(self.admin).get("/api/reports/risk/?period=2026-2").data
        self.assertEqual(data["totals"]["students"], self.predictions.count())
        levels = {item["code"]: item["count"] for item in data["totals"]["levels"]}
        for level in RiskLevel:
            self.assertEqual(levels[level.value], self.predictions.filter(risk_level=level).count())
        self.assertEqual(sum(row["total"] for row in data["by_program"]), self.predictions.count())
        self.assertEqual(data["models"][0]["predictions"], self.predictions.count())
        self.assertTrue(any("estimación" in notice for notice in data["notices"]))

    def test_risk_report_respects_scope_and_filters(self):
        data = self.client_for(self.professor).get("/api/reports/risk/?period=2026-2").data
        self.assertEqual(data["totals"]["students"], 1)
        self.assertEqual([row["program"] for row in data["by_program"]], ["Ingeniería de Sistemas"])
        self.assertTrue(data["scope_restricted"])
        admin = self.client_for(self.admin)
        self.assertEqual(admin.get("/api/reports/risk/?period=2026-2&program=CIV").data["totals"]["students"], 1)
        self.assertEqual(admin.get("/api/reports/risk/?period=2025-1").data["totals"]["students"], 0)
        self.assertEqual(admin.get("/api/reports/risk/?date_from=mal").status_code, 400)

    def test_risk_csv_uses_same_numbers_as_view(self):
        rows = read_csv(self.client_for(self.admin).get("/api/reports/risk/csv/?period=2026-2"))
        self.assertEqual(rows[0][:3], ["Agrupación", "Grupo", "Estudiantes"])
        self.assertEqual(rows[1][:3], ["Total", "2026-2", str(self.predictions.count())])
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.REPORT_EXPORTED).exists())

    def test_individual_listing_is_admin_only_and_excludes_sensitive_fields(self):
        for user in (self.coordinator, self.professor):
            self.assertEqual(self.client_for(user).get("/api/reports/risk/students/csv/").status_code, 403)
        rows = read_csv(self.client_for(self.admin).get("/api/reports/risk/students/csv/?period=2026-2"))
        self.assertEqual(len(rows) - 1, self.predictions.count())
        header = " ".join(rows[0]).lower()
        for sensitive in ("estrato", "socioecon", "financ", "trabaja"):
            self.assertNotIn(sensitive, header)

    def test_pdf_exports(self):
        admin = self.client_for(self.admin)
        for url in ("/api/reports/risk/pdf/?period=2026-2", "/api/reports/risk/pdf/?period=2025-1",
                    "/api/reports/models/pdf/", "/api/reports/activity/pdf/"):
            response = admin.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertEqual(response["Content-Type"], "application/pdf")
            self.assertTrue(response.content.startswith(b"%PDF"), url)
        # Un filtro con marcado no rompe el documento.
        self.assertEqual(admin.get("/api/reports/risk/pdf/?program=<b>X").status_code, 200)

    def test_model_report_and_csv(self):
        data = self.client_for(self.professor).get("/api/reports/models/").data
        version = ModelVersion.objects.get(active=True)
        row = next(v for v in data["versions"] if v["id"] == version.pk)
        self.assertEqual(row["metrics"]["f1"], version.metrics["f1"])
        self.assertIsNone(row["approved_by"])  # sin datos de usuarios para roles no administradores
        rows = read_csv(self.client_for(self.admin).get("/api/reports/models/csv/"))
        self.assertIn("F1 (prueba)", rows[0])
        self.assertEqual(len(rows) - 1, ModelVersion.objects.count())

    def test_activity_report_is_admin_only(self):
        for user in (self.coordinator, self.professor):
            client = self.client_for(user)
            self.assertEqual(client.get("/api/reports/activity/").status_code, 403)
            self.assertEqual(client.get("/api/reports/activity/csv/").status_code, 403)
            self.assertEqual(client.get("/api/reports/activity/pdf/").status_code, 403)
        data = self.client_for(self.admin).get("/api/reports/activity/").data
        counts = {item["action"]: item["count"] for item in data["audit_counts"]}
        self.assertEqual(counts[AuditAction.PREDICTION_RUN], 1)
        self.assertIsNotNone(data["coverage_since"])

    def test_csv_cells_are_protected_against_formulas(self):
        self.assertEqual(safe_cell("=HYPERLINK(\"x\")"), "'=HYPERLINK(\"x\")")
        self.assertEqual(safe_cell("+1"), "'+1")
        self.assertEqual(safe_cell("@SUM(A1)"), "'@SUM(A1)")
        self.assertEqual(safe_cell(-0.5), -0.5)
        self.assertEqual(safe_cell(None), "")
        self.assertEqual(safe_cell("Ingeniería"), "Ingeniería")
