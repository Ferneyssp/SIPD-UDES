"""
Reentrenamiento desde la interfaz web, aprobación y activación de versiones.

- El entrenamiento usa el MISMO procedimiento que ml/scripts/train.py
  (sipd_ml.pipeline.run_training_pipeline): misma partición, preprocesador,
  algoritmos, métricas y umbral de evaluación.
- Se ejecuta fuera de la petición HTTP (hilo en segundo plano o proceso
  `process_training_runs`, según ML_TRAINING_EXECUTOR).
- Las versiones nuevas se escriben en carpetas propias (nunca se sobrescribe
  una existente) y quedan PENDIENTES de aprobación: no reemplazan al modelo activo.
- Activar = verificar integridad + cargar y probar el modelo + cambiar la
  referencia en BD dentro de una transacción. Si algo falla, sigue activo el anterior.
"""
from __future__ import annotations

import hashlib
import logging
import threading
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.utils import timezone

from audit.models import AuditAction
from audit.services import log_action
from notifications.models import NotificationLevel, NotificationType
from notifications.services import notify, notify_admins

from .models import (
    ACTIVE_RUN_STATUSES,
    ActivationAction,
    ApprovalStatus,
    DatasetSource,
    DatasetStatus,
    ModelActivationLog,
    ModelVersion,
    RunStatus,
    TrainingDataset,
    TrainingRun,
)
from .services import ModelNotAvailableError, artifact_path, clear_cache

logger = logging.getLogger(__name__)
HEARTBEAT_SECONDS = 20


class RunInterrupted(Exception):
    """La ejecución dejó de estar en curso (p. ej. se marcó como interrumpida por falta de latido)."""


