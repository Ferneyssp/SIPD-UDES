"""
Entrenamiento de modelos candidatos.

Cada candidato se entrena sobre la MISMA partición y con el MISMO
preprocesador ajustado sólo con datos de entrenamiento (evita fuga de datos).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

from .config import RANDOM_STATE, TEST_SIZE
from .preprocessing import build_preprocessor


@dataclass
class TrainedCandidate:
    algorithm: str
    estimator: Any


@dataclass
class DatasetSplit:
    x_train: np.ndarray
    x_test: np.ndarray
    y_train: pd.Series
    y_test: pd.Series
    preprocessor: ColumnTransformer
    raw_test: pd.DataFrame


def xgboost_available() -> bool:
    try:
        import xgboost  # noqa: F401
    except ImportError:
        return False
    return True


def split_and_preprocess(features: pd.DataFrame, target: pd.Series) -> DatasetSplit:
    raw_train, raw_test, y_train, y_test = train_test_split(
        features, target, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=target
    )
    preprocessor = build_preprocessor()
    x_train = preprocessor.fit_transform(raw_train)
    x_test = preprocessor.transform(raw_test)
    return DatasetSplit(x_train, x_test, y_train, y_test, preprocessor, raw_test)


def build_estimator(algorithm: str, y_train: pd.Series):
    """Los modelos se entrenan SIN reponderar clases para que la probabilidad
    estimada se mantenga calibrada (se interpreta directamente en los umbrales
    de riesgo). El desbalance se aborda evaluando Recall/F1/ROC-AUC."""
    if algorithm == "logistic_regression":
        return LogisticRegression(max_iter=2000, random_state=RANDOM_STATE)
    if algorithm == "random_forest":
        return RandomForestClassifier(
            n_estimators=300,
            max_depth=8,
            min_samples_leaf=5,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
    if algorithm == "xgboost":
        from xgboost import XGBClassifier

        return XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            eval_metric="logloss",
            random_state=RANDOM_STATE,
            n_jobs=2,
        )
    raise ValueError(f"Algoritmo no soportado: {algorithm}")


def available_algorithms() -> list[str]:
    algorithms = ["logistic_regression", "random_forest"]
    if xgboost_available():
        algorithms.append("xgboost")
    return algorithms


def train_candidates(split: DatasetSplit, algorithms: list[str] | None = None) -> list[TrainedCandidate]:
    algorithms = algorithms or available_algorithms()
    candidates = []
    for algorithm in algorithms:
        estimator = build_estimator(algorithm, split.y_train)
        estimator.fit(split.x_train, split.y_train)
        candidates.append(TrainedCandidate(algorithm=algorithm, estimator=estimator))
    return candidates
