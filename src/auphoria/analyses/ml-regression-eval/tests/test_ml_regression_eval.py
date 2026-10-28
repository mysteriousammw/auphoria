"""Tests for the ML regression model evaluation analysis.

Uses small synthetic data and compares the reported metrics against
scikit-learn's reference implementation (the "documented reference"): the same
train/test split (same seed and test_size) and a plain LinearRegression fit,
so RMSE, MAE and R2 must match to within floating error.
"""

from __future__ import annotations

import importlib

import numpy as np
import pandas as pd
import pytest

from auphoria.core.analysis import AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

# The analysis id contains a hyphen ('ml-regression-eval'), which is not valid
# Python syntax in an import statement, so load the module by name.
_ML_MODULE = importlib.import_module("auphoria.analyses.ml-regression-eval.analysis")
MLRegressionEvalAnalysis = _ML_MODULE.MLRegressionEvalAnalysis


def _ctx() -> RunContext:
    import logging

    logger = logging.getLogger("auphoria_test")
    logger.handlers = []
    return RunContext(
        seed=1,
        out_dir=__import__("pathlib").Path("."),
        data_name="test",
        expert=False,
        _log=logger,
        _log_decision=lambda m: None,
    )


# 60 rows, two numeric features and a clean linear target with mild noise.
_rng = np.random.default_rng(42)
_X1 = _rng.normal(0, 1, 60)
_X2 = _rng.normal(0, 1, 60)
_Y = 3.0 * _X1 - 2.0 * _X2 + _rng.normal(0, 0.5, 60)
_DATA = pd.DataFrame(
    {
        "x1": _X1,
        "x2": _X2,
        "y": _Y,
        "label": ["cat" if i % 2 == 0 else "dog" for i in range(60)],
    }
)


def _make_df(**overrides) -> pd.DataFrame:
    df = _DATA.copy()
    for k, v in overrides.items():
        df[k] = v
    return df


def _run(df: pd.DataFrame, **params) -> AnalysisResult:
    return MLRegressionEvalAnalysis().run(
        df,
        {"test_size": 0.3, "cv_folds": 5, "random_state": 1, **params},
        {"target": "y"},
        _ctx(),
    )


def _reference_metrics(df: pd.DataFrame):
    """Reference metrics via sklearn directly (the documented reference)."""
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from sklearn.model_selection import train_test_split

    X = df[["x1", "x2"]].to_numpy(dtype=float)
    y = df["y"].to_numpy(dtype=float)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, random_state=1)
    model = LinearRegression().fit(Xtr, ytr)
    pred = model.predict(Xte)
    return {
        "rmse": float(np.sqrt(mean_squared_error(yte, pred))),
        "mae": float(mean_absolute_error(yte, pred)),
        "r2": float(r2_score(yte, pred)),
        "n_test": int(len(yte)),
    }


def _metric(result: AnalysisResult, name: str) -> float:
    table = result.tables["Test-set metrics"].set_index("Metric")
    return float(table.loc[name, "Value"])


def test_ml_rmse_matches_sklearn():
    ref = _reference_metrics(_DATA)
    result = _run(_DATA)
    assert ref["n_test"] == 18  # 0.3 * 60, same split as the analysis
    assert _metric(result, "RMSE") == pytest.approx(ref["rmse"], abs=1e-3)


def test_ml_r2_matches_sklearn():
    ref = _reference_metrics(_DATA)
    result = _run(_DATA)
    assert _metric(result, "R2") == pytest.approx(ref["r2"], abs=1e-4)


def test_ml_mae_matches_sklearn():
    ref = _reference_metrics(_DATA)
    result = _run(_DATA)
    assert _metric(result, "MAE") == pytest.approx(ref["mae"], abs=1e-4)


def test_ml_cv_table_present_and_consistent():
    result = _run(_DATA)
    cv = result.tables["Cross-validation RMSE"]
    assert len(cv) == 5  # cv_folds = 5
    assert "Cross-validation summary" in result.tables
    mean_row = result.tables["Cross-validation summary"].set_index("Measure")
    assert float(mean_row.loc["Mean CV RMSE", "Value"]) == pytest.approx(
        float(cv["RMSE"].mean()), abs=1e-4
    )


def test_ml_refuses_no_numeric_feature():
    df = pd.DataFrame(
        {"y": [1.0, 2.0, 3.0, 4.0, 5.0] * 5,
         "group": ["a", "b", "c", "d", "e"] * 5}
    )
    with pytest.raises(AssumptionError, match="[Nn]umeric feature"):
        _run(df)


def test_ml_missing_values_dropped_with_warning_never_imputed():
    df = _make_df()
    df.loc[0, "x1"] = np.nan
    df.loc[1, "x1"] = np.nan
    result = _run(df)
    # Missing rows are counted and dropped (listwise), never imputed.
    missing_ws = [w for w in result.warnings if "row(s)" in w and "missing" in w]
    assert missing_ws
    assert "imputed" in missing_ws[0] and "counted" in missing_ws[0]
    methods_text = " ".join(result.methods)
    assert "imputed" in methods_text and "excluded" in methods_text
    assert int(result.summaries["rows used"]) == 58  # 60 - 2 dropped
    # The reported test metrics still compare against the reference computed
    # on the same dropped data.
    ref_df = df.dropna(subset=["x1", "x2", "y"])
    ref = _reference_metrics(ref_df)
    assert int(ref["n_test"]) == int(result.summaries["test set"])
    assert _metric(result, "RMSE") == pytest.approx(ref["rmse"], abs=1e-3)


def test_ml_refuses_too_few_rows():
    df = pd.DataFrame(
        {"x1": [1.0] * 10, "x2": [1.0] * 10, "y": list(range(10))}
    )
    with pytest.raises(AssumptionError, match="20"):
        _run(df)


def test_ml_figures_methods_and_honest_limits():
    result = _run(_DATA)
    assert len(result.figures) == 2
    names = {f.name for f in result.figures}
    assert names == {"predicted_vs_actual", "cv_rmse"}
    assert len(result.methods) >= 3
    assert result.what_does_not_tell  # honest interpretation is set
    # Sample size verdict: 60 complete rows -> PASS.
    levels = {v.check: v.level for v in result.verdicts}
    assert levels["sample-size"] == "PASS"


def test_ml_small_sample_expert_review_and_warn_verdict():
    df = pd.DataFrame(
        {"x1": np.linspace(0, 1, 25), "x2": np.linspace(1, 0, 25),
         "y": 2.0 * np.linspace(0, 1, 25) + _rng.normal(0, 0.1, 25)}
    )
    result = _run(df)
    levels = {v.check: v.level for v in result.verdicts}
    assert levels["sample-size"] == "WARN"  # fewer than 30 rows
    assert result.expert_review  # advanced analysis flags for review
    assert "statistician" in result.expert_review[0]
