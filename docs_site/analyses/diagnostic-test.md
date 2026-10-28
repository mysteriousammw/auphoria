# Diagnostic Test Performance

`diagnostic-test` · maturity: **experimental**

Discipline packs: `health`  

Validation reference: Tiny 10-row set (scores 1-10 vs binary reference); cross-checked vs sklearn.metrics  


## What it does

Evaluates how well a numeric diagnostic test score separates two groups defined by a binary reference standard (e.g. diseased vs not). Reports sensitivity, specificity, positive/negative predictive value, prevalence, a confusion matrix at an optimised threshold (Youden's J), and full ROC curve with the area under the curve (AUC).

## What you need

- **test** (numeric-column, required): The numeric test score; higher values are taken to indicate disease.
- **reference** (categorical-column, required): The true/reference status used as the gold standard (e.g. disease yes/no).

## Options

- `threshold` (default None): Optional fixed cutoff for the score (score >= threshold is called positive). If omitted, Youden's J is used to pick the cutoff.

## What you get out

- confusion matrix table (true vs predicted at the chosen threshold)
- performance table (sensitivity, specificity, PPV, NPV, prevalence, AUC, chosen threshold)
- ROC curve figure with AUC
- methods.txt paragraph
- report.html

## Assumptions

- The reference standard is valid (an independent, trusted gold standard).
- The sample is independent (one row per subject, no repeated measures).
- A higher test score indicates a higher probability of disease.
- The reference column has exactly two categories, both with at least one non-missing row after listwise exclusion.
- Minimum sample size: at least 20 complete rows total (with at least 5 in each class) for a result that does not need a statistician's review; smaller samples still run but are flagged for expert review.
- Prevalence is reported so you can interpret PPV/NPV in context.

## Limitations

- Sensitivity/specificity depend on the chosen threshold and on the prevalence of disease in the sample; they are not fixed properties of the test.
- AUC is an overall summary, not a per-patient probability, and is insensitive to intermediate-performance classifiers that operate in a small region of the ROC curve.
- PPV/NPV depend heavily on prevalence and do not transfer to a different population with a different prevalence.
- The whole result is only as good as the reference standard — a faulty gold standard produces misleading accuracy figures.
- Missing values in the two chosen columns are excluded (and reported), not imputed.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis diagnostic-test --extra test=<test> --extra reference=<reference>
```
