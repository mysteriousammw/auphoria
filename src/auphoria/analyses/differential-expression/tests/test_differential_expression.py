"""Tests for the differential-expression analysis.

Synthetic setup: 8 samples (4 treated / 4 control), 200 genes, where a known
set of genes is over-expressed in the treated group and a known set is
under-expressed. Counts are drawn from a negative-binomial distribution
(over-dispersion, like real RNA-seq).

The per-gene adjusted p-values in the results table are cross-checked against
a directly recomputed PyDESeq2 model on the same counts, so this is a
second-library-style repro of the analysis's own fit.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydeseq2.dds import DeseqDataSet
from pydeseq2.ds import DeseqStats

from auphoria.core.analysis import AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

# The analysis id contains a hyphen, which is not valid Python syntax in an
# import statement, so load the module by name the way the registry does.
_MOD = importlib.import_module("auphoria.analyses.differential-expression.analysis")
DifferentialExpressionAnalysis = _MOD.DifferentialExpressionAnalysis

N_GENES = 200
N_TREAT = 4
N_CONTROL = 4
BASE_MEAN = 50.0
EFFECT = 4.0
UP = list(range(10))     # genes 0..9  -> over-expressed in treated
DOWN = list(range(10, 20))  # genes 10..19 -> under-expressed in treated


def _ctx() -> RunContext:
    import logging

    logger = logging.getLogger("auphoria_de")
    logger.handlers = []
    return RunContext(
        seed=1,
        out_dir=Path("."),
        data_name="test",
        expert=False,
        _log=logger,
        _log_decision=lambda m: None,
    )


def _counts_df() -> pd.DataFrame:
    """A deterministic synthetic counts matrix (samples x genes)."""
    rng = np.random.default_rng(123)
    n = N_TREAT + N_CONTROL
    # Baseline negative-binomial counts across all samples/genes.
    counts = rng.negative_binomial(n=5, p=5 / (5 + BASE_MEAN), size=(n, N_GENES)).astype(float)
    # Over-expressed genes in the treated samples (first N_TREAT rows).
    counts[:N_TREAT, UP] = rng.negative_binomial(
        n=5, p=5 / (5 + BASE_MEAN * EFFECT), size=(N_TREAT, len(UP))
    ).astype(float)
    # Under-expressed genes in the treated samples.
    counts[:N_TREAT, DOWN] = rng.negative_binomial(
        n=5, p=5 / (5 + BASE_MEAN / EFFECT), size=(N_TREAT, len(DOWN))
    ).astype(float)
    sample_ids = [f"s{i}" for i in range(n)]
    gene_names = [f"g{j}" for j in range(N_GENES)]
    return pd.DataFrame(counts, index=sample_ids, columns=gene_names)


def _dataset() -> pd.DataFrame:
    df = _counts_df()
    df.insert(0, "condition", ["treat"] * N_TREAT + ["control"] * N_CONTROL)
    return df


def _run(df: pd.DataFrame, **params) -> AnalysisResult:
    return DifferentialExpressionAnalysis().run(
        df, params, {"condition": "condition"}, _ctx()
    )


def _recompute_reference(alpha: float = 0.05) -> pd.DataFrame:
    """Directly recompute a PyDESeq2 model on the same synthetic counts."""
    df = _dataset()
    counts = df.drop(columns=["condition"]).astype(float)
    meta = pd.DataFrame({"condition": df["condition"].astype(str)}, index=df.index)
    dds = DeseqDataSet(
        counts=counts,
        metadata=meta,
        design="~condition",
        refit_cooks=True,
        quiet=True,
    )
    dds.deseq2()
    stat = DeseqStats(dds, contrast=["condition", "treat", "control"], alpha=alpha, quiet=True)
    stat.summary()
    return stat.results_df


def test_results_table_shape_and_expected_de_genes():
    result = _run(_dataset())
    table = result.tables["Results"]
    # Columns required by the spec.
    for col in ("baseMean", "log2FoldChange", "lfcSE", "stat", "pvalue", "padj"):
        assert col in table.columns
    assert table.index.name == "gene"
    assert len(table) == N_GENES
    # The known over- and under-expressed genes are significantly differential.
    assert table.loc[[f"g{i}" for i in UP], "padj"].lt(0.05).mean() >= 0.8
    assert table.loc[[f"g{i}" for i in DOWN], "padj"].lt(0.05).mean() >= 0.8
    # Direction is sensible: up genes have positive log2FC, down genes negative.
    assert table.loc[[f"g{i}" for i in UP], "log2FoldChange"].mean() > 0
    assert table.loc[[f"g{i}" for i in DOWN], "log2FoldChange"].mean() < 0


def test_results_match_recomputed_deseq2_within_tolerance():
    result = _run(_dataset())
    table = result.tables["Results"]
    ref = _recompute_reference()
    # A couple of genes: include known DE and a neutral gene.
    for gene in ("g0", "g3", "g12", "g50"):
        got = float(table.loc[gene, "padj"])
        expected = float(ref.loc[gene, "padj"])
        if np.isnan(got) and np.isnan(expected):
            continue
        assert got == pytest.approx(expected, abs=1e-3)
        assert float(table.loc[gene, "log2FoldChange"]) == pytest.approx(
            float(ref.loc[gene, "log2FoldChange"]), abs=1e-3
        )


def test_volcano_figure_present():
    result = _run(_dataset())
    assert len(result.figures) == 1
    fig = result.figures[0]
    assert fig.name == "volcano_plot"
    assert "volcano" in fig.caption.lower()


def test_summary_up_down_positive():
    result = _run(_dataset())
    assert int(result.summaries["significant (padj < alpha)"]) > 0
    assert int(result.summaries["up-regulated"]) > 0
    assert int(result.summaries["down-regulated"]) > 0


def test_refuses_single_condition_category():
    df = _counts_df()
    df.insert(0, "condition", ["treat"] * (N_TREAT + N_CONTROL))
    with pytest.raises(AssumptionError, match="exactly two"):
        _run(df)


def test_refuses_three_condition_categories():
    df = _dataset().copy()
    df.loc[df.index[-1], "condition"] = "third"
    with pytest.raises(AssumptionError, match="exactly two"):
        _run(df)


def test_refuses_fewer_than_four_samples():
    df = _counts_df().iloc[:3].copy()
    df.insert(0, "condition", ["treat", "treat", "control"])
    with pytest.raises(AssumptionError, match="at least 4 sample"):
        _run(df)


def test_refuses_fewer_than_four_genes():
    df = _counts_df().iloc[:, :3].copy()
    df.insert(0, "condition", ["treat"] * N_TREAT + ["control"] * N_CONTROL)
    with pytest.raises(AssumptionError, match="count column"):
        _run(df)


def test_missing_counts_refused_with_clear_message():
    df = _dataset().copy()
    df.iloc[0, df.columns.get_loc("g21")] = np.nan
    with pytest.raises(AssumptionError, match="missing value"):
        _run(df)
    # Missing condition value is also refused.
    df2 = _dataset().copy()
    df2.iloc[1, df2.columns.get_loc("condition")] = np.nan
    with pytest.raises(AssumptionError, match="missing value"):
        _run(df2)


def test_methods_and_what_does_not_tell():
    result = _run(_dataset())
    assert result.methods
    methods_text = " ".join(result.methods)
    assert "PyDESeq2" in methods_text
    assert "negative-binomial" in methods_text
    assert result.what_does_not_tell
    assert "causation" in result.what_does_not_tell
    assert "relative" in result.what_does_not_tell


def test_low_replication_expert_review():
    # 3 per group -> below the _MIN_PER_GROUP = 6 threshold -> expert review.
    df = _counts_df().iloc[:6].copy()
    df.insert(0, "condition", ["treat"] * 3 + ["control"] * 3)
    result = _run(df)
    assert result.expert_review
    levels = {v.check: v.level for v in result.verdicts}
    assert levels["sample-size"] == "WARN"
