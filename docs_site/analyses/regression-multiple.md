# Multiple Linear Regression

`regression-multiple` · maturity: **experimental**

Discipline packs: `econ-eng`, `social`  

Validation reference: Synthetic y = 1 + 2*x1 - 1*x2 + e; cross-checked vs statsmodels.api.OLS
  


## What it does

Fits a multiple linear regression of a numeric outcome on two or more numeric predictors using ordinary least squares (statsmodels). Every numeric column besides the outcome is used automatically as a predictor, so the model asks how the predictors jointly relate to the outcome after adjusting for one another. It reports a coefficient table (beta, standard error, t, p and 95% confidence interval per predictor), an overall model table (R2, adjusted R2, the model F test and its p, sample size and residual degrees of freedom), a VIF table that flags multicollinearity, and a predicted-vs-actual figure.

## What you need

- **outcome** (numeric-column, required): The numeric outcome you want to explain or predict.
- **predictor** (numeric-column, optional): Optional numeric predictor. When omitted, every other numeric column in the data is used as a predictor automatically.


## Options

- `alpha` (default 0.05): Significance level you accept for a false positive in the model F test.

## What you get out

- coefficients table (predictor, beta, std err, t, p, 95% confidence interval)
- model table (R2, adjusted R2, F, p, sample size, residual df)
- VIF table (multicollinearity check, one row per predictor)
- predicted-vs-actual scatter figure
- methods.txt paragraph
- report.html

## Assumptions

- The outcome is numeric and the relationship between the outcome and each predictor is approximately linear, jointly (all predictors at once).
- Observations are independent (no repeated measures of the same subject).
- The residuals are approximately normally distributed and of roughly equal spread across the fitted values (homoscedasticity).
- The predictors are not too strongly correlated with each other (checked with the variance inflation factor, VIF); VIF above about 10 signals severe multicollinearity that makes individual coefficients unstable.
- Minimum sample size: there must be more complete rows than predictors (n > k), and at least two numeric predictors.

## Limitations

- A significant coefficient does not prove that predictor causes the outcome; the model only adjusts for the other predictors that are in the data.
- Coefficients are sensitive to collinear predictors: with multicollinearity individual betas can flip sign or look non-significant even when the model fits well.
- The model does not extrapolate sensibly beyond the observed range of the predictors.
- Missing values in the used columns are counted and dropped (listwise), never imputed.
- With very many predictors relative to rows the model can overfit and R2 is optimistic; adjusted R2 partly corrects for this.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis regression-multiple --outcome <outcome>
```
