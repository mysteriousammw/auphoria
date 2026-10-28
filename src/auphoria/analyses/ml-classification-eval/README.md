# ML Classification Model Evaluation (`ml-classification-eval`)

Trains a **logistic-regression baseline** to predict a **binary categorical
label** from every other **numeric column**, and evaluates it **honestly**:
one part of the data is held out for testing, and the rest is used to train.
A **stratified cross-validation** run estimates how stable the accuracy is.

This is a **baseline**, not a tuned model — its job is to give you a number
to compare more complex approaches against.

## When to use it

- You have a categorical target with **two classes** (yes/no, disease/healthy,
  churn/not churn, survival/dead).
- You have several numeric measurements that might help predict the label
  (height, age, dosage, expression levels, ...).
- You want an honest, leakage-free estimate of how well a simple classifier
  separates the two classes.
- **Not** for more than two classes, and **not** as a substitute for a
  carefully tuned or cross-validated production model.

## Inputs

- **label** (required): the categorical target class to predict.
- **features**: every **other** numeric column is used automatically (you do
  not choose them — the analysis uses all of them).

## What you get

- **Confusion matrix** (predicted vs actual class counts).
- **Classification metrics** table: precision, recall, F1 and support per
  class, plus the weighted average and overall accuracy.
- **ROC curve** figure with the test-set ROC-AUC.
- **Cross-validation** scores table and figure (per-fold accuracy, with the
  mean and SD over the folds).
- A `methods.txt` paragraph you can paste into a paper.

## Choices (parameters)

- **test_size** (default `0.3`, range `0.1–0.5`): fraction of data held out
  for testing.
- **cv_folds** (default `5`, range `2–10`): number of cross-validation folds.
- **random_state** (default `1`): seed for a reproducible split and model.

## Assumptions (checked and reported, never silently ignored)

- The **label has exactly two classes**; a single-class column (or more than
  two classes) is refused, because a one-class column cannot be learned and
  ROC-AUC needs exactly two classes.
- **At least two numeric feature columns** are available.
- **Minimum sample size: at least 20 complete rows** after dropping rows with
  missing values (the analysis refuses below this). Below **30 rows**, or if
  a class has **fewer than 5 rows**, or if the label is strongly imbalanced,
  the result is flagged for **expert review**.
- **Class balance is reported**, so you can judge whether accuracy is a
  meaningful metric for your data.

## Limitations

- A good test-set ROC-AUC or accuracy does **not** prove the model
  generalises — it only describes the single held-out sample.
- **Leakage** (using test information while training, e.g. normalising on the
  full dataset before the split) invalidates every number; this run keeps
  train and test strictly separate.
- **Accuracy is misleading on imbalanced classes** — read precision, recall
  and ROC-AUC together.
- This is an **untuned baseline**, not a tuned model.
- **Missing values** are counted and their rows are dropped with a warning;
  values are **never imputed** (imputation leaks information), so your row
  count may shrink.

## Example

```bash
auphoria run --data my_data.csv --analysis ml-classification-eval --group label
```

> Maturity: **experimental** (not "validated").