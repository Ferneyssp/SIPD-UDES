import csv
import io

from audit.models import AuditAction, AuditLog
from config.risk import RiskLevel
from config.testing import SipdAPITestCase
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
        data = self.client_for(self.coordinator_sis).get("/api/reports/risk/?period=2026-2").data
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
        for user in (self.coordinator, self.coordinator_sis):
            self.assertEqual(self.client_for(user).get("/api/reports/risk/students/csv/").status_code, 403)
        rows = read_csv(self.client_for(self.admin).get("/api/reports/risk/students/csv/?period=2026-2"))
        self.assertEqual(len(rows) - 1, self.predictions.count())
        header = " ".join(rows[0]).lower()
        for sensitive in ("estrato", "socioecon", "financ", "trabaja"):
            self.assertNotIn(sensitive, header)

    def test_pdf_exports(self):
        admin = self.client_for(self.admin)
        for url in ("/api/reports/risk/pdf/?period=2026-2", "/api/reports/risk/pdf/?period=2025-1",
                    ):
            response = admin.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertEqual(response["Content-Type"], "application/pdf")
            self.assertTrue(response.content.startswith(b"%PDF"), url)
        # Un filtro con marcado no rompe el documento.
        self.assertEqual(admin.get("/api/reports/risk/pdf/?program=<b>X").status_code, 200)

    def test_model_evaluation_report_was_removed(self):
        admin = self.client_for(self.admin)
        for url in ("/api/reports/models/", "/api/reports/models/csv/", "/api/reports/models/pdf/"):
            self.assertEqual(admin.get(url).status_code, 404, url)

    def test_activity_report_and_audit_module_were_removed(self):
        admin = self.client_for(self.admin)
        for url in ("/api/reports/activity/", "/api/reports/activity/csv/", "/api/reports/activity/pdf/", "/api/audit/"):
            self.assertEqual(admin.get(url).status_code, 404, url)

    def test_reports_do_not_label_data_as_synthetic(self):
        risk = self.client_for(self.admin).get("/api/reports/risk/?period=2026-2").data
        text = str(risk)
        self.assertNotIn("is_synthetic", text)
        self.assertNotIn("SINTÉTICOS", text.upper().replace("SINTETICOS", "SINTÉTICOS"))

    def test_csv_cells_are_protected_against_formulas(self):
        self.assertEqual(safe_cell("=HYPERLINK(\"x\")"), "'=HYPERLINK(\"x\")")
        self.assertEqual(safe_cell("+1"), "'+1")
        self.assertEqual(safe_cell("@SUM(A1)"), "'@SUM(A1)")
        self.assertEqual(safe_cell(-0.5), -0.5)
        self.assertEqual(safe_cell(None), "")
        self.assertEqual(safe_cell("Ingeniería"), "Ingeniería")
