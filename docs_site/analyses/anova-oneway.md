# One-Way ANOVA

`anova-oneway` · maturity: **experimental**

Validation reference: Three groups, means 4/10/16; cross-checked vs scipy.stats.f_oneway + studentized_range  


## What it does

Tests whether three or more independent groups differ in their average numeric outcome (for example, plant height across three fertiliser doses) with a one-way analysis of variance, at a single significance level, and follows a significant result with a Tukey post-hoc comparison so you can see which groups actually differ.

## What you need

- **outcome** (numeric-column, required): The numeric outcome you want to compare (e.g. height_cm).
- **group** (categorical-column, required): The grouping column with three or more categories (e.g. treatment).

## Options

- `alpha` (default 0.05): Significance level (probability of a false positive you accept).

## What you get out

- group statistics table (n, mean, standard deviation per group)
- ANOVA table (sum of squares, degrees of freedom, mean square, F, p)
- effect size table (eta-squared)
- Tukey post-hoc table (pairwise mean differences, q, p)
- box-and-whisker figure comparing all groups
- methods.txt paragraph
- report.html

## Assumptions

- The outcome is measured on a continuous (numeric) scale.
- The groups are independent (one observation does not belong to both).
- The outcome is roughly normally distributed within each group (checked with Shapiro-Wilk; ANOVA is fairly robust for larger samples).
- The groups have equal variances (checked with Levene's test); if they clearly do not, prefer Kruskal-Wallis.
- Each group has at least two non-missing observations.

## Limitations

- A significant F only says that at least one group differs from the others; it does not say which groups differ or by how much — use the Tukey post-hoc table for that.
- A significant result does not prove the group caused the difference; ANOVA is not causation.
- Missing values in the two chosen columns are excluded (and reported), not imputed.
- Very non-normal or very unequal-variance data should use Kruskal-Wallis instead; repeated measurements on the same subjects need a different design (repeated-measures ANOVA or Friedman).

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis anova-oneway --outcome <outcome> --group <group>
```