class TrainingError(Exception):
    """Error de negocio con un mensaje apto para mostrar al administrador."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------------------- configuración
def executor_mode() -> str:
    return settings.ML_TRAINING_EXECUTOR


def training_enabled() -> bool:
    return executor_mode() in {"thread", "worker", "sync"}


def training_config() -> dict:
    from sipd_ml.config import ALGORITHM_DISPLAY_NAMES, CLASSIFICATION_THRESHOLD, DEFAULT_SELECTION_METRIC, RANDOM_STATE, TEST_SIZE
    from sipd_ml.dataset_validation import OPTIONAL_COLUMNS, REQUIRED_COLUMNS
    from sipd_ml.config import TARGET_COLUMN
    from sipd_ml.evaluation import SELECTION_METRICS
    from sipd_ml.training import available_algorithms

    return {
        "enabled": training_enabled(),
        "executor": executor_mode(),
        "disabled_reason": None if training_enabled() else (
            "El reentrenamiento desde la web está desactivado en este despliegue (ML_TRAINING_EXECUTOR="
            f"{executor_mode()}). En Vercel el disco es efímero y las funciones tienen tiempo máximo: entrene con "
            "ml/scripts/train.py y publique los modelos."
        ),
        "algorithms": [{"value": a, "label": ALGORITHM_DISPLAY_NAMES.get(a, a)} for a in available_algorithms()],
        "selection_metrics": list(SELECTION_METRICS),
        "default_selection_metric": DEFAULT_SELECTION_METRIC,
        "fixed_parameters": {
            "threshold": CLASSIFICATION_THRESHOLD,
            "test_fraction": TEST_SIZE,
            "random_state": RANDOM_STATE,
            "stratified": True,
        },
        "dataset": {
            "required_columns": REQUIRED_COLUMNS,
            "optional_columns": OPTIONAL_COLUMNS,
            "target_column": TARGET_COLUMN,
            "min_rows": settings.ML_TRAINING_MIN_ROWS,
            "min_rows_per_class": settings.ML_TRAINING_MIN_CLASS_ROWS,
            "max_rows": settings.UPLOAD_MAX_ROWS,
            "max_mb": settings.UPLOAD_MAX_BYTES // (1024 * 1024),
        },
        "acceptance_min_metrics": settings.ML_ACCEPTANCE_MIN_METRICS,
    }


# ---------------------------------------------------------------------------- datasets
_REJECTION_TYPES = {
    "MISSING_COLUMNS": NotificationType.DATASET_MISSING_COLUMNS,
    "FORMAT": NotificationType.DATASET_FORMAT_ERRORS,
    "TARGET": NotificationType.DATASET_FORMAT_ERRORS,
    "INSUFFICIENT": NotificationType.DATASET_INSUFFICIENT,
}


def _validate_bytes(raw: bytes):
    from sipd_ml.dataset_validation import DatasetRejected, validate_training_dataset
    from academic.models import Program
    from uploads.validators import FileRejected, decode_content

    try:
        text = decode_content(raw)
        return validate_training_dataset(
            text,
            gpa_min=settings.GPA_MIN, gpa_max=settings.GPA_MAX, max_rows=settings.UPLOAD_MAX_ROWS,
            min_rows=settings.ML_TRAINING_MIN_ROWS, min_rows_per_class=settings.ML_TRAINING_MIN_CLASS_ROWS,
            known_programs=set(Program.objects.values_list("code", flat=True)),
        )
    except (FileRejected, DatasetRejected) as exc:
        from sipd_ml.dataset_validation import DatasetReport

        report = DatasetReport()
        report.error(getattr(exc, "code", "FILE"), str(exc))
        return report


def create_dataset(user, uploaded_file=None, request=None) -> TrainingDataset:
    """Valida y registra un dataset de entrenamiento (CSV cargado). No entrena ni modifica modelos."""
    from uploads.validators import FileRejected, check_file

    if uploaded_file is None:
        raise TrainingError("Seleccione un archivo CSV.")
    filename, source = uploaded_file.name or "archivo.csv", DatasetSource.UPLOAD
    try:
        check_file(uploaded_file)
    except FileRejected as exc:
        # El archivo no se guarda: sólo queda constancia del rechazo.
        from sipd_ml.dataset_validation import DatasetReport

        report = DatasetReport()
        report.error("FILE", str(exc))
        return _save_dataset(user, b"", filename, source, report, request)
    raw = uploaded_file.read()

    return _save_dataset(user, raw, filename, source, _validate_bytes(raw), request)


def _save_dataset(user, raw: bytes, filename: str, source: str, report, request) -> TrainingDataset:
    """Sólo se guarda un dataset válido. Uno rechazado se devuelve sin guardar (sólo para mostrar su informe)."""
    data = report.as_dict()
    dataset = TrainingDataset(
        source=source, filename=filename[:255], content=raw, checksum=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw), rows=report.rows, status=DatasetStatus.VALID if report.is_valid else DatasetStatus.REJECTED,
        report=data, is_synthetic=bool(data["summary"].get("is_synthetic")),
        uploaded_by=user,
    )
    if report.is_valid:
        dataset.save()
    log_action(AuditAction.TRAINING_DATASET, request=request, user=user, entity="TrainingDataset", entity_id=dataset.pk,
               description=f"Dataset {dataset.get_status_display().lower()}",
               metadata={"rows": dataset.rows, "errors": len(data["errors"]), "source": source})
    if not report.is_valid:
        first = data["errors"][0]
        notify([user], _REJECTION_TYPES.get(first["code"], NotificationType.DATASET_REJECTED),
               f"Dataset rechazado: {dataset.filename}", first["message"] + (
                   f" ({len(data['errors'])} problemas en total)." if len(data["errors"]) > 1 else ""),
               level=NotificationLevel.WARNING, link="/reentrenamiento", entity="TrainingDataset")
    return dataset


# ---------------------------------------------------------------------------- ejecuciones
def fail_stale_runs() -> int:
    """Marca como fallidas las ejecuciones sin latido reciente (proceso reiniciado o detenido)."""
    limit = timezone.now() - timedelta(minutes=settings.ML_TRAINING_STALE_MINUTES)
    stale = list(TrainingRun.objects.filter(status__in=ACTIVE_RUN_STATUSES, heartbeat_at__lt=limit))
    for run in stale:
        if run.status == RunStatus.PENDING:
            error = ("La ejecución no comenzó en el tiempo esperado (¿está en marcha el proceso "
                     "process_training_runs?). No se modificó ningún modelo.")
        else:
            error = ("La ejecución se interrumpió (el servidor se reinició o el proceso se detuvo). No se activó "
                     "ninguna versión; puede iniciar un nuevo entrenamiento.")
        _finish(run, RunStatus.FAILED, error=error)
    return len(stale)


def get_active_run() -> TrainingRun | None:
    fail_stale_runs()
    return TrainingRun.objects.filter(status__in=ACTIVE_RUN_STATUSES).select_related("dataset", "requested_by").first()


def start_run(user, dataset: TrainingDataset, algorithms: list[str], selection_metric: str, request=None) -> TrainingRun:
    from sipd_ml.config import CLASSIFICATION_THRESHOLD
    from sipd_ml.evaluation import SELECTION_METRICS
    from sipd_ml.training import available_algorithms

    if not training_enabled():
        raise TrainingError(training_config()["disabled_reason"], 503)
    if dataset.status != DatasetStatus.VALID:
        raise TrainingError("El dataset no superó la validación; corrija los errores y cárguelo de nuevo.")
    supported = available_algorithms()
    algorithms = [a for a in supported if a in set(algorithms or [])]  # orden y valores del procedimiento
    if not algorithms:
        raise TrainingError("Seleccione al menos un algoritmo disponible.")
    if selection_metric not in SELECTION_METRICS:
        raise TrainingError("Métrica de selección no válida.")
    if dataset.runs.exclude(status__in=[RunStatus.FAILED, RunStatus.CANCELLED]).exists():
        raise TrainingError("Este dataset ya se usó en un entrenamiento. Valide de nuevo el archivo si desea repetirlo.", 409)

    fail_stale_runs()
    discard_undecided_versions()  # versiones de entrenamientos anteriores que nunca se aprobaron
    now = timezone.now()
    try:
        with transaction.atomic():
            run = TrainingRun.objects.create(
                dataset=dataset, requested_by=user, algorithms=algorithms, selection_metric=selection_metric,
                threshold=CLASSIFICATION_THRESHOLD, heartbeat_at=now, stage_message="En cola para ejecutarse.",
                events=[{"status": RunStatus.PENDING, "at": now.isoformat(), "message": "Solicitud registrada."}],
            )
    except IntegrityError as exc:
        raise TrainingError("Ya hay un entrenamiento en curso. Espere a que termine antes de iniciar otro.", 409) from exc

    log_action(AuditAction.TRAINING_STARTED, request=request, user=user, entity="TrainingRun", entity_id=run.pk,
               metadata={"algorithms": algorithms, "selection_metric": selection_metric, "dataset": dataset.pk})
    notify_admins(NotificationType.TRAINING_STARTED, f"Reentrenamiento #{run.pk} iniciado",
                  f"{user.username} inició el reentrenamiento con {dataset.rows} registros "
                  f"({', '.join(algorithms)}).", link=f"/reentrenamiento?run={run.pk}", entity="TrainingRun",
                  entity_id=run.pk, dedupe_key=f"run-{run.pk}-started")
    _dispatch(run.pk)
    return run


def _dispatch(run_id: int) -> None:
    mode = executor_mode()
    if mode == "sync":
        execute_run(run_id)
    elif mode == "thread":
        transaction.on_commit(lambda: threading.Thread(target=_execute_in_thread, args=(run_id,), daemon=True,
                                                       name=f"sipd-training-{run_id}").start())
    # worker: el comando process_training_runs toma las ejecuciones pendientes.


def _execute_in_thread(run_id: int) -> None:
    close_old_connections()
    try:
        execute_run(run_id)
    finally:
        connection.close()


def cancel_run(run: TrainingRun, user, request=None) -> TrainingRun:
    """Sólo se cancela una ejecución que aún no empezó: interrumpir un ajuste en curso no es seguro."""
    updated = TrainingRun.objects.filter(pk=run.pk, status=RunStatus.PENDING).update(
        status=RunStatus.CANCELLED, in_progress=None, finished_at=timezone.now(),
        stage_message=f"Cancelado por {user.username} antes de iniciar.",
    )
    if not updated:
        raise TrainingError("Sólo puede cancelarse un entrenamiento que todavía no ha comenzado.", 409)
    log_action(AuditAction.TRAINING_CANCELLED, request=request, user=user, entity="TrainingRun", entity_id=run.pk)
    run.refresh_from_db()
    return run


def _set_stage(run: TrainingRun, status: str, message: str) -> None:
    now = timezone.now()
    run.status, run.stage_message, run.heartbeat_at = status, message[:255], now
    run.events = [*run.events, {"status": status, "at": now.isoformat(), "message": message}]
    updated = TrainingRun.objects.filter(pk=run.pk, status__in=ACTIVE_RUN_STATUSES).update(
        status=status, stage_message=run.stage_message, heartbeat_at=now, events=run.events,
    )
    if not updated:
        raise RunInterrupted()


def _finish(run: TrainingRun, status: str, error: str = "", message: str = "") -> bool:
    """Cierra la ejecución sólo si sigue en curso; devuelve False si ya estaba cerrada."""
    now = timezone.now()
    text = message or error
    events = [*run.events, {"status": status, "at": now.isoformat(), "message": text}]
    updated = TrainingRun.objects.filter(pk=run.pk, status__in=ACTIVE_RUN_STATUSES).update(
        status=status, in_progress=None, finished_at=now, heartbeat_at=now, error_message=error[:500],
        stage_message=text[:255], events=events,
    )
    if not updated:
        return False
    run.status, run.error_message, run.finished_at, run.events = status, error[:500], now, events
    if status == RunStatus.FAILED:
        log_action(AuditAction.TRAINING_FINISHED, user=run.requested_by, entity="TrainingRun", entity_id=run.pk,
                   description="Entrenamiento fallido", metadata={"status": status})
        notify_admins(NotificationType.TRAINING_FAILED, f"Reentrenamiento #{run.pk} fallido", error[:300],
                      level=NotificationLevel.ERROR, link=f"/reentrenamiento?run={run.pk}", entity="TrainingRun",
                      entity_id=run.pk, dedupe_key=f"run-{run.pk}-failed")
    return True


class _Heartbeat:
    """Actualiza heartbeat_at mientras el entrenamiento ocupa el hilo principal de la ejecución."""

    def __init__(self, run_id: int):
        self.run_id = run_id
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._beat, daemon=True)

    def _beat(self):
        try:
            while not self.stop.wait(HEARTBEAT_SECONDS):
                TrainingRun.objects.filter(pk=self.run_id, status__in=ACTIVE_RUN_STATUSES).update(heartbeat_at=timezone.now())
        finally:
            connection.close()

    def __enter__(self):
        if executor_mode() != "sync":
            self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stop.set()


def _new_version_label(models_dir: Path) -> str:
    label = timezone.localtime().strftime("%Y%m%d%H%M%S")
    while any(models_dir.glob(f"*_{label}")):
        label = str(int(label) + 1)
    return label


def execute_run(run_id: int) -> None:
    """Ejecuta una ejecución PENDIENTE. Toda excepción deja la ejecución en FALLIDO y el modelo activo intacto."""
    from sipd_ml.config import ALGORITHM_DISPLAY_NAMES
    from sipd_ml.pipeline import run_training_pipeline

    claimed = TrainingRun.objects.filter(pk=run_id, status=RunStatus.PENDING).update(
        status=RunStatus.VALIDATING, started_at=timezone.now(), heartbeat_at=timezone.now(),
    )
    if not claimed:
        return  # ya la tomó otro proceso o fue cancelada
    run = TrainingRun.objects.select_related("dataset", "requested_by").get(pk=run_id)
    stage = {"current": RunStatus.VALIDATING}

    def on_stage(name, algorithm=None, position=None, total=None):
        label = ALGORITHM_DISPLAY_NAMES.get(algorithm, algorithm)
        if name == "preparing":
            stage["current"] = RunStatus.PREPARING
            _set_stage(run, RunStatus.PREPARING, "Preparando datos: variables derivadas, partición estratificada "
                                                 "entrenamiento/prueba y ajuste del preprocesador.")
        elif name == "training":
            stage["current"] = RunStatus.TRAINING
            _set_stage(run, RunStatus.TRAINING, f"Entrenando {label} ({position} de {total}).")
        elif name == "evaluating":
            stage["current"] = RunStatus.EVALUATING
            _set_stage(run, RunStatus.EVALUATING, f"Evaluando {label} en el conjunto de prueba ({position} de {total}).")
        elif name == "saving":
            stage["current"] = RunStatus.REGISTERING
            _set_stage(run, RunStatus.REGISTERING, "Guardando artefactos versionados y registrando las versiones.")

    try:
        with _Heartbeat(run.pk):
            _set_stage(run, RunStatus.VALIDATING, "Verificando la integridad y validez del dataset.")
            dataset = run.dataset
            raw = bytes(dataset.content)
            if hashlib.sha256(raw).hexdigest() != dataset.checksum:
                raise TrainingError("El dataset almacenado no coincide con el validado (suma de verificación distinta).")
            report = _validate_bytes(raw)
            if not report.is_valid:
                raise TrainingError("El dataset ya no supera la validación: " + report.errors[0]["message"])

            models_dir = Path(settings.ML_MODELS_DIR)
            version = _new_version_label(models_dir)
            TrainingRun.objects.filter(pk=run.pk).update(version=version)
            summary = run_training_pipeline(
                report.frame, algorithms=run.algorithms, selection_metric=run.selection_metric, models_dir=models_dir,
                version=version, threshold=run.threshold, publish_default=False, on_stage=on_stage,
                extra_metadata={"training_run_id": run.pk, "dataset_sha256": dataset.checksum,
                                "dataset_source": dataset.source},
            )
            versions = _register_versions(run, summary)
    except RunInterrupted:
        logger.warning("El entrenamiento #%s dejó de estar en curso; se detiene sin registrar resultados.", run.pk)
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Falló el entrenamiento #%s en la etapa %s", run.pk, stage["current"])
        message = str(exc) if isinstance(exc, (TrainingError, ValueError)) else (
            "Error inesperado durante el entrenamiento. El detalle quedó en el registro del servidor.")
        if stage["current"] in (RunStatus.VALIDATING, RunStatus.PREPARING):
            notify_admins(NotificationType.DATA_PREPARATION_ERROR, f"Error en la preparación de datos (#{run.pk})",
                          message[:300], level=NotificationLevel.ERROR, link=f"/reentrenamiento?run={run.pk}",
                          entity="TrainingRun", entity_id=run.pk, dedupe_key=f"run-{run.pk}-prep-error")
        _finish(run, RunStatus.FAILED, error=f"Etapa {RunStatus(stage['current']).label.lower()}: {message}")
        return

    TrainingRun.objects.filter(pk=run.pk).update(ranking=summary["ranking"], selected_algorithm=summary["selected_algorithm"])
    passed = [v for v in versions if v.acceptance.get("passed")]
    if not _finish(run, RunStatus.COMPLETED, message=f"Entrenamiento completado: {len(versions)} versiones evaluadas, "
                                                     f"{len(passed)} cumplen los criterios de aceptación."):
        return
    log_action(AuditAction.TRAINING_FINISHED, user=run.requested_by, entity="TrainingRun", entity_id=run.pk,
               description="Entrenamiento completado", metadata={"version": version, "versions": len(versions)})
    link = f"/reentrenamiento?run={run.pk}"
    notify_admins(NotificationType.TRAINING_COMPLETED, f"Reentrenamiento #{run.pk} completado",
                  f"Versión {version}: {len(versions)} modelos entrenados y evaluados. Ninguno se activó "
                  "automáticamente; revise la evaluación para aprobar o rechazar.", level=NotificationLevel.SUCCESS,
                  link=link, entity="TrainingRun", entity_id=run.pk, dedupe_key=f"run-{run.pk}-completed")
    for item in versions:
        metrics = item.metrics
        notify_admins(NotificationType.MODEL_EVALUATED, f"Nueva versión evaluada: {item}",
                      f"Prueba: F1 {metrics.get('f1')}, Recall {metrics.get('recall')}, ROC-AUC {metrics.get('roc_auc')}. "
                      + ("Cumple los criterios de aceptación." if item.acceptance.get("passed")
                         else "No cumple los criterios de aceptación."),
                      link=link, entity="ModelVersion", entity_id=item.pk, dedupe_key=f"version-{item.pk}-evaluated")


def _register_versions(run: TrainingRun, summary: dict) -> list[ModelVersion]:
    from sipd_ml.persistence import artifact_checksums, load_metadata

    from .services import _version_fields

    versions = []
    with transaction.atomic():
        for algorithm, directory in summary["saved_dirs"].items():
            directory = Path(directory)
            metadata = load_metadata(directory)
            version = ModelVersion.objects.create(
                algorithm=algorithm, version=metadata["version"], training_run=run,
                approval_status=ApprovalStatus.PENDING, artifact_checksums=artifact_checksums(directory),
                **_version_fields(directory, metadata),
            )
            versions.append(version)
    for version in versions:
        version.acceptance = evaluate_acceptance(version)
        ModelVersion.objects.filter(pk=version.pk).update(acceptance=version.acceptance)
    return versions


# ---------------------------------------------------------------------------- integridad y aceptación
def verify_artifacts(version: ModelVersion):
    """Comprueba ubicación, sumas SHA-256, metadatos y que el modelo cargue y prediga.
    Sólo se cargan artefactos generados por el propio sistema dentro de ML_MODELS_DIR."""
    from sipd_ml.inference import RiskPredictor
    from sipd_ml.persistence import ARTIFACT_FILENAMES, artifact_checksums

    directory = artifact_path(version.artifact_dir)
    missing = [name for name in ARTIFACT_FILENAMES if not (directory / name).is_file()]
    if missing:
        raise ModelNotAvailableError(f"Faltan artefactos de la versión: {', '.join(missing)}.")
    if not version.artifact_checksums:
        raise ModelNotAvailableError("La versión no tiene sumas de verificación registradas; sincronice los modelos.")
    if artifact_checksums(directory) != version.artifact_checksums:
        raise ModelNotAvailableError("Los artefactos fueron modificados después de registrarse (sumas de verificación distintas).")
    try:
        predictor = RiskPredictor.from_directory(directory)
        probability = predictor.predict_proba([{}])[0]  # fila vacía: todas las variables imputadas
    except Exception as exc:  # noqa: BLE001
        logger.exception("No se pudo cargar la versión %s", version.pk)
        raise ModelNotAvailableError("Los artefactos no se pudieron cargar con la versión instalada de las bibliotecas.") from exc
    if predictor.metadata.get("algorithm") != version.algorithm or str(predictor.metadata.get("version")) != version.version:
        raise ModelNotAvailableError("Los metadatos de los artefactos no corresponden a la versión registrada.")
    if not 0 <= probability <= 1:
        raise ModelNotAvailableError("El modelo produjo una probabilidad fuera del rango 0-1.")
    return predictor


def evaluate_acceptance(version: ModelVersion) -> dict:
    """Criterios de aceptación. Los técnicos son obligatorios; los mínimos de métricas sólo se aplican si la
    institución los configuró (ML_ACCEPTANCE_MIN_*): el proyecto no define umbrales de rendimiento aprobados."""
    from sipd_ml.config import MODEL_FEATURES
    from sipd_ml.persistence import load_metadata

    checks = []
    metrics = version.metrics or {}
    required = ("accuracy", "precision", "recall", "f1", "roc_auc")
    missing = [m for m in required if not isinstance(metrics.get(m), (int, float))]
    checks.append({"code": "metrics", "label": "Métricas calculadas en el conjunto de prueba", "passed": not missing,
                   "detail": "Faltan: " + ", ".join(missing) if missing else "Accuracy, Precision, Recall, F1 y ROC-AUC."})
    matrix = metrics.get("confusion_matrix") or {}
    both = matrix.get("tp", 0) + matrix.get("fn", 0) > 0 and matrix.get("tn", 0) + matrix.get("fp", 0) > 0
    checks.append({"code": "test_classes", "label": "El conjunto de prueba contiene ambas clases", "passed": both,
                   "detail": f"Casos positivos: {matrix.get('tp', 0) + matrix.get('fn', 0)}, "
                             f"negativos: {matrix.get('tn', 0) + matrix.get('fp', 0)}."})
    try:
        features = load_metadata(artifact_path(version.artifact_dir)).get("features")
        compatible = features == MODEL_FEATURES
        detail = "Mismas variables que usa el servicio de predicción." if compatible else "Las variables no coinciden."
    except Exception:  # noqa: BLE001
        compatible, detail = False, "No se pudieron leer los metadatos."
    checks.append({"code": "features", "label": "Compatibilidad con el servicio de predicción", "passed": compatible,
                   "detail": detail})
    try:
        verify_artifacts(version)
        checks.append({"code": "artifacts", "label": "Artefactos íntegros y cargables", "passed": True,
                       "detail": "Sumas SHA-256 verificadas y predicción de prueba correcta."})
    except ModelNotAvailableError as exc:
        checks.append({"code": "artifacts", "label": "Artefactos íntegros y cargables", "passed": False, "detail": str(exc)})
    for metric, minimum in settings.ML_ACCEPTANCE_MIN_METRICS.items():
        value = metrics.get(metric)
        checks.append({"code": f"min_{metric}", "label": f"{metric} ≥ {minimum} (criterio institucional configurado)",
                       "passed": isinstance(value, (int, float)) and value >= minimum, "detail": f"Valor obtenido: {value}."})
    return {
        "passed": all(c["passed"] for c in checks),
        "checks": checks,
        "metric_minimums_configured": bool(settings.ML_ACCEPTANCE_MIN_METRICS),
        "evaluated_at": timezone.now().isoformat(),
    }


COMPARED_METRICS = ("accuracy", "precision", "recall", "f1", "roc_auc")


def compare_versions(new: ModelVersion, reference: ModelVersion | None) -> dict | None:
    """Compara métricas de prueba. Sólo son comparables si se evaluaron con el mismo umbral y la misma
    partición del mismo dataset; si no, se informa la limitación (las diferencias se muestran como orientativas)."""
    if reference is None:
        return None
    warnings = []
    new_eval, ref_eval = new.evaluation or {}, reference.evaluation or {}
    if new.metrics.get("threshold") != reference.metrics.get("threshold"):
        warnings.append("Se evaluaron con umbrales de clasificación distintos.")
    new_sha, ref_sha = _dataset_sha(new), _dataset_sha(reference)
    if not new_sha or not ref_sha:
        warnings.append("No consta el dataset de evaluación de una de las versiones: no se puede verificar que el "
                        "conjunto de prueba sea el mismo.")
    elif new_sha != ref_sha:
        warnings.append("Se entrenaron y evaluaron con datasets distintos: las métricas no son directamente comparables.")
    if new_eval.get("test_fraction") != ref_eval.get("test_fraction") or new_eval.get("random_state") != ref_eval.get("random_state"):
        if new_eval and ref_eval:
            warnings.append("La partición entrenamiento/prueba fue distinta.")
    rows = []
    for metric in COMPARED_METRICS:
        before, after = reference.metrics.get(metric), new.metrics.get(metric)
        diff = round(after - before, 4) if isinstance(before, (int, float)) and isinstance(after, (int, float)) else None
        rows.append({"metric": metric, "reference": before, "new": after, "difference": diff})
    return {
        "reference": {"id": reference.pk, "label": str(reference), "active": reference.active},
        "comparable": not warnings,
        "warnings": warnings,
        "rows": rows,
    }


def _dataset_sha(version: ModelVersion) -> str | None:
    if version.training_run_id:
        return version.training_run.dataset.checksum
    try:
        from sipd_ml.persistence import load_metadata

        return load_metadata(artifact_path(version.artifact_dir)).get("dataset_sha256")
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------- aprobación y activación
def discard_version(version: ModelVersion) -> None:
    """Elimina una versión no aprobada (artefactos y registro). Sólo se guardan los modelos aprobados:
    una versión aprobada, heredada o que haya estado activa nunca se borra."""
    import shutil

    if version.approval_status != ApprovalStatus.PENDING or version.active \
            or ModelActivationLog.objects.filter(new_version=version).exists():
        raise TrainingError("Sólo pueden descartarse versiones pendientes de aprobación.", 409)
    try:
        shutil.rmtree(artifact_path(version.artifact_dir), ignore_errors=True)
    except ModelNotAvailableError:
        logger.warning("Ubicación no válida para la versión %s; se elimina sólo el registro.", version.pk)
    version.delete()


def discard_undecided_versions(exclude_run=None) -> int:
    """Descarta las versiones pendientes de entrenamientos anteriores que nunca se aprobaron."""
    pending = ModelVersion.objects.filter(approval_status=ApprovalStatus.PENDING, active=False)
    if exclude_run is not None:
        pending = pending.exclude(training_run=exclude_run)
    count = 0
    for version in pending:
        try:
            discard_version(version)
            count += 1
        except TrainingError:
            continue
    return count


def review_version(version: ModelVersion, user, approve: bool, notes: str = "", request=None) -> ModelVersion | None:
    """Aprobar guarda la versión como disponible; rechazar la elimina por completo (devuelve None)."""
    if version.approval_status != ApprovalStatus.PENDING:
        raise TrainingError(f"La versión ya está en estado «{version.get_approval_status_display()}».", 409)
    acceptance = evaluate_acceptance(version)  # se recalcula: los artefactos pudieron cambiar desde el entrenamiento
    ModelVersion.objects.filter(pk=version.pk).update(acceptance=acceptance)
    if approve and not acceptance["passed"]:
        raise TrainingError("La versión no cumple los criterios de aceptación; no puede aprobarse.", 409)
    label, version_id, link = str(version), version.pk, _version_link(version)
    with transaction.atomic():
        version = ModelVersion.objects.select_for_update().get(pk=version.pk)
        if version.approval_status != ApprovalStatus.PENDING:
            raise TrainingError(f"La versión ya está en estado «{version.get_approval_status_display()}».", 409)
        if approve:
            version.acceptance = acceptance
            version.approval_status = ApprovalStatus.APPROVED
            version.approved_by, version.approved_at, version.approval_notes = user, timezone.now(), notes[:500]
            version.save(update_fields=["approval_status", "approved_by", "approved_at", "approval_notes", "acceptance"])
        else:
            discard_version(version)  # los modelos rechazados no se guardan
            version = None
    log_action(AuditAction.MODEL_APPROVED if approve else AuditAction.MODEL_REJECTED, request=request, user=user,
               entity="ModelVersion", entity_id=version_id, description=label)
    notify_admins(NotificationType.MODEL_APPROVED if approve else NotificationType.MODEL_REJECTED,
                  f"Modelo {'aprobado' if approve else 'rechazado'}: {label}",
                  f"Revisado por {user.username}." + (" Puede activarse cuando lo decida." if approve else
                                                      " La versión rechazada se eliminó."),
                  level=NotificationLevel.SUCCESS if approve else NotificationLevel.WARNING,
                  link=link, entity="ModelVersion", entity_id=version_id,
                  dedupe_key=f"version-{version_id}-reviewed")
    return version


def _version_link(version: ModelVersion) -> str:
    return f"/reentrenamiento?run={version.training_run_id}" if version.training_run_id else "/reentrenamiento"


def activate_version(version: ModelVersion, user, *, rollback: bool = False, request=None) -> ModelVersion:
    if not version.can_be_activated:
        raise TrainingError("Sólo pueden activarse versiones aprobadas.", 409)
    if rollback and not ModelActivationLog.objects.filter(new_version=version).exists():
        raise TrainingError("Sólo puede recuperarse una versión que haya estado activa anteriormente.", 409)
    # 1) Verificación fuera de la transacción: si falla, nada cambia y sigue activo el modelo anterior.
    try:
        verify_artifacts(version)
    except ModelNotAvailableError as exc:
        raise TrainingError(f"No se activó la versión: {exc}", 409) from exc
    # 2) Cambio de referencia atómico. Las predicciones en curso conservan el modelo que ya cargaron.
    with transaction.atomic():
        locked = list(ModelVersion.objects.select_for_update().order_by("pk"))
        target = next(v for v in locked if v.pk == version.pk)
        previous = next((v for v in locked if v.active), None)
        if target.active:
            raise TrainingError("Esta versión ya es el modelo activo.", 409)
        if not target.can_be_activated:
            raise TrainingError("Sólo pueden activarse versiones aprobadas.", 409)
        target.activate()
        ModelActivationLog.objects.create(
            action=ActivationAction.ROLLBACK if rollback else ActivationAction.ACTIVATION,
            previous_version=previous, new_version=target, previous_label=str(previous) if previous else "",
            new_label=str(target), performed_by=user,
        )
        transaction.on_commit(clear_cache)
    log_action(AuditAction.MODEL_ROLLBACK if rollback else AuditAction.MODEL_ACTIVATED, request=request, user=user,
               entity="ModelVersion", entity_id=target.pk, description=str(target),
               metadata={"previous": str(previous) if previous else None})
    notify_admins(NotificationType.MODEL_ROLLED_BACK if rollback else NotificationType.MODEL_ACTIVATED,
                  f"{'Versión recuperada' if rollback else 'Modelo activado'}: {target}",
                  f"{user.username} cambió el modelo activo de {previous or '—'} a {target}. "
                  "Las nuevas predicciones usarán esta versión.", level=NotificationLevel.SUCCESS,
                  link=_version_link(target), entity="ModelVersion", entity_id=target.pk)
    return target


def rollback_candidates():
    previous_ids = ModelActivationLog.objects.exclude(new_version=None).values_list("new_version_id", flat=True)
    return ModelVersion.objects.filter(pk__in=previous_ids, active=False)
