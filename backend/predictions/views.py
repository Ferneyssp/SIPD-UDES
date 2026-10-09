from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from academic.models import AcademicPeriod, AcademicRecord, Program
from audit.models import AuditAction
from audit.services import log_action
from config.risk import RiskLevel
from ml.services import ModelNotAvailableError, model_status
from students.models import Student
from students.queries import annotate_current_risk, filter_by_followup_status
from students.scoping import allowed_program_ids, scope_queryset, user_can_access_student
from students.serializers import StudentListSerializer
from users.permissions import IsAdminRole

from .models import Prediction, PredictionStatus
from .serializers import (
    BatchPredictionRequestSerializer,
    PredictionDetailSerializer,
    PredictionRequestSerializer,
    PredictionSerializer,
)
from .services import predict_period, predict_records, serialize_result


class PredictionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Consulta de predicciones. Filtros: period, program, risk_level, model, date_from, date_to,
    student, status (VIGENTE por defecto; 'all' para incluir reemplazadas).
    """

    search_fields = ["student__anonymous_code"]
    ordering_fields = ["prediction_date", "probability", "academic_period__code"]
    ordering = ["-prediction_date"]

    def get_permissions(self):
        if self.action in {"create", "run_batch"}:
            return [IsAdminRole()]
        return super().get_permissions()

    def get_serializer_class(self):
        return PredictionDetailSerializer if self.action == "retrieve" else PredictionSerializer

    def get_queryset(self):
        params = self.request.query_params
        queryset = scope_queryset(
            Prediction.objects.select_related("student__program", "academic_period", "academic_record", "created_by"),
            self.request.user,
            program_field="student__program_id",
        )
        if self.action == "retrieve":
            return queryset
        status_param = params.get("status", PredictionStatus.CURRENT)
        if status_param != "all":
            queryset = queryset.filter(status=status_param)
        if params.get("period"):
            queryset = queryset.filter(academic_period__code=params["period"])
        if params.get("program"):
            queryset = queryset.filter(student__program__code=params["program"])
        if params.get("risk_level"):
            queryset = queryset.filter(risk_level=params["risk_level"].upper())
        if params.get("model"):
            queryset = queryset.filter(model_name__icontains=params["model"])
        if params.get("student"):
            queryset = queryset.filter(student__anonymous_code=params["student"].upper())
        for param, lookup in (("date_from", "prediction_date__date__gte"), ("date_to", "prediction_date__date__lte")):
            if params.get(param):
                parsed = parse_date(params[param])
                if parsed is None:
                    raise ValidationError({param: "Fecha inválida, use AAAA-MM-DD."})
                queryset = queryset.filter(**{lookup: parsed})
        return queryset

    # ------------------------------------------------------------------ escritura (Administrador)
    def create(self, request):
        """Ejecuta la predicción de un estudiante (usa el modelo activo ya entrenado)."""
        payload = PredictionRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        student = get_object_or_404(Student, anonymous_code=payload.validated_data["student"].upper())
        records = AcademicRecord.objects.filter(student=student).select_related("student__program", "academic_period")
        if payload.validated_data.get("academic_period"):
            records = records.filter(academic_period__code=payload.validated_data["academic_period"])
        record = records.order_by("-academic_period__code").first()
        if record is None:
            raise ValidationError({"detail": "El estudiante no tiene información académica para el periodo indicado."})
        try:
            [prediction] = predict_records([record], user=request.user)
        except ModelNotAvailableError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        log_action(AuditAction.PREDICTION_RUN, request=request, entity="Student", entity_id=student.anonymous_code,
                   metadata={"period": record.academic_period.code, "count": 1})
        return Response(
            {**serialize_result(prediction), "prediction": PredictionDetailSerializer(prediction).data},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="run-batch")
    def run_batch(self, request):
        payload = BatchPredictionRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        period = get_object_or_404(AcademicPeriod, code=payload.validated_data["academic_period"])
        program_ids = None
        if payload.validated_data.get("program"):
            program_ids = [get_object_or_404(Program, code=payload.validated_data["program"]).id]
        try:
            total = predict_period(period, user=request.user, program_ids=program_ids)
        except ModelNotAvailableError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        log_action(AuditAction.PREDICTION_RUN, request=request, entity="AcademicPeriod", entity_id=period.code,
                   metadata={"count": total, "program": payload.validated_data.get("program") or "todos"})
        return Response({"detail": f"Se generaron {total} predicciones para {period.code}.", "predictions_generated": total})

    # ------------------------------------------------------------------ historial
    @action(detail=False, methods=["get"])
    def history(self, request):
        """Evolución del riesgo estimado de un estudiante a través de los periodos."""
        code = request.query_params.get("student", "").upper()
        if not code:
            raise ValidationError({"student": "Indique el código del estudiante (p. ej. E001)."})
        student = get_object_or_404(Student.objects.select_related("program"), anonymous_code=code)
        if not user_can_access_student(request.user, student):
            return Response({"detail": "No tiene acceso a este estudiante."}, status=status.HTTP_403_FORBIDDEN)
        include_superseded = request.query_params.get("include_superseded") == "true"
        predictions = student.predictions.select_related("academic_period", "academic_record", "student__program", "created_by")
        if not include_superseded:
            predictions = predictions.filter(status=PredictionStatus.CURRENT)
        predictions = predictions.order_by("academic_period__code", "prediction_date")
        return Response({
            "student": {"id": student.id, "anonymous_code": student.anonymous_code, "program": student.program.name,
                        "semester": student.semester},
            "timeline": PredictionSerializer(predictions, many=True).data,
        })

    @action(detail=False, methods=["get"])
    def trend(self, request):
        """Porcentaje de estudiantes por nivel de riesgo en cada periodo (predicciones vigentes)."""
        queryset = scope_queryset(Prediction.objects.filter(status=PredictionStatus.CURRENT), request.user,
                                  program_field="student__program_id")
        if request.query_params.get("program"):
            queryset = queryset.filter(student__program__code=request.query_params["program"])
        rows = (
            queryset.values("academic_period__code")
            .annotate(
                total=Count("id"),
                alto=Count("id", filter=Q(risk_level=RiskLevel.HIGH)),
                medio=Count("id", filter=Q(risk_level=RiskLevel.MEDIUM)),
                bajo=Count("id", filter=Q(risk_level=RiskLevel.LOW)),
            )
            .order_by("academic_period__code")
        )
        return Response([
            {
                "period": row["academic_period__code"], "total": row["total"],
                "alto": row["alto"], "medio": row["medio"], "bajo": row["bajo"],
                "alto_pct": round(100 * row["alto"] / row["total"], 1) if row["total"] else 0,
            }
            for row in rows
        ])

    # ------------------------------------------------------------------ Inicio
    @action(detail=False, methods=["get"])
    def summary(self, request):
        params = request.query_params
        period = (
            AcademicPeriod.objects.filter(code=params["period"]).first() if params.get("period") else AcademicPeriod.get_current()
        )
        period_code = period.code if period else None

        students = scope_queryset(Student.objects.filter(is_active=True).select_related("program"), request.user)
        if params.get("program"):
            students = students.filter(program__code=params["program"])
        if params.get("semester"):
            students = students.filter(semester=params["semester"])
        students = annotate_current_risk(students, period_code)
        students = filter_by_followup_status(students, params.get("followup_status"))

        level_counts = {row["current_risk_level"]: row["n"] for row in
                        students.values("current_risk_level").annotate(n=Count("id")).order_by()}
        total = sum(level_counts.values())

        predictions = scope_queryset(Prediction.objects.filter(status=PredictionStatus.CURRENT), request.user,
                                     program_field="student__program_id")
        if period_code:
            predictions = predictions.filter(academic_period__code=period_code)
        if params.get("program"):
            predictions = predictions.filter(student__program__code=params["program"])
        if params.get("semester"):
            predictions = predictions.filter(student__semester=params["semester"])

        by_program: dict[str, dict] = {}
        for row in students.values("program__name", "current_risk_level").annotate(n=Count("id")).order_by():
            entry = by_program.setdefault(row["program__name"], {"program": row["program__name"], "ALTO": 0, "MEDIO": 0, "BAJO": 0, "SIN_PREDICCION": 0})
            entry[row["current_risk_level"] or "SIN_PREDICCION"] += row["n"]

        attention_levels = [params["risk_level"].upper()] if params.get("risk_level") else [RiskLevel.HIGH]
        attention = students.filter(current_risk_level__in=attention_levels).order_by("-current_probability")
        attention_limit = min(int(params.get("limit", 10)), 50)

        def pct(value):
            return round(100 * value / total, 1) if total else 0

        return Response({
            "period": period_code,
            "totals": {
                "students": total,
                "high": level_counts.get(RiskLevel.HIGH, 0),
                "medium": level_counts.get(RiskLevel.MEDIUM, 0),
                "low": level_counts.get(RiskLevel.LOW, 0),
                "without_prediction": level_counts.get(None, 0),
                "high_pct": pct(level_counts.get(RiskLevel.HIGH, 0)),
                "medium_pct": pct(level_counts.get(RiskLevel.MEDIUM, 0)),
                "low_pct": pct(level_counts.get(RiskLevel.LOW, 0)),
                "predictions": predictions.count(),
            },
            "by_program": sorted(by_program.values(), key=lambda e: (e["ALTO"], e["MEDIO"]), reverse=True),
            "attention_total": attention.count(),
            "attention": StudentListSerializer(attention[:attention_limit], many=True).data,
            "model": model_status(),
            "scope_restricted": allowed_program_ids(request.user) is not None,
        })
