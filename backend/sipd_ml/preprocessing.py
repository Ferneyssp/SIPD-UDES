"""
Preprocesamiento reproducible.

Se construye un ColumnTransformer de scikit-learn que se ajusta UNA vez
durante el entrenamiento y se serializa (preprocessor.joblib). En inferencia
se carga el mismo objeto ya ajustado, garantizando compatibilidad exacta.
"""
from __future__ import annotations

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import CATEGORICAL_FEATURES, MODEL_FEATURES, NUMERIC_FEATURES, TARGET_COLUMN
from .features import add_derived_features


def build_preprocessor() -> ColumnTransformer:
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, NUMERIC_FEATURES),
            ("cat", categorical_pipeline, CATEGORICAL_FEATURES),
        ],
        remainder="drop",
        verbose_feature_names_out=True,
    )


def prepare_training_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Calcula variables derivadas, valida columnas y separa X / y."""
    enriched = add_derived_features(frame)
    missing = [c for c in MODEL_FEATURES + [TARGET_COLUMN] if c not in enriched.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas para entrenar: {missing}")
    features = enriched[MODEL_FEATURES].copy()
    numeric = [c for c in MODEL_FEATURES if c not in CATEGORICAL_FEATURES]
    features[numeric] = features[numeric].apply(pd.to_numeric, errors="coerce").astype(float)
    features["program_code"] = features["program_code"].astype(object)
    target = enriched[TARGET_COLUMN].astype(int)
    return features, target


def original_feature_for(transformed_name: str) -> str:
    """Mapea 'num__gpa' -> 'gpa' y 'cat__program_code_SIS' -> 'program_code'."""
    _, _, name = transformed_name.partition("__")
    for categorical in CATEGORICAL_FEATURES:
        if name.startswith(categorical + "_"):
            return categorical
    return name
