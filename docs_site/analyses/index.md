# Analyses

Every analysis AUPHORIA ships, each with a plain-English page: what it does,
what you need, the options, assumptions, limitations, and how to run it.

Run `auphoria list` to see them, and `auphoria demo --analysis <id>` to run a
working example on bundled synthetic data.

## Basic & descriptive

- [**Summary**](summary.md) — `summary` — averages, spread, counts, missing values.
- [**Describe My Data**](describe.md) — `describe` — full data-quality review.

## Comparing groups

- [**Independent-Samples t-Test**](ttest.md) — `ttest` — 2 independent groups.
- [**Paired-Samples t-Test**](ttest-paired.md) — `ttest-paired` — before/after.
- [**Mann-Whitney U Test**](mann-whitney.md) — `mann-whitney` — 2 groups, not normal.
- [**Chi-Square Test**](chi-square.md) — `chi-square` — two categorical columns.
- [**One-Way ANOVA**](anova-oneway.md) — `anova-oneway` — 3+ independent groups.
- [**ANCOVA**](ancova.md) — `ancova` — a group comparison adjusting for a covariate.
- [**Linear Mixed-Effects Model**](mixed-effects.md) — `mixed-effects` — clustered/repeated.

## Relationships

- [**Pearson Correlation**](correlation.md) — `correlation`.
- [**Spearman Rank Correlation**](spearman-correlation.md) — `spearman-correlation`.

## Survival

- [**Kaplan-Meier Survival Analysis**](kaplan-meier.md) — `kaplan-meier`.
- [**Cox Proportional-Hazards Regression**](cox-regression.md) — `cox-regression`.

## Prediction & diagnostics

- [**Diagnostic Test Performance**](diagnostic-test.md) — `diagnostic-test`.
- [**ML Classification Evaluation**](ml-classification-eval.md) — `ml-classification-eval`.
- [**ML Regression Evaluation**](ml-regression-eval.md) — `ml-regression-eval`.

## Data reduction

- [**Principal Component Analysis**](pca.md) — `pca`.
- [**Exploratory Factor Analysis**](factor-analysis.md) — `factor-analysis`.
- [**K-Means Clustering**](clustering-kmeans.md) — `clustering-kmeans`.