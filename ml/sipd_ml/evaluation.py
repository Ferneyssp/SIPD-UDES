"""
Evaluación y comparación objetiva de modelos.

Para deserción se priorizan Recall, Precision, F1 y ROC-AUC. Accuracy se
reporta pero NUNCA se usa como criterio único de selección.
"""
from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from .config import CLASSIFICATION_THRESHOLD

SELECTION_METRICS = ("f1", "recall", "roc_auc", "precision")


def evaluate_estimator(estimator, x_test, y_test, threshold: float = CLASSIFICATION_THRESHOLD) -> dict[str, Any]:
    probabilities = estimator.predict_proba(x_test)[:, 1]
    predicted = (probabilities >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, predicted, labels=[0, 1]).ravel()
    return {
        "accuracy": round(float(accuracy_score(y_test, predicted)), 4),
        "precision": round(float(precision_score(y_test, predicted, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, predicted, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, predicted, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, probabilities)), 4),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "threshold": threshold,
        "test_size": int(len(y_test)),
        "positive_rate_test": round(float(np.mean(y_test)), 4),
    }


def compare_models(results: dict[str, dict[str, Any]], selection_metric: str) -> list[dict[str, Any]]:
    """Devuelve la tabla comparativa ordenada por la métrica elegida
    (desempate por ROC-AUC y luego Recall)."""
    if selection_metric not in SELECTION_METRICS:
        raise ValueError(f"Métrica de selección inválida. Opciones: {SELECTION_METRICS}")
    rows = [{"algorithm": name, **metrics} for name, metrics in results.items()]
    rows.sort(key=lambda r: (r[selection_metric], r["roc_auc"], r["recall"]), reverse=True)
    return rows
