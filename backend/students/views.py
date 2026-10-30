from django.db.models import F
from django.shortcuts import get_object_or_404
from django.conf import settings
from rest_framework import viewsets
from rest_framework.decorators import action

from audit.models import AuditAction
from audit.services import log_action

from .models import Student
from .queries import annotate_current_risk, filter_by_followup_status
from .scoping import scope_queryset
from .serializers import StudentDetailSerializer, StudentListSerializer


class StudentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Consulta de estudiantes (sólo lectura, según el ámbito de cada rol). Los datos de los
    estudiantes se crean y actualizan únicamente con la carga CSV validada (uploads), que deja
    trazabilidad de cada registro; no hay edición manual.

    Filtros: program (código), semester, academic_status, risk_level, period, followup_status, search.
    Orden: ?ordering=-current_probability | anonymous_code | semester
    """

    search_fields = ["anonymous_code", "program__name", "program__code"]
    # current_probability se ordena manualmente en get_queryset (nulos al final)
    ordering_fields = ["anonymous_code", "semester", "current_prediction_date"]
    filterset_fields = []

    def get_serializer_class(self):
        if self.action == "retrieve":
            return StudentDetailSerializer
        return StudentListSerializer

    def get_queryset(self):
        params = self.request.query_params
        queryset = scope_queryset(Student.objects.select_related("program", "current_period"), self.request.user)
        if params.get("include_inactive") != "true":
            queryset = queryset.filter(is_active=True)
        if params.get("program"):
            queryset = queryset.filter(program__code=params["program"])
        if params.get("semester"):
            queryset = queryset.filter(semester=params["semester"])
        if params.get("academic_status"):
            queryset = queryset.filter(academic_status=params["academic_status"])
        queryset = annotate_current_risk(queryset, params.get("period"))
        if params.get("risk_level"):
            queryset = queryset.filter(current_risk_level=params["risk_level"].upper())
        queryset = filter_by_followup_status(queryset, params.get("followup_status"))
        if params.get("trend") == "up":
            queryset = queryset.filter(risk_change__gt=0)
        elif params.get("trend") == "down":
            queryset = queryset.filter(risk_change__lt=0)
        if params.get("alert") == "open":
            queryset = queryset.filter(open_alert_status__isnull=False)
        # Por defecto, de mayor a menor riesgo estimado (lista de trabajo priorizada).
        ordering = params.get("ordering") or "-current_probability"
        field = ordering.lstrip("-")
        if field in {"current_probability", "risk_change"}:
            descending = ordering.startswith("-")
            order = F(field).desc(nulls_last=True) if descending else F(field).asc(nulls_last=True)
            return queryset.order_by(order, "anonymous_code")
        return queryset

    def retrieve(self, request, *args, **kwargs):
        """Cada apertura de una ficha queda en la bitácora (quién consultó a qué estudiante y cuándo)."""
        response = super().retrieve(request, *args, **kwargs)
        log_action(AuditAction.STUDENT_VIEWED, request=request, entity="Student", entity_id=response.data["anonymous_code"])
        return response

    def get_object(self):
        """Permite /api/students/E001/ además de /api/students/15/."""
        lookup = self.kwargs["pk"]
        queryset = self.get_queryset()
        field = {"anonymous_code": lookup.upper()} if not str(lookup).isdigit() else {"pk": lookup}
        obj = get_object_or_404(queryset, **field)
        self.check_object_permissions(self.request, obj)
        return obj

    @action(detail=False, methods=["get"])
    def export(self, request):
        """CSV del listado con los mismos filtros y ámbito que la vista (sin datos socioeconómicos)."""
        from reports.views import _csv_response

        header = [("anonymous_code", "Código seudonimizado"), ("program", "Programa"), ("semester", "Semestre"),
                  ("academic_status", "Estado académico"), ("period", "Periodo de la predicción"),
                  ("probability", "Probabilidad estimada"), ("risk_level", "Nivel de riesgo estimado"),
                  ("change", "Cambio vs. periodo anterior (puntos)"), ("alert", "Alerta abierta"),
                  ("followup", "Estado de seguimiento")]
        serializer = StudentListSerializer()

        def rows():
            for student in self.filter_queryset(self.get_queryset())[: settings.REPORT_EXPORT_MAX_ROWS].iterator():
                yield {
                    "anonymous_code": student.anonymous_code, "program": student.program.name, "semester": student.semester,
                    "academic_status": student.academic_status, "period": student.current_prediction_period,
                    "probability": None if student.current_probability is None else round(student.current_probability, 4),
                    "risk_level": serializer.get_current_risk_level_display(student),
                    "change": serializer.get_risk_change_points(student),
                    "alert": bool(student.open_alert_status),
                    "followup": serializer.get_latest_followup_status_display(student),
                }

        filters = {k: v for k, v in request.query_params.items()}
        return _csv_response(request, "estudiantes", header, rows(), filters)
