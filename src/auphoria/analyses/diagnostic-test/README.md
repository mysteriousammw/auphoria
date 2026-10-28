# Diagnostic Test Performance (`diagnostic-test`)

Evaluates how well a **numeric test score** separates two groups defined by a
**binary reference standard** (the gold-standard truth, e.g. diseased vs
healthy). You get the classic accuracy figures — **sensitivity,
specificity**, **predictive values**, the **confusion matrix**, and a full
**ROC curve with AUC** — at a cutoff chosen for you.

## When to use it

- You have a numeric test/score with higher values meaning "more likely to be
  the positive state".
- You have a **binary reference standard** (true diseased vs not, present vs
  absent, case vs control) that you trust as the ground truth.
- You want sensitivity, specificity, predictive values, and an overall
  discrimination summary (AUC).
- Example: serum biomarker vs biopsy-confirmed disease; screening score vs a
  reference diagnosis.

## What you get

- **Confusion matrix** (true vs predicted) at the chosen cutoff.
- **Performance table**: sensitivity, specificity, PPV, NPV, disease
  prevalence, the chosen threshold, and the **AUC with a bootstrap 95% CI**.
- **ROC curve** figure (with the chance line).
- Which category was treated as the *positive* (disease) class.
- A `methods.txt` paragraph you can paste into a paper.

## Choices

- **alpha** (default `0.05`): significance level used when flagging
  concerning results and uncertainty.
- **threshold**: *optional*. A fixed cutoff — a score **>= threshold** is
  called positive. Omit it and the cutoff is chosen automatically by
  **Youden's J** (the threshold maximising sensitivity + specificity − 1).

## How the positive class is chosen

The reference must have **exactly two categories**. The "positive" (disease)
class is chosen as: (1) a label that literally says so (`positive`, `disease`,
`yes`, `case`, `1`, …); otherwise (2) the **rarer** class (disease is usually
the less common state); ties break deterministically. The mapping is logged
and shown in the output so you can see and override expectations.

## Assumptions (checked and reported, never silently ignored)

- The **reference standard is valid** — an independent, trusted gold standard.
- The sample is **independent** (one row per subject).
- **Higher score = higher probability of disease** (the ROC orientation).
- The reference has **exactly two categories**; both classes are present.
- Minimum sample size: at least **20 complete rows total** (ideally **≥ 5 in
  each class**). Smaller or badly imbalanced samples still run but are
  flagged for **expert review** as unreliable.
- Prevalence is reported so you can interpret PPV/NPV in context.
- Missing values are **counted and excluded with a warning, never imputed**.

## When NOT to use it

- Your reference has **more than two categories** → the tool refuses (use
  multi-class classification instead).
- You only want a correlation / linear relation, not a test accuracy.
- Your reference standard is itself unreliable — the whole result is only as
  good as the gold standard.

## How to read the output

1. **Check the reference mapping** first: make sure the chosen *positive*
   class really is the disease state in your data.
2. **Sensitivity / specificity** are at the *chosen threshold* — change the
   threshold and they change. A cutoff tuned by Youden's J balances them but
   "optimised" does not mean "clinically best".
3. **PPV / NPV depend on prevalence.** The same test in a population with a
   different prevalence gives different predictive values.
4. **AUC** summarises the whole ROC curve. A high AUC does *not* mean every
   patient near the threshold is correctly classified.

> Maturity: **experimental** (not "validated").

## Example command

```bash
auphoria run \
  --data results.csv \
  --analysis diagnostic-test \
  --outcome biomarker \
  --extra reference=true_status
```

(`--outcome` holds the numeric test score; the reference-standard column is
passed as the `reference` extra.)