"""Differential expression / count comparison analysis for AUPHORIA.

Runs RNA-seq style differential-expression analysis on a *counts* matrix
using PyDESeq2's negative-binomial model. It compares per-gene read/count
levels between two biological conditions (e.g. treated vs control) while
accounting for library-size differences and over-dispersion.

Expected input layout (one row per sample, one column per gene):

    +----function+----------+----------+-----+-----+
    | sample | condition | gene1   | gene2  | ... |
    +========+===========+==========+========+=====+
    | s1     | treat     |  153    |  14    | ... |
    | s2     | treat     |  98     |  20    | ... |
    | s3     | control   |  31     |  12    | ... |
    +----+-------------+----------+--------+-----+

- one *categorical* ``condition`` column marks each sample's group,
- every OTHER numeric column is a per-gene count (the features).

The manifest declares a single required input: ``condition``
(``categorical-column``). All other numeric columns are treated as the
gene counts. The condition column must have exactly two categories, and
there must be at least four samples with at least two per condition.

Scientific output: per-gene table (baseMean, log2 fold-change, lfcSE,
Wald statistic, p-value, Benjamini-Hochberg FDR-adjusted p-value), a
volcano plot, a top differentially-expressed genes table, and a summary
count of up/down genes.

Guardrails are enforced here, not in the front end:
- the condition must have exactly two categories (refuse otherwise),
- at least 4 samples and at least 2 per condition are required,
- any missing value in a count column or the condition column is REFUSED
  with a clear message (counts are never imputed or silently dropped),
- small groups (< 6 per condition) and very sparse groups (a condition
  with all-zero counts for many genes) are flagged for expert review.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError

#: Minimum number of count (gene) columns required.
_MIN_GENES = 4
#: Minimum number of samples (rows) required.
_MIN_SAMPLES = 4
#: Minimum samples per condition before the result is considered underpowered.
_MIN_PER_GROUP = 6
#: A condition whose all-zero (in its group) gene fraction exceeds this is
#: flagged as sparse for expert review.
_SPARSE_FRAC = 0.30


class DifferentialExpressionAnalysis(Analysis):
    id = "differential-expression"
    name = "Differential Expression / Count Comparison (RNA-seq style)"

    def check_fit(
        self,
        profile: Any,
        params: dict[str, Any],
        inputs: dict[str, str],
    ) -> list[str]:
        del params
        refusals: list[str] = []
        cond = inputs.get("condition")
        if cond is not None:
            col = profile.by_name(cond)
            if col is not None and col.kind not in ("categorical", "text"):
                refusals.append(
                    f"'{cond}' looks like a {col.kind} column, not a categorical "
                    "condition column. The condition (e.g. treated vs control) "
                    "must label each sample's group."
                )
        return refusals

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        result = AnalysisResult()
        cond_col = inputs["condition"]

        if cond_col not in data.columns:
            raise AssumptionError(
                f"The data has no column named '{cond_col}'.",
                hint="Pick the categorical column that marks each sample's condition.",
            )

        alpha = float(params.get("alpha", 0.05))
        padj_method = str(params.get("padj_method") or "fdr_bh").lower()
        ctx.log_decision(f"alpha = {alpha}, padj method = '{padj_method}'.")

        # Every OTHER numeric column is a gene-count column (the features).
        count_cols = [
            c
            for c in data.columns
            if c != cond_col and pd.api.types.is_numeric_dtype(data[c])
        ]
        if len(count_cols) < _MIN_GENES:
            raise AssumptionError(
                f"Found {len(count_cols)} numeric count column(s); at least "
                f"{_MIN_GENES} are needed. The count matrix must be laid out "
                "with one numeric column per gene (counts) plus one categorical "
                "condition column.",
                hint=(
                    "Arrange the data as rows of samples, columns of gene counts, "
                    "plus a 'condition' column marking each sample's group."
                ),
            )

        n_samples = int(data.shape[0])
        if n_samples < _MIN_SAMPLES:
            raise AssumptionError(
                f"The data has {n_samples} sample row(s); at least {_MIN_SAMPLES} "
                "samples are required for differential-expression analysis.",
                hint="Provide at least 4 samples with counts.",
            )

        # Never impute: refuse on ANY missing count/condition value.
        nan_counts = int(data[count_cols].isna().sum().sum())
        nan_cond = int(data[cond_col].isna().sum())
        if nan_counts or nan_cond:
            raise AssumptionError(
                f"The count matrix contains missing values "
                f"({nan_counts} in count columns, {nan_cond} in '{cond_col}'). "
                "PyDESeq2 needs a complete counts matrix.",
                hint=(
                    "Fill or remove any cells with missing counts before running. "
                    "AUPHORIA never imputes or silently drops counts."
                ),
            )

        # --- build the DESeq2 containers (samples as rows, genes as columns)
        idx = list(data.index)
        counts_df = data.loc[idx, count_cols].astype(float).copy()
        metadata_df = pd.DataFrame(
            {"condition": [str(v) for v in data.loc[idx, cond_col]]}, index=idx
        )

        cats = sorted({str(v) for v in metadata_df["condition"].unique()})
        if len(cats) != 2:
            raise AssumptionError(
                f"The condition column '{cond_col}' has {len(cats)} distinct "
                f"categories ({', '.join(cats)}), but differential expression "
                "needs exactly two (e.g. treated vs control).",
                hint="Pick a binary condition column with exactly two categories.",
            )

        per_group = {c: int((metadata_df["condition"] == c).sum()) for c in cats}
        ctx.log_decision(
            "Condition mapping: " + "; ".join(f"{c} = {per_group[c]} samples" for c in cats)
        )
        if any(n < 2 for n in per_group.values()):
            raise AssumptionError(
                "Each condition needs at least 2 samples to estimate dispersion; "
                f"got {per_group}.",
                hint="Add replicate samples to both conditions.",
            )

        # Deterministic reference: alphabetically-first category is the
        # baseline (denominator), the other is the numerator (comparison).
        reference_cat, numerator_cat = cats[0], cats[1]
        ctx.log_decision(
            f"log2 fold-change is relative to baseline '{reference_cat}' "
            f"(numerator = '{numerator_cat}')."
        )

        # --- fit the DESeq2 model on the actual data
        results = self._run_deseq2(
            counts_df, metadata_df, reference_cat, numerator_cat, alpha, ctx
        )

        # --- result table (all genes), sorted by padj, NaN last
        res = results.copy()
        ordered = res.sort_values("padj", na_position="last")
        result.tables["Results"] = ordered

        sig = res["padj"].lt(alpha) & res["padj"].notna()
        n_sig = int(sig.sum())
        n_up = int((sig & (res["log2FoldChange"] > 0)).sum())
        n_down = int((sig & (res["log2FoldChange"] < 0)).sum())

        top = res[sig].sort_values("padj")
        result.tables["Top differential genes"] = top

        # --- verdicts & expert review
        worst_per_group = min(per_group.values())
        if worst_per_group < _MIN_PER_GROUP:
            result.add_verdict(
                "WARN",
                "sample-size",
                f"Only {worst_per_group} sample(s) per condition (recommended at "
                f"least {_MIN_PER_GROUP}); the power to detect differential "
                "expression is low and the result needs a statistician's review.",
            )
            result.add_expert_review(
                f"Few samples per condition (smallest group n = {worst_per_group}, "
                "recommended at least 6 per condition). Differential expression "
                "here is underpowered and needs a statistician's (or supervisor's) "
                "review."
            )
        else:
            result.add_verdict(
                "PASS",
                "sample-size",
                f"Each condition has at least {_MIN_PER_GROUP} samples "
                f"(smallest group n = {worst_per_group}).",
            )

        # Sparse groups: a condition with all-zero counts across many genes.
        grp0 = counts_df[metadata_df["condition"] == reference_cat]
        grp1 = counts_df[metadata_df["condition"] == numerator_cat]
        z0 = float((grp0.sum(axis=0) == 0).mean())
        z1 = float((grp1.sum(axis=0) == 0).mean())
        max_zero_frac = max(z0, z1)
        if max_zero_frac > _SPARSE_FRAC:
            result.add_verdict(
                "WARN",
                "sparse-counts",
                f"{max_zero_frac:.0%} of genes have zero total counts in one "
                "condition; many zero-count genes make dispersion estimates "
                "unreliable and need expert review.",
            )
            result.add_expert_review(
                f"A condition has all-zero counts for {max_zero_frac:.0%} of genes. "
                "These sparse genes make the dispersion estimate unreliable; "
                "review the result with a statistician."
            )
        else:
            result.add_verdict(
                "PASS",
                "sparse-counts",
                f"No condition is dominated by zero-count genes "
                f"(max zero-gene fraction {max_zero_frac:.0%}).",
            )
        ctx.log_decision(
            f"Number of genes tested = {len(res)}; significant at alpha={alpha} "
            f"({padj_method}): {n_sig} (up = {n_up}, down = {n_down})."
        )

        # --- summaries
        result.summaries = {
            "genes tested": f"{len(res)}",
            "significant (padj < alpha)": f"{n_sig}",
            "up-regulated": f"{n_up}",
            "down-regulated": f"{n_down}",
            "padj method": f"{padj_method}",
            "baseline (reference)": f"{reference_cat}",
        }

        # --- volcano figure
        fig, caption = _volcano_figure(res, alpha, reference_cat, numerator_cat)
        result.figures.append(FigureItem(name="volcano_plot", figure=fig, caption=caption))

        # --- methods sentences
        methods = [
            "Differential expression was assessed with PyDESeq2's "
            "negative-binomial generalised linear model on a counts matrix of "
            f"{len(res)} genes across {counts_df.shape[0]} samples, comparing "
            f"'{numerator_cat}' against the '{reference_cat}' baseline."
        ]
        if padj_method == "fdr_bh":
            methods.append(
                "P-values were multiplicity-adjusted with the "
                "Benjamini-Hochberg false-discovery-rate method "
                f"(padj < {alpha} called significant)."
            )
        else:
            methods.append(
                f"P-values were multiplicity-adjusted with the '{padj_method}' "
                f"method (padj < {alpha} called significant)."
            )
        methods.append(
            f"Of {len(res)} genes, {n_sig} were differentially expressed "
            f"({n_up} up-, {n_down} down-regulated) at padj < {alpha}."
        )
        result.methods = methods

        # --- honest interpretation
        result.what_does_not_tell = (
            "Differential expression is a statistical association between "
            "counts and condition; it is not proof of biological causation, and "
            "differentially expressed genes still need pathway or functional "
            "follow-up. log2 fold-changes are within-study, relative to the "
            "baseline condition in THIS dataset — they are not measures of "
            "absolute expression abundance and are not comparable in magnitude "
            "across independent studies. Significance depends on sample size, "
            "dispersion, and library size, so a non-significant gene may simply "
            "be underpowered rather than truly unchanged."
        )
        return result

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _run_deseq2(
        counts_df: pd.DataFrame,
        metadata_df: pd.DataFrame,
        reference_cat: str,
        numerator_cat: str,
        alpha: float,
        ctx: RunContext,
    ) -> pd.DataFrame:
        """Fit the DESeq2 model and return the per-gene results table."""
        from pydeseq2.dds import DeseqDataSet
        from pydeseq2.ds import DeseqStats

        dds = DeseqDataSet(
            counts=counts_df,
            metadata=metadata_df,
            design="~condition",
            refit_cooks=True,
            quiet=True,
        )
        dds.deseq2()
        stat = DeseqStats(
            dds,
            contrast=["condition", numerator_cat, reference_cat],
            alpha=alpha,
            quiet=True,
        )
        stat.summary()
        res = stat.results_df
        if res is None or len(res) == 0:
            raise AssumptionError(
                "PyDESeq2 returned no per-gene results; check that the count "
                "matrix is well-formed.",
                hint="Make sure every count column is numeric with values >= 0.",
            )
        ctx.log_decision(
            f"PyDESeq2: {res.shape[0]} genes tested; baseMean range "
            f"{res['baseMean'].min():.2g}-{res['baseMean'].max():.2g}."
        )
        res.index.name = "gene"
        return res


def _volcano_figure(
    res: pd.DataFrame,
    alpha: float,
    reference_cat: str,
    numerator_cat: str,
) -> tuple[Figure, str]:
    import matplotlib.pyplot as plt

    sig = res["padj"].lt(alpha) & res["padj"].notna()
    x = res["log2FoldChange"].to_numpy(dtype=float)
    y = -np.log10(res["pvalue"].to_numpy(dtype=float))

    fig, ax = plt.subplots(figsize=(6.4, 5.4))
    ax.scatter(x[~sig], y[~sig], s=8, color="#8a8a8a", alpha=0.55, label="not significant")
    ax.scatter(
        x[sig],
        y[sig],
        s=10,
        color="#c0392b",
        label=f"significant (padj < {alpha})",
        edgecolors="none",
    )
    ax.axhline(-np.log10(alpha), ls="--", color="#555", lw=1)
    ax.set_xlabel("log2 fold change")
    ax.set_ylabel(r"$-\log_{10}$(p-value)")
    ax.set_title("Differential expression volcano plot", fontsize=11)
    ax.grid(ls=":", alpha=0.5)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    caption = (
        f"Volcano plot of {len(res)} genes: log2 fold-change "
        f"('{numerator_cat}' vs '{reference_cat}') against the raw "
        f"-log10 p-value. A horizontal line marks the p = {alpha} threshold; "
        "genes whose Benjamini-Hochberg-adjusted p-value < "
        f"{alpha} are highlighted as differentially expressed."
    )
    return fig, caption


# Module-level instance the registry looks for.
ANALYSIS = DifferentialExpressionAnalysis()
