"""Tests for the Cox proportional-hazards regression analysis.

Uses small deterministic synthetic survival data and compares the reported
hazard ratios (exp(coef)) and p-values against statsmodels' ``PHReg`` directly
(the "documented reference"), plus guardrail tests: refusing a non-0/1 event
column, a constant covariate, and zero events; listwise exclusion of missing
values with a warning (never imputed); and that the result carries a figure,
>= 3 methods sentences and a what_does_not_tell note.
"""

from __future__ import annotations

import importlib

import numpy as np
import pandas as pd
import pytest
from statsmodels.duration.hazard_regression import PHReg

from auphoria.core.analysis import AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

# The analysis id contains a hyphen ('cox-regression'), which is not valid
# Python syntax in an import statement, so load the module by name.
_COX_MODULE = importlib.import_module("auphoria.analyses.cox-regression.analysis")
CoxRegressionAnalysis = _COX_MODULE.CoxRegressionAnalysis


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


def _survival_df(n: int = 120, seed: int = 7) -> pd.DataFrame:
    """Deterministic synthetic survival data with ~30% censoring."""
    rng = np.random.default_rng(seed)
    cov1 = rng.normal(0.0, 1.0, n)
    cov2 = rng.normal(0.0, 1.0, n)
    # Risk soars with cov1 (true HR ~ exp(0.4)), slight negative effect cov2.
    lam = np.exp(0.4 * cov1 - 0.3 * cov2) * 0.02
    u = rng.uniform(size=n)
    event_t = -np.log(u) / lam
    # Admin censoring at a follow-up cap -> roughly 30% censored.
    cap = np.quantile(event_t, 0.7)
    observed = np.minimum(event_t, cap)
    status = (event_t <= cap).astype(int)
    df = pd.DataFrame(
        {"time": observed, "status": status, "cov1": cov1, "cov2": cov2}
    )
    # Keep time consistent: values must be non-negative and status only 0/1.
    assert df["time"].min() >= 0
    assert set(df["status"].unique()) <= {0, 1}
    return df


def _run(
    df: pd.DataFrame, covariate: str = "cov1, cov2", **params
) -> AnalysisResult:
    return CoxRegressionAnalysis().run(
        df,
        {"alpha": 0.05, **params},
        {"time": "time", "event": "status", "covariate": covariate},
        _ctx(),
    )


def _reference(df: pd.DataFrame, covariate: str = "cov1, cov2") -> PHReg:
    covs = [c.strip() for c in covariate.split(",")]
    t = df["time"].to_numpy(dtype=float)
    e = df["status"].to_numpy(dtype=float)
    x = df[covs].to_numpy(dtype=float)
    return PHReg(endog=t, exog=x, status=e).fit(disp=0)


def test_hazard_ratios_match_statsmodels():
    df = _survival_df()
    result = _run(df)
    ref = _reference(df)
    table = result.tables["Hazard ratios"].set_index("Covariate")
    assert list(table.index) == ["cov1", "cov2"]
    for i, cov in enumerate(["cov1", "cov2"]):
        ref_hr = float(np.exp(ref.params[i]))
        assert float(table.loc[cov, "Hazard ratio (exp coef)"]) == pytest.approx(
            ref_hr, abs=1e-3
        )
        ref_lo = float(np.exp(ref.params[i] - 1.96 * ref.bse[i]))
        ref_hi = float(np.exp(ref.params[i] + 1.96 * ref.bse[i]))
        assert float(table.loc[cov, "95% CI lower"]) == pytest.approx(ref_lo, abs=1e-3)
        assert float(table.loc[cov, "95% CI upper"]) == pytest.approx(ref_hi, abs=1e-3)


def test_pvalues_match_statsmodels():
    df = _survival_df()
    result = _run(df)
    ref = _reference(df)
    table = result.tables["Hazard ratios"].set_index("Covariate")
    for i, cov in enumerate(["cov1", "cov2"]):
        assert float(table.loc[cov, "p"]) == pytest.approx(
            float(ref.pvalues[i]), abs=1e-3
        )


def test_single_covariate_and_methods_figure_notes():
    df = _survival_df()
    result = _run(df, covariate="cov1")
    table = result.tables["Hazard ratios"].set_index("Covariate")
    assert list(table.index) == ["cov1"]
    # Figure present with a sensible name.
    assert len(result.figures) == 1
    assert result.figures[0].name == "cox_forest_plot"
    # >= 3 methods sentences, all mention the model.
    assert len(result.methods) >= 3
    methods_text = " ".join(result.methods)
    assert "Cox proportional-hazards" in methods_text
    assert "Hazard ratio" in methods_text or "HR" in methods_text
    # Honest what_does_not_tell note is present and substantive.
    assert len(result.what_does_not_tell) > 50
    assert "relative" in result.what_does_not_tell


def test_refuses_event_not_01():
    df = _survival_df().copy()
    df.loc[0, "status"] = 2  # a value other than 0/1
    with pytest.raises(AssumptionError, match="event indicator"):
        _run(df)


def test_refuses_constant_covariate():
    df = _survival_df().copy()
    df["cov2"] = 5.0  # constant
    with pytest.raises(AssumptionError, match="constant"):
        _run(df, covariate="cov1, cov2")


def test_refuses_no_events():
    df = _survival_df().copy()
    df["status"] = 0
    with pytest.raises(AssumptionError, match="no events"):
        _run(df)


def test_missing_listwise_with_warning_never_imputed():
    df = _survival_df().copy()
    # Drop 5 time values and 3 cov1 values (overlap expected on some rows).
    df.loc[0, "time"] = np.nan
    df.loc[1, "time"] = np.nan
    df.loc[2, "cov1"] = np.nan
    df.loc[3, "cov1"] = np.nan
    df.loc[4, "cov2"] = np.nan
    result = _run(df)
    missing_rows = df[["time", "cov1", "cov2"]].isna().any(axis=1).sum()
    assert missing_rows == 5
    # The model ran on the complete rows only (listwise).
    fit = result.tables["Model fit"].set_index("Quantity")
    assert int(fit.loc["total complete rows (n)", "Value"]) == len(df) - missing_rows
    # A warning is recorded; it must say rows were excluded, never imputed.
    assert any("row(s)" in w and "missing" in w for w in result.warnings)
    assert any("imputed" in w for w in result.warnings)
    assert any("excluded" in w or "left out" in w for w in result.warnings)


def test_verdicts_emitted():
    df = _survival_df()
    result = _run(df)
    checks = {v.check for v in result.verdicts}
    assert "events-count" in checks
    assert "proportional-hazards" in checks
    by_check = {v.check: v.level for v in result.verdicts}
    assert by_check["events-count"] == "PASS"
