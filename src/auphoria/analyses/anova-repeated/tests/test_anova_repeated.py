"""Tests for the repeated-measures ANOVA analysis.

Uses a small balanced synthetic dataset whose sums of squares are
hand-computable, and cross-checks the within-subjects F (and its hand-computed
partial eta-squared) against the same statsmodels AnovaRM call, which is the
documented reference library.

Hand-computed values for the balanced 6-subject x 3-time long dataset
(subjects s1..s6; times t1 -> [9, 11, 10, 12, 13, 8], t2 -> [12, 13, 14, 15,
11, 14], t3 -> [14, 17, 16, 19, 15, 18]):

  grand mean         GM = 208/18 = 11.5556
  time means         t1 = 10.5, t2 = 13.1667, t3 = 16.5
  SS_time            = 6 * sum((Mt - GM)^2)          = 976/9   = 108.4444
  SS_subject         = 3 * sum((My - GM)^2)          = 7544/360 ~ 20.9444
  SS_total           = sum((y - GM)^2)               = 154.2778
  SS_error           = SS_total - SS_time - SS_subject = 224/9  = 24.8889
  MS_time = SS_time/2 = 488/9 ;  MS_error = SS_error/10 = 224/90
  F = MS_time/MS_error = (488/9) / (224/90) = 4880/224 = 21.7857 on df(2, 10)
  partial eta-squared = SS_time / (SS_time + SS_error) = 976/1200 = 0.8133
  Mauchly W = 0.3817, chi2(2) = 4.120, p = 0.1275  (not violated)

All match statsmodels AnovaRM, so the tests assert both the hand values and
agreement with the reference implementation.
"""

from __future__ import annotations

import importlib

import numpy as np
import pandas as pd
import pytest
from scipy import stats
from statsmodels.stats.anova import AnovaRM

from auphoria.core.analysis import AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

_MODULE = importlib.import_module("auphoria.analyses.anova-repeated.analysis")
AnalysisClass = _MODULE.RepeatedMeasuresAnovaAnalysis


def _ctx() -> RunContext:
    import logging
    from pathlib import Path

    logger = logging.getLogger("auphoria_anova_repeated_test")
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
    return AnalysisClass().run(
        df,
        {"alpha": 0.05, **params},
        {"outcome": "out", "subject": "subj", "time": "time"},
        _ctx(),
    )


def _balanced_df() -> pd.DataFrame:
    """6 subjects x 3 time points in long format (hand-computable)."""
    return pd.DataFrame(
        {
            "out": [
                9.0, 11.0, 10.0, 12.0, 13.0, 8.0,   # t1
                12.0, 13.0, 14.0, 15.0, 11.0, 14.0,  # t2
                14.0, 17.0, 16.0, 19.0, 15.0, 18.0,  # t3
            ],
            "subj": ["s1", "s2", "s3", "s4", "s5", "s6"] * 3,
            "time": ["t1"] * 6 + ["t2"] * 6 + ["t3"] * 6,
        }
    )


# --------------------------------------------------------------------------
# (1) agreement with statsmodels AnovaRM (the documented reference) within 1e-4
# --------------------------------------------------------------------------
def test_matches_statsmodels_anvarm():
    df = _balanced_df()
    result = _run(df)

    ref = AnovaRM(df, "out", "subj", within=["time"]).fit()
    ref_F = float(ref.anova_table["F Value"].iloc[0])
    ref_p = float(ref.anova_table["Pr > F"].iloc[0])
    ref_dfn = int(ref.anova_table["Num DF"].iloc[0])
    ref_dfd = int(ref.anova_table["Den DF"].iloc[0])

    table = result.tables["Within-subjects ANOVA"]
    # F, p and df from the analysis match the reference within 1e-4.
    assert float(table["F"].iloc[0]) == pytest.approx(ref_F, abs=1e-4)
    assert float(table["p"].iloc[0]) == pytest.approx(ref_p, abs=1e-4)
    assert int(table["df"].iloc[0]) == ref_dfn
    assert int(table["df"].iloc[1]) == ref_dfd

    # Hand-computed partial eta-squared agrees with SS-based computation.
    eff = result.tables["Effect size"].set_index("Measure")
    ss_time = float(table["SS"].iloc[0])
    assert float(eff.loc["partial eta-squared (time effect)", "Value"]) == \
        pytest.approx(ss_time / (ss_time + float(table["SS"].iloc[1])), abs=1e-6)


