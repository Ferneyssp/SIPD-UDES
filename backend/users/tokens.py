"""
Sesión con JWT:

- El refresh token viaja sólo en una cookie HttpOnly (Secure, SameSite=Strict, limitada a
  /api/auth/): un script del navegador no puede leerlo. El access token se guarda sólo en
  memoria en el frontend.
- Las rutas que usan la cookie exigen la cabecera X-Requested-With (un formulario de otro
  sitio no puede enviarla), además de SameSite=Strict.
- Al cambiar o restablecer la contraseña se revocan todos los refresh tokens del usuario y
  se rechazan los access tokens emitidos antes del cambio.
"""
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

REFRESH_COOKIE = "sipd_refresh"
REMEMBER_COOKIE = "sipd_remember"
COOKIE_PATH = "/api/auth/"
CSRF_HEADER = "HTTP_X_REQUESTED_WITH"


def has_csrf_header(request) -> bool:
    return request.META.get(CSRF_HEADER) == "XMLHttpRequest"


def set_refresh_cookie(response, refresh: str, remember: bool) -> None:
    max_age = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()) if remember else None
    options = {"max_age": max_age, "path": COOKIE_PATH, "secure": settings.AUTH_COOKIE_SECURE, "httponly": True,
               "samesite": "Strict"}
    response.set_cookie(REFRESH_COOKIE, refresh, **options)
    response.set_cookie(REMEMBER_COOKIE, "1" if remember else "0", **options)


def clear_refresh_cookie(response) -> None:
    for name in (REFRESH_COOKIE, REMEMBER_COOKIE):
        response.delete_cookie(name, path=COOKIE_PATH, samesite="Strict")


def revoke_user_sessions(user) -> int:
    """Lista negra para todos los refresh tokens vigentes del usuario y marca la fecha del cambio."""
    user.password_changed_at = timezone.now()
    user.save(update_fields=["password_changed_at"])
    tokens = OutstandingToken.objects.filter(user=user).exclude(blacklistedtoken__isnull=False)
    BlacklistedToken.objects.bulk_create([BlacklistedToken(token=t) for t in tokens], ignore_conflicts=True)
    return len(tokens)


class SipdJWTAuthentication(JWTAuthentication):
    """Rechaza access tokens emitidos antes del último cambio de contraseña."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        changed = getattr(user, "password_changed_at", None)
        issued = validated_token.get("iat")
        if changed and issued is not None and int(issued) < int(changed.timestamp()):
            raise AuthenticationFailed("La sesión ya no es válida. Inicie sesión nuevamente.", code="token_revoked")
        return user
