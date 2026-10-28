# Paired-Samples t-Test (`ttest-paired`)

Compares measurements taken on the **same subjects** at two time points — e.g.
blood pressure before vs after a treatment, exam score before vs after a study
course, or weight at the start vs end of a diet. It answers one question: **did
the average change?**

The test works on the **pair differences** (after − before) for each subject,
so each row of your data must hold **one subject measured twice**.

## When to use it

- You have **two numeric columns** measured on the same units (one row =
  one subject at two times).
- You are asking "did the average change between the two measurements?"
- You have at least two complete pairs (more is much better).

## What you get

- Paired statistics (n, mean before, mean after, mean difference, SD of the
  differences).
- The t statistic, degrees of freedom, p-value, and a 95% confidence interval
  for the mean difference.
- Cohen's d_z effect size (the mean difference in units of the differences'
  spread) so you can judge practical importance.
- A before/after figure with one thin line per subject (green = increase,
  red = decrease), t and p in the title.
- A `methods.txt` paragraph you can paste into a paper.

## Choices

- **alpha** (default `0.05`): significance level. The confidence interval is
  computed at 1 − alpha (so 95% by default).

## Assumptions & limitations

- The two columns must hold the **same subjects** measured twice. If the
  before and after groups are *different* people, this test is wrong — use
  the independent-samples t-test instead.
- The pair differences should be **approximately normal**. A Shapiro-Wilk
  check is run when the sample size allows; if the differences look
  non-normal, this tool warns you and recommends the **Wilcoxon
  signed-rank test on the differences** instead.
- With fewer than 10 pairs the normality assumption cannot be verified
  reliably — results are preliminary.
- Missing values in the two used columns are **counted and excluded** (never
  imputed or replaced).
- A significant p-value does **not** prove the treatment caused the change —
  it could be natural change over time or regression to the mean.

## When NOT to use it

- The two groups are **independent** (different subjects). Use the
  independent-samples t-test.
- You have **more than two time points** per subject. This test compares only
  one pair of measurements; a repeated-measures approach is planned.
- The differences are strongly skewed *and* the sample is small. Use the
  Wilcoxon signed-rank test on the differences.

## Common mistakes

- Running an **independent** t-test on paired data: pairing is real
  information, and ignoring it inflates the standard error and can hide a
  genuine change.
- Forgetting that **each row must be one subject at two times**; if your rows
  are "subject A before" and "subject A after" in separate rows, the pairing
  is lost — reshape the data first.
- Reading a significant result as proof of causation (see Assumptions).

## Check

Run `auphoria info ttest-paired` for the manifest (inputs, parameters,
assumptions). The automated tests (`tests/test_ttest_paired.py`) verify t, df,
p, the mean difference and Cohen's d_z against SciPy's reference
implementation and against hand-computed values on small synthetic data
(differences 4, 3, 2, 3, 2 → mean 2.8, t = 7.4833, p = 0.0017).

> Maturity: **experimental** (not "validated").
