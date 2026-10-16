from django.db import models, transaction


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

    class Meta:
        ordering = ["-trained_at", "name"]
        constraints = [models.UniqueConstraint(fields=["algorithm", "version"], name="unique_model_version")]
        verbose_name = "versión de modelo"

    def __str__(self) -> str:
        return f"{self.name} v{self.version}"

    @transaction.atomic
    def activate(self):
        ModelVersion.objects.exclude(pk=self.pk).update(active=False)
        self.active = True
        self.save(update_fields=["active"])
