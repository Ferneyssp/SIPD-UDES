from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from audit.models import AuditAction
from audit.services import log_action
from users.permissions import IsAdminOrReadOnly, IsAdminRole

from .models import ModelVersion
from .services import clear_cache, model_status, sync_model_versions


class ModelVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelVersion
        fields = ["id", "name", "algorithm", "version", "metrics", "trained_at", "active", "is_synthetic",
                  "selection_metric", "artifact_dir"]


class ModelVersionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Versiones de modelos entrenados y sus métricas de evaluación."""

    queryset = ModelVersion.objects.all()
    serializer_class = ModelVersionSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = None

    @action(detail=True, methods=["post"], permission_classes=[IsAdminRole])
    def activate(self, request, pk=None):
        version = self.get_object()
        version.activate()
        clear_cache()
        log_action(AuditAction.MODEL_ACTIVATED, request=request, entity="ModelVersion", entity_id=version.pk,
                   description=str(version))
        return Response(ModelVersionSerializer(version).data)

    @action(detail=False, methods=["post"], permission_classes=[IsAdminRole])
    def sync(self, request):
        versions = sync_model_versions()
        return Response({"detail": f"{len(versions)} versiones sincronizadas.",
                         "results": ModelVersionSerializer(ModelVersion.objects.all(), many=True).data})

    @action(detail=False, methods=["get"])
    def status(self, request):
        return Response(model_status())
