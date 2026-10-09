from django.db.models import F
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from academic.serializers import AcademicRecordSerializer
from audit.models import AuditAction
from audit.services import log_action
from users.permissions import IsAdminOrReadOnly

from .models import Student
from .queries import annotate_current_risk, filter_by_followup_status
from .scoping import scope_queryset
from .serializers import StudentDetailSerializer, StudentListSerializer, StudentWriteSerializer


class StudentViewSet(viewsets.ModelViewSet):
    """
    Consulta de estudiantes (todos los roles, según su ámbito).
    Creación/edición: sólo Administrador. DELETE = desactivación lógica.

    Filtros: program (código), semester, academic_status, risk_level, period, followup_status, search.
    Orden: ?ordering=-current_probability | anonymous_code | semester
    """

    permission_classes = [IsAdminOrReadOnly]
    search_fields = ["anonymous_code", "program__name", "program__code"]
    # current_probability se ordena manualmente en get_queryset (nulos al final)
    ordering_fields = ["anonymous_code", "semester", "current_prediction_date"]
    filterset_fields = []

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return StudentWriteSerializer
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
        if params.get("ordering", "").lstrip("-") == "current_probability":
            descending = params["ordering"].startswith("-")
            order = F("current_probability").desc(nulls_last=True) if descending else F("current_probability").asc(nulls_last=True)
            return queryset.order_by(order, "anonymous_code")
        return queryset

    def get_object(self):
        """Permite /api/students/E001/ además de /api/students/15/."""
        lookup = self.kwargs["pk"]
        queryset = self.get_queryset()
        field = {"anonymous_code": lookup.upper()} if not str(lookup).isdigit() else {"pk": lookup}
        obj = get_object_or_404(queryset, **field)
        self.check_object_permissions(self.request, obj)
        return obj

    def perform_create(self, serializer):
        student = serializer.save()
        log_action(AuditAction.STUDENT_CHANGED, request=self.request, entity="Student", entity_id=student.anonymous_code,
                   description="Estudiante creado")

    def perform_update(self, serializer):
        student = serializer.save()
        log_action(AuditAction.STUDENT_CHANGED, request=self.request, entity="Student", entity_id=student.anonymous_code,
                   metadata={"fields": sorted(serializer.validated_data)})

    def destroy(self, request, *args, **kwargs):
        student = self.get_object()
        Student.objects.filter(pk=student.pk).update(is_active=False)
        log_action(AuditAction.STUDENT_CHANGED, request=request, entity="Student", entity_id=student.anonymous_code,
                   description="Estudiante desactivado")
        return Response({"detail": "Estudiante desactivado."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="records")
    def add_record(self, request, pk=None):
        """Registra/actualiza la información académica de un periodo (Administrador)."""
        student = self.get_object()
        existing = student.academic_records.filter(academic_period__code=request.data.get("academic_period")).first()
        serializer = AcademicRecordSerializer(instance=existing, data=request.data)
        serializer.is_valid(raise_exception=True)
        record = serializer.save(student=student)
        log_action(AuditAction.STUDENT_CHANGED, request=request, entity="AcademicRecord", entity_id=record.pk,
                   description=f"Registro académico {record.academic_period.code}")
        return Response(AcademicRecordSerializer(record).data, status=status.HTTP_201_CREATED if not existing else status.HTTP_200_OK)
