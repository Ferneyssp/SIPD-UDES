import tempfile

from django.test import override_settings

from audit.models import AuditAction, AuditLog
from config.risk import classify_risk
from config.testing import SipdAPITestCase
from ml.models import ModelVersion
from ml.services import clear_cache
from predictions.models import Prediction, PredictionStatus


class PredictionApiTests(SipdAPITestCase):
    def test_admin_runs_prediction_for_student(self):
        response = self.client_for(self.admin).post("/api/predictions/", {"student": "E001"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        for key in ("student_id", "risk_probability", "risk_percentage", "risk_level", "model", "prediction_date"):
            self.assertIn(key, response.data)
        self.assertEqual(response.data["student_id"], "E001")
        self.assertTrue(0 <= response.data["risk_probability"] <= 1)
        prediction = Prediction.objects.get()
        self.assertEqual(prediction.risk_level, classify_risk(prediction.probability))
        self.assertEqual(prediction.input_features["previous_gpa"], 3.2)
        self.assertTrue(prediction.explanation)
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.PREDICTION_RUN).exists())

    def test_risky_profile_scores_higher_than_good_profile(self):
        client = self.client_for(self.admin)
        risky = client.post("/api/predictions/", {"student": "E001"}, format="json").data["risk_probability"]
        good = client.post("/api/predictions/", {"student": "E002"}, format="json").data["risk_probability"]
        self.assertGreater(risky, good)

    def test_predictions_are_never_overwritten(self):
        client = self.client_for(self.admin)
        client.post("/api/predictions/", {"student": "E001"}, format="json")
        client.post("/api/predictions/", {"student": "E001"}, format="json")
        self.assertEqual(Prediction.objects.filter(student=self.student_sis).count(), 2)
        self.assertEqual(Prediction.objects.filter(student=self.student_sis, status=PredictionStatus.CURRENT).count(), 1)

    def test_history_shows_evolution_across_periods(self):
        client = self.client_for(self.admin)
        client.post("/api/predictions/", {"student": "E001", "academic_period": "2026-1"}, format="json")
        client.post("/api/predictions/", {"student": "E001", "academic_period": "2026-2"}, format="json")
        timeline = client.get("/api/predictions/history/?student=E001").data["timeline"]
        self.assertEqual([t["academic_period"] for t in timeline], ["2026-1", "2026-2"])

    def test_only_admin_runs_predictions(self):
        self.assertEqual(self.client_for(self.coordinator).post("/api/predictions/", {"student": "E001"}, format="json").status_code, 403)
        self.assertEqual(self.client_for(self.professor).post("/api/predictions/run-batch/", {"academic_period": "2026-2"}, format="json").status_code, 403)

    def test_batch_and_filters(self):
        client = self.client_for(self.admin)
        response = client.post("/api/predictions/run-batch/", {"academic_period": "2026-2"}, format="json")
        self.assertEqual(response.data["predictions_generated"], 2)
        self.assertEqual(client.get("/api/predictions/?period=2026-2").data["count"], 2)
        self.assertEqual(client.get("/api/predictions/?program=CIV").data["count"], 1)
        self.assertEqual(client.get("/api/predictions/?date_from=bad").status_code, 400)

    def test_professor_sees_only_scope_predictions(self):
        self.client_for(self.admin).post("/api/predictions/run-batch/", {"academic_period": "2026-2"}, format="json")
        results = self.client_for(self.professor).get("/api/predictions/").data["results"]
        self.assertEqual({r["student_code"] for r in results}, {"E001"})
        self.assertEqual(self.client_for(self.professor).get("/api/predictions/history/?student=E002").status_code, 403)

    def test_summary_for_inicio(self):
        self.client_for(self.admin).post("/api/predictions/run-batch/", {"academic_period": "2026-2"}, format="json")
        data = self.client_for(self.admin).get("/api/predictions/summary/").data
        totals = data["totals"]
        self.assertEqual(data["period"], "2026-2")
        self.assertEqual(totals["students"], 2)
        self.assertEqual(totals["high"] + totals["medium"] + totals["low"], 2)
        self.assertEqual(totals["predictions"], 2)
        self.assertTrue(data["model"]["available"])

    def test_model_not_available_returns_503(self):
        ModelVersion.objects.all().delete()
        with override_settings(ML_MODELS_DIR=tempfile.mkdtemp()):
            clear_cache()
            response = self.client_for(self.admin).post("/api/predictions/", {"student": "E001"}, format="json")
        clear_cache()
        self.assertEqual(response.status_code, 503)
        self.assertIn("modelo", response.data["detail"])

    def test_config_exposes_centralized_thresholds(self):
        data = self.client_for(self.professor).get("/api/config/").data
        self.assertEqual(data["risk_thresholds"], {"low": 0.3, "medium": 0.6})
        self.assertEqual([level["code"] for level in data["risk_levels"]], ["BAJO", "MEDIO", "ALTO"])
