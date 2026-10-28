# Mann-Whitney U Test (`mann-whitney`)

Compares the **distribution** of a **numeric or ordinal outcome** between
**two independent groups** — e.g. survey scores between two teaching
methods, or growth scores between two strains — without assuming the data
are normally distributed.

## When to use it

- Your outcome is a number or an ordinal score (rankable), and is **not**
  reasonably normally distributed (skewed, heavy-tailed, or with clear
  outliers).
- You have a grouping column with **exactly two** categories.
- The two groups are **independent** (different observations; not the same
  subject measured twice).
- You want to know whether the two groups' distributions sit apart more
  than chance would suggest.

## What you get

- Group statistics (n and median per group).
- The U statistic and p-value.
- Rank-biserial r effect size with a plain-English label (negligible /
  small / medium / large) — its sign shows which group tends to score
  higher.
- A box-and-whisker figure of the two groups.
- A `methods.txt` paragraph you can paste into a paper.

## Choices

- **alpha** (default `0.05`): significance level.
- **tail** (default `two-sided`): direction of the test.

## Assumptions & limitations

- Outcome must be numeric (or ordinal); group must have exactly two
  categories.
- The two samples must be **independent** and the outcome at least ordinal
  (rankable).
- To read the result as a location shift ("one group tends higher"), the
  two distributions should have a **similar shape (spread)**. If the
  spreads differ a lot, describe the result as a difference in
  distributions (stochastic superiority), not a median shift.
- No normality assumption is needed, but if your data ARE reasonably normal
  a t-test is more powerful — don't reach for this test just to "be safe".
- A significant p-value does **not** prove the group caused the difference.
- Missing values in the two used columns are counted and excluded (never
  imputed or replaced).

## When NOT to use it

- **Data are reasonably normal** → use the independent-samples t-test
  (more powerful).
- **More than two groups** → use a Kruskal-Wallis test.
- **Paired / repeated measures** (same subject measured twice) → use a
  Wilcoxon signed-rank test.
- You specifically want to compare **means** → the Mann-Whitney test is not
  a test of means.

## How to read the output

The p-value answers: "if the two groups really came from the same
distribution, how unlikely is a difference this large by chance alone?"
p < alpha is called statistically significant. The rank-biserial r tells
you the size and direction: r ≈ 1 means group 1 (listed first) almost always
ranks above group 2; r ≈ 0 means little separation.

## Check

Run `auphoria info mann-whitney` for the manifest (inputs, parameters,
assumptions). The automated tests (`tests/test_mann_whitney.py`) verify U
and p against SciPy's reference implementation and against hand-computed
ranks (U = 0, p = 0.05714 two-sided) on small synthetic data.

> Maturity: **experimental** (not "validated").
