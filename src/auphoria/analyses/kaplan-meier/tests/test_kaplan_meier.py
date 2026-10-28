"""Tests for the Kaplan-Meier survival analysis.

Uses small synthetic survival data with hand-computable answers, and compares
against statsmodels' SurvfuncRight as the documented reference.

Hand-computed values:
- Tiny single-curve dataset times [2, 3, 5, 6], events [1, 1, 0, 1]:
    S(2) = 1 - 1/4 = 0.75
    S(3) = 0.75 * (1 - 1/3) = 0.50
    S(5) = no event (censored), S unchanged = 0.50
    S(6) = 0.50 * (1 - 1/1) = 0.00
    -> survival times [2, 3, 6] with probabilities [0.75, 0.50, 0.00].
- Hand log-rank (two groups A=[1,2], B=[3,4], all events). At each event time
  the observed-minus-expected and hypergeometric variance for group A:
    t=1: E = 2/4 = 0.5,    V = 2*2*1*3/(16*3)   = 0.25
    t=2: E = 1/3,          V = 1*2*1*2/(9*2)    = 2/9
    t=3,4: A no longer at risk -> contribution 0.
    S_A = 2 - (0.5 + 1/3) = 7/6
    V_A = 0.25 + 2/9 = 17/36
    chi2 = (7/6)^2 / (17/36) = 147/51 = 2.8823529
    p    = scipy chi2.sf(2.8823529, 1) = 0.089555
"""

from __future__ import annotations

import importlib
import re

import numpy as np
import pandas as pd
import pytest
from scipy import stats
from statsmodels.duration.survfunc import SurvfuncRight

from auphoria.core.analysis import AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

# The analysis id contains a hyphen ('kaplan-meier'), which is not valid
# Python syntax in an import statement, so load the module by name.
_KM_MODULE = importlib.import_module("auphoria.analyses.kaplan-meier.analysis")
KaplanMeierAnalysis = _KM_MODULE.KaplanMeierAnalysis


def _ctx() -> RunContext:
    import logging

    logger = logging.getLogger("auphoria_test_km")
    logger.handlers = []
    return RunContext(
        seed=1,
        out_dir=__import__("pathlib").Path("."),
        data_name="test",
        expert=False,
        _log=logger,
        _log_decision=lambda m: None,
    )


def _run(df: pd.DataFrame, **params) -> AnalysisResult:
    return KaplanMeierAnalysis().run(
        df,
        {"alpha": 0.05, **params},
        {"time": "time", "event": "event", "group": "group"},
        _ctx(),
    )


# Primary dataset with two groups, both reaching their median with modest
# censoring. Group A: times [5,10,20,25] events (censored at 15,30,35).
# Group B: times [3,6,9,12,18,21,27] events (censored at 15,24,30).
PRIMARY = pd.DataFrame(
    {
        "time": [5, 10, 15, 20, 25, 30, 35, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30],
        "event": [1, 1, 0, 1, 1, 0, 0, 1, 1, 1, 1, 0, 1, 1, 0, 1, 0],
        "group": ["A"] * 7 + ["B"] * 10,
    }
)


def _group_table(result: AnalysisResult, group: str) -> pd.DataFrame:
    return result.tables[f"Survival table: {group}"]


def test_survival_probabilities_match_statsmodels():
    result = _run(PRIMARY)
    for g in ("A", "B"):
        mask = PRIMARY["group"] == g
        ref = SurvfuncRight(
            PRIMARY.loc[mask, "time"].to_numpy(dtype=float),
            PRIMARY.loc[mask, "event"].to_numpy(dtype=float),
        )
        tab = _group_table(result, g)
        assert tab["time"].to_numpy() == pytest.approx(
            np.asarray(ref.surv_times), abs=1e-6
        )
        assert tab["survival probability"].to_numpy() == pytest.approx(
            np.asarray(ref.surv_prob), abs=1e-4
        )
        assert tab["at-risk n"].to_numpy().astype(int).tolist() == [
            int(x) for x in ref.n_risk
        ]
        assert tab["events"].to_numpy().tolist() == [int(e) for e in ref.n_events]


def test_hand_computed_survival_curve():
    # Group A is the tiny hand-computed dataset; group B provides the required
    # second group with events so the module runs.
    df = pd.DataFrame(
        {
            "time": [2, 3, 5, 6,  4, 8, 12],
            "event": [1, 1, 0, 1,  1, 1, 1],
            "group": ["A", "A", "A", "A", "B", "B", "B"],
        }
    )
    result = _run(df)
    tab = _group_table(result, "A")
    # Hand values: times [2, 3, 6], S = [0.75, 0.50, 0.00] (time 5 is censored).
    assert tab["time"].to_numpy().tolist() == [2.0, 3.0, 6.0]
    assert tab["survival probability"].to_numpy() == pytest.approx(
        [0.75, 0.50, 0.00], abs=1e-4
    )


def test_median_survival_matches_statsmodels():
    result = _run(PRIMARY)
    for g in ("A", "B"):
        mask = PRIMARY["group"] == g
        ref = SurvfuncRight(
            PRIMARY.loc[mask, "time"].to_numpy(dtype=float),
            PRIMARY.loc[mask, "event"].to_numpy(dtype=float),
        )
        ref_med = ref.quantile(0.5)
        # Medians are named in the plain-English summary as "A: 25.00, B: ...".
        m = re.search(rf"\b{g}:\s+([0-9.]+|not reached)", result.summaries["median survival"])
        assert m is not None
        if np.isnan(ref_med) or np.isinf(ref_med):
            assert m.group(1) == "not reached"
        else:
            assert float(m.group(1)) == pytest.approx(ref_med, abs=1e-4)


