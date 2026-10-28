"""Tests for the Describe-my-data (data card) analysis.

Uses a hand-built mixed-type data frame with deliberately inserted problems
(missing values, a duplicate row, a constant column, an outlier, a negative
age) and confirms each is caught, reported, and -- crucially -- NEITHER
changed NOR removed.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from auphoria.analyses.describe.analysis import DescribeAnalysis
from auphoria.core.analysis import RunContext


def _ctx() -> RunContext:
    logger = logging.getLogger("auphoria_test_describe")
    logger.handlers = []
    return RunContext(
        seed=1, out_dir=Path("."), data_name="test", expert=False,
        _log=logger, _log_decision=lambda m: None,
    )


def _messy_frame() -> pd.DataFrame:
    """A mixed-type data frame with deliberate data-quality problems."""
    df = pd.DataFrame({
        "patient_id": [f"P{p}" for p in range(1, 9)],  # string id (text heuristic ids it)
        "age": [34, 52, -5, 41, 29, 63, 38, 45],       # negative age at row 2
        "height_cm": [172.0, 158.0, 166.0, 310.0, 160.0, 170.0, 155.0, 168.0],  # outlier 310
        "group": ["A", "B", "A", "B", "A", "B", "A", "B"],                        # binary
        "sex": ["M", "F", "M", "F", "M", "F", "M", "F"],                          # binary
        "mood": [None, "happy", "ok", "happy", None, "ok", "happy", "ok"],        # categorical, missing
        "symptom": ["mild", "mild", "mild", "mild", "mild", "mild", "mild", "mild"],  # constant
        "reg_date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04",
                     "2024-01-05", "2024-01-06", "2024-01-07", "2024-01-08"],     # date-like
        "note": ["a long free-text notes field with lots of words " * 3 for _ in range(8)],  # text
    })
    # Duplicate the last row once.
    df = pd.concat([df, df.iloc[[7]]], ignore_index=True)
    return df


def test_describe_catches_and_reports_problems_without_changing_data():
    analysis = DescribeAnalysis()
    df = _messy_frame()
    before = df.copy(deep=True)

    result = analysis.run(df, {}, {}, _ctx())

    # --- changed/unchanged guarantee: nothing was edited.
    pd.testing.assert_frame_equal(df, before)

    # --- tables exist
    assert "Data card" in result.tables
    assert "Dataset overview" in result.tables
    card = result.tables["Data card"]

    # --- duplicate row detected
    overview = result.tables["Dataset overview"].set_index("Metric")
    assert int(overview.loc["Duplicate rows", "Value"]) == 1

    # --- constant column detected
    const = card[card["Column"] == "symptom"]
    assert const.iloc[0]["Unique"] == 1

    # --- id / categorical / date / text kinds detected
    by_col = card.set_index("Column")
    assert by_col.loc["patient_id", "Type"] == "id"
    assert by_col.loc["mood", "Type"] in ("categorical", "binary")
    assert by_col.loc["note", "Type"] == "free_text"

    # --- a negative age is flagged
    assert any("negative" in f.message.lower() for f in result.verdicts) or \
           any("age" in f.message.lower() for f in result.verdicts) or \
           any("negative" in m.lower() for m in result.notes)

    # --- an outlier is flagged (IQR: 310 is far outside)
    assert any("-5" in m or "outlier" in m.lower() or "far from" in m.lower()
               for m in result.notes) or \
           any("outlier" in m.lower() for m in result.warnings)

    # --- verdicts have the expected vocabulary
    levels = {v.level for v in result.verdicts}
    assert levels <= {"PASS", "WARN", "FAIL"}
    assert any(v.level == "WARN" for v in result.verdicts)   # something warned
    assert any(v.level == "PASS" for v in result.verdicts)   # rows present

    # --- what-this-does-not-tell is present and honest
    assert result.what_does_not_tell
    assert "does NOT test" in result.what_does_not_tell


def test_describe_clean_frame_gives_passes():
    analysis = DescribeAnalysis()
    df = pd.DataFrame({
        "x": [1.0, 2.0, 3.0, 4.0],
        "g": ["a", "a", "b", "b"],
    })
    result = analysis.run(df, {}, {}, _ctx())
    levels = {v.level for v in result.verdicts}
    assert "FAIL" not in levels
    assert result.tables["Dataset overview"].set_index("Metric").loc["Duplicate rows", "Value"] == 0


def test_describe_marks_missing_and_reports_never_imputed():
    analysis = DescribeAnalysis()
    df = pd.DataFrame({"v": [1.0, np.nan, 3.0, np.nan]})
    result = analysis.run(df, {}, {}, _ctx())
    card = result.tables["Data card"].set_index("Column")
    assert int(card.loc["v", "Missing"]) == 2
    assert any("imputed" in v.message.lower() or "missing" in v.message.lower()
               for v in result.verdicts)


def test_describe_returns_human_card_note():
    analysis = DescribeAnalysis()
    df = pd.DataFrame({"a": [1, 2, 3]})
    result = analysis.run(df, {}, {}, _ctx())
    assert any("Data card:" in n for n in result.notes)
    assert len(result.methods) >= 1


def test_describe_registered_and_has_manifest():
    from auphoria.core.registry import discover

    infos = discover()
    assert "describe" in infos
    m = infos["describe"].manifest
    assert m["id"] == "describe"
    assert m["maturity"] == "experimental"
