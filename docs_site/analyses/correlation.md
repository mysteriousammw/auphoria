# Pearson Correlation

`correlation` · maturity: **experimental**

Validation reference: Hand-computed Pearson r on x=[1..5]; cross-checked vs scipy.stats.pearsonr  


## What it does

Measures the strength and direction of a straight-line (linear) relationship between two numeric columns, and reports the correlation coefficient r, a p-value, the sample size used, and a plain-English interpretation.

## What you need

- **x** (numeric-column, required): The first numeric column (e.g. hours_studied).
- **y** (numeric-column, required): The second numeric column (e.g. exam_score).

## Options

- `tail` (default two-sided): Direction of the test for the correlation.

## What you get out

- correlation result table (r, p-value, n, interpretation)
- scatter figure with a labelled trend line
- methods.txt paragraph
- report.html

## Assumptions

- Both columns are numeric and measured on the same set of observations.
- The relationship of interest is roughly straight-line (linear); a strongly curved relationship can give a misleading r near zero.
- Pearson r is most meaningful when the two variables are roughly bivariate normal; rank methods are more robust to outliers (planned analysis).

## Limitations

- Correlation does not imply causation.
- r close to zero does not mean "no relationship" — only no *linear* relationship.
- One very unusual (outlier) value can change r a lot.
- Missing values in the two columns are excluded pairwise (and reported), never imputed.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis correlation --extra x=<x> --extra y=<y>
```
