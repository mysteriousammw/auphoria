"""Tests for the Friedman test analysis.

Uses small synthetic data with known, hand-computable answers, and compares
against SciPy's reference implementation (the "documented reference").

Hand-computed example: 3 time points x 6 subjects where each subject ranks
the three times 1, 2, 3:
  t1 = [1, 2, 3, 4, 5, 6]
  t2 = [2, 3, 4, 5, 6, 7]
  t3 = [3, 4, 5, 6, 7, 8]
Within every subject the ranks are (1, 2, 3), so R1 = R2 = ... = 6*1 = 6,
R2-col sums 12, R3-col sums 18.  k = 3 times, n = 6 subjects.

chi2 = 12/(k*n*(k+1)) * sum(Rj^2/n) - 3*n*(k+1)
     = 12/(3*6*4) * (72 + 288 + 648) - 3*6*4
     = 12/72 * 1008 - 72
     = 168 - 72
     = 12
df = k - 1 = 2.

Every pair of columns differs by exactly 1 in each subject, so each Wilcoxon
signed-rank on a pair gives p = 0.03125 (from 6 even signs); with k = 3 times
there are 3 comparisons, so the Bonferroni-corrected p = min(1, 0.03125*3) =
0.09375.
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

# The folder name contains no hyphen-friendly import, but we still load the
# module by string the way the registry does (stable across analysis ids).
_analysis_module = importlib.import_module(
    "auphoria.analyses.friedman.analysis"
)
FriedmanAnalysis = _analysis_module.FriedmanAnalysis


def _ctx() -> RunContext:
    logger = logging.getLogger("auphoria_test_friedman")
    logger.handlers = []
    return RunContext(
        seed=1,
        out_dir=Path("."),
        data_name="test",
        expert=False,
        _log=logger,
        _log_decision=lambda m: None,
    )


# Hand-computed example: each subject ranks the three times 1, 2, 3.
T1 = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
T2 = [2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
T3 = [3.0, 4.0, 5.0, 6.0, 7.0, 8.0]


def _long(
    *cols: list[float],
    times: list[str] | None = None,
    drop_subject: int | None = None,
    drop_cell: tuple[int, int] | None = None,
) -> pd.DataFrame:
    """Build a LONG-format frame: one row per (subject, time) pair."""
    k = len(cols)
    tnames = times or ["t1", "t2", "t3"][:k]
    n = len(cols[0])
    ts: list[float] = []
    subj: list[str] = []
    tp: list[str] = []
    for s in range(n):
        if drop_subject is not None and s == drop_subject:
            continue
        for c in range(k):
            val = float(cols[c][s])
            if drop_cell is not None and (s, c) == drop_cell:
                val = np.nan
            ts.append(val)
            subj.append(f"s{s + 1}")
            tp.append(tnames[c])
    return pd.DataFrame(
        {"outcome": ts, "subject": subj, "time": tp}
    )


def test_friedman_matches_scipy() -> None:
    analysis = FriedmanAnalysis()
    df = _long(T1, T2, T3)
    result = analysis.run(
        df, {"alpha": 0.05},
        {"outcome": "outcome", "subject": "subject", "time": "time"}, _ctx(),
    )
    ref = stats.friedmanchisquare(
        np.asarray(T1), np.asarray(T2), np.asarray(T3)
    )
    table = result.tables["Friedman test"]
    got_chi2 = float(
        table.loc[table["Item"] == "chi2 (Friedman statistic)", "Value"].iloc[0]
    )
    got_p = float(table.loc[table["Item"] == "p-value", "Value"].iloc[0])
    got_df = int(
        table.loc[table["Item"] == "degrees of freedom (df)", "Value"].iloc[0]
    )
    # Cross-check against SciPy's reference implementation.
    assert got_chi2 == pytest.approx(float(ref.statistic), abs=1e-4)
    assert got_p == pytest.approx(float(ref.pvalue), abs=1e-4)
    # Hand-computed values: chi2 = 12, df = k - 1 = 2.
    assert got_chi2 == pytest.approx(12.0, abs=1e-4)
    assert got_df == 2


def test_friedman_bonferroni_posthoc_corrected() -> None:
    """Corrected p = raw p * #comparisons, capped at 1."""
    analysis = FriedmanAnalysis()
    df = _long(T1, T2, T3)
    result = analysis.run(
        df, {"alpha": 0.05},
        {"outcome": "outcome", "subject": "subject", "time": "time"}, _ctx(),
    )
    ph = result.tables["Pairwise comparisons"]
    n_comp = 3
    for _, row in ph.iterrows():
        raw = float(row["raw p"])
        corr = float(row["Bonferroni p"])
        assert corr == pytest.approx(min(1.0, raw * n_comp), abs=1e-6)
        assert 0.0 <= corr <= 1.0


