# Pearson Correlation (`correlation`)

Measures the strength and direction of a **straight-line relationship**
between two numeric columns — e.g. hours studied vs exam score, or soil pH vs
crop yield.

## When to use it

- You have two **numeric** columns.
- You want to know whether they move together (and how strongly).
- The relationship you care about looks roughly like a straight line.

## What you get

- The correlation coefficient `r` (from −1 to +1).
- A p-value (how likely this strong a relationship would be by chance if the
  true correlation were 0).
- The sample size `n` actually used.
- A plain-English description (strength and direction).
- A scatter figure with an honest, clearly-labelled trend line (visual aid).

## Interpretation of r

| |r|          | strength    |
|-------------|-------------|
| < 0.2      | negligible  |
| 0.2 – 0.4  | weak        |
| 0.4 – 0.6  | moderate    |
| 0.6 – 0.8  | strong      |
| ≥ 0.8      | very strong |

## Assumptions & limitations

- Both columns numeric and measured on the same rows.
- Pearson r captures **linear** relationships only; a U-shaped relationship
  can give r ≈ 0 despite a strong pattern.
- Outliers can greatly change r.
- Correlation ≠ causation.

## Check

`auphoria info correlation` shows the manifest. Tests
(`tests/test_correlation.py`) verify r and p against SciPy's reference
implementation and a hand-computed example (exact line r = 1; textbook-ish
example r ≈ 0.967).

> Maturity: **experimental** (not "validated").