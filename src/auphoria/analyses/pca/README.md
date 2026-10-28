# Principal Component Analysis (`pca`)

Reduces **many numeric columns** into a few combined scores — **principal
components** — that capture most of the variation. Use it to shrink a wide
table (gene expression, soil chemistry, questionnaire items, spectra) into a
small number of interpretable dimensions and to see whether your variables
share underlying structure.

## When to use it

- You have **many numeric columns** and want a few combined scores instead.
- You want to **explore** which variables move together (correlated blocks).
- You want a **scatter plot** of observations in a low-dimensional space
  (the first two components) to look for clusters or patterns.
- You want to feed a reduced set of scores into a later analysis.

## What you get

- **Variance-explained table**: eigenvalue, % variance explained and
  cumulative % for each component.
- **Component loadings table**: each variable's weight on every component —
  the recipe for turning a row of raw numbers into a component score.
- **How-many-components guidance**: how many to keep (keep until the
  cumulative variance reaches 80 % or the eigenvalue exceeds 1).
- A **scree plot** (eigenvalue per component, with cumulative %) and a
  **score scatter** of observations on the first two components.
- A `methods.txt` paragraph you can paste into a paper.
- Bartlett's test of sphericity when the data allows it (more rows than
  variables), as a correlation check.

## Choices

- **n_components** (default `2`): how many components to compute and report.
- **standardize** (default `true`): centre and scale each variable to unit
  variance before PCA. Keep this on unless every variable already lives on
  the same scale — otherwise high-variance columns dominate.

## Assumptions (checked and reported, never silent)

- At least **two numeric columns**; the analysis uses **all** numeric
  columns automatically (it needs no column choices).
- The variables are **correlated enough** to share structure (Bartlett's
  test of sphericity, when it can run).
- Variables are **standardised** (the default) or already on the same scale.
- **No strong outliers** — PCA is not robust and a few extreme values can
  dominate a component.
- **Minimum sample size**: at least **3 complete rows** to run; results are
  only stable with **at least 10 rows**, ideally more rows than variables
  (n > p). With fewer than 10 rows the result is flagged for expert review.

## When NOT to use it

- You hypothesise that a few unobserved **latent factors** explain the
  correlations → use **factor analysis**, not PCA (PCA maximises variance,
  it does not model latent constructs).
- Your variables share little/no correlation → PCA will find no meaningful
  structure.
- You have one variable on a wildly different scale and do not standardise
  → that variable silently dominates.

## How to read the output

1. Look at the scree plot and the cumulative % column: pick the smallest
   number of components that captures most (≈ 80 %) of the variance.
2. Read the loadings: a large |loading| means that variable leans heavily
   on that component. Give the component a name from its biggest loadings.
3. Read the score scatter with caution — points near each other are
   similar in those two combined scores, nothing more.

> Maturity: **experimental** (not "validated").

## Example

```
auphoria run --data my_data.csv --analysis pca
```