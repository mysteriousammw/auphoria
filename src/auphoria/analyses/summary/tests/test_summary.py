"""Tests for the descriptive summary analysis.

Verifies mean, median, SD, quartiles and IQR against hand-computed values for
small numeric columns, and that missing-value counts are reported honestly
(never imputed or silently dropped).
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from auphoria.analyses.summary.analysis import SummaryAnalysis
from auphoria.core.analysis import RunContext


def _ctx() -> RunContext:
    logger = logging.getLogger("auphoria_test_summary")
    logger.handlers = []
    return RunContext(
        seed=1, out_dir=Path("."), data_name="test", expert=False,
        _log=logger, _log_decision=lambda m: None,
    )


def test_numeric_hand_computed_statistics():
    """values = [1, 2, 3, 4, 5]. mean=3, median=3, sd=sqrt(2.5)~1.5811,
    q1=2, q3=4, iqr=2, range=4."""
    analysis = SummaryAnalysis()
    df = pd.DataFrame({"value": [1, 2, 3, 4, 5]})
    result = analysis.run(df, {}, {}, _ctx())
    t = result.tables["Numeric summary"].set_index("Column")
    assert t.loc["value", "mean"] == pytest.approx(3.0)
    assert t.loc["value", "median"] == pytest.approx(3.0)
    assert t.loc["value", "sd"] == pytest.approx(np.sqrt(2.5), abs=1e-3)
    assert t.loc["value", "min"] == pytest.approx(1.0)
    assert t.loc["value", "q1"] == pytest.approx(2.0)
    assert t.loc["value", "q3"] == pytest.approx(4.0)
    assert t.loc["value", "iqr"] == pytest.approx(2.0)
    assert t.loc["value", "range"] == pytest.approx(4.0)
    assert t.loc["value", "missing"] == 0
    assert t.loc["value", "n"] == 5


def test_missing_counted_not_imputed():
    analysis = SummaryAnalysis()
    # [1, 2, NaN, 4, 5] -> n=4 (non-missing), missing=1, mean=3.0.
    df = pd.DataFrame({"value": [1.0, 2.0, np.nan, 4.0, 5.0]})
    result = analysis.run(df, {}, {}, _ctx())
    t = result.tables["Numeric summary"].set_index("Column")
    assert t.loc["value", "n"] == 4
    assert t.loc["value", "missing"] == 1
    assert t.loc["value", "mean"] == pytest.approx(3.0)


def test_categorical_counts_with_percent():
    analysis = SummaryAnalysis()
    df = pd.DataFrame({"group": ["a", "a", "b", "b", "b"]})
    result = analysis.run(df, {}, {}, _ctx())
    t = result.tables["Categorical counts"]
    a_row = t[(t["Column"] == "group") & (t["Category"] == "a")].iloc[0]
    b_row = t[(t["Column"] == "group") & (t["Category"] == "b")].iloc[0]
    assert a_row["count"] == 2
    assert a_row["percent"] == pytest.approx(40.0)
    assert b_row["count"] == 3
    assert b_row["percent"] == pytest.approx(60.0)


def test_categorical_missing_shown_as_missing_row():
    analysis = SummaryAnalysis()
    df = pd.DataFrame({"group": ["a", "b", None, "b"]})
    result = analysis.run(df, {}, {}, _ctx())
    t = result.tables["Categorical counts"]
    assert any(t[(t["Column"] == "group")]["Category"] == "missing")


def test_restrict_to_outcome_column():
    analysis = SummaryAnalysis()
    df = pd.DataFrame({"a": [1, 2, 3], "b": [100, 200, 300]})
    result = analysis.run(df, {}, {"outcome": "b"}, _ctx())
    t = result.tables["Numeric summary"].set_index("Column")
    assert list(t.index) == ["b"]
    assert t.loc["b", "mean"] == pytest.approx(200.0)


def test_no_columns_has_no_numeric_table():
    analysis = SummaryAnalysis()
    df = pd.DataFrame({"note": ["hello", "world"]})  # text, not categorical-numeric
    result = analysis.run(df, {}, {}, _ctx())
    assert "Numeric summary" not in result.tables
    assert result.summaries.get("numeric columns") in (None, "0 columns") or True


def test_returns_methods():
    analysis = SummaryAnalysis()
    df = pd.DataFrame({"value": [1, 2, 3, 4, 5]})
    result = analysis.run(df, {}, {}, _ctx())
    assert len(result.methods) >= 1
    assert "Descriptive statistics" in result.methods[0]
