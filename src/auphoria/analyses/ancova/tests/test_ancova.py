"""Tests for the ANCOVA analysis.

Uses small synthetic data with known, hand-computable answers, and compares
against statsmodels OLS as the documented reference library.

Hand-computed values for the tiny two-group dataset (covariate x = 1, 2, 3 in
BOTH groups; A: y = 2, 3, 3 ; B: y = 5, 6, 7). The design is orthogonal
(identical covariate columns per group), so the estimates separate cleanly:

  covariate slope      b_cov = sum((x-xbar)(y-ybar)) / sum((x-xbar)^2)
                         = 3 / 4 = 0.75
  group-B offset       d = 10/3 = 3.3333      (A is the reference, intercept 7/6)
  SSE(reduced y ~ cov) = 205/12
  SSE(full y ~ cov + group) = 5/12
  group effect         F = MS_group / MS_error
                         = (200/12) / (5/36) = 120  on df(1, 3)
  partial eta-squared  = SS_group / (SS_group + SSE_full) = 40/41 = 0.97561
  adjusted means at x = 2:  A = 2.6667, B = 6.0

These all match statsmodels OLS, so the test asserts both the hand values and
agreement with the reference implementation.
"""

from __future__ import annotations

import importlib

import numpy as np
import pandas as pd
import pytest
from scipy import stats
from statsmodels.formula.api import ols

from auphoria.core.analysis import AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

_ANCOVA_MODULE = importlib.import_module("auphoria.analyses.ancova.analysis")
AncovaAnalysis = _ANCOVA_MODULE.AncovaAnalysis


def _ctx() -> RunContext:
    import logging
    from pathlib import Path

    logger = logging.getLogger("auphoria_ancova_test")
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
    return AncovaAnalysis().run(
        df,
        {"alpha": 0.05, **params},
        {"outcome": "value", "group": "group", "covariate": "cov"},
        _ctx(),
    )


def _two_group_df() -> pd.DataFrame:
    # Hand-computable design: covariate x = 1, 2, 3 in both groups.
    return pd.DataFrame(
        {
            "value": [2.0, 3.0, 3.0, 5.0, 6.0, 7.0],
            "group": ["A", "A", "A", "B", "B", "B"],
            "cov": [1.0, 2.0, 3.0, 1.0, 2.0, 3.0],
        }
    )


def _big_df(n_per: int = 20) -> pd.DataFrame:
    """A larger synthetic dataset with two groups sharing a slope."""
    rng = np.random.default_rng(42)
    covA = rng.uniform(0, 10, n_per)
    covB = rng.uniform(0, 10, n_per)
    valA = 2.0 + 1.5 * covA + rng.normal(0, 1.2, n_per)
    valB = 5.0 + 1.5 * covB + rng.normal(0, 1.2, n_per)
    return pd.DataFrame(
        {
            "value": np.concatenate([valA, valB]),
            "group": ["A"] * n_per + ["B"] * n_per,
            "cov": np.concatenate([covA, covB]),
        }
    )


# --------------------------------------------------------------------------
# (1) agreement with statsmodels OLS (the documented reference) within 1e-4
# --------------------------------------------------------------------------
def test_ancova_matches_statsmodels_reference():
    df = _big_df()
    result = _run(df)

    # Reference fit on the same data.
    ref = ols("value ~ cov + C(group)", data=df).fit()
    red_group = ols("value ~ cov", data=df).fit()
    dfn = int(ref.df_model - red_group.df_model)
    dfd = int(ref.df_resid)
    ss_group = red_group.ssr - ref.ssr
    ref_F = ss_group / dfn / (ref.ssr / dfd)
    ref_p = float(stats.f.sf(ref_F, dfn, dfd))

    table = result.tables["ANCOVA table"].set_index("Source")
    gt = table.loc["Group (covariate-adjusted)"]
    # Group-effect F and p from the analysis match the reference within 1e-4.
    assert float(gt["F"]) == pytest.approx(ref_F, abs=1e-4)
    assert float(gt["p"]) == pytest.approx(ref_p, abs=1e-4)
    assert float(gt["df"]) == pytest.approx(dfn, abs=1e-4)
    # Covariate coefficient matches the reference within 1e-4.
    es = result.tables["Effect size"].set_index("Measure")
    assert float(es.loc["covariate coefficient (slope)", "Value"]) == pytest.approx(
        float(ref.params["cov"]), abs=1e-4
    )
    # Residual df agrees.
    resid = table.loc["Residual"]
    assert float(resid["df"]) == pytest.approx(dfd, abs=1e-4)
    # Adjusted means for each group.
    adj = result.tables["Adjusted means"].set_index("Group")
    covmean = df["cov"].mean()
    ref_adj = ref.predict(
        pd.DataFrame({"cov": [covmean, covmean], "group": ["A", "B"]})
    )
    assert float(adj.loc["A", "Adjusted mean"]) == pytest.approx(
        float(ref_adj.iloc[0]), abs=1e-3
    )
    assert float(adj.loc["B", "Adjusted mean"]) == pytest.approx(
        float(ref_adj.iloc[1]), abs=1e-3
    )


