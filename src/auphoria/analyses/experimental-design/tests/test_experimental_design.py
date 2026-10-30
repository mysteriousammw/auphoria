"""Tests for the experimental-design analysis.

Four balanced-design fixtures, each with hand-computed sum-of-squares and
F statistics:

CRD (3 treatments x 4 reps, means 4/10/16):
  SS_between = 4*((4-10)^2 + (10-10)^2 + (16-10)^2) = 288
  SS_within  = 24  ->  F = (288/2) / (24/9) = 54

RCBD (3 treatments x 4 blocks), values:
  blocks b1..b4 with effects -1,+1,+2,-2 and orthogonal errors
  SS_trt = 288, SS_block = 3*(1+1+4+4) = 30, SS_err = 4, SS_total = 322
  df: trt 2, block 3, err 6  ->  MS_trt = 144, MS_err = 4/6
  F_trt = 144 / (4/6) = 216

Latin square (3x3), treatment means 4/10/16:
  SS_trt = 3*(36+0+36) = 216, SS_row = 6, SS_col = 24, SS_err = 6
  df: trt 2, row 2, col 2, err 2 -> MS_trt = 108, MS_err = 3, F = 36

Factorial (2x2 x 4 reps), A effects +-2, B effects +-1, interaction +-0.5:
  cell means 7.5/8.5/10.5/13.5, errors +-1 within cells
  SS_A = 64, SS_B = 16, SS_AB = 4, SS_err = 8, SS_total = 92
  df: A 1, B 1, AB 1, err 12 -> F_A = 96, F_B = 24, F_AB = 6
"""

from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from auphoria.core.analysis import RunContext
from auphoria.core.errors import AssumptionError

_MOD = importlib.import_module("auphoria.analyses.experimental-design.analysis")
ExpDesignAnalysis = _MOD.ExperimentalDesignAnalysis


def _ctx() -> RunContext:
    import logging

    logger = logging.getLogger("auphoria_exp_test")
    logger.handlers = []
    return RunContext(
        seed=1,
        out_dir=Path("."),
        data_name="test",
        expert=False,
        _log=logger,
        _log_decision=lambda m: None,
    )


def _f(table_name: str, result) -> pd.DataFrame:
    return result.tables[table_name]


def _row(result, source: str) -> dict:
    aov = _f("anova", result)
    return aov[aov["Source"] == source].iloc[0]


# ---------------------------------------------------------------- fixtures
def crd_df() -> pd.DataFrame:
    vals = [2, 4, 4, 6, 8, 10, 10, 12, 14, 16, 16, 18]
    trt = ["A"] * 4 + ["B"] * 4 + ["C"] * 4
    return pd.DataFrame({"yield": vals, "treatment": trt})


def rcbd_df() -> pd.DataFrame:
    # block effects -1,+1,+2,-2 over treatments 4/10/16 with orthogonal errors.
    vals = [2, 5, 7, 2, 10, 11, 11, 8, 15, 17, 18, 14]
    trt = ["A", "A", "A", "A", "B", "B", "B", "B", "C", "C", "C", "C"]
    blk = ["b1", "b2", "b3", "b4"] * 3
    return pd.DataFrame({"yield": vals, "treatment": trt, "block": blk})


def latin_df() -> pd.DataFrame:
    # Latin square: rows r1..r3, cols c1..c3, one of each treatment per row/col.
    rows = ["r1", "r1", "r1", "r2", "r2", "r2", "r3", "r3", "r3"]
    cols = ["c1", "c2", "c3"] * 3
    trt = ["A", "B", "C", "B", "C", "A", "C", "A", "B"]
    vals = [5, 11, 14, 11, 20, 2, 14, 5, 8]
    return pd.DataFrame(
        {"yield": vals, "treatment": trt, "row": rows, "col": cols}
    )


def factorial_df() -> pd.DataFrame:
    groups = [
        (7.5, "A1", "B1"), (8.5, "A1", "B2"),
        (10.5, "A2", "B1"), (13.5, "A2", "B2"),
    ]
    rows: list[dict] = []
    for mean, a, b in groups:
        rows.append({"yield": mean - 1, "treatment": a, "factor_b": b})
        rows.append({"yield": mean, "treatment": a, "factor_b": b})
        rows.append({"yield": mean, "treatment": a, "factor_b": b})
        rows.append({"yield": mean + 1, "treatment": a, "factor_b": b})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- CRD
def test_crd_anova_matches_hand_computed():
    res = ExpDesignAnalysis().run(
        crd_df(), {"design": "crd", "alpha": 0.05}, {"outcome": "yield", "treatment": "treatment"}, _ctx()
    )
    aov = _f("anova", res)
    assert aov.loc[aov["Source"] == "Treatment", "SS"].iloc[0] == pytest.approx(288.0)
    assert aov.loc[aov["Source"] == "Treatment", "df"].iloc[0] == 2
    assert aov.loc[aov["Source"] == "Error", "df"].iloc[0] == 9
    assert aov.loc[aov["Source"] == "Treatment", "F"].iloc[0] == pytest.approx(54.0)
    # cross-check against scipy reference
    fb = stats.f_oneway(*[g for _, g in crd_df().groupby("treatment")["yield"]])
    assert aov.loc[aov["Source"] == "Treatment", "p"].iloc[0] == pytest.approx(fb.pvalue)
    means = _f("treatment_means", res)
    assert dict(zip(means["treatment"], means["mean"], strict=False)) == {"A": 4.0, "B": 10.0, "C": 16.0}
    assert res.what_does_not_tell.strip() != ""


