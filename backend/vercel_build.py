"""
Paso de build del servicio "backend" en Vercel (ver vercel.json).

El servicio se construye con root=backend/, así que el paquete de inferencia
(ml/sipd_ml) y los modelos entrenados (ml/models) quedarían fuera del bundle de
la función. Este script los copia a backend/_ml/, que settings.py usa como
ML_DIR cuando ../ml no está disponible en tiempo de ejecución.
"""
import shutil
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
SOURCE = BACKEND_DIR.parent / "ml"
TARGET = BACKEND_DIR / "_ml"


def main() -> None:
    if not (SOURCE / "sipd_ml").is_dir() or not (SOURCE / "models").is_dir():
        raise SystemExit(f"No se encontró {SOURCE}/sipd_ml o {SOURCE}/models.")
    shutil.rmtree(TARGET, ignore_errors=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    for name in ("sipd_ml", "models"):
        shutil.copytree(SOURCE / name, TARGET / name, ignore=ignore)
    print(f"Paquete ML copiado a {TARGET}")


if __name__ == "__main__":
    main()
