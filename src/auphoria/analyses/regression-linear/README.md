# Simple Linear Regression

Fits a straight line that predicts one numeric **outcome** from one numeric
**predictor**, and reports the slope, intercept, correlation `r`, `R²`, the
significance of the slope, the standard error and a 95% confidence interval
for the slope.

Two figures are produced:

- a **scatter** of the outcome against the predictor with the best-fit line;
- a **residuals-vs-fitted** plot so you can judge whether a straight line is
  reasonable (points scattered evenly around zero with no obvious curve).

## When to use it

Use it when you have **two numeric columns** and want to know whether a change
in one predicts a change in the other, and how strong the straight-line
relationship is — for example hours studied vs exam score, or dose vs response.

## Inputs

| Role       | Kind             | Required | Description                          |
|------------|------------------|----------|--------------------------------------|
| `outcome`  | numeric-column   | yes      | The column you want to predict.      |
| `predictor`| numeric-column   | yes      | The single column used to predict.   |

## Parameter

| Name    | Type   | Default | Description                                             |
|---------|--------|---------|---------------------------------------------------------|
| `alpha` | number | 0.05    | Significance level for the slope CI and p-value verdict.|

## Outputs

- **Coefficients table** — slope, intercept, standard errors, p-value, and the
  `(1-alpha)`% confidence interval for each.
- **Fit statistics table** — `r`, `R²`, slope standard error, p-value,
  residual degrees of freedom, and sample size.
- **Scatter figure** with the best-fit line.
- **Residuals vs fitted figure**.
- **methods.txt** paragraph and **report.html**.

## Under the hood

The line is fit by ordinary least squares using `scipy.stats.linregress`
(a light, permissive dependency). The 95% (or `(1-alpha)`%) confidence
interval for each coefficient is `estimate ± t(n-2, 1-alpha/2) × SE`.

## Guardrails

- Both columns must exist and be numeric.
- At least **three complete** (outcome, predictor) pairs are required.
- A **constant** predictor (every value the same) is refused — the slope is
  undefined.
- Samples under **10 pairs** get a WARN verdict and flag for statistician
  review.
- Missing values are counted and excluded pairwise (with a warning), **never
  imputed**.

## What this result does NOT tell you

Linear regression does not prove causation. `R²` is not a prediction-accuracy
score and says nothing about how well the line predicts new, unseen data. The
fitted line is only meaningful inside the observed range of the predictor —
do not extrapolate it beyond the data.

## Dependencies

`requirements: []` — only the core permissive stack (numpy, pandas, scipy,
matplotlib) is used.