# Exploratory Factor Analysis (`factor-analysis`)

Exploratory Factor Analysis (EFA) finds the **hidden (latent) dimensions**
behind a set of several correlated **numeric item columns** — for example a
bunch of questionnaire items that you suspect are measuring a few underlying
traits (anxiety, engagement, motivation, ...) rather than being separate,
independent measures.

## When to use it

- You have **several correlated numeric columns** (the "items") and want to
  know how many underlying dimensions they tap and which items belong to each.
- You are building or validating a questionnaire/scales and want to see the
  **factor structure** of the items.
- You want to **reduce many items to a few interpretable factors** for later
  analysis.

The tool uses **every numeric column** it finds in your file (that is the
item set).

## What you get

- **Sampling-adequacy checks**: the Kaiser-Meyer-Olkin (KMO) statistic and
  Bartlett's test of sphericity, so you know whether the items share enough
  variance to be factored at all.
- A **factor loadings matrix** (each item × each factor), varimax-rotated by
  default so the pattern is easier to read.
- **Variance explained** per factor (and cumulative).
- The **eigenvalues** of the correlation matrix and a **scree plot**, which
  help you decide how many factors to keep.
- A **loadings heatmap** figure.
- A `methods.txt` paragraph you can paste into a paper.

## Choices

- **n_factors** (default `2`): how many latent factors to extract. Choose this
  by looking at the scree plot (elbow + eigenvalues > 1), the variance
  explained, and your theoretical expectation.
- **rotation** (`varimax` / `none`): an orthogonal varimax rotation makes the
  loadings pattern easier to interpret; `none` keeps the raw unrotated
  loadings.

## Assumptions and minimum sample size (checked and reported)

- Each item column must be **numeric** (item responses on a numeric scale).
- The items must be **correlated** with one another — if the correlation
  matrix is essentially diagonal, there is no shared structure to find. This
  is checked with **KMO** (below ~0.6 flags poor sampling adequacy) and
  **Bartlett's test of sphericity**.
- **Sample size**: a stable solution generally needs about **5–10
  observations per item** and **at least 100 observations overall**. With
  fewer, the analysis still runs (as long as there are at least 5 complete
  rows and 3 numeric columns) but the result is flagged for **expert review**.
- At least **3 numeric columns** and at least **5 complete rows** are
  required; fewer is refused. Missing values are **counted, reported and
  excluded** (listwise), **never imputed**.

## When NOT to use it

- Fewer than 3 numeric (varying) columns → refused; there is nothing to
  factor.
- Items that are essentially uncorrelated (low KMO) → a factor solution will
  be meaningless; the tool warns about this.
- If you want to **summarise total variance** of the items rather than model
  their shared variance, you want **PCA** — EFA is not PCA, and the two give
  different numbers.

## How to read the output

1. **KMO & Bartlett**: a high KMO (ideally ≥ 0.6–0.7) and a significant
   Bartlett's test mean the correlation matrix is worth factoring.
2. **Scree plot / eigenvalues**: look for the "elbow" — factors before the
   bend (and with eigenvalue > 1) are usually worth keeping.
3. **Loadings matrix**: each item's loading on each factor. Items with high
   loadings (say |loading| ≥ 0.4–0.5) on the same factor hang together.
4. **Variance explained**: how much of the item variance each factor accounts
   for.
5. **Names are your job**: the tool tells you which items cluster; giving the
   cluster a name ("anxiety", "engagement", ...) is the analyst's
   interpretation, not something the analysis outputs.

## Example

```bash
auphoria run --data my_questionnaire.csv --analysis factor-analysis
```

> Maturity: **experimental** (not "validated"). This is an **advanced-level**
> analysis meant for statistically experienced users; treat small-sample or
> poor-adequacy results as preliminary and seek expert review.