def test_friedman_descriptives_and_test_table() -> None:
    analysis = FriedmanAnalysis()
    df = _long(T1, T2, T3)
    result = analysis.run(
        df, {"alpha": 0.05},
        {"outcome": "outcome", "subject": "subject", "time": "time"}, _ctx(),
    )
    desc = result.tables["Descriptives by time"].set_index("Time")
    assert int(desc.loc["t1", "n"]) == 6
    # Median of [1..6] = 3.5; IQR (P75-P25, linear interp) = 4.75 - 2.25 = 2.5.
    assert float(desc.loc["t1", "Median"]) == pytest.approx(3.5, abs=1e-4)
    assert float(desc.loc["t1", "IQR"]) == pytest.approx(2.5, abs=1e-4)
    table = result.tables["Friedman test"]
    assert int(table.loc[table["Item"] == "n (subjects)", "Value"].iloc[0]) == 6
    assert (
        int(table.loc[table["Item"] == "number of time points", "Value"].iloc[0])
        == 3
    )
    assert (
        table.loc[table["Item"] == "test", "Value"].iloc[0] == "Friedman test"
    )
    # chi2 = 12, p < 0.05 -> significant.
    assert (
        table.loc[table["Item"] == "significant at alpha?", "Value"].iloc[0]
        == "Yes"
    )


def test_friedman_refuses_less_than_two_times() -> None:
    analysis = FriedmanAnalysis()
    df = pd.DataFrame(
        {"outcome": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
         "subject": ["s1", "s2", "s3", "s4", "s5", "s6"],
         "time": ["t1"] * 6}
    )
    with pytest.raises(AssumptionError):
        analysis.run(
            df, {"alpha": 0.05},
            {"outcome": "outcome", "subject": "subject", "time": "time"}, _ctx(),
        )


def test_friedman_refuses_less_than_three_subjects() -> None:
    analysis = FriedmanAnalysis()
    df = pd.DataFrame(
        {"outcome": [1.0, 2.0, 3.0, 1.5, 2.5, 3.5],
         "subject": ["s1", "s1", "s1", "s2", "s2", "s2"],
         "time": ["t1", "t2", "t3"] * 2}
    )
    with pytest.raises(AssumptionError):
        analysis.run(
            df, {"alpha": 0.05},
            {"outcome": "outcome", "subject": "subject", "time": "time"}, _ctx(),
        )


def test_friedman_incomplete_subject_dropped_with_warning() -> None:
    """A subject missing ANY time cell cannot form a block and is dropped."""
    analysis = FriedmanAnalysis()
    # Drop subject s6 entirely and knock out one cell of subject s5.
    df = _long(T1, T2, T3, drop_subject=5, drop_cell=(4, 2))
    result = analysis.run(
        df, {"alpha": 0.05},
        {"outcome": "outcome", "subject": "subject", "time": "time"}, _ctx(),
    )
    # 4 complete subjects remain (s1..s4).
    table = result.tables["Friedman test"]
    assert int(table.loc[table["Item"] == "n (subjects)", "Value"].iloc[0]) == 4
    assert any("subject" in w and "missing" in w for w in result.warnings)
    assert any("excluded" in m and "imputed" in m for m in result.methods)


def test_friedman_less_than_four_complete_subjects_refused() -> None:
    analysis = FriedmanAnalysis()
    # Only 3 subjects total -> refused even before completeness is considered.
    small = pd.DataFrame(
        {"outcome": [1.0, 2.0, 3.0, 2.0, 3.0, 4.0, 3.0, 4.0, 5.0],
         "subject": ["s1"] * 3 + ["s2"] * 3 + ["s3"] * 3,
         "time": ["t1", "t2", "t3"] * 3}
    )
    with pytest.raises(AssumptionError):
        analysis.run(
            small, {"alpha": 0.05},
            {"outcome": "outcome", "subject": "subject", "time": "time"}, _ctx(),
        )


def test_friedman_small_sample_adds_expert_review() -> None:
    analysis = FriedmanAnalysis()
    # 4 complete subjects (< 6) -> expert review flag.
    df = _long(T1[:4], T2[:4], T3[:4])
    result = analysis.run(
        df, {"alpha": 0.05},
        {"outcome": "outcome", "subject": "subject", "time": "time"}, _ctx(),
    )
    assert result.expert_review, "expected an expert-review reason for n < 6"
    assert any("4" in e for e in result.expert_review)


def test_friedman_figure_methods_and_honest_limits() -> None:
    analysis = FriedmanAnalysis()
    df = _long(T1, T2, T3)
    result = analysis.run(
        df, {"alpha": 0.05},
        {"outcome": "outcome", "subject": "subject", "time": "time"}, _ctx(),
    )
    assert len(result.figures) == 1
    assert result.figures[0].name == "friedman_by_time"
    assert len(result.methods) >= 3
    assert any("friedman" in m.lower() for m in result.methods)
    # Honest limits: the result does not say which times differ.
    assert result.what_does_not_tell
    assert "which" in result.what_does_not_tell.lower()
    assert "post-hoc" in result.what_does_not_tell.lower() or \
        "pairwise" in result.what_does_not_tell.lower()


def test_friedman_check_fit_refuses_nonnumeric_time() -> None:
    analysis = FriedmanAnalysis()

    class _Col:
        def __init__(self, kind: str) -> None:
            self.kind = kind

    class _Profile:
        def by_name(self, name: str):
            del name
            return _Col("numeric")

    refusals = analysis.check_fit(
        _Profile(),
        {"alpha": 0.05},
        {"outcome": "outcome", "subject": "subject", "time": "time"},
    )
    assert refusals
    assert any("time" in r for r in refusals)
