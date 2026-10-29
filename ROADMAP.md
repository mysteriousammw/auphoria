# AUPHORIA — Build Roadmap

The single source of truth for what AUPHORIA advertises versus what is built.
This file reconciles three things that currently disagree:

- `catalog/analyses.yaml` — the **planned** analysis list (32 entries, P1/P2/P3).
- `src/auphoria/analyses/` — the **built** analysis modules (19 shipped).
- `docs/DISCIPLINE_PACKS.md` + README — the **advertised** pack contents.

**Golden rule:** do not advertise an analysis that is not built. Any row below
that ships is moved to the "Shipped" section and its pack/catalogue/docs entry
updated the same day.

---

## Current state (2026-10-30)

| Source | Count | Notes |
|--------|-------|-------|
| Catalogue (planned) | 32 | P1×19, P2×9, P3×4 |
| Built (shipped) | 26 | every one `maturity: experimental` |
| Planned but unbuilt | 6 | see Wave 3 |
| Pack-page analyses (unbuilt) | ~24 | see Wave 3 |
| Cross-field gaps not in catalogue | 3+ | see Wave 4 |

## Shipped (built; do not rebuild)

summary, describe, ttest, ttest-paired, correlation, spearman-correlation,
chi-square, anova-oneway, mann-whitney, kaplan-meier, cox-regression, pca,
ml-classification-eval, ml-regression-eval, clustering-kmeans, ancova,
mixed-effects, factor-analysis, diagnostic-test, anova-repeated, friedman,
bland-altman, panel-regression, time-series, differential-expression, sem.

---

## Wave 1 — finish the P1 plan (highest priority; universal demand)

Every one of these is on the P1 "ship-first" list and is either `core` or
cross-field. Until these ship, AUPHORIA is not yet what it advertises.

| # | Analysis | Packs | Notes |
|---|----------|-------|-------|
| 1 | `kruskal-wallis` | core, social, health | Non-parametric ANOVA; the paired trainer for anova-oneway normality-refusal. |
| 2 | `regression-linear` | core, econ-eng | Simple linear regression: fit, R², slope/intercept CI, resid plots. |
| 3 | `regression-multiple` | core, econ-eng, social | Multiple linear regression incl. categorical predictors, VIF collinearity. |
| 4 | `logistic-regression` | health, social, econ-eng, bioinformatics | Binary logistic; OR, CI, Pseudo-R², Hosmer-Lemeshow, ROC. |
| 5 | `odds-and-risk` | health, agri-animal | 2×2 RR/OR, CI, chi-square/Fisher. Melts into logistic-regression later. |
| 6 | `cronbach-alpha` | social, health | Scale reliability; the psychology/education survey staple. |

**Exit gate for Wave 1:** all six `auphoria demo --analysis <id>` run end to
end; every analysis has reference fixtures in `docs/validation/references.yaml`;
catalogue + advisor `rules.yaml` + docs_site page all updated. P1 coverage =
19 of 19.

---

## Wave 2 — complete the P2/P3 named plans

| # | Analysis | Priority | Packs | Notes |
|---|----------|----------|-------|-------|
| 7 | `anova-repeated` | P2 | social, health, life-science | Repeated-measures ANOVA (statsmodels AnovaRM). |
| 8 | `friedman` | P2 | social, health | Non-parametric repeated measures. Pairs with #7. |
| 9 | `bland-altman` | P2 | health, life-science | Method-agreement limits. |
| 10 | `panel-regression` | P3 | econ-eng, social | Fixed-effects panel / longitudinal (statsmodels). |
| 11 | `time-series` | P3 | econ-eng, life-science | Decomposition & trend (statsmodels). |
| 12 | `differential-expression` | P3 | bioinformatics | RNA-seq count DE (PyDESeq2) — **the supervisor's ask**. Needs count matrix input; heavy. |
| 13 | `sem` | P3 | social | Structural equation basics (CFA + path). Heavy; ship with explicit assumptions. |

---

