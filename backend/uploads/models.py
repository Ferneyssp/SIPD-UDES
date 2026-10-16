from django.conf import settings
from django.db import models


class UploadStatus(models.TextChoices):
    VALIDATED = "VALIDADO", "Validado (pendiente de confirmar)"
    REJECTED = "RECHAZADO", "Rechazado"
    PROCESSED = "PROCESADO", "Procesado"
    FAILED = "FALLIDO", "Fallido"


class DataUpload(models.Model):
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="uploads")
    file = models.FileField(upload_to="uploads/%Y/%m/")
    # Copia del CSV en BD: en despliegues serverless (Vercel) el disco no persiste entre peticiones.
    content = models.BinaryField(null=True, blank=True, editable=False)
    filename = models.CharField(max_length=255)
    checksum = models.CharField(max_length=64)
    records_found = models.PositiveIntegerField(default=0)
    records_valid = models.PositiveIntegerField(default=0)
    records_failed = models.PositiveIntegerField(default=0)
    records_processed = models.PositiveIntegerField(default=0)
    predictions_generated = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=15, choices=UploadStatus.choices, default=UploadStatus.VALIDATED)
    run_predictions = models.BooleanField(default=True)
    message = models.CharField(max_length=500, blank=True)
    upload_date = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-upload_date"]
        verbose_name = "carga de datos"

    def __str__(self) -> str:
        return f"{self.filename} ({self.get_status_display()})"
