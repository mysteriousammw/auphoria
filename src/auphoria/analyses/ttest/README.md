# Independent-Samples t-Test (`ttest`)

Compares the average of a **numeric outcome** between **two independent
groups** — e.g. plant height between a treatment and a control, exam score
between two teaching methods, or growth between two strains.

## When to use it

- Your outcome is a number (height, weight, score, time, concentration).
- You have a grouping column with **exactly two** categories.
- The two groups are **independent** (different observations; not the same
  subject measured twice).
- You want to know whether the group averages differ more than chance would
  suggest.

## What you get

- Group statistics (n, mean, SD per group).
- The t statistic, degrees of freedom, p-value, mean difference.
- Cohen's d effect size with a plain-English label (negligible / small /
  medium / large).
- A box-and-whisker figure of the two groups.
- A `methods.txt` paragraph you can paste into a paper.

## Choices

- **equal_var** (default `false`): uses **Welch's** t-test, which does not
  assume the two groups have equal spread. Set `true` for the classic pooled
  (Student) test if you are sure the variances are equal. Welch is the safer
  default.
- **alpha** (default `0.05`): significance level.
- **tail** (default `two-sided`): direction of the test.

## Assumptions & limitations

- Outcome must be numeric; group must have exactly two categories.
- For small samples the outcome should be roughly normal in each group;
  strongly skewed data should use a rank-based comparison (planned analysis).
- A significant p-value does **not** prove the group caused the difference.
- Missing values in the two used columns are counted and excluded (never
  imputed or replaced).

## Check

Run `auphoria info ttest` for the manifest (inputs, parameters, assumptions).
The automated tests (`tests/test_ttest.py`) verify t, df and p against
SciPy's reference implementation and against hand-computed textbook values on
small synthetic data.

> Maturity: **experimental** (not "validated").