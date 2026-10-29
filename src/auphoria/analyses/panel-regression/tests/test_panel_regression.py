"""Tests for the fixed-effects (within) panel regression analysis.

Uses a small deterministic synthetic panel with a known true generating
process,

    y_it = 2 * x_it + alpha_i + e_it

where alpha_i is an entity-specific fixed effect (drawn once per entity) and
e_it is random within-unit noise. Because statsmodels 0.15 does not ship
PanelOLS (that lives in the separate ``linearmodels`` package), the independent
reference here is the *least-squared-dummy-variable* (LSDV) fixed-effects fit
with statsmodels OLS on the raw data plus a full set of entity dummies, which
is algebraically equivalent to the within (group-demeaned) estimator. The
analysis's reported within beta and R-square-within must therefore match the
LSDV beta and the canonical within R-square (computed from the LSDV residuals
and the within sum of squares) within 1e-5.
"""

from __future__ import annotations

import importlib

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from auphoria.core.analysis import AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

_ANALYSIS_MODULE = importlib.import_module("auphoria.analyses.panel-regression.analysis")
PanelRegressionAnalysis = _ANALYSIS_MODULE.PanelRegressionAnalysis

_TRUE_BETA = 2.0


def _ctx() -> RunContext:
    import logging
    from pathlib import Path

    logger = logging.getLogger("auphoria_panel_test")
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
    return PanelRegressionAnalysis().run(
        df,
        {"alpha": 0.05, **params},
        {"outcome": "y", "entity": "entity", "time": "time"},
        _ctx(),
    )


