"""Genera los notebooks 01-05 del pipeline (python ml/scripts/build_notebooks.py)."""
from pathlib import Path

import nbformat as nbf

NB_DIR = Path(__file__).resolve().parent.parent / "notebooks"
SETUP = """import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent.parent / "backend"))  # sipd_ml vive en backend/
import pandas as pd
from sipd_ml import config
pd.set_option("display.max_columns", 30)"""

WARNING = ("> **Advertencia:** mientras no se disponga de datos institucionales, estos notebooks usan el dataset "
           "**SINTÉTICO** `data/sample/synthetic_training_dataset.csv`. Los resultados sirven sólo para verificar "
           "técnicamente el pipeline y **no deben reportarse como hallazgos académicos**.")

NOTEBOOKS = {
    "01_exploracion.ipynb": [
        ("md", "# 01 · Exploración de datos\nAnálisis descriptivo de las variables académicas y de encuestas.\n\n" + WARNING),
        ("code", SETUP),
        ("code", """from sipd_ml.synthetic import generate_training_dataset
if not config.SYNTHETIC_DATASET_PATH.exists():
    config.SAMPLE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    generate_training_dataset().to_csv(config.SYNTHETIC_DATASET_PATH, index=False)
df = pd.read_csv(config.SYNTHETIC_DATASET_PATH)
print(df.shape)
df.head()"""),
        ("code", "df.describe().T"),
        ("md", "## Valores faltantes\nLas variables de encuesta son opcionales; el pipeline las imputa."),
        ("code", "(df.isna().mean() * 100).round(1).sort_values(ascending=False).to_frame('% faltante')"),
        ("md", "## Balance de la variable objetivo"),
        ("code", "df['dropout'].value_counts(normalize=True).rename({0: 'Permanece', 1: 'Deserta'}).round(3)"),
        ("md", "## Relación descriptiva de variables con la etiqueta\n(Asociaciones, no relaciones causales.)"),
        ("code", "df.groupby('dropout')[['gpa', 'attendance_percentage', 'failed_subjects', 'course_repetitions']].mean().round(2)"),
        ("code", """import matplotlib.pyplot as plt
fig, axes = plt.subplots(1, 2, figsize=(10, 3.5))
for ax, col in zip(axes, ['gpa', 'attendance_percentage']):
    for label, group in df.groupby('dropout'):
        ax.hist(group[col], bins=25, alpha=0.6, label='Deserta' if label else 'Permanece')
    ax.set_title(config.FEATURE_LABELS[col]); ax.legend()
plt.tight_layout()"""),
    ],
    "02_preprocesamiento.ipynb": [
        ("md", "# 02 · Preprocesamiento\nVariables derivadas, imputación, escalamiento y codificación. El mismo `ColumnTransformer` "
               "ajustado se serializa como `preprocessor.joblib` y se reutiliza en inferencia.\n\n" + WARNING),
        ("code", SETUP),
        ("code", """from sipd_ml.preprocessing import build_preprocessor, prepare_training_frame
df = pd.read_csv(config.SYNTHETIC_DATASET_PATH)
X, y = prepare_training_frame(df)
print('Variables del modelo:', config.MODEL_FEATURES)
X.head()"""),
        ("code", """preprocessor = build_preprocessor()
X_t = preprocessor.fit_transform(X)
print('Matriz transformada:', X_t.shape)
list(preprocessor.get_feature_names_out())"""),
        ("md", "La selección de variables es explícita (`config.MODEL_FEATURES`). Se excluyen identificadores y datos personales."),
    ],
    "03_entrenamiento.ipynb": [
        ("md", "# 03 · Entrenamiento\nSe entrenan Regresión Logística, Random Forest y XGBoost (si está disponible) sobre la misma partición.\n\n" + WARNING),
        ("code", SETUP),
        ("code", """from sipd_ml.preprocessing import prepare_training_frame
from sipd_ml.training import available_algorithms, split_and_preprocess, train_candidates
df = pd.read_csv(config.SYNTHETIC_DATASET_PATH)
X, y = prepare_training_frame(df)
split = split_and_preprocess(X, y)
candidates = train_candidates(split)
print('Modelos entrenados:', [c.algorithm for c in candidates])"""),
    ],
    "04_evaluacion.ipynb": [
        ("md", "# 04 · Evaluación y comparación\nSe priorizan Recall, Precision, F1 y ROC-AUC. Accuracy no se usa como criterio único.\n\n" + WARNING),
        ("code", SETUP),
        ("code", """from sipd_ml.evaluation import compare_models, evaluate_estimator
from sipd_ml.preprocessing import prepare_training_frame
from sipd_ml.training import split_and_preprocess, train_candidates
df = pd.read_csv(config.SYNTHETIC_DATASET_PATH)
split = split_and_preprocess(*prepare_training_frame(df))
candidates = train_candidates(split)
results = {c.algorithm: evaluate_estimator(c.estimator, split.x_test, split.y_test) for c in candidates}
ranking = pd.DataFrame(compare_models(results, 'f1')).set_index('algorithm')
ranking[['accuracy', 'precision', 'recall', 'f1', 'roc_auc']]"""),
        ("code", "pd.DataFrame({k: v['confusion_matrix'] for k, v in results.items()}).T"),
        ("md", "El umbral de clasificación usado para estas métricas es `config.CLASSIFICATION_THRESHOLD` (0,30 por defecto, "
               "coherente con el inicio del nivel de riesgo Medio)."),
    ],
    "05_guardado_modelo.ipynb": [
        ("md", "# 05 · Guardado del modelo\nEjecuta el pipeline completo y guarda los artefactos versionados en `backend/ml_models/`. "
               "Equivale a `python ml/scripts/train.py`. Después ejecute `python manage.py sync_models` en el backend.\n\n" + WARNING),
        ("code", SETUP),
        ("code", """from sipd_ml.pipeline import run_training_pipeline
summary = run_training_pipeline(pd.read_csv(config.SYNTHETIC_DATASET_PATH), selection_metric='f1')
print('Seleccionado:', summary['selected_algorithm'], 'versión', summary['version'])
pd.DataFrame(summary['ranking']).set_index('algorithm')[['precision', 'recall', 'f1', 'roc_auc']]"""),
        ("code", """from sipd_ml.inference import RiskPredictor
predictor = RiskPredictor.from_directory(config.MODELS_DIR)
ejemplo = {'program_code': 'SIS', 'semester': 6, 'gpa': 2.7, 'previous_gpa': 3.2, 'credits_enrolled': 18,
           'credits_approved': 9, 'credits_failed': 9, 'failed_subjects': 3, 'attendance_percentage': 62,
           'course_repetitions': 2}
predictor.predict_with_explanation([ejemplo])[0]"""),
    ],
}

for name, cells in NOTEBOOKS.items():
    nb = nbf.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nb.cells = [nbf.v4.new_markdown_cell(src) if kind == "md" else nbf.v4.new_code_cell(src) for kind, src in cells]
    nbf.write(nb, NB_DIR / name)
    print("Generado", name)
