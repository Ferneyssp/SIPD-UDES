"""Pruebas del pipeline de ML: preprocesamiento, entrenamiento, carga e inferencia."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sipd_ml.config import MODEL_FEATURES  # noqa: E402
from sipd_ml.features import build_feature_row, compute_approval_rate, compute_gpa_change  # noqa: E402
from sipd_ml.inference import RiskPredictor  # noqa: E402
from sipd_ml.pipeline import run_training_pipeline  # noqa: E402
from sipd_ml.preprocessing import build_preprocessor, prepare_training_frame  # noqa: E402
from sipd_ml.synthetic import generate_training_dataset  # noqa: E402

SAMPLE_STUDENT = {
    "program_code": "SIS", "semester": 6, "gpa": 2.7, "previous_gpa": 3.2,
    "credits_enrolled": 18, "credits_approved": 9, "credits_failed": 9, "failed_subjects": 3,
    "attendance_percentage": 62, "course_repetitions": 2, "works_while_studying": 1,
    "socioeconomic_stratum": None, "financial_difficulty": 4, "motivation_level": 2,
}


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    models_dir = tmp_path_factory.mktemp("models")
    dataset = generate_training_dataset(1200, seed=7)
    summary = run_training_pipeline(dataset, models_dir=models_dir, algorithms=["logistic_regression", "random_forest"], version="test")
    return models_dir, summary


def test_derived_features():
    assert compute_approval_rate(9, 18) == 0.5
    assert compute_approval_rate(5, 0) is None
    assert compute_gpa_change(3.0, 3.5) == -0.5
    assert compute_gpa_change(3.0, None) is None
    row = build_feature_row(SAMPLE_STUDENT)
    assert set(row) == set(MODEL_FEATURES)
    assert row["approval_rate"] == 0.5


def test_preprocessor_handles_missing_values():
    features, _ = prepare_training_frame(generate_training_dataset(300, seed=3))
    features.loc[features.index[:10], "gpa"] = np.nan
    transformed = build_preprocessor().fit_transform(features)
    assert not np.isnan(transformed).any()


def test_training_saves_artifacts(trained):
    models_dir, summary = trained
    assert (models_dir / "model.joblib").exists()
    assert (models_dir / "preprocessor.joblib").exists()
    assert summary["is_synthetic"] is True
    for row in summary["ranking"]:
        assert 0 <= row["roc_auc"] <= 1


def test_model_loads_and_predicts(trained):
    models_dir, _ = trained
    predictor = RiskPredictor.from_directory(models_dir)
    [probability] = predictor.predict_proba([SAMPLE_STUDENT])
    assert 0.0 <= probability <= 1.0


def test_higher_risk_profile_scores_higher(trained):
    models_dir, _ = trained
    predictor = RiskPredictor.from_directory(models_dir)
    good = dict(SAMPLE_STUDENT, gpa=4.5, previous_gpa=4.4, credits_approved=18, credits_failed=0,
                failed_subjects=0, attendance_percentage=98, course_repetitions=0, works_while_studying=0,
                financial_difficulty=1, motivation_level=5)
    risky, safe = predictor.predict_proba([SAMPLE_STUDENT, good])
    assert risky > safe


def test_explanation_has_labels(trained):
    models_dir, _ = trained
    [result] = RiskPredictor.from_directory(models_dir).predict_with_explanation([SAMPLE_STUDENT], top_n=3)
    assert len(result["explanation"]) == 3
    assert all("label" in f and "direction" in f for f in result["explanation"])


def test_unknown_program_does_not_fail(trained):
    models_dir, _ = trained
    [probability] = RiskPredictor.from_directory(models_dir).predict_proba([dict(SAMPLE_STUDENT, program_code="XYZ")])
    assert 0.0 <= probability <= 1.0
