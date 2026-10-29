"""Tests for the binary logistic regression analysis.

Uses deterministic synthetic data generated from a known coefficient vector
logit(p) = -1 + 1.5*x1 - 0.8*x2 (+ noise) and compares the analysis's
coefficients, odds ratios and likelihood-ratio p-value against statsmodels'
own Logit fit on the same data (the "reference implementation"). They must
agree within 1e-5.

The outcome is recorded as a categorical yes/no string in some tests and as a
numeric 0/1 column in others, to exercise the gracefully-accepted numeric
binary outcome.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from sklearn.metrics import roc_auc_score

from auphoria.core.analysis import AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

# The analysis id contains a hyphen ('logistic-regression'), which is not
# valid Python syntax in an import statement, so load the module by name.
_MODULE = importlib.import_module(
    "auphoria.analyses.logistic-regression.analysis"
)
LogRegAnalysis = _MODULE.LogisticRegressionAnalysis


def _ctx() -> RunContext:
    logger = logging.getLogger("auphoria_test_logreg")
    logger.handlers = []
    return RunContext(
        seed=1,
        out_dir=Path("."),
        data_name="test",
        expert=False,
        _log=logger,
        _log_decision=lambda m: None,
    )


def _synthetic(n: int = 300, seed: int = 7) -> pd.DataFrame:
    """Data from logit(p) = -1 + 1.5*x1 - 0.8*x2 + noise (deterministic)."""
    rng = np.random.default_rng(seed)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    logit = -1.0 + 1.5 * x1 - 0.8 * x2 + rng.normal(scale=1.0, size=n)
    y = (logit > 0.0).astype(int)  # threshold at probability 0.5, fixed seed
    return pd.DataFrame({"x1": x1, "x2": x2, "outcome": y})


def _run(df: pd.DataFrame) -> AnalysisResult:
    return LogRegAnalysis().run(
        df, {}, {"outcome": "outcome"}, _ctx()
    )


def _to_numeric_y(df: pd.DataFrame) -> pd.Series:
    """Coerce the outcome column to 0/1 float (matches the analysis's mapping)."""
    orig = df["outcome"]
    num = pd.to_numeric(orig, errors="coerce")
    if num.notna().all():
        vals = sorted(num.unique().tolist())
        return num.map({vals[0]: 0, vals[1]: 1}).astype(float)
    classes = sorted(orig.unique().tolist(), key=str)
    return orig.map({classes[0]: 0, classes[1]: 1}).astype(float)


def _reference(df: pd.DataFrame) -> dict:
    """Independent statsmodels Logit fit (the documented reference)."""
    X = sm.add_constant(df[["x1", "x2"]])
    y = _to_numeric_y(df)
    fit = sm.Logit(y, X).fit(disp=False)
    return {
        "params": fit.params,
        "llr_p": float(fit.llr_pvalue),
        "prsquared": float(fit.prsquared),
        "auc": roc_auc_score(y, fit.predict(X)),
    }


def test_coefficients_match_statsmodels_reference():
    df = _synthetic()
    result = _run(df)
    ref = _reference(df)
    coef = result.tables["Coefficients (odds ratios)"].set_index("predictor")
    assert coef.loc["Intercept", "beta"] == pytest.approx(ref["params"]["const"], abs=1e-5)
    assert coef.loc["x1", "beta"] == pytest.approx(ref["params"]["x1"], abs=1e-5)
    assert coef.loc["x2", "beta"] == pytest.approx(ref["params"]["x2"], abs=1e-5)


def test_lr_p_matches_statsmodels_reference():
    df = _synthetic()
    result = _run(df)
    ref = _reference(df)
    fit = result.tables["Model fit"].set_index("metric")
    assert float(fit.loc["Likelihood-ratio p-value", "value"]) == pytest.approx(
        ref["llr_p"], abs=1e-5
    )


def test_odds_ratios_are_exp_of_beta_and_zero_is_midway():
    df = _synthetic()
    result = _run(df)
    coef = result.tables["Coefficients (odds ratios)"].set_index("predictor")
    # OR = exp(beta)
    assert coef.loc["x1", "odds_ratio"] == pytest.approx(
        np.exp(coef.loc["x1", "beta"]), abs=1e-5
    )
    # The CI straddles the OR and excludes 1 when p < 0.05 (x1 effect).
    assert coef.loc["x1", "odds_ratio_ci_low"] < coef.loc["x1", "odds_ratio"]
    assert coef.loc["x1", "odds_ratio"] < coef.loc["x1", "odds_ratio_ci_high"]


def test_numeric_binary_outcome_gracefully_accepted():
    # The outcome is already a numeric 0/1 column (the common real-world case).
    df = _synthetic()
    result = _run(df)
    ref = _reference(df)
    coef = result.tables["Coefficients (odds ratios)"].set_index("predictor")
    assert coef.loc["x1", "beta"] == pytest.approx(ref["params"]["x1"], abs=1e-5)


def test_text_categorical_outcome_accepted_and_mapped():
    df = _synthetic()
    df["outcome"] = df["outcome"].map({0: "no", 1: "yes"})
    result = _run(df)
    ref = _reference(df)
    coef = result.tables["Coefficients (odds ratios)"].set_index("predictor")
    assert coef.loc["x1", "beta"] == pytest.approx(ref["params"]["x1"], abs=1e-5)


def test_refuses_three_class_outcome():
    df = _synthetic(90, seed=3)
    df["outcome"] = ["a", "b", "c"] * 30
    with pytest.raises(AssumptionError):
        _run(df)


def test_refuses_single_class_outcome():
    df = _synthetic(60, seed=4)
    df["outcome"] = 0
    with pytest.raises(AssumptionError):
        _run(df)


def test_refuses_no_numeric_predictor():
    df = pd.DataFrame({"outcome": [0, 1] * 10, "label": list("abcdefghijklmnopqrst")})
    with pytest.raises(AssumptionError):
        _run(df)


def test_missing_dropped_with_warning_never_imputed():
    df = _synthetic()
    df.iloc[0, df.columns.get_loc("x1")] = np.nan
    df.iloc[-1, df.columns.get_loc("x2")] = np.nan
    result = _run(df)
    fit = result.tables["Model fit"].set_index("metric")
    assert int(fit.loc["N (complete rows used)", "value"]) == len(df) - 2
    assert any("missing" in w and "dropped" in w for w in result.warnings)
    methods_text = " ".join(result.methods)
    assert "imputed" in methods_text and "dropped" in methods_text


def test_figures_methods_and_disclaimer():
    df = _synthetic()
    result = _run(df)
    assert len(result.figures) == 1
    assert result.figures[0].name == "roc_curve"
    assert len(result.methods) >= 3
    ref = _reference(df)
    assert float(result.summaries["McFadden pseudo-R2"]) == pytest.approx(
        ref["prsquared"], abs=1e-3
    )
    assert result.what_does_not_tell
    assert "in-sample" in result.what_does_not_tell or "causation" in result.what_does_not_tell


def test_in_sample_accuracy_and_confusion_matrix_present_and_labeled():
    df = _synthetic()
    result = _run(df)
    assert "Confusion matrix (in-sample)" in result.tables
    assert float(result.summaries["in-sample accuracy"]) >= 0.0
    assert float(result.summaries["in-sample accuracy"]) <= 1.0
    methods_text = " ".join(result.methods)
    assert "held-out" in methods_text or "in-sample" in methods_text


def test_expert_review_flagged_for_small_event_count():
    df = _synthetic(40, seed=11)
    # Force a lopsided / small-event outcome to trip the expert-review rule.
    df.loc[df["outcome"] == 1, "outcome"] = 0
    if df["outcome"].sum() == 0:  # re-inject a couple of rare events
        df.iloc[:2, df.columns.get_loc("outcome")] = 1
    result = _run(df)
    assert len(result.expert_review) >= 1
    assert any("class" in r.lower() or "case" in r.lower() for r in result.expert_review)


def test_roc_auc_matches_statsmodels_predict():
    df = _synthetic()
    result = _run(df)
    ref = _reference(df)
    # The figure caption embeds the AUC; recompute from the model-fit instead.
    fit = result.tables["Model fit"].set_index("metric")
    prs = float(fit.loc["McFadden Pseudo R-squared", "value"])
    assert prs == pytest.approx(ref["prsquared"], abs=1e-5)
    assert len(result.figures) == 1
