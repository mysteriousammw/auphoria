# Gallery — example reports

Every analysis ships with a **self-contained demo** you can run on bundled
synthetic data — no file of your own needed. Run one and then open its
`report.html` in a browser to see exactly what AUPHORIA produces.

```bash
auphoria demo --analysis ttest
```

Then open the newest folder under `~/AUPHORIA_results/` and view
`report.html`.

## Quick tour — run these, in order

| # | Analysis | What the report shows |
|---|---|---|
| 1 | `auphoria demo --analysis summary` | Averages, spread, missing-value counts |
| 2 | `auphoria demo --analysis ttest` | t, df, p, Cohen's d, boxplot |
| 3 | `auphoria demo --analysis correlation` | r, p, scatterplot |
| 4 | `auphoria demo --analysis anova-oneway` | ANOVA table, F, p, Tukey post-hoc |
| 5 | `auphoria demo --analysis kaplan-meier` | Survival curves + log-rank, at-risk table |
| 6 | `auphoria demo --analysis diagnostic-test` | Sensitivity/specificity, ROC curve, AUC |
| 7 | `auphoria demo --analysis ml-classification-eval` | Confusion matrix, precision/recall/F1, ROC-AUC |
| 8 | `auphoria demo --analysis pca` | Variance-explained, loadings, score scatter |

## What every report contains

All reports follow the same template, so once you've seen one you know where
to look:

- **Summary cards** — the headline numbers at a glance.
- **Quality checks (verdicts)** — PASS / WARN / FAIL for the assumptions checked.
- **What this result does *not* tell you** — the honest caveat, in plain words.
- **Methods** — paste-ready sentences describing exactly what was done.
- **Results tables** — every number, also saved as CSVs.
- **Figures** — every plot, also saved as PNGs.
- **Assumptions & limitations** — from the analysis's manifest.
- **Decision log** — every warning and assumption check, with the reason.
- **Reproducibility** — the exact command + random seed to re-run and confirm.

## A real run, end to end

```bash
# Pull down a fresh repo of demo results into one place
mkdir -p ~/demo_reports && cd ~/demo_reports
auphoria demo --analysis anova-oneway
auphoria demo --analysis mixed-effects
auphoria demo --analysis cox-regression
open ~/AUPHORIA_results   # macOS: open the folder of reports
```

## Note about the demos' data

The demo datasets are **small, synthetic, and chosen so the analysis is
clear-cut** (treatments obviously differ, survival curves clearly separate,
etc.). They are for learning the interface, **not** a claim about real data.
Your own data will usually be messier — which is exactly what the data-quality
checks and the "what this does NOT tell you" boxes are for.

## Reproducing a report exactly

Open any results folder and run its `replay.sh` (or `replay.ps1` on Windows)
to reproduce the exact run — the same numbers, figures, and report, in a fresh
folder.