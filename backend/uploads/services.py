"""Procesamiento de cargas CSV en dos pasos: validar -> confirmar."""
from __future__ import annotations

import hashlib
import logging

from django.db import transaction
from django.utils import timezone

from academic.models import AcademicPeriod, AcademicRecord, Program
from ml.services import ModelNotAvailableError
from predictions.services import predict_records
from students.models import Student

from .models import DataUpload, UploadStatus
from .validators import FileRejected, check_file, validate_csv

logger = logging.getLogger(__name__)


def active_program_codes() -> set[str]:
    return set(Program.objects.filter(is_active=True).values_list("code", flat=True))


def create_validated_upload(uploaded_file, user) -> DataUpload:
    """Valida el archivo y registra la carga. No modifica datos académicos."""
    check_file(uploaded_file)
    raw = uploaded_file.read()
    checksum = hashlib.sha256(raw).hexdigest()
    uploaded_file.seek(0)
    upload = DataUpload(uploaded_by=user, filename=uploaded_file.name[:255], checksum=checksum)
    try:
        report = validate_csv(raw, active_program_codes())
    except FileRejected as exc:
        upload.status = UploadStatus.REJECTED
        upload.message = str(exc)
        upload.errors = [{"row": None, "column": "-", "message": str(exc), "value": None}]
        upload.file.save(f"{checksum[:16]}.csv", uploaded_file, save=False)
        upload.save()
        return upload

    upload.records_found = report.records_found
    upload.records_valid = report.records_valid
    upload.records_failed = report.records_failed
    upload.errors = report.errors
    if report.records_valid == 0:
        upload.status = UploadStatus.REJECTED
        upload.message = "Ningún registro es válido. Corrija los errores e intente de nuevo."
    else:
        upload.status = UploadStatus.VALIDATED
        upload.message = "Archivo validado. Revise los errores y confirme la carga."
    upload.file.save(f"{checksum[:16]}.csv", uploaded_file, save=False)
    upload.save()
    return upload


def _upsert_rows(rows: list[dict], upload: DataUpload) -> list[AcademicRecord]:
    programs = {p.code: p for p in Program.objects.all()}
    periods = {p.code: p for p in AcademicPeriod.objects.all()}
    records = []
    for row in rows:
        period = periods.get(row["academic_period"])
        if period is None:
            period = AcademicPeriod.objects.create(code=row["academic_period"])
            periods[period.code] = period
        student, _ = Student.objects.get_or_create(
            anonymous_code=row["student_code"],
            defaults={"program": programs[row["program_code"]], "semester": row["semester"],
                      "academic_status": row["academic_status"], "current_period": period},
        )
        is_latest = student.current_period is None or period.code >= student.current_period.code
        if is_latest:
            student.program = programs[row["program_code"]]
            student.semester = row["semester"]
            student.academic_status = row["academic_status"]
            student.current_period = period
            student.is_active = True
            student.save()
        record, _ = AcademicRecord.objects.update_or_create(
            student=student,
            academic_period=period,
            defaults={
                "semester": row["semester"], "academic_status": row["academic_status"], "gpa": row["gpa"],
                "credits_enrolled": row["credits_enrolled"], "credits_approved": row["credits_approved"],
                "credits_failed": row["credits_failed"], "failed_subjects": row["failed_subjects"],
                "attendance_percentage": row["attendance_percentage"], "course_repetitions": row["course_repetitions"],
                "works_while_studying": row["works_while_studying"], "socioeconomic_stratum": row["socioeconomic_stratum"],
                "financial_difficulty": row["financial_difficulty"], "motivation_level": row["motivation_level"],
                "source_upload": upload,
            },
        )
        records.append(record)
    return records


def confirm_upload(upload: DataUpload, user, run_predictions: bool = True) -> DataUpload:
    if upload.status != UploadStatus.VALIDATED:
        raise FileRejected("Sólo se pueden confirmar cargas en estado 'Validado'.")
    with upload.file.open("rb") as handle:
        raw = handle.read()
    if hashlib.sha256(raw).hexdigest() != upload.checksum:
        raise FileRejected("El archivo almacenado fue modificado después de la validación.")
    report = validate_csv(raw, active_program_codes())

    with transaction.atomic():
        records = _upsert_rows(report.valid_rows, upload)
        upload.records_processed = len(records)
        upload.run_predictions = run_predictions
        upload.status = UploadStatus.PROCESSED
        upload.processed_at = timezone.now()
        upload.message = f"Se procesaron {len(records)} registros."

    if run_predictions and records:
        try:
            records = list(AcademicRecord.objects.filter(pk__in=[r.pk for r in records]).select_related("student__program", "academic_period"))
            upload.predictions_generated = len(predict_records(records, user=user))
            upload.message += f" Se generaron {upload.predictions_generated} predicciones."
        except ModelNotAvailableError as exc:
            upload.message += f" No se generaron predicciones: {exc}"
            logger.warning("Carga %s sin predicciones: %s", upload.pk, exc)
    upload.save()
    return upload
