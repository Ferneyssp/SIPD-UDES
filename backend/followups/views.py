from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from academic.models import AcademicPeriod
from audit.models import AuditAction
from audit.services import log_action
from students.scoping import allowed_program_ids, scope_queryset
from users.models import Role, User
from users.permissions import CanRegisterFollowUp

from .models import FollowUp
from .serializers import FollowUpSerializer


class FollowUpViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                      mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Seguimiento/intervenciones. No se eliminan registros para conservar trazabilidad.

    Filtros: student (código), status, user (id responsable), intervention_type, period, date_from, date_to.
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
        responsible = serializer.validated_data.get("user") or self.request.user
        period = serializer.validated_data.get("academic_period") or AcademicPeriod.get_current()
        followup = serializer.save(user=responsible, created_by=self.request.user, academic_period=period)
        log_action(AuditAction.FOLLOWUP_CREATED, request=self.request, entity="FollowUp", entity_id=followup.pk,
                   metadata={"student": followup.student.anonymous_code, "status": followup.status})

    def perform_update(self, serializer):
        followup = serializer.instance
        user = self.request.user
        if user.role == Role.PROFESSOR and user not in (followup.user, followup.created_by):
            raise PermissionDenied("Sólo el responsable o quien registró el seguimiento puede editarlo.")
        followup = serializer.save()
        log_action(AuditAction.FOLLOWUP_UPDATED, request=self.request, entity="FollowUp", entity_id=followup.pk,
                   metadata={"status": followup.status})


class ResponsibleUsersView(APIView):
    """Usuarios activos que pueden figurar como responsables de un seguimiento."""

    permission_classes = [CanRegisterFollowUp]

    def get(self, request):
        users = User.objects.filter(is_active=True).order_by("first_name", "username")
        program_ids = allowed_program_ids(request.user)
        if program_ids is not None:
            users = users.filter(
                Q(programs__id__in=program_ids) | Q(pk=request.user.pk) | Q(role__in=[Role.COORDINATOR, Role.ADMIN])
            )
        return Response([
            {"id": u.id, "name": u.display_name, "role": u.get_role_display()} for u in users.distinct()
        ])
