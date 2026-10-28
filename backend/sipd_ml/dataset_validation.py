"""
Validación de un dataset de ENTRENAMIENTO antes de reentrenar.

Las columnas requeridas se obtienen de config.py (las mismas que exige
preprocessing.prepare_training_frame); los rangos son los del validador de
cargas académicas (uploads/validators.py). El contenido se interpreta sólo
como texto/números: nunca se evalúa ni se ejecuta.

El resultado incluye el DataFrame ya tipado que recibe el pipeline, de modo
que se entrena exactamente con los datos validados.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .config import (
    CATEGORICAL_FEATURES,
    DERIVED_FEATURES,
    MODEL_FEATURES,
    SURVEY_FEATURES,
    TARGET_COLUMN,
)

# Columnas que el pipeline necesita en el archivo (las derivadas se calculan).
REQUIRED_COLUMNS = [c for c in MODEL_FEATURES if c not in DERIVED_FEATURES and c not in SURVEY_FEATURES] + [TARGET_COLUMN]
# Variables de encuesta: opcionales; si faltan, el preprocesador las imputa (ver config.SURVEY_FEATURES).
OPTIONAL_COLUMNS = list(SURVEY_FEATURES) + ["is_synthetic"]
# Sin estos valores una fila no puede usarse (el objetivo y la variable categórica no se imputan).
NON_NULL_COLUMNS = [TARGET_COLUMN] + CATEGORICAL_FEATURES
MAX_ROWS_PER_ISSUE = 10


class DatasetRejected(Exception):
    """El archivo no puede interpretarse como un CSV de entrenamiento."""

    def __init__(self, message: str, code: str = "FILE"):
        super().__init__(message)
        self.code = code


@dataclass
class DatasetReport:
    rows: int = 0
    columns: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    frame: pd.DataFrame | None = None

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def error(self, code: str, message: str, column: str = "-", rows: list[int] | None = None, count: int | None = None):
        self.errors.append({"code": code, "column": column, "message": message,
                            "rows": (rows or [])[:MAX_ROWS_PER_ISSUE], "count": count if count is not None else len(rows or [])})

    def warning(self, code: str, message: str, column: str = "-", count: int = 0):
        self.warnings.append({"code": code, "column": column, "message": message, "count": count})

    def as_dict(self) -> dict[str, Any]:
        return {"rows": self.rows, "columns": self.columns, "errors": self.errors, "warnings": self.warnings,
                "summary": self.summary, "is_valid": self.is_valid}


def numeric_ranges(gpa_min: float, gpa_max: float) -> dict[str, tuple[float, float, bool]]:
    """(mínimo, máximo, entero) por columna numérica."""
    return {
        "semester": (1, 12, True),
        "gpa": (gpa_min, gpa_max, False),
        "previous_gpa": (gpa_min, gpa_max, False),
        "credits_enrolled": (0, 40, True),
        "credits_approved": (0, 40, True),
        "credits_failed": (0, 40, True),
        "failed_subjects": (0, 20, True),
        "attendance_percentage": (0, 100, False),
        "course_repetitions": (0, 20, True),
        "works_while_studying": (0, 1, True),
        "socioeconomic_stratum": (1, 6, True),
        "financial_difficulty": (1, 5, True),
        "motivation_level": (1, 5, True),
    }


def _line_numbers(mask: pd.Series) -> list[int]:
    # +2: la fila 1 del archivo es el encabezado y el índice empieza en 0.
    return [int(i) + 2 for i in mask[mask].index[:MAX_ROWS_PER_ISSUE]]


def _read_frame(text: str) -> pd.DataFrame:
    header = text.splitlines()[0] if text else ""
    delimiter = ";" if header.count(";") > header.count(",") else ","
    try:
        # dtype=str y sin conversión automática de NA: cada valor se valida explícitamente.
        return pd.read_csv(io.StringIO(text), sep=delimiter, dtype=str, keep_default_na=False,
                           skipinitialspace=True, engine="python")
    except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError) as exc:
        raise DatasetRejected("No se pudo leer el archivo como CSV: revise separadores y comillas.") from exc


def validate_training_dataset(
    text: str,
    *,
    gpa_min: float,
    gpa_max: float,
    max_rows: int,
    min_rows: int,
    min_rows_per_class: int,
    known_programs: set[str] | None = None,
) -> DatasetReport:
    raw = _read_frame(text)
    report = DatasetReport()
    columns = [str(c).strip() for c in raw.columns]
    raw.columns = columns
    report.columns = columns

    duplicated = sorted({c for c in columns if columns.count(c) > 1})
    if duplicated:
        report.error("FORMAT", f"Columnas duplicadas: {', '.join(duplicated)}.")
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]
    if missing:
        report.error("MISSING_COLUMNS", f"Faltan columnas obligatorias: {', '.join(missing)}.", count=len(missing))
    if report.errors:
        return report

    raw = raw[[c for c in columns if c.strip()]]
    raw = raw.map(lambda v: v.strip() if isinstance(v, str) else v)
    raw = raw[(raw != "").any(axis=1)].reset_index(drop=True)  # filas vacías
    report.rows = len(raw)
    if report.rows == 0:
        report.error("INSUFFICIENT", "El archivo no contiene registros.")
        return report
    if report.rows > max_rows:
        report.error("INSUFFICIENT", f"El archivo supera el máximo de {max_rows} registros.")
        return report

    absent_optional = [c for c in SURVEY_FEATURES if c not in columns]
    if absent_optional:
        report.warning("OPTIONAL_ABSENT", "Columnas de encuesta ausentes; el preprocesamiento las imputará: "
                       + ", ".join(absent_optional) + ".", count=len(absent_optional))
    ignored = [c for c in columns if c not in REQUIRED_COLUMNS + OPTIONAL_COLUMNS]
    if ignored:
        report.warning("IGNORED_COLUMNS", f"Columnas no utilizadas por el modelo (se ignoran): {', '.join(ignored)}.",
                       count=len(ignored))

    frame = pd.DataFrame(index=raw.index)
    for column in NON_NULL_COLUMNS:
        empty = raw[column] == ""
        if empty.any():
            report.error("FORMAT", "Valor obligatorio vacío.", column, _line_numbers(empty), int(empty.sum()))

    frame["program_code"] = raw["program_code"].str.upper().replace("", None)

    target = pd.to_numeric(raw[TARGET_COLUMN].str.replace(",", ".", regex=False), errors="coerce")
    bad_target = (raw[TARGET_COLUMN] != "") & ~target.isin([0, 1])
    if bad_target.any():
        report.error("TARGET", f"La variable objetivo '{TARGET_COLUMN}' sólo admite 0 (no desertó) o 1 (desertó).",
                     TARGET_COLUMN, _line_numbers(bad_target), int(bad_target.sum()))

    for column, (minimum, maximum, integer) in numeric_ranges(gpa_min, gpa_max).items():
        if column not in raw.columns:
            frame[column] = float("nan")
            continue
        text_values = raw[column].str.replace(",", ".", regex=False)
        values = pd.to_numeric(text_values, errors="coerce")
        present = text_values != ""
        not_numeric = present & values.isna()
        if not_numeric.any():
            report.error("FORMAT", "Debe ser numérico.", column, _line_numbers(not_numeric), int(not_numeric.sum()))
        out_of_range = present & values.notna() & ((values < minimum) | (values > maximum))
        if out_of_range.any():
            report.error("FORMAT", f"Fuera de rango ({minimum:g}-{maximum:g}).", column, _line_numbers(out_of_range),
                         int(out_of_range.sum()))
        if integer:
            fractional = present & values.notna() & (values % 1 != 0)
            if fractional.any():
                report.error("FORMAT", "Debe ser un número entero.", column, _line_numbers(fractional), int(fractional.sum()))
        empties = int((~present).sum())
        if empties == report.rows and column not in SURVEY_FEATURES:
            report.error("FORMAT", "La columna no tiene ningún valor.", column, count=empties)
        elif empties:
            report.warning("MISSING_VALUES", f"{empties} valores vacíos; se imputarán con la mediana del entrenamiento.",
                           column, empties)
        frame[column] = values.astype(float)

    incoherent = (frame["credits_approved"] + frame["credits_failed"]) > frame["credits_enrolled"]
    if incoherent.any():
        report.error("FORMAT", "Créditos aprobados + reprobados supera los matriculados.", "credits_approved",
                     _line_numbers(incoherent), int(incoherent.sum()))

    if "is_synthetic" in raw.columns:
        frame["is_synthetic"] = raw["is_synthetic"].str.lower().isin({"1", "true", "si", "sí", "yes"})
    frame[TARGET_COLUMN] = target

    class_counts = {str(int(k)): int(v) for k, v in target[target.isin([0, 1])].value_counts().items()}
    programs = sorted(p for p in frame["program_code"].dropna().unique())
    report.summary = {
        "class_counts": {"0": class_counts.get("0", 0), "1": class_counts.get("1", 0)},
        "positive_rate": round(class_counts.get("1", 0) / report.rows, 4) if report.rows else None,
        "programs": programs,
        "is_synthetic": bool(frame.get("is_synthetic", pd.Series([False])).any()),
        "duplicated_rows": int(raw.duplicated().sum()),
    }
    if report.summary["duplicated_rows"]:
        report.warning("DUPLICATED_ROWS", "Hay filas idénticas en el archivo.", count=report.summary["duplicated_rows"])
    if known_programs is not None:
        unknown = [p for p in programs if p not in known_programs]
        if unknown:
            report.warning("UNKNOWN_PROGRAMS", "Programas no registrados en el sistema (el modelo los aprenderá igual): "
                           + ", ".join(unknown) + ".", "program_code", len(unknown))

    if report.rows < min_rows:
        report.error("INSUFFICIENT", f"Se requieren al menos {min_rows} registros para entrenar y evaluar "
                     f"(el archivo tiene {report.rows}).", count=report.rows)
    for label, name in (("1", "casos de deserción (1)"), ("0", "casos sin deserción (0)")):
        if report.summary["class_counts"][label] < min_rows_per_class:
            report.error("INSUFFICIENT", f"Se requieren al menos {min_rows_per_class} {name} para la partición "
                         f"estratificada de prueba (hay {report.summary['class_counts'][label]}).", TARGET_COLUMN)

    if report.is_valid:
        frame[TARGET_COLUMN] = frame[TARGET_COLUMN].astype(int)
        frame["program_code"] = frame["program_code"].astype(object)
        report.frame = frame
    return report
