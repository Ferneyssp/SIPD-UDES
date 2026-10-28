"""
Cálculo de los reportes a partir de registros reales (predicciones vigentes,
versiones de modelo, ejecuciones de entrenamiento y auditoría). La vista en
pantalla, el CSV y el PDF usan exactamente estas mismas funciones.
"""
from __future__ import annotations

from django.db.models import Count, Min, Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError

from academic.models import AcademicPeriod
from audit.models import AuditAction, AuditLog
from config.risk import RiskLevel, get_thresholds
from ml.models import ModelActivationLog, ModelVersion, RunStatus, TrainingRun
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
    models = list(queryset.values("model_name", "model_version_label", "model_version__is_synthetic")
                  .annotate(predictions=Count("id")).order_by("-predictions"))
    notices = [ESTIMATE_NOTICE]
    if any(m["model_version__is_synthetic"] for m in models):
        notices.append("Parte de las predicciones se generó con modelos entrenados con datos SINTÉTICOS (pruebas técnicas).")
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
        "models": [{"model": m["model_name"], "version": m["model_version_label"], "predictions": m["predictions"],
                    "is_synthetic": bool(m["model_version__is_synthetic"])} for m in models],
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


# ---------------------------------------------------------------------------- evaluación de modelos
METRIC_KEYS = ("accuracy", "precision", "recall", "f1", "roc_auc")


def model_report(user, params) -> dict:
    from ml.training_service import _dataset_sha

    queryset = ModelVersion.objects.select_related("approved_by", "training_run")
    if params.get("algorithm"):
        queryset = queryset.filter(algorithm=params["algorithm"])
    is_admin = getattr(user, "is_admin_role", False)
    versions = []
    for version in queryset:
        evaluation = version.evaluation or {}
        metrics = version.metrics or {}
        versions.append({
            "id": version.pk, "name": version.name, "algorithm": version.algorithm, "version": version.version,
            "trained_at": version.trained_at.isoformat() if version.trained_at else None,
            "dataset_rows": version.dataset_rows,
            "train_size": evaluation.get("train_size"),
            "test_size": metrics.get("test_size") or evaluation.get("test_size"),
            "threshold": metrics.get("threshold"),
            "metrics": {key: metrics.get(key) for key in METRIC_KEYS},
            "confusion_matrix": metrics.get("confusion_matrix"),
            "is_synthetic": version.is_synthetic,
            "approval_status": version.approval_status,
            "approval_status_display": version.get_approval_status_display(),
            "approved_by": version.approved_by.username if is_admin and version.approved_by else None,
            "active": version.active,
            "training_run": version.training_run_id,
            "comparison_group": (_dataset_sha(version) or "")[:12] or None,
        })
    groups = {}
    for item in versions:
        groups.setdefault(item["comparison_group"], []).append(item["id"])
    notices = ["Métricas calculadas sobre el conjunto de PRUEBA (partición estratificada) de cada entrenamiento, "
               "con el umbral de clasificación indicado. Sólo son comparables versiones del mismo grupo de evaluación "
               "(mismo dataset y partición)."]
    if any(v["comparison_group"] is None for v in versions):
        notices.append("Las versiones sin grupo de evaluación se entrenaron fuera de la web y no registran el dataset "
                       "usado: su comparación con otras versiones es sólo orientativa.")
    if any(v["is_synthetic"] for v in versions):
        notices.append("Hay versiones entrenadas con datos SINTÉTICOS: sus métricas no son resultados académicos.")
    return {
        "generated_at": timezone.now().isoformat(),
        "filters": {"algorithm": params.get("algorithm") or None},
        "versions": versions,
        "comparison_groups": [{"group": g, "versions": ids} for g, ids in groups.items() if g and len(ids) > 1],
        "source": "Versiones registradas (metadata.json de cada artefacto y resultados del reentrenamiento).",
        "notices": notices,
    }


# ---------------------------------------------------------------------------- actividad administrativa
ACTIVITY_ACTIONS = [AuditAction.TRAINING_STARTED, AuditAction.TRAINING_FINISHED, AuditAction.TRAINING_CANCELLED,
                    AuditAction.MODEL_APPROVED, AuditAction.MODEL_REJECTED, AuditAction.MODEL_ACTIVATED,
                    AuditAction.MODEL_ROLLBACK, AuditAction.PREDICTION_RUN, AuditAction.DATA_UPLOAD,
                    AuditAction.TRAINING_DATASET, AuditAction.REPORT_EXPORTED]


def activity_report(params) -> dict:
    date_from, date_to = _date(params, "date_from"), _date(params, "date_to")

    def by_date(queryset, field="created_at"):
        if date_from:
            queryset = queryset.filter(**{f"{field}__date__gte": date_from})
        if date_to:
            queryset = queryset.filter(**{f"{field}__date__lte": date_to})
        return queryset

    runs = by_date(TrainingRun.objects.select_related("requested_by", "dataset").defer("dataset__content"))
    run_counts = {row["status"]: row["n"] for row in runs.values("status").annotate(n=Count("id")).order_by()}
    activations = by_date(ModelActivationLog.objects.select_related("performed_by"))
    audit = by_date(AuditLog.objects.filter(action__in=ACTIVITY_ACTIONS))
    audit_counts = {row["action"]: row["n"] for row in audit.values("action").annotate(n=Count("id")).order_by()}
    since = AuditLog.objects.aggregate(first=Min("created_at"))["first"]
    labels = dict(AuditAction.choices)
    return {
        "generated_at": timezone.now().isoformat(),
        "filters": {"date_from": date_from.isoformat() if date_from else None,
                    "date_to": date_to.isoformat() if date_to else None},
        "training": {
            "total": sum(run_counts.values()),
            "completed": run_counts.get(RunStatus.COMPLETED, 0),
            "failed": run_counts.get(RunStatus.FAILED, 0),
            "cancelled": run_counts.get(RunStatus.CANCELLED, 0),
            "runs": [{
                "id": r.pk, "created_at": r.created_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "requested_by": r.requested_by.username if r.requested_by else None,
                "dataset": r.dataset.filename, "rows": r.dataset.rows, "algorithms": r.algorithms,
                "status": r.status, "status_display": r.get_status_display(), "version": r.version,
                "error": r.error_message,
            } for r in runs[:200]],
        },
        "activations": [{
            "created_at": a.created_at.isoformat(), "action": a.action, "action_display": a.get_action_display(),
            "previous": a.previous_label, "new": a.new_label,
            "performed_by": a.performed_by.username if a.performed_by else "Sistema",
        } for a in activations[:200]],
        "audit_counts": [{"action": action, "label": labels.get(action, action), "count": audit_counts.get(action, 0)}
                         for action in ACTIVITY_ACTIONS],
        "coverage_since": since.isoformat() if since else None,
        "source": "Registros persistentes de entrenamiento, cambios de modelo activo y auditoría.",
        "notices": ["La auditoría cubre sólo las acciones registradas desde "
                    + (timezone.localtime(since).strftime("%Y-%m-%d") if since else "—")
                    + "; las acciones anteriores a la incorporación de cada tipo de registro no aparecen."],
    }
