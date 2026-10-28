# Cox Proportional-Hazards Regression

`cox-regression` · maturity: **experimental**

Discipline packs: `health`, `life-science`  

Validation reference: Synthetic survival data; cross-checked vs statsmodels.duration.hazard_regression.PHReg  


## What it does

Models the time until an event (survival / time-to-event data) with one or more numeric covariates, estimating a hazard ratio for each predictor: how the instantaneous risk of the event changes per unit of that predictor while the others are held fixed. Built on statsmodels' PHReg (permissive licence; lifelines/autograd is avoided).

## What you need

- **time** (numeric-column, required): Time to event or censoring (e.g. months, days, years).
- **event** (numeric-column, required): Event indicator - exactly 0 (censored) or 1 (event happened).
- **covariate** (numeric-column, required): One or more numeric predictors. A single column name (e.g. age), or a comma-separated list for a multivariable model (e.g. age, BMI, stage).

## Options

- `alpha` (default 0.05): Significance level used for the p-value "significant" flags and the assumption checks.

## What you get out

- hazard-ratio table (exp(coef), 95% CI lower/upper, log HR, log HR SE, p per covariate)
- model-fit table (log-likelihood, total complete rows, event count)
- proportional-hazards verdict (Schoenfeld residual correlation with event time)
- forest plot of hazard ratios with 95% CIs
- methods.txt paragraph
- report.html

## Assumptions

- Proportional hazards: the hazard ratio for each predictor is roughly constant over time (checked with a Schoenfeld-residual correlation vs event time; if violated the hazard ratio is only an average over follow-up).
- Non-informative censoring: subjects who are censored would, had they been followed longer, have the same future risk as those still under observation.
- Linearity of continuous predictors: each numeric covariate relates to the log hazard in a straight-line fashion (no bending) unless it is transformed or categorised.
- Events are independent across subjects; time and covariates are measured without error.

## Limitations

- A hazard ratio is a relative effect, not an estimate of absolute risk or of how many subjects will experience the event by a given time.
- Cox proportional hazards measures association, not causation; the hazard ratios can be confounded by unmeasured predictors.
- If proportional hazards is violated, the single hazard ratio does not capture time-varying effects.
- Missing values in the chosen columns are excluded listwise (and reported), never imputed; very heavy missingness can bias results.
- Strongly collinear covariates inflate standard errors and make individual hazard ratios unstable (flagged for review when |r| exceeds 0.95).

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis cox-regression --extra time=<time> --extra event=<event> --extra covariate=<covariate>
```
