from rest_framework import serializers, viewsets

from users.permissions import IsAdminRole

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = ["id", "username", "action", "action_display", "entity", "entity_id", "description", "metadata",
                  "ip_address", "created_at"]


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminRole]
    filterset_fields = ["action", "username"]
    search_fields = ["username", "description", "entity_id"]
