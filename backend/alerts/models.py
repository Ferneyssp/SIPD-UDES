from django.conf import settings
from django.db import models


class AlertReason(models.TextChoices):
    HIGH_LEVEL = "NIVEL_ALTO", "Nivel de riesgo estimado Alto"
    RISE = "AUMENTO", "Aumento del riesgo estimado respecto a la predicción anterior"
    HIGH_AND_RISE = "ALTO_Y_AUMENTO", "Nivel Alto con aumento respecto a la predicción anterior"


class AlertPriority(models.TextChoices):
    HIGH = "ALTA", "Alta"
    MEDIUM = "MEDIA", "Media"


class AlertStatus(models.TextChoices):
    OPEN = "ABIERTA", "Abierta"
    IN_PROGRESS = "EN_ATENCION", "En atención"
    CLOSED = "CERRADA", "Cerrada"


class Alert(models.Model):
    """Alerta temprana generada al registrar una predicción. Una por estudiante y periodo:
    las predicciones repetidas del mismo periodo actualizan el motivo, no duplican la alerta."""

    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="alerts")
    academic_period = models.ForeignKey("academic.AcademicPeriod", on_delete=models.PROTECT, related_name="alerts")
    prediction = models.ForeignKey("predictions.Prediction", null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="alerts")
    reason = models.CharField(max_length=20, choices=AlertReason.choices)
    priority = models.CharField(max_length=10, choices=AlertPriority.choices)
    probability = models.FloatField(help_text="Probabilidad estimada que originó la alerta")
    previous_probability = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=AlertStatus.choices, default=AlertStatus.OPEN)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="assigned_alerts")
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="closed_alerts")
    closing_observation = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    # Seguimiento con el que se gestiona la alerta (la alerta no se gestiona por separado).
    followup = models.ForeignKey("followups.FollowUp", null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="alerts")

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["student", "academic_period"], name="one_alert_per_student_period")]
        indexes = [models.Index(fields=["status", "priority"])]
        verbose_name = "alerta temprana"

    def __str__(self) -> str:
        return f"{self.student} {self.academic_period} {self.get_status_display()}"

    @property
    def change(self):
        if self.previous_probability is None:
            return None
        return round(self.probability - self.previous_probability, 4)


class AlertComment(models.Model):
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
