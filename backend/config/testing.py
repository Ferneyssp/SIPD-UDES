"""Utilidades compartidas por las pruebas del backend (datos SINTÉTICOS)."""
import tempfile
from pathlib import Path

from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from academic.models import AcademicPeriod, AcademicRecord, Program
from ml.services import clear_cache, sync_model_versions
from students.models import Student
from users.models import Role, User

PASSWORD = "Prueba#Segura2026"
_MODEL_DIR: Path | None = None


def trained_models_dir() -> Path:
    """Entrena UNA sola vez (por ejecución de pruebas) un modelo pequeño en un directorio temporal."""
    global _MODEL_DIR
    if _MODEL_DIR is None:
        from sipd_ml.pipeline import run_training_pipeline
        from sipd_ml.synthetic import generate_training_dataset

        _MODEL_DIR = Path(tempfile.mkdtemp(prefix="sipd-models-"))
        run_training_pipeline(
            generate_training_dataset(800, seed=11), models_dir=_MODEL_DIR,
            algorithms=["logistic_regression"], version="test",
        )
    return _MODEL_DIR


def record_values(**overrides):
    values = {
        "semester": 5, "academic_status": "Activo", "gpa": 3.6, "credits_enrolled": 18, "credits_approved": 18,
        "credits_failed": 0, "failed_subjects": 0, "attendance_percentage": 92, "course_repetitions": 0,
    }
    values.update(overrides)
    return values


class SipdAPITestCase(APITestCase):
    """Crea programas, periodos, usuarios por rol y algunos estudiantes."""

    @classmethod
    def setUpClass(cls):
        cls._settings = override_settings(ML_MODELS_DIR=trained_models_dir())
        cls._settings.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._settings.disable()
        clear_cache()

    @classmethod
    def setUpTestData(cls):
        cls.sis = Program.objects.create(code="SIS", name="Ingeniería de Sistemas")
        cls.civ = Program.objects.create(code="CIV", name="Ingeniería Civil")
        cls.previous_period = AcademicPeriod.objects.create(code="2026-1")
        cls.period = AcademicPeriod.objects.create(code="2026-2", is_current=True)
        cls.admin = User.objects.create_user("admin_t", "admin@test.local", PASSWORD, role=Role.ADMIN)
        cls.coordinator = User.objects.create_user("coord_t", "coord@test.local", PASSWORD, role=Role.COORDINATOR)
        cls.professor = User.objects.create_user("prof_t", "prof@test.local", PASSWORD, role=Role.PROFESSOR)
        cls.professor.programs.set([cls.sis])
        cls.student_sis = Student.objects.create(anonymous_code="E001", program=cls.sis, semester=5, current_period=cls.period)
        cls.student_civ = Student.objects.create(anonymous_code="E002", program=cls.civ, semester=3, current_period=cls.period)
        cls.record_sis = AcademicRecord.objects.create(
            student=cls.student_sis, academic_period=cls.period,
            **record_values(gpa=2.4, credits_approved=8, credits_failed=10, failed_subjects=4,
                            attendance_percentage=60, course_repetitions=3),
        )
        AcademicRecord.objects.create(student=cls.student_sis, academic_period=cls.previous_period, **record_values(semester=4, gpa=3.2))
        cls.record_civ = AcademicRecord.objects.create(student=cls.student_civ, academic_period=cls.period, **record_values(gpa=4.6))

    def setUp(self):
        clear_cache()
        sync_model_versions()

    def client_for(self, user) -> APIClient:
        client = APIClient()
        client.force_authenticate(user)
        return client
