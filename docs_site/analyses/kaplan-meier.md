# Kaplan-Meier survival analysis

`kaplan-meier` · maturity: **experimental**

Discipline packs: `health`, `life-science`  

Validation reference: Hand-computed survival curve for times [2,3,5,6], events [1,1,0,1]; cross-checked vs statsmodels SurvfuncRight + hand log-rank  


## What it does

Estimates survival curves over time for censored time-to-event data (e.g. time to relapse, failure of a component, time to dropout), one curve per group, using the Kaplan-Meier product-limit method (statsmodels SurvfuncRight), reports median survival, and compares the groups with a log-rank test so you can see whether their survival curves differ.

## What you need

- **time** (numeric-column, required): Time-to-event column (e.g. time since study entry, months, days).
- **event** (numeric-column, required): Event indicator: 0 = censored, 1 = event occurred.
- **group** (categorical-column, required): Grouping column with two or more categories to compare.

## Options

- `alpha` (default 0.05): Significance level (probability of a false positive you accept).

## What you get out

- survival table per group (time, at-risk n, events, survival probability)
- median survival per group
- log-rank test chi-squared, degrees of freedom and p-value
- number-at-risk table and survival-curve figure for all groups
- methods.txt paragraph
- report.html

## Assumptions

- Right-censoring is non-informative: subjects who drop out are no more and no less likely to have the event than those who remain under observation.
- Censoring is independent of survival time.
- The groups are comparable and their curves are estimated independently.
- Minimum sample size: at least 20 complete observations overall and at least 5 observed events per group for the curves and log-rank test to be meaningful. With fewer, the analysis runs but flags an expert review.

## Limitations

- Survival curves describe this sample only; they are not a cure rate or a true population risk, and informative censoring biases them heavily.
- The log-rank test compares whole curves; it does not quantify how much groups differ or give a hazard ratio, and it is not causation.
- Heavy censoring (>70%) or very few events make the right tail and the median unreliable.
- Missing values in the chosen columns are excluded (and reported), not imputed.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis kaplan-meier --extra time=<time> --extra event=<event> --group <group>
```
