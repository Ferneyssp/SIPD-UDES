"""
Protocolo experimental complementario de los modelos del sistema.

Reutiliza exactamente la partición, el preprocesador, los hiperparámetros y la
evaluación del pipeline (sipd_ml) y añade:
  - línea base de prevalencia (DummyClassifier),
  - PR-AUC, puntaje de Brier, especificidad e IC 95 % bootstrap de la ROC-AUC
    en la partición hold-out (75/25, semilla 42),
  - validación cruzada estratificada repetida (5 particiones x 5 repeticiones)
    con el preprocesador ajustado dentro de cada partición,
  - curvas de calibración, análisis del umbral y distribución por niveles de
    riesgo de la Regresión Logística.

Uso:
    python ml/scripts/validate.py --data data/private/synthetic_students.csv --label C500 --figures
    python ml/scripts/validate.py --data data/sample/synthetic_training_dataset.csv --label C4000 --figures

Los resultados se guardan en ml/results/<label>/ (results.json y, con --figures, PNG).
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.dummy import DummyClassifier
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.pipeline import Pipeline

import _bootstrap  # noqa: F401
from sipd_ml.config import CLASSIFICATION_THRESHOLD, RANDOM_STATE
from sipd_ml.evaluation import evaluate_estimator
from sipd_ml.preprocessing import build_preprocessor, prepare_training_frame
from sipd_ml.training import available_algorithms, build_estimator, split_and_preprocess

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
NAMES = {
    "logistic_regression": "Regresión Logística",
    "random_forest": "Random Forest",
    "xgboost": "XGBoost",
    "baseline": "Línea base (prevalencia)",
}
RISK_LOW, RISK_MEDIUM = 0.30, 0.60
THRESHOLDS = [round(t, 2) for t in np.arange(0.10, 0.701, 0.05)]


def build_model(algorithm: str, y_train: pd.Series):
    if algorithm == "baseline":
        return DummyClassifier(strategy="prior")
    return build_estimator(algorithm, y_train)


def threshold_metrics(y_true, probabilities, threshold: float) -> dict:
    predicted = (probabilities >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, predicted, labels=[0, 1]).ravel()
    return {
        "threshold": threshold,
        "precision": float(precision_score(y_true, predicted, zero_division=0)),
        "recall": float(recall_score(y_true, predicted, zero_division=0)),
        "f1": float(f1_score(y_true, predicted, zero_division=0)),
        "specificity": float(tn / (tn + fp)) if tn + fp else 0.0,
        "accuracy": float((tp + tn) / len(y_true)),
        "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
    }


def bootstrap_roc_auc(y_true: np.ndarray, probabilities: np.ndarray, n: int) -> list[float]:
    rng = np.random.default_rng(RANDOM_STATE)
    scores = []
    for _ in range(n):
        idx = rng.integers(0, len(y_true), len(y_true))
        if y_true[idx].min() == y_true[idx].max():
            continue
        scores.append(roc_auc_score(y_true[idx], probabilities[idx]))
    return [float(np.percentile(scores, 2.5)), float(np.percentile(scores, 97.5))]


def holdout(features, target, algorithms, n_bootstrap: int) -> tuple[dict, dict]:
    split = split_and_preprocess(features, target)
    y_test = split.y_test.to_numpy()
    results, probabilities = {}, {}
    for algorithm in algorithms + ["baseline"]:
        model = build_model(algorithm, split.y_train)
        model.fit(split.x_train, split.y_train)
        proba = model.predict_proba(split.x_test)[:, 1]
        probabilities[algorithm] = proba
        metrics = evaluate_estimator(model, split.x_test, split.y_test) if algorithm != "baseline" else {
            "roc_auc": float(roc_auc_score(y_test, proba))}
        metrics.update(threshold_metrics(y_test, proba, CLASSIFICATION_THRESHOLD))
        metrics["roc_auc"] = float(roc_auc_score(y_test, proba))
        metrics["pr_auc"] = float(average_precision_score(y_test, proba))
        metrics["brier"] = float(brier_score_loss(y_test, proba))
        if algorithm != "baseline":
            metrics["roc_auc_ci95"] = bootstrap_roc_auc(y_test, proba, n_bootstrap)
            observed, mean_pred = calibration_curve(y_test, proba, n_bins=5, strategy="quantile")
            metrics["calibration"] = {"mean_predicted": mean_pred.tolist(), "observed": observed.tolist()}
        results[algorithm] = metrics

    lr = probabilities["logistic_regression"]
    levels = np.where(lr < RISK_LOW, "Bajo", np.where(lr < RISK_MEDIUM, "Medio", "Alto"))
    extra = {
        "test_size": int(len(y_test)),
        "test_positives": int(y_test.sum()),
        "thresholds_logistic_regression": [threshold_metrics(y_test, lr, t) for t in THRESHOLDS],
        "risk_levels_logistic_regression": {
            level: {"share": float(np.mean(levels == level)), "count": int(np.sum(levels == level)),
                    "observed_rate": float(y_test[levels == level].mean()) if np.any(levels == level) else None}
            for level in ("Bajo", "Medio", "Alto")
        },
    }
    return results, extra


def cross_validation(features, target, algorithms, folds: int, repeats: int) -> dict:
    cv = RepeatedStratifiedKFold(n_splits=folds, n_repeats=repeats, random_state=RANDOM_STATE)
    scores = {a: {k: [] for k in ("roc_auc", "pr_auc", "brier", "recall", "precision", "f1")}
              for a in algorithms + ["baseline"]}
    for train_idx, test_idx in cv.split(features, target):
        x_train, x_test = features.iloc[train_idx], features.iloc[test_idx]
        y_train, y_test = target.iloc[train_idx], target.iloc[test_idx].to_numpy()
        for algorithm in scores:
            pipeline = Pipeline([("preprocessor", build_preprocessor()), ("model", build_model(algorithm, y_train))])
            pipeline.fit(x_train, y_train)
            proba = pipeline.predict_proba(x_test)[:, 1]
            at_threshold = threshold_metrics(y_test, proba, CLASSIFICATION_THRESHOLD)
            fold = scores[algorithm]
            fold["roc_auc"].append(roc_auc_score(y_test, proba))
            fold["pr_auc"].append(average_precision_score(y_test, proba))
            fold["brier"].append(brier_score_loss(y_test, proba))
            for key in ("recall", "precision", "f1"):
                fold[key].append(at_threshold[key])
    return {
        algorithm: {metric: {"mean": float(np.mean(v)), "std": float(np.std(v, ddof=1))} for metric, v in values.items()}
        for algorithm, values in scores.items()
    } | {"fits_per_model": folds * repeats}


def save_figures(output: Path, label: str, holdout_results: dict, extra: dict, cv: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Serif", "axes.spines.top": False, "axes.spines.right": False,
                         "axes.edgecolor": "#777777", "xtick.color": "#555555", "ytick.color": "#555555",
                         "grid.color": "#e3e3e3"})
    style = {"logistic_regression": ("#2b7bd6", "o"), "random_forest": ("#ea6a3a", "s"),
             "xgboost": ("#1fae7a", "D"), "baseline": ("#888888", "x")}
    order = [a for a in ("logistic_regression", "random_forest", "xgboost", "baseline") if a in cv]

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.4), sharey=True)
    for ax, (metric, title) in zip(axes, [("roc_auc", "ROC-AUC"), ("pr_auc", "PR-AUC"),
                                          ("brier", "Brier (menor es mejor)")]):
        for i, algorithm in enumerate(order):
            color, marker = style[algorithm]
            mean, std = cv[algorithm][metric]["mean"], cv[algorithm][metric]["std"]
            y = len(order) - 1 - i
            ax.errorbar(mean, y, xerr=std, fmt=marker, color=color, capsize=3, markersize=7, lw=1.5)
            ax.annotate(f"{mean:.3f}", (mean, y), textcoords="offset points", xytext=(0, 9), ha="center", fontsize=9)
        ax.set_title(title, fontsize=11)
        ax.grid(True)
        ax.set_ylim(-0.6, len(order) - 0.4)
    axes[0].set_yticks(range(len(order)))
    axes[0].set_yticklabels([NAMES[a].replace("Línea base (prevalencia)", "Base (prevalencia)") for a in reversed(order)])
    fig.tight_layout()
    fig.savefig(output / "cv_comparison.png", dpi=200)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(4.6, 4))
    ax.plot([0, 1], [0, 1], "--", color="#888888", lw=1, label="Calibración perfecta")
    for algorithm in ("logistic_regression", "random_forest", "xgboost"):
        if algorithm in holdout_results:
            color, marker = style[algorithm]
            cal = holdout_results[algorithm]["calibration"]
            ax.plot(cal["mean_predicted"], cal["observed"], marker=marker, color=color, lw=2, label=NAMES[algorithm])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Probabilidad media estimada (quintiles)")
    ax.set_ylabel("Proporción observada de deserción")
    ax.grid(True)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    fig.tight_layout()
    fig.savefig(output / "calibration.png", dpi=200)
    plt.close(fig)

    rows = extra["thresholds_logistic_regression"]
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    for key, name, color, marker in [("recall", "Recall (sensibilidad)", "#2b7bd6", "o"),
                                     ("precision", "Precision", "#ea6a3a", "s"),
                                     ("f1", "F1-score", "#1fae7a", "D"),
                                     ("specificity", "Especificidad", "#888888", "^")]:
        ax.plot([r["threshold"] for r in rows], [r[key] for r in rows], marker=marker, color=color, lw=2,
                markersize=4, label=name)
    for value, text in [(RISK_LOW, "0,30 (inicio nivel Medio)"), (RISK_MEDIUM, "0,60 (inicio nivel Alto)")]:
        ax.axvline(value, color="#444444", ls="--", lw=1)
        ax.text(value + 0.005, 0.42, text, rotation=90, fontsize=8, color="#555555", va="bottom")
    ax.set_xlabel("Umbral de probabilidad")
    ax.set_ylabel("Valor de la métrica")
    ax.set_ylim(0.4, 1.0)
    ax.grid(True)
    ax.legend(frameon=False, fontsize=8, ncol=4, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout()
    fig.savefig(output / "thresholds.png", dpi=200)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validación complementaria de los modelos de riesgo de deserción.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--label", required=True, help="Nombre corto del conjunto (por ejemplo C500)")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--figures", action="store_true", help="Genera las figuras (requiere matplotlib)")
    args = parser.parse_args()

    features, target = prepare_training_frame(pd.read_csv(args.data))
    algorithms = available_algorithms()
    holdout_results, extra = holdout(features, target, algorithms, args.bootstrap)
    cv = cross_validation(features, target, algorithms, args.folds, args.repeats)

    output = RESULTS_DIR / args.label
    output.mkdir(parents=True, exist_ok=True)
    payload = {"dataset": args.data, "rows": int(len(target)), "positives": int(target.sum()),
               "threshold": CLASSIFICATION_THRESHOLD, "holdout": holdout_results, **extra, "cross_validation": cv}
    (output / "results.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.figures:
        save_figures(output, args.label, holdout_results, extra, cv)

    print(f"{args.label}: {len(target)} registros, {int(target.sum())} positivos")
    print(f"{'Modelo':<26}{'ROC-AUC':>16}{'PR-AUC':>16}{'Brier':>16}{'F1@0,30':>16}")
    for algorithm in algorithms + ["baseline"]:
        row = cv[algorithm]
        print(f"{NAMES[algorithm]:<26}" + "".join(
            f"{row[m]['mean']:>9.3f}±{row[m]['std']:.3f}" for m in ("roc_auc", "pr_auc", "brier", "f1")))
    print(f"Resultados en {output}")


if __name__ == "__main__":
    main()
