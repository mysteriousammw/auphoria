# Binary Logistic Regression (`logistic-regression`)

Fits a **multiple binary logistic-regression model** (via statsmodels) that
predicts a **two-class outcome** from **every other numeric column** in the
data, and reports each predictor's effect as an **odds ratio** with its 95%
CI and p-value.

This is about *interpreting* which predictors are associated with a yes/no
outcome. It is **not** a tuned prediction model — use
`ml-classification-eval` if your goal is an honest held-out accuracy/ROC-AUC.

## When to use it

- You have a **binary outcome**: recovered/not, survived/died, disease/healthy,
  churn/not, passed/failed — either as text (yes/no) or as a numeric 0/1 column.
- You have one or more numeric measurements you suspect predict that outcome
  (age, dose, blood pressure, expression level, ...).
- You want to know **which predictors matter** and **how strong** each effect
  is (odds ratio), with uncertainty (CI) and a p-value.
- **Not** for more than two outcome classes, and **not** when your goal is a
  reliable prediction score on new data.

## Inputs

- **outcome** (required): the binary thing to predict.
- **predictor** (optional): every other numeric column is used automatically
  as a predictor; the optional predictor input is just a hint and can be left
  out.

## What you get

- **Coefficients (odds ratios)** table: for each predictor — beta, odds ratio,
  std error, z, p, and the 95% CI of the odds ratio (plus the intercept row).
- **Model fit** table: McFadden pseudo-R2, log-likelihood (full and
  intercept-only), likelihood-ratio chi2 and p, the number of complete rows
  used, and the outcome class counts.
- **Confusion matrix** and **accuracy** — explicitly labelled **in-sample**:
  they use the same rows the model was fitted on, so they are optimistic.
  Use `ml-classification-eval` for a proper held-out evaluation.
- **ROC curve** figure (scikit-learn) with the ROC-AUC.
- A `methods.txt` paragraph you can paste into a paper.

## Example

```bash
auphoria run --data my_data.csv --analysis logistic-regression --group outcome
```

## Assumptions (checked and reported, never silently ignored)

- The **outcome has exactly two classes**; a single class or three or more are
  refused (binary logistic regression needs two). A numeric 0/1 outcome column
  is accepted gracefully.
- **At least one numeric predictor column** is available; all of them are used.
- The usual (not auto-tested here) assumption that each continuous predictor is
  **linear in the log-odds**.
- **Events per variable** should be adequate — fewer than 10 cases in either
  class flags the result for **expert review**.
- **No perfect separation** or singular design matrix: those cannot be fitted
  by ordinary maximum-likelihood logistic regression and are refused with a
  plain message.
- **Missing values** are counted and the affected rows are **dropped with a
  warning**; values are **never imputed**.

## Limitations

- Odds ratios are **association, not causation** — unmeasured confounders can
  change the effect.
- The **in-sample accuracy and ROC-AUC are optimistic** (same rows as the fit);
  they do not predict performance on new data.
- This fits **one fixed predictor set**; it does not prove those are the best
  or only predictors.
- On **perfect separation** a penalised / Firth regression is needed.
- **Missing values** are dropped (rows shrink), not imputed.

> Maturity: **experimental** (not "validated").