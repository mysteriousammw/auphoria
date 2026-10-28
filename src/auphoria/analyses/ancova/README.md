# ANCOVA (`ancova`)

Tests whether **two or more independent groups** differ on a **numeric
outcome** after **statistically adjusting for one numeric covariate** — for
example, final exam score across two teaching methods after removing the
influence of prior aptitude, or plant yield across two fertilisers after
adjusting for initial plant size. The estimate is fitted by **ordinary least
squares** (statsmodels): `outcome ~ covariate + group`.

## When to use it

- Your outcome is a number (score, yield, weight, time, concentration).
- You have a grouping column with **two or more categories**.
- You have a **single numeric covariate** you want to hold constant so the
  group comparison is not confounded by it.
- You want the *covariate-adjusted* group means and a test of whether they
  differ.

## What you get

- **Adjusted group means** — the value of each group's outcome at the common
  covariate mean, next to the raw means and per-group covariate means.
- An **ANCOVA table**: sum of squares, degrees of freedom, mean square, F and
  p for the **covariate-adjusted group effect** and for the **covariate effect**.
- An **effect size** table: partial eta-squared for the group (with a
  plain-English label) and the covariate slope coefficient.
- A **scatter figure** of outcome vs covariate coloured by group, with the
  parallel (common-slope) ANCOVA lines.
- A `methods.txt` paragraph you can paste into a paper.

## Choices

- **alpha** (default `0.05`): significance level for the group and covariate
  effect tests and for the assumption checks.

## Assumptions (checked and reported, never silently ignored)

A PASS/WARN verdict is emitted for each check; a WARN never stops the analysis.

- **Linearity**: the covariate is linearly related to the outcome
  (assessed via the covariate coefficient and the scatter figure).
- **Homogeneity of regression slopes**: the slope of the outcome on the
  covariate is the same in every group (checked with the group-by-covariate
  interaction). If this is violated the adjusted comparison is hard to read.
- **Normality of residuals** (Shapiro-Wilk).
- **Equal variance** across groups (ANCOVA is fairly robust for larger samples).
- **Independent groups**, each with at least two observations.

### Minimum sample size (state this clearly)

ANCOVA must estimate both the covariate slope and the group differences, so it
needs enough rows. This tool recommends **at least about 12 complete rows in
total and about 5 per group**. Below that the analysis still runs, but it
emits a prominent **needs-expert-review** banner and you should treat the
result as preliminary.

## When NOT to use it

- **No sensible grouping** (one category only) → fit a plain regression
  instead (the tool refuses with this hint).
- **More than one meaningful covariate** → multiple regression / a model with
  several covariates is the right tool.
- **The covariate was measured after treatment**, or the treatment itself
  changed the covariate → the adjustment is misleading.
- **Very clear non-linearity or non-parallel slopes** → the adjusted means are
  hard to interpret; consider a model with an interaction or a non-linear fit.

## How to read the output

1. **Group effect F and p**: `p < alpha` means the groups differ on the outcome
   *after adjusting for the covariate*. Report as `F(df_group, df_resid)`, e.g.
   `F(1, 37) = 8.21`.
2. **Covariate coefficient**: the expected change in the outcome per one-unit
   increase in the covariate, holding the group constant. Its p-value tells you
   whether the covariate matters.
3. **Adjusted means**: the group averages you would predict if the covariate
   were equal in every group. Because they are equated for the covariate, they
   differ from the raw means.
4. **Partial eta-squared**: the fraction of variance in the outcome (beyond the
   covariate) explained by the group. Roughly: 0.01 small, 0.06 medium,
   0.14+ large.

## Example

```bash
auphoria run --data my_data.csv --analysis ancova \
  --outcome final_score --group teaching_method \
  --extra covariate=pretest_score
```

> Maturity: **experimental** (not "validated"). This is an advanced analysis;
> when used with small samples or on data with violated assumptions it flags a
> requirement for expert review.