"""Tests for the Cronbach's alpha analysis.

Uses small deterministic synthetic data. The overall alpha is checked against
a hand-computed textbook value, and the standardised alpha against the
hand-computed perfect-correlation case. The guardrails (refusing fewer than
two items, dropping missing rows listwise without imputing), the
interpretation, the per-item table and the honest what-does-not-tell note are
also exercised.
"""

from __future__ import annotations

import importlib

import numpy as np
import pandas as pd
import pytest

from auphoria.core.analysis import AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

# The analysis id contains a hyphen ('cronbach-alpha'), which is not valid
# Python syntax in an import statement, so load the module by name.
_MODULE = importlib.import_module("auphoria.analyses.cronbach-alpha.analysis")
CronbachAlphaAnalysis = _MODULE.CronbachAlphaAnalysis
_interpretation = _MODULE._interpretation


def _ctx() -> RunContext:
    import logging
    from pathlib import Path

    logger = logging.getLogger("auphoria_cronbach_test")
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
    return CronbachAlphaAnalysis().run(df, {"acceptable_threshold": 0.7, **params}, {}, _ctx())


# Hand-computed reference:
#   x1 = [1,2,3,4,5], x2 = 2*x1+1 = [3,5,7,9,11], x3 = [2,4,6,8,10]; k = 3.
#   Population item variances: x1 = 2, x2 = 8, x3 = 8 -> sum = 18.
#   Row sums [6,11,16,21,26]; their population variance = 50.
#   alpha = (3/2)*(1 - 18/50) = 1.5 * 0.64 = 0.96.
#   Standardising each item makes all three columns identical (perfectly
#   correlated), so the standardised alpha is 1.0.
def _perfect_df() -> pd.DataFrame:
    x1 = [1, 2, 3, 4, 5]
    x2 = [v * 2 + 1 for v in x1]
    x3 = [2, 4, 6, 8, 10]
    return pd.DataFrame({"x1": x1, "x2": x2, "x3": x3})


# ---- 1. raw alpha matches the hand-computed textbook value 0.96 -----------
def test_alpha_matches_hand_computed() -> None:
    result = _run(_perfect_df())
    assert float(result.summaries["Cronbach's alpha"].split()[0]) == pytest.approx(
        0.96, abs=1e-6
    )
    # largest item variance in 18/50 etc -> sigma works out exactly to 0.96.
    s = result.summaries["Cronbach's alpha"]
    assert "excellent" in s


# ---- 2. standardised alpha is 1.0 (perfect correlations) ------------------
def test_standardised_alpha_matches_hand_computed() -> None:
    result = _run(_perfect_df())
    assert float(result.summaries["standardised alpha"]) == pytest.approx(
        1.0, abs=1e-6
    )


# ---- 3. interpretation bands map alpha to the right labels ----------------
def test_interpretation_bands() -> None:
    assert _interpretation(0.5) == "unacceptable"
    assert _interpretation(0.6) == "questionable"
    assert _interpretation(0.65) == "questionable"
    assert _interpretation(0.7) == "acceptable"
    assert _interpretation(0.75) == "acceptable"
    assert _interpretation(0.8) == "good"
    assert _interpretation(0.85) == "good"
    assert _interpretation(0.9) == "excellent"
    assert _interpretation(0.99) == "excellent"


# ---- 4. refuses fewer than two numeric item columns -----------------------
def test_refuses_fewer_than_two_items() -> None:
    df = pd.DataFrame({"a": [1, 2, 3, 4, 5]})
    with pytest.raises(AssumptionError, match="at least two numeric"):
        _run(df)


# ---- 5. missing values are dropped with a warning, never imputed ----------
def test_missing_dropped_with_warning_not_imputed() -> None:
    df = _perfect_df()
    df.iloc[0, 0] = np.nan
    df.iloc[1, 2] = np.nan
    result = _run(df)
    assert any("missing" in w.lower() and "never" in w.lower() for w in result.warnings)
    assert any("excluded" in w.lower() for w in result.warnings)
    assert result.methods
    methods_text = " ".join(result.methods)
    assert "imputed" in methods_text
    # After dropping 2 rows, n = 3 complete rows remain.
    assert int(result.summaries["observations (complete rows)"]) == 3


# ---- 6. interpretation, item-total table and what_does_not_tell present ---
def test_interpretation_item_table_and_what_not_tell() -> None:
    result = _run(_perfect_df())
    assert "Cronbach's alpha" in result.summaries
    assert "excellent" in result.summaries["Cronbach's alpha"]
    assert "Item statistics" in result.tables
    items = result.tables["Item statistics"]
    # three items, one row each, with a corrected item-total correlation.
    assert set(items["Item"]) == {"x1", "x2", "x3"}
    assert "item-total corr (rest)" in items.columns
    assert "alpha if deleted" in items.columns
    # perfect data -> corrected item-total correlations ~ 1.0
    corr = items["item-total corr (rest)"].astype(float)
    assert corr.abs().max() > 0.99
    assert len(result.what_does_not_tell) > 50
    assert "reverse-code" in result.what_does_not_tell.lower()
    # methods.txt sentences cover the named test, item count, n, alpha with
    # interpretation, and the no-auto-reverse-coding notice.
    methods_text = " ".join(result.methods).lower()
    assert "cronbach's alpha" in methods_text
    assert "3 numeric item column(s)" in methods_text
    assert "n = 5" in methods_text
    assert "0.960" in methods_text
    assert "excellent" in methods_text
    assert "does not automatically reverse-code" in methods_text


# ---- 7. small sample triggers expert review + WARN verdict ----------------
def test_small_sample_expert_review() -> None:
    rng = np.random.default_rng(3)
    df = pd.DataFrame(
        {
            "i1": rng.normal(size=20) + np.arange(20) * 0.5,
            "i2": rng.normal(size=20) + np.arange(20) * 0.5,
            "i3": rng.normal(size=20) + np.arange(20) * 0.5,
        }
    )
    result = _run(df)
    assert result.expert_review, "small sample should flag expert review"
    verdicts = {v.check: v.level for v in result.verdicts}
    assert "cronbach-alpha" in verdicts
    assert verdicts["cronbach-alpha"] in ("PASS", "WARN")
    assert any("sample" in w.lower() for w in result.warnings)


# ---- 8. constant / degenerate no-variance row sums are refused -------------
def test_refuses_zero_total_variance() -> None:
    # Two columns that are each other's negative -> every row sum is 0.
    df = pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [-1, -2, -3, -4, -5]})
    with pytest.raises(AssumptionError, match="variance is zero"):
        _run(df)
