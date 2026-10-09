"""
Generador de datos SINTÉTICOS.

ADVERTENCIA: estos datos son ficticios y sólo sirven para pruebas técnicas
del software. No representan estudiantes reales ni resultados académicos
reales. Las métricas obtenidas con ellos NO deben reportarse como hallazgos
del proyecto de grado.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import RANDOM_STATE

PROGRAMS = {
    "SIS": ("Ingeniería de Sistemas", 0.10),
    "SOF": ("Ingeniería de Software", 0.15),
    "CIV": ("Ingeniería Civil", -0.10),
    "IND": ("Ingeniería Industrial", 0.0),
    "ELE": ("Ingeniería Electrónica", 0.05),
}

ACADEMIC_STATUSES = ["Activo", "Activo", "Activo", "Activo", "Prueba académica"]


def _with_missing(values: np.ndarray, rng: np.random.Generator, ratio: float) -> np.ndarray:
    values = values.astype(float)
    mask = rng.random(len(values)) < ratio
    values[mask] = np.nan
    return values


def generate_student_features(n_rows: int, seed: int = RANDOM_STATE) -> pd.DataFrame:
    """Genera variables académicas y de encuesta plausibles (sin etiqueta)."""
    rng = np.random.default_rng(seed)
    program_codes = rng.choice(list(PROGRAMS), size=n_rows)
    semester = rng.integers(1, 11, size=n_rows)

    ability = rng.normal(0, 1, size=n_rows)  # variable latente no observada
    gpa = np.clip(3.55 + 0.5 * ability + rng.normal(0, 0.2, n_rows), 0.5, 5.0).round(2)
    previous_gpa = np.clip(gpa - rng.normal(0.05, 0.3, n_rows), 0.5, 5.0).round(2).astype(float)
    previous_gpa[semester == 1] = np.nan

    credits_enrolled = rng.integers(10, 21, size=n_rows)
    fail_rate = np.clip(0.9 - 0.45 * gpa + rng.normal(0, 0.3, n_rows), 0, None)
    failed_subjects = np.minimum(rng.poisson(fail_rate * 1.3), 6)
    credits_failed = np.minimum(failed_subjects * rng.integers(2, 5, size=n_rows), credits_enrolled)
    credits_approved = credits_enrolled - credits_failed

    attendance = np.clip(84 + 7 * ability + rng.normal(0, 6, n_rows), 40, 100).round(1)
    course_repetitions = np.minimum(rng.poisson(np.clip(0.8 - 0.4 * ability, 0.05, None)), 5)

    works = _with_missing(rng.binomial(1, 0.35, n_rows), rng, 0.2)
    stratum = _with_missing(rng.choice([1, 2, 3, 4, 5, 6], n_rows, p=[0.2, 0.3, 0.28, 0.14, 0.05, 0.03]), rng, 0.2)
    financial = _with_missing(np.clip(np.round(3 - 0.5 * (np.nan_to_num(stratum, nan=3) - 3) + rng.normal(0, 1, n_rows)), 1, 5), rng, 0.25)
    motivation = _with_missing(np.clip(np.round(3.4 + 0.6 * ability + rng.normal(0, 0.9, n_rows)), 1, 5), rng, 0.25)

    return pd.DataFrame(
        {
            "program_code": program_codes,
            "semester": semester,
            "gpa": gpa,
            "previous_gpa": previous_gpa,
            "credits_enrolled": credits_enrolled,
            "credits_approved": credits_approved,
            "credits_failed": credits_failed,
            "failed_subjects": failed_subjects,
            "attendance_percentage": attendance,
            "course_repetitions": course_repetitions,
            "works_while_studying": works,
            "socioeconomic_stratum": stratum,
            "financial_difficulty": financial,
            "motivation_level": motivation,
        }
    )


def synthetic_dropout_label(frame: pd.DataFrame, seed: int = RANDOM_STATE) -> pd.Series:
    """Asigna una etiqueta sintética de deserción con una regla probabilística
    conocida (útil para verificar que el pipeline aprende algo)."""
    rng = np.random.default_rng(seed + 1)
    program_effect = frame["program_code"].map({k: v[1] for k, v in PROGRAMS.items()}).fillna(0)
    logit = (
        -2.1
        - 1.5 * (frame["gpa"] - 3.4)
        - 0.06 * (frame["attendance_percentage"] - 85)
        + 0.35 * frame["failed_subjects"]
        + 0.30 * frame["course_repetitions"]
        + 0.50 * frame["works_while_studying"].fillna(0.35)
        + 0.30 * (frame["financial_difficulty"].fillna(3) - 3)
        - 0.30 * (frame["motivation_level"].fillna(3) - 3)
        - 0.10 * (frame["semester"] - 5)
        + program_effect
        + rng.normal(0, 0.7, len(frame))
    )
    probability = 1 / (1 + np.exp(-logit))
    return pd.Series(rng.binomial(1, probability), index=frame.index, name="dropout")


def generate_training_dataset(n_rows: int = 4000, seed: int = RANDOM_STATE) -> pd.DataFrame:
    frame = generate_student_features(n_rows, seed)
    frame["dropout"] = synthetic_dropout_label(frame, seed)
    frame.insert(0, "is_synthetic", True)
    return frame


def simulate_student_trajectories(n_students: int, periods: list[str], seed: int = RANDOM_STATE) -> list[dict]:
    """Simula trayectorias por periodo de estudiantes FICTICIOS (E001, E002, ...).

    Cada estudiante tiene entre 1 y len(periods) registros consecutivos que
    terminan en el último periodo (o antes, si 'abandonó' en la simulación).
    """
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    for index in range(1, n_students + 1):
        code = f"E{index:03d}"
        program = str(rng.choice(list(PROGRAMS)))
        ability = rng.normal(0, 1)
        trend = rng.normal(-0.02, 0.18)
        works = None if rng.random() < 0.2 else int(rng.random() < 0.35)
        stratum = None if rng.random() < 0.2 else int(rng.choice([1, 2, 3, 4, 5, 6], p=[0.2, 0.3, 0.28, 0.14, 0.05, 0.03]))
        n_periods = int(rng.integers(1, len(periods) + 1))
        start = len(periods) - n_periods
        start_semester = int(rng.integers(1, 9))
        withdrawn_early = rng.random() < 0.06 and n_periods > 1
        active_periods = periods[start:-1] if withdrawn_early else periods[start:]
        for step, period in enumerate(active_periods):
            semester = min(start_semester + step, 10)
            gpa = float(np.clip(3.5 + 0.5 * ability + trend * step + rng.normal(0, 0.2), 0.5, 5.0))
            credits_enrolled = int(rng.integers(12, 21))
            fail_rate = max(0.9 - 0.45 * gpa + rng.normal(0, 0.3), 0)
            failed_subjects = int(min(rng.poisson(fail_rate * 1.3), 6))
            credits_failed = int(min(failed_subjects * rng.integers(2, 5), credits_enrolled))
            attendance = float(np.clip(84 + 7 * ability + 12 * trend * step + rng.normal(0, 5), 40, 100))
            is_last = step == len(active_periods) - 1
            status = "Prueba académica" if gpa < 3.0 else "Activo"
            if withdrawn_early and is_last:
                status = "Retirado"
            rows.append({
                "student_code": code,
                "program_code": program,
                "academic_period": period,
                "semester": semester,
                "gpa": round(gpa, 2),
                "credits_enrolled": credits_enrolled,
                "credits_approved": credits_enrolled - credits_failed,
                "credits_failed": credits_failed,
                "failed_subjects": failed_subjects,
                "attendance_percentage": round(attendance, 1),
                "academic_status": status,
                "course_repetitions": int(min(rng.poisson(max(0.8 - 0.4 * ability, 0.05)), 5)),
                "works_while_studying": works,
                "socioeconomic_stratum": stratum,
                "financial_difficulty": None if rng.random() < 0.25 else int(np.clip(round(3 + rng.normal(0, 1)), 1, 5)),
                "motivation_level": None if rng.random() < 0.25 else int(np.clip(round(3.4 + 0.6 * ability - 2 * trend * step + rng.normal(0, 0.8)), 1, 5)),
            })
    return rows
