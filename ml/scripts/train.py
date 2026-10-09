"""
Entrena, evalúa y guarda los modelos candidatos.

Uso:
    python ml/scripts/train.py                              # usa el dataset sintético
    python ml/scripts/train.py --data ruta/dataset.csv      # dataset institucional
    python ml/scripts/train.py --select-by recall
    python ml/scripts/train.py --force-model random_forest

El dataset debe contener las columnas definidas en sipd_ml.config (MODEL_FEATURES,
sin las derivadas) y la columna objetivo 'dropout' (0/1).
"""
import argparse
import json
from pathlib import Path

import pandas as pd

import _bootstrap  # noqa: F401
from sipd_ml.config import CLASSIFICATION_THRESHOLD, DEFAULT_SELECTION_METRIC, MODELS_DIR, SYNTHETIC_DATASET_PATH
from sipd_ml.evaluation import SELECTION_METRICS
from sipd_ml.pipeline import run_training_pipeline
from sipd_ml.synthetic import generate_training_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Entrenamiento de modelos de riesgo de deserción.")
    parser.add_argument("--data", default=str(SYNTHETIC_DATASET_PATH))
    parser.add_argument("--select-by", default=DEFAULT_SELECTION_METRIC, choices=SELECTION_METRICS)
    parser.add_argument("--force-model", default=None, choices=["logistic_regression", "random_forest", "xgboost"])
    parser.add_argument("--models-dir", default=str(MODELS_DIR))
    parser.add_argument("--threshold", type=float, default=CLASSIFICATION_THRESHOLD,
                        help="Umbral de probabilidad para calcular precision/recall/F1")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"No existe {data_path}; se genera el dataset sintético.")
        data_path.parent.mkdir(parents=True, exist_ok=True)
        generate_training_dataset().to_csv(data_path, index=False)

    dataset = pd.read_csv(data_path)
    summary = run_training_pipeline(
        dataset,
        selection_metric=args.select_by,
        forced_algorithm=args.force_model,
        models_dir=Path(args.models_dir),
        threshold=args.threshold,
    )

    print(f"\nComparación de modelos (ordenado por {summary['selection_metric']}, umbral de clasificación {args.threshold}):")
    print(f"{'Modelo':<22}{'Accuracy':>9}{'Precision':>10}{'Recall':>8}{'F1':>8}{'ROC-AUC':>9}")
    for row in summary["ranking"]:
        print(f"{row['algorithm']:<22}{row['accuracy']:>9}{row['precision']:>10}{row['recall']:>8}{row['f1']:>8}{row['roc_auc']:>9}")
    print("\nModelo seleccionado:", summary["selected_algorithm"], "- versión", summary["version"])
    if summary["is_synthetic"]:
        print("ADVERTENCIA: métricas sobre datos SINTÉTICOS; no son resultados académicos reales.")
    (Path(args.models_dir) / "last_training_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
