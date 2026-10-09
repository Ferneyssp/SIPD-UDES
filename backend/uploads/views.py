from django.http import HttpResponse
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from audit.models import AuditAction
from audit.services import log_action
from users.permissions import IsAdminRole

from .models import DataUpload
from .services import confirm_upload, create_validated_upload
from .validators import OPTIONAL_COLUMNS, REQUIRED_COLUMNS, FileRejected, template_csv


class DataUploadSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.CharField(source="uploaded_by.username", read_only=True, allow_null=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = DataUpload
        fields = [
            "id", "filename", "uploaded_by", "status", "status_display", "records_found", "records_valid",
            "records_failed", "records_processed", "predictions_generated", "run_predictions", "message",
            "errors", "upload_date", "processed_at",
        ]


class DataUploadListSerializer(DataUploadSerializer):
    class Meta(DataUploadSerializer.Meta):
        fields = [f for f in DataUploadSerializer.Meta.fields if f != "errors"]


class DataUploadViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    Carga de datos (sólo Administrador).
      POST /api/uploads/            -> valida el CSV (multipart, campo 'file'); no modifica datos.
      POST /api/uploads/{id}/confirm/ -> procesa los registros válidos {run_predictions: bool}.
      GET  /api/uploads/template/   -> plantilla CSV.
    """

    queryset = DataUpload.objects.select_related("uploaded_by")
    permission_classes = [IsAdminRole]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    ordering_fields = ["upload_date"]

    def get_serializer_class(self):
        return DataUploadListSerializer if self.action == "list" else DataUploadSerializer

    def create(self, request, *args, **kwargs):
        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            return Response({"detail": "Seleccione un archivo CSV."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            upload = create_validated_upload(uploaded_file, request.user)
        except FileRejected as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        log_action(AuditAction.DATA_UPLOAD, request=request, entity="DataUpload", entity_id=upload.pk,
                   description="Validación de archivo", metadata={"status": upload.status, "found": upload.records_found,
                                                                  "valid": upload.records_valid, "failed": upload.records_failed})
        code = status.HTTP_201_CREATED if upload.status == "VALIDADO" else status.HTTP_422_UNPROCESSABLE_ENTITY
        return Response(DataUploadSerializer(upload).data, status=code)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        upload = self.get_object()
        run_predictions = str(request.data.get("run_predictions", "true")).lower() in {"true", "1"}
        try:
            upload = confirm_upload(upload, request.user, run_predictions=run_predictions)
        except FileRejected as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        log_action(AuditAction.DATA_UPLOAD, request=request, entity="DataUpload", entity_id=upload.pk,
                   description="Confirmación de carga", metadata={"processed": upload.records_processed,
                                                                  "predictions": upload.predictions_generated})
        return Response(DataUploadSerializer(upload).data)

    @action(detail=False, methods=["get"])
    def template(self, request):
        response = HttpResponse(template_csv(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="plantilla_carga_sipd.csv"'
        return response

    @action(detail=False, methods=["get"])
    def schema(self, request):
        return Response({"required_columns": REQUIRED_COLUMNS, "optional_columns": OPTIONAL_COLUMNS})
