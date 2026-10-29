# Structural Equation Model (one-factor CFA)

`sem` · maturity: **experimental**

Discipline packs: `social`  

Validation reference: Synthetic four-item one-factor data (known loadings); CFI/TLI/RMSEA/SRMR via semopy.stats.calc_stats + hand-computed residual SRMR, loadings vs semopy Model.inspect(std_est=True).  


## What it does

Structural Equation Modelling (SEM) here fits a CONFIRMATORY one-factor model — every numeric column in the file (for example questionnaire items) is assumed to load onto a single latent construct, and the analysis reports how well that hypothesised model reproduces the observed correlations. Because AUPHORIA cannot prompt you for your own hypothesised model, it fits the simplest universally-applicable confirmatory model, a one-factor CFA that directly tests whether your items all measure one underlying construct. It reports the standard fit indices (CFI, TLI, RMSEA, SRMR), a chi-square goodness-of-fit test, the standardised factor loadings for every item, and a fitted-equation string, so you can judge whether the one-factor model is acceptable.

## Options

- `alpha` (default 0.05): Significance level used for the fit (chi-square p-value) verdict.

## What you get out

- factor-loadings table (item, standardised loading, SE, p)
- model-fit table (CFI, TLI, RMSEA, SRMR, chi2, df, chi2 p)
- fitted model equation string
- loading bar-chart figure
- methods.txt paragraph
- report.html

## Assumptions

- Each column used must be numeric (item responses on a numeric scale).
- At least 3 numeric items are required to define a latent factor.
- Confirmatory factor analysis requires a fairly large sample; a minimum of about 100 complete observations is recommended, and the result is flagged for expert review below that. Samples under about 30 rows are refused.
- The items are assumed to measure one underlying construct (unidimensionality). This tool fits a one-factor model and does not test cross-loadings or alternative structures.
- Missing values are excluded (listwise) and reported, never imputed.
- The model is one-factor by necessity. Students with more complex hypothesised models (multiple factors, paths, mediators) should see a statistician, because AUPHORIA cannot take a user-specified model.

## Limitations

- A good fit does NOT prove the model is correct. Many different (equivalent) models can reproduce the data equally well, so this is only a test of one hypothesised structure, not a proof of it.
- The tool fits a single-factor confirmatory model by default. It does not test cross-loadings, causal direction, or more complex path/SEM models with mediators unless a student extends the model (which AUPHORIA does not support).
- The one-factor model assumes unidimensionality of the items.
- Missing values are excluded (listwise) and reported, not imputed; heavy missingness shrinks the effective sample.
- The chi-square test is sensitive to large samples (it can reject a well-fitting model when n is large); use the other fit indices too.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis sem
```
