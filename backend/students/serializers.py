from rest_framework import serializers

from academic.models import AcademicRecord, Program
from academic.serializers import AcademicRecordSerializer
from config.risk import RiskLevel
from followups.models import FollowUpStatus

from .models import Student


class StudentListSerializer(serializers.ModelSerializer):
    program = serializers.CharField(source="program.name", read_only=True)
    program_code = serializers.CharField(source="program.code", read_only=True)
    current_probability = serializers.FloatField(read_only=True, allow_null=True)
    current_risk_percentage = serializers.SerializerMethodField()
    current_risk_level = serializers.CharField(read_only=True, allow_null=True)
    current_risk_level_display = serializers.SerializerMethodField()
    current_prediction_date = serializers.DateTimeField(read_only=True, allow_null=True)
    current_prediction_period = serializers.CharField(read_only=True, allow_null=True)
    current_prediction_id = serializers.IntegerField(read_only=True, allow_null=True)
    latest_followup_status = serializers.CharField(read_only=True, allow_null=True)
    latest_followup_status_display = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            "id", "anonymous_code", "program", "program_code", "semester", "academic_status", "is_active",
            "current_prediction_id", "current_probability", "current_risk_percentage", "current_risk_level",
            "current_risk_level_display", "current_prediction_date", "current_prediction_period",
            "latest_followup_status", "latest_followup_status_display",
        ]

    def get_current_risk_percentage(self, obj):
        value = getattr(obj, "current_probability", None)
        return None if value is None else round(value * 100, 1)

    def get_current_risk_level_display(self, obj):
        level = getattr(obj, "current_risk_level", None)
        return RiskLevel(level).label if level else None

    def get_latest_followup_status_display(self, obj):
        status = getattr(obj, "latest_followup_status", None)
        return FollowUpStatus(status).label if status else "Sin seguimiento"


class StudentWriteSerializer(serializers.ModelSerializer):
    program = serializers.SlugRelatedField(slug_field="code", queryset=Program.objects.filter(is_active=True))

    class Meta:
        model = Student
        fields = ["id", "anonymous_code", "program", "semester", "academic_status", "is_active"]

    def to_internal_value(self, data):
        if isinstance(data, dict) and isinstance(data.get("anonymous_code"), str):
            data = {**data, "anonymous_code": data["anonymous_code"].strip().upper()}
        return super().to_internal_value(data)


class StudentDetailSerializer(StudentListSerializer):
    academic_records = serializers.SerializerMethodField()
    current_period = serializers.CharField(source="current_period.code", read_only=True, allow_null=True)

    class Meta(StudentListSerializer.Meta):
        fields = StudentListSerializer.Meta.fields + ["current_period", "academic_records", "created_at", "updated_at"]

    def get_academic_records(self, obj):
        records = AcademicRecord.objects.filter(student=obj).select_related("academic_period").order_by("-academic_period__code")
        return AcademicRecordSerializer(records, many=True).data
