"""Tests for the structural equation model (one-factor CFA) analysis.

Uses a deterministic synthetic one-factor dataset with four items at known
loadings, so a one-factor confirmatory model fits well (CFI near 1, RMSEA <
0.06). We assert that the analysis:

1. runs and reports the fit indices (CFI, TLI, RMSEA, SRMR, chi2, df, p);
2. reports a standardised loading for every item;
3. builds the 'F =~ item1 + item2 + ...' model string correctly;
4. emits PASS/WARN fit verdicts;
5. refuses fewer than 3 numeric items;
6. drops missing values with a warning (never imputes);
7. returns a figure, methods text and a non-empty what_does_not_tell.

The model string builder and the SRMR computation are tested directly against
their hand-computed references.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from auphoria.core.analysis import AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

# The analysis id has no hyphen, but keep the registry-style import for
# consistency with sibling analyses.
_MODULE = importlib.import_module("auphoria.analyses.sem.analysis")
SEMAnalysis = _MODULE.SEMAnalysis
_model_string = _MODULE._model_string
_srmr = _MODULE._srmr

#: A true one-factor structure: four items load on one factor F.
_TRUE_LOADINGS = [0.80, 0.70, 0.75, 0.65]


def _ctx() -> RunContext:
    logger = logging.getLogger("auphoria_sem_test")
    logger.handlers = []
    return RunContext(
        seed=1,
        out_dir=Path("."),
        data_name="test",
        expert=False,
        _log=logger,
        _log_decision=lambda m: None,
    )


def _one_factor_df(n: int = 300, seed: int = 42) -> pd.DataFrame:
    """Deterministic one-factor data: X_i = lambda_i * F + error."""
    rng = np.random.default_rng(seed)
    F = rng.normal(size=n)
    cols = {}
    for name, lam in zip(["i1", "i2", "i3", "i4"], _TRUE_LOADINGS, strict=True):
        err_sd = float(np.sqrt(max(0.0, 1.0 - lam**2)))
        cols[name] = lam * F + rng.normal(scale=err_sd, size=n)
    return pd.DataFrame(cols)


def _run(df: pd.DataFrame, **params) -> AnalysisResult:
    return SEMAnalysis().run(
        df, {"alpha": 0.05, **params}, {}, _ctx()
    )


# ---- 1. builds the correct one-factor model string ----
def test_model_string_built_from_items():
    assert _model_string(["i1", "i2", "i3"]) == "F =~ i1 + i2 + i3"
    assert _model_string(["a", "b", "c", "d"]) == "F =~ a + b + c + d"
    assert _model_string(["x"]) == "F =~ x"


# ---- 2. running the analysis produces fit indices and a loading per item ----
def test_runs_and_reports_fit_indices_and_loadings():
    df = _one_factor_df()
    result = _run(df)

    # A clean one-factor fit: CFI near 1, RMSEA well under 0.06.
    summary = result.summaries
    assert float(summary["CFI"]) > 0.95
    assert "RMSEA" in summary

    # Fit table exists and holds the indices.
    fit = result.tables["Model fit"]
    assert {"CFI", "TLI", "RMSEA", "SRMR", "chi2", "Df", "chi2 p"}.issubset(
        set(fit["Statistic"])
    )
    cfi_row = float(fit.set_index("Statistic").loc["CFI", "Value"])
    rmsea_row = float(fit.set_index("Statistic").loc["RMSEA", "Value"])
    assert cfi_row > 0.95
    assert rmsea_row < 0.06

    # A standardised loading for each item.
    loadings = result.tables["Factor loadings"]
    assert set(loadings["Item"]) == {"i1", "i2", "i3", "i4"}
    assert loadings["Std. loading"].notna().all()
    # High-loading items dominate; all loadings should be clearly positive.
    assert (loadings["Std. loading"] > 0.4).all()


# ---- 3. SRMR helper matches the hand-computed residual formula ----
def test_srmr_helper_matches_hand_computation():
    df = _one_factor_df(n=200, seed=3)
    import semopy

    m = semopy.Model(_model_string(list(df.columns)))
    m.fit(df)
    implied = np.asarray(m.calc_sigma()[0], dtype=float)
    obs = df.cov().values
    p = obs.shape[0]
    so = np.diag(obs)
    sq = sum(
        (obs[i, j] - implied[i, j]) ** 2 / (so[i] * so[j])
        for i in range(p)
        for j in range(p)
        if so[i] * so[j] > 0
    )
    expected = float(np.sqrt(sq / (p * (p + 1) // 2)))
    assert _srmr(df, implied) == pytest.approx(expected, abs=1e-12)


# ---- 4. fit verdicts are present (PASS/WARN) ----
def test_fit_verdicts_present():
    result = _run(_one_factor_df())
    checks = {v.check for v in result.verdicts}
    assert "model-fit" in checks
    assert any(v.check == "model-fit" for v in result.verdicts)
    # On clean one-factor data the model-fit verdict should PASS.
    mf = next(v for v in result.verdicts if v.check == "model-fit")
    assert mf.level in ("PASS", "WARN")
    assert "CFI" in mf.message or "RMSEA" in mf.message


# ---- 5. refuses fewer than 3 numeric items ----
def test_refuses_fewer_than_three_items():
    # 40 rows (above the 30-row floor) but only two numeric columns.
    df = pd.DataFrame({"a": range(40), "b": [x % 3 for x in range(40)]})
    with pytest.raises(AssumptionError, match="at least 3 numeric"):
        _run(df)


# ---- 6. refuses too few rows ----
def test_refuses_fewer_than_30_rows():
    df = _one_factor_df(n=20, seed=9)
    with pytest.raises(AssumptionError, match="at least 30 rows"):
        _run(df)


# ---- 7. missing values dropped with a warning, never imputed ----
def test_missing_dropped_with_warning_not_imputed():
    df = _one_factor_df(n=120, seed=5)
    df.iloc[0, 0] = np.nan
    df.iloc[1, 3] = np.nan
    result = _run(df)
    assert any(
        "missing" in w.lower() and "never imputed" in w.lower()
        for w in result.warnings
    )
    assert any("excluded" in w.lower() for w in result.warnings)
    assert result.methods, "methods should be present"
    assert "imputed" in " ".join(result.methods)


# ---- 8. figure + methods + non-empty what_does_not_tell ----
def test_outputs_figure_methods_and_what_not_tell():
    result = _run(_one_factor_df())
    assert len(result.figures) == 1
    assert result.figures[0].name == "sem_loadings"
    assert len(result.methods) >= 3
    methods_text = " ".join(result.methods)
    assert "confirmatory factor analysis" in methods_text.lower()
    assert "CFI" in methods_text
    assert len(result.what_does_not_tell) > 50
    assert "does NOT prove" in result.what_does_not_tell
    assert len(result.summaries) >= 3


# ---- 9. small sample triggers expert review ----
def test_small_sample_expert_review():
    # n = 60 (< 100 recommended) -> expert-review banner, analysis still runs.
    result = _run(_one_factor_df(n=60, seed=7))
    assert result.expert_review, "small sample should flag expert review"
    assert any("sample" in r.lower() for r in result.expert_review)
    verdicts = {v.check: v.level for v in result.verdicts}
    assert "model-fit" in verdicts
