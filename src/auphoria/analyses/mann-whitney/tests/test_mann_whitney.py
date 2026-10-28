"""Tests for the Mann-Whitney U test analysis.

Uses small synthetic data with known, hand-computable answers, and compares
against SciPy's reference implementation (the "documented reference").

Hand-computed example: group A = [1, 2, 3], group B = [4, 5, 6, 7].
Combined ranks: A holds ranks 1, 2, 3 (sum 6); B holds 4, 5, 6, 7 (sum 22);
n1 = 3, n2 = 4, n1*n2 = 12.
U1 (for A) = sum_ranks_A - n1(n1+1)/2 = 6 - 6 = 0; U2 = 12 - 0 = 12.
One-sided p = P(U <= 0) = 1 / C(7,3) = 1/35 = 0.02857; two-sided doubles
to 0.05714.
Rank-biserial r = 1 - 2*U1/(n1*n2) = 1 - 2*0/12 = 1.0 -> "large".
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
    "auphoria.analyses.mann-whitney.analysis"
)
MannWhitneyAnalysis = _analysis_module.MannWhitneyAnalysis


def _ctx() -> RunContext:
    logger = logging.getLogger("auphoria_test_mw")
    logger.handlers = []
    return RunContext(
        seed=1,
        out_dir=Path("."),
        data_name="test",
        expert=False,
        _log=logger,
        _log_decision=lambda m: None,
    )


def _df(a: list[float], b: list[float]) -> pd.DataFrame:
    groups = ["A"] * len(a) + ["B"] * len(b)
    return pd.DataFrame({"value": a + b, "group": groups})


# Hand-computed example: A = [1,2,3], B = [4,5,6,7] -> U1(A) = 0, U2 = 12,
# p (two-sided, exact) = 2/35 = 0.05714, rank-biserial r = 1.0.
A = [1.0, 2.0, 3.0]
B = [4.0, 5.0, 6.0, 7.0]


def test_mann_whitney_matches_scipy():
    analysis = MannWhitneyAnalysis()
    df = _df(A, B)
    result = analysis.run(
        df, {"alpha": 0.05, "tail": "two-sided"},
        {"outcome": "value", "group": "group"}, _ctx(),
    )
    a = np.asarray(A)
    b = np.asarray(B)
    ref = stats.mannwhitneyu(a, b, alternative="two-sided", method="auto")
    table = result.tables["Mann-Whitney U test"]
    got_u = float(table.loc[table["Item"] == "U statistic", "Value"].iloc[0])
    got_p = float(table.loc[table["Item"] == "p-value", "Value"].iloc[0])
    assert got_u == pytest.approx(float(ref.statistic), abs=1e-6)
    assert got_p == pytest.approx(float(ref.pvalue), abs=1e-4)
    # Hand-computed values: U = 0, p = 2/35 = 0.05714.
    assert got_u == pytest.approx(0.0, abs=1e-6)
    assert got_p == pytest.approx(0.05714, abs=1e-4)


def test_mann_whitney_effect_size():
    analysis = MannWhitneyAnalysis()
    df = _df(A, B)
    result = analysis.run(
        df, {"alpha": 0.05, "tail": "two-sided"},
        {"outcome": "value", "group": "group"}, _ctx(),
    )
    table = result.tables["Mann-Whitney U test"]
    # U1 for A = 0 -> r = 1 - 2*0/12 = 1.0 -> "large".
    r = float(table.loc[table["Item"] == "rank-biserial r (effect size)", "Value"].iloc[0])
    assert r == pytest.approx(1.0, abs=1e-4)
    assert table.loc[table["Item"] == "effect size label", "Value"].iloc[0] == "large"
    # Group statistics: medians 2.0 (A) and 5.5 (B), n = 3 and 4.
    gs = result.tables["Group statistics"].set_index("Group")
    assert int(gs.loc["A", "n"]) == 3
    assert int(gs.loc["B", "n"]) == 4
    assert float(gs.loc["A", "Median"]) == pytest.approx(2.0, abs=1e-4)
    assert float(gs.loc["B", "Median"]) == pytest.approx(5.5, abs=1e-4)


def test_mann_whitney_works_with_exactly_two_categories():
    analysis = MannWhitneyAnalysis()
    df = _df(A, B)
    result = analysis.run(
        df, {"alpha": 0.05, "tail": "two-sided"},
        {"outcome": "value", "group": "group"}, _ctx(),
    )
    assert result.tables["Mann-Whitney U test"] is not None


def test_mann_whitney_refuses_single_group():
    analysis = MannWhitneyAnalysis()
    df = pd.DataFrame({"value": [1.0, 2.0, 3.0], "group": ["A", "A", "A"]})
    with pytest.raises(AssumptionError):
        analysis.run(
            df, {"alpha": 0.05, "tail": "two-sided"},
            {"outcome": "value", "group": "group"}, _ctx(),
        )


def test_mann_whitney_refuses_more_than_two_groups():
    analysis = MannWhitneyAnalysis()
    df = pd.DataFrame({"value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
                       "group": ["A", "A", "B", "B", "C", "C"]})
    with pytest.raises(AssumptionError):
        analysis.run(
            df, {"alpha": 0.05, "tail": "two-sided"},
            {"outcome": "value", "group": "group"}, _ctx(),
        )


def test_mann_whitney_refuses_non_numeric_outcome_with_text():
    analysis = MannWhitneyAnalysis()
    df = pd.DataFrame({
        "value": ["1", "2", "three", "4", "5", "6"],
        "group": ["A", "A", "A", "B", "B", "B"],
    })
    with pytest.raises(AssumptionError):
        analysis.run(
            df, {"alpha": 0.05, "tail": "two-sided"},
            {"outcome": "value", "group": "group"}, _ctx(),
        )


def test_mann_whitney_handles_missing_without_imputation():
    analysis = MannWhitneyAnalysis()
    df = _df(A, B)
    # Drop 2 rows (one per group) via a missing value in the outcome.
    df.iloc[0, df.columns.get_loc("value")] = np.nan
    df.iloc[-1, df.columns.get_loc("value")] = np.nan  # the very last row (group B)
    result = analysis.run(
        df, {"alpha": 0.05, "tail": "two-sided"},
        {"outcome": "value", "group": "group"}, _ctx(),
    )
    # 2 rows excluded with a warning, none imputed: group n = 2 and 3.
    gs = result.tables["Group statistics"].set_index("Group")
    assert int(gs.loc["A", "n"]) == 2
    assert int(gs.loc["B", "n"]) == 3
    assert any("row(s)" in w and "missing" in w for w in result.warnings)


def test_mann_whitney_missing_in_group_column_excluded():
    """Missingness in the group column is also excluded and counted."""
    analysis = MannWhitneyAnalysis()
    df = _df(A, B)
    df.loc[0, "group"] = np.nan
    result = analysis.run(
        df, {"alpha": 0.05, "tail": "two-sided"},
        {"outcome": "value", "group": "group"}, _ctx(),
    )
    gs = result.tables["Group statistics"].set_index("Group")
    assert int(gs.loc["A", "n"]) == 2
    assert int(gs.loc["B", "n"]) == 4


def test_mann_whitney_returns_figure_and_methods():
    analysis = MannWhitneyAnalysis()
    df = _df(A, B)
    result = analysis.run(
        df, {"alpha": 0.05, "tail": "two-sided"},
        {"outcome": "value", "group": "group"}, _ctx(),
    )
    assert len(result.figures) == 1
    assert result.figures[0].name == "mann_whitney_boxplot"
    assert len(result.methods) >= 3
    assert any("mann-whitney" in m.lower() for m in result.methods)
    assert "rank-biserial" in " ".join(result.methods)
    # No missing values here, so no imputation claims in methods.
    assert not any("imputed" in m.lower() for m in result.methods)
