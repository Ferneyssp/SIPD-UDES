"""
Validación de archivos CSV de información académica.

Se valida: tipo/tamaño del archivo, codificación, columnas requeridas, tipos
de datos, valores faltantes, rangos, duplicados e identificadores. Ninguna
fila con errores se procesa en silencio: todos los errores se reportan.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field

from django.conf import settings

from academic.models import PERIOD_CODE_REGEX
from students.models import ANONYMOUS_CODE_REGEX, AcademicStatus

REQUIRED_COLUMNS = [
    "student_code", "program_code", "academic_period", "semester", "gpa", "credits_enrolled",
    "credits_approved", "credits_failed", "failed_subjects", "attendance_percentage", "academic_status",
]
OPTIONAL_COLUMNS = [
    "course_repetitions", "works_while_studying", "socioeconomic_stratum", "financial_difficulty", "motivation_level",
]
ALLOWED_EXTENSIONS = (".csv",)
ALLOWED_CONTENT_TYPES = {"text/csv", "application/csv", "text/plain", "application/vnd.ms-excel", "application/octet-stream", ""}
MAX_ERRORS_STORED = 500
TRUE_VALUES = {"1", "si", "sí", "true", "yes", "s"}
FALSE_VALUES = {"0", "no", "false", "n"}


class FileRejected(Exception):
    """El archivo completo no es aceptable (estructura, tipo, tamaño...)."""


@dataclass
class ValidationReport:
    records_found: int = 0
    valid_rows: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    failed_lines: set[int] = field(default_factory=set)
    columns: list[str] = field(default_factory=list)

    @property
    def records_valid(self) -> int:
        return len(self.valid_rows)

    @property
    def records_failed(self) -> int:
        return len(self.failed_lines)

    def add_error(self, line: int, column: str, message: str, value=None):
        self.failed_lines.add(line)
        if len(self.errors) < MAX_ERRORS_STORED:
            self.errors.append({"row": line, "column": column, "message": message, "value": None if value is None else str(value)[:50]})


def check_file(uploaded_file) -> None:
    name = (uploaded_file.name or "").lower()
    if not name.endswith(ALLOWED_EXTENSIONS):
        raise FileRejected("Sólo se permiten archivos .csv.")
    if uploaded_file.size == 0:
        raise FileRejected("El archivo está vacío.")
    if uploaded_file.size > settings.UPLOAD_MAX_BYTES:
        raise FileRejected(f"El archivo supera el tamaño máximo de {settings.UPLOAD_MAX_BYTES // (1024 * 1024)} MB.")
    content_type = (getattr(uploaded_file, "content_type", "") or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise FileRejected("Tipo de archivo no permitido.")


def decode_content(raw: bytes) -> str:
    if b"\x00" in raw[:4096]:
        raise FileRejected("El archivo parece binario; se esperaba texto CSV.")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise FileRejected("El archivo debe estar codificado en UTF-8.") from exc


def _detect_delimiter(sample: str) -> str:
    header = sample.splitlines()[0] if sample else ""
    return ";" if header.count(";") > header.count(",") else ","


def _parse_int(value, column, line, report, minimum, maximum, required=True):
    if value in (None, ""):
        if required:
            report.add_error(line, column, "Valor requerido faltante.")
        return None
    try:
        number = float(value.replace(",", "."))
        if not number.is_integer():
            raise ValueError
        number = int(number)
    except ValueError:
        report.add_error(line, column, "Debe ser un número entero.", value)
        return None
    if not minimum <= number <= maximum:
        report.add_error(line, column, f"Fuera de rango ({minimum}-{maximum}).", value)
        return None
    return number


def _parse_float(value, column, line, report, minimum, maximum):
    if value in (None, ""):
        report.add_error(line, column, "Valor requerido faltante.")
        return None
    try:
        number = float(value.replace(",", "."))
    except ValueError:
        report.add_error(line, column, "Debe ser numérico.", value)
        return None
    if not minimum <= number <= maximum:
        report.add_error(line, column, f"Fuera de rango ({minimum}-{maximum}).", value)
        return None
    return round(number, 2)


def _parse_bool(value, column, line, report):
    if value in (None, ""):
        return None
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    report.add_error(line, column, "Valor inválido (use 1/0 o si/no).", value)
    return None


def validate_row(raw: dict, line: int, report: ValidationReport, program_codes: set[str]) -> dict | None:
    row = {key: (value or "").strip() for key, value in raw.items() if key}
    code = row.get("student_code", "").upper()
    if not code:
        report.add_error(line, "student_code", "Valor requerido faltante.")
    elif not re.match(ANONYMOUS_CODE_REGEX, code):
        report.add_error(line, "student_code", "Identificador inválido (formato E001).", code)

    program = row.get("program_code", "").upper()
    if not program:
        report.add_error(line, "program_code", "Valor requerido faltante.")
    elif program not in program_codes:
        report.add_error(line, "program_code", "Programa no registrado en el sistema.", program)

    period = row.get("academic_period", "")
    if not re.match(PERIOD_CODE_REGEX, period):
        report.add_error(line, "academic_period", "Periodo inválido (formato AAAA-1 o AAAA-2).", period)

    status = row.get("academic_status", "")
    valid_statuses = {s.value.lower(): s.value for s in AcademicStatus}
    if status.lower() not in valid_statuses:
        report.add_error(line, "academic_status", f"Estado inválido. Opciones: {', '.join(valid_statuses.values())}.", status)

    parsed = {
        "semester": _parse_int(row.get("semester"), "semester", line, report, 1, 12),
        "gpa": _parse_float(row.get("gpa"), "gpa", line, report, settings.GPA_MIN, settings.GPA_MAX),
        "credits_enrolled": _parse_int(row.get("credits_enrolled"), "credits_enrolled", line, report, 0, 40),
        "credits_approved": _parse_int(row.get("credits_approved"), "credits_approved", line, report, 0, 40),
        "credits_failed": _parse_int(row.get("credits_failed"), "credits_failed", line, report, 0, 40),
        "failed_subjects": _parse_int(row.get("failed_subjects"), "failed_subjects", line, report, 0, 20),
        "attendance_percentage": _parse_float(row.get("attendance_percentage"), "attendance_percentage", line, report, 0, 100),
        "course_repetitions": _parse_int(row.get("course_repetitions"), "course_repetitions", line, report, 0, 20, required=False),
        "works_while_studying": _parse_bool(row.get("works_while_studying"), "works_while_studying", line, report),
        "socioeconomic_stratum": _parse_int(row.get("socioeconomic_stratum"), "socioeconomic_stratum", line, report, 1, 6, required=False),
        "financial_difficulty": _parse_int(row.get("financial_difficulty"), "financial_difficulty", line, report, 1, 5, required=False),
        "motivation_level": _parse_int(row.get("motivation_level"), "motivation_level", line, report, 1, 5, required=False),
    }
    enrolled, approved, failed = parsed["credits_enrolled"], parsed["credits_approved"], parsed["credits_failed"]
    if None not in (enrolled, approved, failed) and approved + failed > enrolled:
        report.add_error(line, "credits_approved", "Créditos aprobados + reprobados supera los matriculados.")

    if line in report.failed_lines:
        return None
    parsed["course_repetitions"] = parsed["course_repetitions"] or 0
    return {
        "student_code": code,
        "program_code": program,
        "academic_period": period,
        "academic_status": valid_statuses[status.lower()],
        **parsed,
    }


def validate_csv(raw_bytes: bytes, program_codes: set[str]) -> ValidationReport:
    text = decode_content(raw_bytes)
    reader = csv.DictReader(io.StringIO(text), delimiter=_detect_delimiter(text[:2048]))
    columns = [c.strip() for c in (reader.fieldnames or []) if c]
    reader.fieldnames = columns
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]
    if missing:
        raise FileRejected(f"Faltan columnas requeridas: {', '.join(missing)}.")
    duplicated_columns = {c for c in columns if columns.count(c) > 1}
    if duplicated_columns:
        raise FileRejected(f"Columnas duplicadas: {', '.join(sorted(duplicated_columns))}.")

    report = ValidationReport(columns=columns)
    seen: dict[tuple[str, str], int] = {}
    for index, raw in enumerate(reader, start=2):  # la fila 1 es el encabezado
        if not any((value or "").strip() for key, value in raw.items() if key):
            continue  # filas vacías
        report.records_found += 1
        if report.records_found > settings.UPLOAD_MAX_ROWS:
            raise FileRejected(f"El archivo supera el máximo de {settings.UPLOAD_MAX_ROWS} registros.")
        if None in raw:
            report.add_error(index, "-", "La fila tiene más columnas que el encabezado.")
            continue
        parsed = validate_row(raw, index, report, program_codes)
        if parsed is None:
            continue
        key = (parsed["student_code"], parsed["academic_period"])
        if key in seen:
            report.add_error(index, "student_code", f"Registro duplicado (misma combinación en la fila {seen[key]}).", parsed["student_code"])
            continue
        seen[key] = index
        parsed["line"] = index
        report.valid_rows.append(parsed)
    if report.records_found == 0:
        raise FileRejected("El archivo no contiene registros.")
    return report


def template_csv() -> str:
    header = REQUIRED_COLUMNS + OPTIONAL_COLUMNS
    examples = [
        ["E001", "SIS", "2026-2", "6", "3.1", "18", "12", "6", "2", "78", "Activo", "1", "1", "3", "4", "3"],
        ["E002", "CIV", "2026-2", "3", "4.2", "17", "17", "0", "0", "95", "Activo", "0", "0", "", "", ""],
    ]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(examples)
    return buffer.getvalue()
