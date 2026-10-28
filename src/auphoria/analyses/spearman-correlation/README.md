# Spearman Rank Correlation (`spearman-correlation`)

Measures whether two variables tend to **increase or decrease together when
ranked** — e.g. exam ranking vs hours of study ranking, or a survey score vs
an objective measure. Spearman's rho asks: do the *orders* match, not whether
the points fall on a straight line.

## When to use it

- You have two **numeric** columns (ordinal scales such as ranks or Likert
  scores are fine).
- You want to know whether they move together (and how strongly).
- The relationship is **monotonic** — it goes steadily up, or steadily down,
  but not necessarily in a straight line.
- You are not sure the data is normal or linear; ranks sidestep both worries.

## What you get

- Spearman's `rho` (from −1 to +1), computed on the ranks.
- A p-value (how likely this strong an ordering would be by chance if the
  true correlation were 0).
- The sample size `n` actually used.
- A plain-English description (direction and strength of the monotonic
  relationship).
- A scatter figure of the **ranks**, with a light trend line (visual aid).

## Choices

- `alpha` (default 0.05): the significance level used to judge the p-value.
- `tail` (default `two-sided`): whether to test for any association
  (`two-sided`), specifically positive (`greater`), or specifically negative
  (`less`).

## Assumptions

- Both columns numeric and measured on the same rows.
- The relationship you care about is **monotonic** (steadily up or down).
- No normality assumption — ranks do the work.
- Heavy ties (many equal values) distort rho; you get a warning when ties are
  common.

## When NOT to use it

- When you need the **size of a linear relationship** (how many units of y
  per unit of x) — that is Pearson's `correlation`, or a regression.
- When the relationship is **U-shaped** (low, high, low): rho can be near
  zero even though a strong pattern exists.
- When exact duplicate values are very common — rho becomes unreliable.

## How to read the output

| |rho|    | strength     |
|----------|--------------|
| < 0.2    | negligible   |
| 0.2 – 0.5| weak         |
| 0.5 – 0.8| moderate     |
| ≥ 0.8    | strong       |

A positive rho means higher ranks of x tend to go with higher ranks of y;
negative means they go in opposite directions. rho near zero means **no
monotonic** relationship — a curved pattern may still exist. And remember:
correlation is not causation, and rho says nothing about *how much* one
variable moves with the other.

## Check

`auphoria info spearman-correlation` shows the manifest. Tests
(`tests/test_spearman.py`) verify rho against SciPy's reference
implementation and a hand-computed example (perfect monotonic lines rho = 1
and rho = −1; hand-computed example rho = 0.5).

> Maturity: **experimental** (not "validated").
