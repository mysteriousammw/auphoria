# Repeated-Measures ANOVA

`anova-repeated` · maturity: **experimental**

Discipline packs: `social`, `health`, `life-science`  

Validation reference: Balanced 6-subject by 3-time synthetic dataset; the within-subjects F (and its hand-computed partial eta-squared) are cross-checked against the same statsmodels AnovaRM call in tests/test_anova_repeated.py; Mauchly W comes from the within-subjects covariance matrix.  


## What it does

Tests whether a numeric outcome changes across several time points measured on the SAME subjects (a within-subject design). The data are in LONG format: one row per subject per time point, with a subject id, a time column and the numeric reading. The outcome is pivoted to wide (subject by time) and analysed with statsmodels AnovaRM. It reports descriptives per time point, Mauchly's sphericity test, the within-subjects ANOVA table (sum of squares, df, mean square, F, p and a hand-computed partial eta-squared), Bonferroni-corrected paired t-test post-hoc comparisons between time points, and a line plot of the mean across time with faint per-subject trajectories.

## What you need

- **outcome** (numeric-column, required): The numeric reading measured repeatedly (e.g. reaction_time).
- **subject** (categorical-column, required): The id column identifying each subject (e.g. participant_id).
- **time** (categorical-column, required): The within-subject factor naming the repeated measurement (e.g. time_point).

## Options

- `alpha` (default 0.05): Significance level (probability of a false positive you accept).

## What you get out

- descriptives per time point (n, mean, SD)
- Mauchly sphericity test (W, chi-square, df, p)
- within-subjects ANOVA table (sum of squares, df, mean square, F, p, partial eta-squared)
- Bonferroni-corrected paired t-test post-hoc comparisons between time points
- line plot of mean across time with faint per-subject trajectories
- methods.txt paragraph
- report.html

## Assumptions

- The outcome is numeric and measured on the same subjects at every time point (a within-subject, repeated-measures design).
- Sphericity: the variances of the differences between every pair of time points are roughly equal. This is checked with Mauchly's test and reported. When it is violated (p < alpha) the ordinary repeated-measures F is only an approximation and a mixed model is recommended.
- The differences between time points are approximately normally distributed (paired t-tests are reasonably robust for moderate samples).
- No carry-over or order effects: measurement at one time point does not change the value at the next simply because of the order in which they were taken.
- Every subject is measured at every included time point (no missing cells). Missing values are excluded listwise with a warning, never imputed. If that leaves any subject without a complete set of time points the analysis refuses and suggests a mixed model instead.
- Minimum sample size: at least 2 time points and at least 3 subjects are required to run. Results with fewer than about 10 subjects are unstable and are flagged for expert review.

## Limitations

- A significant time effect only tells you the outcome changes across time. It does NOT say which specific time points differ; that requires the post-hoc comparisons.
- With exactly 2 time points the repeated-measures F equals the squared paired t-test and sphericity is not an issue (there is only one difference to check).
- A within-subject ANOVA does not prove causation, and the time factor is treated as a simple categorical grouping that you have told it nothing else about (no assumed spacing or trend shape).
- Missing data is excluded listwise (and reported) but never imputed. Heavy missingness biases the result, and a subject with an incomplete set of time points is refused rather than silently averaged.
- If sphericity is violated the p-value is only approximate. Consider a Greenhouse-Geisser corrected test or a mixed-effects model.
- This is an advanced analysis carried at experimental maturity. It emits a prominent requirement for expert review when used with small samples, when sphericity is violated, or when only 2 time points are available.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis anova-repeated --outcome <outcome> --extra subject=<subject> --extra time=<time>
```
