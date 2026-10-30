"""Tests for the hardy-weinberg analysis.

Hand-computed HWE examples:

Marker 1 (in equilibrium): AA=30, Aa=50, aa=20 -> n=100.
  p = (2*30+50)/200 = 0.55, q = 0.45
  E(AA)=100*0.55^2 = 30.25, E(Aa)=2*100*0.55*0.45 = 49.5, E(aa)=20.25
  chi2 = (30-30.25)^2/30.25 + (50-49.5)^2/49.5 + (20-20.25)^2/20.25
       = 0.0625/30.25 + 0.25/49.5 + 0.0625/20.25 = 0.010203
  p = chi2.sf(0.010203, 1) = 0.9195

Marker 2 (strong deviation): AA=40, Aa=20, aa=40 -> n=100, p=q=0.5.
  E = 25/50/25 -> chi2 = 9 + 18 + 9 = 36, p = chi2.sf(36, 1) = 2.0e-9
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
import pytest
from scipy import stats

from auphoria.core.analysis import AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

_MOD = importlib.import_module("auphoria.analyses.hardy-weinberg.analysis")
HweAnalysis = _MOD.HardyWeinbergAnalysis


def _ctx() -> RunContext:
    import logging

    logger = logging.getLogger("auphoria_hwe_test")
    logger.handlers = []
    return RunContext(seed=1, out_dir=Path("."), data_name="test", expert=False,
                      _log=logger, _log_decision=lambda m: None)


def _run(aa: list, het: list, aa2: list, **params) -> AnalysisResult:
    df = pd.DataFrame({"AA": aa, "Aa": het, "aa": aa2})
    p = {"alpha": 0.05}
    p.update(params)
    return HweAnalysis().run(
        df, p,
        {"n_homo_ref": "AA", "n_het": "Aa", "n_homo_alt": "aa"},
        _ctx(),
    )


def test_equilibrium_marker():
    res = _run([30], [50], [20])
    t = res.tables["hwe_test"]
    r = t.iloc[0]
    assert r["freq_A_p"] == pytest.approx(0.55)
    assert r["freq_a_q"] == pytest.approx(0.45)
    assert r["exp_AA"] == pytest.approx(30.25)
    assert r["exp_Aa"] == pytest.approx(49.5)
    assert r["exp_aa"] == pytest.approx(20.25)
    assert r["chi2"] == pytest.approx(0.0102, abs=1e-3)
    assert r["p_value"] == pytest.approx(stats.chi2.sf(0.0102, 1), abs=1e-3)
    assert r["hwe"] == "consistent"


def test_deviation_marker():
    res = _run([40], [20], [40])
    t = res.tables["hwe_test"]
    r = t.iloc[0]
    # E = 25/50/25
    assert r["chi2"] == pytest.approx(36.0)
    assert r["p_value"] == pytest.approx(stats.chi2.sf(36.0, 1))
    assert r["hwe"] == "deviation"


def test_multiple_markers():
    res = _run([30, 40], [50, 20], [20, 40])
    t = res.tables["hwe_test"]
    assert len(t) == 2
    assert list(t["hwe"]) == ["consistent", "deviation"]
    assert res.summaries["markers tested"] == "2"


def test_negative_counts_refused():
    with pytest.raises(AssumptionError, match="negative"):
        _run([-1], [5], [5])


def test_zero_total_refused():
    with pytest.raises(AssumptionError, match="n = 0"):
        _run([0], [0], [0])


def test_small_expected_warns():
    res = _run([1], [2], [1])  # n=4, minimal expected < 5
    assert any("expected" in v.message.lower() and "5" in v.message for v in res.verdicts)


def test_decimal_counts_rounded_with_warning():
    res = _run([2.4], [5.0], [3.0])
    assert len(res.warnings) >= 1


def test_what_does_not_tell_present():
    res = _run([30], [50], [20])
    assert res.what_does_not_tell.strip() != ""
