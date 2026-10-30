"""
Alertas tempranas (Administrador y Coordinador, dentro de su ámbito). Sólo lectura: las alertas
se gestionan registrando un seguimiento del estudiante (ver alerts.services.sync_with_followup).

  GET /api/alerts/?status=&priority=&reason=&program=&period=&student=&assigned=me|none
  GET /api/alerts/{id}/
  GET /api/alerts/summary/              conteos por estado y alertas recientes
"""
from django.db.models import Case, Count, IntegerField, Q, Value, When
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from students.scoping import scope_queryset
from users.permissions import CanRegisterFollowUp

from .models import Alert, AlertComment, AlertStatus


class AlertCommentSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="author.display_name", read_only=True, allow_null=True)

    class Meta:
        model = AlertComment
        fields = ["id", "author", "text", "created_at"]


class AlertSerializer(serializers.ModelSerializer):
    student_code = serializers.CharField(source="student.anonymous_code", read_only=True)
    program = serializers.CharField(source="student.program.name", read_only=True)
    academic_period = serializers.CharField(source="academic_period.code", read_only=True)
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    assigned_to_name = serializers.CharField(source="assigned_to.display_name", read_only=True, allow_null=True)
    closed_by_name = serializers.CharField(source="closed_by.display_name", read_only=True, allow_null=True)
    change_points = serializers.SerializerMethodField()
    comments_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Alert
        fields = ["id", "student_code", "program", "academic_period", "reason", "reason_display", "priority",
                  "priority_display", "probability", "previous_probability", "change_points", "status", "status_display",
                  "assigned_to", "assigned_to_name", "closed_by_name", "closing_observation", "created_at", "updated_at",
                  "closed_at", "comments_count", "followup"]
        read_only_fields = fields

    def get_change_points(self, alert):
        return None if alert.change is None else round(alert.change * 100, 1)


class AlertDetailSerializer(AlertSerializer):
    comments = AlertCommentSerializer(many=True, read_only=True)

    class Meta(AlertSerializer.Meta):
        fields = AlertSerializer.Meta.fields + ["comments"]
        read_only_fields = fields


class AlertViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [CanRegisterFollowUp]
    filter_backends = []

    def get_serializer_class(self):
        return AlertDetailSerializer if self.action == "retrieve" else AlertSerializer

    def get_queryset(self):
        queryset = scope_queryset(
            Alert.objects.select_related("student__program", "academic_period", "assigned_to", "closed_by")
            .annotate(comments_count=Count("comments")),
            self.request.user, program_field="student__program_id",
        )
        if self.action != "list":
            return queryset.prefetch_related("comments__author")
        params = self.request.query_params
        if params.get("status") == "pending":
            queryset = queryset.exclude(status=AlertStatus.CLOSED)
        elif params.get("status") and params["status"] != "all":
            queryset = queryset.filter(status=params["status"].upper())
        for param, lookup in (("priority", "priority"), ("reason", "reason"),
                              ("program", "student__program__code"), ("period", "academic_period__code")):
            if params.get(param):
                queryset = queryset.filter(**{lookup: params[param].upper()})
        if params.get("student"):
            queryset = queryset.filter(student__anonymous_code=params["student"].upper())
        if params.get("assigned") == "me":
            queryset = queryset.filter(assigned_to=self.request.user)
        elif params.get("assigned") == "none":
            queryset = queryset.filter(assigned_to__isnull=True)
        # Abiertas primero, luego en atención y cerradas; dentro, prioridad y probabilidad.
        status_order = Case(When(status=AlertStatus.OPEN, then=Value(0)), When(status=AlertStatus.IN_PROGRESS, then=Value(1)),
                            default=Value(2), output_field=IntegerField())
        return queryset.order_by(status_order, "priority", "-probability", "-created_at")

    @action(detail=False, methods=["get"])
    def summary(self, request):
        queryset = scope_queryset(Alert.objects.all(), request.user, program_field="student__program_id")
        if request.query_params.get("period"):
            queryset = queryset.filter(academic_period__code=request.query_params["period"])
        counts = queryset.aggregate(
            open=Count("id", filter=Q(status=AlertStatus.OPEN)),
            in_progress=Count("id", filter=Q(status=AlertStatus.IN_PROGRESS)),
            closed=Count("id", filter=Q(status=AlertStatus.CLOSED)),
            unassigned=Count("id", filter=Q(assigned_to__isnull=True) & ~Q(status=AlertStatus.CLOSED)),
            mine=Count("id", filter=Q(assigned_to=request.user) & ~Q(status=AlertStatus.CLOSED)),
        )
        recent = self.get_queryset().exclude(status=AlertStatus.CLOSED).order_by("-created_at")[:5]
        return Response({**counts, "recent": AlertSerializer(recent, many=True).data})
