from rest_framework import serializers

from academic.models import AcademicPeriod
from students.models import Student
from students.scoping import user_can_access_student
from users.models import User

from .models import FollowUp


class FollowUpSerializer(serializers.ModelSerializer):
    student = serializers.SlugRelatedField(slug_field="anonymous_code", queryset=Student.objects.filter(is_active=True))
    student_id = serializers.IntegerField(source="student.id", read_only=True)
    program = serializers.CharField(source="student.program.name", read_only=True)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True), required=False)
    user_name = serializers.CharField(source="user.display_name", read_only=True)
    user_role = serializers.CharField(source="user.get_role_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.display_name", read_only=True, allow_null=True)
    academic_period = serializers.SlugRelatedField(
        slug_field="code", queryset=AcademicPeriod.objects.all(), required=False, allow_null=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    intervention_type_display = serializers.CharField(source="get_intervention_type_display", read_only=True)

    class Meta:
        model = FollowUp
        fields = [
            "id", "student", "student_id", "program", "user", "user_name", "user_role", "created_by_name",
            "academic_period", "intervention_type", "intervention_type_display", "status", "status_display",
            "observation", "follow_up_date", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_student(self, student):
        if not user_can_access_student(self.context["request"].user, student):
            raise serializers.ValidationError("No tiene acceso a este estudiante.")
        return student

    def validate_observation(self, value):
        value = value.strip()
        if len(value) < 5:
            raise serializers.ValidationError("La observación debe tener al menos 5 caracteres.")
        return value
