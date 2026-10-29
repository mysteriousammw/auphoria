# Bland-Altman Agreement

`bland-altman` · maturity: **experimental**

Validation reference: Hand-computed synthetic example (differences -0.2, 0.1, -0.1, 0.0, 0.1 -> bias -0.02, SD 0.13038, limits -0.2756 and 0.2356); cross-checked against a simple in-test hand routine on a larger random dataset.  


## What it does

Assesses how closely two measurement methods agree when both measure the same quantity on the same subjects (one row per subject). It reports the mean difference (bias), the SD of the differences, the 95% limits of agreement (bias +/- 1.96 * SD), confidence intervals, a Bland-Altman plot, and a proportional-bias check (does the difference grow with the size of the measurement?). The limits are NOT a pass/fail verdict by themselves: you must judge them against an acceptable difference you choose in advance.

## What you need

- **method_a** (numeric-column, required): The first measurement method (e.g. the test instrument or method under evaluation).
- **method_b** (numeric-column, required): The second measurement method (e.g. the reference / established method).

## Options

- `alpha` (default 0.05): Significance level for the confidence intervals and the proportional-bias check.

## What you get out

- agreement statistics table (n, bias, SD of differences, 95% limits of agreement, SE of bias)
- limits of agreement table with 95% confidence intervals
- proportional-bias check table (correlation |difference| vs mean, r and p)
- Bland-Altman plot (difference vs mean, bias line, limits, shaded band, regression line)
- methods.txt paragraph
- report.html

## Assumptions

- Both methods measure the same underlying quantity on a continuous (numeric) scale, on the same subjects, one pair per row are genuine matched measurements.
- The differences (method_a - method_b) are roughly normally distributed; the limits of agreement assume this. Checked with Shapiro-Wilk when the sample size allows.
- The bias and limits of agreement do not change with the magnitude being measured (no proportional bias). A correlation between |difference| and the mean is checked and flagged as a WARN when significant.
- At least three complete pairs are needed for the analysis to run.

## Limitations

- The limits of agreement are NOT a pass/fail check by themselves: whether a given bias and spread is acceptable must be judged externally against a pre-chosen clinically or professionally acceptable difference.
- With small samples the limits of agreement are very unstable (wide confidence intervals); results are preliminary.
- If the differences grow with magnitude (proportional bias), a log-scale analysis is more appropriate.
- The bias differing from zero (shown by a t-test) is not the same as poor agreement, and an insignificant t-test is not proof of good agreement.
- This analysis does not say which method is 'more accurate' — it only measures how well they agree with each other.
- Missing values in the two chosen columns are excluded (and reported), not imputed.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis bland-altman --extra method_a=<method_a> --extra method_b=<method_b>
```
