from django.test import override_settings

from alerts.models import Alert, AlertReason, AlertStatus
from config.testing import SipdAPITestCase
from notifications.models import Notification, NotificationType
from predictions.models import Prediction
from predictions.services import predict_records
from users.models import Role, User


class AlertGenerationTests(SipdAPITestCase):
    def test_high_risk_prediction_creates_one_alert(self):
        with self.captureOnCommitCallbacks(execute=True):
            predict_records([self.record_sis])
        prediction = Prediction.objects.get()
        self.assertEqual(prediction.risk_level, "ALTO", "el perfil de prueba E001 es de riesgo alto")
        alert = Alert.objects.get()
        self.assertEqual((alert.student, alert.reason, alert.priority), (self.student_sis, AlertReason.HIGH_LEVEL, "ALTA"))
        predict_records([self.record_sis])  # repetir la predicción no duplica la alerta
        self.assertEqual(Alert.objects.count(), 1)
        self.assertEqual(Alert.objects.get().prediction, Prediction.objects.get(status="VIGENTE"))
        # Aviso agregado a los coordinadores del programa, no a otros.
        recipients = set(Notification.objects.filter(type=NotificationType.ALERTS_CREATED).values_list("recipient", flat=True))
        self.assertEqual(recipients, {self.coordinator.pk, self.coordinator_sis.pk})

    def test_low_risk_without_rise_creates_no_alert(self):
        predict_records([self.record_civ])
        self.assertFalse(Alert.objects.exists())

    @override_settings(ALERT_RISE_THRESHOLD=0.0001)
    def test_rise_against_previous_period_creates_alert(self):
        civ_previous = self.record_civ.__class__.objects.create(
            student=self.student_civ, academic_period=self.previous_period, semester=2, academic_status="Activo",
            gpa=4.9, credits_enrolled=18, credits_approved=18, credits_failed=0, failed_subjects=0,
            attendance_percentage=99, course_repetitions=0,
        )
        predict_records([civ_previous])
        self.record_civ.gpa, self.record_civ.attendance_percentage = 3.0, 70
        self.record_civ.save()
        predict_records([self.record_civ])
        alert = Alert.objects.get(student=self.student_civ, academic_period=self.period)
        self.assertIn(alert.reason, {AlertReason.RISE, AlertReason.HIGH_AND_RISE})
        self.assertGreater(alert.change, 0)

    def test_closed_alert_is_not_reopened_automatically(self):
        predict_records([self.record_sis])
        Alert.objects.update(status=AlertStatus.CLOSED, closing_observation="Atendido por la coordinación.")
        predict_records([self.record_sis])
        self.assertEqual(Alert.objects.get().status, AlertStatus.CLOSED)


class AlertApiTests(SipdAPITestCase):
    def setUp(self):
        super().setUp()
        predict_records([self.record_sis])
        self.alert = Alert.objects.get()
        self.url = f"/api/alerts/{self.alert.pk}/"

    def test_scope(self):
        self.assertEqual(self.client_for(self.admin).get("/api/alerts/").data["count"], 1)
        self.assertEqual(self.client_for(self.coordinator_sis).get("/api/alerts/").data["count"], 1)
        civ_only = User.objects.create_user("coord_civ", "civ@test.local", "Prueba#Segura2026", role=Role.COORDINATOR)
        civ_only.programs.set([self.civ])
        client = self.client_for(civ_only)
        self.assertEqual(client.get("/api/alerts/").data["count"], 0)
        self.assertEqual(client.get(self.url).status_code, 404)
        self.assertEqual(client.post(self.url + "close/", {"observation": "x" * 20}, format="json").status_code, 404)
        self.assertEqual(self.client.get("/api/alerts/").status_code, 401)

    def test_alert_is_managed_through_followup(self):
        """Registrar el seguimiento pone la alerta "En atención"; marcarlo Atendido la cierra con su observación."""
        client = self.client_for(self.coordinator_sis)
        payload = {"student": "E001", "status": "PENDIENTE", "intervention_type": "TUTORIA",
                   "observation": "Se contactó al estudiante y se programó tutoría."}
        created = client.post("/api/followups/", payload, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, AlertStatus.IN_PROGRESS)
        self.assertEqual((self.alert.assigned_to, self.alert.followup_id), (self.coordinator_sis, created.data["id"]))
        client.patch(f"/api/followups/{created.data['id']}/", {"status": "ATENDIDO",
                     "observation": "Tutoría realizada; plan de estudio acordado."}, format="json")
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, AlertStatus.CLOSED)
        self.assertEqual(self.alert.closing_observation, "Tutoría realizada; plan de estudio acordado.")
        self.assertEqual(self.alert.closed_by, self.coordinator_sis)
        # Las alertas ya no se gestionan por separado.
        for action in ("assign", "comment", "start", "close"):
            self.assertEqual(client.post(f"{self.url}{action}/", {}, format="json").status_code, 404)

    def test_filters_and_summary(self):
        client = self.client_for(self.admin)
        self.assertEqual(client.get("/api/alerts/?status=pending").data["count"], 1)
        self.assertEqual(client.get("/api/alerts/?status=CERRADA").data["count"], 0)
        self.assertEqual(client.get("/api/alerts/?assigned=none").data["count"], 1)
        self.assertEqual(client.get("/api/alerts/?student=E001").data["count"], 1)
        summary = client.get("/api/alerts/summary/").data
        self.assertEqual((summary["open"], summary["unassigned"], len(summary["recent"])), (1, 1, 1))

    def test_student_list_shows_open_alert(self):
        row = self.client_for(self.admin).get("/api/students/?alert=open").data["results"]
        self.assertEqual([r["anonymous_code"] for r in row], ["E001"])
        self.assertEqual(row[0]["open_alert_status"], AlertStatus.OPEN)
