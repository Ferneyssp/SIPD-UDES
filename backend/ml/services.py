"""
Servicio de inferencia para Django.

- Carga el modelo activo UNA vez y lo mantiene en memoria (cache por proceso).
- Nunca entrena: sólo usa artefactos ya serializados en ML_MODELS_DIR.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import ModelVersion

logger = logging.getLogger(__name__)
_lock = threading.Lock()
_cache: dict = {"key": None, "predictor": None}


class ModelNotAvailableError(RuntimeError):
    """No existe un modelo entrenado disponible."""


def _models_dir() -> Path:
    return Path(settings.ML_MODELS_DIR)


def sync_model_versions() -> list[ModelVersion]:
    """Registra en BD las versiones encontradas en ML_MODELS_DIR (idempotente)."""
    from sipd_ml.persistence import list_model_dirs, load_metadata

    models_dir = _models_dir()
    if not models_dir.exists():
        return []
    registered = []
    for directory in list_model_dirs(models_dir):
        metadata = load_metadata(directory)
        trained_at = metadata.get("trained_at")
        version, _ = ModelVersion.objects.update_or_create(
            algorithm=metadata["algorithm"],
            version=metadata["version"],
            defaults={
                "name": metadata.get("name", metadata["algorithm"]),
                "metrics": metadata.get("metrics", {}),
                "trained_at": datetime.fromisoformat(trained_at) if trained_at else None,
                "artifact_dir": directory.name,
                "is_synthetic": bool(metadata.get("is_synthetic")),
                "selection_metric": metadata.get("selection_metric", ""),
            },
        )
        registered.append((version, bool(metadata.get("selected"))))
    with transaction.atomic():
        if registered and not ModelVersion.objects.filter(active=True).exists():
            selected = [v for v, is_selected in registered if is_selected] or [registered[-1][0]]
            selected[-1].activate()
    clear_cache()
    return [version for version, _ in registered]


def get_active_model_version() -> ModelVersion | None:
    return ModelVersion.objects.filter(active=True).first()


def clear_cache() -> None:
    with _lock:
        _cache.update(key=None, predictor=None)


def get_predictor():
    """Devuelve (RiskPredictor, ModelVersion|None) del modelo activo."""
    from sipd_ml.inference import RiskPredictor

    active = get_active_model_version()
    directory = _models_dir() / active.artifact_dir if active else _models_dir()
    key = (str(directory), active.pk if active else None)
    with _lock:
        if _cache["key"] != key:
            try:
                _cache["predictor"] = RiskPredictor.from_directory(directory)
            except FileNotFoundError as exc:
                logger.error("Modelo no disponible: %s", exc)
                raise ModelNotAvailableError(
                    "No hay un modelo entrenado disponible. Ejecute el entrenamiento (ml/scripts/train.py) "
                    "y 'python manage.py sync_models'."
                ) from exc
            _cache["key"] = key
            logger.info("Modelo cargado en memoria: %s", directory)
        return _cache["predictor"], active


def model_status() -> dict:
    active = get_active_model_version()
    try:
        predictor, _ = get_predictor()
        available = True
        name, version = predictor.model_name, predictor.model_version
        synthetic = bool(predictor.metadata.get("is_synthetic"))
    except ModelNotAvailableError:
        available, name, version, synthetic = False, None, None, False
    return {
        "available": available,
        "name": name,
        "version": version,
        "is_synthetic": synthetic,
        "model_version_id": active.pk if active else None,
        "checked_at": timezone.now().isoformat(),
    }
