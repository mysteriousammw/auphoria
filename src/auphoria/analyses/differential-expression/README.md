# Differential Expression / Count Comparison (`differential-expression`)

Runs RNA-seq style **differential expression** on a **counts matrix** using
**PyDESeq2**. It compares per-gene read/count levels between **two
conditions** (e.g. treated vs control) while accounting for library-size
differences and over-dispersion between replicate samples.

## When to use it

- You have a table of **gene (or feature) counts** across samples.
- You have a **binary condition** column marking each sample's group
  (treated vs control, mutant vs wild-type, disease vs healthy).
- You want to know *which genes are expressed significantly differently*
  between the two conditions, with fold-changes and FDR-corrected p-values.

## Expected input shape

The data must be laid out with **one row per sample, one column per gene**,
plus a separate categorical **condition** column:

| sample | condition | geneA | geneB | geneC |
|--------|-----------|-------|-------|-------|
| s1     | treat     | 153   | 14    | 402   |
| s2     | treat     | 98    | 20    | 355   |
| s3     | control   | 31    | 12    | 388   |
| s4     | control   | 40    | 10    | 371   |

- **`condition`** (the *only* required input) marks each sample's group. It
  must have **exactly two categories**.
- **Every other numeric column** is treated as a per-gene counts column.
- You need **at least 4 samples** total and **at least 2 per condition**.

> A column-per-gene, row-per-sample layout is required. If your data has
> genes as rows and samples as columns, transpose it before running.

## What you get

- **Results table**: per-gene `baseMean`, `log2FoldChange`, `lfcSE`,
  `stat`, `pvalue`, `padj` — sorted by adjusted p-value.
- **Top differential genes**: the significantly DE genes (`padj < alpha`).
- **Volcano plot**: `log2` fold-change vs `-log10(p-value)`.
- **Summary**: genes tested, significant, **up-regulated**, **down-regulated**.
- A `methods.txt` paragraph for your paper.

## Choices

- **alpha** (default `0.05`): a gene is called differentially expressed when
  its adjusted p-value is below alpha.
- **padj_method** (default `fdr_bh`): the multiple-testing adjustment.
  `fdr_bh` is Benjamini-Hochberg false-discovery-rate control, and matches
  PyDESeq2's own correction.

## Direction of the fold-change

The condition labels are sorted and the **alphabetically-first** category is
used as the **baseline** (denominator). A `log2FoldChange > 0` means the gene
is more highly expressed in the *other* condition relative to that baseline.
This mapping is logged and shown in the summary so you can see which direction
your comparison runs.

## Assumptions (checked and reported, never silently ignored)

- **Complete counts**: any missing value in a count column or the condition
  column is **refused** with a clear message — counts are never imputed or
  silently dropped.
- **Independent samples**, one row per biological replicate.
- **Exactly two condition categories**, each with **≥ 2 samples**.
- Counts are described well by a negative-binomial model with a
  gene-specific dispersion (DESeq2 estimates/shrinks this).
- **Minimum sample size**: at least 4 samples total; ideally **≥ 6 per
  condition**. Smaller designs run but are flagged for **expert review**.

## When NOT to use it

- More than two conditions → the tool refuses (use a different design).
- Whole-transcriptome / raw reads → this analysis needs a *counts table*,
  not FASTQ/BAM files.
- You only want library-size normalisation, not differential testing.

## How to read the output

1. Check the **baseline** shown in the summary — that fixes the direction of
   every fold-change.
2. **`padj`** is the multiple-testing-corrected p-value; use it, not the raw
   `pvalue`, when calling genes differentially expressed.
3. A gene that is *not* significant is not necessarily unchanged — it may
   simply be **underpowered** given your sample size.
4. The fold-changes are **within-study and relative to this baseline**; they
   are not absolute expression levels.

> Maturity: **experimental** (not "validated").

## Example command

```bash
# metadata-like file with rows = samples, a 'condition' column, and gene-count columns
auphoria run \
  --data counts.csv \
  --analysis differential-expression \
  --group condition
```

(`--group` holds the categorical condition column; all other numeric columns
are taken as the gene counts.)

## Installing the dependency

This analysis needs **PyDESeq2**:

```bash
pip install "auphoria[life-science] @ git+https://github.com/mysteriousammw/auphoria"
```