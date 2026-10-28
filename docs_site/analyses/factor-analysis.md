# Exploratory Factor Analysis

`factor-analysis` · maturity: **experimental**

Discipline packs: `health`, `social`  

Validation reference: Synthetic two-factor data; cross-checked vs sklearn.decomposition.FactorAnalysis + textbook Bartlett/KMO  


## What it does

Exploratory Factor Analysis (EFA) finds the latent (hidden) dimensions or factors that lie behind a set of several correlated numeric item columns (for example questionnaire items all thought to measure a few underlying traits). It reports sampling adequacy (KMO, Bartlett's test of sphericity), the factor loadings matrix (varimax-rotated), eigenvalues and a scree plot, and the variance explained by each factor, so you can see how many dimensions the items really seem to tap and which items load on each.

## Options

- `n_factors` (default 2): Number of latent factors to extract.
- `rotation` (default varimax): Rotation to make loadings easier to interpret; 'varimax' is the default, 'none' keeps the raw (unrotated) factor loadings.

## What you get out

- sampling-adequacy table (KMO statistic, Bartlett's chi-squared, df, p)
- factor loadings matrix (items x factors, varimax-rotated by default)
- variance-explained table (sum of squared loadings per factor /
- eigenvalues table for correlation matrix (scree)
- loadings heatmap figure
- scree plot figure
- methods.txt paragraph
- report.html

## Assumptions

- Each column used must be numeric (item responses on a numeric scale).
- The items must be meaningfully correlated with one another; if the correlation matrix is essentially diagonal there is no shared structure to find (checked with Kaiser-Meyer-Olkin KMO and Bartlett's test of sphericity; KMO below about 0.6 flags poor sampling adequacy).
- A minimum sample size of about 5-10 observations per item, and at least 100 observations overall, is strongly recommended for stable factor solutions. With fewer observations the analysis still runs on small data but the result is flagged for expert review.
- The data must have at least 3 numeric columns and at least 5 complete rows (listwise deletion of rows with missing values; missing values are counted and reported, never imputed).
- Removing or adding factors (choosing n_factors) is an analyst judgement informed by eigenvalues, variance explained and interpretability.

## Limitations

- EFA finds structure in the correlations between items, not causes; it does not establish that a latent factor caused the item responses.
- The factor names are the analyst's interpretation of the loadings pattern, not something the analysis outputs.
- EFA is not PCA: principal components summarise the total variance of the items, whereas factors model the shared variance. The two give different numbers and should not be confused.
- Missing values are excluded (listwise) and reported, not imputed; heavy missingness shrinks the effective sample.
- The number of factors is not an output of the analysis alone; it is chosen by the analyst guided by the scree plot, eigenvalues > 1, variance explained and theoretical expectations.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis factor-analysis
```
