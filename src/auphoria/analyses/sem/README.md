# Structural Equation Model — one-factor CFA (`sem`)

A **confirmatory factor analysis (CFA)** that tests whether a set of numeric
**item columns** all measure **one underlying construct** (a single latent
factor). It is a confirmatory model — you posit "these items hang together"
and the tool checks how well the data agree with that hypothesis.

## What the tool does

Aproper SEM starts from a **hypothesised model you specify** (which factors
load on which items, and any paths between them). AUPHORIA runs
non-interactively and cannot collect your model, so it fits the simplest
universally-applicable confirmatory model:

```
F =~ item1 + item2 + ... + itemN
```

i.e. **all numeric columns load onto a single latent factor `F`**. This
one-factor CFA directly answers "do my items measure one underlying construct?"
Students with more complex hypothesised models (multiple factors, paths,
mediators) should **see a statistician** — the tool notes this as a limitation.

## When to use it

- You have **several correlated numeric columns** (questionnaire items) that
  you believe measure **one trait** (anxiety, engagement, knowledge, ...).
- You want to **confirm** (not just explore) that structure with the standard
  fit indices: **CFI, TLI, RMSEA, SRMR** and a chi-square test.
- You want the **standardised factor loading** of every item and a **fitted
  equation string** you can quote.

## What you get

- A **factor-loadings table** — each item, its standardised loading on the
  latent factor, its standard error and p-value.
- A **model-fit table** with **CFI, TLI, RMSEA, SRMR**, **chi-square, df** and
  the **chi-square p-value**.
- A **PASS / WARN verdict** interpreting the fit against common rules of thumb
  (CFI ≥ 0.95, TLI ≥ 0.95, RMSEA ≤ 0.06, SRMR < 0.08).
- The **fitted equation string**.
- A **loading bar chart** figure.
- A `methods.txt` paragraph you can paste into a paper.

## Choices

- **alpha** (default `0.05`): the significance level used for the chi-square
  goodness-of-fit verdict.

## Assumptions and minimum sample size (checked and reported)

- Each item column must be **numeric**.
- **At least 3 numeric items** are required (you cannot define a latent factor
  with fewer); fewer is refused.
- **At least 30 complete rows** are required; fewer is refused.
- A stable CFA generally needs **about 100 complete observations**; below that
  the analysis still runs but is flagged for **expert review**.
- The items are assumed to be **unidimensional** (all measure one factor).
- Missing values are **counted, reported and excluded** (listwise), **never
  imputed**.

## When NOT to use it

- Fewer than 3 numeric (varying) columns → refused.
- You haven't hypothesised a structure yet → run **Exploratory Factor Analysis
  (`factor-analysis`)** or **PCA** first.
- You need a **multi-factor model with paths and mediators** → this tool can't
  take your model; consult a statistician / specialised SEM software.

## How to read the output

1. **Fit indices**: CFI ≥ 0.95, TLI ≥ 0.95, RMSEA ≤ 0.06 and SRMR < 0.08
   suggest a good fit. A low CFI (< 0.9) means the one-factor model doesn't fit
   — the items may not be unidimensional, or some items load poorly.
2. **Chi-square p-value**: a **non-significant** p supports the model. But note
   the chi-square test is sensitive to large samples — it can reject even a
   good model when `n` is big, so look at CFI/RMSEA/SRMR too.
3. **Loadings**: items with high standardised loadings (say ≥ 0.4) hang
   together well on the factor; a low-loading item may not belong.
4. **Remember the limits**: a good fit does **not** prove your model is right —
   many equivalent models fit equally well.

## Example

```bash
auphoria run --data my_questionnaire.csv --analysis sem
```

> Maturity: **experimental** (not "validated"). This is a **PhD-level,
> confirmatory** analysis meant for statistically experienced users; treat
> small-sample or poor-fit results as preliminary and seek expert review.