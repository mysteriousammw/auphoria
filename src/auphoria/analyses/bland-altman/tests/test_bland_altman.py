"""Tests for the Bland-Altman agreement analysis.

Uses small synthetic data with known, hand-computable answers and a larger
random dataset cross-checked against a simple in-test hand routine.

The analysis folder is 'bland-altman' (hyphenated, like the registry id), so
the module is loaded with importlib the same way the registry loads it.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from auphoria.core.analysis import RunContext
from auphoria.core.errors import AssumptionError

# Hyphenated module names cannot use the `import` statement; importlib is how
# auphoria.core.registry.load_analysis loads this module at runtime.
_BA_MODULE = importlib.import_module("auphoria.analyses.bland-altman.analysis")
BlandAltmanAnalysis = _BA_MODULE.BlandAltmanAnalysis


def _ctx() -> RunContext:
    logger = logging.getLogger("auphoria_test_bland_altman")
    logger.handlers = []
    return RunContext(
        seed=1,
        out_dir=Path("."),
        data_name="test",
        expert=False,
        _log=logger,
        _log_decision=lambda m: None,
    )


def _df(method_a: list[float], method_b: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"method_a": method_a, "method_b": method_b})


# Hand-computed example: differences (A - B) = -0.2, 0.1, -0.1, 0.0, 0.1.
# mean (bias) = -0.02; sample SD = sqrt(0.068 / 4) = 0.130384;
# 95% LoA = -0.02 +/- 1.96 * 0.130384 -> lower -0.2756, upper 0.2356.
METHOD_A = [1.0, 2.0, 3.0, 4.0, 5.0]
METHOD_B = [1.2, 1.9, 3.1, 4.0, 4.9]
EXPECTED_BIAS = -0.02
EXPECTED_SD = 0.130384
EXPECTED_LOWER = EXPECTED_BIAS - 1.96 * EXPECTED_SD  # -0.2756
EXPECTED_UPPER = EXPECTED_BIAS + 1.96 * EXPECTED_SD  # 0.2356


def _run(
    df: pd.DataFrame, params: dict | None = None
):
    analysis = BlandAltmanAnalysis()
    return analysis.run(
        df, params or {"alpha": 0.05},
        {"method_a": "method_a", "method_b": "method_b"}, _ctx(),
    )


def test_bland_altman_hand_computed_fixture():
    result = _run(_df(METHOD_A, METHOD_B))
    t = result.tables["Agreement statistics"]
    val = dict(zip(t["Item"], t["Value"], strict=False))
    assert int(val["number of pairs (n)"]) == 5
    assert float(val["mean difference (bias)"]) == pytest.approx(EXPECTED_BIAS, abs=1e-4)
    assert float(val["SD of differences"]) == pytest.approx(EXPECTED_SD, abs=1e-3)
    assert float(val["95% LoA lower"]) == pytest.approx(EXPECTED_LOWER, abs=1e-3)
    assert float(val["95% LoA upper"]) == pytest.approx(EXPECTED_UPPER, abs=1e-3)
    # The bias summary matches the hand figure.
    assert result.summaries["bias (mean difference)"] == "-0.02"
    assert result.summaries["SD of differences"] == "0.13"


def test_bland_altman_cross_checks_larger_random_dataset():
    rng = np.random.default_rng(7)
    n = 40
    a = rng.normal(50.0, 10.0, n)
    b = a + rng.normal(0.5, 2.0, n)  # small positive bias, no proportional bias
    df = pd.DataFrame({"method_a": a, "method_b": b})
    result = _run(df)

    diff = a - b
    (a + b) / 2.0
    hand_bias = float(diff.mean())
    hand_sd = float(np.std(diff, ddof=1))
    hand_lower = hand_bias - 1.96 * hand_sd
    hand_upper = hand_bias + 1.96 * hand_sd

    t = result.tables["Agreement statistics"]
    val = dict(zip(t["Item"], t["Value"], strict=False))
    assert float(val["mean difference (bias)"]) == pytest.approx(hand_bias, abs=1e-3)
    assert float(val["SD of differences"]) == pytest.approx(hand_sd, abs=1e-3)
    assert float(val["95% LoA lower"]) == pytest.approx(hand_lower, abs=1e-3)
    assert float(val["95% LoA upper"]) == pytest.approx(hand_upper, abs=1e-3)
    # SE of the bias matches SD / sqrt(n).
    assert float(val["SE of bias"]) == pytest.approx(hand_sd / np.sqrt(n), abs=1e-4)


def test_bland_altman_refuses_fewer_than_three_pairs():
    df = _df([1.0, 2.0], [0.9, 2.1])
    with pytest.raises(AssumptionError):
        _run(df)
    # After listwise deletion only 2 pairs survive.
    df3 = pd.DataFrame(
        {
            "method_a": [1.0, np.nan, 3.0, 4.0],
            "method_b": [np.nan, 2.0, 3.1, 3.9],
        }
    )
    with pytest.raises(AssumptionError):
        _run(df3)


def test_bland_altman_refuses_non_numeric_text():
    df = pd.DataFrame(
        {"method_a": [1.0, 2.0, 3.0, 4.0, 5.0], "method_b": [1.2, "x", 3.1, 4.0, 4.9]}
    )
    with pytest.raises(AssumptionError, match="text that cannot become a number"):
        _run(df)


def test_bland_altman_drops_missing_with_warning_not_imputed():
    df = _df(METHOD_A, METHOD_B)
    df.loc[0, "method_a"] = np.nan
    result = _run(df)
    t = result.tables["Agreement statistics"]
    val = dict(zip(t["Item"], t["Value"], strict=False))
    assert int(val["number of pairs (n)"]) == 4
    assert any("row(s)" in w and "missing" in w for w in result.warnings)
    assert any("no missing values were imputed" in m for m in result.methods)


def test_bland_altman_warns_on_proportional_bias():
    # Differences scale linearly with magnitude -> clear proportional bias.
    m = np.linspace(1.0, 20.0, 30)
    a = m
    b = 0.9 * m
    result = _run(pd.DataFrame({"method_a": a, "method_b": b}))
    verdict = next(v for v in result.verdicts if v.check == "proportional-bias")
    assert verdict.level == "WARN"
    assert result.summaries["proportional bias"].startswith("flagged")
    prop = result.tables["Proportional-bias check"]
    pval = prop.loc[prop["Item"] == "p-value", "Value"].iloc[0]
    assert pval == "< 0.001"


def test_bland_altman_returns_figure_methods_and_caveat():
    result = _run(_df(METHOD_A, METHOD_B))
    assert len(result.figures) == 1
    assert result.figures[0].name == "bland_altman_plot"
    assert len(result.methods) >= 2
    assert any("Bland-Altman" in m for m in result.methods)
    # Honest caveat must be present and non-empty.
    assert result.what_does_not_tell.strip()
    assert "NOT a pass/fail" in result.what_does_not_tell
    assert "roughly normally distributed" in result.what_does_not_tell
    assert "significant t-test" in result.what_does_not_tell
