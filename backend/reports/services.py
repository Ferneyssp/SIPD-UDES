"""
Cálculo de los reportes a partir de registros reales (predicciones vigentes y
versiones de modelo). La vista en
pantalla, el CSV y el PDF usan exactamente estas mismas funciones.
"""
from __future__ import annotations

from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError

from academic.models import AcademicPeriod
from config.risk import RiskLevel, get_thresholds
from predictions.models import Prediction, PredictionStatus
from students.scoping import allowed_program_ids, scope_queryset

LEVELS = [RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW]
ESTIMATE_NOTICE = ("El nivel de riesgo es una estimación probabilística generada por un modelo de Machine Learning "
                   "para apoyar el acompañamiento académico; no es una certeza sobre el comportamiento del estudiante.")


def _date(params, name):
    if not params.get(name):
        return None
    value = parse_date(params[name])
    if value is None:
        raise ValidationError({name: "Fecha inválida, use AAAA-MM-DD."})
    return value


def _pct(value, total):
    return round(100 * value / total, 1) if total else 0.0


# ---------------------------------------------------------------------------- riesgo estudiantil
def risk_filters(params) -> dict:
    period_code = params.get("period") or getattr(AcademicPeriod.get_current(), "code", None)
    semester = params.get("semester")
    if semester and not str(semester).isdigit():
        raise ValidationError({"semester": "El semestre debe ser un número."})
    return {
        "period": period_code,
        "program": (params.get("program") or "").upper() or None,
        "semester": int(semester) if semester else None,
        "risk_level": (params.get("risk_level") or "").upper() or None,
        "date_from": _date(params, "date_from"),
        "date_to": _date(params, "date_to"),
    }


def risk_queryset(user, filters: dict):
    """Predicciones VIGENTES (una por estudiante y periodo) dentro del ámbito del usuario."""
    queryset = scope_queryset(
        Prediction.objects.filter(status=PredictionStatus.CURRENT, student__is_active=True),
        user, program_field="student__program_id",
    )
    if filters["period"]:
        queryset = queryset.filter(academic_period__code=filters["period"])
    if filters["program"]:
        queryset = queryset.filter(student__program__code=filters["program"])
    if filters["semester"]:
        queryset = queryset.filter(academic_record__semester=filters["semester"])
    if filters.get("risk_level") in RiskLevel.values:
        queryset = queryset.filter(risk_level=filters["risk_level"])
    if filters["date_from"]:
        queryset = queryset.filter(prediction_date__date__gte=filters["date_from"])
    if filters["date_to"]:
        queryset = queryset.filter(prediction_date__date__lte=filters["date_to"])
    return queryset


def _level_counts(queryset) -> dict:
    return queryset.aggregate(
        total=Count("id"),
        **{level.value: Count("id", filter=Q(risk_level=level)) for level in LEVELS},
    )


def _grouped(queryset, field: str, label: str) -> list[dict]:
    rows = (queryset.values(field).annotate(total=Count("id"),
                                            **{level.value: Count("id", filter=Q(risk_level=level)) for level in LEVELS})
            .order_by(field))
    result = []
    for row in rows:
        entry = {label: row[field], "total": row["total"]}
        for level in LEVELS:
            entry[level.value] = row[level.value]
            entry[f"{level.value}_pct"] = _pct(row[level.value], row["total"])
        result.append(entry)
    return result


def risk_report(user, params) -> dict:
    filters = risk_filters(params)
    queryset = risk_queryset(user, filters)
    counts = _level_counts(queryset)
    total = counts["total"]
    models = list(queryset.values("model_name", "model_version_label")
                  .annotate(predictions=Count("id")).order_by("-predictions"))
    notices = [ESTIMATE_NOTICE]
    if len(models) > 1:
        notices.append("Las predicciones del reporte provienen de más de una versión de modelo.")
    return {
        "generated_at": timezone.now().isoformat(),
        "filters": {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in filters.items()},
        "scope_restricted": allowed_program_ids(user) is not None,
        "thresholds": get_thresholds(),
        "totals": {
            "students": total,
            "levels": [{"code": level.value, "label": level.label, "count": counts[level.value],
                        "pct": _pct(counts[level.value], total)} for level in LEVELS],
        },
        "by_program": _grouped(queryset, "student__program__name", "program"),
        "by_semester": _grouped(queryset.exclude(academic_record__isnull=True), "academic_record__semester", "semester"),
        "models": [{"model": m["model_name"], "version": m["model_version_label"], "predictions": m["predictions"]}
                   for m in models],
        "source": "Predicciones vigentes almacenadas por SIPD (una por estudiante y periodo).",
        "notices": notices,
    }


def risk_student_rows(user, params, limit: int):
    """Listado individual (sólo Administrador): código seudonimizado, sin datos socioeconómicos."""
    filters = risk_filters(params)
    queryset = (risk_queryset(user, filters)
                .select_related("student__program", "academic_period", "academic_record")
                .order_by("-probability", "student__anonymous_code"))
    for prediction in queryset[:limit].iterator(chunk_size=1000):
        yield {
            "student_code": prediction.student.anonymous_code,
            "program": prediction.student.program.name,
            "semester": prediction.academic_record.semester if prediction.academic_record else None,
            "period": prediction.academic_period.code,
            "probability": round(prediction.probability, 4),
            "risk_level": prediction.get_risk_level_display(),
            "model": prediction.model_name,
            "model_version": prediction.model_version_label,
            "prediction_date": timezone.localtime(prediction.prediction_date).strftime("%Y-%m-%d %H:%M"),
        }
