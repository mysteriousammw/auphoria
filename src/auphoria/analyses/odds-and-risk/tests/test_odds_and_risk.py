"""Tests for the relative risk & odds ratio (2x2) analysis.

Uses small synthetic data with known, hand-computable answers and compares
against SciPy's reference implementations (chi2_contingency and fisher_exact).
"""

from __future__ import annotations

import logging
from importlib import import_module
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from auphoria.core.analysis import RunContext
from auphoria.core.errors import AssumptionError

# The folder name is 'odds-and-risk'; Python source cannot spell a hyphenated
# import, so load the module through importlib (as the registry does).
_mod = import_module("auphoria.analyses.odds-and-risk.analysis")
OddsAndRiskAnalysis = _mod.OddsAndRiskAnalysis


def _ctx() -> RunContext:
    logger = logging.getLogger("auphoria_odds_risk_test")
    logger.handlers = []
    return RunContext(
        seed=1,
        out_dir=Path("."),
        data_name="test",
        expert=False,
        _log=logger,
        _log_decision=lambda m: None,
    )


def _expand(
    counts: list[list[int]], exposed: str, unexposed: str, event: str, no_event: str
) -> pd.DataFrame:
    """Expand [[a,b],[c,d]] (exposed x outcome) into one row per observation."""
    exposure, outcome = [], []
    for row_cat, row in zip((exposed, unexposed), counts, strict=False):
        for col_cat, c in zip((event, no_event), row, strict=False):
            exposure.extend([row_cat] * c)
            outcome.extend([col_cat] * c)
    return pd.DataFrame({"exposure": exposure, "outcome": outcome})


def test_odds_risk_matches_hand_and_scipy():
    analysis = OddsAndRiskAnalysis()
    # a=40,b=20,c=15,d=45  ->  OR = 40*45/(20*15) = 1800/300 = 6.0
    # RR = (40/60)/(15/60) = 0.6667/0.25 = 2.6667
    df = _expand([[40, 20], [15, 45]], "Exposed", "Unexposed", "event", "no_event")
    result = analysis.run(
        df, {"alpha": 0.05}, {"exposure": "exposure", "outcome": "outcome"}, _ctx(),
    )

    observed = np.array([[40, 20], [15, 45]])
    ref_chi2, ref_chi2_p, ref_dof, _ = stats.chi2_contingency(
        observed, correction=True
    )
    ref_fisher_or, ref_fisher_p = stats.fisher_exact(observed)

    table = result.tables["Effect measures"]

    def val(item: str) -> float:
        return float(table.loc[table["Measure"] == item, "Value"].iloc[0])

    assert val("odds ratio (OR)") == pytest.approx(6.0, abs=1e-6)
    assert val("relative risk (RR)") == pytest.approx(2.6666667, abs=1e-5)
    assert val("odds ratio (OR)") == pytest.approx(40 * 45 / (20 * 15), abs=1e-6)
    assert val("relative risk (RR)") == pytest.approx(
        (40 / 60) / (15 / 60), abs=1e-6
    )
    assert val("chi-square (Yates) statistic") == pytest.approx(ref_chi2, abs=1e-6)
    assert val("chi-square p-value") == pytest.approx(ref_chi2_p, abs=1e-6)
    assert val("Fisher exact p-value") == pytest.approx(ref_fisher_p, abs=1e-6)
    assert val("sample size (n)") == pytest.approx(120.0, abs=1e-9)

    # The 95% RR interval is simply the Woolf-log normal approx (already the
    # only implementation, so sanity check ordering and exclusion of 1).
    rr_lo = val("RR 95% CI (lower)")
    rr_hi = val("RR 95% CI (upper)")
    or_lo = val("OR 95% CI (lower)")
    or_hi = val("OR 95% CI (upper)")
    assert 0 < rr_lo < rr_hi
    assert 0 < or_lo < or_hi

    # Events are far more frequent in the exposed group => intervals exclude 1.
    assert rr_lo > 1 and or_lo > 1

    # Expected counts all well above 5 -> PASS verdict.
    assert any(
        v.level == "PASS" and v.check == "expected-counts"
        for v in result.verdicts
    )