# --------------------------------------------------------------------------
# (2) hand-computed values on the balanced dataset
# --------------------------------------------------------------------------
def test_hand_computed_values():
    result = _run(_balanced_df())
    table = result.tables["Within-subjects ANOVA"]

    # F = 21.7857 on df(2, 10); SS_time = 976/9; SS_error = 224/9.
    assert float(table["F"].iloc[0]) == pytest.approx(21.7857142857, abs=1e-4)
    assert float(table["SS"].iloc[0]) == pytest.approx(976.0 / 9.0, abs=1e-4)
    assert float(table["SS"].iloc[1]) == pytest.approx(224.0 / 9.0, abs=1e-4)
    assert float(table["df"].iloc[0]) == 2.0
    assert float(table["df"].iloc[1]) == 10.0
    ref_p = float(stats.f.sf(21.7857142857, 2, 10))
    assert float(table["p"].iloc[0]) == pytest.approx(ref_p, abs=1e-6)

    # Partial eta-squared = 976/1200 = 0.8133.
    eff = result.tables["Effect size"].set_index("Measure")
    assert float(eff.loc["partial eta-squared (time effect)", "Value"]) == \
        pytest.approx(976.0 / 1200.0, abs=1e-4)

    # Post-hoc t1-vs-t3 Bonferroni p matches the hand computation.
    post = result.tables["Post-hoc comparisons (Bonferroni)"]
    row = post.loc[post["Comparison"] == "t1 vs t3"].iloc[0]
    t_res = stats.ttest_rel([9.0, 11.0, 10.0, 12.0, 13.0, 8.0],
                            [14.0, 17.0, 16.0, 19.0, 15.0, 18.0])
    assert float(row["p (uncorrected)"]) == pytest.approx(
        float(t_res.pvalue), abs=1e-4)
    assert float(row["p (Bonferroni-corrected)"]) == pytest.approx(
        min(float(t_res.pvalue) * 3, 1.0), abs=1e-4)


# --------------------------------------------------------------------------
# (3) guardrails
# --------------------------------------------------------------------------
def test_refuses_less_than_two_time_points():
    df = _balanced_df()
    df = df.loc[df["time"] != "t3"].copy()  # only t1 and t? keep single time
    df = df.loc[df["time"] == "t1"].copy()  # exactly one time point
    with pytest.raises(AssumptionError, match="time point"):
        _run(df)


def test_refuses_less_than_three_subjects():
    df = _balanced_df()
    df = df.loc[df["subj"].isin(["s1", "s2"])].copy()
    with pytest.raises(AssumptionError, match="three subjects"):
        _run(df)


def test_refuses_duplicate_subject_time_cell():
    df = pd.concat([_balanced_df(), _balanced_df().iloc[:1]], ignore_index=True)
    with pytest.raises(AssumptionError, match="more than once"):
        _run(df)


def test_refuses_incomplete_subject():
    # A subject missing a time point entirely -> refused, never averaged.
    df = _balanced_df().copy()
    df = df.loc[~((df["subj"] == "s1") & (df["time"] == "t2"))].copy()
    with pytest.raises(AssumptionError, match="missing at least one time point"):
        _run(df)


def test_missing_rows_dropped_with_warning():
    # A malformed row (missing outcome) is dropped listwise with a warning,
    # and the remaining balanced design still analyses cleanly.
    df = pd.concat(
        [_balanced_df(),
         pd.DataFrame({"out": [np.nan], "subj": ["s7"], "time": ["t1"]})],
        ignore_index=True,
    )
    result = _run(df)
    assert any("row(s)" in w and "missing" in w for w in result.warnings)
    # 6 clean subjects still analysed.
    assert int(result.summaries["subjects"]) == 6


# --------------------------------------------------------------------------
# (4) returns a figure, >= 3 methods sentences, and a what_does_not_tell
# --------------------------------------------------------------------------
def test_returns_figure_methods_and_caveats():
    result = _run(_balanced_df())
    assert len(result.figures) == 1
    assert result.figures[0].name == "anova_repeated_profile"
    assert len(result.methods) >= 3
    methods_text = " ".join(result.methods)
    assert "repeated-measures ANOVA" in methods_text
    assert "partial eta-squared" in methods_text
    assert "Bonferroni" in methods_text
    assert len(result.what_does_not_tell) > 40
    # Summaries present.
    assert "time effect" in result.summaries
    assert "subjects" in result.summaries


# --------------------------------------------------------------------------
# (5) advanced-analysis behaviour: assumption verdicts + expert review
# --------------------------------------------------------------------------
def test_verdicts_and_expert_review_for_small_n():
    # 6 subjects is below the ~10 recommended minimum.
    result = _run(_balanced_df())
    levels = {v.check: v.level for v in result.verdicts}
    assert "sphericity" in levels
    assert "sample-size" in levels
    assert any("expert review" in r or "statistician" in r
               for r in result.expert_review)
    assert any("subject" in r and "review" in r for r in result.expert_review)


def test_no_expert_review_banner_in_healthy_sample():
    # 24 subjects, several clean time points -> no small-sample flag.
    rng = np.random.default_rng(0)
    rows = []
    for s in range(1, 25):
        base = 10.0 + rng.normal(0, 2.0)
        for t, effect in zip(["t1", "t2", "t3", "t4"],
                             [0.0, 0.5, 1.0, 1.5], strict=False):
            rows.append({"out": base + effect + rng.normal(0, 1.0),
                         "subj": f"s{s}", "time": t})
    result = _run(pd.DataFrame(rows))
    assert not any("below the recommended minimum" in r
                   for r in result.expert_review)
