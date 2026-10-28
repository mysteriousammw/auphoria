"""Tests for Phase 2 core: pydantic manifest validation, data card profiling,
verdicts/decision log, and the guarantee that no code path mutates user data
without logging it."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from auphoria.adapters.adapters import read_data_frame
from auphoria.core.analysis import RunContext
from auphoria.core.data_card import profile_data_card
from auphoria.core.errors import ConfigError
from auphoria.core.manifest import validate_manifest


# ------------------------------------------------------------------ errors
def test_error_classes_have_hint_and_to_user():
    from auphoria.core.errors import AuphoriaError, DataError, InputValidationError

    for cls in (AuphoriaError, DataError, InputValidationError):
        e = cls("plain message", hint="a fix")
        assert "plain message" in e.to_user()
        assert "a fix" in e.to_user()
        assert isinstance(str(e), str)


def test_data_error_no_hint_still_readable():
    from auphoria.core.errors import DataError

    e = DataError("only message")
    assert e.to_user() == "only message"


# ---------------------------------------------------------- manifest (pydantic)
def test_valid_manifest_and_missing_key(tmp_path: Path):
    p = tmp_path / "manifest.yaml"
    p.write_text(
        "id: summary\n"
        "name: Summary\n"
        "maturity: experimental\n"
        "inputs: []\n"
        "parameters: []\n"
        "levels: [beginner]\n"
        "disciplines: [health]\n",
        encoding="utf-8",
    )
    data = validate_manifest(p)
    assert data["id"] == "summary"
    assert data["maturity"] == "experimental"


def test_invalid_manifest_clear_error_bad_kind(tmp_path: Path):
    p = tmp_path / "bad.yaml"
    p.write_text(
        "id: x\nname: X\nmaturity: experimental\n"
        "inputs:\n  - name: outcome\n    kind: nonsense-kind\n"
        "parameters: []\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError) as ei:
        validate_manifest(p)
    # The pydantic error names the offending field.
    assert "nonsense-kind" in str(ei.value.hint) or "kind" in str(ei.value.hint)


def test_invalid_manifest_bad_parameter_type(tmp_path: Path):
    p = tmp_path / "bad2.yaml"
    p.write_text(
        "id: y\nname: Y\nmaturity: experimental\ninputs: []\n"
        "parameters:\n  - name: alpha\n    type: not-a-type\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        validate_manifest(p)


# ------------------------------------------------------------ data card types
def test_data_card_detects_all_kinds():
    df = pd.DataFrame({
        "num": [1.5, 2.5, 3.5, 4.5],
        "ord": [1, 2, 3, 2],                    # integer, few distinct -> ordinal
        "cat": ["apple", "banana", "apple", "cherry"],
        "flag": [True, False, True, False],     # binary
        "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]),
        "subject": ["S1", "S2", "S3", "S4"],    # id (name hint + unique)
        "note": ["long free text " * 20 for _ in range(4)],  # free_text
    })
    card = profile_data_card(df)
    by = {c.name: c.kind for c in card.columns}
    assert by["num"] == "numeric"
    assert by["ord"] == "ordinal"
    assert by["cat"] == "categorical"
    assert by["flag"] == "binary"
    assert by["date"] == "date"
    assert by["subject"] == "id"
    assert by["note"] == "free_text"
    # date column gets time role; id gets id role.
    roles = {c.name: c.suggested_role for c in card.columns}
    assert roles["date"] == "time"
    assert roles["subject"] == "id"


def test_data_card_missing_and_duplicates():
    df = pd.DataFrame({"a": [1, 1, np.nan, 3], "b": ["x", "x", "y", "z"]})
    # duplicate row: (1, 'x') twice
    card = profile_data_card(df)
    assert card.n_duplicate_rows == 1
    assert card.by_name("a").n_missing == 1
    assert any("uplicate" in f.message for f in card.flags)
    # duplicate row flag is a NOTE not a removal
    assert all(f.level in ("WARN", "NOTE") for f in card.flags)


def test_data_card_flags_outlier_but_keeps_row():
    df = pd.DataFrame({"v": [10, 11, 10, 12, 11, 300]})  # 300 is an IQR outlier
    card = profile_data_card(df)
    outlier_flag = [f for f in card.flags if "far from" in f.message]
    assert outlier_flag, "expected an IQR outlier flag"
    # The outlier is NOT removed (flag only).
    assert df["v"].iloc[-1] == 300


def test_data_card_flags_negative_age_but_keeps_value():
    df = pd.DataFrame({"age": [34, -5, 45, 22]})
    card = profile_data_card(df)
    assert any("negative" in f.message.lower() for f in card.flags)
    assert -5 in df["age"].values  # unchanged


def test_data_card_constant_column_flagged():
    df = pd.DataFrame({"g": ["a", "a", "a", "a"], "x": [1, 2, 3, 4]})
    card = profile_data_card(df)
    assert any("only 1 distinct" in f.message for f in card.flags)


def test_data_card_marks_role_no_mutation():
    df = pd.DataFrame({"outcome": [1, 2, 3], "grp": ["a", "a", "b"]})
    before = df.copy(deep=True)
    profile_data_card(df)
    pd.testing.assert_frame_equal(df, before)


# -------------------------------------------------------- verdicts, decision log
def _ctx() -> RunContext:
    import logging

    logger = logging.getLogger("auphoria_test_p2")
    logger.handlers = []
    return RunContext(
        seed=1, out_dir=Path("."), data_name="test", expert=False,
        _log=logger, _log_decision=lambda m: None,
        input_sha256="abcd", package_versions={"numpy": "2.0"},
        parameters={"alpha": 0.05},
    )


def test_run_context_logs_decisions_with_metadata():
    ctx = _ctx()
    ctx.log_decision("checked normality; data not normal")
    events = ctx.decision_log
    assert len(events) == 1
    assert events[0].message == "checked normality; data not normal"
    assert events[0].at  # timestamp present
    assert ctx.input_sha256 == "abcd"
    assert ctx.package_versions["numpy"] == "2.0"
    assert ctx.parameters["alpha"] == 0.05
    assert len(ctx.decision_log_dicts()) == 1


def test_verdict_add_render():
    from auphoria.core.analysis import AnalysisResult

    r = AnalysisResult()
    r.add_verdict("WARN", "small-sample", "n is only 4; results are preliminary.")
    r.add_verdict("PASS", "rows-present", "There are rows.")
    assert len(r.verdicts) == 2
    assert r.verdicts[0].level == "WARN"
    assert r.verdicts[0].as_dict()["check"] == "small-sample"
    assert r.what_does_not_tell == ""  # default honest-empty


# ------------------------------------------------ no data changed without logging
def test_read_data_frame_never_mutates_input(path_with_spaces):
    """Reading must leave the on-disk file byte-for-byte identical."""
    p, original_bytes = path_with_spaces
    _df, warnings = read_data_frame(p)
    assert p.read_bytes() == original_bytes


@pytest.fixture
def path_with_spaces(tmp_path: Path):
    d = tmp_path / "Data Folder"
    d.mkdir()
    p = d / "survey data.csv"
    data = b"id,score,grp\n1,10,a\n2,20,b\n\n3,15,c\n"
    p.write_bytes(data)
    return p, data
