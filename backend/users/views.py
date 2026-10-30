from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from audit.models import AuditAction
from audit.services import log_action

from .models import Role, User
from .permissions import CanManageUsers
from .serializers import ChangePasswordSerializer, LoginSerializer, ProfileSerializer, UserSerializer
from .tokens import (
    REFRESH_COOKIE,
    REMEMBER_COOKIE,
    clear_refresh_cookie,
    has_csrf_header,
    revoke_user_sessions,
    set_refresh_cookie,
)

CSRF_REQUIRED = "Solicitud no permitida."


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
        tokens = serializer.validated_data["tokens"]
        remember = str(request.data.get("remember", "")).lower() in {"true", "1"}
        log_action(AuditAction.LOGIN, user=user, request=request, entity="User", entity_id=user.pk)
        # El refresh token NO va en el cuerpo: sólo en la cookie HttpOnly.
        response = Response({"access": tokens["access"], "user": ProfileSerializer(user).data})
        set_refresh_cookie(response, tokens["refresh"], remember)
        return response


class CookieTokenRefreshView(APIView):
    """Renueva el access token con el refresh token de la cookie (con rotación y lista negra)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not has_csrf_header(request):
            return Response({"detail": CSRF_REQUIRED}, status=status.HTTP_403_FORBIDDEN)
        refresh = request.COOKIES.get(REFRESH_COOKIE)
        if not refresh:
            return Response({"detail": "Sesión expirada."}, status=status.HTTP_401_UNAUTHORIZED)
        serializer = TokenRefreshSerializer(data={"refresh": refresh})
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:  # noqa: BLE001 - token inválido, expirado, revocado o usuario inactivo
            response = Response({"detail": "Sesión expirada."}, status=status.HTTP_401_UNAUTHORIZED)
            clear_refresh_cookie(response)
            return response
        response = Response({"access": serializer.validated_data["access"]})
        if serializer.validated_data.get("refresh"):
            set_refresh_cookie(response, serializer.validated_data["refresh"], request.COOKIES.get(REMEMBER_COOKIE) == "1")
        return response


class LogoutView(APIView):
    """Invalida el refresh token de la cookie y la borra. Funciona aunque el access token haya expirado."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not has_csrf_header(request):
            return Response({"detail": CSRF_REQUIRED}, status=status.HTTP_403_FORBIDDEN)
        user_id = None
        refresh = request.COOKIES.get(REFRESH_COOKIE)
        if refresh:
            try:
                token = RefreshToken(refresh)
                user_id = token.get("user_id")
                token.blacklist()
            except TokenError:
                pass  # token ya inválido o expirado: la sesión igualmente se cierra
        user = User.objects.filter(pk=user_id).first() if user_id else None
        log_action(AuditAction.LOGOUT, user=user, request=request, entity="User", entity_id=user_id or "")
        response = Response({"detail": "Sesión cerrada correctamente."})
        clear_refresh_cookie(response)
        return response


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
        revoked = revoke_user_sessions(request.user)
        log_action(AuditAction.PASSWORD_CHANGED, request=request, entity="User", entity_id=request.user.pk,
                   metadata={"sessions_revoked": revoked})
        response = Response({"detail": "Contraseña actualizada. Inicie sesión nuevamente."})
        clear_refresh_cookie(response)
        return response


class UserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                  mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Gestión de usuarios. DELETE realiza desactivación lógica (conserva trazabilidad)."""

    serializer_class = UserSerializer
    permission_classes = [CanManageUsers]
    filterset_fields = ["role", "is_active"]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering_fields = ["username", "email", "role", "created_at"]

    def get_queryset(self):
        """El Administrador gestiona a todos. Un coordinador con permiso de gestión sólo ve (y puede
        modificar) coordinadores sin ese permiso cuyos programas estén todos dentro de los suyos;
        nunca administradores, otros gestores ni a sí mismo."""
        queryset = User.objects.prefetch_related("programs").order_by("username")
        actor = self.request.user
        if actor.role == Role.ADMIN:
            return queryset
        own = list(actor.programs.values_list("id", flat=True))
        outside = User.programs.through.objects.exclude(program_id__in=own).values("user_id")
        return (queryset.filter(role=Role.COORDINATOR, can_manage_users=False)
                .exclude(pk=actor.pk).exclude(pk__in=outside))

    def perform_create(self, serializer):
        user = serializer.save()
        log_action(AuditAction.USER_CREATED, request=self.request, entity="User", entity_id=user.pk,
                   description=f"Usuario {user.username} creado con rol {user.role}")

    def perform_update(self, serializer):
        changed = sorted(k for k in serializer.validated_data if k != "password")
        password_reset = "password" in serializer.validated_data
        if password_reset:
            changed.append("password(reset)")
        user = serializer.save()
        if password_reset or serializer.validated_data.get("is_active") is False:
            revoke_user_sessions(user)
        log_action(AuditAction.USER_UPDATED, request=self.request, entity="User", entity_id=user.pk,
                   metadata={"fields": changed})

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if user == request.user:
            return Response({"detail": "No puede desactivar su propia cuenta."}, status=status.HTTP_400_BAD_REQUEST)
        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])
        revoke_user_sessions(user)
        log_action(AuditAction.USER_DEACTIVATED, request=request, entity="User", entity_id=user.pk)
        return Response({"detail": "Usuario desactivado."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=["is_active", "updated_at"])
        log_action(AuditAction.USER_UPDATED, request=request, entity="User", entity_id=user.pk, metadata={"fields": ["is_active"]})
        return Response(UserSerializer(user).data)
