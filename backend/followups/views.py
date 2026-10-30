from django.db.models import OuterRef, Subquery
from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from academic.models import AcademicPeriod
from alerts.services import sync_with_followup
from audit.models import AuditAction
from audit.services import log_action
from students.models import Student
from students.scoping import allowed_program_ids, eligible_responsibles, scope_queryset, user_can_access_student
from users.models import Role, User
from users.permissions import CanRegisterFollowUp

from .models import FollowUp
from .serializers import FollowUpSerializer


class FollowUpViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                      mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Seguimiento/intervenciones. No se eliminan registros para conservar trazabilidad.

    Filtros: student (código), status, user (id responsable), intervention_type, period, date_from, date_to,
    latest=true (sólo el último seguimiento de cada estudiante, como en el módulo Seguimiento).
    """

    serializer_class = FollowUpSerializer
    permission_classes = [CanRegisterFollowUp]
    search_fields = ["student__anonymous_code", "observation"]
    ordering_fields = ["follow_up_date", "created_at", "status"]

    def get_queryset(self):
        params = self.request.query_params
        queryset = scope_queryset(
            FollowUp.objects.select_related("student__program", "user", "created_by", "academic_period"),
            self.request.user,
            program_field="student__program_id",
        )
        if self.action == "list" and params.get("latest") == "true":
            # Un registro por estudiante: su último seguimiento (estado actual). El resto es historial.
            latest = FollowUp.objects.filter(student=OuterRef("student")).order_by("-follow_up_date", "-created_at", "-id")
            queryset = queryset.filter(pk=Subquery(latest.values("pk")[:1]))
        filters = {
            "student": ("student__anonymous_code__startswith", str.upper),
            "student_exact": ("student__anonymous_code", str.upper),
            "status": ("status", str),
            "user": ("user_id", str),
            "intervention_type": ("intervention_type", str),
            "period": ("academic_period__code", str),
            "date_from": ("follow_up_date__gte", str),
            "date_to": ("follow_up_date__lte", str),
        }
        for param, (lookup, cast) in filters.items():
            if params.get(param):
                queryset = queryset.filter(**{lookup: cast(params[param])})
        return queryset

    def perform_create(self, serializer):
        period = serializer.validated_data.get("academic_period") or AcademicPeriod.get_current()
        followup = serializer.save(created_by=self.request.user, academic_period=period)
        sync_with_followup(followup, self.request.user)
        log_action(AuditAction.FOLLOWUP_CREATED, request=self.request, entity="FollowUp", entity_id=followup.pk,
                   metadata={"student": followup.student.anonymous_code, "status": followup.status})

    def perform_update(self, serializer):
        followup = serializer.save()
        sync_with_followup(followup, self.request.user)
        log_action(AuditAction.FOLLOWUP_UPDATED, request=self.request, entity="FollowUp", entity_id=followup.pk,
                   metadata={"status": followup.status})


class ResponsibleUsersView(APIView):
    """Posibles responsables: coordinadores con acceso al programa del estudiante (?student=E001).
    Sin estudiante: coordinadores que comparten algún programa con quien consulta. Nunca administradores."""

    permission_classes = [CanRegisterFollowUp]

    def get(self, request):
        users = User.objects.filter(is_active=True)
        code = request.query_params.get("student", "").upper()
        if code:
            student = get_object_or_404(Student, anonymous_code=code)
            if not user_can_access_student(request.user, student):
                return Response({"detail": "No tiene acceso a este estudiante."}, status=403)
            users = eligible_responsibles(student.program_id, users)
        else:
            program_ids = allowed_program_ids(request.user)
            users = users.filter(role=Role.COORDINATOR, programs__isnull=False)
            if program_ids is not None:
                users = users.filter(programs__id__in=program_ids)
        users = users.distinct().order_by("first_name", "username")
        return Response([
            {"id": u.id, "name": u.display_name, "role": u.get_role_display()} for u in users.distinct()
        ])
