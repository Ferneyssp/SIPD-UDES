from audit.models import AuditAction, AuditLog
from config.testing import SipdAPITestCase
from followups.models import FollowUp


class FollowUpTests(SipdAPITestCase):
    payload = {"student": "E001", "status": "PENDIENTE", "intervention_type": "TUTORIA",
               "observation": "Se programa tutoría de refuerzo en cálculo."}

    def test_professor_registers_followup_for_own_student(self):
        response = self.client_for(self.professor).post("/api/followups/", self.payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        followup = FollowUp.objects.get()
        self.assertEqual(followup.user, self.professor)
        self.assertEqual(followup.academic_period, self.period)
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.FOLLOWUP_CREATED).exists())

    def test_professor_cannot_register_outside_scope(self):
        response = self.client_for(self.professor).post("/api/followups/", {**self.payload, "student": "E002"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_status_update_and_permissions(self):
        created = self.client_for(self.coordinator).post("/api/followups/", self.payload, format="json").data
        url = f"/api/followups/{created['id']}/"
        self.assertEqual(self.client_for(self.professor).patch(url, {"status": "CERRADO"}, format="json").status_code, 403)
        response = self.client_for(self.coordinator).patch(url, {"status": "EN_SEGUIMIENTO"}, format="json")
        self.assertEqual(response.data["status_display"], "En seguimiento")

    def test_followups_cannot_be_deleted(self):
        created = self.client_for(self.admin).post("/api/followups/", self.payload, format="json").data
        self.assertEqual(self.client_for(self.admin).delete(f"/api/followups/{created['id']}/").status_code, 405)

    def test_students_filter_by_followup_status(self):
        self.client_for(self.admin).post("/api/followups/", self.payload, format="json")
        data = self.client_for(self.admin).get("/api/students/?followup_status=PENDIENTE").data
        self.assertEqual([s["anonymous_code"] for s in data["results"]], ["E001"])

    def test_responsibles_endpoint_for_scoped_user(self):
        response = self.client_for(self.professor).get("/api/followups/responsibles/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.professor.id, [u["id"] for u in response.data])
