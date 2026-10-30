"""
Creación de notificaciones desde los procesos reales del backend.

- Se crean al confirmarse la transacción (on_commit): nunca se avisa de algo que luego se revierte.
- dedupe_key evita duplicados del mismo acontecimiento.
- Un fallo al notificar nunca interrumpe la operación principal.
"""
from __future__ import annotations

import logging
from typing import Iterable

from django.db import transaction

from users.models import Role, User

from .models import Notification, NotificationLevel

logger = logging.getLogger(__name__)


def active_admins():
    return User.objects.filter(is_active=True, role=Role.ADMIN)


def _create(recipient_ids: list[int], fields: dict) -> None:
    try:
        Notification.objects.bulk_create(
            [Notification(recipient_id=pk, **fields) for pk in recipient_ids], ignore_conflicts=True,
        )
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo crear la notificación %s", fields.get("type"))


def notify(recipients: Iterable, type: str, title: str, message: str = "", *, level: str = NotificationLevel.INFO,
           link: str = "", entity: str = "", entity_id="", dedupe_key: str = "") -> None:
    recipient_ids = sorted({getattr(r, "pk", r) for r in recipients if r is not None})
    if not recipient_ids:
        return
    if link and not link.startswith("/"):
        link = ""  # sólo rutas internas
    fields = {
        "type": type, "level": level, "title": title[:150], "message": message[:500], "link": link[:200],
        "entity": entity[:60], "entity_id": str(entity_id or "")[:60], "dedupe_key": dedupe_key[:120],
    }
    transaction.on_commit(lambda: _create(recipient_ids, fields))


def notify_admins(type: str, title: str, message: str = "", **kwargs) -> None:
    notify(active_admins(), type, title, message, **kwargs)


def notify_predictions_completed(actor, period_code: str, total: int, program_ids=None, origin: str = "") -> None:
    """Avisa a quien ejecutó el proceso y, sin cifras ni datos individuales, a los usuarios con acceso a esos programas."""
    from .models import NotificationType

    if not total:
        return
    link = f"/predicciones?period={period_code}" if "," not in period_code else "/predicciones"
    notify([actor], NotificationType.PREDICTIONS_COMPLETED, f"Predicciones generadas para {period_code}",
           f"Se generaron {total} predicciones{origin} con el modelo activo.", level=NotificationLevel.SUCCESS, link=link,
           entity="AcademicPeriod", entity_id=period_code)
    others = User.objects.filter(is_active=True).exclude(pk=getattr(actor, "pk", None)).exclude(role=Role.ADMIN)
    recipients = []
    for user in others.prefetch_related("programs"):
        scope = {p.pk for p in user.programs.all()}
        if user.role == Role.COORDINATOR and scope and (program_ids is None or scope & set(program_ids)):
            recipients.append(user)
    notify(recipients, NotificationType.PREDICTIONS_COMPLETED, f"Nuevas predicciones disponibles ({period_code})",
           "Hay estimaciones de riesgo actualizadas para estudiantes de sus programas.", link=link,
           entity="AcademicPeriod", entity_id=period_code)
