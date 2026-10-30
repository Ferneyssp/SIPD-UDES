from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

ANONYMOUS_CODE_REGEX = r"^E\d{3,}$"


class AcademicStatus(models.TextChoices):
    ACTIVE = "Activo", "Activo"
    INACTIVE = "Inactivo", "Inactivo"
    WITHDRAWN = "Retirado", "Retirado"
    GRADUATED = "Graduado", "Graduado"


class Student(models.Model):
    """Estudiante identificado ÚNICAMENTE por un código seudonimizado (p. ej. E001).
    No se almacenan nombres ni documentos de identidad."""

    anonymous_code = models.CharField(
        "código anonimizado",
        max_length=12,
        unique=True,
        validators=[RegexValidator(ANONYMOUS_CODE_REGEX, "El código debe tener el formato E001.")],
    )
    program = models.ForeignKey("academic.Program", on_delete=models.PROTECT, related_name="students")
    semester = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    academic_status = models.CharField(max_length=30, choices=AcademicStatus.choices, default=AcademicStatus.ACTIVE)
    current_period = models.ForeignKey(
        "academic.AcademicPeriod", null=True, blank=True, on_delete=models.SET_NULL, related_name="current_students"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["anonymous_code"]
        verbose_name = "estudiante"

    def __str__(self) -> str:
        return self.anonymous_code

    def latest_record(self):
        return self.academic_records.select_related("academic_period").order_by("-academic_period__code").first()
