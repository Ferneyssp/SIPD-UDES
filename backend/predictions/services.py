"""
Lógica de negocio de predicciones: arma las entradas desde la BD, invoca el
servicio de inferencia y guarda los resultados como registros históricos.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from academic.models import AcademicPeriod, AcademicRecord
from config.risk import classify_risk
from ml.services import get_predictor

from .models import Prediction, PredictionStatus


def _previous_records_map(records: list[AcademicRecord]) -> dict[int, AcademicRecord]:
    """Para cada registro, obtiene el registro del periodo anterior del mismo estudiante (1 consulta)."""
    student_ids = {r.student_id for r in records}
    history: dict[int, list[AcademicRecord]] = {}
    for record in (
        AcademicRecord.objects.filter(student_id__in=student_ids)
        .select_related("academic_period")
        .order_by("student_id", "academic_period__code")
    ):
        history.setdefault(record.student_id, []).append(record)
    previous = {}
    for record in records:
        earlier = [r for r in history.get(record.student_id, []) if r.academic_period.code < record.academic_period.code]
        previous[record.pk] = earlier[-1] if earlier else None
    return previous


@transaction.atomic
def predict_records(records: list[AcademicRecord], user=None) -> list[Prediction]:
    """Genera una predicción nueva por registro. Las anteriores del mismo
    estudiante y periodo se conservan marcadas como 'Reemplazada'."""
    records = list(records)
    if not records:
        return []
    predictor, model_version = get_predictor()
    previous = _previous_records_map(records)
    raw_inputs = [record.to_model_input(previous=previous[record.pk]) for record in records]
    results = predictor.predict_with_explanation(raw_inputs)

    for record in records:
        Prediction.objects.filter(
            student_id=record.student_id, academic_period_id=record.academic_period_id, status=PredictionStatus.CURRENT
        ).update(status=PredictionStatus.SUPERSEDED)

    predictions = [
        Prediction(
            student_id=record.student_id,
            academic_record=record,
            academic_period_id=record.academic_period_id,
            model_version=model_version,
            model_name=predictor.model_name,
            model_version_label=predictor.model_version,
            probability=result["probability"],
            risk_level=classify_risk(result["probability"]),
            status=PredictionStatus.CURRENT,
            input_features=result["features"],
            explanation=result["explanation"],
            created_by=user,
        )
        for record, result in zip(records, results)
    ]
    return Prediction.objects.bulk_create(predictions)


def predict_period(period: AcademicPeriod, user=None, program_ids=None, batch_size: int = 500) -> int:
    queryset = AcademicRecord.objects.filter(academic_period=period, student__is_active=True).select_related(
        "student__program", "academic_period"
    )
    if program_ids is not None:
        queryset = queryset.filter(student__program_id__in=program_ids)
    total = 0
    batch: list[AcademicRecord] = []
    for record in queryset.iterator(chunk_size=batch_size):
        batch.append(record)
        if len(batch) >= batch_size:
            total += len(predict_records(batch, user))
            batch = []
    if batch:
        total += len(predict_records(batch, user))
    return total


def serialize_result(prediction: Prediction) -> dict:
    """Formato de salida estándar de una predicción."""
    return {
        "student_id": prediction.student.anonymous_code,
        "academic_period": prediction.academic_period.code,
        "risk_probability": round(prediction.probability, 4),
        "risk_percentage": prediction.risk_percentage,
        "risk_level": prediction.get_risk_level_display(),
        "model": prediction.model_name,
        "model_version": prediction.model_version_label,
        "prediction_date": timezone.localtime(prediction.prediction_date).date().isoformat(),
    }
