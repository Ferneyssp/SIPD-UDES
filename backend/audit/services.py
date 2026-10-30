"""Registro de auditoría. Nunca incluir contraseñas, tokens ni datos académicos en metadata."""
import logging

from .models import AuditLog

logger = logging.getLogger(__name__)


def client_ip(request) -> str | None:
    """IP del cliente. X-Forwarded-For sólo se usa si hay TRUSTED_PROXY_COUNT proxies de confianza:
    se toma la entrada que agregó el proxy más externo de confianza (las anteriores las puede inventar
    el cliente)."""
    if request is None:
        return None
    from django.conf import settings

    proxies = getattr(settings, "TRUSTED_PROXY_COUNT", 0)
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if proxies and forwarded:
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if hops:
            return hops[-min(proxies, len(hops))]
    return request.META.get("REMOTE_ADDR")


def log_action(action: str, *, user=None, request=None, entity: str = "", entity_id="", description: str = "", metadata=None):
    actor = user if user is not None and getattr(user, "is_authenticated", False) else None
    if actor is None and request is not None and getattr(request, "user", None) and request.user.is_authenticated:
        actor = request.user
    try:
        return AuditLog.objects.create(
            user=actor,
            username=(actor.username if actor else (metadata or {}).get("username", ""))[:150],
            action=action,
            entity=entity,
            entity_id=str(entity_id or ""),
            description=description[:255],
            metadata={k: v for k, v in (metadata or {}).items() if k != "username"},
            ip_address=client_ip(request),
        )
    except Exception:  # la auditoría nunca debe romper la operación principal
        logger.exception("No se pudo registrar la acción de auditoría %s", action)
        return None
