# Repeated-Measures ANOVA (`anova-repeated`)

Tests whether a **numeric outcome** changes across **several time points**
measured on the **same subjects** — for example, anxiety measured at three
sessions, blood pressure at four clinic visits, or reaction time across several
training blocks. Because the same people are measured repeatedly, the
observations are *not* independent, so an ordinary between-group ANOVA is the
wrong tool — this one accounts for the within-subject design.

## When to use it

- Your data are in **long format**: one row per subject per time point, with a
  subject id, a time/occasion column, and the numeric reading.
- You have the **same subjects** at every time point (a within-subject /
  repeated-measures design).
- You want to know whether the **mean outcome changes across time** and, if
  so, **which time points differ**.

## What the tool does with the data

1. Pivots the long data to **wide** (each row = one subject, each column = one
   time point).
2. Runs a **within-subjects ANOVA** (statsmodels `AnovaRM`).
3. Reports descriptives per time point, Mauchly's **sphericity** test, the
   ANOVA table with a hand-computed **partial eta-squared**, and
   **Bonferroni-corrected paired t-tests** between time points.

## What you get

- **Descriptives by time point** — n, mean, SD for each occasion.
- **Sphericity (Mauchly's test)** — W, chi-square, df, p. A significant
  `p < alpha` warns that the ordinary F is only approximate.
- **Within-subjects ANOVA table** — sum of squares, df, mean square, F, p, and
  **partial eta-squared** for the time effect (computed by hand as
  `SS_time / (SS_time + SS_error)`), with a plain-English effect-size label.
- **Post-hoc comparisons** — paired t-tests between every pair of time points,
  **Bonferroni-corrected** for multiple testing, reporting each pair's mean
  difference and corrected p-value.
- **Profile line plot** — mean ± SE across time, with faint per-subject lines.
- A `methods.txt` paragraph you can paste into a paper.

## Choices

- **alpha** (default `0.05`): significance level for the F test, sphericity
  test, and post-hoc comparisons.

## Assumptions (checked and reported, never silently ignored)

A PASS/WARN verdict is emitted for each check; a WARN never stops the analysis.

- **Sphericity**: the variances of the differences between every pair of time
  points are roughly equal (Mauchly's test). If violated, the standard F is
  only approximate.
- **Normality of the paired differences** (paired t-tests are fairly robust for
  moderate samples).
- **No carry-over / order effects.** No **missing cells** (every kept subject
  is measured at every time point).
- **Exactly one reading per subject per time point.**

### Minimum sample size (state this clearly)

Repeated-measures ANOVA needs **at least 2 time points and at least 3
subjects** to run at all. Results from **fewer than about 10 subjects** are
unstable and trigger a prominent **needs-expert-review** banner.

## When NOT to use it

- **Independent groups** (different people in each condition) → use a
  between-group ANOVA (`anova-oneway`) instead.
- **A subject is missing a whole time point** → the tool refuses (it never
  averages over or imputes missing cells). Consider a **mixed-effects model**
  (`mixed-effects`), which tolerates unbalanced repeated measures.
- **Only one before/after time point** → a paired t-test (`ttest-paired`) is
  the right tool.
- **Non-normal repeated data or a sphericity violation you cannot correct** →
  the non-parametric **Friedman test** is a common alternative.

## How to read the output

1. **Sphericity first.** If Mauchly's `p < alpha`, the sphericity assumption is
   violated — the F and p below are only approximate; consider a correction or
   a mixed model.
2. **Time effect F and p.** `p < alpha` means the mean outcome changes across
   time. Report as `F(df_time, df_error)`, e.g. `F(2, 10) = 21.79`.
3. **Partial eta-squared** — the fraction of within-subject variance explained
   by time. Roughly: 0.01 small, 0.06 medium, 0.14+ large.
4. **Post-hoc comparisons** look at *which* pairs differ. Use the
   **Bonferroni-corrected** p, not the raw one.

## Note on only 2 time points

With exactly **2 time points** the repeated-measures F equals the squared
paired t-test, sphericity is irrelevant, and you cannot assess any trend
shape. The score reduces to testing whether the change score is non-zero — the
tool notes this limitation.

## Example

```bash
auphoria run --data my_long.csv --analysis anova-repeated \
  --outcome score --group participant_id --extra time=session
```

> Maturity: **experimental** (not "validated"). This is an advanced analysis;
> when used with small samples, a sphericity violation, or only 2 time points
> it flags a requirement for expert review.