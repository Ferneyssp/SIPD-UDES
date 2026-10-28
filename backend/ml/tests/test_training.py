"""Reentrenamiento desde la web: permisos, validación, ejecución real, aprobación, activación y recuperación."""
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from audit.models import AuditAction, AuditLog
from config.testing import SipdAPITestCase, trained_models_dir
from ml.models import ApprovalStatus, ModelActivationLog, ModelVersion, RunStatus, TrainingDataset, TrainingRun
from ml.training_service import fail_stale_runs
from notifications.models import Notification, NotificationType
from predictions.models import Prediction
from sipd_ml.dataset_validation import validate_training_dataset

VALIDATION = {"gpa_min": 0, "gpa_max": 5, "max_rows": 1000, "min_rows": 100, "min_rows_per_class": 10}
_DATASET_CSV: bytes | None = None


def training_csv() -> bytes:
    """Dataset SINTÉTICO pequeño con el formato que exige el pipeline."""
    global _DATASET_CSV
    if _DATASET_CSV is None:
        from sipd_ml.synthetic import generate_training_dataset

        _DATASET_CSV = generate_training_dataset(400, seed=7).to_csv(index=False).encode("utf-8")
    return _DATASET_CSV


def csv_file(content: bytes, name="entrenamiento.csv"):
    return SimpleUploadedFile(name, content, content_type="text/csv")


class DatasetValidationTests(SimpleTestCase):
    def test_valid_dataset_produces_typed_frame(self):
        report = validate_training_dataset(training_csv().decode(), **VALIDATION)
        self.assertTrue(report.is_valid, report.errors)
        self.assertEqual(report.rows, 400)
        self.assertEqual(set(report.frame["dropout"].unique()), {0, 1})
        self.assertTrue(report.summary["is_synthetic"])

    def test_missing_columns_are_reported(self):
        report = validate_training_dataset("program_code,gpa,dropout\nSIS,3.1,0\n", **VALIDATION)
        self.assertEqual(report.errors[0]["code"], "MISSING_COLUMNS")
        self.assertIn("semester", report.errors[0]["message"])

    def test_types_ranges_and_target(self):
        header = training_csv().decode().splitlines()[0]
        good = training_csv().decode().splitlines()[1].split(",")
        columns = header.split(",")

        def row(**changes):
            values = list(good)
            for key, value in changes.items():
                values[columns.index(key)] = value
            return ",".join(values)

        text = "\n".join([header, row(gpa="abc"), row(attendance_percentage="140"), row(dropout="2"), row(semester="3.5")])
        report = validate_training_dataset(text, **VALIDATION)
        codes = {(e["code"], e["column"]) for e in report.errors}
        self.assertIn(("FORMAT", "gpa"), codes)
        self.assertIn(("FORMAT", "attendance_percentage"), codes)
        self.assertIn(("TARGET", "dropout"), codes)
        self.assertIn(("FORMAT", "semester"), codes)
        self.assertIn("INSUFFICIENT", {e["code"] for e in report.errors})
        self.assertIsNone(report.frame)

    def test_formula_like_values_are_just_invalid_data(self):
        header = training_csv().decode().splitlines()[0]
        values = training_csv().decode().splitlines()[1].split(",")
        values[header.split(",").index("gpa")] = "=cmd|' /C calc'!A0"
        report = validate_training_dataset(header + "\n" + ",".join(values), **VALIDATION)
        self.assertIn(("FORMAT", "gpa"), {(e["code"], e["column"]) for e in report.errors})


