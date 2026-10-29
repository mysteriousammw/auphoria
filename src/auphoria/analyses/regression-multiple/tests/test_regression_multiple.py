"""Tests for the multiple linear regression analysis.

Uses small synthetic data with a known linear structure, and compares the
coefficients and R2 against statsmodels.api.OLS fitted directly in the test as
the documented reference library.

Reference model used throughout:  y = 1 + 2*x1 - 1*x2 + e

with x1, x2 random and e random noise. Because the analysis fits the same
OLS (with a constant) as statsmodels, the reported coefficients and R2 must
match the reference implementation exactly (within 1e-6).
"""

from __future__ import annotations

import importlib

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from auphoria.core.analysis import AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

_ANALYSIS_MODULE = importlib.import_module("auphoria.analyses.regression-multiple.analysis")
RegressionMultipleAnalysis = _ANALYSIS_MODULE.RegressionMultipleAnalysis

# The documented reference: y = 1 + 2*x1 - 1*x2 + e
_TRUE_BETA = {"Intercept": 1.0, "x1": 2.0, "x2": -1.0}


def _ctx() -> RunContext:
    import logging
    from pathlib import Path

    logger = logging.getLogger("auphoria_reg_multiple_test")
    logger.handlers = []
    return RunContext(
        seed=1,
        out_dir=Path("."),
        data_name="test",
        expert=False,
        _log=logger,
        _log_decision=lambda m: None,
    )


def _run(df: pd.DataFrame, **params) -> AnalysisResult:
    return RegressionMultipleAnalysis().run(
        df,
        {"alpha": 0.05, **params},
        {"outcome": "y"},
        _ctx(),
    )


def _make_df(n: int = 120, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    x1 = rng.uniform(0, 10, n)
    x2 = rng.normal(0, 3, n)
    e = rng.normal(0, 1.5, n)
    y = 1.0 + 2.0 * x1 - 1.0 * x2 + e
    return pd.DataFrame({"y": y, "x1": x1, "x2": x2})


# --------------------------------------------------------------------------
# (1) agreement with statsmodels OLS (the documented reference) within 1e-6
# --------------------------------------------------------------------------
def test_multiple_regression_matches_statsmodels_reference():
    df = _make_df()
    result = _run(df)

    coeffs = result.tables["Coefficients"].set_index("predictor")
    model = result.tables["Model"].set_index("Statistic")

    # Reference fit on the same data.
    X = sm.add_constant(df[["x1", "x2"]])
    ref = sm.OLS(df["y"], X).fit()

    # Coefficients match the reference within 1e-6.
    for name, beta in _TRUE_BETA.items():
        if name == "Intercept":
            continue
        assert float(coeffs.loc[name, "beta"]) == pytest.approx(
            float(ref.params[name]), abs=1e-6
        )
        # And close to the true generating coefficient.
        assert float(coeffs.loc[name, "beta"]) == pytest.approx(beta, abs=0.5)

    # R2 and adjusted R2 match the reference within 1e-6.
    assert float(model.loc["R2", "Value"]) == pytest.approx(
        float(ref.rsquared), abs=1e-6
    )
    assert float(model.loc["Adjusted R2", "Value"]) == pytest.approx(
        float(ref.rsquared_adj), abs=1e-6
    )
    # Model F, p and residual df match.
    assert float(model.loc["F", "Value"]) == pytest.approx(
        float(ref.fvalue), abs=1e-6
    )
    assert float(model.loc["p (model)", "Value"]) == pytest.approx(
        float(ref.f_pvalue), abs=1e-6
    )
    assert int(model.loc["df residual", "Value"]) == pytest.approx(
        int(ref.df_resid)
    )


# --------------------------------------------------------------------------
# (2) VIF table is present and well-formed for uncorrelated predictors
# --------------------------------------------------------------------------
def test_vif_table_present_and_finite():
    result = _run(_make_df())
    vif = result.tables["VIF"]
    assert list(vif.columns) == ["predictor", "R2_j (vs others)", "VIF"]
    assert set(vif["predictor"].tolist()) == {"x1", "x2"}
    # Weakly correlated predictors -> finite reasonable VIFs around 1.
    for v in vif["VIF"]:
        assert np.isfinite(v)
        assert 0.5 < v < 5.0


# --------------------------------------------------------------------------
# (3) refuses a single predictor
# --------------------------------------------------------------------------
def test_refuses_single_predictor():
    df = _make_df(60).drop(columns=["x2"])
    with pytest.raises(AssumptionError, match="at least two"):
        _run(df)


# --------------------------------------------------------------------------
# (4) refuses n <= k (not enough rows for the predictors)
# --------------------------------------------------------------------------
def test_refuses_n_leq_k():
    df = _make_df(3)  # 3 rows, 2 predictors -> n >= k refuses
    with pytest.raises(AssumptionError, match="n > k"):
        _run(df)


def test_refuses_exactly_k_rows():
    df = _make_df(2)  # exactly k = 2 rows for 2 predictors
    with pytest.raises(AssumptionError, match="n > k"):
        _run(df)


# --------------------------------------------------------------------------
# (5) refuses a perfectly collinear (singular) design
# --------------------------------------------------------------------------
def test_refuses_singular_design():
    df = _make_df(60)
    # x3 is an exact linear combination of x1: perfect collinearity.
    df["x3"] = 2.0 * df["x1"] + 3.0
    with pytest.raises(AssumptionError):
        _run(df)


# --------------------------------------------------------------------------
# (6) missing values -> listwise exclusion with a warning, never imputed
# --------------------------------------------------------------------------
def test_missing_values_dropped_with_warning():
    df = _make_df(100)
    df.iloc[2, df.columns.get_loc("y")] = np.nan
    df.iloc[5, df.columns.get_loc("x2")] = np.nan
    result = _run(df)

    model = result.tables["Model"].set_index("Statistic")
    # Two rows dropped listwise -> n = 98.
    assert int(model.loc["n", "Value"]) == 98
    assert any("row(s)" in w and "missing" in w for w in result.warnings)
    assert all("imput" not in w.lower() or "no" in w.lower()
               for w in result.warnings)


# --------------------------------------------------------------------------
# (7) returns a figure, methods, summaries and a what_does_not_tell
# --------------------------------------------------------------------------
def test_returns_figure_methods_and_caveats():
    result = _run(_make_df())
    assert len(result.figures) == 1
    assert result.figures[0].name == "predicted_vs_actual"
    assert len(result.methods) >= 2
    methods_text = " ".join(result.methods)
    assert "multiple linear regression" in methods_text.lower()
    assert "R2" in methods_text
    assert len(result.what_does_not_tell) > 40
    assert "caus" in result.what_does_not_tell.lower()
    assert "extrapolat" in result.what_does_not_tell.lower()
    assert "multicollinearity" in result.what_does_not_tell.lower()
    assert "predictors" in result.summaries
    assert "R2" in result.summaries


# --------------------------------------------------------------------------
# (8) expert review banner for a small sample
# --------------------------------------------------------------------------
def test_expert_review_banner_for_small_n():
    result = _run(_make_df(15))  # 15 rows < recommended 30
    assert any("expert review" in r or "statistician" in r
               for r in result.expert_review)
    levels = {v.check: v.level for v in result.verdicts}
    assert "sample-size" in levels
    assert levels["sample-size"] == "WARN"


def test_no_expert_review_banner_in_healthy_sample():
    result = _run(_make_df(120))
    assert not any("recommended minimum" in r for r in result.expert_review)
    levels = {v.check: v.level for v in result.verdicts}
    assert levels["sample-size"] == "PASS"
    assert levels["multicollinearity"] == "PASS"
