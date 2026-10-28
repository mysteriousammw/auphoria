# Chi-Square Test of Independence (`chi-square`)

Tests whether **two categorical variables are associated** — whether the
pattern of counts in one variable (e.g. treatment) differs across the
categories of another (e.g. outcome category: recovered / not recovered).

## When to use it

- You have **two categorical columns** (each with two or more categories —
  e.g. treatment x outcome, species x habitat, gender x pass/fail).
- You want to know whether the categories are related: do the count
  patterns differ from what pure chance would produce?
- Each observation belongs to exactly **one** category of each variable
  (categories are mutually exclusive) and observations are independent.

## What you get

- A **contingency table** with counts and row totals.
- A **row percentage table** (percentages within each row).
- The **chi-square statistic, degrees of freedom, and p-value**.
- **Cramer's V** effect size with a plain-English label (negligible /
  small / medium / large).
- A **stacked bar figure** showing the proportion of each outcome category
  within each group.
- A `methods.txt` paragraph you can paste into a paper.
- An **expected-count check**: if any expected cell count is 5 or fewer the
  result is flagged as approximate and Fisher's exact test is recommended
  (for 2x2 tables).

## Choices

- **alpha** (default `0.05`): significance level used for the
  "significant at alpha?" verdicts.

## Assumptions

- **Expected cell counts**: every cell should have an expected count of at
  least 5. When this fails the p-value is only approximate — this module
  warns you and recommends Fisher's exact test for 2x2 tables instead.
- **Independent observations**: one row of data must not belong to two
  cells (no repeated measures, no paired categories).
- **Mutually exclusive categories**: each observation falls into exactly
  one category of each variable.

## When NOT to use it

- When expected cell counts are small (below 5) and you need a reliable
  p-value — use **Fisher's exact test** (planned analysis) for 2x2 tables.
- With **paired or repeated categorical data** (e.g. before/after on the
  same subjects) — that design needs a paired test (e.g. McNemar), not
  chi-square.
- When you need to know the **direction or absolute size** of an
  association — chi-square only tells you whether the pattern differs, and
  Cramer's V is relative to the strongest possible association.

## How to read the output

- The **contingency table** shows the raw counts; the **row percentages**
  show, within each row, what fraction falls into each column — this is what
  to look at to see *which* category has more of a given outcome.
- The **p-value** is the probability of seeing count patterns at least this
  extreme if the two variables were unrelated. `p < alpha` means the
  association is called statistically significant.
- **Cramer's V** ranges from 0 (no association) to 1 (perfect association);
  0.1 / 0.3 / 0.5 are the usual negligible / small / medium / large
  breakpoints.
- A significant result means the counts differ across groups — it does
  **not** mean one variable caused the other.

Run `auphoria info chi-square` for the manifest (inputs, parameters,
assumptions). The automated tests (`tests/test_chi_square.py`) verify the
chi-square statistic and p-value against SciPy's reference implementation
and hand-check Cramer's V on small synthetic data.

> Maturity: **experimental** (not "validated").
