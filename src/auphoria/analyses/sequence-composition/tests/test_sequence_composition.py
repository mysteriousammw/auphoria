"""Tests for the sequence-composition analysis.

Hand-computed values:
  'ATGCGC' (DNA) -> length 6, GC = (G2+C2)/6 = 66.67%, counts A1 T1 G2 C2
  'AUGC'   (RNA) -> length 4, GC = 50%, U detected -> alphabet RNA
  'ATGC'   (DNA) -> GC 50%, T counted
  mixed 'ATGU' auto -> refused (both T and U)
  bad letter 'AXGC' -> refused
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
import pytest

from auphoria.core.analysis import RunContext
from auphoria.core.errors import AssumptionError

_MOD = importlib.import_module("auphoria.analyses.sequence-composition.analysis")
Analysis = _MOD.SequenceCompositionAnalysis
Result = _MOD.AnalysisResult


def _ctx() -> RunContext:
    import logging

    logger = logging.getLogger("auphoria_seq_test")
    logger.handlers = []
    return RunContext(seed=1, out_dir=Path("."), data_name="test", expert=False,
                      _log=logger, _log_decision=lambda m: None)


def _run(seqs: list[str], **params) -> Result:
    df = pd.DataFrame({"seq": seqs})
    return Analysis().run(df, params or {}, {"sequence": "seq"}, _ctx())


def test_dna_gc_and_counts_hand_computed():
    res = _run(["ATGCGC"])
    t = res.tables["per_sequence_composition"]
    assert t.iloc[0]["length"] == 6
    assert t.iloc[0]["gc_percent"] == pytest.approx(round(100 * 4 / 6, 2))  # 66.67
    assert t.iloc[0]["A"] == 1 and t.iloc[0]["T"] == 1
    assert t.iloc[0]["G"] == 2 and t.iloc[0]["C"] == 2
    assert res.summaries["alphabet"] == "DNA"


def test_rna_detected():
    res = _run(["AUGC"])
    t = res.tables["per_sequence_composition"]
    assert t.iloc[0]["length"] == 4
    assert t.iloc[0]["gc_percent"] == pytest.approx(50.0)
    assert t.iloc[0]["U"] == 1
    assert res.summaries["alphabet"] == "RNA"


def test_multiple_sequences_aggregate():
    res = _run(["ATGC", "AT", "GC"])
    agg = res.tables["summary"]
    n = agg[agg["statistic"] == "n_sequences"]["value"].iloc[0]
    assert n == 3
    mean_gc = float(agg[agg["statistic"] == "mean_gc_percent"]["value"].iloc[0])
    # GC%: 50, 0, 100 -> mean 50
    assert mean_gc == pytest.approx(50.0)


def test_blank_rows_skipped_with_warning():
    res = _run(["ATGC", "", "GC"])
    assert len(res.warnings) >= 1
    assert len(res.tables["per_sequence_composition"]) == 2


def test_bad_letter_refused():
    with pytest.raises(AssumptionError, match="non-IUPAC"):
        _run(["AXGC"])


def test_mixed_tu_refused_in_auto():
    with pytest.raises(AssumptionError, match="BOTH T"):
        _run(["ATGU"])


def test_forced_dna_refuses_u():
    with pytest.raises(AssumptionError, match="U"):
        _run(["AUGC"], mode="dna")


def test_forced_rna_refuses_t():
    with pytest.raises(AssumptionError, match="T"):
        _run(["ATGC"], mode="rna")


def test_what_does_not_tell_present():
    res = _run(["ATGC"])
    assert res.what_does_not_tell.strip() != ""
