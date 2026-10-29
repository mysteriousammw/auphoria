# Panel Regression (Fixed Effects) (`panel-regression`)

**Panel (longitudinal) regression with fixed effects** explains a **numeric
outcome using repeated observations of the same units over time** — for
example, how a firm's profit responds to investment while absorbing each
firm's stable unobserved differences, or how student scores change across
school years while holding each student's stable ability constant.

It fits the **within estimator**:

```
y_it = alpha_i + beta * x_it + u_it
```

where `alpha_i` is an entity-specific intercept (the fixed effect) that
absorbs every **time-constant** difference between units. The model is
estimated by **group-demeaning**: each variable is subtracted from its own
entity mean, then ordinary least squares is run on the demeaned data. Only the
variation that happens *inside* each unit over time is used.

## When to use it

- Your data is a **panel**: several units (people, firms, schools, countries)
  each observed more than once over time.
- You want to control for **stable, unmeasured differences between units**
  (location, management quality, ability) that could otherwise confound the
  relationship.
- You are interested in **within-unit effects**: how a change in a covariate
  is associated with a change in the outcome for the same unit.

## When NOT to use it

- **Fewer than 8 entities, or fewer than 30 complete rows** in total → refused
  (too few units or too little within-variation to estimate stable effects).
- **No numeric covariate** besides the outcome → refused.
- **Perfectly collinear covariates** (one is exactly a combination of the
  others) → refused.
- **Cross-sectional data** (each unit observed once) → use ordinary multiple
  regression instead.
- When you want to compare outcomes *between* units, or when most of the action
  is between-unit rather than within-unit, a random-effects / mixed model may
  be more appropriate (this analysis is deliberately fixed-effects only).

## What you get

- A **coefficients table**: per covariate, the beta coefficient (the
  within-entity effect), its standard error, the t statistic, the p-value, and
  a 95% confidence interval.
- A **model table**: R-squared within, the overall model F test and its
  p-value, the sample size, the number of entities, and the number of time
  periods.
- A **fitted-versus-actual figure** on the within-de-meaned values.
- A `methods.txt` paragraph you can paste into a paper.

## Choices

- **alpha** (default `0.05`): significance level used for the confidence
  intervals and hypothesis tests.

## Assumptions

- The outcome is numeric and approximately **linear within entities** in the
  covariates.
- **Fixed effects** absorb time-invariant unit differences; identification
  comes from within-unit changes over time.
- Each unit should be observed more than once so there is within-unit
  variation (a unit with a single observation contributes nothing).
- Missing values are counted and dropped (listwise), **never imputed**.
- **Minimum sample size**: at least 8 entities and at least 30 complete rows.
  A panel with fewer than 15 entities or fewer than 60 rows is flagged for
  expert review.

## How to read the output

1. **R-squared within**: the share of *within-entity* variation in the outcome
   explained by the covariates (after removing stable unit differences).
2. **A covariate's beta and p**: the expected change in the outcome per
   one-unit increase in that covariate, for the *same unit* over time (holding
   the other covariates and the fixed effect constant).
3. **Model F and p**: whether the covariates, taken together, explain a
   significant share of the within-entity variation.
4. **Remember the limit**: fixed effects remove time-constant confounders, but
   **not** time-varying ones.

## Example

```bash
auphoria run --data my_panel.csv --analysis panel-regression \
    --outcome profit --extra entity=firm --extra time=year
```

> Maturity: **experimental** (not "validated"). This is an advanced analysis;
> when used with a small panel (fewer than 15 entities or 60 rows) it flags a
> requirement for expert review.