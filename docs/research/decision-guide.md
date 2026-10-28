# Which analysis should I use? — a plain-language decision guide

This is the advisor's human-readable core. AUPHORIA asks a student a few
questions and walks a tree exactly like this one. Every branch ends in one of
the catalogue's analyses (ids shown in `code`). If the data do not fit the
test's assumptions, the guide sends the student to the non-parametric (or
otherwise appropriate) alternative — it never silently runs a wrong test.

Assumptions are "to check", not guarantees: AUPHORIA reports them and warns or
refuses when a chosen test clearly does not fit the data or design.

---

## Step 0 — Look first, always

Run `summary` (Descriptive Summary) before any other test. You want to see:
averages + spread for numeric columns, counts/percentages for categorical
columns, and how many values are missing. Also inspect for typos, impossible
values (negative height, age 250), and inconsistent units. A test on dirty
data is worse than no test.

---

## Step 1 — What is your research question?

| You want to know... | Question type | Jump to |
|---|---|---|
| What the data look like (no hypothesis) | Describe | `summary` (always run this first anyway) |
| Is there a *relationship* between variables? | Relationship | Step 2 |
| Do *groups differ* on something? | Comparison | Step 3 |
| Can I *predict* an outcome from inputs? | Prediction/modelling | Step 4 |
| How fast does an *event / failure* happen? | Time-to-event | Step 5 |
| Does a *scale/questionnaire* measure well? | Measurement/psychometrics | Step 6 |
| Can I *reduce / group* many variables? | Exploration/reduction | Step 7 |

---

## Step 2 — Relationship between variables

**What are your variables?**

- **Two numeric, same rows** → `correlation` (Pearson) if roughly linear and
  no big outliers; if non-normal or only monotonic → `spearman-correlation`.
  *Check:* scatterplot first; one outlier can dominate r.
- **One numeric outcome, one numeric predictor, want to predict** →
  `regression-linear` (simple linear regression).
- **One numeric outcome, several predictors** → `regression-multiple`
  (multiple linear regression, MS/PhD level).
- **Two categorical variables (counts)** → `chi-square` (test of
  independence). If any expected count < 5, use Fisher's exact.
- **Yes/no outcome, one predictor** → is it a study where you report how much
  more/less likely → `odds-and-risk` (RR/OR from a 2×2 table). If adjusting
  for several predictors → `logistic-regression`.

> Rule of thumb: if both variables are numbers and you ask "do they move
> together?" you almost always want `correlation` first; if you genuinely want
> to *predict* one from the other, `regression-linear/-multiple`.

---

## Step 3 — Comparing groups

**Three questions:**
1. How many groups/samples are you comparing? 2 or 3+?
2. Are the groups **independent** (different people/plants/etc.) or **paired /
   repeated** (the same units measured more than once, e.g. before/after)?
3. Is your outcome **numeric** (a measurement) or **categorical** (counts of
   yes/no, categories)?

| Outcome | #Groups | Independent? | Test (assumptions OK) | If not normal |
|---|---|---|---|---|
| numeric | 2 | independent | `ttest` (Welch by default) | `mann-whitney` |
| numeric | 2 | paired (before/after) | `ttest-paired` | Wilcoxon signed-rank (planned) |
| numeric | 3+ | independent | `anova-oneway` + Tukey post-hoc | `kruskal-wallis` |
| numeric | 3+ repeated (same units at several times) | within-subject | `anova-repeated` | `friedman` |
| numeric | groups + want to control a covariate | independent + covariate | `ancova` | mixed-effects / transform |
| categorical (counts) | any, independent | independent | `chi-square` (+ Fisher if small) | — (Fisher exact) |

**Checklist before the test (AUPHORIA will prompt you):**
- **t-test:** groups independent; outcome roughly normal in each group for
  small samples; Welch handles unequal variances.
