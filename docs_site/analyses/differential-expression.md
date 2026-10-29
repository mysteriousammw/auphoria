# Differential Expression / Count Comparison (RNA-seq style)

`differential-expression` · maturity: **experimental**

Discipline packs: `life-science`  

Validation reference: Deterministic synthetic counts matrix in tests/test_differential_expression.py (8 samples, 4 treated / 4 control, 200 genes with a known set of over/under-expressed genes); per-gene padj cross-checked against a directly recomputed PyDESeq2 model.  


## What it does

Runs RNA-seq style differential-expression analysis on a counts matrix (one row per sample, one numeric column per gene) with PyDESeq2's negative-binomial model, comparing gene counts between two conditions such as treated vs control. It normalises for library size, models over-dispersion, and reports per-gene log2 fold-change and Benjamini-Hochberg FDR-adjusted p-values, plus a volcano plot and a top differentially-expressed genes table.

## What you need

- **condition** (categorical-column, required): The categorical column that marks each sample's condition/group (e.g. treated vs control).

## Options

- `alpha` (default 0.05): Significance level for flagging differentially expressed genes (padj < alpha).
- `padj_method` (default fdr_bh): Multiple-testing adjustment applied to the per-gene p-values. Default is Benjamini-Hochberg FDR ('fdr_bh'), matching PyDESeq2's own correction.

## What you get out

- per-gene results table (baseMean, log2FoldChange, lfcSE, stat, pvalue, padj), sorted by padj
- top differentially-expressed genes table (padj < alpha)
- volcano plot (log2 fold-change vs -log10 p-value)
- summary counts (genes tested, significant, up-regulated, down-regulated)
- methods.txt paragraph and report.html

## Assumptions

- One row per biological sample; one numeric column per gene (counts).
- The condition column has exactly two categories, each with at least 2 samples (only groups with replicates are analysable).
- The counts are close to a negative-binomial distribution with a gene-specific dispersion; DESeq2 estimates and shrinks the dispersion.
- Library sizes differ between samples and are accounted for via normalisation (fit-type ratio).
- Minimum sample size: at least 4 samples total and preferably at least 6 per condition for reliable power. Smaller designs run but are flagged for expert review as underpowered.
- The data is a complete counts matrix; any missing value causes a refusal (counts are never imputed or silently dropped).

## Limitations

- Low replication (fewer than ~6 samples per condition) severely limits the power to detect differential expression and inflates uncertainty.
- Very sparse genes (zero counts in a whole condition) make dispersion estimates unreliable.
- Differentially expressed genes are associations, not causal relationships, and require pathway or functional follow-up.
- Fold-changes are relative to the baseline condition within this study only and are not absolute abundance measures.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis differential-expression --extra condition=<condition>
```
