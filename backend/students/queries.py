"""Consultas reutilizables: anota a cada estudiante su riesgo vigente y su último seguimiento."""
from django.db.models import ExpressionWrapper, F, FloatField, OuterRef, Subquery

from followups.models import FollowUp
from predictions.models import Prediction, PredictionStatus


def annotate_current_risk(queryset, period_code: str | None = None):
    predictions = Prediction.objects.filter(student=OuterRef("pk"), status=PredictionStatus.CURRENT)
    if period_code:
        predictions = predictions.filter(academic_period__code=period_code)
    latest = predictions.order_by("-academic_period__code", "-prediction_date")
    latest_followup = FollowUp.objects.filter(student=OuterRef("pk")).order_by("-follow_up_date", "-created_at")
    queryset = queryset.annotate(
        current_prediction_id=Subquery(latest.values("id")[:1]),
        current_probability=Subquery(latest.values("probability")[:1]),
        current_risk_level=Subquery(latest.values("risk_level")[:1]),
        current_prediction_date=Subquery(latest.values("prediction_date")[:1]),
        current_prediction_period=Subquery(latest.values("academic_period__code")[:1]),
        current_model_name=Subquery(latest.values("model_name")[:1]),
        latest_followup_status=Subquery(latest_followup.values("status")[:1]),
    )
    # Cambio respecto a la predicción vigente del periodo anterior (equivalente al "cambio" de Civitas).
    previous = Prediction.objects.filter(
        student=OuterRef("pk"), status=PredictionStatus.CURRENT,
        academic_period__code__lt=OuterRef("current_prediction_period"),
    ).order_by("-academic_period__code")
    from alerts.models import Alert, AlertStatus

    open_alert = Alert.objects.filter(student=OuterRef("pk")).exclude(status=AlertStatus.CLOSED).order_by("-created_at")
    return queryset.annotate(
        previous_probability=Subquery(previous.values("probability")[:1]),
        open_alert_status=Subquery(open_alert.values("status")[:1]),
    ).annotate(
        risk_change=ExpressionWrapper(F("current_probability") - F("previous_probability"), output_field=FloatField()),
    )


NO_FOLLOWUP = "SIN_SEGUIMIENTO"


def filter_by_followup_status(queryset, status: str | None):
    if not status:
        return queryset
    if status == NO_FOLLOWUP:
        return queryset.filter(latest_followup_status__isnull=True)
    return queryset.filter(latest_followup_status=status)
