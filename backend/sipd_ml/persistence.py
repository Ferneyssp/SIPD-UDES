"""
Guardado y carga de artefactos de modelo.

Estructura en disco:
    backend/ml_models/<algoritmo>_<version>/model.joblib
    backend/ml_models/<algoritmo>_<version>/preprocessor.joblib
    backend/ml_models/<algoritmo>_<version>/metadata.json
    backend/ml_models/model.joblib, preprocessor.joblib, metadata.json  -> copia del modelo seleccionado
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import sklearn

from .config import (
    ALGORITHM_DISPLAY_NAMES,
    CATEGORICAL_FEATURES,
    METADATA_FILENAME,
    MODEL_FEATURES,
    MODEL_FILENAME,
    MODELS_DIR,
    NUMERIC_FEATURES,
    PREPROCESSOR_FILENAME,
)


def build_metadata(algorithm: str, version: str, metrics: dict[str, Any], *, is_synthetic: bool,
                   selection_metric: str, dataset_rows: int, selected: bool) -> dict[str, Any]:
    return {
        "name": ALGORITHM_DISPLAY_NAMES.get(algorithm, algorithm),
        "algorithm": algorithm,
        "version": version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "selection_metric": selection_metric,
        "selected": selected,
        "features": MODEL_FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "dataset_rows": dataset_rows,
        "is_synthetic": is_synthetic,
        "sklearn_version": sklearn.__version__,
        "disclaimer": (
            "Métricas calculadas sobre datos SINTÉTICOS con fines de prueba técnica; no representan "
            "resultados académicos reales." if is_synthetic else ""
        ),
    }


def save_artifacts(target_dir: Path, estimator, preprocessor, metadata: dict[str, Any]) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(estimator, target_dir / MODEL_FILENAME)
    joblib.dump(preprocessor, target_dir / PREPROCESSOR_FILENAME)
    (target_dir / METADATA_FILENAME).write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return target_dir


def publish_as_default(source_dir: Path, models_dir: Path = MODELS_DIR) -> None:
    """Copia el modelo seleccionado a la raíz de backend/ml_models/."""
    for filename in (MODEL_FILENAME, PREPROCESSOR_FILENAME, METADATA_FILENAME):
        shutil.copy2(source_dir / filename, models_dir / filename)


def load_metadata(model_dir: Path) -> dict[str, Any]:
    return json.loads((Path(model_dir) / METADATA_FILENAME).read_text(encoding="utf-8"))


def load_artifacts(model_dir: Path):
    model_dir = Path(model_dir)
    for filename in (MODEL_FILENAME, PREPROCESSOR_FILENAME, METADATA_FILENAME):
        if not (model_dir / filename).exists():
            raise FileNotFoundError(f"No se encontró el artefacto {filename} en {model_dir}")
    estimator = joblib.load(model_dir / MODEL_FILENAME)
    preprocessor = joblib.load(model_dir / PREPROCESSOR_FILENAME)
    return estimator, preprocessor, load_metadata(model_dir)


def list_model_dirs(models_dir: Path = MODELS_DIR) -> list[Path]:
    return sorted(p for p in Path(models_dir).iterdir() if p.is_dir() and (p / METADATA_FILENAME).exists())
