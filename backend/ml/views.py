from django.utils.dateparse import parse_date
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsAdminOrReadOnly, IsAdminRole

from .models import ApprovalStatus, ModelActivationLog, ModelVersion, RunStatus, TrainingDataset, TrainingRun
from .serializers import (
    ActivationLogSerializer,
    ModelVersionSerializer,
    ReviewSerializer,
    StartRunSerializer,
    TrainingDatasetSerializer,
    TrainingRunListSerializer,
    TrainingRunSerializer,
)
from .services import get_active_model_version, model_status, sync_model_versions
from .training_service import (
    TrainingError,
    activate_version,
    cancel_run,
    compare_versions,
    create_dataset,
    get_active_run,
    review_version,
    rollback_candidates,
    start_run,
    training_config,
)


def _error(exc: TrainingError) -> Response:
    return Response({"detail": str(exc)}, status=exc.status_code)


class ModelVersionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Versiones de modelos entrenados, métricas, aprobación y activación (escritura: Administrador)."""

    serializer_class = ModelVersionSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = None

    def get_queryset(self):
        """Sólo los modelos guardados (aprobados o registrados offline) se listan; los pendientes se ven en
        su entrenamiento y se pueden aprobar o rechazar por id."""
        queryset = ModelVersion.objects.select_related("approved_by")
        if self.action == "list":
            queryset = queryset.exclude(approval_status=ApprovalStatus.PENDING)
        return queryset

    @action(detail=True, methods=["post"], permission_classes=[IsAdminRole])
    def activate(self, request, pk=None):
        try:
            version = activate_version(self.get_object(), request.user, request=request)
        except TrainingError as exc:
            return _error(exc)
        return Response(ModelVersionSerializer(version).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminRole])
    def rollback(self, request, pk=None):
        try:
            version = activate_version(self.get_object(), request.user, rollback=True, request=request)
        except TrainingError as exc:
            return _error(exc)
        return Response(ModelVersionSerializer(version).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminRole])
    def approve(self, request, pk=None):
        return self._review(request, approve=True)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminRole])
    def reject(self, request, pk=None):
        return self._review(request, approve=False)

    def _review(self, request, approve):
        payload = ReviewSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            version = review_version(self.get_object(), request.user, approve, payload.validated_data["notes"], request=request)
        except TrainingError as exc:
            return _error(exc)
        if version is None:
            return Response({"detail": "Versión rechazada y eliminada.", "deleted": True})
        return Response(ModelVersionSerializer(version).data)

    @action(detail=True, methods=["get"], permission_classes=[IsAdminRole])
    def evaluation(self, request, pk=None):
        version = self.get_object()
        active = get_active_model_version()
        return Response({
            "version": ModelVersionSerializer(version).data,
            "comparison": compare_versions(version, active) if active and active.pk != version.pk else None,
        })

    @action(detail=False, methods=["get"], permission_classes=[IsAdminRole])
    def activations(self, request):
        logs = ModelActivationLog.objects.select_related("performed_by")[:100]
        return Response({
            "results": ActivationLogSerializer(logs, many=True).data,
            "rollback_candidates": ModelVersionSerializer(rollback_candidates(), many=True).data,
        })

    @action(detail=False, methods=["post"], permission_classes=[IsAdminRole])
    def sync(self, request):
        versions = sync_model_versions()
        return Response({"detail": f"{len(versions)} versiones sincronizadas.",
                         "results": ModelVersionSerializer(ModelVersion.objects.all(), many=True).data})

    @action(detail=False, methods=["get"])
    def status(self, request):
        return Response(model_status())


class TrainingOverviewView(APIView):
    """Estado de los modelos y configuración del reentrenamiento (Administrador)."""

    permission_classes = [IsAdminRole]

    def get(self, request):
        active_run = get_active_run()
        last_run = TrainingRun.objects.exclude(status__in=[RunStatus.PENDING]).select_related("dataset", "requested_by").first()
        return Response({
            "config": training_config(),
            "model_status": model_status(),
            "active_model": ModelVersionSerializer(get_active_model_version()).data if get_active_model_version() else None,
            "versions": ModelVersionSerializer(ModelVersion.objects.select_related("approved_by")
                                               .exclude(approval_status=ApprovalStatus.PENDING), many=True).data,
            "active_run": TrainingRunSerializer(active_run).data if active_run else None,
            "last_run": TrainingRunListSerializer(last_run).data if last_run else None,
        })


class TrainingDatasetViewSet(mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """POST multipart `file`: valida y registra un dataset; no entrena."""

    queryset = TrainingDataset.objects.select_related("uploaded_by").defer("content")
    serializer_class = TrainingDatasetSerializer
    permission_classes = [IsAdminRole]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request, *args, **kwargs):
        try:
            dataset = create_dataset(request.user, uploaded_file=request.FILES.get("file"), request=request)
        except TrainingError as exc:
            return _error(exc)
        code = status.HTTP_201_CREATED if dataset.status == "VALIDO" else status.HTTP_422_UNPROCESSABLE_ENTITY
        return Response(TrainingDatasetSerializer(dataset).data, status=code)


class TrainingRunViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                         viewsets.GenericViewSet):
    """Ejecuciones de entrenamiento: crear (202), consultar estado, historial con filtros y cancelar."""

    permission_classes = [IsAdminRole]
    queryset = TrainingRun.objects.select_related("dataset", "requested_by").prefetch_related("model_versions").defer("dataset__content")

    def get_serializer_class(self):
        return TrainingRunListSerializer if self.action == "list" else TrainingRunSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action != "list":
            return queryset
        params = self.request.query_params
        if params.get("status"):
            queryset = queryset.filter(status=params["status"].upper())
        if params.get("algorithm"):
            queryset = queryset.filter(algorithms__icontains=f'"{params["algorithm"]}"')
        for param, lookup in (("date_from", "created_at__date__gte"), ("date_to", "created_at__date__lte")):
            if params.get(param):
                parsed = parse_date(params[param])
                if parsed is None:
                    raise ValidationError({param: "Fecha inválida, use AAAA-MM-DD."})
                queryset = queryset.filter(**{lookup: parsed})
        return queryset

    def create(self, request, *args, **kwargs):
        payload = StartRunSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        try:
            run = start_run(request.user, data["dataset"], data["algorithms"], data["selection_metric"], request=request)
        except TrainingError as exc:
            return _error(exc)
        run.refresh_from_db()
        return Response(TrainingRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)

    def retrieve(self, request, *args, **kwargs):
        get_active_run()  # marca como fallidas las ejecuciones interrumpidas antes de responder
        run = self.get_object()
        data = TrainingRunSerializer(run).data
        active = get_active_model_version()
        data["comparisons"] = {
            str(v.pk): compare_versions(v, active) for v in run.model_versions.all() if active and v.pk != active.pk
        }
        return Response(data)

    @action(detail=False, methods=["get"])
    def active(self, request):
        run = get_active_run()
        return Response({"run": TrainingRunSerializer(run).data if run else None})

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        try:
            run = cancel_run(self.get_object(), request.user, request=request)
        except TrainingError as exc:
            return _error(exc)
        return Response(TrainingRunSerializer(run).data)
