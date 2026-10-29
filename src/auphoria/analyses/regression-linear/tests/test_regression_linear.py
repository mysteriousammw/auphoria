"""Tests for the simple linear regression analysis.

Cross-checks slope, intercept, r, R2 and p against scipy.stats.linregress,
and against the hand-computed reference dataset x=[1..5], y=[2,4,5,4,5]
(Sxx=10, Sxy=6, slope=0.6, intercept=2.2, r=0.7746, R2=0.6). The module is
loaded the way the registry does (importlib) because the folder name contains
a hyphen and cannot be imported directly.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from auphoria.core.analysis import RunContext
from auphoria.core.errors import AssumptionError

MOD = importlib.import_module(
    "auphoria.analyses.regression-linear.analysis"
)
RegressionLinearAnalysis = MOD.RegressionLinearAnalysis


def _ctx() -> RunContext:
    logger = logging.getLogger("auphoria_test_regression_linear")
    logger.handlers = []
    return RunContext(
        seed=1, out_dir=Path("."), data_name="test", expert=False,
        _log=logger, _log_decision=lambda m: None,
    )


def _run(df: pd.DataFrame, params: dict | None = None):
    analysis = RegressionLinearAnalysis()
    return analysis.run(
        df,
        params or {"alpha": 0.05},
        {"outcome": "y", "predictor": "x"},
        _ctx(),
    )


def test_matches_scipy_and_hand_computed_reference():
    """x=[1..5], y=[2,4,5,4,5] -> slope 0.6, intercept 2.2, R2 0.6, r=0.7746."""
    analysis = RegressionLinearAnalysis()
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 5.0],
                       "y": [2.0, 4.0, 5.0, 4.0, 5.0]})
    result = analysis.run(
        df, {"alpha": 0.05}, {"outcome": "y", "predictor": "x"}, _ctx(),
    )

    ref = stats.linregress(df["x"], df["y"])
    assert result is not None

    coeff = result.tables["Coefficients"].set_index("Term")
    slope_row = coeff.loc["Slope (x)", "Estimate"]
    intercept_row = coeff.loc["Intercept", "Estimate"]
    assert float(slope_row) == pytest.approx(ref.slope, abs=1e-6)
    assert float(slope_row) == pytest.approx(0.6, abs=1e-6)
    assert float(intercept_row) == pytest.approx(ref.intercept, abs=1e-6)
    assert float(intercept_row) == pytest.approx(2.2, abs=1e-6)

    fits = result.tables["Fit statistics"].set_index("Measure")
    assert float(fits.loc["correlation (r)", "Value"]) == pytest.approx(
        ref.rvalue, abs=1e-6
    )
    assert float(fits.loc["R-squared", "Value"]) == pytest.approx(0.6, abs=1e-6)
    assert float(fits.loc["slope standard error", "Value"]) == pytest.approx(
        ref.stderr, abs=1e-6
    )
    assert float(fits.loc["R-squared", "Value"]) == pytest.approx(
        0.7746 ** 2, abs=1e-3
    )
    assert float(fits.loc["correlation (r)", "Value"]) == pytest.approx(
        6.0 / np.sqrt(60.0), abs=1e-3
    )

    # p-value matches SciPy.
    p_cell = str(fits.loc["p-value (slope)", "Value"])
    assert p_cell == "< 0.001" or float(p_cell) == pytest.approx(ref.pvalue, abs=1e-3)


def test_slope_p_and_ci_in_methods():
    result = _run(pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 5.0],
                                "y": [2.0, 4.0, 5.0, 4.0, 5.0]}))
    methods_text = " ".join(result.methods)
    assert "linear regression" in methods_text.lower()
    assert "0.600" in methods_text
    assert "R2" in methods_text or "R²" in methods_text
    assert any("not imputed" in m for m in result.methods) or any(
        "imputed" in m for m in result.methods
    )


def test_refuses_under_three_pairs():
    analysis = RegressionLinearAnalysis()
    df = pd.DataFrame({"x": [1.0, 2.0], "y": [1.0, 2.0]})
    with pytest.raises(AssumptionError):
        analysis.run(df, {"alpha": 0.05}, {"outcome": "y", "predictor": "x"}, _ctx())


def test_refuses_constant_predictor():
    analysis = RegressionLinearAnalysis()
    df = pd.DataFrame({"x": [3.0, 3.0, 3.0, 3.0, 3.0],
                       "y": [2.0, 4.0, 5.0, 4.0, 5.0]})
    with pytest.raises(AssumptionError):
        analysis.run(df, {"alpha": 0.05}, {"outcome": "y", "predictor": "x"}, _ctx())


def test_missing_pair_dropped_with_warning():
    analysis = RegressionLinearAnalysis()
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 5.0],
                       "y": [2.0, 4.0, 5.0, 4.0, 5.0]})
    df.iloc[0, 1] = np.nan  # drop the first outcome value
    result = analysis.run(
        df, {"alpha": 0.05}, {"outcome": "y", "predictor": "x"}, _ctx(),
    )
    fits = result.tables["Fit statistics"].set_index("Measure")
    assert int(fits.loc["sample size (n)", "Value"]) == 4  # one pair excluded
    assert any("row(s)" in w and "missing" in w for w in result.warnings)


def test_figures_methods_and_what_does_not_tell_present():
    result = _run(pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 5.0],
                                "y": [2.0, 4.0, 5.0, 4.0, 5.0]}))
    names = [f.name for f in result.figures]
    assert names == ["regression_scatter", "regression_residuals"]
    assert any("linear regression" in m for m in result.methods)
    text = result.what_does_not_tell
    assert text  # non-empty
    assert "causation" in text.lower()
    assert "extrapolat" in text.lower()


def test_small_sample_gets_warn_verdict():
    # 8 points -> n < 10 -> WARN verdict.
    x = [float(i) for i in range(1, 9)]
    y = [2.0 * v + 1.0 + (0.5 if i % 2 else -0.5) for i, v in enumerate(x)]
    result = _run(pd.DataFrame({"x": x, "y": y}))
    verdicts = {v.check: v.level for v in result.verdicts}
    assert verdicts["sample-size"] == "WARN"
    assert result.expert_review  # small sample flags statistician review


def test_adequate_sample_gets_pass_verdict():
    rng = np.random.default_rng(1)
    x = rng.uniform(0, 10, size=50)
    y = 2.0 * x + 5.0 + rng.normal(0, 1, size=50)
    result = _run(pd.DataFrame({"x": x, "y": y}))
    verdicts = {v.check: v.level for v in result.verdicts}
    assert verdicts["sample-size"] == "PASS"