## Wave 3 — stop the discipline-pack over-promise

`docs/DISCIPLINE_PACKS.md` + README currently advertise these as pack
contents, but they have **no module, no catalogue entry, no tests**. Pick per
pack in demand order. Each must first be added to the catalogue with a
priority, then built.

**agri-animal** (highest demand for agricultural MS students):
- CRD, RCBD, Latin square, split-plot, factorial designs (ANOVA with blocking —
  one "experimental-design" family, may build as one module with a `design`
  parameter)
- Mean separation: Tukey, LSD, Duncan (Tukey HSD already exists inside anova-oneway)
- Heritability & variance components, growth curves, feed-trial designs

**life-science:**
- dose-response (IC50/EC50 fit), qPCR relative quantification (ΔΔCt),
  enzyme kinetics (Lineweaver–Burk/Michaelis–Menten) — strong biotech demand

**health:**
- meta-analysis (2×2 pooling; RR/OR machinery already exists)

**social:**
- Inter-rater agreement (Cohen's kappa — Wave 4 #16 too), Likert scale handling,
  confirmatory factor analysis (extends factor-analysis)

**econ-eng:**
- robust errors (bootstrap/HC), instrumental variables, curve fitting,
  error propagation

**Design note:** several are one engine with a switch (the ANOVA-design family),
so they share manifest/README/tests scaffolding. Do not create a stub for each;
build the family as one analysis and expand when demand justifies.

---

## Wave 4 — cross-field analyses NOT in the catalogue (new findings)

These are not in `catalog/analyses.yaml` today but are (a) recommended by the
tool's own outputs as fallbacks, or (b) named standard methods for fields the
packs promise. Add each to the catalogue, then build.

| # | Analysis | Backing | Notes |
|---|----------|---------|-------|
| 14 | `wilcoxon-signed-rank` | `ttest-paired` already tells students to use it when normality fails | Matched-ranks; the honest non-parametric sibling. |
| 15 | `mann-whitney` already covers independent ranks — no new work | — | (record only) |
| 16 | `cohens-kappa` | Inter-rater reliability promised in social/health packs | Also ICC / intraclass correlation as one "reliability" family. |
| 17 | `intraclass-correlation` | Reliability, social/health | rater agreement / repeated measures consistency. |

---

## Process for every new analysis (project convention)

1. `manifest.yaml` — exact fields per skill (id == folder, maturity
   `experimental`, quote any scalar containing `: `, pack+requires for heavy).
2. `analysis.py` — subclass `Analysis`; `run()` + `check_fit()`; always set
   `what_does_not_tell`; add `expert_review` when used outside intended
   conditions; warn (never silently coerce/impute).
3. `README.md` + `tests/test_<id>.py` (hand-computed + scipy/statsmodels/
   sklearn reference).
4. Register in `catalog/analyses.yaml` (built-analysis ⊆ catalogue test).
5. `rules.yaml` entry (advisor test enforces coverage).
6. Reference fixture in `docs/validation/references.yaml` (dashboard test).
7. `auphoria demo --analysis <id>` verified against real sample data — not just
   unit tests.
8. Update `docs/DISCIPLINE_PACKS.md` / README only when it actually ships.
9. Docs_site page regenerated (`gen_analysis_docs.py`), `--check` current.

## Priority recommendation

1. **Wave 1** (finish P1) — closes the biggest advertised gap and benefits every
   field. ~6 analyses.
2. **Wave 3 agri-animal + life-science** — directly serves the agricultural /
   biotech students AUPHORIA targets and the supervisor's sequencing interest.
3. **Wave 4** (kappa/ICC, wilcoxon-signed-rank) — cheap, cross-field, honest.
4. **Wave 2** — P2/P3 named plans as reach.
5. **Wave 3 remaining** — econ-eng/social-heavy, lower immediate demand.

Milestone: when Wave 1 + Wave 4 land, AUPHORIA covers the full P1 plan and its
two most-cited reliability fallbacks — a defensible "1.0 for all fields" claim.