def test_log_rank_hand_computed_reference():
    # Two groups, all events: A=[1,2], B=[3,4]. Hand chi2 = 2.8823529.
    df = pd.DataFrame(
        {
            "time": [1, 2, 3, 4],
            "event": [1, 1, 1, 1],
            "group": ["A", "A", "B", "B"],
        }
    )
    result = _run(df)
    lr = result.tables["Log-rank test"].set_index("Measure")
    chi2 = float(lr.loc["log-rank chi-squared", "Value"])
    p = float(lr.loc["log-rank p-value", "Value"])
    # Hand-computed chi-squared and its p-value.
    assert chi2 == pytest.approx(147 / 51, abs=1e-5)
    assert p == pytest.approx(0.08955507441364274, abs=1e-5)
    assert p == pytest.approx(stats.chi2.sf(147 / 51, 1), abs=1e-9)
    assert float(lr.loc["degrees of freedom", "Value"]) == 1.0


def test_log_rank_matches_hand_accumulated_reference():
    # Check the primary dataset against a fresh hand accumulation of the
    # standard two-sample log-rank statistic (observed minus expected over V).
    result = _run(PRIMARY)
    t = PRIMARY["time"].to_numpy(dtype=float)
    e = PRIMARY["event"].to_numpy(dtype=float)
    g = PRIMARY["group"].to_numpy()
    grp0 = "A"
    S, V = 0.0, 0.0
    for tj in np.unique(t[e == 1]):
        atrisk = t >= tj
        n_total = int(atrisk.sum())
        d_total = int(((t == tj) & (e == 1)).sum())
        n0 = int((atrisk & (g == grp0)).sum())
        d0 = int(((t == tj) & (e == 1) & (g == grp0)).sum())
        S += d0 - n0 * d_total / n_total
        V += n0 * (n_total - n0) * d_total * (n_total - d_total) / (
            n_total * n_total * (n_total - 1)
        )
    ref_chi2 = S**2 / V
    ref_p = stats.chi2.sf(ref_chi2, 1)
    lr = result.tables["Log-rank test"].set_index("Measure")
    assert float(lr.loc["log-rank chi-squared", "Value"]) == pytest.approx(
        ref_chi2, abs=1e-6
    )
    assert float(lr.loc["log-rank p-value", "Value"]) == pytest.approx(
        ref_p, abs=1e-12
    )


def test_refuses_event_not_0_1():
    df = PRIMARY.copy()
    df.loc[0, "event"] = 2
    with pytest.raises(AssumptionError, match="only contain 0"):
        _run(df)


def test_refuses_single_category_group():
    df = PRIMARY.copy()
    df["group"] = "A"
    with pytest.raises(AssumptionError, match="only 1 distinct"):
        _run(df)


def test_refuses_negative_time():
    df = PRIMARY.copy()
    df.loc[0, "time"] = -3.0
    with pytest.raises(AssumptionError, match="negative"):
        _run(df)


def test_refuses_group_with_no_events():
    df = PRIMARY.copy()
    # Group C has rows but all censored.
    df = pd.concat(
        [df, pd.DataFrame({"time": [1, 2], "event": [0, 0], "group": ["C", "C"]})],
        ignore_index=True,
    )
    with pytest.raises(AssumptionError, match="no observed events"):
        _run(df)


def test_missing_values_listwise_with_warning():
    df = PRIMARY.copy()
    # Remove the row at index 15 (group B event) by NA-ing its time, and an
    # index-0 (group A event) row too.
    df.loc[15, "time"] = np.nan
    df.loc[0, "event"] = np.nan
    result = _run(df)
    # 2 rows excluded with a warning, none imputed; remaining n still > 1 group.
    assert any("row(s)" in w and "missing" in w for w in result.warnings)
    # The saved curves must reflect the reduced sample, e.g. group B lost its
    # t=27 row: its survival table's last time is now 21.
    tabB = _group_table(result, "B")
    assert 27.0 not in tabB["time"].to_numpy()


def test_figure_methods_and_what_does_not_tell():
    result = _run(PRIMARY)
    assert len(result.figures) == 1
    assert result.figures[0].name == "kaplan_meier_curves"
    assert len(result.methods) >= 3
    methods_text = " ".join(result.methods)
    assert "Kaplan-Meier" in methods_text
    assert "log-rank" in methods_text
    assert "median" in methods_text.lower()
    assert result.what_does_not_tell
    assert "censoring" in result.what_does_not_tell
    # Verdicts for the events-per-group and censoring checks exist.
    checks = {v.check for v in result.verdicts}
    assert "events-per-group" in checks
    assert "censoring" in checks


def test_expert_review_when_underpowered():
    # Small n and a group with very few events triggers expert-review banners.
    df = pd.DataFrame(
        {
            "time": [2, 4, 6, 8, 10, 12, 14, 16],
            "event": [1, 1, 1, 1, 1, 1, 0, 0],
            "group": ["A", "A", "A", "A", "B", "B", "B", "B"],
        }
    )
    result = _run(df)
    assert result.expert_review, "expected expert-review banner for small sample"


def test_heavy_censoring_warns():
    # 70%+ censoring overall on a two-group dataset.
    df = pd.DataFrame(
        {
            "time": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10,  1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "event": [1, 1, 0, 0, 0, 0, 0, 0, 0, 0,  1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
            "group": ["A"] * 10 + ["B"] * 10,
        }
    )
    result = _run(df)
    levels = {v.check: v.level for v in result.verdicts}
    assert levels["censoring"] == "WARN"
    assert any("% censored" in w or "censored" in w for w in result.warnings)
