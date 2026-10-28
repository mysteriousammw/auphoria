# ML Classification Model Evaluation

`ml-classification-eval` · maturity: **experimental**

Discipline packs: `econ-eng`  

Validation reference: Synthetic features; cross-checked vs scikit-learn (LogisticRegression, same split/seed)  


## What it does

Evaluates a cross-validated machine-learning classification baseline (logistic regression) against one categorical label column, using every other numeric column as automatic features. Reporting is honest about train/test separation: a held-out stratified test set scores accuracy, precision, recall, F1 and ROC-AUC, and stratified cross-validation adds an estimate of how stable the accuracy is across folds. This is a baseline, not a tuned model.

## What you need

- **label** (categorical-column, required): The target class you want to predict (e.g. diagnosis, outcome).

## Options

- `test_size` (default 0.3): Fraction of the data held out as the test set for honest evaluation.
- `cv_folds` (default 5): Number of folds for cross-validation.
- `random_state` (default 1): Seed for reproducible train/test split and model fitting.

## What you get out

- confusion matrix table (predicted vs actual class counts)
- classification metrics table (precision, recall, F1, support per class, accuracy)
- cross-validation scores table (per-fold accuracy, mean and SD)
- ROC curve figure (with the test-set ROC-AUC)
- cross-validation scores figure
- methods.txt paragraph
- report.html

## Assumptions

- The label column has exactly two classes (binary classification; ROC-AUC needs two classes). A single-class column is refused.
- At least two numeric feature columns are available (all other numeric columns are used automatically as features).
- A minimum of 20 rows is required to run; results from fewer than 30 rows, a class with fewer than 5 rows, or strongly imbalanced classes are flagged for expert review.
- Class balance is reported so you can see whether accuracy is a meaningful metric for your data.
- Missing values are counted and rows with missing values are dropped with a warning; values are never imputed (imputation would leak information).

## Limitations

- A good test-set ROC-AUC or accuracy does not prove the model generalises to new settings; it only reports how it performed on the single held-out sample. Cross-validation gives only a rough idea of stability.
- Leakage (using test information when training, e.g. scaling before the split or imputing on the full data) invalidates every number here; this run keeps train and test separate.
- Accuracy is misleading on imbalanced classes — read precision, recall and ROC-AUC together.
- This is a plain, untuned logistic-regression baseline, not a tuned model; it is for establishing a lower bound, not for final deployment.
- Missing values are dropped, not imputed, so rows shrink.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis ml-classification-eval --extra label=<label>
```