@override_settings(ML_TRAINING_EXECUTOR="sync", ML_TRAINING_MIN_ROWS=100, ML_TRAINING_MIN_CLASS_ROWS=10)
class TrainingApiTests(SipdAPITestCase):
    def setUp(self):
        # Cada prueba entrena en una copia: no se tocan los artefactos compartidos.
        self.models_dir = Path(tempfile.mkdtemp(prefix="sipd-retrain-"))
        shutil.copytree(trained_models_dir(), self.models_dir, dirs_exist_ok=True)
        self.dir_override = override_settings(ML_MODELS_DIR=self.models_dir)
        self.dir_override.enable()
        super().setUp()
        self.admin_client = self.client_for(self.admin)
        self.original = ModelVersion.objects.get(active=True)

    def tearDown(self):
        self.dir_override.disable()
        shutil.rmtree(self.models_dir, ignore_errors=True)

    def upload_dataset(self, content=None, name="entrenamiento.csv"):
        with self.captureOnCommitCallbacks(execute=True):
            return self.admin_client.post("/api/training/datasets/", {"file": csv_file(content or training_csv(), name)},
                                          format="multipart")

    def start(self, dataset_id, **extra):
        payload = {"dataset": dataset_id, "algorithms": ["logistic_regression"], "selection_metric": "f1", "confirm": True}
        payload.update(extra)
        with self.captureOnCommitCallbacks(execute=True):
            return self.admin_client.post("/api/training/runs/", payload, format="json")

    # ------------------------------------------------------------------ permisos
    def test_only_admin_can_use_training_endpoints(self):
        dataset = TrainingDataset.objects.create(filename="x.csv", content=b"", checksum="x", status="VALIDO")
        for user in (self.coordinator, self.professor):
            client = self.client_for(user)
            self.assertEqual(client.get("/api/training/overview/").status_code, 403)
            self.assertEqual(client.get("/api/training/runs/").status_code, 403)
            self.assertEqual(client.post("/api/training/datasets/", {"source": "reference"}, format="json").status_code, 403)
            self.assertEqual(client.post("/api/training/runs/", {"dataset": dataset.pk, "algorithms": ["logistic_regression"],
                                                                 "selection_metric": "f1", "confirm": True}, format="json").status_code, 403)
            self.assertEqual(client.post(f"/api/models/{self.original.pk}/approve/").status_code, 403)
            self.assertEqual(client.post(f"/api/models/{self.original.pk}/activate/").status_code, 403)
            self.assertEqual(client.post(f"/api/models/{self.original.pk}/rollback/").status_code, 403)
        self.assertEqual(self.client.get("/api/training/overview/").status_code, 401)
        self.assertFalse(TrainingRun.objects.exists())

    def test_overview_exposes_real_configuration(self):
        data = self.admin_client.get("/api/training/overview/").data
        self.assertTrue(data["config"]["enabled"])
        self.assertIn("dropout", data["config"]["dataset"]["required_columns"])
        self.assertNotIn("approval_rate", data["config"]["dataset"]["required_columns"])
        self.assertEqual(data["config"]["fixed_parameters"]["threshold"], 0.30)
        self.assertEqual(data["active_model"]["id"], self.original.pk)

    # ------------------------------------------------------------------ validación de datos
    def test_rejected_files_notify_the_uploader(self):
        response = self.upload_dataset(b"hola", name="datos.txt")
        self.assertEqual(response.status_code, 422)
        response = self.upload_dataset(b"program_code,gpa,dropout\nSIS,3.0,1\n")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["report"]["errors"][0]["code"], "MISSING_COLUMNS")
        few = b"\n".join(training_csv().splitlines()[:30])
        self.assertEqual(self.upload_dataset(few).data["report"]["errors"][0]["code"], "INSUFFICIENT")
        types = set(Notification.objects.filter(recipient=self.admin).values_list("type", flat=True))
        self.assertEqual(types, {NotificationType.DATASET_REJECTED, NotificationType.DATASET_MISSING_COLUMNS,
                                 NotificationType.DATASET_INSUFFICIENT})
        self.assertEqual(self.start(response.data["id"]).status_code, 400)  # no se entrena con un dataset rechazado

    def test_start_requires_explicit_confirmation_and_valid_options(self):
        dataset_id = self.upload_dataset().data["id"]
        self.assertEqual(self.start(dataset_id, confirm=False).status_code, 400)
        self.assertEqual(self.start(dataset_id, algorithms=["red_neuronal"]).status_code, 400)
        self.assertEqual(self.start(dataset_id, selection_metric="accuracy").status_code, 400)
        self.assertFalse(TrainingRun.objects.exists())

    @override_settings(ML_TRAINING_EXECUTOR="disabled")
    def test_disabled_executor_returns_503(self):
        dataset_id = self.upload_dataset().data["id"]
        response = self.start(dataset_id)
        self.assertEqual(response.status_code, 503)
        self.assertIn("desactivado", response.data["detail"])

    # ------------------------------------------------------------------ flujo completo (entrenamiento real)
    def test_full_retraining_flow(self):
        dataset = self.upload_dataset()
        self.assertEqual(dataset.status_code, 201, dataset.data)
        self.assertEqual(dataset.data["rows"], 400)

        response = self.start(dataset.data["id"])
        self.assertEqual(response.status_code, 202, response.data)
        run = TrainingRun.objects.get(pk=response.data["id"])
        self.assertEqual(run.status, RunStatus.COMPLETED, run.error_message)
        self.assertIsNone(run.in_progress)
        self.assertEqual(run.requested_by, self.admin)
        self.assertEqual([e["status"] for e in run.events],
                         ["PENDIENTE", "VALIDANDO", "PREPARANDO", "ENTRENANDO", "EVALUANDO", "REGISTRANDO", "COMPLETADO"])

        new = run.model_versions.get()
        self.assertEqual(new.approval_status, ApprovalStatus.PENDING)
        self.assertFalse(new.active)
        self.assertTrue(new.acceptance["passed"], new.acceptance)
        self.assertEqual(new.evaluation["dataset"], "test")
        self.assertEqual(new.evaluation["train_size"] + new.evaluation["test_size"], 400)
        self.assertEqual(new.metrics["test_size"], new.evaluation["test_size"])
        self.assertTrue((self.models_dir / new.artifact_dir / "model.joblib").exists())
        # El modelo activo no cambió.
        self.assertEqual(ModelVersion.objects.get(active=True), self.original)

        detail = self.admin_client.get(f"/api/training/runs/{run.pk}/").data
        self.assertEqual(detail["versions"][0]["id"], new.pk)
        comparison = detail["comparisons"][str(new.pk)]
        self.assertFalse(comparison["comparable"])  # datasets distintos: se advierte
        self.assertTrue(comparison["warnings"])

        admin_types = set(Notification.objects.filter(recipient=self.admin).values_list("type", flat=True))
        self.assertTrue({NotificationType.TRAINING_STARTED, NotificationType.TRAINING_COMPLETED,
                         NotificationType.MODEL_EVALUATED} <= admin_types)
        self.assertFalse(Notification.objects.filter(recipient__in=[self.coordinator, self.professor]).exists())

        # Activar sin aprobar no está permitido.
        self.assertEqual(self.admin_client.post(f"/api/models/{new.pk}/activate/").status_code, 409)
        with self.captureOnCommitCallbacks(execute=True):
            approved = self.admin_client.post(f"/api/models/{new.pk}/approve/", {"notes": "Revisado"}, format="json")
        self.assertEqual(approved.status_code, 200, approved.data)
        self.assertEqual(self.admin_client.post(f"/api/models/{new.pk}/approve/").status_code, 409)  # repetido

        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.admin_client.post(f"/api/models/{new.pk}/activate/").status_code, 200)
        self.assertEqual(ModelVersion.objects.get(active=True), new)
        self.assertEqual(self.admin_client.post(f"/api/models/{new.pk}/activate/").status_code, 409)  # ya activo
        log = ModelActivationLog.objects.filter(new_version=new).get()
        self.assertEqual((log.previous_version, log.performed_by), (self.original, self.admin))

        # Las predicciones usan el modelo activo nuevo.
        self.admin_client.post("/api/predictions/", {"student": "E001"}, format="json")
        self.assertEqual(Prediction.objects.latest("prediction_date").model_version, new)

        # Recuperación de la versión anterior.
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.admin_client.post(f"/api/models/{self.original.pk}/rollback/").status_code, 200)
        self.assertEqual(ModelVersion.objects.get(active=True), self.original)
        self.admin_client.post("/api/predictions/", {"student": "E001"}, format="json")
        self.assertEqual(Prediction.objects.latest("prediction_date").model_version, self.original)

        types = set(Notification.objects.filter(recipient=self.admin).values_list("type", flat=True))
        self.assertTrue({NotificationType.MODEL_APPROVED, NotificationType.MODEL_ACTIVATED,
                         NotificationType.MODEL_ROLLED_BACK} <= types)
        actions = set(AuditLog.objects.values_list("action", flat=True))
        self.assertTrue({AuditAction.TRAINING_STARTED, AuditAction.TRAINING_FINISHED, AuditAction.MODEL_APPROVED,
                         AuditAction.MODEL_ACTIVATED, AuditAction.MODEL_ROLLBACK} <= actions)
        history = self.admin_client.get("/api/training/runs/?status=COMPLETADO&algorithm=logistic_regression").data
        self.assertEqual(history["count"], 1)
        # El mismo dataset no se reutiliza por accidente.
        self.assertEqual(self.start(dataset.data["id"]).status_code, 409)

    def test_rejected_version_cannot_be_activated(self):
        run_id = self.start(self.upload_dataset().data["id"]).data["id"]
        new = TrainingRun.objects.get(pk=run_id).model_versions.get()
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.admin_client.post(f"/api/models/{new.pk}/reject/").status_code, 200)
        self.assertEqual(self.admin_client.post(f"/api/models/{new.pk}/activate/").status_code, 409)
        self.assertEqual(ModelVersion.objects.get(active=True), self.original)
        self.assertTrue(Notification.objects.filter(type=NotificationType.MODEL_REJECTED).exists())

    def test_rollback_only_to_previously_active_versions(self):
        run_id = self.start(self.upload_dataset().data["id"]).data["id"]
        new = TrainingRun.objects.get(pk=run_id).model_versions.get()
        self.admin_client.post(f"/api/models/{new.pk}/approve/")
        self.assertEqual(self.admin_client.post(f"/api/models/{new.pk}/rollback/").status_code, 409)

    @override_settings(ML_ACCEPTANCE_MIN_METRICS={"f1": 1.01})
    def test_configured_minimum_blocks_approval(self):
        run_id = self.start(self.upload_dataset().data["id"]).data["id"]
        new = TrainingRun.objects.get(pk=run_id).model_versions.get()
        self.assertFalse(new.acceptance["passed"])
        self.assertEqual(self.admin_client.post(f"/api/models/{new.pk}/approve/").status_code, 409)
        new.refresh_from_db()
        self.assertEqual(new.approval_status, ApprovalStatus.PENDING)

    # ------------------------------------------------------------------ fallos y concurrencia
    def test_failed_training_keeps_active_model(self):
        dataset_id = self.upload_dataset().data["id"]
        with mock.patch("sipd_ml.pipeline.train_candidates", side_effect=RuntimeError("detalle interno /ruta/secreta")):
            response = self.start(dataset_id)
        run = TrainingRun.objects.get(pk=response.data["id"])
        self.assertEqual(run.status, RunStatus.FAILED)
        self.assertNotIn("/ruta/secreta", run.error_message)
        self.assertIsNotNone(run.finished_at)
        self.assertFalse(run.model_versions.exists())
        self.assertEqual(ModelVersion.objects.get(active=True), self.original)
        self.assertTrue(Notification.objects.filter(recipient=self.admin, type=NotificationType.TRAINING_FAILED).exists())
        # Tras un fallo se puede volver a intentar con el mismo dataset.
        self.assertEqual(self.start(dataset_id).status_code, 202)

    def test_tampered_artifacts_are_not_activated(self):
        run_id = self.start(self.upload_dataset().data["id"]).data["id"]
        new = TrainingRun.objects.get(pk=run_id).model_versions.get()
        self.admin_client.post(f"/api/models/{new.pk}/approve/")
        with open(self.models_dir / new.artifact_dir / "model.joblib", "ab") as handle:
            handle.write(b"alterado")
        response = self.admin_client.post(f"/api/models/{new.pk}/activate/")
        self.assertEqual(response.status_code, 409)
        self.assertIn("sumas de verificación", response.data["detail"])
        self.assertEqual(ModelVersion.objects.get(active=True), self.original)

    def test_invalid_artifact_dir_is_rejected(self):
        version = ModelVersion.objects.create(name="X", algorithm="x", version="1", artifact_dir="../fuera",
                                              artifact_checksums={"a": "b"})
        response = self.admin_client.post(f"/api/models/{version.pk}/activate/")
        self.assertEqual(response.status_code, 409)
        self.assertIn("no es válida", response.data["detail"])

    @override_settings(ML_TRAINING_EXECUTOR="worker")
    def test_only_one_run_at_a_time_and_cancel_pending(self):
        first = self.start(self.upload_dataset().data["id"])
        self.assertEqual(first.status_code, 202)
        self.assertEqual(first.data["status"], RunStatus.PENDING)
        second = self.start(self.upload_dataset().data["id"])
        self.assertEqual(second.status_code, 409)
        self.assertEqual(TrainingRun.objects.count(), 1)
        self.assertEqual(self.admin_client.get("/api/training/runs/active/").data["run"]["id"], first.data["id"])
        self.assertEqual(self.admin_client.post(f"/api/training/runs/{first.data['id']}/cancel/").status_code, 200)
        self.assertEqual(self.admin_client.post(f"/api/training/runs/{first.data['id']}/cancel/").status_code, 409)
        self.assertEqual(self.start(self.upload_dataset().data["id"]).status_code, 202)

    @override_settings(ML_TRAINING_EXECUTOR="worker")
    def test_worker_command_executes_pending_run(self):
        from django.core.management import call_command

        run_id = self.start(self.upload_dataset().data["id"]).data["id"]
        call_command("process_training_runs", "--once", stdout=open(Path(self.models_dir) / "out.txt", "w"))
        self.assertEqual(TrainingRun.objects.get(pk=run_id).status, RunStatus.COMPLETED)

    @override_settings(ML_TRAINING_EXECUTOR="worker")
    def test_stale_runs_are_marked_failed(self):
        run_id = self.start(self.upload_dataset().data["id"]).data["id"]
        TrainingRun.objects.filter(pk=run_id).update(status=RunStatus.TRAINING,
                                                     heartbeat_at=timezone.now() - timedelta(hours=1))
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(fail_stale_runs(), 1)
        run = TrainingRun.objects.get(pk=run_id)
        self.assertEqual(run.status, RunStatus.FAILED)
        self.assertIn("interrumpió", run.error_message)
        self.assertEqual(ModelVersion.objects.get(active=True), self.original)

    def test_reference_dataset_source(self):
        with override_settings(ML_REFERENCE_DATASET=self.models_dir / "no-existe.csv"):
            self.assertEqual(self.admin_client.post("/api/training/datasets/", {"source": "reference"}, format="json").status_code, 404)
        reference = self.models_dir / "referencia.csv"
        reference.write_bytes(training_csv())
        with override_settings(ML_REFERENCE_DATASET=reference):
            response = self.admin_client.post("/api/training/datasets/", {"source": "reference"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["is_synthetic"])
        self.assertEqual(response.data["source"], "REFERENCIA")
