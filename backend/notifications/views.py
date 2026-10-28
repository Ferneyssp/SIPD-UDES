from django.utils import timezone
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import CATEGORY_LABELS, CATEGORY_TYPES, Notification, NotificationType


class NotificationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    level_display = serializers.CharField(source="get_level_display", read_only=True)
    is_read = serializers.BooleanField(read_only=True)
    category = serializers.CharField(read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "type", "type_display", "category", "level", "level_display", "title", "message", "link",
                  "entity", "entity_id", "created_at", "read_at", "is_read"]
        read_only_fields = fields


class NotificationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Notificaciones del usuario autenticado (nunca las de otra persona).
      GET  /api/notifications/?is_read=false&type=...&category=MODELOS
      GET  /api/notifications/unread-count/
      POST /api/notifications/{id}/read/
      POST /api/notifications/read-all/
    """

    serializer_class = NotificationSerializer
    filter_backends = []  # filtros explícitos abajo

    def get_queryset(self):
        queryset = Notification.objects.filter(recipient=self.request.user)
        if self.action != "list":
            return queryset
        params = self.request.query_params
        if params.get("is_read") in {"true", "false"}:
            queryset = queryset.filter(read_at__isnull=params["is_read"] == "false")
        if params.get("type") in NotificationType.values:
            queryset = queryset.filter(type=params["type"])
        if params.get("category") in CATEGORY_TYPES:
            queryset = queryset.filter(type__in=CATEGORY_TYPES[params["category"]])
        return queryset

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data["unread"] = Notification.objects.filter(recipient=request.user, read_at__isnull=True).count()
        response.data["categories"] = [{"value": k, "label": v} for k, v in CATEGORY_LABELS.items()]
        response.data["types"] = [{"value": v, "label": label} for v, label in NotificationType.choices]
        return response

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        return Response({"unread": Notification.objects.filter(recipient=request.user, read_at__isnull=True).count()})

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        updated = Notification.objects.filter(recipient=request.user, read_at__isnull=True).update(read_at=timezone.now())
        return Response({"updated": updated, "unread": 0})
