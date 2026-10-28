"""Tests for the Pearson correlation analysis.

Checks r and p against SciPy's reference implementation and hand-computed
values on small synthetic data.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from auphoria.analyses.correlation.analysis import CorrelationAnalysis
from auphoria.core.analysis import RunContext
from auphoria.core.errors import AssumptionError


def _ctx() -> RunContext:
    logger = logging.getLogger("auphoria_test_correl")
    logger.handlers = []
    return RunContext(
        seed=1, out_dir=Path("."), data_name="test", expert=False,
        _log=logger, _log_decision=lambda m: None,
    )


def test_perfect_positive_line_r_eq_1():
    analysis = CorrelationAnalysis()
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 5.0],
                       "y": [2.0, 4.0, 6.0, 8.0, 10.0]})
    result = analysis.run(
        df, {"tail": "two-sided"}, {"x": "x", "y": "y"}, _ctx(),
    )
    table = result.tables["Pearson correlation"].set_index("Variable")
    assert float(table.loc["Pearson correlation (r)", "Value"]) == pytest.approx(1.0, abs=1e-9)
    assert int(table.loc["sample size (n)", "Value"]) == 5


def test_hand_computed_r_0967():
    """y = x^2 on x = 1..5. Cov(x,y)=60, var(x)=10, var(y)=374.
    r = 60/sqrt(10*374) = 0.9811 (matches SciPy)."""
    analysis = CorrelationAnalysis()
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [1.0, 4.0, 9.0, 16.0, 25.0]
    df = pd.DataFrame({"x": x, "y": y})
    result = analysis.run(df, {"tail": "two-sided"}, {"x": "x", "y": "y"}, _ctx())
    table = result.tables["Pearson correlation"].set_index("Variable")
    got = float(table.loc["Pearson correlation (r)", "Value"])
    ref_r, ref_p = stats.pearsonr(x, y)
    assert got == pytest.approx(ref_r, abs=1e-4)
    assert got == pytest.approx(60.0 / np.sqrt(10.0 * 374.0), abs=1e-3)
    assert got == pytest.approx(0.9811, abs=1e-3)


def test_perfect_negative_line():
    analysis = CorrelationAnalysis()
    x = [1.0, 2.0, 3.0, 4.0]
    y = [10.0, 7.0, 4.0, 1.0]
    df = pd.DataFrame({"x": x, "y": y})
    result = analysis.run(df, {"tail": "two-sided"}, {"x": "x", "y": "y"}, _ctx())
    table = result.tables["Pearson correlation"].set_index("Variable")
    r = float(table.loc["Pearson correlation (r)", "Value"])
    assert r == pytest.approx(-1.0, abs=1e-9)
    assert table.loc["direction", "Value"] == "negative"


def test_requires_three_pairs():
    analysis = CorrelationAnalysis()
    df = pd.DataFrame({"x": [1.0, 2.0], "y": [1.0, 2.0]})
    with pytest.raises(AssumptionError):
        analysis.run(df, {"tail": "two-sided"}, {"x": "x", "y": "y"}, _ctx())


def test_refuses_constant_column():
    analysis = CorrelationAnalysis()
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "y": [7.0, 7.0, 7.0, 7.0]})
    with pytest.raises(AssumptionError):
        analysis.run(df, {"tail": "two-sided"}, {"x": "x", "y": "y"}, _ctx())


def test_pairwise_missing_reported_not_imputed():
    analysis = CorrelationAnalysis()
    df = pd.DataFrame({
        "x": [1.0, 2.0, 3.0, 4.0, 5.0],
        "y": [1.0, 4.0, 9.0, 16.0, 25.0],
    })
    df.iloc[0, 1] = np.nan  # drop the first y
    result = analysis.run(df, {"tail": "two-sided"}, {"x": "x", "y": "y"}, _ctx())
    table = result.tables["Pearson correlation"].set_index("Variable")
    assert int(table.loc["sample size (n)", "Value"]) == 4  # one pair excluded
    assert any("row(s)" in w and "missing" in w for w in result.warnings)


def test_returns_figure_and_methods():
    analysis = CorrelationAnalysis()
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 5.0],
                       "y": [2.0, 4.0, 6.0, 8.0, 10.0]})
    result = analysis.run(df, {"tail": "two-sided"}, {"x": "x", "y": "y"}, _ctx())
    assert len(result.figures) == 1
    assert result.figures[0].name == "correlation_scatter"
    assert any("Pearson" in m for m in result.methods)
