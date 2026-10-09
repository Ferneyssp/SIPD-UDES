from django.conf import settings
from django.db import models

from config.risk import RiskLevel


class PredictionStatus(models.TextChoices):
    CURRENT = "VIGENTE", "Vigente"
    SUPERSEDED = "REEMPLAZADA", "Reemplazada"


class Prediction(models.Model):
    """Resultado del modelo para un estudiante y periodo.

    Las predicciones NUNCA se sobrescriben: una nueva ejecución crea un
    registro nuevo y la anterior del mismo periodo pasa a 'Reemplazada'.
    """

    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="predictions")
    academic_record = models.ForeignKey(
        "academic.AcademicRecord", null=True, blank=True, on_delete=models.SET_NULL, related_name="predictions"
    )
    academic_period = models.ForeignKey("academic.AcademicPeriod", on_delete=models.PROTECT, related_name="predictions")
    model_version = models.ForeignKey(
        "ml.ModelVersion", null=True, blank=True, on_delete=models.SET_NULL, related_name="predictions"
    )
    model_name = models.CharField(max_length=80)
    model_version_label = models.CharField(max_length=40)
    probability = models.FloatField()
    risk_level = models.CharField(max_length=10, choices=RiskLevel.choices)
    status = models.CharField(max_length=15, choices=PredictionStatus.choices, default=PredictionStatus.CURRENT)
    input_features = models.JSONField(default=dict)
    explanation = models.JSONField(default=list)
    prediction_date = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="predictions_run"
    )

    class Meta:
        ordering = ["-prediction_date"]
        indexes = [
            models.Index(fields=["student", "academic_period", "status"]),
            models.Index(fields=["risk_level", "status"]),
        ]
        verbose_name = "predicción"
        verbose_name_plural = "predicciones"

    def __str__(self) -> str:
        return f"{self.student} {self.academic_period} {self.risk_percentage}%"

    @property
    def risk_percentage(self) -> float:
        return round(self.probability * 100, 1)
