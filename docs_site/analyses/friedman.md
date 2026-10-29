# Friedman Test

`friedman` · maturity: **experimental**

Discipline packs: `social`, `health`  

Validation reference: 3 treatments x 6 subjects; cross-checked vs scipy.stats.friedmanchisquare  


## What it does

Tests whether at least one time point (repeated measurement) differs from the others for a numeric outcome measured on the same subjects at two or more times, without assuming normally distributed data. It is the non-parametric alternative to repeated-measures ANOVA. Reports the chi2 (Friedman) statistic, degrees of freedom, the p-value, medians by time, and pairwise post-hoc comparisons with a Bonferroni correction.

## What you need

- **outcome** (numeric-column, required): The numeric or ordinal outcome measured repeatedly (e.g. score).
- **subject** (categorical-column, required): The column identifying each subject measured repeatedly (e.g. id).
- **time** (categorical-column, required): The column identifying the time point or condition (e.g. week).

## Options

- `alpha` (default 0.05): Significance level (probability of a false positive you accept).

## What you get out

- descriptives table by time point (n, median, IQR)
- Friedman test result table (chi2, df, p-value, n subjects, significance)
- pairwise post-hoc table (Wilcoxon signed-rank, Bonferroni-corrected p-values)
- median-by-time line/box figure
- methods.txt paragraph
- report.html

## Assumptions

- The outcome is measured at least twice (preferably three or more times) on the SAME subjects, so the measurements at different times are related.
- The outcome is measured on at least an ordinal scale, so values can be ranked.
- The subjects are a sample from the population of interest; the test does not assume normality but does assume the blocking (subject) effect is present in the data.

## Limitations

- Needs two or more time points and at least three subjects (with fewer than three subjects the chi2 approximation is unreliable).
- A significant result shows SOME time point tends to rank higher or lower than the others, but it does not say WHICH times differ — follow up with the pairwise post-hoc table.
- It is a test on ranks, not on the mean values; it answers whether the distributions differ, not by how much.
- Missing cells within a subject mean that subject cannot be used at all (the subject must have an outcome at every time). Incomplete subjects are dropped and reported, never imputed.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis friedman --outcome <outcome> --extra subject=<subject> --extra time=<time>
```
