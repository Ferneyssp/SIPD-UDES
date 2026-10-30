"""
Recuperación de contraseña por correo.

  POST /api/auth/password-reset/          {email}
       Responde siempre lo mismo (no revela si el correo existe). Si pertenece a un usuario activo,
       envía un enlace de un solo uso válido PASSWORD_RESET_TIMEOUT segundos (30 min por defecto).
  POST /api/auth/password-reset/confirm/  {uid, token, new_password, confirm_password}
       Valida el enlace y la nueva contraseña, la cambia y cierra todas las sesiones del usuario.

El token es el de Django (default_token_generator): depende del hash de la contraseña y del último
inicio de sesión, así que deja de servir en cuanto se usa o se cambia la contraseña.
"""
import logging
from html import escape

from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import EmailMultiAlternatives
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from audit.models import AuditAction
from audit.services import log_action

from .models import User
from .tokens import revoke_user_sessions

logger = logging.getLogger(__name__)
GENERIC_RESPONSE = ("Si el correo pertenece a una cuenta activa, recibirá un enlace para restablecer la contraseña. "
                    "Revise también la carpeta de correo no deseado.")
INVALID_LINK = "El enlace no es válido o ya expiró. Solicite uno nuevo."


def reset_link(user) -> str:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f"{settings.FRONTEND_URL.rstrip('/')}/restablecer-contrasena/{uid}/{token}"


def send_reset_email(user) -> None:
    link = reset_link(user)
    minutes = settings.PASSWORD_RESET_TIMEOUT // 60
    name = user.display_name
    subject = "SIPD · Restablecer contraseña"
    text = (
        f"Hola {name}:\n\n"
        "Recibimos una solicitud para restablecer la contraseña de su cuenta en SIPD.\n"
        f"Abra este enlace (válido por {minutes} minutos y de un solo uso):\n\n{link}\n\n"
        "Si usted no hizo la solicitud, ignore este mensaje: su contraseña no cambiará.\n\n"
        f"SIPD · {settings.INSTITUTION_NAME}"
    )
    logo = f"{settings.FRONTEND_URL.rstrip('/')}/escudo-udes.png"
    html = f"""<div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;color:#1f2a37">
  <div style="text-align:center;padding:16px"><img src="{escape(logo)}" alt="UDES" width="72" height="72"></div>
  <h2 style="color:#1d3a5c;margin:0 0 12px">Restablecer contraseña</h2>
  <p>Hola {escape(name)}:</p>
  <p>Recibimos una solicitud para restablecer la contraseña de su cuenta en SIPD.</p>
  <p style="text-align:center;margin:24px 0">
    <a href="{escape(link)}" style="background:#1d3a5c;color:#fff;padding:12px 22px;border-radius:8px;text-decoration:none;font-weight:bold">Crear nueva contraseña</a>
  </p>
  <p style="font-size:13px;color:#4a5563">El enlace es válido por {minutes} minutos y sólo puede usarse una vez.
  Si usted no hizo la solicitud, ignore este mensaje: su contraseña no cambiará.</p>
  <p style="font-size:12px;color:#6b7684">SIPD · {escape(settings.INSTITUTION_NAME)}</p>
</div>"""
    message = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [user.email])
    message.attach_alternative(html, "text/html")
    message.send()


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        email = str(request.data.get("email", "")).strip()
        if not email or "@" not in email:
            return Response({"detail": "Ingrese su correo institucional.", "errors": {"email": "Correo inválido."}},
                            status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user is not None:
            try:
                send_reset_email(user)
            except Exception:  # noqa: BLE001 - el error no se revela al cliente (respuesta siempre igual)
                logger.exception("No se pudo enviar el correo de recuperación al usuario %s", user.pk)
            log_action(AuditAction.PASSWORD_RESET_REQUESTED, user=user, request=request, entity="User", entity_id=user.pk)
        return Response({"detail": GENERIC_RESPONSE})


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8)
    confirm_password = serializers.CharField()

    def validate(self, attrs):
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(attrs["uid"])), is_active=True)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            user = None
        if user is None or not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": INVALID_LINK})
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Las contraseñas no coinciden."})
        try:
            password_validation.validate_password(attrs["new_password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)}) from exc
        attrs["user"] = user
        return attrs


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            detail = INVALID_LINK if "token" in errors else "Revise los datos de la nueva contraseña."
            return Response({"detail": detail, "errors": errors}, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])
        revoke_user_sessions(user)  # cierra cualquier sesión abierta con la contraseña anterior
        log_action(AuditAction.PASSWORD_RESET, user=user, request=request, entity="User", entity_id=user.pk)
        return Response({"detail": "Contraseña restablecida. Ya puede iniciar sesión."})
