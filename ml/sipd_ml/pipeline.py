"""
Orquestación completa: datos -> preprocesamiento -> entrenamiento ->
evaluación -> guardado. Usado por scripts/train.py y los notebooks.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .config import CLASSIFICATION_THRESHOLD, DEFAULT_SELECTION_METRIC, MODELS_DIR
from .evaluation import compare_models, evaluate_estimator
from .persistence import build_metadata, publish_as_default, save_artifacts
from .preprocessing import prepare_training_frame
from .training import split_and_preprocess, train_candidates


def run_training_pipeline(
    dataset: pd.DataFrame,
    *,
    selection_metric: str = DEFAULT_SELECTION_METRIC,
    algorithms: list[str] | None = None,
    forced_algorithm: str | None = None,
    models_dir: Path = MODELS_DIR,
    version: str | None = None,
    threshold: float = CLASSIFICATION_THRESHOLD,
) -> dict[str, Any]:
    is_synthetic = bool(dataset.get("is_synthetic", pd.Series([False])).any())
    features, target = prepare_training_frame(dataset)
    split = split_and_preprocess(features, target)
    candidates = train_candidates(split, algorithms)

    results = {c.algorithm: evaluate_estimator(c.estimator, split.x_test, split.y_test, threshold) for c in candidates}
    ranking = compare_models(results, selection_metric)
    selected_algorithm = forced_algorithm or ranking[0]["algorithm"]
    if selected_algorithm not in results:
        raise ValueError(f"El algoritmo forzado '{selected_algorithm}' no fue entrenado.")

    version = version or datetime.now().strftime("%Y%m%d%H%M%S")
    saved_dirs = {}
    for candidate in candidates:
        metadata = build_metadata(
            candidate.algorithm,
            version,
            results[candidate.algorithm],
            is_synthetic=is_synthetic,
            selection_metric=selection_metric,
            dataset_rows=len(dataset),
            selected=candidate.algorithm == selected_algorithm,
        )
        target_dir = Path(models_dir) / f"{candidate.algorithm}_{version}"
        saved_dirs[candidate.algorithm] = save_artifacts(target_dir, candidate.estimator, split.preprocessor, metadata)

    publish_as_default(saved_dirs[selected_algorithm], Path(models_dir))
    return {
        "version": version,
        "selected_algorithm": selected_algorithm,
        "selection_metric": selection_metric,
        "ranking": ranking,
        "saved_dirs": {k: str(v) for k, v in saved_dirs.items()},
        "is_synthetic": is_synthetic,
    }
