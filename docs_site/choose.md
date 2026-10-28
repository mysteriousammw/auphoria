# Which analysis should I use?

AUPHORIA can answer this for you. When you run the guided form it asks one
question — **"What do you want to know?"** — and recommends the analyses that
fit both your question and your data. The same decision guide is explained
below in plain language, so you understand the *why*, not just the answer.

## Step 0 — Look first, always

Run `summary` before anything else. You want averages and spread for numeric
columns, counts for categories, and how many values are missing. You also want
to spot typos and impossible values (a negative height, an age of 250). A test
on dirty data is worse than no test.

## Step 1 — What is your question?

| You want to know... | Question type | Start here |
|---|---|---|
| What do the data look like (no hypothesis)? | Describe | `summary`, `describe` |
| Do **groups differ** on something? | Comparison | Step 3 |
| Do variables **move together**? | Relationship | Step 2 |
| Can I **predict** an outcome? | Prediction | Step 4 |

The on-screen questions map to these; pick the one that matches, and AUPHORIA
suggests the right analyses for your column types.

## Step 2 — Relationship between variables

- **Two numeric columns, same rows** → `correlation` (Pearson). If the
  relationship is non-linear or the data aren't normal, use
  `spearman-correlation`.
- **Two categorical columns (counts)** → `chi-square` (independence).
- **A numeric outcome + features** you want to use for prediction →
  `ml-regression-eval`; a **categorical outcome** → `ml-classification-eval`
  or `diagnostic-test`.

## Step 3 — Comparing groups

Ask yourself: **how many groups**, are they **independent** (different
subjects/plants) or **paired/repeated** (same units measured twice), and is
your outcome **numeric** (a measurement) or **categorical** (counts)?

| Outcome | #Groups | Design | Analysis |
|---|---|---|---|
| numeric | 2 | independent | `ttest` (or `mann-whitney` if not normal) |
| numeric | 2 | paired (before/after) | `ttest-paired` |
| numeric | 3+ | independent | `anova-oneway` (+ Tukey post-hoc) |
| numeric | any | comparing groups while adjusting for a covariate | `ancova` |
| numeric | any | repeated measures on the same units | `mixed-effects` |
| categorical (counts) | any | independent | `chi-square` |
| time-to-event | any | survival | `kaplan-meier`, `cox-regression` |

AUPHORIA checks assumptions for you (normality, equal variances, expected
counts) and **warns or refuses** when a test clearly doesn't fit — it never
silently runs a wrong test.

## Step 4 — Predicting an outcome

- **Numeric target** → `ml-regression-eval` (RMSE, MAE, R², cross-validated).
- **Categorical label** → `ml-classification-eval` (accuracy, precision,
  recall, F1, ROC-AUC).
- **Binary "test result vs truth"** → `diagnostic-test` (sensitivity,
  specificity, PPV/NPV, ROC).

These are **honest** baselines: they report performance on data the model did
not train on. A good number does **not** prove your model generalises — read
that caveat on the report.

## Step 5 — Reducing many variables

- Lots of numeric columns you want to compress → `pca`.
- Correlated questionnaire items hiding a latent dimension → `factor-analysis`.
- Group the rows into clusters → `clustering-kmeans`.

## Trust but verify

Every analysis page lists its assumptions, limitations, and any known issues.
A significant p-value does **not** mean a real effect caused the difference; a
good R² does **not** mean a correct model. The report always includes a
**"What this result does not tell you"** box for exactly this reason. Advanced
analyses add a **"Needs expert review"** notice when they are run outside their
intended conditions — take that seriously and talk to your supervisor.

See the full [decision guide](research/decision-guide.md) and browse
every analysis in the [Analyses](analyses/index.md) section.