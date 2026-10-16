"""
Servicio de inferencia.

Carga un modelo YA ENTRENADO (no reentrena) y devuelve la probabilidad
estimada de riesgo junto con las variables que más pesaron en el resultado.
Las explicaciones son asociativas: indican qué variables usó el modelo,
NO relaciones causales.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .config import FEATURE_LABELS, MODELS_DIR
from .features import build_feature_row, rows_to_frame
from .persistence import load_artifacts
from .preprocessing import original_feature_for


class RiskPredictor:
    def __init__(self, estimator, preprocessor, metadata: dict[str, Any]):
        self.estimator = estimator
        self.preprocessor = preprocessor
        self.metadata = metadata
        self.transformed_names = list(preprocessor.get_feature_names_out())

    @classmethod
    def from_directory(cls, model_dir: Path | str = MODELS_DIR) -> "RiskPredictor":
        estimator, preprocessor, metadata = load_artifacts(Path(model_dir))
        return cls(estimator, preprocessor, metadata)

    @property
    def model_name(self) -> str:
        return self.metadata.get("name", self.metadata.get("algorithm", "desconocido"))

    @property
    def model_version(self) -> str:
        return self.metadata.get("version", "0")

    def _transform(self, raw_rows: list[Mapping[str, Any]]):
        rows = [build_feature_row(raw) for raw in raw_rows]
        frame = rows_to_frame(rows)
        return rows, self.preprocessor.transform(frame)

    def predict_proba(self, raw_rows: list[Mapping[str, Any]]) -> list[float]:
        if not raw_rows:
            return []
        _, transformed = self._transform(raw_rows)
        return [float(p) for p in self.estimator.predict_proba(transformed)[:, 1]]

    # ------------------------------------------------------------------ explicabilidad
    def _contributions(self, transformed: np.ndarray) -> tuple[np.ndarray, bool]:
        """Devuelve (matriz de contribuciones, tiene_signo)."""
        estimator = self.estimator
        if hasattr(estimator, "coef_"):
            return transformed * estimator.coef_[0], True
        if estimator.__class__.__name__ == "XGBClassifier":
            import xgboost

            contribs = estimator.get_booster().predict(xgboost.DMatrix(transformed), pred_contribs=True)
            return contribs[:, :-1], True  # última columna = sesgo
        if hasattr(estimator, "feature_importances_"):
            # Aproximación: importancia global ponderada por la desviación estandarizada.
            return np.abs(transformed) * estimator.feature_importances_, False
        return np.zeros_like(transformed), False

    def predict_with_explanation(self, raw_rows: list[Mapping[str, Any]], top_n: int = 5) -> list[dict[str, Any]]:
        if not raw_rows:
            return []
        rows, transformed = self._transform(raw_rows)
        probabilities = self.estimator.predict_proba(transformed)[:, 1]
        matrix, signed = self._contributions(transformed)
        return [
            {
                "probability": round(float(probabilities[i]), 4),
                "features": rows[i],
                "explanation": self._top_factors(matrix[i], signed, rows[i], top_n),
            }
            for i in range(len(rows))
        ]

    def _top_factors(self, contribution_row: np.ndarray, signed: bool, row: dict[str, Any], top_n: int):
        aggregated: dict[str, float] = {}
        for name, value in zip(self.transformed_names, contribution_row):
            original = original_feature_for(name)
            aggregated[original] = aggregated.get(original, 0.0) + float(value)
        ranked = sorted(aggregated.items(), key=lambda item: abs(item[1]), reverse=True)[:top_n]
        factors = []
        for feature, weight in ranked:
            if signed:
                direction = "asociada a mayor riesgo estimado" if weight > 0 else "asociada a menor riesgo estimado"
            else:
                direction = "variable con alta relevancia para el modelo"
            factors.append(
                {
                    "feature": feature,
                    "label": FEATURE_LABELS.get(feature, feature),
                    "value": row.get(feature),
                    "weight": round(weight, 4),
                    "direction": direction,
                }
            )
        return factors
