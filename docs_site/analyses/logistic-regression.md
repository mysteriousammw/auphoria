# Binary Logistic Regression

`logistic-regression` · maturity: **experimental**

Discipline packs: `health`, `social`, `econ-eng`, `bioinformatics`  

Validation reference: Synthetic data from logit(p) = -1 + 1.5*x1 - 0.8*x2 + noise; coefficients and the likelihood-ratio p cross-checked against statsmodels Logit (same fit).  


## What it does

Fits a multiple binary logistic-regression model (statsmodels Logit) that predicts a two-class outcome from every other numeric column in the data. The report gives an odds ratio with its 95% CI and p-value for each predictor, a model-fit table (McFadden pseudo-R2, log-likelihood, LR chi2 and p, class counts), an in-sample confusion matrix and accuracy (clearly labelled as in-sample, so it does not overstate performance), and a ROC curve. A numeric binary 0/1 outcome column is accepted gracefully.

## What you need

- **outcome** (categorical-column, required): The two-class thing you want to predict (e.g. recovered = yes/no, or a numeric 0/1 column).
- **predictor** (numeric-column, optional): Optional hint; if omitted every other numeric column is used automatically as a predictor.

## What you get out

- coefficient table (predictor, beta, odds ratio with 95% CI, std error, z, p)
- model fit table (McFadden pseudo-R2, log-likelihood, LR chi2 + p, n, class counts)
- in-sample confusion matrix and accuracy (clearly labelled in-sample)
- ROC curve figure (scikit-learn ROC-AUC)
- methods.txt paragraph
- report.html

## Assumptions

- The outcome has exactly two classes; a single class (or three or more) is refused.
- At least one numeric predictor column exists; every other numeric column is used automatically as a predictor.
- The relationship between each continuous predictor and the log-odds is linear (a standard logistic-regression assumption, not automatically tested here).
- Events per variable should be adequate; fewer than 10 cases in either class flags the result for expert review.
- No perfect separation or singular design matrix (those cannot be fitted with ordinary maximum-likelihood logistic regression and are refused).
- Missing values are counted and rows with missing values are dropped with a warning; values are never imputed.

## Limitations

- Odds ratios describe association, not causation; unmeasured confounders can change the effect.
- The confusion matrix and accuracy use the FITTED (in-sample) rows, so they are optimistic — use ml-classification-eval for an honest held-out evaluation.
- This fits one fixed predictor set; it does not prove the predictors are the best or only ones.
- Standard logistic regression fails on perfect separation; a penalised / Firth approach is needed there.
- Missing values are dropped, not imputed, so rows shrink.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis logistic-regression --outcome <outcome>
```
