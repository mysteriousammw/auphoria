# ML Regression Model Evaluation

`ml-regression-eval` · maturity: **experimental**

Discipline packs: `econ-eng`  

Validation reference: Synthetic features; cross-checked vs scikit-learn LinearRegression (same split/seed)  


## What it does

Evaluates a cross-validated machine-learning regression baseline (linear regression) on a continuous target. Trains on one part of the data and scores a held-out test set, reporting RMSE, MAE and R2, plus 5-fold cross-validation RMSE (mean and spread) so you see how stable the model is. Honest train/test separation means the numbers reflect how the model generalises to data it has not seen, not how well it memorises the training set.

## What you need

- **target** (numeric-column, required): The continuous outcome you want to predict (e.g. price_usd).

## Options

- `test_size` (default 0.3): Fraction of rows held out for the final, honest evaluation.
- `cv_folds` (default 5): Number of folds for the cross-validation of the same baseline.
- `random_state` (default 1): Seed for reproducible train/test split and cross-validation.

## What you get out

- test-set metrics table (RMSE, MAE, R2)
- 5-fold cross-validation RMSE table (per-fold and mean +/- SD)
- predicted-vs-actual scatter figure
- per-fold CV scores figure
- methods.txt paragraph
- report.html

## Assumptions

- The target is a continuous numeric outcome; every other numeric column is used automatically as a feature (text and categorical columns are ignored).
- The relationship the linear model is asked to learn is roughly linear; RMSE, MAE and R2 on a linear baseline only make sense if a linear fit is a reasonable starting point.
- Rows are independent (a linear regression baseline assumes independent observations; repeated measures of the same subject would violate this).
- No future or overlapping information is used as a feature (no leakage); the features must be known before you would predict the target.
- The units of the target matter: RMSE and MAE are on the target's own scale, so a small error for tiny-valued targets is not the same as a small error for large-valued targets.
- Minimum sample size: at least 20 complete rows are required, and at least one numeric feature column (besides the target) is required.

## Limitations

- R2 is often misread as 'goodness of fit'; without inspecting residuals it only says how much of the target's variance the linear model captures on a specific test set.
- A good test-set R2 does not prove the model generalises to new data, populations, or time periods beyond this sample.
- This is a linear baseline, not a tuned or flexible model; it cannot capture non-linear effects or interactions unless you engineer them as features.
- Missing values in the used columns are counted and dropped (listwise), never imputed.
- Report a small sample or a very small test set to a statistician before treating the numbers as trustworthy.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis ml-regression-eval --extra target=<target>
```
