# Principal Component Analysis

`pca` · maturity: **experimental**

Discipline packs: `life-science`, `social`  

Validation reference: Perfect-correlation 2-column data; cross-checked vs sklearn.decomposition.PCA  


## What it does

Reduces many numeric columns (gene expression, soil chemistry, questionnaire items, spectral data) into a few combined scores — principal components — that capture most of the variation, so you can see structure and shrink a wide table to a small number of interpretable dimensions before further analysis.

## Options

- `n_components` (default 2): Number of principal components to compute and report.
- `standardize` (default True): Centre and scale each variable to unit variance before PCA. Recommended when variables are on different measurement scales.

## What you get out

- variance-explained table (eigenvalue, % variance explained, cumulative % per component)
- component loadings table (each variable's weight on each component)
- how-many-components guidance (keep until cumulative >= 80% or eigenvalue > 1)
- scree plot figure
- score scatter figure of the first two components
- methods.txt paragraph
- report.html

## Assumptions

- The data has at least two numeric columns; PCA uses all of them automatically.
- The variables are correlated enough to share structure (checked with Bartlett's test of sphericity when there are more rows than variables).
- Variables are standardised to unit variance before PCA (the default), or are already on the same scale.
- No strong outliers; PCA is not robust and a few extreme values can dominate a component.
- Minimum sample size: at least 3 complete rows to run, and results are only stable with at least 10 rows, ideally more rows than variables (n > p).

## Limitations

- PCA is not factor analysis: components are variance-maximising linear combinations, not latent constructs or causes.
- The scaling choice changes the result; standardising (the default) weights variables equally, while raw-scale PCA lets high-variance variables dominate.
- Missing values are excluded row-wise with a warning, never imputed.
- With fewer rows than variables the component estimates are unstable and Bartlett's test cannot run.
- Components are computed on your data alone and may not generalise to new samples without validation.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis pca
```
