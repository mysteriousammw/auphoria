# Relative Risk & Odds Ratio (2x2)

`odds-and-risk` · maturity: **experimental**

Discipline packs: `health`, `agri-animal`  

Validation reference: 2x2 table a=40,b=20,c=15,d=45 gives OR = 40*45/(20*15) = 6.0 and RR = (40/60)/(15/60) = 2.667; chi-square and Fisher cross-checked vs scipy.stats.  


## What it does

Builds a 2x2 table from two binary categorical columns (a binary exposure and a binary outcome) and reports the relative risk and the odds ratio, each with a Woolf-log 95% confidence interval, plus a chi-square test (Yates) and Fisher's exact test.

## What you need

- **exposure** (categorical-column, required): Binary exposure/group column (e.g. treated/control, exposed/unexposed).
- **outcome** (categorical-column, required): Binary outcome column (e.g. recovered/not, event/no event).

## Options

- `alpha` (default 0.05): Significance level (probability of a false positive you accept).
- `event_level` (default ): The outcome category to treat as the 'event' (e.g. 'yes' or 'disease'). Leave blank to let AUPHORIA pick it (the first category alphabetically) — if your event is not named first, set this to the actual event label.

## What you get out

- 2x2 contingency table with counts and row totals
- row percentage table (percentages within each exposure group)
- effect-measures table (relative risk, odds ratio, 95% CIs, chi-square, Fisher p, n)
- bar figure of event rate by exposure group
- methods.txt paragraph
- report.html

## Assumptions

- Each column has exactly two categories (a 2x2 analysis); observations are independent and every observation belongs to one cell of the table.
- The chosen measure matches the study design — relative risk suits a cohort or trial, while the odds ratio also suits a case-control (or cross-sectional) study, where only the OR is meaningful.
- Cell counts are large enough for normal-approximation confidence intervals; whenever an expected cell count is below 5 the chi-square p-value is flagged as approximate and the Fisher exact p-value is used.
- When any observed cell is zero, a Haldane 0.5 continuity correction is applied to the odds ratio and its interval, and the result is warned about.
- Missing values in the two chosen columns are counted and excluded, never imputed.

## Limitations

- RR and OR describe association, not causation.
- An odds ratio is not equal to a relative risk when the outcome is common; do not report an OR as 'times more likely' in that setting.
- For cross-sectional or case-control data, only the odds ratio is meaningful; the relative risk would be misleading because outcome prevalence is fixed by the sampling design.
- Zero cells (after Haldane correction) and small counts give wide, uncertain confidence intervals.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis odds-and-risk --extra exposure=<exposure> --outcome <outcome>
```
