"""
Evalúa un modelo guardado sobre un dataset etiquetado.

Uso:
    python ml/scripts/evaluate.py --model-dir ml/models --data data/sample/synthetic_training_dataset.csv
"""
import argparse
import json

import pandas as pd

import _bootstrap  # noqa: F401
from sipd_ml.config import MODELS_DIR, SYNTHETIC_DATASET_PATH
from sipd_ml.evaluation import evaluate_estimator
from sipd_ml.inference import RiskPredictor
from sipd_ml.preprocessing import prepare_training_frame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default=str(MODELS_DIR))
    parser.add_argument("--data", default=str(SYNTHETIC_DATASET_PATH))
    args = parser.parse_args()

    predictor = RiskPredictor.from_directory(args.model_dir)
    features, target = prepare_training_frame(pd.read_csv(args.data))
    metrics = evaluate_estimator(predictor.estimator, predictor.preprocessor.transform(features), target)
    print(f"Modelo: {predictor.model_name} v{predictor.model_version}")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    print("Nota: si el dataset incluye filas usadas en entrenamiento, las métricas serán optimistas.")


if __name__ == "__main__":
    main()
