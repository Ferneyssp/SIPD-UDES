from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from academic.models import AcademicRecord
from audit.models import AuditAction, AuditLog
from config.testing import SipdAPITestCase
from predictions.models import Prediction
from students.models import Student
from uploads.validators import FileRejected, validate_csv

HEADER = ("student_code,program_code,academic_period,semester,gpa,credits_enrolled,credits_approved,"
          "credits_failed,failed_subjects,attendance_percentage,academic_status,works_while_studying\n")
PROGRAMS = {"SIS", "CIV"}


def csv_bytes(*rows: str) -> bytes:
    return (HEADER + "\n".join(rows) + "\n").encode("utf-8")


class CsvValidatorTests(SimpleTestCase):
    def test_valid_rows(self):
        report = validate_csv(csv_bytes("E100,SIS,2026-2,3,3.5,18,15,3,1,90,Activo,si"), PROGRAMS)
        self.assertEqual((report.records_found, report.records_valid, report.records_failed), (1, 1, 0))
        self.assertTrue(report.valid_rows[0]["works_while_studying"])

    def test_academic_probation_status_no_longer_exists(self):
        report = validate_csv(csv_bytes("E120,SIS,2026-2,3,3.5,18,15,3,1,90,Prueba académica,"), PROGRAMS)
        self.assertEqual(report.records_valid, 0)
        self.assertIn("academic_status", {e["column"] for e in report.errors})

    def test_missing_required_columns(self):
        with self.assertRaises(FileRejected):
            validate_csv(b"student_code,gpa\nE001,3.2\n", PROGRAMS)

    def test_out_of_range_and_type_errors(self):
        report = validate_csv(csv_bytes(
            "E101,SIS,2026-2,3,3.5,18,15,3,1,140,Activo,",   # asistencia > 100
            "E102,SIS,2026-2,3,7.5,18,15,3,1,90,Activo,",    # promedio fuera de rango
            "E103,SIS,2026-2,tres,3.5,18,15,3,1,90,Activo,",  # tipo inválido
            "E104,XYZ,2026-2,3,3.5,18,15,3,1,90,Activo,",    # programa inexistente
            "Pedro,SIS,2026-2,3,3.5,18,15,3,1,90,Activo,",   # identificador inválido
            "E105,SIS,2026-3,3,3.5,18,15,3,1,90,Activo,",    # periodo inválido
            "E106,SIS,2026-2,3,3.5,18,15,9,1,90,Activo,",    # créditos inconsistentes
            "E107,SIS,2026-2,3,,18,15,3,1,90,Activo,",       # valor faltante
        ), PROGRAMS)
        self.assertEqual(report.records_found, 8)
        self.assertEqual(report.records_valid, 0)
        self.assertEqual(report.records_failed, 8)
        columns = {e["column"] for e in report.errors}
        self.assertTrue({"attendance_percentage", "gpa", "semester", "program_code", "student_code", "academic_period"} <= columns)

    def test_duplicates_are_reported(self):
        report = validate_csv(csv_bytes(
            "E110,SIS,2026-2,3,3.5,18,15,3,1,90,Activo,",
            "E110,SIS,2026-2,3,3.6,18,15,3,1,91,Activo,",
        ), PROGRAMS)
        self.assertEqual((report.records_valid, report.records_failed), (1, 1))
        self.assertIn("duplicado", report.errors[0]["message"])

    def test_semicolon_delimiter_and_decimal_comma(self):
        text = HEADER.replace(",", ";") + "E120;SIS;2026-2;3;3,5;18;15;3;1;90,5;Activo;0\n"
        report = validate_csv(text.encode(), PROGRAMS)
        self.assertEqual(report.records_valid, 1)
        self.assertEqual(report.valid_rows[0]["gpa"], 3.5)

    def test_binary_file_rejected(self):
        with self.assertRaises(FileRejected):
            validate_csv(b"\x00\x01\x02binario", PROGRAMS)


