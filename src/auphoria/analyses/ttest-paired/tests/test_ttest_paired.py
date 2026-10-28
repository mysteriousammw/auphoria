"""Tests for the paired-samples t-test analysis.

Uses small synthetic data with known, hand-computable answers, and compares
against SciPy's reference implementation (the "documented reference").

The analysis folder is 'ttest-paired' (hyphenated, like the registry id), so
the module is loaded with importlib the same way the registry loads it.
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

# Hyphenated module names cannot use the `import` statement; importlib is how
# auphoria.core.registry.load_analysis loads this module at runtime.
_PAIRED_MODULE = importlib.import_module("auphoria.analyses.ttest-paired.analysis")
PairedTTestAnalysis = _PAIRED_MODULE.PairedTTestAnalysis


def _ctx() -> RunContext:
    logger = logging.getLogger("auphoria_test_paired")
    logger.handlers = []
    return RunContext(
        seed=1,
        out_dir=Path("."),
        data_name="test",
        expert=False,
        _log=logger,
        _log_decision=lambda m: None,
    )


def _df(before: list[float], after: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"before": before, "after": after})


# Hand-computed textbook example: differences 4, 3, 2, 3, 2 -> mean 2.8,
# sample SD = sqrt(0.7) = 0.83666, Cohen's d_z = 2.8 / 0.83666 = 3.3466,
# t = 2.8 / (0.83666 / sqrt(5)) = 7.4833, df = 4, two-sided p = 0.0017.
BEFORE = [20.0, 22.0, 21.0, 23.0, 22.0]
AFTER = [24.0, 25.0, 23.0, 26.0, 24.0]


def test_ttest_paired_matches_scipy():
    analysis = PairedTTestAnalysis()
    df = _df(BEFORE, AFTER)
    result = analysis.run(
        df, {"alpha": 0.05}, {"before": "before", "after": "after"}, _ctx()
    )
    ref_t, ref_p = stats.ttest_rel(np.asarray(AFTER), np.asarray(BEFORE))
    table = result.tables["Paired-samples t-test"]
    got_t = float(table.loc[table["Item"] == "t statistic", "Value"].iloc[0])
    got_p = float(table.loc[table["Item"] == "p-value", "Value"].iloc[0])
    # t is stored with 6 decimals; p passes through fmt_p (3 decimals).
    assert got_t == pytest.approx(ref_t, abs=1e-4)
    assert got_p == pytest.approx(ref_p, abs=1e-3)
    # Hand-computed magnitudes straight from the given data.
    assert got_t == pytest.approx(7.4833, abs=0.001)
    assert ref_p == pytest.approx(0.0017, abs=0.0001)
    df_used = float(table.loc[table["Item"] == "degrees of freedom", "Value"].iloc[0])
    assert df_used == pytest.approx(4.0, abs=0.02)


def test_ttest_paired_mean_diff_and_cohens_dz():
    analysis = PairedTTestAnalysis()
    df = _df(BEFORE, AFTER)
    result = analysis.run(
        df, {"alpha": 0.05}, {"before": "before", "after": "after"}, _ctx()
    )
    ps = result.tables["Paired statistics"]
    # Mean difference = 2.8 and SD of differences = sqrt(0.7) ~ 0.8367.
    assert float(ps.loc[0, "Mean difference"]) == pytest.approx(2.8, abs=1e-4)
    assert float(ps.loc[0, "SD of differences"]) == pytest.approx(0.8367, abs=1e-3)
    assert int(ps.loc[0, "n"]) == 5
    # Cohen's d_z = 2.8 / 0.83666 = 3.3466.
    res = result.tables["Paired-samples t-test"]
    d_z = float(res.loc[res["Item"] == "Cohen's d_z (effect size)", "Value"].iloc[0])
    assert d_z == pytest.approx(3.3466, abs=0.01)
    assert result.summaries["Cohen's d_z"] == "3.35"


def test_ttest_paired_refuses_constant_differences():
    analysis = PairedTTestAnalysis()
    # Identical columns: every difference is 0, t is undefined.
    df_same = _df(BEFORE, BEFORE)
    with pytest.raises(AssumptionError):
        analysis.run(
            df_same, {"alpha": 0.05},
            {"before": "before", "after": "after"}, _ctx(),
        )
    # Constant NON-zero difference is equally undefined (SD of differences 0).
    df_const = _df([1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0])
    with pytest.raises(AssumptionError):
        analysis.run(
            df_const, {"alpha": 0.05},
            {"before": "before", "after": "after"}, _ctx(),
        )


def test_ttest_paired_handles_missing_without_imputation():
    analysis = PairedTTestAnalysis()
    df = _df(BEFORE, AFTER)
    df.loc[0, "before"] = np.nan  # one missing pair excluded, never imputed
    result = analysis.run(
        df, {"alpha": 0.05}, {"before": "before", "after": "after"}, _ctx()
    )
    ps = result.tables["Paired statistics"]
    assert int(ps.loc[0, "n"]) == 4
    assert any("row(s)" in w and "missing" in w for w in result.warnings)
    assert any("no missing values were imputed" in m for m in result.methods)


def test_ttest_paired_refuses_fewer_than_two_complete_pairs():
    analysis = PairedTTestAnalysis()
    # Only row 2 is complete -> 1 pair left after listwise deletion.
    df = pd.DataFrame({
        "before": [1.0, np.nan, 3.0],
        "after": [np.nan, 2.0, 4.0],
    })
    with pytest.raises(AssumptionError):
        analysis.run(
            df, {"alpha": 0.05}, {"before": "before", "after": "after"}, _ctx()
        )


def test_ttest_paired_shapiro_path_on_small_valid_data():
    """n = 5: Shapiro runs, the small-sample caution is added, no crash."""
    analysis = PairedTTestAnalysis()
    df = _df(BEFORE, AFTER)
    result = analysis.run(
        df, {"alpha": 0.05}, {"before": "before", "after": "after"}, _ctx()
    )
    assert result.summaries["significant at alpha"] == "0.050 → Yes"
    assert any("pair(s)" in w and "preliminary" in w for w in result.warnings)


def test_ttest_paired_returns_figure_and_methods():
    analysis = PairedTTestAnalysis()
    df = _df(BEFORE, AFTER)
    result = analysis.run(
        df, {"alpha": 0.05}, {"before": "before", "after": "after"}, _ctx()
    )
    assert len(result.figures) == 1
    assert result.figures[0].name == "ttest_paired_lines"
    assert len(result.methods) >= 3
    assert any("paired-samples" in m.lower() for m in result.methods)
    assert "Cohen's d_z" in " ".join(result.methods)
    # Honest caveat must be present.
    assert "does not prove the treatment caused" in result.what_does_not_tell
