# ML Regression Model Evaluation (`ml-regression-eval`)

Fits a **linear regression baseline** to predict a **continuous target** and
scores it **honestly** — on data the model has never seen. You pick the target
column; every **other numeric column** becomes a feature automatically (text
and categorical columns are ignored). The rows are split into a **training set**
(used to fit the model) and a **held-out test set** (scored after fitting), so
the reported RMSE, MAE and R2 are a test of generalisation, not of memorising
the training data. The same baseline is also re-run in **5-fold
cross-validation** so you can see how stable it is.

## When to use it

- You have a **continuous outcome** you want to predict from several numeric
  inputs (price, score, concentration, ...).
- You want an **honest** estimate of how well a simple model predicts new data,
  rather than a "did it fit the training points" number.
- You want a fast **baseline** before reaching for fancier models (trees,
  forests, neural nets).

## What you get

- A **Test-set metrics** table: RMSE, MAE and R2 on the held-out test set.
- A **Cross-validation RMSE** table (per fold) and a summary (mean ± SD of CV
  RMSE) showing how stable the baseline is.
- A **predicted-vs-actual** scatter figure — points should hug the diagonal.
- A **per-fold CV RMSE** bar figure.
- A `methods.txt` paragraph.

## Choices

- **test_size** (default `0.3`): fraction of rows held out for the final,
  honest evaluation.
- **cv_folds** (default `5`): number of folds for cross-validation.
- **random_state** (default `1`): seed so the same data gives the same split.

## Example

```bash
auphoria run --data my_data.csv --analysis ml-regression-eval --outcome price_usd
```

## Assumptions and minimum sample size

- **Minimum sample size: at least 20 complete rows**, and at least **one
  numeric feature column** besides the target. With fewer than 30 rows the
  results are flagged for statistician review.
- The target and features must be **known before prediction** (no leakage); a
  feature that carries the answer leaks it and inflates R2.
- The relationship is roughly **linear** — this is a linear baseline.
- Rows are **independent** observations.
- **The target's units matter**: RMSE/MAE are on the target's own scale.
- Missing values in the used columns are **counted and dropped** with a
  warning — never imputed.

## When NOT to use it / limitations

- **R2 is not "goodness of fit"** on its own — without checking residuals a
  high R2 can hide bias or outliers.
- A good test R2 does **not** prove the model generalises to new data,
  populations or time periods.
- This is a **linear baseline, not a tuned or flexible model**; it cannot
  capture non-linearities or interactions unless you build them as features.
- If the target is categorical, you want a classification analysis instead.

> Maturity: **experimental** (not "validated"). Advanced analysis — report
> small samples or violated assumptions to a statistician.