from django.conf import settings
from rest_framework import serializers

from .models import AcademicPeriod, AcademicRecord, Program


class ProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = ["id", "code", "name", "is_active"]


class AcademicPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicPeriod
        fields = ["id", "code", "year", "term", "start_date", "end_date", "is_current"]
        read_only_fields = ["year", "term"]


class AcademicRecordSerializer(serializers.ModelSerializer):
    academic_period = serializers.SlugRelatedField(slug_field="code", queryset=AcademicPeriod.objects.all())
    approval_rate = serializers.FloatField(read_only=True)

    class Meta:
        model = AcademicRecord
        fields = [
            "id", "academic_period", "semester", "academic_status", "gpa", "credits_enrolled", "credits_approved",
            "credits_failed", "failed_subjects", "attendance_percentage", "course_repetitions", "approval_rate",
            "works_while_studying", "socioeconomic_stratum", "financial_difficulty", "motivation_level",
            "extra_survey_data", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_gpa(self, value):
        if not settings.GPA_MIN <= float(value) <= settings.GPA_MAX:
            raise serializers.ValidationError(f"El promedio debe estar entre {settings.GPA_MIN} y {settings.GPA_MAX}.")
        return value

    def validate(self, attrs):
        enrolled = attrs.get("credits_enrolled", getattr(self.instance, "credits_enrolled", 0))
        approved = attrs.get("credits_approved", getattr(self.instance, "credits_approved", 0))
        failed = attrs.get("credits_failed", getattr(self.instance, "credits_failed", 0))
        if approved + failed > enrolled:
            raise serializers.ValidationError("Créditos aprobados + reprobados no puede superar los matriculados.")
        return attrs
