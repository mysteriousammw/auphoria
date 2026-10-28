"""Tests for the Spearman rank correlation analysis.

Checks rho and p against SciPy's reference implementation and hand-computed
values on small synthetic data.
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

# The folder name contains a hyphen, so it cannot appear in an import
# statement; import the module via string and grab the class from it.
_analysis_module = importlib.import_module(
    "auphoria.analyses.spearman-correlation.analysis"
)
SpearmanCorrelationAnalysis = _analysis_module.SpearmanCorrelationAnalysis


def _ctx() -> RunContext:
    logger = logging.getLogger("auphoria_test_spearman")
    logger.handlers = []
    return RunContext(
        seed=1, out_dir=Path("."), data_name="test", expert=False,
        _log=logger, _log_decision=lambda m: None,
    )


def _run(x, y, params=None):
    analysis = SpearmanCorrelationAnalysis()
    df = pd.DataFrame({"x": [float(v) for v in x], "y": [float(v) for v in y]})
    return analysis.run(
        df, params or {"tail": "two-sided", "alpha": 0.05},
        {"x": "x", "y": "y"}, _ctx(),
    )


def test_perfect_positive_monotonic_rho_eq_1():
    result = _run([1.0, 2.0, 3.0, 4.0, 5.0], [2.0, 4.0, 6.0, 8.0, 10.0])
    table = result.tables["Spearman correlation"].set_index("Variable")
    assert float(table.loc["Spearman rho", "Value"]) == pytest.approx(1.0, abs=1e-9)
    assert int(table.loc["sample size (n)", "Value"]) == 5
    assert table.loc["direction", "Value"] == "positive"


def test_perfect_negative_monotonic_rho_eq_minus_1():
    result = _run([1.0, 2.0, 3.0, 4.0, 5.0], [10.0, 8.0, 6.0, 4.0, 2.0])
    table = result.tables["Spearman correlation"].set_index("Variable")
    rho = float(table.loc["Spearman rho", "Value"])
    assert rho == pytest.approx(-1.0, abs=1e-9)
    assert table.loc["direction", "Value"] == "negative"


def test_hand_computed_rho_05():
    """x = [1..5], y = [3,1,4,2,5].

    rank_x = [1,2,3,4,5], rank_y = [3,1,4,2,5]
    d = rank_x - rank_y = [-2,1,-1,2,0], sum(d^2) = 10
    rho = 1 - 6*10/(5*(25-1)) = 1 - 60/120 = 0.5
    """
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [3.0, 1.0, 4.0, 2.0, 5.0]
    result = _run(x, y)
    table = result.tables["Spearman correlation"].set_index("Variable")
    got = float(table.loc["Spearman rho", "Value"])
    ref_rho, ref_p = stats.spearmanr(x, y)
    assert got == pytest.approx(ref_rho, abs=1e-6)
    assert got == pytest.approx(0.5, abs=1e-6)


def test_requires_three_pairs():
    with pytest.raises(AssumptionError):
        _run([1.0, 2.0], [1.0, 2.0])


def test_refuses_constant_column():
    with pytest.raises(AssumptionError):
        _run([1.0, 2.0, 3.0, 4.0], [7.0, 7.0, 7.0, 7.0])


def test_pairwise_missing_reported_not_imputed():
    analysis = SpearmanCorrelationAnalysis()
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 5.0],
                       "y": [3.0, 1.0, 4.0, 2.0, 5.0]})
    df.iloc[0, 1] = np.nan  # drop the first y
    result = analysis.run(
        df, {"tail": "two-sided", "alpha": 0.05}, {"x": "x", "y": "y"}, _ctx(),
    )
    table = result.tables["Spearman correlation"].set_index("Variable")
    assert int(table.loc["sample size (n)", "Value"]) == 4  # one pair excluded
    assert any("row(s)" in w and "missing" in w for w in result.warnings)


def test_returns_figure_and_methods():
    result = _run([1.0, 2.0, 3.0, 4.0, 5.0], [2.0, 4.0, 6.0, 8.0, 10.0])
    assert len(result.figures) == 1
    assert result.figures[0].name == "spearman_rank_scatter"
    assert any("Spearman" in m for m in result.methods)
