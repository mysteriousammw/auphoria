# Experimental Design ANOVA (CRD, RCBD, Latin Square, Factorial)

`experimental-design` · maturity: **experimental**

Validation reference: Standard textbook CRD/RCBD examples: three treatments (means 4/10/16), SS_between = 288, SS_within = 24, F = 54, p < 0.001 — the same fixture as anova-oneway; RCBD fixture with block SS subtracted from the error term.  


## What it does

Analyses a designed experiment with one of four classic layouts chosen via the 'design' parameter: completely randomized (CRD), randomized complete block (RCBD), Latin square, or a two-factor factorial. Reports the analysis-of-variance table for that design (blocking factors removed from the error term), treatment means, Tukey/LSD mean separation, and the assumptions checked, so students see the design's structure in the output.

## What you need

- **outcome** (numeric-column, required): The numeric response (e.g. yield, growth, score).
- **treatment** (categorical-column, required): The treatment/factor of interest (e.g. fertiliser dose, variety).
- **block** (categorical-column, optional): Blocking factor (required for RCBD; optional elsewhere).
- **row** (categorical-column, optional): Row block (required for Latin square).
- **col** (categorical-column, optional): Column block (required for Latin square).
- **factor_b** (categorical-column, optional): Second factor (required for factorial design).

## Options

- `design` (default crd): The experimental layout to analyse.
- `alpha` (default 0.05): Significance level for the F tests and mean separation.
- `separation` (default tukey): Mean-separation method (Tukey HSD or Fisher LSD).

## What you get out

- design structure table (layout, units, treatments, blocks)
- ANOVA table (source, SS, df, MS, F, p for every factor in the design)
- treatment means table with mean separation letters
- assumption checks (Shapiro-Wilk residuals, Levene's test)
- effects plot (treatment means with error bars)
- methods.txt paragraph
- report.html

## Assumptions

- The design must be balanced (equal observations per treatment combination); unbalanced layouts are refused with a hint to use anova-oneway or regression instead.
- The outcome is numeric and roughly normally distributed (checked on residuals with Shapiro-Wilk; reported as WARN, never a hard refusal).
- Variances are homogeneous across treatments (checked with Levene's test; reported as WARN).
- For CRD, groups are independent; for RCBD, one observation per treatment per block; for Latin square, one observation per row/col/treatment cell; for factorial, all treatment combinations present equally often.
- Missing values are counted and excluded with a warning, never imputed.

## Limitations

- A significant F only says at least one treatment differs; use the mean-separation table to see which treatments differ.
- Results are associations, not causation; randomisation and replication happened at design time, not inside this tool.
- Unbalanced and incomplete designs (missing cells, different block sizes) are out of scope — use regression-multiple with dummy variables for those.
- Split-plot and other partially nested layouts are not covered by this version.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis experimental-design --outcome <outcome> --extra treatment=<treatment>
```
