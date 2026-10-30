"""Tests for the sequence-translation analysis.

Hand-checked fixtures (standard code, forward strand, ATG start):
  'ATGGCTTAATAA' frame 1: ATG GCT TAA TAA -> peptide 'MA**'
  'ATGGCCATGTTTTAA' frame 1: ATG GCC ATG TTT TAA -> 'MAMF*' (one ORF,
    inner ATG is consumed inside the first ORF)
  'GGGATGGCTTAA'    frame 1: GGG ATG GCT TAA -> ORF starts at base 4,
    peptide 'MA*'
  'ATGGCT'          frame 1 -> 'MA'
  RNA input 'AUGGCU' converts U->T and gives 'MA'
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
import pytest

from auphoria.core.analysis import AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

_MOD = importlib.import_module("auphoria.analyses.sequence-translation.analysis")
TranslationAnalysis = _MOD.SequenceTranslationAnalysis


def _ctx() -> RunContext:
    import logging

    logger = logging.getLogger("auphoria_tr_test")
    logger.handlers = []
    return RunContext(seed=1, out_dir=Path("."), data_name="test", expert=False,
                      _log=logger, _log_decision=lambda m: None)


def _run(seqs: list[str], **params) -> AnalysisResult:
    df = pd.DataFrame({"dna": seqs})
    p = {"min_orf_length": 3}
    p.update(params)
    return TranslationAnalysis().run(df, p, {"sequence": "dna"}, _ctx())


def test_basic_translation_frame1():
    res = _run(["ATGGCT"])
    t = res.tables["translations"]
    row = t[(t["frame"] == 1)].iloc[0]
    assert row["translation"] == "MA"


def test_rna_u_converted():
    res = _run(["AUGGCU"])
    t = res.tables["translations"]
    assert t[t["frame"] == 1].iloc[0]["translation"] == "MA"


def test_orf_found_including_stop():
    # ATG GCT TAA TAA -> first ORF stops at the first TAA (bases 7-9).
    res = _run(["ATGGCTTAATAA"])
    orf = res.tables["orfs"]
    assert len(orf) == 1
    r = orf.iloc[0]
    assert r["start"] == 1 and r["end"] == 9
    assert r["length_aa"] == 3
    assert r["peptide"] == "MA*"
    assert r["longest"] == "yes"


def test_inner_atg_consumed_by_first_orf():
    res = _run(["ATGGCCATGTTTTAA"])
    orf = res.tables["orfs"]
    assert len(orf) == 1
    r = orf.iloc[0]
    assert r["start"] == 1
    assert r["length_aa"] == 5
    assert r["peptide"] == "MAMF*"


def test_orf_offset_frame():
    res = _run(["GGGATGGCTTAA"])
    orf = res.tables["orfs"]
    assert len(orf) == 1
    r = orf.iloc[0]
    assert r["start"] == 4
    assert r["peptide"] == "MA*"


def test_min_length_filters():
    # 'ATGGCTTAA' is a 3-aa ORF (ATG GCT TAA): shown at min 3, filtered at min 5.
    shown = _run(["ATGGCTTAA"], min_orf_length=3)
    assert len(shown.tables["orfs"]) == 1
    filtered = _run(["ATGGCTTAA"], min_orf_length=5)
    assert len(filtered.tables["orfs"]) == 0
    assert any("No ORF" in w for w in filtered.warnings)


def test_no_orf_warns():
    res = _run(["TTTTTT"], min_orf_length=3)
    assert len(res.tables["orfs"]) == 0
    assert any("No ORF" in w for w in res.warnings)


def test_ambiguous_base_refused():
    with pytest.raises(AssumptionError, match="N"):
        _run(["ATGNGC"])


def test_blank_rows_skipped():
    res = _run(["ATGGCT", ""])
    assert len(res.warnings) >= 1
    assert len(res.tables["translations"]) == 3  # 3 frames for 1 row


def test_what_does_not_tell_present():
    res = _run(["ATGGCT"])
    assert res.what_does_not_tell.strip() != ""
