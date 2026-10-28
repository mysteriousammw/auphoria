# Paired-Samples t-Test

`ttest-paired` · maturity: **experimental**

Validation reference: Hand-computed paired example; cross-checked vs scipy.stats.ttest_rel  


## What it does

Compares measurements taken on the same subjects (for example, before vs after a treatment) and answers: did the average change? Each row must hold one subject measured twice; the test works on the pair differences and reports the mean difference, t, df, p-value, a confidence interval, and an effect size (Cohen's d_z).

## What you need

- **before** (numeric-column, required): The first measurement of each subject (e.g. score before the treatment).
- **after** (numeric-column, required): The second measurement of the same subjects (e.g. score after the treatment).

## Options

- `alpha` (default 0.05): Significance level (alpha = 0.05).

## What you get out

- paired statistics table (n, mean before, mean after, mean difference, SD of differences)
- paired-samples t-test table (t, degrees of freedom, p-value, 95% CI, Cohen's d_z)
- before/after connected-line figure, one line per subject
- methods.txt paragraph
- report.html

## Assumptions

- Both measurements are on a continuous (numeric) scale.
- The two columns hold the SAME subjects measured twice; each row is one subject at two time points (e.g. before and after).
- The pair differences (after - before) are approximately normally distributed; the test is fairly robust for larger samples.
- At least two complete pairs are needed for the test to run.
- A warning is raised when the sample is too small to verify normality.

## Limitations

- Only ONE pair of measurements per subject and one comparison is supported. For more than two time points use a repeated-measures approach (planned analysis).
- If the differences are strongly non-normal, the Wilcoxon signed-rank test on the differences is the safer alternative (planned analysis).
- This test is only for paired data. If the two groups are independent, use the independent-samples t-test instead; running the wrong one can inflate or hide a real difference.
- A significant p-value does not prove the treatment caused the change; it could be natural change over time or regression to the mean.
- Missing values in the two chosen columns are excluded (and reported), not imputed.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis ttest-paired --extra before=<before> --extra after=<after>
```
