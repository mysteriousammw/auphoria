"""Tests for the one-way ANOVA analysis.

Uses small synthetic data with known, hand-computable answers, and compares
against SciPy's reference implementation (the "documented reference"):
f_oneway for F/p, studentized_range.sf for the Tukey q-p-values, levene
for the equal-variance check.

Hand-computed values for the main dataset (three groups of 4, means 4, 10,
16, grand mean 10):
  SS_between = 4*((4-10)^2 + (10-10)^2 + (16-10)^2) = 4*(36+0+36) = 288
  SS_within  = 3 groups * variance([x], ddof=1) * (n-1) = 3 * (8/3) * 3 = 24
  SS_total   = 288 + 24 = 312
  df_between = 2, df_within = 9
  F          = (288/2) / (24/9) = 54
  eta-squared = 288 / 312 = 0.9231
"""

from __future__ import annotations

import importlib

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from auphoria.core.analysis import AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

# The analysis id contains a hyphen ('anova-oneway'), which is not valid
# Python syntax in an import statement, so load the module by name.
_ANOVA_MODULE = importlib.import_module("auphoria.analyses.anova-oneway.analysis")
AnovaOnewayAnalysis = _ANOVA_MODULE.AnovaOnewayAnalysis


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


def _df(a: list[float], b: list[float], c: list[float]) -> pd.DataFrame:
    groups = ["A"] * len(a) + ["B"] * len(b) + ["C"] * len(c)
    return pd.DataFrame({"value": a + b + c, "group": groups})


def _run(df: pd.DataFrame, **params) -> AnalysisResult:
    return AnovaOnewayAnalysis().run(
        df, {"alpha": 0.05, **params}, {"outcome": "value", "group": "group"}, _ctx()
    )


# Hand-computed textbook example (see module docstring): means 4, 10, 16;
# SS_between = 288, SS_within = 24, SS_total = 312, F = 54, eta-squared =
# 288/312 = 0.9231.
A = [2.0, 4.0, 4.0, 6.0]
B = [8.0, 10.0, 10.0, 12.0]
C = [14.0, 16.0, 16.0, 18.0]


def test_anova_matches_scipy_and_hand_values():
    result = _run(_df(A, B, C))
    ref_F, ref_p = stats.f_oneway(*[np.asarray(x, dtype=float) for x in (A, B, C)])
    table = result.tables["ANOVA table"].set_index("Source")
    # F and p exactly as SciPy's reference implementation computes them.
    assert float(table.loc["Between", "F"]) == pytest.approx(ref_F, abs=1e-6)
    assert float(table.loc["Between", "p"]) == pytest.approx(ref_p, abs=1e-6)
    assert float(table.loc["Between", "df"]) == pytest.approx(2.0, abs=1e-6)
    assert float(table.loc["Within", "df"]) == pytest.approx(9.0, abs=1e-6)
    assert float(table.loc["Total", "df"]) == pytest.approx(11.0, abs=1e-6)
    # Hand-computed sums of squares.
    assert float(table.loc["Between", "SS"]) == pytest.approx(288.0, abs=1e-4)
    assert float(table.loc["Within", "SS"]) == pytest.approx(24.0, abs=1e-4)
    assert float(table.loc["Total", "SS"]) == pytest.approx(312.0, abs=1e-4)
    # Hand-computed effect size: 288 / 312.
    es = result.tables["Effect size"].set_index("Measure")
    eta = float(es.loc["eta-squared (SS_between / SS_total)", "Value"])
    assert eta == pytest.approx(288.0 / 312.0, abs=1e-4)
    assert eta == pytest.approx(0.9231, abs=1e-4)


def test_anova_group_statistics():
    result = _run(_df(A, B, C))
    gs = result.tables["Group statistics"].set_index("Group")
    assert int(gs.loc["A", "n"]) == 4
    assert int(gs.loc["B", "n"]) == 4
    assert int(gs.loc["C", "n"]) == 4
    assert float(gs.loc["A", "Mean"]) == pytest.approx(4.0, abs=1e-4)
    assert float(gs.loc["B", "Mean"]) == pytest.approx(10.0, abs=1e-4)
    assert float(gs.loc["C", "Mean"]) == pytest.approx(16.0, abs=1e-4)
    # Each group has variance (ddof=1) = 8/3, so SD = sqrt(8/3) = 1.6330.
    assert float(gs.loc["A", "SD"]) == pytest.approx(np.sqrt(8 / 3), abs=1e-4)
    assert float(gs.loc["B", "SD"]) == pytest.approx(np.sqrt(8 / 3), abs=1e-4)
    assert float(gs.loc["C", "SD"]) == pytest.approx(np.sqrt(8 / 3), abs=1e-4)


