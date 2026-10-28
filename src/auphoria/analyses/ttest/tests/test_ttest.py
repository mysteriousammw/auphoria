"""Tests for the independent-samples t-test analysis.

Uses small synthetic data with known, hand-computable answers, and compares
against SciPy's reference implementation (the "documented reference").
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from auphoria.analyses.ttest.analysis import TTestAnalysis
from auphoria.core.analysis import RunContext
from auphoria.core.errors import AssumptionError


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


def _df(a: list[float], b: list[float]) -> pd.DataFrame:
    groups = ["A"] * len(a) + ["B"] * len(b)
    return pd.DataFrame({"value": a + b, "group": groups})


# Hand-computed textbook example: means 4.0 and 10.0, t = 5.196, df = 6,
# two-sided p ~ 0.002. (Welch and pooled give the same here since variances
# are equal: A SD and B SD are both sqrt(8/3).)
A = [2.0, 4.0, 4.0, 6.0]
B = [8.0, 10.0, 10.0, 12.0]


def test_ttest_matches_scipy():
    analysis = TTestAnalysis()
    df = _df(A, B)
    result = analysis.run(
        df, {"alpha": 0.05, "equal_var": False, "tail": "two-sided"},
        {"outcome": "value", "group": "group"}, _ctx(),
    )
    a = np.asarray(A)
    b = np.asarray(B)
    ref_t, ref_p = stats.ttest_ind(a, b, equal_var=False)
    table = result.tables["Independent-samples t-test"]
    got_t = float(table.loc[table["Item"] == "t statistic", "Value"].iloc[0])
    got_p = float(table.loc[table["Item"] == "p-value", "Value"].iloc[0])
    assert got_t == pytest.approx(ref_t, abs=1e-4)
    assert got_p == pytest.approx(ref_p, abs=1e-4)
    # Hand-computed magnitude: |t| = 5.196, df ~ 6. The sign depends on which
    # group is listed first, so compare absolute value.
    assert abs(got_t) == pytest.approx(5.1962, abs=0.01)
    df_used = float(table.loc[table["Item"] == "degrees of freedom", "Value"].iloc[0])
    assert df_used == pytest.approx(6.0, abs=0.02)


def test_ttest_pooled_matches_scipy():
    analysis = TTestAnalysis()
    df = _df(A, B)
    result = analysis.run(
        df, {"alpha": 0.05, "equal_var": True, "tail": "two-sided"},
        {"outcome": "value", "group": "group"}, _ctx(),
    )
    ref_t, ref_p = stats.ttest_ind(np.asarray(A), np.asarray(B), equal_var=True)
    table = result.tables["Independent-samples t-test"]
    got_t = float(table.loc[table["Item"] == "t statistic", "Value"].iloc[0])
    assert got_t == pytest.approx(ref_t, abs=1e-4)
    assert abs(got_t) == pytest.approx(5.1962, abs=0.01)


def test_ttest_group_means_and_cohens_d():
    analysis = TTestAnalysis()
    df = _df(A, B)
    result = analysis.run(
        df, {"alpha": 0.05, "equal_var": False, "tail": "two-sided"},
        {"outcome": "value", "group": "group"}, _ctx(),
    )
    gs = result.tables["Group statistics"]
    means = {row["Group"]: row["Mean"] for _, row in gs.iterrows()}
    assert means["A"] == pytest.approx(4.0, abs=1e-4)
    assert means["B"] == pytest.approx(10.0, abs=1e-4)
    # Cohen's d = (10-4)/sqrt(8/3) = 3.674 (sign depends on group order).
    res = result.tables["Independent-samples t-test"]
    d = float(res.loc[res["Item"] == "Cohen's d (effect size)", "Value"].iloc[0])
    assert abs(d) == pytest.approx(3.6742, abs=0.01)
    assert res.loc[res["Item"] == "effect size label", "Value"].iloc[0] == "large"


def test_ttest_refuses_more_than_two_groups():
    analysis = TTestAnalysis()
    df = pd.DataFrame({"value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0],
                       "group": ["A", "A", "B", "B", "C", "C", "D", "D", "E"]})
    with pytest.raises(AssumptionError):
        analysis.run(
            df, {"alpha": 0.05, "equal_var": False, "tail": "two-sided"},
            {"outcome": "value", "group": "group"}, _ctx(),
        )


def test_ttest_refuses_single_group():
    analysis = TTestAnalysis()
    df = pd.DataFrame({"value": [1.0, 2.0, 3.0], "group": ["A", "A", "A"]})
    with pytest.raises(AssumptionError):
        analysis.run(
            df, {"alpha": 0.05, "equal_var": False, "tail": "two-sided"},
            {"outcome": "value", "group": "group"}, _ctx(),
        )


def test_ttest_refuses_non_numeric_outcome_with_text():
    analysis = TTestAnalysis()
    df = pd.DataFrame({
        "value": ["1", "2", "three", "4", "5", "6"],
        "group": ["A", "A", "A", "B", "B", "B"],
    })
    with pytest.raises(AssumptionError):
        analysis.run(
            df, {"alpha": 0.05, "equal_var": False, "tail": "two-sided"},
            {"outcome": "value", "group": "group"}, _ctx(),
        )


def test_ttest_handles_missing_without_imputation():
    analysis = TTestAnalysis()
    a = [2.0, 4.0, 4.0, 6.0]
    b = [8.0, 10.0, 10.0, 12.0]
    df = _df(a, b)
    # Drop 2 rows (one per group) via a missing value in the outcome.
    df.iloc[0, df.columns.get_loc("value")] = np.nan
    df.iloc[-1, df.columns.get_loc("value")] = np.nan  # the very last row (group B)
    result = analysis.run(
        df, {"alpha": 0.05, "equal_var": False, "tail": "two-sided"},
        {"outcome": "value", "group": "group"}, _ctx(),
    )
    # 2 rows excluded with a warning, none imputed: group n = 3 and 3.
    gs = result.tables["Group statistics"].set_index("Group")
    assert int(gs.loc["A", "n"]) == 3
    assert int(gs.loc["B", "n"]) == 3
    assert any("row(s)" in w and "missing" in w for w in result.warnings)


def test_ttest_three_missing_ensure_reported():
    """Missingness in the group column is also excluded and counted."""
    analysis = TTestAnalysis()
    a = [2.0, 4.0, 4.0, 6.0]
    b = [8.0, 10.0, 10.0, 12.0]
    df = _df(a, b)
    df.loc[0, "group"] = np.nan
    result = analysis.run(
        df, {"alpha": 0.05, "equal_var": False, "tail": "two-sided"},
        {"outcome": "value", "group": "group"}, _ctx(),
    )
    gs = result.tables["Group statistics"].set_index("Group")
    assert int(gs.loc["A", "n"]) == 3
    assert int(gs.loc["B", "n"]) == 4


def test_ttest_returns_figure_and_methods():
    analysis = TTestAnalysis()
    df = _df(A, B)
    result = analysis.run(
        df, {"alpha": 0.05, "equal_var": False, "tail": "two-sided"},
        {"outcome": "value", "group": "group"}, _ctx(),
    )
    assert len(result.figures) == 1
    assert result.figures[0].name == "ttest_boxplot"
    assert len(result.methods) >= 3
    assert any("independent-samples" in m.lower() for m in result.methods)
    assert "Cohen's d" in " ".join(result.methods)
