"""
Lógica CENTRALIZADA de niveles de riesgo.

Los umbrales se definen en settings (variables de entorno RISK_LOW_THRESHOLD
y RISK_MEDIUM_THRESHOLD). Ningún otro módulo del backend ni del frontend
debe codificar estos valores: el frontend los obtiene de /api/config/.

    0% ───────── 30% ───────── 60% ───────── 100%
          Bajo          Medio          Alto
"""
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


class RiskLevel(models.TextChoices):
    LOW = "BAJO", "Bajo"
    MEDIUM = "MEDIO", "Medio"
    HIGH = "ALTO", "Alto"


def get_thresholds() -> dict[str, float]:
    low = float(settings.RISK_LOW_THRESHOLD)
    medium = float(settings.RISK_MEDIUM_THRESHOLD)
    if not 0 < low < medium < 1:
        raise ImproperlyConfigured("Los umbrales deben cumplir 0 < RISK_LOW_THRESHOLD < RISK_MEDIUM_THRESHOLD < 1.")
    return {"low": low, "medium": medium}


def classify_risk(probability: float) -> str:
    """Devuelve el código de nivel (BAJO, MEDIO, ALTO) para una probabilidad 0-1."""
    if probability is None:
        raise ValueError("La probabilidad no puede ser nula.")
    if not 0 <= probability <= 1:
        raise ValueError("La probabilidad debe estar entre 0 y 1.")
    thresholds = get_thresholds()
    if probability < thresholds["low"]:
        return RiskLevel.LOW
    if probability < thresholds["medium"]:
        return RiskLevel.MEDIUM
    return RiskLevel.HIGH


def risk_levels_description() -> list[dict]:
    thresholds = get_thresholds()
    return [
        {"code": RiskLevel.LOW.value, "label": RiskLevel.LOW.label, "min": 0.0, "max": thresholds["low"]},
        {"code": RiskLevel.MEDIUM.value, "label": RiskLevel.MEDIUM.label, "min": thresholds["low"], "max": thresholds["medium"]},
        {"code": RiskLevel.HIGH.value, "label": RiskLevel.HIGH.label, "min": thresholds["medium"], "max": 1.0},
    ]
