# Independent-Samples t-Test

`ttest` · maturity: **experimental**

Validation reference: Hand-computed textbook example (independent-samples t); cross-checked vs scipy.stats.ttest_ind  


## What it does

Compares the average of a numeric outcome between two independent groups (for example, plant height between a treatment and a control) and reports the difference, the p-value, and an effect size (Cohen's d).

## What you need

- **outcome** (numeric-column, required): The numeric outcome you want to compare (e.g. height_cm).
- **group** (categorical-column, required): The grouping column with exactly two categories (e.g. treatment).

## Options

- `alpha` (default 0.05): Significance level (probability of a false positive you accept).
- `equal_var` (default False): Use the classic pooled-variance test instead of Welch's. Defaults to false because Welch works whether or not the two groups have equal spread, and is the recommended modern choice.

- `tail` (default two-sided): Direction of the test.

## What you get out

- group statistics table (n, mean, standard deviation per group)
- t-test result table (t, degrees of freedom, p-value, mean difference, Cohen's d)
- box-and-whisker figure comparing the two groups
- methods.txt paragraph
- report.html

## Assumptions

- The outcome is measured on a continuous (numeric) scale.
- The two groups are independent (one observation does not belong to both).
- Each group has at least two non-missing observations.
- For small samples, the outcome should be roughly normally distributed within each group; if it is very skewed, results are approximate.
- Welch's variant does not assume equal variances; the pooled variant does.

## Limitations

- Only two groups can be compared. For three or more groups use a one-way comparison (planned analysis).
- A significant p-value does not prove the difference is caused by the group; correlation is not causation.
- Missing values in the two chosen columns are excluded (and reported), not imputed.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis ttest --outcome <outcome> --group <group>
```
