from django.conf import settings
from django.db import models, transaction
from django.db.models import Q


class ApprovalStatus(models.TextChoices):
    PENDING = "PENDIENTE", "Pendiente de aprobación"
    APPROVED = "APROBADO", "Aprobado"
    REJECTED = "RECHAZADO", "Rechazado"
    # Versiones entrenadas offline (ml/scripts/train.py) y registradas con sync_models.
    NOT_REQUIRED = "NO_REQUERIDA", "Registrado sin flujo de aprobación"


class ModelVersion(models.Model):
    """Versión registrada de un modelo entrenado (artefactos en backend/ml_models/<dir>)."""

    name = models.CharField(max_length=80)
    algorithm = models.CharField(max_length=40)
    version = models.CharField(max_length=40)
    metrics = models.JSONField(default=dict)
    trained_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=False)
    artifact_dir = models.CharField(max_length=255, help_text="Nombre de la carpeta dentro de ML_MODELS_DIR")
    is_synthetic = models.BooleanField(default=False, help_text="Entrenado con datos sintéticos")
    selection_metric = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Reentrenamiento y aprobación
    training_run = models.ForeignKey("ml.TrainingRun", null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="model_versions")
    selected = models.BooleanField(default=False, help_text="Mejor candidato según la métrica de selección")
    dataset_rows = models.PositiveIntegerField(null=True, blank=True)
    evaluation = models.JSONField(default=dict, blank=True, help_text="Conjunto y procedimiento de evaluación")
    artifact_checksums = models.JSONField(default=dict, blank=True, help_text="SHA-256 de cada artefacto")
    approval_status = models.CharField(max_length=15, choices=ApprovalStatus.choices, default=ApprovalStatus.NOT_REQUIRED)
    acceptance = models.JSONField(default=dict, blank=True, help_text="Resultado de los criterios de aceptación")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="approved_model_versions")
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-trained_at", "name"]
        constraints = [models.UniqueConstraint(fields=["algorithm", "version"], name="unique_model_version")]
        verbose_name = "versión de modelo"

    def __str__(self) -> str:
        return f"{self.name} v{self.version}"

    @property
    def can_be_activated(self) -> bool:
        return self.approval_status in (ApprovalStatus.APPROVED, ApprovalStatus.NOT_REQUIRED)

    @transaction.atomic
    def activate(self):
        ModelVersion.objects.exclude(pk=self.pk).update(active=False)
        self.active = True
        self.save(update_fields=["active"])


class DatasetSource(models.TextChoices):
    UPLOAD = "CARGA", "Archivo CSV cargado"
    REFERENCE = "REFERENCIA", "Dataset de referencia del proyecto (sintético)"


class DatasetStatus(models.TextChoices):
    VALID = "VALIDO", "Válido"
    REJECTED = "RECHAZADO", "Rechazado"


class TrainingDataset(models.Model):
    """Conjunto de datos validado para reentrenar. El contenido se guarda en BD (con su SHA-256)
    para entrenar exactamente con lo que se validó."""

    source = models.CharField(max_length=12, choices=DatasetSource.choices, default=DatasetSource.UPLOAD)
    filename = models.CharField(max_length=255)
    content = models.BinaryField(editable=False)
    checksum = models.CharField(max_length=64)
    size_bytes = models.PositiveIntegerField(default=0)
    rows = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=DatasetStatus.choices)
    report = models.JSONField(default=dict, blank=True, help_text="Errores, advertencias y resumen de la validación")
    is_synthetic = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                    related_name="training_datasets")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "dataset de entrenamiento"

    def __str__(self) -> str:
        return f"{self.filename} ({self.get_status_display()})"


class RunStatus(models.TextChoices):
    PENDING = "PENDIENTE", "Pendiente"
    VALIDATING = "VALIDANDO", "Validando datos"
    PREPARING = "PREPARANDO", "Preparando datos"
    TRAINING = "ENTRENANDO", "Entrenando"
    EVALUATING = "EVALUANDO", "Evaluando"
    REGISTERING = "REGISTRANDO", "Registrando versiones"
    COMPLETED = "COMPLETADO", "Completado"
    FAILED = "FALLIDO", "Fallido"
    CANCELLED = "CANCELADO", "Cancelado"


ACTIVE_RUN_STATUSES = [RunStatus.PENDING, RunStatus.VALIDATING, RunStatus.PREPARING, RunStatus.TRAINING,
                       RunStatus.EVALUATING, RunStatus.REGISTERING]
FINISHED_RUN_STATUSES = [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED]


class TrainingRun(models.Model):
    """Ejecución persistente del procedimiento de entrenamiento (sipd_ml.pipeline)."""

    dataset = models.ForeignKey(TrainingDataset, on_delete=models.PROTECT, related_name="runs")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                     related_name="training_runs")
    status = models.CharField(max_length=12, choices=RunStatus.choices, default=RunStatus.PENDING)
    stage_message = models.CharField(max_length=255, blank=True)
    events = models.JSONField(default=list, blank=True, help_text="Etapas recorridas con su hora")
    algorithms = models.JSONField(default=list)
    selection_metric = models.CharField(max_length=20)
    threshold = models.FloatField()
    version = models.CharField(max_length=40, blank=True)
    selected_algorithm = models.CharField(max_length=40, blank=True)
    ranking = models.JSONField(default=list, blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    # True mientras la ejecución está en curso; la restricción única impide dos ejecuciones simultáneas.
    in_progress = models.BooleanField(null=True, default=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["in_progress"], condition=Q(in_progress=True), name="single_training_run_in_progress"),
        ]
        verbose_name = "ejecución de entrenamiento"

    def __str__(self) -> str:
        return f"Entrenamiento #{self.pk} ({self.get_status_display()})"

    @property
    def is_finished(self) -> bool:
        return self.status in FINISHED_RUN_STATUSES


class ActivationAction(models.TextChoices):
    INITIAL = "INICIAL", "Activación inicial (registro de modelos)"
    ACTIVATION = "ACTIVACION", "Activación"
    ROLLBACK = "RECUPERACION", "Recuperación de versión anterior"


class ModelActivationLog(models.Model):
    """Historial de cambios del modelo activo (no se borra)."""

    action = models.CharField(max_length=12, choices=ActivationAction.choices)
    previous_version = models.ForeignKey(ModelVersion, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    new_version = models.ForeignKey(ModelVersion, null=True, on_delete=models.SET_NULL, related_name="activations")
    previous_label = models.CharField(max_length=130, blank=True)
    new_label = models.CharField(max_length=130)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="model_activations")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "cambio de modelo activo"

    def __str__(self) -> str:
        return f"{self.get_action_display()}: {self.previous_label or '—'} → {self.new_label}"