def test_anova_tukey_posthoc():
    result = _run(_df(A, B, C))
    tukey = result.tables["Tukey post-hoc"]
    # 3 groups -> 3 pairs.
    assert len(tukey) == 3
    means = {"A": 4.0, "B": 10.0, "C": 16.0}
    ms_within = 24.0 / 9.0
    for _, row in tukey.iterrows():
        gi, gj = str(row["Pair"]).split(" vs ")
        diff = means[gi] - means[gj]
        q = abs(diff) / np.sqrt(ms_within * (1.0 / 4.0 + 1.0 / 4.0) / 2.0)
        ref_p = stats.studentized_range.sf(q, 3, 9)
        assert float(row["Mean difference"]) == pytest.approx(diff, abs=1e-4)
        assert float(row["q"]) == pytest.approx(q, abs=1e-6)
        assert float(row["p (Tukey)"]) == pytest.approx(ref_p, abs=1e-6)
        assert row["significant at alpha?"] == ("Yes" if ref_p < 0.05 else "No")
    # Hand value for the most different pair (A vs C): q = 12 / sqrt(2/3).
    ac = tukey.set_index("Pair").loc["A vs C"]
    assert float(ac["q"]) == pytest.approx(12.0 / np.sqrt(2.0 / 3.0), abs=1e-6)
    assert ac["significant at alpha?"] == "Yes"


def test_anova_refuses_two_groups():
    df = pd.DataFrame(
        {"value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0], "group": ["A", "A", "A", "B", "B", "B"]}
    )
    with pytest.raises(AssumptionError, match="t-test"):
        _run(df)


def test_anova_refuses_single_group():
    df = pd.DataFrame({"value": [1.0, 2.0, 3.0], "group": ["A", "A", "A"]})
    with pytest.raises(AssumptionError):
        _run(df)


def test_anova_refuses_single_observation_group():
    # Group A has only one observation.
    df = pd.DataFrame(
        {
            "value": [2.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0],
            "group": ["A", "B", "B", "B", "C", "C", "C"],
        }
    )
    with pytest.raises(AssumptionError):
        _run(df)


def test_anova_missing_dropped_with_warning():
    df = _df(A, B, C)
    df.iloc[0, df.columns.get_loc("value")] = np.nan
    df.iloc[-1, df.columns.get_loc("value")] = np.nan  # the last row (group C)
    result = _run(df)
    # 2 rows excluded with a warning, none imputed: n = 3, 4 and 3.
    gs = result.tables["Group statistics"].set_index("Group")
    assert int(gs.loc["A", "n"]) == 3
    assert int(gs.loc["B", "n"]) == 4
    assert int(gs.loc["C", "n"]) == 3
    assert any("row(s)" in w and "missing" in w for w in result.warnings)


def test_anova_levene_warn_does_not_refuse():
    # Group spreads differ hugely: tight constant groups vs one wide group.
    wide = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0]
    df = _df([5.0] * 8, wide, [10.0] * 8)
    # Sanity: Levene really is significant on this deterministic data.
    ref_p = stats.levene(
        np.full(8, 5.0), np.asarray(wide, dtype=float), np.full(8, 10.0)
    ).pvalue
    assert ref_p < 0.05
    result = _run(df)
    levels = {v.check: v.level for v in result.verdicts}
    assert levels["equal-variances"] == "WARN"
    assert any("Kruskal-Wallis" in w for w in result.warnings)
    # The analysis still ran and reported the ANOVA.
    assert "ANOVA table" in result.tables


def test_anova_normality_warn_does_not_refuse():
    # One heavily skewed group (outlier 90) fails Shapiro-Wilk.
    skewed = [1.0, 1.0, 1.0, 2.0, 2.0, 3.0, 4.0, 90.0]
    df = _df([2.0, 4.0, 4.0, 6.0], [8.0, 10.0, 10.0, 12.0], skewed)
    # Sanity: Shapiro-Wilk really rejects the skewed group.
    assert stats.shapiro(np.asarray(skewed)).pvalue < 0.05
    result = _run(df)
    levels = {v.check: v.level for v in result.verdicts}
    assert levels["normality"] == "WARN"
    assert any("Kruskal-Wallis" in w for w in result.warnings)
    assert "ANOVA table" in result.tables


def test_anova_figure_methods_and_summaries():
    result = _run(_df(A, B, C))
    assert len(result.figures) == 1
    assert result.figures[0].name == "anova_boxplots"
    assert len(result.methods) >= 3
    methods_text = " ".join(result.methods)
    assert "ANOVA" in methods_text
    assert "F(2, 9)" in methods_text
    assert "eta-squared" in methods_text
    assert "Yes" in result.summaries["significant at alpha"]
    assert "A vs C" in result.summaries["most different groups"]
    assert result.summaries["p-value"] == "< 0.001"
