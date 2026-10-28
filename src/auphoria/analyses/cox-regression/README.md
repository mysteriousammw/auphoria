# Cox Proportional-Hazards Regression (`cox-regression`)

Models the **time until an event** (survival / time-to-event data) with one or
more **numeric covariates**, and reports a **hazard ratio (HR)** for each one:
how the *instantaneous risk* of the event changes per unit of that predictor
while the others are held fixed. Common in medicine (time to death, relapse,
hospital readmission), engineering (time to failure), economics and social
science (time to an event such as job exit or re-offence). Built on
statsmodels' `PHReg` (permissively licensed) — **lifelines** is not used.

## When to use it

- You have a **time-to-event** outcome (months, days, years) plus an **event
  indicator** (0 = censored, 1 = the event happened).
- You have **one or more numeric covariates** whose effect on the risk of the
  event you want to estimate — e.g. age, dose, biomarker level.
- Your data has **censoring**: some subjects did not experience the event by
  the end of follow-up (that is fine — Cox handles it; it does not throw those
  subjects away).
- You want a **hazard ratio with a confidence interval and p-value** for each
  predictor.

## What you get

- A **hazard-ratio table**: for every covariate, `exp(coef)`, 95% CI,
  log HR and its SE, p-value, and a "significant at alpha?" flag.
- A **model-fit table**: log-likelihood, number of complete rows, event count.
- A **proportional-hazards check** (Schoenfeld-residual correlation with event
  time) reported as a PASS/WARN verdict.
- A **forest plot** of the hazard ratios with 95% CIs.
- A `methods.txt` paragraph you can paste into a paper.

## Choices

- **alpha** (default `0.05`): significance level for the p-value flags and the
  assumption checks. CI is `(1 - alpha)`.
- **covariate**: a single numeric column (e.g. `age`) **or a comma-separated
  list** for a multivariable model (e.g. `age, bmi, stage`).

## Assumptions (checked and reported, never silently ignored)

- **Proportional hazards** — each hazard ratio is roughly constant over time.
  This is checked (Schoenfeld residuals vs event time). If it fails you get a
  WARN and the hazard ratio should be read as an average over follow-up.
- **Non-informative censoring** — censored subjects would, if followed longer,
  have the same future risk as those still observed.
- **Linearity** of continuous predictors on the log-hazard scale.
- **Events are independent** across subjects.

**Minimum sample size:** aim for at least **30 events** and **≥ 50 complete
rows** (≈10 events per covariate). The tool **refuses to run with zero events**,
and warns + flags **expert review** when there are **fewer than 10 events** or
**fewer than 30 complete rows** — those results are preliminary only.

## When NOT to use it

- **No event indicator**, or just everyone-censored → cannot run; needs an
  event column.
- You only want **survival probabilities / median survival** (not hazard
  ratios) → use **Kaplan-Meier** instead.
- The event happens **immediately / always** and everyone has the same
  follow-up → ordinary (logistic / linear) regression may be more natural.
- Hazard ratios that **change a lot over time** (proportional-hazards violated)
  → consider a stratified or time-varying model.

## How to read the output

1. **Hazard ratio (HR)**: `HR > 1` means higher predictor → higher instantaneous
   risk; `HR < 1` means lower risk; `HR = 1` means no association. Read it with
   its **95% CI** — if the CI straddles 1 the effect is not clearly significant.
2. **p**: p < alpha means the association is statistically unlikely to be
   chance, under the model's assumptions.
3. **Proportional-hazards verdict**: PASS means no strong evidence the ratio
   drifts over time; WARN means treat the single HR as an average.

## Example

```bash
auphoria run --data survival.csv \
  --analysis cox-regression \
  --outcome time_months \
  --extra "event=event" \
  --extra "covariate=age"
```

For a multivariable model: `--extra "covariate=age, bmi"`.

> Maturity: **experimental** (not "validated"). Advanced analysis: results
> outside the intended conditions are flagged for expert review.