def test_crd_mean_separation_letters():
    res = ExpDesignAnalysis().run(
        crd_df(), {"design": "crd", "alpha": 0.05}, {"outcome": "yield", "treatment": "treatment"}, _ctx()
    )
    means = _f("treatment_means", res)
    # All three means differ (6+) well beyond the HSD threshold -> 3 letters.
    assert means["group"].nunique() == 3


# ---------------------------------------------------------------- RCBD
def test_rcbd_removes_block_from_error():
    res = ExpDesignAnalysis().run(
        rcbd_df(), {"design": "rcbd", "alpha": 0.05}, {"outcome": "yield", "treatment": "treatment", "block": "block"}, _ctx()
    )
    aov = _f("anova", res)
    assert aov.loc[aov["Source"] == "Treatment", "SS"].iloc[0] == pytest.approx(288.0)
    assert aov.loc[aov["Source"] == "Block", "SS"].iloc[0] == pytest.approx(30.0)
    assert aov.loc[aov["Source"] == "Error", "SS"].iloc[0] == pytest.approx(4.0)
    assert aov.loc[aov["Source"] == "Error", "df"].iloc[0] == 6
    f_trt = aov.loc[aov["Source"] == "Treatment", "F"].iloc[0]
    assert f_trt == pytest.approx(144.0 / (4.0 / 6.0))
    assert aov.loc[aov["Source"] == "Total", "SS"].iloc[0] == pytest.approx(322.0)


# ---------------------------------------------------------------- Latin
def test_latin_square():
    res = ExpDesignAnalysis().run(
        latin_df(), {"design": "latin-square", "alpha": 0.05}, {"outcome": "yield", "treatment": "treatment", "row": "row", "col": "col"}, _ctx()
    )
    aov = _f("anova", res)
    assert aov.loc[aov["Source"] == "Treatment", "SS"].iloc[0] == pytest.approx(216.0)
    assert aov.loc[aov["Source"] == "Row", "SS"].iloc[0] == pytest.approx(6.0)
    assert aov.loc[aov["Source"] == "Column", "SS"].iloc[0] == pytest.approx(24.0)
    assert aov.loc[aov["Source"] == "Error", "SS"].iloc[0] == pytest.approx(6.0)
    f = aov.loc[aov["Source"] == "Treatment", "F"].iloc[0]
    assert f == pytest.approx(36.0)
    # p via scipy reference
    assert aov.loc[aov["Source"] == "Treatment", "p"].iloc[0] == pytest.approx(stats.f.sf(36.0, 2, 2))


# ---------------------------------------------------------------- factorial
def test_factorial_two_way():
    res = ExpDesignAnalysis().run(
        factorial_df(),
        {"design": "factorial", "alpha": 0.05},
        {"outcome": "yield", "treatment": "treatment", "factor_b": "factor_b"},
        _ctx(),
    )
    aov = _f("anova", res)
    assert aov.loc[aov["Source"] == "Factor A (treatment)", "SS"].iloc[0] == pytest.approx(64.0)
    assert aov.loc[aov["Source"] == "Factor B", "SS"].iloc[0] == pytest.approx(16.0)
    assert aov.loc[aov["Source"] == "Interaction A x B", "SS"].iloc[0] == pytest.approx(4.0)
    assert aov.loc[aov["Source"] == "Error", "SS"].iloc[0] == pytest.approx(8.0)
    f_ab = aov.loc[aov["Source"] == "Interaction A x B", "F"].iloc[0]
    assert f_ab == pytest.approx(6.0)
    # interaction p vs scipy
    assert aov.loc[aov["Source"] == "Interaction A x B", "p"].iloc[0] == pytest.approx(stats.f.sf(6.0, 1, 12))


# ---------------------------------------------------------------- guardrails
def test_rcbd_refuses_without_block():
    with pytest.raises(AssumptionError):
        ExpDesignAnalysis().run(
            rcbd_df(), {"design": "rcbd", "alpha": 0.05}, {"outcome": "yield", "treatment": "treatment"}, _ctx()
        )


def test_latin_refuses_missing_row_col():
    refusals = ExpDesignAnalysis().check_fit(
        None, {"design": "latin-square"}, {"outcome": "yield", "treatment": "treatment"}
    )
    assert any("row" in r and "col" in r for r in refusals)


def test_factorial_refuses_missing_second_factor():
    refusals = ExpDesignAnalysis().check_fit(
        None, {"design": "factorial"}, {"outcome": "yield", "treatment": "treatment"}
    )
    assert any("factor_b" in r for r in refusals)


def test_unbalanced_refused():
    df = crd_df().drop(index=0)  # 3/4/4 reps -> unbalanced
    with pytest.raises(AssumptionError):
        ExpDesignAnalysis().run(
            df, {"design": "crd"}, {"outcome": "yield", "treatment": "treatment"}, _ctx()
        )


def test_single_observation_treatment_refused():
    df = crd_df()
    df = pd.concat([df, pd.DataFrame({"yield": [99.0], "treatment": ["D"]})])
    with pytest.raises(AssumptionError):
        ExpDesignAnalysis().run(
            df, {"design": "crd"}, {"outcome": "yield", "treatment": "treatment"}, _ctx()
        )


def test_unknown_design_refused():
    refusals = ExpDesignAnalysis().check_fit(
        None, {"design": "split-plot"}, {"outcome": "yield", "treatment": "treatment"}
    )
    assert any("unknown" in r for r in refusals)


def test_missing_values_excluded_with_warning():
    df = crd_df()
    df.loc[0, "yield"] = np.nan
    res = ExpDesignAnalysis().run(
        df, {"design": "crd"}, {"outcome": "yield", "treatment": "treatment"}, _ctx()
    )
    assert len(res.warnings) >= 1
    assert any("missing" in w.lower() for w in res.warnings)
