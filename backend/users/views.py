from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from audit.models import AuditAction
from audit.services import log_action

from .models import User
from .permissions import CanManageUsers
from .serializers import ChangePasswordSerializer, LoginSerializer, ProfileSerializer, UserSerializer


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            log_action(
                AuditAction.LOGIN_FAILED, request=request, entity="User",
                metadata={"username": str(request.data.get("username", ""))[:150]},
            )
            detail = serializer.errors.get("detail", ["Credenciales incorrectas."])
            message = detail[0] if isinstance(detail, list) else str(detail)
            if "username" in serializer.errors or "password" in serializer.errors:
                message = "Ingrese usuario y contraseña."
            return Response({"detail": str(message)}, status=status.HTTP_401_UNAUTHORIZED)
        user = serializer.validated_data["user"]
        log_action(AuditAction.LOGIN, user=user, request=request, entity="User", entity_id=user.pk)
        return Response({**serializer.validated_data["tokens"], "user": ProfileSerializer(user).data})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh")
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError:
                pass  # token ya inválido o expirado: la sesión igualmente se cierra
        log_action(AuditAction.LOGOUT, request=request, entity="User", entity_id=request.user.pk)
        return Response({"detail": "Sesión cerrada correctamente."})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(ProfileSerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password", "updated_at"])
        log_action(AuditAction.PASSWORD_CHANGED, request=request, entity="User", entity_id=request.user.pk)
        return Response({"detail": "Contraseña actualizada. Inicie sesión nuevamente."})


class UserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                  mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Gestión de usuarios. DELETE realiza desactivación lógica (conserva trazabilidad)."""

    serializer_class = UserSerializer
    permission_classes = [CanManageUsers]
    queryset = User.objects.prefetch_related("programs").order_by("username")
    filterset_fields = ["role", "is_active"]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering_fields = ["username", "email", "role", "created_at"]

    def perform_create(self, serializer):
        user = serializer.save()
        log_action(AuditAction.USER_CREATED, request=self.request, entity="User", entity_id=user.pk,
                   description=f"Usuario {user.username} creado con rol {user.role}")

    def perform_update(self, serializer):
        changed = sorted(k for k in serializer.validated_data if k != "password")
        if "password" in serializer.validated_data:
            changed.append("password(reset)")
        user = serializer.save()
        log_action(AuditAction.USER_UPDATED, request=self.request, entity="User", entity_id=user.pk,
                   metadata={"fields": changed})

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if user == request.user:
            return Response({"detail": "No puede desactivar su propia cuenta."}, status=status.HTTP_400_BAD_REQUEST)
        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])
        log_action(AuditAction.USER_DEACTIVATED, request=request, entity="User", entity_id=user.pk)
        return Response({"detail": "Usuario desactivado."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=["is_active", "updated_at"])
        log_action(AuditAction.USER_UPDATED, request=request, entity="User", entity_id=user.pk, metadata={"fields": ["is_active"]})
        return Response(UserSerializer(user).data)
