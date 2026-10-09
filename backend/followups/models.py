from django.conf import settings
from django.db import models
from django.utils import timezone


class FollowUpStatus(models.TextChoices):
    PENDING = "PENDIENTE", "Pendiente"
    IN_PROGRESS = "EN_SEGUIMIENTO", "En seguimiento"
    ATTENDED = "ATENDIDO", "Atendido"
    CLOSED = "CERRADO", "Cerrado"


class InterventionType(models.TextChoices):
    TUTORING = "TUTORIA", "Tutoría académica"
    PHONE_CALL = "LLAMADA", "Llamada telefónica"
    WELLBEING = "BIENESTAR", "Remisión a bienestar"
    GUARDIAN_MEETING = "ACUDIENTE", "Reunión con acudiente"
    FINANCIAL = "FINANCIERO", "Apoyo financiero"
    COUNSELING = "CONSEJERIA", "Consejería académica"
    OTHER = "OTRO", "Otro"


class FollowUp(models.Model):
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="followups")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="followups_responsible",
        verbose_name="usuario responsable",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="followups_created"
    )
    academic_period = models.ForeignKey(
        "academic.AcademicPeriod", null=True, blank=True, on_delete=models.SET_NULL, related_name="followups"
    )
    intervention_type = models.CharField(max_length=20, choices=InterventionType.choices, default=InterventionType.TUTORING)
    status = models.CharField(max_length=20, choices=FollowUpStatus.choices, default=FollowUpStatus.PENDING)
    observation = models.TextField(max_length=2000)
    follow_up_date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-follow_up_date", "-created_at"]
        verbose_name = "seguimiento"

    def __str__(self) -> str:
        return f"{self.student} - {self.get_status_display()}"
