from config.testing import SipdAPITestCase
from predictions.services import predict_records
from students.models import Student


class StudentCrudTests(SipdAPITestCase):
    def test_admin_creates_student(self):
        response = self.client_for(self.admin).post(
            "/api/students/", {"anonymous_code": "e050", "program": "SIS", "semester": 2}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(Student.objects.filter(anonymous_code="E050").exists())

    def test_invalid_anonymous_code_rejected(self):
        response = self.client_for(self.admin).post(
            "/api/students/", {"anonymous_code": "Juan Perez", "program": "SIS", "semester": 2}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_retrieve_by_code_includes_records(self):
        response = self.client_for(self.admin).get("/api/students/E001/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["anonymous_code"], "E001")
        self.assertEqual(len(response.data["academic_records"]), 2)

    def test_update_and_soft_delete(self):
        client = self.client_for(self.admin)
        self.assertEqual(client.patch("/api/students/E002/", {"semester": 4}, format="json").status_code, 200)
        self.assertEqual(client.delete("/api/students/E002/").status_code, 200)
        student = Student.objects.get(anonymous_code="E002")
        self.assertEqual(student.semester, 4)
        self.assertFalse(student.is_active)

    def test_non_admin_cannot_modify(self):
        response = self.client_for(self.coordinator).patch("/api/students/E002/", {"semester": 4}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_professor_only_sees_assigned_programs(self):
        client = self.client_for(self.professor)
        codes = [s["anonymous_code"] for s in client.get("/api/students/").data["results"]]
        self.assertEqual(codes, ["E001"])
        self.assertEqual(client.get("/api/students/E002/").status_code, 404)

    def test_coordinator_without_programs_sees_all(self):
        self.assertEqual(self.client_for(self.coordinator).get("/api/students/").data["count"], 2)

    def test_filters_and_search(self):
        predict_records([self.record_sis, self.record_civ])
        client = self.client_for(self.admin)
        self.assertEqual(client.get("/api/students/?program=CIV").data["count"], 1)
        self.assertEqual(client.get("/api/students/?search=E00").data["count"], 2)
        high = client.get("/api/students/?risk_level=ALTO").data["results"]
        self.assertTrue(all(s["current_risk_level"] == "ALTO" for s in high))
        ordered = client.get("/api/students/?ordering=-current_probability").data["results"]
        self.assertGreaterEqual(ordered[0]["current_probability"], ordered[1]["current_probability"])
        self.assertEqual(client.get("/api/students/?followup_status=SIN_SEGUIMIENTO").data["count"], 2)
