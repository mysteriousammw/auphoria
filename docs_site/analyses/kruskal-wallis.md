# Kruskal-Wallis H Test

`kruskal-wallis` · maturity: **experimental**

Discipline packs: `core`, `social`, `health`  

Validation reference: A=[1,2,3], B=[4,5,6], C=[7,8,9]; cross-checked vs scipy.stats.kruskal  


## What it does

Compares the distribution of a numeric or ordinal outcome across three or more independent groups (for example, plant growth under several treatments) without assuming the data are normally distributed. It is the non-parametric alternative to one-way ANOVA. Reports the H statistic, degrees of freedom, the p-value, and group medians.

## What you need

- **outcome** (numeric-column, required): The numeric or ordinal outcome you want to compare (e.g. score).
- **group** (categorical-column, required): The grouping column with three or more categories (e.g. treatment).

## Options

- `alpha` (default 0.05): Significance level (probability of a false positive you accept).

## What you get out

- group statistics table (n, median per group)
- Kruskal-Wallis test result table (H, df, p-value, n)
- box-and-whisker figure comparing the groups
- methods.txt paragraph
- report.html

## Assumptions

- The groups are independent (one observation does not belong to more than one group).
- The outcome is measured on at least an ordinal scale, so values can be ranked.
- To read the result as a shift in medians, the distributions of the groups should have a similar shape (spread); otherwise the test is best described as comparing distributions (stochastic ordering), not medians.

## Limitations

- It needs three or more groups. For exactly two groups use a Mann-Whitney U test, which the engine suggests if the group column has fewer than three categories.
- No normality assumption is needed, but when the data ARE reasonably normal a one-way ANOVA has more power.
- A significant result shows the groups' distributions sit apart; it does not say WHICH groups differ. Follow up with a post-hoc test (e.g. Dunn's) if you need pairwise comparisons.
- Missing values in the two chosen columns are excluded (and reported), not imputed.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis kruskal-wallis --outcome <outcome> --group <group>
```