def _make_df(n_entities: int = 12, n_time: int = 6, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ent = np.repeat(np.arange(n_entities), n_time)
    tim = np.tile(np.arange(n_time), n_entities)
    fe = np.repeat(rng.normal(0, 2, n_entities), n_time)
    x = rng.uniform(0, 10, len(ent))
    e = rng.normal(0, 1.5, len(ent))
    y = _TRUE_BETA * x + fe + e
    return pd.DataFrame(
        {
            "y": y,
            "x": x,
            "entity": ent.astype(str),
            "time": tim.astype(str),
        }
    )


def _lsdv_reference(df: pd.DataFrame):
    """Independent fixed-effects reference: OLS with entity dummies (LSDV)."""
    covariate = "x" if "x" in df.columns else _single_raw_covariate(df)
    X = pd.get_dummies(df["entity"], drop_first=True).astype(float)
    X[covariate] = df[covariate]
    model = sm.OLS(df["y"], sm.add_constant(X)).fit()
    # Canonical within R-square: 1 - SSR_LSDV / SST_within
    sst_within = float(
        np.sum((df["y"] - df.groupby("entity")["y"].transform("mean")) ** 2)
    )
    r2_within = 1.0 - float(np.sum(model.resid ** 2)) / sst_within
    return {"beta": float(model.params[covariate]), "r2_within": r2_within}


def _single_raw_covariate(df: pd.DataFrame) -> str:
    return [c for c in df.columns if c not in {"y", "entity", "time"}][0]


# --------------------------------------------------------------------------
# (1) agreement with LSDV fixed-effects reference within 1e-5
# --------------------------------------------------------------------------
def test_panel_regression_matches_fixed_effects_reference():
    df = _make_df()
    result = _run(df)

    coeffs = result.tables["Coefficients"].set_index("covariate")
    model = result.tables["Model"].set_index("Statistic")

    ref = _lsdv_reference(df)

    # Within beta matches the LSDV (dummy-variable) fixed-effects estimate.
    assert float(coeffs.loc["x", "beta"]) == pytest.approx(ref["beta"], abs=1e-5)
    # And is close to the true generating coefficient (within +/-
    # one standard error or so of sampling noise).
    assert float(coeffs.loc["x", "beta"]) == pytest.approx(_TRUE_BETA, abs=0.2)

    # R-square within matches the canonical LSDV-based value within 1e-5.
    assert float(model.loc["R2 within", "Value"]) == pytest.approx(
        ref["r2_within"], abs=1e-5
    )

    # Model table carries correct sizes and derived statistics.
    assert int(model.loc["n", "Value"]) == len(df)
    assert int(model.loc["entities", "Value"]) == 12
    assert int(model.loc["time periods", "Value"]) == 6


# --------------------------------------------------------------------------
# (2) refuses a panel with too few entities (< 8)
# --------------------------------------------------------------------------
def test_refuses_too_few_entities():
    df = _make_df(n_entities=6, n_time=6)
    with pytest.raises(AssumptionError, match="at least 8"):
        _run(df)


# --------------------------------------------------------------------------
# (3) refuses a panel with too few rows (< 30)
# --------------------------------------------------------------------------
def test_refuses_too_few_rows():
    df = _make_df(n_entities=8, n_time=3)
    with pytest.raises(AssumptionError, match="at least 30"):
        _run(df)


# --------------------------------------------------------------------------
# (4) refuses when there is no numeric covariate
# --------------------------------------------------------------------------
def test_refuses_no_covariate():
    df = _make_df()
    df = df[["y", "entity", "time"]]
    with pytest.raises(AssumptionError, match="at least one numeric covariate"):
        _run(df)


# --------------------------------------------------------------------------
# (5) refuses a perfectly collinear covariate set
# --------------------------------------------------------------------------
def test_refuses_collinear_covariates():
    df = _make_df()
    df["x2"] = 2.0 * df["x"] + 1.0  # exactly a linear combination of x
    with pytest.raises(AssumptionError, match="perfectly collinear"):
        _run(df)


# --------------------------------------------------------------------------
# (6) missing values -> listwise exclusion with a warning, never imputed
# --------------------------------------------------------------------------
def test_missing_values_dropped_with_warning():
    df = _make_df()
    df.iloc[2, df.columns.get_loc("y")] = np.nan
    df.iloc[5, df.columns.get_loc("x")] = np.nan
    result = _run(df)

    model = result.tables["Model"].set_index("Statistic")
    # Two rows dropped listwise -> n = 70.
    assert int(model.loc["n", "Value"]) == len(df) - 2
    assert any("row(s)" in w and "missing" in w for w in result.warnings)
    assert all("imput" not in w.lower() or "no" in w.lower()
               for w in result.warnings)


# --------------------------------------------------------------------------
# (7) returns a figure, methods, summaries and a what_does_not_tell
# --------------------------------------------------------------------------
def test_returns_figure_methods_and_caveats():
    result = _run(_make_df())
    assert len(result.figures) == 1
    assert result.figures[0].name == "fitted_vs_actual"
    assert len(result.methods) >= 2
    methods_text = " ".join(result.methods)
    assert "fixed-effects" in methods_text.lower() or "within" in methods_text.lower()
    assert "R2" in methods_text
    assert len(result.what_does_not_tell) > 40
    assert "time-invariant" in result.what_does_not_tell.lower()
    assert "caus" in result.what_does_not_tell.lower()
    assert "within-entity" in result.what_does_not_tell.lower()
    assert "covariates" in result.summaries
    assert "R2 within" in result.summaries
    assert "entities" in result.summaries


# --------------------------------------------------------------------------
# (9) expert review banner for a small panel
# --------------------------------------------------------------------------
def test_expert_review_banner_for_small_panel():
    # 10 entities < 15 -> expert review.
    result = _run(_make_df(n_entities=10, n_time=6))
    assert any("expert review" in r or "statistician" in r
               for r in result.expert_review)
    levels = {v.check: v.level for v in result.verdicts}
    assert levels["sample-size"] == "WARN"


def test_no_expert_review_banner_in_healthy_panel():
    result = _run(_make_df(n_entities=20, n_time=6))
    assert not any("expert review" in r for r in result.expert_review)
    levels = {v.check: v.level for v in result.verdicts}
    assert levels["sample-size"] == "PASS"
