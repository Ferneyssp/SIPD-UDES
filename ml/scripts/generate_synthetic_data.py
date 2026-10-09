"""
Genera el dataset SINTÉTICO de entrenamiento en data/sample/.

Uso:
    python ml/scripts/generate_synthetic_data.py --rows 4000
"""
import argparse

import _bootstrap  # noqa: F401
from sipd_ml.config import SYNTHETIC_DATASET_PATH
from sipd_ml.synthetic import generate_training_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera datos sintéticos de entrenamiento.")
    parser.add_argument("--rows", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default=str(SYNTHETIC_DATASET_PATH))
    args = parser.parse_args()

    dataset = generate_training_dataset(args.rows, args.seed)
    dataset.to_csv(args.output, index=False)
    print(f"Dataset sintético guardado en {args.output} ({len(dataset)} filas, "
          f"tasa de deserción sintética {dataset['dropout'].mean():.1%}).")
    print("ADVERTENCIA: datos ficticios, sólo para pruebas técnicas.")


if __name__ == "__main__":
    main()
