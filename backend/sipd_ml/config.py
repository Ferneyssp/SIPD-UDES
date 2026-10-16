"""
Configuración central del pipeline de Machine Learning de SIPD.

Define las variables (features) que usa el modelo, su tipo y la etiqueta
legible que se muestra en la interfaz. Tanto el entrenamiento como la
inferencia importan estas constantes, de modo que el preprocesamiento
aplicado en producción sea exactamente el mismo que en entrenamiento.
"""
from pathlib import Path

# --- Rutas -------------------------------------------------------------------
# El paquete vive en backend/ para que el servicio Django (Vercel/Docker) lo incluya
# junto con los artefactos entrenados (backend/ml_models).
BACKEND_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = BACKEND_ROOT / "ml_models"
PROJECT_ROOT = BACKEND_ROOT.parent
SAMPLE_DATA_DIR = PROJECT_ROOT / "data" / "sample"
SYNTHETIC_DATASET_PATH = SAMPLE_DATA_DIR / "synthetic_training_dataset.csv"

MODEL_FILENAME = "model.joblib"
PREPROCESSOR_FILENAME = "preprocessor.joblib"
METADATA_FILENAME = "metadata.json"

# --- Variables ---------------------------------------------------------------
TARGET_COLUMN = "dropout"

CATEGORICAL_FEATURES = ["program_code"]

ACADEMIC_NUMERIC_FEATURES = [
    "semester",
    "gpa",
    "previous_gpa",
    "gpa_change",
    "credits_enrolled",
    "credits_approved",
    "credits_failed",
    "failed_subjects",
    "approval_rate",
    "attendance_percentage",
    "course_repetitions",
]

# Variables provenientes de instrumentos institucionales (encuestas).
# Todas son opcionales: el pipeline imputa los valores faltantes.
SURVEY_FEATURES = [
    "works_while_studying",
    "socioeconomic_stratum",
    "financial_difficulty",
    "motivation_level",
]

NUMERIC_FEATURES = ACADEMIC_NUMERIC_FEATURES + SURVEY_FEATURES
MODEL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Variables derivadas que se calculan a partir de las anteriores.
DERIVED_FEATURES = ["gpa_change", "approval_rate"]

FEATURE_LABELS = {
    "program_code": "Programa académico",
    "semester": "Semestre",
    "gpa": "Promedio del periodo",
    "previous_gpa": "Promedio del periodo anterior",
    "gpa_change": "Variación del promedio",
    "credits_enrolled": "Créditos matriculados",
    "credits_approved": "Créditos aprobados",
    "credits_failed": "Créditos reprobados",
    "failed_subjects": "Asignaturas perdidas",
    "approval_rate": "Progreso académico (tasa de aprobación)",
    "attendance_percentage": "Asistencia (%)",
    "course_repetitions": "Asignaturas repetidas",
    "works_while_studying": "Trabaja mientras estudia (encuesta)",
    "socioeconomic_stratum": "Estrato socioeconómico (encuesta)",
    "financial_difficulty": "Dificultad financiera percibida 1-5 (encuesta)",
    "motivation_level": "Motivación académica 1-5 (encuesta)",
}

# --- Entrenamiento -----------------------------------------------------------
RANDOM_STATE = 42
TEST_SIZE = 0.25
# Umbral usado SÓLO para calcular métricas de clasificación (precision/recall/F1).
# Por defecto coincide con el límite a partir del cual un estudiante entra en
# monitoreo (riesgo Medio, RISK_LOW_THRESHOLD=0.30 en el backend). En deserción
# se prefiere mayor Recall. Puede cambiarse con: train.py --threshold 0.5
CLASSIFICATION_THRESHOLD = 0.30
DEFAULT_SELECTION_METRIC = "f1"

ALGORITHM_DISPLAY_NAMES = {
    "logistic_regression": "Regresión Logística",
    "random_forest": "Random Forest",
    "xgboost": "XGBoost",
}
