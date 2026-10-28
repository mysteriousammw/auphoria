# Spearman Rank Correlation

`spearman-correlation` · maturity: **experimental**

Validation reference: Hand-computed rho = 0.5 (rank-d^2 sum = 10) for x=[1..5], y=[3,1,4,2,5]; cross-checked vs scipy.stats.spearmanr  


## What it does

Measures whether two variables tend to increase or decrease together when their values are converted to ranks. Reports Spearman's rho, a p-value, the sample size used, and a plain-English interpretation of the direction and strength of the monotonic relationship.

## What you need

- **x** (numeric-column, required): The first numeric column (e.g. study_rank).
- **y** (numeric-column, required): The second numeric column (e.g. exam_score).

## Options

- `alpha` (default 0.05): Significance level used to judge the p-value.
- `tail` (default two-sided): Direction of the test for the correlation.

## What you get out

- Spearman correlation table (rho, p-value, n, direction, strength)
- scatter figure of the ranks with a rho annotation
- methods.txt paragraph
- report.html

## Assumptions

- Both columns are numeric and measured on the same set of observations.
- The relationship of interest is monotonic (steadily up or down, not necessarily a straight line); a U-shaped relationship can give a misleading rho near zero even though a strong pattern exists.
- Spearman works on ranks, so it does not need a normality assumption, but heavy ties (many equal values) distort rho, and rho is reported with a caution note when ties are common.

## Limitations

- Correlation does not imply causation.
- rho close to zero does not mean 'no relationship' — only no *monotonic* relationship.
- rho tells you whether things move together when ranked, not how big the moves are; ranks hide effect sizes.
- Missing values in the two columns are excluded pairwise (and reported), never imputed.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis spearman-correlation --extra x=<x> --extra y=<y>
```
