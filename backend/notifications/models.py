from django.conf import settings
from django.db import models
from django.db.models import Q


class NotificationType(models.TextChoices):
    # Administración de modelos
    TRAINING_STARTED = "TRAINING_STARTED", "Inicio del reentrenamiento"
    TRAINING_COMPLETED = "TRAINING_COMPLETED", "Reentrenamiento finalizado"
    TRAINING_FAILED = "TRAINING_FAILED", "Fallo del reentrenamiento"
    MODEL_EVALUATED = "MODEL_EVALUATED", "Nueva versión evaluada"
    MODEL_APPROVED = "MODEL_APPROVED", "Modelo aprobado"
    MODEL_REJECTED = "MODEL_REJECTED", "Modelo rechazado"
    MODEL_ACTIVATED = "MODEL_ACTIVATED", "Activación de una versión"
    MODEL_ROLLED_BACK = "MODEL_ROLLED_BACK", "Recuperación de una versión anterior"
    # Validación de datos
    DATASET_REJECTED = "DATASET_REJECTED", "Archivo rechazado"
    DATASET_MISSING_COLUMNS = "DATASET_MISSING_COLUMNS", "Columnas obligatorias ausentes"
    DATASET_FORMAT_ERRORS = "DATASET_FORMAT_ERRORS", "Problemas de formato"
    DATASET_INSUFFICIENT = "DATASET_INSUFFICIENT", "Datos insuficientes"
    DATA_PREPARATION_ERROR = "DATA_PREPARATION_ERROR", "Error durante la preparación de datos"
    UPLOAD_REJECTED = "UPLOAD_REJECTED", "Carga académica rechazada"
    # Predicciones
    PREDICTIONS_COMPLETED = "PREDICTIONS_COMPLETED", "Proceso de predicción finalizado"
    # Alertas tempranas
    ALERTS_CREATED = "ALERTS_CREATED", "Nuevas alertas tempranas"
    ALERT_ASSIGNED = "ALERT_ASSIGNED", "Alerta asignada"


CATEGORY_TYPES = {
    "MODELOS": [NotificationType.TRAINING_STARTED, NotificationType.TRAINING_COMPLETED, NotificationType.TRAINING_FAILED,
                NotificationType.MODEL_EVALUATED, NotificationType.MODEL_APPROVED, NotificationType.MODEL_REJECTED,
                NotificationType.MODEL_ACTIVATED, NotificationType.MODEL_ROLLED_BACK],
    "DATOS": [NotificationType.DATASET_REJECTED, NotificationType.DATASET_MISSING_COLUMNS,
              NotificationType.DATASET_FORMAT_ERRORS, NotificationType.DATASET_INSUFFICIENT,
              NotificationType.DATA_PREPARATION_ERROR, NotificationType.UPLOAD_REJECTED],
    "PREDICCIONES": [NotificationType.PREDICTIONS_COMPLETED],
    "ALERTAS": [NotificationType.ALERTS_CREATED, NotificationType.ALERT_ASSIGNED],
}
CATEGORY_LABELS = {"MODELOS": "Administración de modelos", "DATOS": "Validación de datos", "PREDICCIONES": "Predicciones",
                   "ALERTAS": "Alertas tempranas"}


class NotificationLevel(models.TextChoices):
    INFO = "INFO", "Información"
    SUCCESS = "SUCCESS", "Éxito"
    WARNING = "WARNING", "Advertencia"
    ERROR = "ERROR", "Error"


class Notification(models.Model):
    """Aviso persistente para un usuario. Nunca incluye datos personales ni trazas internas."""

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=30, choices=NotificationType.choices)
    level = models.CharField(max_length=10, choices=NotificationLevel.choices, default=NotificationLevel.INFO)
    title = models.CharField(max_length=150)
    message = models.CharField(max_length=500, blank=True)
    link = models.CharField(max_length=200, blank=True, help_text="Ruta interna del frontend (p. ej. /reentrenamiento?run=3)")
    entity = models.CharField(max_length=60, blank=True)
    entity_id = models.CharField(max_length=60, blank=True)
    # Evita duplicados del mismo acontecimiento para un mismo destinatario.
    dedupe_key = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["recipient", "read_at"])]
        constraints = [
            models.UniqueConstraint(fields=["recipient", "dedupe_key"], condition=~Q(dedupe_key=""),
                                    name="unique_notification_event_per_recipient"),
        ]
        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"

    def __str__(self) -> str:
        return f"{self.recipient_id} {self.type} {self.title}"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    @property
    def category(self) -> str:
        return next((name for name, types in CATEGORY_TYPES.items() if self.type in types), "")
