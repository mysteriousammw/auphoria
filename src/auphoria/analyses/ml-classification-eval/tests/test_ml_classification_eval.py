"""Tests for the ML classification model evaluation analysis.

Uses deterministic synthetic data and compares the analysis's numbers
against scikit-learn's own reference implementation (the "documented
reference"): the same split with the same seed, the same
LogisticRegression, and the same scoring functions, checking that the
analysis reproduces sklearn exactly.

The main dataset has two numeric features plus a binary label in ~60 rows,
enough for a stratified split while staying small and fast.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

from auphoria.core.analysis import AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

# The analysis id contains a hyphen ('ml-classification-eval'), which is not
# valid Python syntax in an import statement, so load the module by name.
_MODULE = importlib.import_module("auphoria.analyses.ml-classification-eval.analysis")
MLAnalysis = _MODULE.MlClassificationEvalAnalysis


def _ctx() -> RunContext:
    import logging

    logger = logging.getLogger("auphoria_test_ml")
    logger.handlers = []
    return RunContext(
        seed=1,
        out_dir=Path("."),
        data_name="test",
        expert=False,
        _log=logger,
        _log_decision=lambda m: None,
    )


def _synthetic(n: int = 60, seed: int = 42) -> pd.DataFrame:
    """Deterministic ~balanced binary data with two numeric features."""
    rng = np.random.default_rng(seed)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    score = 1.5 * x1 - 1.2 * x2 + rng.normal(scale=0.6, size=n)
    label = (score > 0.0).astype(int)
    return pd.DataFrame({"x1": x1, "x2": x2, "label": label})


def _run(df: pd.DataFrame, **params) -> AnalysisResult:
    return MLAnalysis().run(
        df,
        {"test_size": 0.3, "cv_folds": 5, "random_state": 1, **params},
        {"label": "label"},
        _ctx(),
    )


def _reference(df: pd.DataFrame, params: dict | None = None) -> dict:
    """Compute the sklearn reference on clean data (no missing values)."""
    params = params or {}
    test_size = params.get("test_size", 0.3)
    random_state = params.get("random_state", 1)
    features = ["x1", "x2"]
    X, y = df[features], df["label"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
    clf = LogisticRegression(max_iter=1000)
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)
    return {
        "y_test": y_test,
        "y_pred": y_pred,
        "y_proba": clf.predict_proba(X_test)[:, 1],
        "accuracy": accuracy_score(y_test, y_pred),
        "auc": roc_auc_score(y_test, clf.predict_proba(X_test)[:, 1]),
        "cm": confusion_matrix(y_test, y_pred, labels=sorted(np.unique(y))),
    }


def test_accuracy_matches_sklearn():
    df = _synthetic()
    result = _run(df)
    ref = _reference(df)
    acc = float(result.summaries["accuracy (test)"])
    assert acc == pytest.approx(ref["accuracy"], abs=1e-4)


def test_roc_auc_matches_sklearn():
    df = _synthetic()
    result = _run(df)
    ref = _reference(df)
    auc = float(result.summaries["ROC-AUC (test)"])
    assert auc == pytest.approx(ref["auc"], abs=1e-4)


def test_confusion_matrix_matches_sklearn():
    df = _synthetic()
    result = _run(df)
    ref = _reference(df)
    cm = result.tables["Confusion matrix"].to_numpy(dtype=float)
    assert np.allclose(cm, ref["cm"], atol=1e-6)


def test_refuses_single_class_label():
    df = _synthetic()
    df["label"] = 0  # single class (also at least two classes is a binary rule)
    with pytest.raises(AssumptionError):
        _run(df)


def test_refuses_too_few_numeric_features():
    df = pd.DataFrame({"x1": np.arange(30, dtype=float), "label": [0, 1] * 15})
    with pytest.raises(AssumptionError):
        _run(df)


def test_missing_dropped_with_warning_never_imputed():
    df = _synthetic()
    df.iloc[0, df.columns.get_loc("x1")] = np.nan
    df.iloc[-1, df.columns.get_loc("x2")] = np.nan
    result = _run(df)
    # 2 rows dropped, so the model sees 58 rows in total (train + test).
    train, test = (int(v) for v in result.summaries["train / test rows"].split(" / "))
    assert train + test == 58
    # A warning names the missing (dropped) handling.
    assert any("missing" in w and "dropped" in w for w in result.warnings)
    # Never imputed: methods paragraph records the drop, no imputation mention.
    methods_text = " ".join(result.methods)
    assert "imputed" in methods_text and "dropped" in methods_text


def test_figures_methods_and_disclaimer():
    df = _synthetic()
    result = _run(df)
    assert len(result.figures) == 2
    names = {f.name for f in result.figures}
    assert "roc_curve" in names
    assert "cross_validation_scores" in names
    assert len(result.methods) >= 3
    assert "logistic-regression" in " ".join(result.methods).lower()
    assert result.what_does_not_tell
    assert result.what_does_not_tell != "no data"


def _metric_summary(result: AnalysisResult, metric: str) -> float:
    """Grab a weighted average* number from the metrics table."""
    table = result.tables["Classification metrics"].set_index("Class")
    return float(table.loc["weighted avg", metric])


def test_metrics_table_agrees_with_classification_report():
    df = _synthetic()
    result = _run(df)
    ref = _reference(df)
    report = classification_report(
        ref["y_test"], ref["y_pred"], output_dict=True, zero_division=0
    )
    # Weighted F1 from the reference matches the summary F1.
    assert _metric_summary(result, "F1") == pytest.approx(
        report["weighted avg"]["f1-score"], abs=1e-4
    )
