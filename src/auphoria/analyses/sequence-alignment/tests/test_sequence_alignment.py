"""Tests for the pairwise sequence-alignment analysis.

Hand-computed values (match=2, mismatch=-1, gap=-2):

  'ACGT' vs 'ACGT' (global): score = 4*2 = 8, identity 100%
  'ACGT' vs 'ACG'  (global): 'ACGT' vs 'ACG-' -> 3*2 - 2 = 4, identity 100%
  'ACGT' vs 'ACGA' (global): 3 matches + 1 mismatch = 3*2 - 1 = 5, id 75%
  'XXACGTYY' vs 'WWACGTZZ' (local): best region ACGT, score 8, id 100%
  'ACGU' vs 'ACGT': U normalised to T -> identity 100%
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
import pytest

from auphoria.core.analysis import AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

_MOD = importlib.import_module("auphoria.analyses.sequence-alignment.analysis")
AlignmentAnalysis = _MOD.SequenceAlignmentAnalysis


def _ctx() -> RunContext:
    import logging

    logger = logging.getLogger("auphoria_aln_test")
    logger.handlers = []
    return RunContext(seed=1, out_dir=Path("."), data_name="test", expert=False,
                      _log=logger, _log_decision=lambda m: None)


def _run(pairs: list[tuple[str, str]], mode: str = "global", **params) -> AnalysisResult:
    df = pd.DataFrame(pairs, columns=["a", "b"])
    p = {"mode": mode}
    p.update(params)
    return AlignmentAnalysis().run(df, p, {"sequence_a": "a", "sequence_b": "b"}, _ctx())


def test_identical_global():
    res = _run([("ACGT", "ACGT")])
    t = res.tables["alignments"]
    assert t.iloc[0]["score"] == 8
    assert t.iloc[0]["identity_percent"] == 100.0


def test_global_with_gap():
    res = _run([("ACGT", "ACG")])
    t = res.tables["alignments"]
    assert t.iloc[0]["score"] == 4
    assert t.iloc[0]["identity_percent"] == 100.0


def test_global_mismatch():
    res = _run([("ACGT", "ACGA")])
    t = res.tables["alignments"]
    assert t.iloc[0]["score"] == 5
    assert t.iloc[0]["identity_percent"] == 75.0


def test_local_finds_best_region():
    res = _run([("XXACGTYY", "WWACGTZZ")], mode="local")
    t = res.tables["alignments"]
    r = t.iloc[0]
    assert r["score"] == 8
    assert r["identity_percent"] == 100.0
    # aligned strings contain only the ACGT core
    assert "-" not in r["aligned_a"]
    assert r["aligned_a"] == "ACGT"
    assert r["aligned_b"] == "ACGT"


def test_u_equals_t():
    res = _run([("ACGU", "ACGT")])
    t = res.tables["alignments"]
    assert t.iloc[0]["identity_percent"] == 100.0


def test_protein_alphabet_accepted():
    res = _run([("MKT", "MKT")])
    assert res.tables["alignments"].iloc[0]["identity_percent"] == 100.0


def test_bad_characters_refused():
    with pytest.raises(AssumptionError):
        _run([("ACGT", "AC1T")])


def test_empty_rows_excluded_with_warning():
    res = _run([("ACGT", ""), ("AC", "AC")])
    assert len(res.warnings) >= 1
    assert len(res.tables["alignments"]) == 1


def test_both_columns_empty_refused():
    with pytest.raises(AssumptionError):
        _run([("", "")])


def test_unknown_mode_refused():
    with pytest.raises(AssumptionError, match="mode"):
        _run([("AC", "AC")], mode="semi")


def test_what_does_not_tell_present():
    res = _run([("ACGT", "ACGT")])
    assert res.what_does_not_tell.strip() != ""
