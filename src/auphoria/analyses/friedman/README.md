# Friedman Test (`friedman`)

Tests whether **at least one time point** differs from the others for a
**numeric outcome measured on the SAME subjects** at **two or more times** —
e.g. a score taken each week, or a measure before / after / at follow-up —
without assuming the data are normally distributed. It is the non-parametric
counterpart of repeated-measures ANOVA (it works on the ranks *within each
subject*, not the raw means).

## When to use it

- Your outcome is a number or an ordinal score (rankable), and is **not**
  reasonably normally distributed (skewed, heavy-tailed, with outliers).
- The same set of subjects is measured at **two or more** time points (or
  under two or more related conditions).
- Your data are in **long format**: one row per subject per time, with an
  outcome column, a subject column (e.g. an id), and a time column.
- You want to know whether at least one time point sits apart from the
  others more than chance would suggest.

## What you get

- Descriptive statistics by time point (n, median, interquartile range).
- The Friedman chi2 statistic, degrees of freedom (df = k − 1, where k is the
  number of time points), and the p-value.
- A pairwise post-hoc table: a Wilcoxon signed-rank test on each pair of time
  points with a Bonferroni correction — this locates WHICH times differ.
- A median-by-time box/line figure.
- A `methods.txt` paragraph you can paste into a paper.

## Choices

- **alpha** (default `0.05`): significance level.

## Assumptions & limitations

- The outcome must be numeric (or ordinal) and measured on the **same**
  subjects at every time point.
- You need **two or more** time points and **at least three** subjects
  (four or more after dropping incomplete subjects).
- The rankable, related-measures design is the point of the test — you are
  comparing repeated measurements, not independent groups.
- A subject missing **any** time point cannot contribute a complete block, so
  that subject is dropped and reported — missing cells are **never imputed**.
- A significant p-value says *some* time point differs, but **not which** —
  read the pairwise (Bonferroni-corrected) post-hoc table to locate it.
- Because it works on ranks, it is not a test of the medians themselves, and
  it does not prove that time (or treatment order) caused the change.

## When NOT to use it

- **Independent groups** (different subjects in each group) → use a
  Kruskal-Wallis test or one-way ANOVA.
- **Exactly two measurements** → a Wilcoxon signed-rank test is the direct
  two-time-point equivalent.
- **Normally distributed repeated measures with a clear structure** →
  repeated-measures ANOVA (more powerful, more assumptions).

## How to read the output

The p-value answers: "if there really were no difference between the time
points, how unlikely is a within-subject rank spread this large by chance
alone?" p < alpha is called statistically significant, which is the trigger
to consult the pairwise post-hoc table — the Friedman test itself does *not*
name the differing time points.

## Check

Run `auphoria info friedman` for the manifest (inputs, parameters,
assumptions). The automated tests (`tests/test_friedman.py`) verify chi2 and
p against SciPy's reference implementation and against a hand-computed
example: 3 time points × 6 subjects where each subject ranks 1, 2, 3
(A = [1..6], B = [2..7], C = [3..8]) → chi2 = 12, df = 2, with the
Bonferroni-corrected post-hoc verified against the raw Wilcoxon p-values.

> Maturity: **experimental** (not "validated"). With fewer than 6 complete
> subjects a prominent "needs expert review" notice is shown because the
> chi-squared approximation is unreliable with so few blocks.