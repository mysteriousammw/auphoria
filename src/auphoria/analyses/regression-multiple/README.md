# Multiple Linear Regression (`regression-multiple`)

**Multiple linear regression** explains a **numeric outcome using two or more
numeric predictors at once** — for example, predicting exam score from study
hours *and* attendance, or crop yield from rainfall *and* fertiliser. It is
fitted by **ordinary least squares** (statsmodels):

```
outcome ~ 1 + predictor1 + predictor2 + ...
```

Every numeric column besides the outcome is used automatically as a predictor
(text and categorical columns are ignored).

## When to use it

- Your outcome is a number (score, yield, price, time, concentration).
- You have **two or more numeric predictor columns** and want to know how they
  *jointly* relate to the outcome, after adjusting for one another.
- You want to see each predictor's partial effect (its coefficient holds every
  other predictor constant) and how much of the outcome they all explain
  together (R2).

## When NOT to use it

- **Only one numeric predictor** → use simple linear regression (this analysis
  refuses with that hint).
- **More rows needed than predictors**: if you have no more complete rows than
  predictor columns the coefficients cannot be estimated (refused).
- **Perfectly collinear predictors** (one is exactly a combination of the
  others) → refused, because the fit is singular.
- **Categorical predictors** → this is not the tool (ANCOVA / logistic or
  dummy-coding are better fits for grouped designs).

## What you get

- A **coefficients table**: per predictor, the beta coefficient, its standard
  error, the t statistic, the p-value, and a 95% confidence interval. This is
  the *partial* (adjusted) effect of each predictor.
- A **model table**: R2, adjusted R2, the overall model F test and its p-value,
  the sample size, and the residual degrees of freedom.
- A **VIF table**: the variance inflation factor for every predictor,
  hand-computed as `1 / (1 - R2_j)`, where `R2_j` comes from regressing that
  predictor on all the others. VIF above about 10 signals severe
  multicollinearity.
- A **predicted-vs-actual figure** on the fitted values.
- A `methods.txt` paragraph you can paste into a paper.

## Choices

- **alpha** (default `0.05`): significance level for the overall model F test.

## Assumptions

- The outcome is numeric and the relationship to each predictor is
  approximately linear, jointly.
- **Independent observations** (no repeated measures of the same subject).
- Residuals are roughly normal and of similar spread (homoscedasticity).
- **No severe multicollinearity** (checked by VIF). Above about VIF = 10 the
  individual coefficients are unstable.
- **Minimum sample size**: n > k (more complete rows than predictors) and at
  least two numeric predictors. A small sample (below about 30 rows) is flagged
  for expert review.

## How to read the output

1. **Model F and p**: `p < alpha` means the predictors, taken together, explain
   a significant share of the outcome's variance.
2. **R2**: the fraction of outcome variance the predictors jointly capture;
   adjusted R2 corrects this for the number of predictors.
3. **A predictor's beta and p**: the expected change in the outcome per
   one-unit increase in that predictor *while all the other predictors stay
   fixed*. Its p-value is for that partial effect.
4. **VIF**: keep an eye out — if any predictor's VIF is above about 10, that
   coefficient is unstable and should not be quoted as a clean effect even if
   the model as a whole fits well.

## Example

```bash
auphoria run --data my_data.csv --analysis regression-multiple --outcome price
```

> Maturity: **experimental** (not "validated"). This is an advanced analysis;
> when used with a small sample or with strong multicollinearity it flags a
> requirement for expert review.