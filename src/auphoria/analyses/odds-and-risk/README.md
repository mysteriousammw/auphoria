# Relative Risk & Odds Ratio (`odds-and-risk`)

Builds a **2x2 table** from two binary categorical columns and reports two
strength-of-association measures, each with a **95% confidence interval**:

- **Relative risk (RR)** — how many times more (or less) *likely* the event
  is in the exposed group than in the unexposed group.
- **Odds ratio (OR)** — the odds of the event in the exposed group divided by
  the odds in the unexposed group.

Both are cross-checked with a **chi-square test** (Yates' correction) and
**Fisher's exact test**.

## When to use it

- You have two columns, each with **exactly two categories**: a binary
  *exposure/group* and a binary *outcome* (e.g. `treated/control` x
  `recovered/not`, `exposed/unexposed` x `infection/no infection`).
- You want to know **how much** more (or less) likely the event is in one
  group than the other, and how precise that estimate is.

## What you get

- A **2x2 contingency table** with counts and row totals.
- A **row percentage table** (event rate within each exposure group).
- A **measures table**: relative risk + 95% CI, odds ratio + 95% CI,
  chi-square statistic and p-value, Fisher exact p-value, sample size.
- A **bar figure** of the event rate in each exposure group.
- A `methods.txt` paragraph you can paste into a paper.

## Choices

- **alpha** (default `0.05`): significance level for the "significant at
  alpha?" verdict and the width of the confidence intervals.

## Assumptions

- Each column has **exactly two categories** and observations are independent.
- The measure matches the **study design**: RR suits a cohort or trial; for a
  case-control or cross-sectional study only the **OR** is meaningful.
- Cells are large enough for normal-approximation intervals. When an expected
  cell count is below 5 the chi-square p is flagged approximate and the
  Fisher p is used. When any cell is **zero**, a **Haldane 0.5 correction** is
  applied to the OR and its interval (with a warning).
- Missing values are counted and excluded, never imputed.

## When NOT to use it

- When a column has more than two categories — use
  **`chi-square`** for an r x c association table.
- When you need to *adjust* for confounders — use a regression (plain
  **`logistic-regression`** for a binary outcome).
- When you must report the **causal effect**, not just an association — this
  module describes association only.

## How to read the output

- **RR > 1** means the event is *more likely* in the exposed group; **RR < 1**
  means less likely; **RR = 1** means no difference. Same for the OR.
- The **95% CI** shows the range the true value plausibly sits in: if the
  interval **does not include 1**, the difference is statistically significant
  at alpha.
- When the outcome is **common**, the OR is *larger* than the RR — do not
  report an OR as "x times more likely".

Run `auphoria info odds-and-risk` for the manifest. The automated tests
(`tests/test_odds_and_risk.py`) verify RR = 2.6667 and OR = 6.0 on a
hand-computed 2x2 table (a=40, b=20, c=15, d=45) and cross-check the chi-square
and Fisher p-values against SciPy.

> Maturity: **experimental** (not "validated").