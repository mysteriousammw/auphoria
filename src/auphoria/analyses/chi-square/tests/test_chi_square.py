"""Tests for the chi-square test of independence analysis.

Uses small synthetic data with known, hand-computable answers, and compares
against SciPy's reference implementation (the "documented reference").
"""

from __future__ import annotations

from importlib import import_module

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from auphoria.core.analysis import RunContext
from auphoria.core.errors import AssumptionError

# The folder name is 'chi-square'; Python source cannot spell a hyphenated
# import, so load the module through importlib (as the registry does).
ChiSquareAnalysis = import_module(
    "auphoria.analyses.chi-square.analysis"
).ChiSquareAnalysis


def _ctx() -> RunContext:
    import logging

    logger = logging.getLogger("auphoria_chi_test")
    logger.handlers = []
    return RunContext(
        seed=1,
        out_dir=__import__("pathlib").Path("."),
        data_name="test",
        expert=False,
        _log=logger,
        _log_decision=lambda m: None,
    )


def _df(var1: list, var2: list) -> pd.DataFrame:
    return pd.DataFrame({"var1": var1, "var2": var2})


def _expand(cats1: list[str], cats2: list[str], counts: list[list[int]]) -> pd.DataFrame:
    """Expand a count table into one observation per row."""
    var1, var2 = [], []
    for i, row in enumerate(counts):
        for j, c in enumerate(row):
            var1.extend([cats1[i]] * c)
            var2.extend([cats2[j]] * c)
    return _df(var1, var2)


def test_chi_square_matches_scipy_and_hand_cramers_v():
    analysis = ChiSquareAnalysis()
    df = _expand(["A", "B"], ["yes", "no"], [[30, 10], [10, 30]])
    result = analysis.run(
        df, {"alpha": 0.05}, {"var1": "var1", "var2": "var2"}, _ctx(),
    )
    observed = np.array([[30, 10], [10, 30]])
    # Total n = 80; under independence all four expected counts are exactly 20.
    ref_chi2, ref_p, ref_dof, ref_expected = stats.chi2_contingency(
        observed, correction=True
    )
    assert np.allclose(ref_expected, 20.0)
    assert ref_dof == 1

    table = result.tables["Chi-square test"]
    got_chi2 = float(
        table.loc[table["Item"] == "chi-square statistic", "Value"].iloc[0]
    )
    got_p = float(table.loc[table["Item"] == "p-value", "Value"].iloc[0])
    got_df = float(
        table.loc[table["Item"] == "degrees of freedom", "Value"].iloc[0]
    )
    assert got_chi2 == pytest.approx(ref_chi2, abs=1e-6)
    assert got_p == pytest.approx(ref_p, abs=1e-6)
    assert got_df == pytest.approx(ref_dof, abs=1e-6)

    # Hand-check Cramer's V: sqrt(chi2 / (n * min(rows-1, cols-1)))
    # = sqrt(chi2 / (80 * 1)) for this 2x2 table.
    hand_v = float(np.sqrt(ref_chi2 / (80 * min(2 - 1, 2 - 1))))
    got_v = float(
        table.loc[table["Item"] == "Cramer's V (effect size)", "Value"].iloc[0]
    )
    assert got_v == pytest.approx(hand_v, abs=1e-6)

    # All expected counts are well above 5, so the check passes.
    assert any(
        v.level == "PASS" and v.check == "expected-counts"
        for v in result.verdicts
    )


def test_chi_square_warns_on_small_expected_counts():
    analysis = ChiSquareAnalysis()
    # Every expected count comes out exactly 5 — the boundary of the rule of
    # thumb (at least 5 per cell) — so the result must be flagged.
    df = _expand(["A", "B"], ["yes", "no"], [[1, 9], [9, 1]])
    result = analysis.run(
        df, {"alpha": 0.05}, {"var1": "var1", "var2": "var2"}, _ctx(),
    )
    assert any(
        v.level == "WARN" and v.check == "expected-counts"
        for v in result.verdicts
    )
    assert any("Fisher" in w for w in result.warnings)
    assert any("approximate" in w.lower() for w in result.warnings)


def test_chi_square_refuses_single_category_column():
    analysis = ChiSquareAnalysis()
    df = pd.DataFrame(
        {"var1": ["A", "A", "A", "A"], "var2": ["x", "y", "x", "y"]}
    )
    with pytest.raises(AssumptionError):
        analysis.run(
            df, {"alpha": 0.05}, {"var1": "var1", "var2": "var2"}, _ctx(),
        )


def test_chi_square_refuses_missing_columns():
    analysis = ChiSquareAnalysis()
    df = _df(["A", "B"], ["x", "y"])
    with pytest.raises(AssumptionError):
        analysis.run(
            df, {"alpha": 0.05}, {"var1": "var1", "var2": "nope"}, _ctx(),
        )


def test_chi_square_drops_missing_rows_with_warning():
    analysis = ChiSquareAnalysis()
    df = _expand(["A", "B"], ["yes", "no"], [[30, 10], [10, 30]])
    # Rows 0-29 are A/yes and rows 30-39 are A/no: two missing rows (both
    # A/yes) are dropped, leaving 78 observations.
    df.loc[0, "var1"] = np.nan
    df.loc[3, "var2"] = np.nan
    result = analysis.run(
        df, {"alpha": 0.05}, {"var1": "var1", "var2": "var2"}, _ctx(),
    )
    cont = result.tables["Contingency table"]
    assert int(cont.loc["A", "yes"]) == 28
    assert int(cont.loc["A", "Row total"]) == 38
    assert int(cont.loc["B", "Row total"]) == 40
    assert any("row(s)" in w and "missing" in w for w in result.warnings)
    table = result.tables["Chi-square test"]
    got_n = float(table.loc[table["Item"] == "sample size (n)", "Value"].iloc[0])
    assert got_n == pytest.approx(78.0, abs=1e-9)


def test_chi_square_returns_figure_and_methods():
    analysis = ChiSquareAnalysis()
    df = _expand(["A", "B"], ["yes", "no"], [[30, 10], [10, 30]])
    result = analysis.run(
        df, {"alpha": 0.05}, {"var1": "var1", "var2": "var2"}, _ctx(),
    )
    assert len(result.figures) == 1
    assert result.figures[0].name == "chi_square_stacked_bars"
    assert len(result.methods) >= 2
    assert any("chi-square" in m.lower() for m in result.methods)
    assert "Row total" in result.tables["Contingency table"].columns
    assert "Row total" in result.tables["Row percentages"].columns
