# Kruskal-Wallis H Test (`kruskal-wallis`)

Compares the **distribution** of a **numeric or ordinal outcome** across
**three or more independent groups** — e.g. growth scores across several
treatments, or survey scores across three teaching methods — without assuming
the data are normally distributed. It is the non-parametric counterpart of
one-way ANOVA (i.e. it works on the ranks of the values, not the means).

## When to use it

- Your outcome is a number or an ordinal score (rankable), and is **not**
  reasonably normally distributed (skewed, heavy-tailed, or with clear
  outliers).
- You have a grouping column with **three or more** categories.
- The groups are **independent** (different observations; not the same
  subject measured repeatedly).
- You want to know whether the groups' distributions sit apart more than
  chance would suggest.

## What you get

- Group statistics (n and median per group).
- The H statistic, degrees of freedom (df = k − 1, where k is the number of
  groups), and the p-value.
- A box-and-whisker figure of all the groups.
- A `methods.txt` paragraph you can paste into a paper.

## Choices

- **alpha** (default `0.05`): significance level.

## Assumptions & limitations

- Outcome must be numeric (or ordinal); group must have three or more
  categories.
- The groups must be **independent** and the outcome at least ordinal
  (rankable).
- To read the result as a shift in medians, the distributions of the groups
  should have a **similar shape (spread)**. If the spreads differ a lot,
  describe the result as a difference in distributions, not a median shift.
- No normality assumption is needed, but if your data ARE reasonably normal
  a one-way ANOVA has more power — don't reach for this test just to
  "be safe".
- A significant p-value shows the groups are **not all the same**, but it
  does **not** say which groups differ — follow up with a post-hoc test
  (e.g. Dunn's) to locate the differences.
- A significant p-value does **not** prove the group variable caused the
  difference.
- Missing values in the two used columns are counted and excluded (never
  imputed or replaced).

## When NOT to use it

- **Exactly two groups** → use a t-test or a Mann-Whitney U test.
- **Data are reasonably normal** → use one-way ANOVA (more powerful).
- **Repeated measurements on the same subjects** → use a Friedman test (this
  is the repeated-measures counterpart).
- You specifically want to compare **means** → Kruskal-Wallis works on ranks,
  not means.

## How to read the output

The p-value answers: "if the groups really came from the same distribution,
how unlikely is a spread this large by chance alone?" p < alpha is called
statistically significant. It does **not** identify which pair of groups
differs — a significant result is the trigger for a post-hoc test, not the
end of the story.

## Check

Run `auphoria info kruskal-wallis` for the manifest (inputs, parameters,
assumptions). The automated tests (`tests/test_kruskal_wallis.py`) verify H
and p against SciPy's reference implementation and against hand-computed
ranks (A = [1,2,3], B = [4,5,6], C = [7,8,9] → rank sums 6, 15, 24 → H = 7.2,
df = 2).

> Maturity: **experimental** (not "validated").