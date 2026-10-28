# Known issues

Outstanding known problems and limitations, grouped per analysis under a
`## <analysis-id>` heading. The validation dashboard
(`scripts/gen_validation_dashboard.py`) reads this file and shows each
analysis's issues. Anything under `## _` is general and not tied to one
analysis.

To report a NEW issue, open one based on
`.github/ISSUE_TEMPLATE/wrong_result.md`.

---

## _

- R is not a runtime dependency, so analyses are cross-checked against
  scikit-learn/statsmodels (second-library reproduction) and hand-computed
  textbook examples rather than an R call. This is recorded per analysis in
  `docs/validation/references.yaml`.
- `maturity: experimental` / `tested` are set by the build agent;
  `reviewed` and `validated` are reserved for a named human reviewer (the
  reviewer gate is enforced at load time and by the dashboard generator).

## clustering-kmeans

- Clusters are descriptive groupings, not proof that "real" groups exist;
  results depend on the chosen `k` and on scaling. A weak silhouette score is
  flagged for expert review, but a "good" score is not proof of a true
  structure.
- k-means assumes roughly spherical, equal-sized clusters; elongated or
  non-spherical data need hierarchical/DBSCAN (recorded in the manifest).

## kaplan-meier

- Censoring must be non-informative; a high censoring fraction is flagged but
  the log-rank test's power is still reduced. Small samples with few events
  produce wide, unstable curves.

## ml-classification-eval / ml-regression-eval

- These are linear baselines, not tuned models. A good test metric does not
  prove generalisation, and leakage (normalising before the split) invalidates
  the result. Small/imbalanced data are flagged for expert review.

## factor-analysis

- Needs an adequate sample (rule of thumb ~5-10 per item, 100+ preferred); low
  KMO is flagged. Factor names are the analyst's interpretation, not part of
  the output.

## mixed-effects

- Random-intercept-only; a random slope or cross-classified structure would
  need an extended model. Few clusters or severe imbalance make variance
  components unstable (flagged).

## diagnostic-test

- Sensitivity/specificity depend on the chosen threshold and on prevalence;
  AUC is not a per-patient probability. Only as good as the reference standard.

## cox-regression

- Requires the proportional-hazards assumption (Schoenfeld check reported).
  Hazard ratios are relative, not absolute risk.

## ancova

- Interpreting the covariate as causal is wrong unless it was measured
  pre-treatment; homogeneity-of-slopes must hold (checked and flagged).

## pca

- PCA is not factor analysis and does not imply latent causes; components are
  linear combinations of the observed variables and may not generalise.