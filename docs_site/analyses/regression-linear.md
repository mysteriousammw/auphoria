# Simple Linear Regression

`regression-linear` · maturity: **experimental**

Discipline packs: `core`, `econ-eng`  

Validation reference: Hand-computed regression on x=[1..5], y=[2,4,5,4,5] (Sxx=10, Sxy=6, slope=0.6, intercept=2.2, r=0.7746, R2=0.6); cross-checked vs scipy.stats.linregress  


## What it does

Fits a straight line that predicts one numeric outcome from one numeric predictor, and reports the slope, intercept, correlation r, R2, the significance of the slope, the standard error and a 95% confidence interval for the slope. Also draws a scatter with the best-fit line and a residual plot so you can judge whether a straight line is reasonable.

## What you need

- **outcome** (numeric-column, required): The numeric outcome column you want to predict (e.g. exam_score).
- **predictor** (numeric-column, required): The single numeric predictor column (e.g. hours_studied).

## Options

- `alpha` (default 0.05): Significance level for the slope's confidence interval and p-value verdict.

## What you get out

- coefficients table (slope, intercept, standard error, p-value, 95% CI)
- fit statistics table (r, R2, p-value, sample size)
- scatter figure with the best-fit line
- residual figure (residuals vs fitted values)
- methods.txt paragraph
- report.html

## Assumptions

- Both columns are numeric and measured on the same set of observations.
- The relationship between the two variables is roughly straight-line (linear); a strongly curved relationship makes the fitted slope misleading.
- The residuals are roughly symmetric and the spread does not change strongly with the predicted value (homoscedasticity).
- Minimum sample size: at least three complete (outcome, predictor) pairs are required to fit the line at all.

## Limitations

- The slope describes association in this sample, not a guaranteed effect.
- R2 is not a prediction-accuracy score and says nothing about how well the line predicts new, unseen data.
- Do not extrapolate: the fitted line is only meaningful inside the range of the predictor you observed.
- One unusual (outlier/high-leverage) point can tilt the slope a lot.
- Missing values in the two columns are excluded pairwise (and reported), never imputed.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis regression-linear --outcome <outcome> --extra predictor=<predictor>
```
