"""
Genera archivos CSV SINTÉTICOS de ejemplo para probar el módulo "Carga de datos".

    python ml/scripts/generate_sample_uploads.py

Crea en data/sample/:
  - carga_ejemplo_valida.csv       (30 estudiantes nuevos E901-E930, periodo 2026-2)
  - carga_ejemplo_con_errores.csv  (mismo formato con errores intencionales)
"""
import csv

import _bootstrap  # noqa: F401
from sipd_ml.config import SAMPLE_DATA_DIR
from sipd_ml.synthetic import simulate_student_trajectories

COLUMNS = [
    "student_code", "program_code", "academic_period", "semester", "gpa", "credits_enrolled", "credits_approved",
    "credits_failed", "failed_subjects", "attendance_percentage", "academic_status", "course_repetitions",
    "works_while_studying", "socioeconomic_stratum", "financial_difficulty", "motivation_level",
]


def rows_for_upload(count: int, seed: int) -> list[dict]:
    rows = simulate_student_trajectories(count, ["2026-2"], seed=seed)
    for index, row in enumerate(rows, start=901):
        row["student_code"] = f"E{index}"
    return rows


def write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if row.get(k) is None else row[k]) for k in COLUMNS})


def main():
    SAMPLE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    valid = rows_for_upload(30, seed=77)
    write(SAMPLE_DATA_DIR / "carga_ejemplo_valida.csv", valid)

    with_errors = [dict(r) for r in valid[:12]]
    with_errors[1]["attendance_percentage"] = 135          # fuera de rango
    with_errors[3]["gpa"] = 7.2                            # fuera del rango institucional
    with_errors[5]["student_code"] = "Estudiante-5"        # identificador inválido
    with_errors[7]["program_code"] = "MED"                 # programa no registrado
    with_errors[8]["academic_period"] = "2026-3"           # periodo inválido
    with_errors[9]["credits_approved"] = 40                # créditos inconsistentes
    with_errors.append(dict(with_errors[0]))               # duplicado
    write(SAMPLE_DATA_DIR / "carga_ejemplo_con_errores.csv", with_errors)
    print("Archivos de ejemplo (sintéticos) generados en", SAMPLE_DATA_DIR)


if __name__ == "__main__":
    main()
