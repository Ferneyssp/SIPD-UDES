from rest_framework import serializers

from .models import Prediction


class PredictionSerializer(serializers.ModelSerializer):
    student_code = serializers.CharField(source="student.anonymous_code", read_only=True)
    student_id = serializers.IntegerField(source="student.id", read_only=True)
    program = serializers.CharField(source="student.program.name", read_only=True)
    semester = serializers.IntegerField(source="academic_record.semester", read_only=True, allow_null=True)
    academic_period = serializers.CharField(source="academic_period.code", read_only=True)
    risk_percentage = serializers.FloatField(read_only=True)
    risk_level_display = serializers.CharField(source="get_risk_level_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    created_by = serializers.CharField(source="created_by.username", read_only=True, allow_null=True)

    class Meta:
        model = Prediction
        fields = [
            "id", "student_id", "student_code", "program", "semester", "academic_period", "model_name",
            "model_version_label", "probability", "risk_percentage", "risk_level", "risk_level_display",
            "status", "status_display", "prediction_date", "created_by",
        ]


class PredictionDetailSerializer(PredictionSerializer):
    class Meta(PredictionSerializer.Meta):
        fields = PredictionSerializer.Meta.fields + ["input_features", "explanation"]


class PredictionRequestSerializer(serializers.Serializer):
    student = serializers.CharField(help_text="Código anonimizado, p. ej. E001")
    academic_period = serializers.CharField(required=False, help_text="Si se omite, se usa el último periodo con datos")


class BatchPredictionRequestSerializer(serializers.Serializer):
    academic_period = serializers.CharField()
    program = serializers.CharField(required=False, allow_blank=True)
