from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

PERIOD_CODE_REGEX = r"^\d{4}-[12]$"
_LOOKUP = object()


class Program(models.Model):
    code = models.CharField("código", max_length=10, unique=True)
    name = models.CharField("nombre", max_length=150)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "programa"

    def __str__(self) -> str:
        return self.name


class AcademicPeriod(models.Model):
    code = models.CharField(
        "código",
        max_length=6,
        unique=True,
        validators=[RegexValidator(PERIOD_CODE_REGEX, "Formato esperado AAAA-1 o AAAA-2.")],
    )
    year = models.PositiveSmallIntegerField()
    term = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(2)])
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField("periodo actual", default=False)

    class Meta:
        ordering = ["-code"]
        verbose_name = "periodo académico"

    def save(self, *args, **kwargs):
        self.year, self.term = (int(part) for part in self.code.split("-"))
        super().save(*args, **kwargs)
        if self.is_current:
            AcademicPeriod.objects.exclude(pk=self.pk).filter(is_current=True).update(is_current=False)

    @classmethod
    def get_current(cls):
        return cls.objects.filter(is_current=True).first() or cls.objects.order_by("-code").first()

    def __str__(self) -> str:
        return self.code


class AcademicRecord(models.Model):
    """Información académica de un estudiante en un periodo concreto."""

    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="academic_records")
    academic_period = models.ForeignKey(AcademicPeriod, on_delete=models.PROTECT, related_name="academic_records")
    semester = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    academic_status = models.CharField(max_length=30)
    gpa = models.DecimalField("promedio", max_digits=4, decimal_places=2)
    credits_enrolled = models.PositiveSmallIntegerField()
    credits_approved = models.PositiveSmallIntegerField()
    credits_failed = models.PositiveSmallIntegerField()
    failed_subjects = models.PositiveSmallIntegerField(default=0)
    attendance_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    course_repetitions = models.PositiveSmallIntegerField(default=0)

    # Variables de encuestas / instrumentos institucionales (opcionales)
    works_while_studying = models.BooleanField(null=True, blank=True)
    socioeconomic_stratum = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(6)]
    )
    financial_difficulty = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    motivation_level = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    extra_survey_data = models.JSONField(default=dict, blank=True, help_text="Otras variables de instrumentos.")

    source_upload = models.ForeignKey(
        "uploads.DataUpload", null=True, blank=True, on_delete=models.SET_NULL, related_name="academic_records"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["student", "-academic_period__code"]
        constraints = [
            models.UniqueConstraint(fields=["student", "academic_period"], name="unique_record_per_student_period"),
        ]
        verbose_name = "registro académico"

    def __str__(self) -> str:
        return f"{self.student} - {self.academic_period}"

    @property
    def approval_rate(self):
        if not self.credits_enrolled:
            return None
        return round(self.credits_approved / self.credits_enrolled, 4)

    def previous_record(self):
        return (
            AcademicRecord.objects.filter(student_id=self.student_id, academic_period__code__lt=self.academic_period.code)
            .order_by("-academic_period__code")
            .first()
        )

    def to_model_input(self, previous=_LOOKUP) -> dict:
        """Datos crudos que el servicio de inferencia transforma en variables.
        `previous` = registro del periodo anterior (None si no existe). Si no se
        indica, se consulta en la base de datos."""
        if previous is _LOOKUP:
            previous = self.previous_record()
        return {
            "program_code": self.student.program.code,
            "semester": self.semester,
            "gpa": float(self.gpa),
            "previous_gpa": float(previous.gpa) if previous else None,
            "credits_enrolled": self.credits_enrolled,
            "credits_approved": self.credits_approved,
            "credits_failed": self.credits_failed,
            "failed_subjects": self.failed_subjects,
            "attendance_percentage": float(self.attendance_percentage),
            "course_repetitions": self.course_repetitions,
            "works_while_studying": None if self.works_while_studying is None else int(self.works_while_studying),
            "socioeconomic_stratum": self.socioeconomic_stratum,
            "financial_difficulty": self.financial_difficulty,
            "motivation_level": self.motivation_level,
        }


def gpa_bounds() -> tuple[float, float]:
    return settings.GPA_MIN, settings.GPA_MAX
