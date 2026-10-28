# Library check — dependencies for AUPHORIA analyses

Verified locally in this environment (macOS arm64, Python 3.11.17) on
2026-10-24. Two tests were actually run for the table below:
- **install**: `pip install <pkg>` succeeded under the venv;
- **import**: the package imported with `import <pkg>` and reported a version;
- **Python-3.10 support**: resolved with
  `pip install --dry-run --ignore-installed --only-binary=:all: --python-version 3.10 <pkg>`
  (pip's authoritative resolver, not an estimate).

"Colab" column meaning: Google Colab's default runtime ships Python 3.10-3.11
and preinstalls numpy / pandas / scipy / matplotlib / seaborn / scikit-learn.
Because AUPHORIA's required range is Python 3.10-3.12 and all packages below
resolve there, they install cleanly on Colab without disturbing its pinned
environment; we did not re-test on a live Colab kernel this phase (flagged).

## P1 / core stack (per analysis in catalog/analyses.yaml)

| Package | Installs | Imports | Py 3.10 resolves to | License | Notes / pin |
|---|---|---|---|---|---|
| numpy | ✓ | ✓ | 2.2.6 | BSD-3 (multi) | pin `>=1.26,<3` |
| pandas | ✓ | ✓ | 2.3.3 | BSD-3 | pin `>=2.0,<3` |
| scipy | ✓ | ✓ | 1.15.3 | BSD-3-Clause | pin `>=1.10,<2` |
| statsmodels | ✓ | ✓ | 0.15.0 | BSD-3-Clause | **heavy-ish** — pulls patsy, formulaic, wrapt, narwhals, xarray (via formulaic) |
| scikit-learn | ✓ | ✓ | 1.7.2 | BSD-3-Clause | pin `>=1.1,<2`; needed for ML + PCA |
| matplotlib | ✓ | ✓ | 3.10.9 | BSD (custom, PSF-compat) | pin `>=3.7,<4` |
| seaborn | ✓ | ✓ | 0.13.2 | BSD-3 | optional sugar over matplotlib; not required for any P1 analysis |
| PyYAML | ✓ | ✓ | 6.0.3 | MIT | pin `>=6,<7` |
| openpyxl | ✓ | ✓ | 3.1.5 | MIT | Excel `.xlsx` reader; optional extra `auphoria[excel]` |
| jinja2 | ✓ | ✓ | 3.1.6 | BSD-3 | report templating (already available) |
| pydantic | ✓ | ✓ | 2.14.1 | MIT | only if we adopt typed config; not needed for P1 |
| typer | ✓ | ✓ | 0.27.3 | MIT | CLI sugar; we use stdlib `argparse` — not required |
| rich | ✓ | ✓ | 15.0.0 | MIT | console styling; not required for P1 |
| pingouin | ✓ | ✓ | 0.6.1 | **GPL-3.0** | ⚠️ see licensing note below |
| lifelines | ✓ | ✓ | 0.30.0 | MIT | survival (Kaplan-Meier, Cox); pulls autograd |

### ⚠️ Licensing caveat — pingouin is GPL-3.0
`pingouin` is convenient (effect sizes, Cronbach alpha, Bland-Altman, robust
t-tests in one call) but it is **GPL-3.0**. AUPHORIA itself is MIT. Depending
on where analyses are distributed and whether AUPHORIA links against it, GPL
is copyleft and can impose conditions on a combined work. Options (recorded in
DECISIONS.md):
- (recommended for all P1 analyses) implement effect sizes / t-tests /
  reliability directly with **scipy + statsmodels + numpy**, which are all
  permissive (BSD), and **drop pingouin**;
- keep pingouin only behind an optional, clearly-flagged extra and do not let
  it become a hard dependency of the MIT core.

Recommendation: **do not make pingouin a required dependency.** The P1
analyses (t-test, paired t-test, ANOVA, chi-square, correlations, Mann-Whitney,
Kruskal-Wallis, regressions, logistic, OR/RR, Kaplan-Meier, Cronbach alpha,
PCA, ML eval) are all implementable with scipy/statsmodels/scikit-learn/
lifelines — all permissively licensed. Where a convenience function from
pingouin would be handy (e.g. `cronbach_alpha`), reimplement it in-scope rather
than pull GPL.

### ⚠️ Heavy-dependency flags
- **statsmodels** brings a fairly large dependency set (formulaic, patsy,
  wrapt, narwhals, xarray-via-formulaic). It is the right tool for regression/
  ANOVA/logistic/mixed-models and is standard and preinstalled-résolvable on
  Colab; acceptable but should be a real (not optional) dependency only once
  those analyses ship. For pure P1 scipy covers most inference; add statsmodels
  when regression/ANOVA models are implemented.
- **lifelines** pulls `autograd` (a numerical-autodiff lib) even for basic
  survival. Acceptable for Kaplan-Meier/Cox at P1; alternatively statsmodels'
  `SurvivalFunctions` (KM) and `PHReg` (Cox) cover it permissively with no
  extra dep —**prefer statsmodels for survival** to avoid autograd.
- **factor_analyzer**, **semopy** (EFA/SEM, P2/P3) were **not** added: `semopy`
  is a niche, less-maintained SEM package; EFA can be done with scikit-learn's
  `FactorAnalysis`/`PCA`. Defer SEM decision until P3.
- **pydeseq2** (differential expression, P3) is **heavy** (depends on tensorflow
  or similar / GPU-adjacent) and out of scope for P1/P2; the catalogue already
  lists differential-expression as P3 and notes statsmodels GLM(negative
  binomial) as the light fallback.

## Colab caveat
All P1 deps resolve for Python 3.10 (and are ≥ current on 3.11). numpy/pandas/
scipy/matplotlib/seaborn/sklearn are preinstalled in Colab's default runtime,
so installing AUPHORIA adds at most statsmodels + lifelines + pyyaml and does
not downgrade anything Colab pins. **Not re-verified on a live Colab kernel
this phase** — the notebook (Phase 1) installs with `pip install` and must be
smoke-tested on Colab before release (PUBLISH_CHECKLIST).

## Recommended pins (pyproject.decision, finalised when P1 analyses ship)
```
numpy>=1.26,<3
pandas>=2.0,<3
scipy>=1.10,<2
statsmodels>=0.14,<1        # when regression/ANOVA/models ship
matplotlib>=3.7,<4
scikit-learn>=1.1,<2        # when ML/PCA ship
PyYAML>=6,<7
openpyxl>=3.1               # optional [excel]
```
These ranges are all acceptable on Python 3.10.0 (numpy 2.2.6, scipy 1.15.3,
statsmodels 0.15.0, sklearn 1.7.2 verified to resolve for 3.10 above).