# Linear Mixed-Effects Model (`mixed-effects`)

Models a **numeric outcome** with **fixed effects** (a categorical predictor,
e.g. treatment) plus a **random intercept per grouping unit** — subject,
school, plot, site, classroom. This is the tool for **clustered**, **nested**
or **repeated** data, where observations inside the same group are *not*
independent and a plain ordinary regression would wrongly treat them as if
they were.

## When to use it

- Your outcome is a number (score, height, yield, reaction time, concentration).
- Your observations hang together in **groups** — the same subject measured
  several times, plants grown on the same plot, students in the same
  classroom, trials at the same site — and you want to account for that
  clustering.
- You have a **categorical predictor** whose effect you want to estimate
  (treatment A vs B, before vs after) while "absorbing" the between-group
  noise.
- You want the **intraclass correlation (ICC)** — how much of the outcome's
  variation sits between groups versus within them.

Use the independent-groups **t-test / ANOVA** only when every observation
belongs to a different unit (no repeated measures, no nesting).

## What you get

- **Fixed effects** table: coefficient, standard error, 95% confidence
  interval, z and p for the intercept and each group level (vs the reference
  level), flagged significant or not at your alpha.
- **Random effects (variance components)** table: intercept (between-cluster)
  variance and residual (within-cluster) variance.
- **Intraclass correlation** (ICC = intercept variance / total variance), with
  a plain-English reading.
- A box-and-whisker figure of the outcome by group.
- A `methods.txt` paragraph you can paste into a paper.

## Choices

- **alpha** (default `0.05`): significance level for the fixed-effect p-values
  and the confidence intervals.

## Assumptions (checked and reported, never silently ignored)

The model is estimated by **restricted maximum likelihood (REML)** using
**statsmodels `MixedLM`** (permissive licence; pingouin is not used).

- The outcome is **numeric** and the residuals are roughly **normally
  distributed** after fitting.
- The **random intercepts** are roughly normally distributed across units.
- Each **cluster** has **at least two observations** (otherwise there is no
  within-cluster variance to estimate — the tool refuses such a cluster).
- There are at least **two group categories** and at least **two clusters**,
  otherwise the model is not identifiable (the tool refuses).

### Minimum sample size (important)

A linear mixed model needs a reasonable number of clusters *and* observations
per cluster to estimate its variance components reliably:

- **Clusters:** aim for **at least 10** (ideally 20+); fewer than **5** is
  unreliable and triggers a "needs expert review" notice.
- **Observations per cluster:** at least **2** (ideally 5+); each cluster must
  have ≥ 2.
- **Total sample size:** roughly **30 or more**; below ~30 triggers a "needs
  expert review" notice.

These are rules of thumb, not hard cut-offs. When you run with a small sample
you still get the model, but the report carries a prominent **"needs expert
review"** banner and you should have a statistician look at it.

## When NOT to use it

- **Fully independent observations** (one measurement per unit, no grouping) →
  use the t-test or ANOVA.
- **Only one cluster** or a group predictor with one category → the model
  cannot be fitted (the tool refuses).
- **Random slopes needed** — this analysis fits a random intercept *only*; if
  your level-1 (within-cluster) effect is expected to vary across clusters,
  you need a richer random structure than this tool provides.
- **Ordered/time-series responses within a cluster** — the random intercept
  assumes exchangeability; an autocorrelation structure may be needed.

## How to run it

```bash
auphoria run --data your_data.csv --analysis mixed-effects \
  --outcome score --group treatment --extra cluster=classroom
```

- `--outcome`: the numeric outcome column.
- `--group`: the categorical fixed-effect predictor.
- `--extra cluster=...`: the random grouping id column.

## How to read the output

1. **ICC**: a value near 0 means almost all variation is within clusters
   (little clustering); near 1 means almost all variation sits between groups.
   High ICC is exactly why you used a mixed model instead of ordinary
   regression.
2. **Fixed effects**: each group coefficient is the expected difference in the
   outcome relative to the reference group, holding the cluster effect
   fixed. `p < alpha` (or a CI that excludes 0) means that level differs from
   the reference.
3. **Variance components**: small between-cluster variance (relative to
   residual) means clusters don't differ much beyond the fixed effects.
4. Common pitfall to avoid: treating a **level-1** (within-group) slope as a
   **level-2** (between-group) effect is the **ecological fallacy** — the
   model does not support that leap.

> Maturity: **experimental** (not "validated"). An advanced analysis: with few
> clusters or a small sample, the result is flagged as needing expert review.