def test_odds_risk_refuses_more_than_two_categories():
    analysis = OddsAndRiskAnalysis()
    df = pd.DataFrame(
        {
            "exposure": ["A", "A", "B", "B"],
            "outcome": ["x", "y", "x", "z"],  # 3 categories -> refuse
        }
    )
    with pytest.raises(AssumptionError):
        analysis.run(
            df, {"alpha": 0.05}, {"exposure": "exposure", "outcome": "outcome"}, _ctx(),
        )

    # Also refuse when the EXPOSURE column has >2 categories.
    df2 = pd.DataFrame(
        {
            "exposure": ["A", "B", "C", "A"],
            "outcome": ["x", "y", "x", "y"],
        }
    )
    with pytest.raises(AssumptionError):
        analysis.run(
            df2,
            {"alpha": 0.05},
            {"exposure": "exposure", "outcome": "outcome"},
            _ctx(),
        )


def test_odds_risk_zero_cell_uses_haldane_with_warning():
    analysis = OddsAndRiskAnalysis()
    # Cell 'a' (exposed & event) is zero -> Haldane 0.5 correction, no crash.
    df = _expand([[0, 10], [8, 2]], "Exposed", "Unexposed", "event", "no_event")
    result = analysis.run(
        df, {"alpha": 0.05}, {"exposure": "exposure", "outcome": "outcome"}, _ctx(),
    )
    assert any("Haldane" in w for w in result.warnings)
    assert any(v.level == "WARN" and v.check == "zero-cells" for v in result.verdicts)
    # The effect-measures table still exists and the OR is +finite.
    measures = result.tables["Effect measures"]
    or_val = float(
        measures.loc[measures["Measure"] == "odds ratio (OR)", "Value"].iloc[0]
    )
    assert or_val == or_val  # not NaN
    assert or_val >= 0


def test_odds_risk_drops_missing_rows_with_warning():
    analysis = OddsAndRiskAnalysis()
    df = _expand([[40, 20], [15, 45]], "Exposed", "Unexposed", "event", "no_event")
    df.loc[0, "exposure"] = np.nan  # row 0 is an exposed/event row
    df.loc[50, "outcome"] = np.nan  # row 50 is an exposed/no_event row
    result = analysis.run(
        df, {"alpha": 0.05}, {"exposure": "exposure", "outcome": "outcome"}, _ctx(),
    )
    assert any("missing" in w for w in result.warnings)
    cont = result.tables["Contingency table"]
    assert int(cont.loc["Exposed", "event"]) == 39  # one event lost
    measures = result.tables["Effect measures"]
    n_val = float(
        measures.loc[measures["Measure"] == "sample size (n)", "Value"].iloc[0]
    )
    assert n_val == pytest.approx(118.0, abs=1e-9)


def test_odds_risk_returns_figure_methods_and_limits_text():
    analysis = OddsAndRiskAnalysis()
    df = _expand([[40, 20], [15, 45]], "Exposed", "Unexposed", "event", "no_event")
    result = analysis.run(
        df, {"alpha": 0.05}, {"exposure": "exposure", "outcome": "outcome"}, _ctx(),
    )
    assert len(result.figures) == 1
    assert result.figures[0].name == "odds_risk_event_rates"

    methods_blob = "\n".join(result.methods).lower()
    # methods must name the exposure column, outcome/event, RR+CI, OR+CI,
    # chi-square p, Fisher p, n, and the fact nothing was imputed.
    for token in (
        "exposure",
        "outcome",
        "event",
        "relative risk",
        "odds ratio",
        "confidence interval",
        "chi-square",
        "fisher",
        "n = 120",
        "imputed",
    ):
        assert token in methods_blob, f"methods missing token: {token}"

    assert result.what_does_not_tell.strip() != ""
    low = result.what_does_not_tell.lower()
    assert "caus" in low
    assert "odds ratio" in low
    assert "relative risk" in low

    assert "Row total" in result.tables["Contingency table"].columns
    assert "Row total" in result.tables["Row percentages"].columns
    assert result.summaries  # non-empty highlights card


def test_module_exposes_analysis_instance():
    # The registry looks for the module-level ANALYSIS instance; it must exist
    # and be an instance of our class with the right id.
    assert isinstance(_mod.ANALYSIS, OddsAndRiskAnalysis)
    assert _mod.ANALYSIS.id == "odds-and-risk"