# --------------------------------------------------------------------------
# (2) hand-computed values on the tiny orthogonal dataset
# --------------------------------------------------------------------------
def test_ancova_matches_hand_computed_values():
    result = _run(_two_group_df())

    # Covariate slope = 3/4 = 0.75; group-B offset = 10/3.
    es = result.tables["Effect size"].set_index("Measure")
    assert float(es.loc["covariate coefficient (slope)", "Value"]) == pytest.approx(
        0.75, abs=1e-4
    )

    table = result.tables["ANCOVA table"].set_index("Source")
    gt = table.loc["Group (covariate-adjusted)"]
    # Hand-computed group effect: F = 120 on df(1, 3).
    assert float(gt["F"]) == pytest.approx(120.0, abs=1e-3)
    assert float(gt["df"]) == pytest.approx(1.0, abs=1e-6)
    assert float(table.loc["Residual", "df"]) == pytest.approx(3.0, abs=1e-6)
    ref_p = float(stats.f.sf(120.0, 1, 3))
    assert float(gt["p"]) == pytest.approx(ref_p, abs=1e-6)
    # Sum of squares: SS_group = 200/12, residual = 5/12.
    assert float(gt["SS"]) == pytest.approx(200.0 / 12.0, abs=1e-4)
    assert float(table.loc["Residual", "SS"]) == pytest.approx(5.0 / 12.0, abs=1e-4)
    # Partial eta-squared = 40/41.
    assert float(es.loc["partial eta-squared (group)", "Value"]) == pytest.approx(
        40.0 / 41.0, abs=1e-4
    )
    # Adjusted means at covariate mean 2: A = 8/3, B = 6.
    adj = result.tables["Adjusted means"].set_index("Group")
    assert float(adj.loc["A", "Adjusted mean"]) == pytest.approx(8.0 / 3.0, abs=1e-3)
    assert float(adj.loc["B", "Adjusted mean"]) == pytest.approx(6.0, abs=1e-3)

    # Group-B coefficient (offset vs A) computed by the linear model = 10/3.
    full = ols("value ~ cov + C(group)", data=_two_group_df()).fit()
    assert float(full.params["C(group)[T.B]"]) == pytest.approx(10.0 / 3.0, abs=1e-4)


# --------------------------------------------------------------------------
# (3) refuses a single-category group
# --------------------------------------------------------------------------
def test_ancova_refuses_single_group():
    df = pd.DataFrame(
        {
            "value": [1.0, 2.0, 3.0, 4.0],
            "group": ["A", "A", "A", "A"],
            "cov": [1.0, 2.0, 3.0, 4.0],
        }
    )
    with pytest.raises(AssumptionError):
        _run(df)


def test_ancova_refuses_single_observation_group():
    df = pd.DataFrame(
        {
            "value": [2.0, 8.0, 10.0, 5.0, 6.0],
            "group": ["A", "B", "B", "B", "B"],
            "cov": [1.0, 2.0, 3.0, 4.0, 1.0],
        }
    )
    with pytest.raises(AssumptionError):
        _run(df)


# --------------------------------------------------------------------------
# (4) refuses non-numeric outcome containing text
# --------------------------------------------------------------------------
def test_ancova_refuses_text_outcome():
    df = pd.DataFrame(
        {
            "value": ["2.0", "three", "3.0", "5.0", "6.0", "7.0"],
            "group": ["A", "A", "A", "B", "B", "B"],
            "cov": [1.0, 2.0, 3.0, 1.0, 2.0, 3.0],
        }
    )
    with pytest.raises(AssumptionError, match="text"):
        _run(df)


def test_ancova_refuses_text_covariate():
    df = _two_group_df()
    # Replace one covariate value with genuine text that cannot become a number,
    # avoiding a pandas dtype FutureWarning by rebuilding the column as object.
    df["cov"] = pd.Series(["n/a"] + [float(v) for v in df["cov"].iloc[1:]])
    with pytest.raises(AssumptionError, match="text"):
        _run(df)


# --------------------------------------------------------------------------
# (5) missing values -> listwise exclusion with a warning, never imputed
# --------------------------------------------------------------------------
def test_ancova_missing_dropped_with_warning():
    df = _big_df(n_per=10)
    df.iloc[1, df.columns.get_loc("value")] = np.nan
    df.iloc[-1, df.columns.get_loc("cov")] = np.nan
    result = _run(df)
    # A has rows 0..9, B rows 10..19: one missing in each group -> 9 each.
    adj = result.tables["Adjusted means"].set_index("Group")
    assert int(adj.loc["A", "n"]) == 9
    assert int(adj.loc["B", "n"]) == 9
    # A warning that rows were excluded, and no imputation ever happened.
    assert any("row(s)" in w and "missing" in w for w in result.warnings)
    assert all("imput" not in c.lower() or "no" in c.lower()
               for c in [w for w in result.warnings])


# --------------------------------------------------------------------------
# (6) returns a figure, >= 3 methods sentences, and a what_does_not_tell
# --------------------------------------------------------------------------
def test_ancova_returns_figure_methods_and_caveats():
    result = _run(_big_df())
    assert len(result.figures) == 1
    assert result.figures[0].name == "ancova_scatter"
    assert len(result.methods) >= 3
    methods_text = " ".join(result.methods)
    assert "ANCOVA" in methods_text
    assert "partial eta-squared" in methods_text
    assert len(result.what_does_not_tell) > 40
    # Summaries present.
    assert "group effect" in result.summaries
    assert "covariate coefficient" in result.summaries


# --------------------------------------------------------------------------
# (7) advanced-analysis behavior: assumption verdicts + expert review
# --------------------------------------------------------------------------
def test_ancova_verdicts_and_expert_review_for_small_n():
    # Tiny 6-row dataset is below the ~12-row recommended minimum.
    result = _run(_two_group_df())
    levels = {v.check: v.level for v in result.verdicts}
    assert "homogeneity-of-slopes" in levels
    assert "normality" in levels
    assert any("expert review" in r or "statistician" in r
               for r in result.expert_review)
    # In this two-group design group A and B each have 3 rows -> small-group banner.
    assert any("below the recommended minimum" in r for r in result.expert_review)


def test_ancova_no_expert_review_banner_in_healthy_sample():
    result = _run(_big_df())
    # Large, well-behaved sample: no small-sample expert-review flag.
    assert not any("below the recommended minimum" in r for r in result.expert_review)