class UploadFlowTests(SipdAPITestCase):
    def _upload(self, content: bytes, name="datos.csv", user=None):
        file = SimpleUploadedFile(name, content, content_type="text/csv")
        return self.client_for(user or self.admin).post("/api/uploads/", {"file": file}, format="multipart")

    def test_validate_then_confirm_creates_data_and_predictions(self):
        response = self._upload(csv_bytes(
            "E200,SIS,2026-2,2,2.8,16,10,6,2,70,Activo,1",
            "E201,CIV,2026-2,4,4.1,18,18,0,0,96,Activo,0",
            "E202,CIV,2026-2,4,9.9,18,18,0,0,96,Activo,0",
        ))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual((response.data["records_found"], response.data["records_valid"], response.data["records_failed"]), (3, 2, 1))
        self.assertFalse(Student.objects.filter(anonymous_code="E200").exists(), "Validar no debe modificar datos")

        confirm = self.client_for(self.admin).post(f"/api/uploads/{response.data['id']}/confirm/", {"run_predictions": True}, format="json")
        self.assertEqual(confirm.status_code, 200, confirm.data)
        self.assertEqual(confirm.data["status"], "PROCESADO")
        self.assertEqual(confirm.data["records_processed"], 2)
        self.assertEqual(confirm.data["predictions_generated"], 2)
        self.assertEqual(AcademicRecord.objects.filter(student__anonymous_code__in=["E200", "E201"]).count(), 2)
        self.assertEqual(Prediction.objects.filter(student__anonymous_code="E200").count(), 1)
        self.assertEqual(AuditLog.objects.filter(action=AuditAction.DATA_UPLOAD).count(), 2)

        again = self.client_for(self.admin).post(f"/api/uploads/{response.data['id']}/confirm/", format="json")
        self.assertEqual(again.status_code, 400)

    def test_file_with_only_errors_is_rejected(self):
        response = self._upload(csv_bytes("E300,SIS,2026-2,2,2.8,16,10,6,2,170,Activo,1"))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["status"], "RECHAZADO")

    def test_rejected_upload_is_not_stored(self):
        from uploads.models import DataUpload

        response = self.client_for(self.admin).post(
            "/api/uploads/", {"file": SimpleUploadedFile("solo_errores.csv", csv_bytes("E1,XYZ,2026-9,0,9,1,1,1,1,200,Nada,"),
                                                        content_type="text/csv")}, format="multipart")
        self.assertEqual(response.status_code, 422)
        self.assertIsNone(response.data["id"])
        self.assertFalse(DataUpload.objects.exists())
        self.assertEqual(self.client_for(self.admin).get("/api/uploads/").data["count"], 0)

    def test_validated_upload_can_be_discarded(self):
        from uploads.models import DataUpload

        client = self.client_for(self.admin)
        upload = client.post("/api/uploads/", {"file": SimpleUploadedFile(
            "ok.csv", csv_bytes("E120,SIS,2026-2,3,3.5,18,15,3,1,90,Activo,"), content_type="text/csv")}, format="multipart").data
        self.assertEqual(upload["status"], "VALIDADO")
        self.assertEqual(client.post(f"/api/uploads/{upload['id']}/discard/").status_code, 200)
        self.assertFalse(DataUpload.objects.exists())
        processed = client.post("/api/uploads/", {"file": SimpleUploadedFile(
            "ok.csv", csv_bytes("E121,SIS,2026-2,3,3.5,18,15,3,1,90,Activo,"), content_type="text/csv")}, format="multipart").data
        client.post(f"/api/uploads/{processed['id']}/confirm/", {"run_predictions": False}, format="json")
        self.assertEqual(client.post(f"/api/uploads/{processed['id']}/discard/").status_code, 409)  # las procesadas se conservan
        self.assertEqual(self.client_for(self.coordinator).post(f"/api/uploads/{processed['id']}/discard/").status_code, 403)

    def test_non_csv_extension_rejected(self):
        self.assertEqual(self._upload(b"hola", name="malware.exe").status_code, 400)

    def test_only_admin_can_upload(self):
        self.assertEqual(self._upload(csv_bytes("E400,SIS,2026-2,2,2.8,16,10,6,2,70,Activo,1"), user=self.coordinator).status_code, 403)

    def test_template_download(self):
        response = self.client_for(self.admin).get("/api/uploads/template/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"student_code", response.content)
