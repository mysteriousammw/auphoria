# Panel Regression (Fixed Effects)

`panel-regression` · maturity: **experimental**

Discipline packs: `econ-eng`, `social`  

Validation reference: Deterministic synthetic panel y_it = 2*x_it + entity_effect + e; the within-estimator beta and R-squared are cross-checked against an independent dummy-variable least-squares fit of the same data within 1e-5 (statsmodels does not ship PanelOLS; the within estimator is the standard equivalent).
  


## What it does

Fits a fixed-effects (within) regression of a numeric outcome on numeric covariates using repeated observations of the same units (a panel or longitudinal dataset). Instead of the between-unit variability, it uses only the variation WITHIN each unit over time, so each unit acts as its own control and time-constant unobserved differences between units (for example stable ability, location or management quality) are removed from the analysis. The within estimator is computed by group-demeaning every variable by the entity (unit) mean and fitting ordinary least squares on the demeaned data. It reports a coefficients table (beta, standard error, t, p and 95% confidence interval per covariate), a model table (R-squared within, model F and p, sample size, number of entities and number of time periods) and a fitted-versus-actual figure.

## What you need

- **outcome** (numeric-column, required): The numeric outcome you want to explain, measured over time.
- **entity** (categorical-column, required): The column identifying each unit in the panel (person, firm, school, country...). Fixed effects are built from this.

- **time** (categorical-column, required): The column identifying the time period (year, month, wave...). Used to count the number of time periods in the panel.


## Options

- `alpha` (default 0.05): Significance level used for the 95% confidence intervals and hypothesis tests.

## What you get out

- coefficients table (covariate, beta, std err, t, p, 95% confidence interval)
- model table (R-squared within, F, p, sample size, number of entities, number of time periods)
- fitted-versus-actual scatter figure
- methods.txt paragraph
- report.html

## Assumptions

- The outcome is numeric and its relationship to each covariate is approximately linear within entities (holding each unit's time-invariant level constant).
- Fixed effects absorb time-invariant unobserved differences between units (e.g. stable ability or location). The remaining identification comes only from within-unit changes over time.
- Each unit is observed at more than one time period, so there is within-unit variation in the variables (a unit observed only once contributes nothing to the fixed-effects estimate and is effectively unused).
- Missing values are counted and dropped (listwise), never imputed.
- Minimum sample size: at least 8 entities and at least 30 complete rows in total; a panel with fewer than 15 entities or fewer than 60 rows is flagged for expert review.

## Limitations

- Fixed effects do NOT remove time-varying confounders (variables that change over time and also affect the outcome); only time-constant unit differences are controlled for.
- The estimated coefficients are WITHIN-entity effects: they say how a change in a covariate is associated with a change in the outcome for the same unit over time, not how units compare with each other.
- The regression does not establish causality; it only adjusts for the covariates present in the data and the entity fixed effects.
- Variance is not adjusted for within-unit serial correlation or clustering beyond the fixed effects, so standard errors may be optimistic.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis panel-regression --outcome <outcome> --extra entity=<entity> --extra time=<time>
```
