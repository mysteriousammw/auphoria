# One-Way ANOVA (`anova-oneway`)

Tests whether **three or more independent groups** differ in their average
**numeric outcome** — e.g. plant height across three fertiliser doses, exam
score across three teaching methods, or growth across several strains. A
significant result is followed by a **Tukey post-hoc** comparison so you can
see exactly which groups differ.

## When to use it

- Your outcome is a number (height, weight, score, time, concentration).
- You have a grouping column with **three or more** categories.
- The groups are **independent** (different observations; not the same
  subject measured several times).
- You want to know whether any of the group averages differ more than chance
  would suggest — and, if so, which ones.

## What you get

- Group statistics (n, mean, SD per group).
- The classic ANOVA table (sum of squares between / within / total,
  degrees of freedom, mean square, F, p).
- **eta-squared** effect size with a plain-English label (negligible /
  small / medium / large).
- A **Tukey post-hoc** table: every pair of groups with its mean
  difference, q statistic and p-value, flagged as significant or not at
  your alpha.
- A box-and-whisker figure of all groups side by side.
- A `methods.txt` paragraph you can paste into a paper.

## Choices

- **alpha** (default `0.05`): significance level for the F test, for the
  assumption checks (Levene, Shapiro-Wilk) and for the Tukey post-hoc flags.

## Assumptions (checked and reported, never silently ignored)

- The outcome is roughly **normal within each group** (Shapiro-Wilk, per
  group; ANOVA is fairly robust for larger samples).
- **Equal variances** across groups (Levene's test).
- Groups are **independent**; each group has at least two observations.
- If a check fails you get a WARN verdict and a warning — the ANOVA still
  runs, but you are told to consider **Kruskal-Wallis** instead.

## When NOT to use it

- **Exactly two groups** → use the independent-samples **t-test** (the tool
  refuses with this hint).
- **Very non-normal or strongly unequal-variance data** → use
  **Kruskal-Wallis** (planned analysis).
- **Repeated measurements on the same subjects** (before/after, same person
  in several conditions) → not independent groups; you need a repeated-
  measures ANOVA or Friedman test.

## How to read the output

1. **F and p**: p < alpha means at least one group average differs from the
   others. Use `F(df_between, df_within)` in a paper, e.g. `F(2, 9) = 54.00`.
2. **eta-squared**: fraction of outcome variation explained by the group —
   0.02-ish is small, 0.06-ish medium, 0.14+ large.
3. **Tukey table**: which pairs actually differ and by how much. A
   significant F does *not* tell you which groups differ — that is what the
   post-hoc is for.
4. Common mistake to avoid: running many separate t-tests instead of one
   ANOVA inflates the chance of a false positive (type-I error inflation).

> Maturity: **experimental** (not "validated").
