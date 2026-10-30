"""
Generación de alertas tempranas a partir de las predicciones registradas.

Regla (parametrizable, no validada con datos institucionales):
  - nivel de riesgo estimado Alto, o
  - aumento de la probabilidad >= ALERT_RISE_THRESHOLD respecto a la predicción vigente del
    periodo anterior del mismo estudiante.
Una alerta por estudiante y periodo (sin duplicados). Las alertas cerradas no se reabren
automáticamente: cerrar una alerta es una decisión de una persona.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from django.conf import settings

from config.risk import RiskLevel

from .models import Alert, AlertPriority, AlertReason, AlertStatus


def previous_probabilities(predictions) -> dict[int, float | None]:
    """Probabilidad de la predicción vigente más reciente de un periodo ANTERIOR, por predicción."""
    from academic.models import AcademicPeriod
    from predictions.models import Prediction, PredictionStatus

    predictions = list(predictions)
    codes = dict(AcademicPeriod.objects.filter(pk__in={p.academic_period_id for p in predictions})
                 .values_list("pk", "code"))
    history = defaultdict(list)
    for student_id, code, probability in (
        Prediction.objects.filter(student_id__in={p.student_id for p in predictions}, status=PredictionStatus.CURRENT)
        .values_list("student_id", "academic_period__code", "probability").order_by("academic_period__code")
    ):
        history[student_id].append((code, probability))
    result = {}
    for prediction in predictions:
        code = codes[prediction.academic_period_id]
        earlier = [prob for period, prob in history[prediction.student_id] if period < code]
        result[prediction.pk] = earlier[-1] if earlier else None
    return result


def evaluate_predictions(predictions) -> list[Alert]:
    """Crea o actualiza alertas para las predicciones recién generadas. Devuelve las alertas nuevas."""
    predictions = [p for p in predictions if p.pk]
    if not predictions:
        return []
    threshold = settings.ALERT_RISE_THRESHOLD
    previous = previous_probabilities(predictions)
    existing = {
        (a.student_id, a.academic_period_id): a
        for a in Alert.objects.filter(student_id__in={p.student_id for p in predictions},
                                      academic_period_id__in={p.academic_period_id for p in predictions})
    }
    created = []
    for prediction in predictions:
        before = previous[prediction.pk]
        high = prediction.risk_level == RiskLevel.HIGH
        rise = before is not None and prediction.probability - before >= threshold
        if not (high or rise):
            continue
        reason = AlertReason.HIGH_AND_RISE if high and rise else AlertReason.HIGH_LEVEL if high else AlertReason.RISE
        fields = {"prediction": prediction, "reason": reason, "probability": prediction.probability,
                  "previous_probability": before, "priority": AlertPriority.HIGH if high else AlertPriority.MEDIUM}
        alert = existing.get((prediction.student_id, prediction.academic_period_id))
        if alert is None:
            created.append(Alert.objects.create(student_id=prediction.student_id,
                                                academic_period_id=prediction.academic_period_id, **fields))
        elif alert.status != AlertStatus.CLOSED:
            Alert.objects.filter(pk=alert.pk).update(**fields)
    _notify_new_alerts(created)
    return created


def _notify_new_alerts(alerts: list[Alert]) -> None:
    """Un aviso agregado por programa a sus coordinadores (sin datos individuales en el mensaje)."""
    if not alerts:
        return
    from notifications.models import NotificationLevel, NotificationType
    from notifications.services import notify
    from users.models import Role, User

    by_program = Counter(a.student.program_id for a in Alert.objects.filter(pk__in=[a.pk for a in alerts])
                         .select_related("student"))
    for program_id, count in by_program.items():
        recipients = User.objects.filter(is_active=True, role=Role.COORDINATOR, programs__id=program_id).distinct()
        notify(recipients, NotificationType.ALERTS_CREATED, f"{count} nuevas alertas tempranas",
               "Hay estudiantes de su programa con riesgo estimado alto o en aumento que requieren revisión.",
               level=NotificationLevel.WARNING, link="/alertas?status=ABIERTA", entity="Program", entity_id=program_id)


def sync_with_followup(followup, actor) -> int:
    """La alerta se gestiona con el seguimiento del estudiante: al registrarlo o actualizarlo, las alertas
    abiertas del estudiante quedan "En atención" con el responsable del seguimiento; cuando el seguimiento
    se marca Atendido o Cerrado, se cierran con su observación. Devuelve cuántas alertas cambió."""
    from django.utils import timezone

    from followups.models import FollowUpStatus

    alerts = Alert.objects.filter(student_id=followup.student_id).exclude(status=AlertStatus.CLOSED)
    fields = {"followup": followup, "assigned_to": followup.user, "updated_at": timezone.now()}
    if followup.status in (FollowUpStatus.ATTENDED, FollowUpStatus.CLOSED):
        fields.update(status=AlertStatus.CLOSED, closing_observation=followup.observation, closed_by=actor,
                      closed_at=timezone.now())
    else:
        fields["status"] = AlertStatus.IN_PROGRESS
    return alerts.update(**fields)
