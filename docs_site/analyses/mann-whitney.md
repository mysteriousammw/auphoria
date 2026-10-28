# Mann-Whitney U Test

`mann-whitney` · maturity: **experimental**

Validation reference: A=[1,2,3], B=[4,5,6,7]; cross-checked vs scipy.stats.mannwhitneyu  


## What it does

Compares the distribution of a numeric or ordinal outcome between two independent groups (for example, survey scores between a treatment and a control) without assuming the data are normally distributed. Reports the U statistic, the p-value, group medians, and an effect size (rank-biserial r).

## What you need

- **outcome** (numeric-column, required): The numeric or ordinal outcome you want to compare (e.g. score).
- **group** (categorical-column, required): The grouping column with exactly two categories (e.g. treatment).

## Options

- `alpha` (default 0.05): Significance level (probability of a false positive you accept).
- `tail` (default two-sided): Direction of the test.

## What you get out

- group statistics table (n, median per group)
- Mann-Whitney U test result table (U, p-value, n1, n2, rank-biserial r)
- box-and-whisker figure comparing the two groups
- methods.txt paragraph
- report.html

## Assumptions

- The two groups are independent (one observation does not belong to both).
- The outcome is measured on at least an ordinal scale, so values can be ranked.
- To read the result as a location shift (one group 'tends higher'), the two distributions should have a similar shape (spread); otherwise the test is best described as comparing distributions (stochastic superiority), not medians.

## Limitations

- Only two groups can be compared. For three or more groups use a Kruskal-Wallis test (planned analysis).
- No normality assumption is needed, but when the data ARE reasonably normal a t-test has more power — the Mann-Whitney test should not be used just to 'be safe' on normal data.
- A significant result shows the groups' distributions sit apart; it is not automatically a difference of medians and not a test of means.
- Missing values in the two chosen columns are excluded (and reported), not imputed.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis mann-whitney --outcome <outcome> --group <group>
```
