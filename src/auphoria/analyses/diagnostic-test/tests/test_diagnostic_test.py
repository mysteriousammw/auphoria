"""Tests for the diagnostic test performance analysis.

Uses a tiny, deterministic dataset whose confusion matrix is hand-computable
at the Youden threshold, and compares the AUC against sklearn's reference
implementation (roc_auc_score).

Hand-computed values for the main dataset (10 rows, five 'no' then five 'yes'):
  scores = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
  reference = ['no'] * 5 + ['yes'] * 5
Youden's J over the unique score thresholds pulls the first threshold with
sensitivity + specificity - 1 = 1, which is t = 6:
  pred = score >= 6  ->  TP = 5, FN = 0, TN = 5, FP = 0
  sensitivity = 5/5 = 1, specificity = 5/5 = 1, PPV = 5/5 = 1, NPV = 5/5 = 1
  prevalence  = 5/10 = 0.5
  AUC = 1.0 (all positives score above all negatives)
"""

from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

from auphoria.core.analysis import AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

# The analysis id contains a hyphen ('diagnostic-test'), which is not valid
# Python syntax in an import statement, so load the module by name.
_MODULE = importlib.import_module("auphoria.analyses.diagnostic-test.analysis")
DiagnosticTestAnalysis = _MODULE.DiagnosticTestAnalysis


def _ctx() -> RunContext:
    import logging

    logger = logging.getLogger("auphoria_diag_test")
    logger.handlers = []
    return RunContext(
        seed=1,
        out_dir=Path("."),
        data_name="test",
        expert=False,
        _log=logger,
        _log_decision=lambda m: None,
    )


def _tiny_df() -> pd.DataFrame:
    scores = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    ref = ["no", "no", "no", "no", "no", "yes", "yes", "yes", "yes", "yes"]
    return pd.DataFrame({"score": scores, "ref": ref})


def _run(df: pd.DataFrame, **params) -> AnalysisResult:
    return DiagnosticTestAnalysis().run(
        df,
        params,
        {"test": "score", "reference": "ref"},
        _ctx(),
    )


def _perf(result: AnalysisResult) -> pd.DataFrame:
    return result.tables["Performance"].set_index("Metric")


def test_sens_spec_ppv_npv_match_hand_values():
    result = _run(_tiny_df())
    perf = _perf(result)
    assert float(perf.loc["Sensitivity (TP/(TP+FN))", "Value"]) == pytest.approx(1.0, abs=1e-4)
    assert float(perf.loc["Specificity (TN/(TN+FP))", "Value"]) == pytest.approx(1.0, abs=1e-4)
    assert float(perf.loc["PPV (TP/(TP+FP))", "Value"]) == pytest.approx(1.0, abs=1e-4)
    assert float(perf.loc["NPV (TN/(TN+FN))", "Value"]) == pytest.approx(1.0, abs=1e-4)
    assert float(perf.loc["Disease prevalence", "Value"]) == pytest.approx(0.5, abs=1e-4)
    # The threshold preferred by Youden's J.
    assert float(perf.loc["Chosen threshold (score >= t)", "Value"]) == pytest.approx(6.0, abs=1e-6)


def test_confusion_matrix_hand_values():
    result = _run(_tiny_df())
    cm = result.tables["Confusion matrix"]
    # tp, then fp, then fn, then tn.
    assert int(cm.loc["Predicted positive", "Reference positive"]) == 5  # TP
    assert int(cm.loc["Predicted positive", "Reference negative"]) == 0  # FP
    assert int(cm.loc["Predicted negative", "Reference positive"]) == 0  # FN
    assert int(cm.loc["Predicted negative", "Reference negative"]) == 5  # TN


def test_auc_matches_sklearn():
    result = _run(_tiny_df())
    y = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
    scores = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    ref_auc = roc_auc_score(y, scores)
    perf = _perf(result)
    assert float(perf.loc["AUC", "Value"]) == pytest.approx(ref_auc, abs=1e-4)


def test_refuses_not_two_categories():
    df = pd.DataFrame(
        {"score": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0], "ref": ["a", "b", "c", "a", "b", "c"]}
    )
    with pytest.raises(AssumptionError, match="exactly two"):
        _run(df)


def test_refuses_single_class():
    df = pd.DataFrame(
        {"score": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0], "ref": ["yes"] * 6}
    )
    with pytest.raises(AssumptionError):
        _run(df)


def test_missing_listwise_exclusion_with_warning():
    df = _tiny_df()
    # Drop the highest 'no' row (row index 4, score 5) and the lowest 'yes'
    # row (row index 5, score 6) -> 8 complete rows remain.
    df.iloc[4, df.columns.get_loc("score")] = np.nan
    df.iloc[5, df.columns.get_loc("score")] = np.nan
    result = _run(df)
    # 2 rows excluded with a warning; none imputed.
    assert any("2 row(s)" in w and "missing" in w for w in result.warnings)
    perf = _perf(result)
    assert int(perf.loc["Total valid rows", "Value"]) == 8
    cm = result.tables["Confusion matrix"]
    assert int(cm.to_numpy().sum()) == 8  # every cell present, nothing imputed
    assert not cm.isna().any().any()


def test_figure_methods_and_honesty():
    result = _run(_tiny_df())
    assert len(result.figures) == 1
    assert result.figures[0].name == "roc_curve"
    assert len(result.methods) >= 3
    methods_text = " ".join(result.methods)
    assert "sensitivity" in methods_text and "specificity" in methods_text
    assert "AUC" in methods_text and "prevalence" in methods_text
    assert result.what_does_not_tell
    assert "threshold" in result.what_does_not_tell
    assert "prevalence" in result.what_does_not_tell
    assert "reference" in result.what_does_not_tell


def test_expert_review_and_verdicts_on_small_sample():
    # n = 10 < 20 -> sample-size WARN and expert review; classes 5/5 -> balance PASS.
    result = _run(_tiny_df())
    assert result.expert_review  # flagged for a statistician
    levels = {v.check: v.level for v in result.verdicts}
    assert levels["sample-size"] == "WARN"
    assert levels["class-balance"] == "PASS"


def test_small_imbalanced_class_expert_review():
    df = pd.DataFrame(
        {"score": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
         "ref": ["no", "no", "no", "no", "no", "no", "no", "yes", "yes", "yes"]}
    )
    result = _run(df)
    assert result.expert_review
    levels = {v.check: v.level for v in result.verdicts}
    assert levels["class-balance"] == "WARN"
