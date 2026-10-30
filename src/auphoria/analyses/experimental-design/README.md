# Experimental Design ANOVA (`experimental-design`)

Analyses a **balanced designed experiment** with four classic layouts,
chosen by the `design` parameter:

| design | Layout | Extra column(s) needed |
|--------|--------|------------------------|
| `crd` | Completely randomized (one-way ANOVA) | — |
| `rcbd` | Randomized complete block (block + treatment) | `block` |
| `latin-square` | Latin square (row, column, treatment) | `row`, `col` |
| `factorial` | Two-factor factorial (A, B, A×B interaction) | `factor_b` |

## When to use it

- You ran (or planned) a designed experiment: a field trial, an animal
  feeding trial, a greenhouse experiment, a bench experiment with blocking.
- You want the ANOVA table **for the design you actually used** — with the
  blocking factors properly removed from the error term, so the F tests are
  honest.
- You want a mean-separation table (Tukey HSD or Fisher LSD) showing which
  treatments differ.

## Expected input shape

One row per experimental unit, with the outcome plus role columns:

| yield | treatment | block | row | col | factor_b |
|-------|-----------|-------|-----|-----|----------|
| 14.2  | A         | b1    | r1  | c1  | low      |
| 16.8  | B         | b1    | r1  | c2  | high     |

Only the columns needed for your chosen design are used; extra columns in
the sheet are ignored.

## What you get

- **ANOVA table** for the design (source, SS, df, MS, F, p).
- **Treatment means table** with compact-letter mean separation.
- **Assumption checks** (Shapiro-Wilk on residuals, Levene's test) as
  PASS/WARN verdicts.
- **Effects plot** (treatment means ± SEM).
- `methods.txt` paragraph and `report.html`.

## Guardrails

- **Balanced designs only.** Unbalanced layouts are refused with a hint to
  use `anova-oneway` or `regression-multiple` instead.
- Exactly one observation per treatment×block (or row/col) cell for
  RCBD/Latin.
- Two observations minimum per treatment (or treatment combination) — there
  must be an error term.
- Missing values are counted, excluded with a warning, never imputed.
