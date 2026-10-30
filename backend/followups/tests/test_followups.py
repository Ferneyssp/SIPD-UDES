from audit.models import AuditAction, AuditLog
from config.testing import SipdAPITestCase
from followups.models import FollowUp


class FollowUpTests(SipdAPITestCase):
    payload = {"student": "E001", "status": "PENDIENTE", "intervention_type": "TUTORIA",
               "observation": "Se programa tutoría de refuerzo en cálculo."}

    def test_coordinator_registers_followup_for_own_student(self):
        response = self.client_for(self.coordinator_sis).post("/api/followups/", self.payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        followup = FollowUp.objects.get()
        self.assertEqual(followup.user, self.coordinator_sis)
        self.assertEqual(followup.academic_period, self.period)
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.FOLLOWUP_CREATED).exists())

    def test_coordinator_cannot_register_outside_scope(self):
        response = self.client_for(self.coordinator_sis).post("/api/followups/", {**self.payload, "student": "E002"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_status_update_and_permissions(self):
        created = self.client_for(self.coordinator).post("/api/followups/", self.payload, format="json").data
        url = f"/api/followups/{created['id']}/"
        response = self.client_for(self.coordinator).patch(url, {"status": "EN_SEGUIMIENTO"}, format="json")
        self.assertEqual(response.data["status_display"], "En seguimiento")

    def test_followups_cannot_be_deleted(self):
        created = self.client_for(self.admin).post("/api/followups/", {**self.payload, "user": self.coordinator_sis.id},
                                                   format="json").data
        self.assertEqual(self.client_for(self.admin).delete(f"/api/followups/{created['id']}/").status_code, 405)

    def test_students_filter_by_followup_status(self):
        self.client_for(self.coordinator_sis).post("/api/followups/", self.payload, format="json")
        data = self.client_for(self.admin).get("/api/students/?followup_status=PENDIENTE").data
        self.assertEqual([s["anonymous_code"] for s in data["results"]], ["E001"])

    def test_responsibles_endpoint_for_scoped_user(self):
        response = self.client_for(self.coordinator_sis).get("/api/followups/responsibles/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.coordinator_sis.id, [u["id"] for u in response.data])

    def test_responsible_must_have_access_to_student_program(self):
        """S7: no se puede asignar como responsable a alguien sin acceso al programa del estudiante."""
        from users.models import Role, User

        civ_only = User.objects.create_user("coord_civ", "civ@test.local", "Prueba#Segura2026", role=Role.COORDINATOR)
        civ_only.programs.set([self.civ])
        response = self.client_for(self.admin).post("/api/followups/", {**self.payload, "user": civ_only.id}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("user", response.data["errors"])
        ok = self.client_for(self.admin).post("/api/followups/", {**self.payload, "user": self.coordinator_sis.id},
                                              format="json")
        self.assertEqual(ok.status_code, 201, ok.data)
        ids = [u["id"] for u in self.client_for(self.admin).get("/api/followups/responsibles/?student=E001").data]
        self.assertIn(self.coordinator_sis.id, ids)
        self.assertNotIn(self.admin.id, ids)  # el Administrador nunca es responsable
        self.assertNotIn(civ_only.id, ids)
        denied = self.client_for(self.coordinator_sis).get("/api/followups/responsibles/?student=E002")
        self.assertEqual(denied.status_code, 403)

    def test_latest_lists_one_followup_per_student(self):
        client = self.client_for(self.coordinator_sis)
        first = client.post("/api/followups/", {**self.payload, "follow_up_date": "2026-09-01"}, format="json").data
        second = client.post("/api/followups/", {**self.payload, "status": "EN_SEGUIMIENTO", "follow_up_date": "2026-09-15",
                                                 "observation": "Segunda intervención con el estudiante."}, format="json").data
        self.assertEqual(client.get("/api/followups/").data["count"], 2)  # historial completo
        latest = client.get("/api/followups/?latest=true").data
        self.assertEqual([f["id"] for f in latest["results"]], [second["id"]])
        self.assertEqual(client.get("/api/followups/?latest=true&status=PENDIENTE").data["count"], 0)  # estado actual
        client.patch(f"/api/followups/{second['id']}/", {"status": "ATENDIDO"}, format="json")
        self.assertEqual(client.get("/api/followups/?latest=true").data["results"][0]["status"], "ATENDIDO")
        self.assertNotEqual(first["id"], second["id"])

    def test_admin_can_never_be_responsible(self):
        admin = self.client_for(self.admin)
        missing = admin.post("/api/followups/", self.payload, format="json")
        self.assertEqual(missing.status_code, 400)  # el Administrador debe elegir un coordinador
        self.assertIn("user", missing.data["errors"])
        self_assigned = admin.post("/api/followups/", {**self.payload, "user": self.admin.id}, format="json")
        self.assertEqual(self_assigned.status_code, 400)
        created = self.client_for(self.coordinator_sis).post("/api/followups/", self.payload, format="json").data
        moved = admin.patch(f"/api/followups/{created['id']}/", {"user": self.admin.id}, format="json")
        self.assertEqual(moved.status_code, 400)
        self.assertEqual(FollowUp.objects.get().user, self.coordinator_sis)
        self.assertNotIn(self.admin.id, [u["id"] for u in admin.get("/api/followups/responsibles/").data])