- **ANOVA:** roughly normal within each group; variances roughly equal across
  groups (Levene's); after a significant F, run the post-hoc (Tukey) to see
  which groups differ — do not just run many t-tests.
- **Non-parametric (Mann-Whitney / Kruskal-Wallis / Friedman):** these do not
  need normality; use them when the parametric assumption fails or the data
  are ordinal.

---

## Step 4 — Prediction / modelling

- **Numeric outcome** → `regression-linear` (1 predictor) or
  `regression-multiple` (several). Check residuals, no strong
  multicollinearity (VIF), no extreme leverage.
- **Yes/no outcome** → `logistic-regression` (odds ratios, 95% CI).
- **You are building a *machine-learning* model with features and a label
  (CS/ML theses)** →
  - categorical label → `ml-classification-eval` (accuracy, precision/recall/
    F1, confusion matrix, ROC-AUC, cross-validated).
  - numeric target → `ml-regression-eval` (RMSE, MAE, R², cross-validated).
  - *Honesty guardrail:* never evaluate a model on data it was trained on; use
    a proper train/test split or cross-validation and watch for leakage.

---

## Step 5 — Time-to-event (health, reliability, survival)

Data have **a time until an event** + **an event/censored indicator**
(0 = never/not yet, 1 = event). If some observations drop out before the event
(censoring), do not just drop them or compute a plain mean.

- Describe survival, compare two/several groups → `kaplan-meier` (survival
  curves, median survival, log-rank test).
- Adjust for several covariates → `cox-regression` (hazard ratios, MS/PhD).

---

## Step 6 — Measurement / scales (psychometrics)

- Several item columns that should form one scale → `cronbach-alpha`
  (reliability). Also inspect item-total correlations.
- Do your items group into underlying dimensions? → `factor-analysis` (EFA)
  / use `pca` for pure data reduction.

---

## Step 7 — Reduce or group many variables

- Many numeric variables you want to compress into a few combined scores →
  `pca` (standardise first; check variance explained / scree).
- Group the *observations* into clusters → `clustering-kmeans` (scale
  variables; choose k with elbow/silhouette); hierarchical/DBSCAN for
  non-spherical clusters.

---

## The "clustered / nested / repeated" trap

If your rows are **not independent** — repeated measures of the same animal,
students nested in classrooms, plots nested in fields, multiple time points —
the simple tests in Step 3 are the wrong tools (they treat each row as an
independent observation, inflating false-positive rate). At MPhil/PhD level
the right answer is a `mixed-effects` model (random intercept per unit). AUPHORIA
warns when it detects a clear grouping/id column so the student isn't misled.

---

## Association ≠ causation

Every branch carries the same reminder: showing that two variables move
together (correlation, regression slope, chi-square association) does **not**
prove one causes the other. Only a properly randomised experiment supports a
causal claim, and even then framing matters. AUPHORIA writes this caveat into
the report's plain-English interpretation.

---

## Quick one-line map

```
Describe?            summary
2 numeric together?  correlation / spearman-correlation
Predict numeric?     regression-linear / regression-multiple
Predict yes/no?      logistic-regression
2 groups, normal?    ttest (independent) / ttest-paired (paired)
2 groups, not normal?mann-whitney (independent) / Wilcoxon (paired, planned)
3+ groups, normal?   anova-oneway (+ Tukey)
3+ groups, not normal?  kruskal-wallis
Counts / categories? chi-square (Fisher if small)
Event over time?     kaplan-meier / cox-regression
Scale reliability?   cronbach-alpha
Reduce variables?    pca
Group observations?  clustering-kmeans
Build an ML model?   ml-classification-eval / ml-regression-eval
Repeated/clustered?  anova-repeated / friedman / mixed-effects
```

> Sources informing this guide: the analysis menu of jamovi/JASP/SPSS/R
> (what students expect), textbook progressions (Rosner; Triola; Gravetter &
> Wallnau), and the PLoS/statistical-reporting evidence — see
> analysis-landscape.md and catalogue sources in catalog/analyses.yaml.