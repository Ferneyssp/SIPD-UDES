"""
Construcción de variables derivadas.

Estas funciones se usan de forma idéntica en entrenamiento (sobre un DataFrame)
y en inferencia (sobre un diccionario por estudiante).
"""
from __future__ import annotations

import math
from typing import Any, Mapping

import pandas as pd

from .config import MODEL_FEATURES


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def compute_approval_rate(credits_approved: Any, credits_enrolled: Any) -> float | None:
    approved = _to_float(credits_approved)
    enrolled = _to_float(credits_enrolled)
    if approved is None or not enrolled:
        return None
    return round(approved / enrolled, 4)


def compute_gpa_change(gpa: Any, previous_gpa: Any) -> float | None:
    current = _to_float(gpa)
    previous = _to_float(previous_gpa)
    if current is None or previous is None:
        return None
    return round(current - previous, 4)


def build_feature_row(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Recibe los datos crudos de un estudiante/periodo y devuelve el
    diccionario con todas las variables que espera el modelo."""
    row = {name: raw.get(name) for name in MODEL_FEATURES}
    row["approval_rate"] = compute_approval_rate(raw.get("credits_approved"), raw.get("credits_enrolled"))
    row["gpa_change"] = compute_gpa_change(raw.get("gpa"), raw.get("previous_gpa"))
    for key, value in row.items():
        if key == "program_code":
            row[key] = None if value in (None, "") else str(value)
        else:
            row[key] = _to_float(value)
    return row


def add_derived_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Versión vectorizada de build_feature_row para DataFrames."""
    result = frame.copy()
    enrolled = pd.to_numeric(result["credits_enrolled"], errors="coerce")
    approved = pd.to_numeric(result["credits_approved"], errors="coerce")
    result["approval_rate"] = (approved / enrolled.where(enrolled > 0)).round(4)
    gpa = pd.to_numeric(result["gpa"], errors="coerce")
    previous = pd.to_numeric(result.get("previous_gpa"), errors="coerce")
    result["gpa_change"] = (gpa - previous).round(4)
    return result


def rows_to_frame(rows: list[Mapping[str, Any]]) -> pd.DataFrame:
    """Convierte filas (ya procesadas con build_feature_row) al DataFrame
    con las columnas en el orden exacto que espera el preprocesador."""
    frame = pd.DataFrame(list(rows), columns=MODEL_FEATURES)
    numeric = [c for c in MODEL_FEATURES if c != "program_code"]
    frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="coerce").astype(float)
    frame["program_code"] = frame["program_code"].astype(object)
    return frame
