from audit.models import AuditAction, AuditLog
from config.testing import SipdAPITestCase
from predictions.models import Prediction
from predictions.services import predict_records
from students.models import Student
from users.models import Role, User


class StudentReadOnlyTests(SipdAPITestCase):
    def test_retrieve_by_code_includes_records_and_is_logged(self):
        response = self.client_for(self.admin).get("/api/students/E001/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["anonymous_code"], "E001")
        self.assertEqual(len(response.data["academic_records"]), 2)
        log = AuditLog.objects.get(action=AuditAction.STUDENT_VIEWED)
        self.assertEqual((log.user, log.entity_id), (self.admin, "E001"))

    def test_profile_cannot_be_edited_by_anyone(self):
        for user in (self.admin, self.coordinator):
            client = self.client_for(user)
            self.assertEqual(client.patch("/api/students/E002/", {"semester": 4}, format="json").status_code, 405)
            self.assertEqual(client.put("/api/students/E002/", {"semester": 4}, format="json").status_code, 405)
            self.assertEqual(client.delete("/api/students/E002/").status_code, 405)
            created = client.post("/api/students/", {"anonymous_code": "E050", "program": "SIS", "semester": 2}, format="json")
            self.assertEqual(created.status_code, 405)
            self.assertEqual(client.post("/api/students/E002/records/", {}, format="json").status_code, 404)
        student = Student.objects.get(anonymous_code="E002")
        self.assertEqual((student.semester, student.is_active), (3, True))
        self.assertFalse(Student.objects.filter(anonymous_code="E050").exists())


class StudentScopeTests(SipdAPITestCase):
    def test_admin_sees_all_students(self):
        self.assertEqual(self.client_for(self.admin).get("/api/students/").data["count"], 2)

    def test_coordinator_only_sees_assigned_programs(self):
        client = self.client_for(self.coordinator_sis)
        codes = [s["anonymous_code"] for s in client.get("/api/students/").data["results"]]
        self.assertEqual(codes, ["E001"])
        self.assertEqual(client.get("/api/students/E002/").status_code, 404)
        self.assertEqual(self.client_for(self.coordinator).get("/api/students/").data["count"], 2)

    def test_coordinator_without_programs_sees_nothing(self):
        lonely = User.objects.create_user("sin_prog", "sinprog@test.local", "Prueba#Segura2026", role=Role.COORDINATOR)
        client = self.client_for(lonely)
        self.assertEqual(client.get("/api/students/").data["count"], 0)
        self.assertEqual(client.get("/api/students/E001/").status_code, 404)
        self.assertEqual(client.get("/api/predictions/summary/").data["totals"]["students"], 0)

    def test_filters_search_and_default_priority_order(self):
        predict_records([self.record_sis, self.record_civ])
        client = self.client_for(self.admin)
        self.assertEqual(client.get("/api/students/?program=CIV").data["count"], 1)
        self.assertEqual(client.get("/api/students/?search=E00").data["count"], 2)
        high = client.get("/api/students/?risk_level=ALTO").data["results"]
        self.assertTrue(all(s["current_risk_level"] == "ALTO" for s in high))
        ordered = client.get("/api/students/").data["results"]  # por defecto: mayor riesgo primero
        self.assertGreaterEqual(ordered[0]["current_probability"], ordered[1]["current_probability"])
        self.assertEqual(client.get("/api/students/?followup_status=SIN_SEGUIMIENTO").data["count"], 2)

    def test_risk_change_against_previous_period(self):
        previous = self.student_sis.academic_records.get(academic_period=self.previous_period)
        predict_records([previous])
        predict_records([self.record_sis])
        before = Prediction.objects.get(academic_period=self.previous_period).probability
        now = Prediction.objects.get(academic_period=self.period).probability
        row = self.client_for(self.admin).get("/api/students/E001/").data
        self.assertAlmostEqual(row["previous_probability"], before)
        self.assertEqual(row["risk_change_points"], round((now - before) * 100, 1))
        trend = "up" if now > before else "down"
        self.assertEqual(self.client_for(self.admin).get(f"/api/students/?trend={trend}").data["count"], 1)
        # Sin predicción anterior el cambio es nulo, no cero.
        predict_records([self.record_civ])
        civ = self.client_for(self.admin).get("/api/students/E002/").data
        self.assertIsNone(civ["risk_change_points"])

    def test_export_csv_respects_scope_and_filters(self):
        predict_records([self.record_sis, self.record_civ])
        content = b"".join(self.client_for(self.coordinator_sis).get("/api/students/export/").streaming_content).decode()
        lines = content.lstrip("﻿").strip().splitlines()
        self.assertIn("Código seudonimizado", lines[0])
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[1].startswith("E001,"))
        self.assertNotIn("strato", lines[0])
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.REPORT_EXPORTED, entity_id="estudiantes").exists())
