from django.conf import settings
from django.db import models


class AuditAction(models.TextChoices):
    LOGIN = "LOGIN", "Inicio de sesión"
    LOGIN_FAILED = "LOGIN_FAILED", "Inicio de sesión fallido"
    LOGOUT = "LOGOUT", "Cierre de sesión"
    PASSWORD_CHANGED = "PASSWORD_CHANGED", "Cambio de contraseña"
    DATA_UPLOAD = "DATA_UPLOAD", "Carga de datos"
    PREDICTION_RUN = "PREDICTION_RUN", "Ejecución de predicciones"
    MODEL_ACTIVATED = "MODEL_ACTIVATED", "Activación de modelo"
    USER_CREATED = "USER_CREATED", "Creación de usuario"
    USER_UPDATED = "USER_UPDATED", "Modificación de usuario"
    USER_DEACTIVATED = "USER_DEACTIVATED", "Desactivación de usuario"
    STUDENT_CHANGED = "STUDENT_CHANGED", "Modificación de estudiante"
    FOLLOWUP_CREATED = "FOLLOWUP_CREATED", "Registro de seguimiento"
    FOLLOWUP_UPDATED = "FOLLOWUP_UPDATED", "Actualización de seguimiento"


class AuditLog(models.Model):
    """Registro de acciones relevantes. No guarda contraseñas, tokens ni datos académicos."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_logs")
    username = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=30, choices=AuditAction.choices)
    entity = models.CharField(max_length=60, blank=True)
    entity_id = models.CharField(max_length=60, blank=True)
    description = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "registro de auditoría"

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.username} {self.action}"
