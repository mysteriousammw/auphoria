"""Exploratory Factor Analysis (EFA) for AUPHORIA.

Finds the latent (hidden) dimensions that lie behind a set of several
correlated numeric item columns. This analysis:

- selects every numeric column in the data (the items);
- standardises them and builds the correlation matrix;
- checks sampling adequacy with the Kaiser-Meyer-Olkin (KMO) statistic and
  Bartlett's test of sphericity;
- extracts factors with ``sklearn.decomposition.FactorAnalysis``;
- optionally applies an orthogonal varimax rotation (implemented here with a
  simple planar-rotation loop, so we do not depend on ``factor_analyzer``);
- reports the factor loadings matrix, the variance explained per factor, and
  the eigenvalues / scree plot, and draws a loadings heatmap.

Guardrails are enforced here, not in the front end:
- fewer than three numeric item columns is refused (nothing to factor);
- fewer than five complete rows is refused;
- missing values are counted, reported and excluded (listwise), never imputed;
- KMO below ~0.6 or a sample below ~100 flags an expert-review banner and a
  WARN verdict (the analysis still runs, but the solution is fragile).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.decomposition import FactorAnalysis

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError

_MIN_ROWS = 5
_MIN_ITEMS = 3
#: Rule-of-thumb minimum observations per item for a stable solution.
_ROWS_PER_ITEM = 5.0
_KMO_ADEQUACY_FLOOR = 0.6
_SAMPLE_RECOMMENDED = 100


def _varimax(loadings: np.ndarray, max_iter: int = 200, tol: float = 1e-9):
    """Orthogonal (Kaiser-normalised) varimax rotation of a p x k loading matrix.

    Standard pairwise planar rotation: at each step the pair of columns whose
    rotation maximises the variance of squared loadings is found analytically.
    Returns ``(rotated_loadings, rotation_matrix)`` where
    ``rotated_loadings = loadings @ rotation_matrix`` (the rotation is computed
    on Kaiser-normalised loadings but applied to the raw loadings).
    """
    p, k = loadings.shape
    if k < 2:
        return loadings.copy(), np.eye(k)
    norms = np.sqrt(np.sum(loadings**2, axis=1))
    norms[norms < np.finfo(float).eps] = 1.0
    B = loadings / norms[:, None]  # Kaiser-normalised loadings
    R = np.eye(k)
    change = np.inf
    it = 0
    while change > tol and it < max_iter:
        it += 1
        change = 0.0
        for a in range(k - 1):
            for b in range(a + 1, k):
                x = B[:, a]
                y = B[:, b]
                u = x**2 - y**2
                v = 2.0 * x * y
                A = float(u.sum())
                Bv = float(v.sum())
                C = float((u**2 - v**2).sum())
                D = float((2.0 * u * v).sum())
                num = D - 2.0 * A * Bv / p
                den = C - (A**2 - Bv**2) / p
                theta = 0.25 * np.arctan2(num, den)
                change = max(change, abs(theta))
                c, s = np.cos(theta), np.sin(theta)
                xa, yb = B[:, a].copy(), B[:, b].copy()
                B[:, a] = c * xa + s * yb
                B[:, b] = -s * xa + c * yb
                ra, rb = R[:, a].copy(), R[:, b].copy()
                R[:, a] = c * ra + s * rb
                R[:, b] = -s * ra + c * rb
    rotated = loadings @ R
    return rotated, R


def _kmo(corr: np.ndarray) -> float:
    """Overall Kaiser-Meyer-Olkin measure of sampling adequacy.

    KMO = sum of squared off-diagonal correlations / (that + sum of squared
    partial correlations). Partial correlations come from the inverse of the
    correlation matrix. KMO near 1 means compact patterns of correlation; a
    rule of thumb treats values below ~0.6 as too low to factor well.
    """
    inv = np.linalg.pinv(corr)
    diag_inv = np.diag(inv)
    partial = -inv / np.sqrt(np.outer(diag_inv, diag_inv))
    np.fill_diagonal(partial, 0.0)
    r2 = corr**2
    np.fill_diagonal(r2, 0.0)
    p2 = partial**2
    denom = float(r2.sum() + p2.sum())
    if denom <= 0.0:
        return 0.0
    return float(r2.sum() / denom)


def _bartlett(corr: np.ndarray, n: int) -> tuple[float, float]:
    """Bartlett's test of sphericity.

    Null hypothesis: the correlation matrix is the identity (items are
    uncorrelated). The statistic is the textbook
    ``chi2 = -(n - 1 - (2p + 5) / 6) * ln(det(R))`` with ``df = p(p-1)/2``.
    """
    p = corr.shape[0]
    det = float(np.linalg.det(corr))
    if det <= 0.0:
        chi2 = 0.0
    else:
        chi2 = -(n - 1 - (2.0 * p + 5.0) / 6.0) * np.log(det)
    chi2 = max(0.0, chi2)
    df = p * (p - 1) // 2
    pvalue = float(stats.chi2.sf(chi2, df))
    return chi2, pvalue


def _heatmap(loadings: np.ndarray, item_labels: list[str], k: int, caption: str):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(max(4.0, 0.8 * k + 2.0), 6.0))
    vmax = max(1e-6, float(np.abs(loadings).max()))
    im = ax.imshow(loadings, aspect="auto", cmap="RdBu_r", vmin=-vmax, vmax=vmax)
    ax.set_xticks(range(k))
    ax.set_xticklabels([f"Factor {i + 1}" for i in range(k)])
    ax.set_yticks(range(len(item_labels)))
    ax.set_yticklabels(item_labels)
    ax.set_title("Factor loadings", fontsize=11)
    for i in range(len(item_labels)):
        for j in range(k):
            ax.text(
                j, i, f"{loadings[i, j]:.2f}", ha="center", va="center",
                color="#222", fontsize=8,
            )
    fig.colorbar(im, ax=ax, fraction=0.05, pad=0.04)
    fig.tight_layout()
    return fig, caption


def _scree(eigenvalues: np.ndarray, caption: str):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.0, 4.0))
    k_e = len(eigenvalues)
    ax.plot(range(1, k_e + 1), eigenvalues, marker="o", color="#4c72b0",
            linewidth=1.6)
    ax.axhline(1.0, color="#d9534f", ls="--", linewidth=1.0,
               label="eigenvalue = 1 (Kaiser)")
    ax.set_xticks(range(1, k_e + 1))
    ax.set_xlabel("Factor / component")
    ax.set_ylabel("Eigenvalue of the correlation matrix")
    ax.set_title("Scree plot", fontsize=11)
    ax.grid(axis="y", ls=":", alpha=0.5)
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig, caption


class FactorAnalysisAnalysis(Analysis):
    id = "factor-analysis"
    name = "Exploratory Factor Analysis"

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        del inputs  # EFA uses every numeric column automatically
        result = AnalysisResult()

        if len(data) < _MIN_ROWS:
            raise AssumptionError(
                f"Exploratory factor analysis needs at least {_MIN_ROWS} rows of "
                f"data; this file has only {len(data)}.",
                hint="Add more complete observations, or use a different analysis.",
            )

        numeric_cols = [
            c for c in data.columns if pd.api.types.is_numeric_dtype(data[c])
        ]
        n_missing_total = 0
        for c in numeric_cols:
            n_missing_total += int(data[c].isna().sum())
            self.describe_missing(data[c], c, ctx)
        if n_missing_total:
            ctx.log_decision(
                f"{n_missing_total} missing value(s) across the numeric item "
                "columns; they are counted and excluded, never imputed."
            )

        # Narrow to the numeric columns that actually vary (constant columns
        # have zero variance and cannot be standardised or correlated).
        used = [c for c in numeric_cols if data[c].dropna().std() > 1e-12]
        dropped_const = set(numeric_cols) - set(used)
        if dropped_const:
            result.add_warning(
                f"Constant column(s) {', '.join(sorted(dropped_const))} were "
                "ignored (zero variance makes them uninformative for a factor "
                "analysis)."
            )
            ctx.log_decision(
                f"Excluded constant column(s): {', '.join(sorted(dropped_const))}."
            )

        if len(used) < _MIN_ITEMS:
            raise AssumptionError(
                f"Exploratory factor analysis needs at least {_MIN_ITEMS} numeric "
                f"columns with variation; found {len(used)}.",
                hint="Pick a file with several correlated numeric item columns."
                     " A factor analysis needs a set of items that might share "
                     "a hidden dimension.",
            )

        matrix = data[used].astype(float)
        n_before = len(matrix)
        complete = matrix.dropna()
        dropped_rows = n_before - len(complete)
        if dropped_rows:
            result.add_warning(
                f"{dropped_rows} row(s) had a missing value in one of the item "
                "columns and were left out of this analysis. Missing values were "
                "counted and excluded, never imputed."
            )
            ctx.log_decision(
                f"Excluded {dropped_rows} row(s) with missing item values "
                f"(listwise); {len(complete)} row(s) remain."
            )

        if len(complete) < _MIN_ROWS:
            raise AssumptionError(
                "After removing rows with missing values there were fewer than "
                f"{_MIN_ROWS} complete rows left to factor.",
                hint="Provide more complete observations, or reduce missingness.",
            )
        n, p = complete.shape
        item_labels = list(complete.columns)
        ctx.log_decision(
            f"Running EFA on {len(item_labels)} numeric item column(s) "
            f"(columns {', '.join(item_labels)}) with n = {n} complete rows, "
            f"p = {p} items."
        )

        # --- standardise and build the correlation matrix
        X = complete.to_numpy(dtype=float)
        mu = X.mean(axis=0)
        sd = X.std(axis=0)
        sd[sd < np.finfo(float).eps] = 1.0
        Xz = (X - mu) / sd
        R = np.corrcoef(Xz, rowvar=False)
        R = np.nan_to_num(R, nan=0.0)
        ctx.log_decision(f"Correlation matrix built from {p} standardised items.")

        # --- sampling adequacy checks
        kmo = _kmo(R)
        chi2, bartlett_p = _bartlett(R, n)
        ctx.log_decision(
            f"KMO = {kmo:.4f}; Bartlett's sphericity chi2 = {chi2:.4f} "
            f"(df = {p * (p - 1) // 2}), p = {bartlett_p:.4g}."
        )

        # --- forcing parameter
        n_factors = int(params.get("n_factors", 2))
        n_factors = max(1, min(int(n_factors), p))
        rotation = params.get("rotation", "varimax")
        ctx.log_decision(
            f"Extracting {n_factors} factor(s) with sklearn FactorAnalysis; "
            f"rotation = '{rotation}'."
        )

        # --- factor analysis
        fa = FactorAnalysis(
            n_components=n_factors,
            random_state=ctx.safe_seed(),
            max_iter=1000,
        )
        fa.fit(Xz)
        raw_loadings = fa.components_.T  # p x k (items x factors)

        loadings = raw_loadings.copy()
        if rotation == "varimax":
            loadings, _rot = _varimax(raw_loadings)
            ctx.log_decision("Applied Kaiser-normalised orthogonal varimax rotation.")

        # variance explained: sum of squared loadings per factor / p
        ss_per_factor = np.sum(loadings**2, axis=0)
        variance_explained = ss_per_factor / float(p)
        cumulative = np.cumsum(variance_explained)

        # eigenvalues of the correlation matrix (for the scree plot)
        eigenvalues = np.sort(np.linalg.eigvalsh(R))[::-1]

        # --- guardrails: warnings + expert review for fragile solutions
        if kmo < _KMO_ADEQUACY_FLOOR:
            result.add_warning(
                f"The Kaiser-Meyer-Olkin measure of sampling adequacy is low "
                f"(KMO = {kmo:.3f} < {_KMO_ADEQUACY_FLOOR:.1f}). The items share "
                "little variance that a factor model can exploit; the solution "
                "is fragile. Consider more (or more correlated) items."
            )
            result.add_expert_review(
                f"KMO = {kmo:.3f} is below the {_KMO_ADEQUACY_FLOOR:.1f} "
                "adequacy threshold; the factor solution may be unstable."
            )
        if n < _SAMPLE_RECOMMENDED or n / p < _ROWS_PER_ITEM:
            result.add_warning(
                f"The sample is small for a stable factor analysis (n = {n} "
                f"rows across {p} items; recommended about "
                f"{_ROWS_PER_ITEM:.0f}-10 observations per item and at least "
                f"{_SAMPLE_RECOMMENDED} observations overall)."
            )
            result.add_expert_review(
                f"Sample size {n} is below the recommended minimum of about "
                f"{_SAMPLE_RECOMMENDED} observations "
                f"({_ROWS_PER_ITEM:.0f}-10 per item); factor loadings carry "
                "substantial sampling error at this size."
            )

        # --- verdicts
        verdict = "PASS" if kmo >= _KMO_ADEQUACY_FLOOR else "WARN"
        result.add_verdict(
            verdict, "kmo-adequacy",
            f"Kaiser-Meyer-Olkin measure of sampling adequacy = {kmo:.3f} "
            f"({'adequate (>= ' + str(_KMO_ADEQUACY_FLOOR) + ')' if kmo >= _KMO_ADEQUACY_FLOOR else 'below the adequacy threshold'});"
            f" this reflects how much shared variance the items have.",
        )
        verdict = "PASS" if bartlett_p < 0.05 else "WARN"
        result.add_verdict(
            verdict, "bartlett-significance",
            f"Bartlett's test of sphericity chi2({p * (p - 1) // 2}) = "
            f"{chi2:.2f}, p = {self.fmt_p(bartlett_p)}; this tests whether the "
            "correlation matrix differs from the identity.",
        )

        # --- tables
        kmo_table = pd.DataFrame(
            {
                "Check": [
                    "KMO (sampling adequacy)",
                    "Bartlett chi-squared",
                    "Bartlett df",
                    "Bartlett p-value",
                ],
                "Value": [
                    round(kmo, 4),
                    round(chi2, 4),
                    p * (p - 1) // 2,
                    self.fmt_p(bartlett_p),
                ],
            }
        )
        result.tables["KMO & Bartlett"] = kmo_table

        loading_df = pd.DataFrame(
            loadings,
            index=item_labels,
            columns=[f"Factor {i + 1}" for i in range(n_factors)],
        )[:].round(4)
        result.tables["Factor loadings"] = loading_df.reset_index().rename(
            columns={"index": "Item"}
        )

        var_df = pd.DataFrame(
            {
                "Factor": [f"Factor {i + 1}" for i in range(n_factors)],
                "Sum of squared loadings": [round(float(v), 4) for v in ss_per_factor],
                "Variance explained": [round(float(v), 4) for v in variance_explained],
                "Cumulative": [round(float(c), 4) for c in cumulative],
            }
        )
        result.tables["Variance explained"] = var_df

        eig_table = pd.DataFrame(
            {
                "Component": range(1, p + 1),
                "Eigenvalue": [round(float(e), 4) for e in eigenvalues],
            }
        )
        result.tables["Eigenvalues"] = eig_table

        # --- figures
        fig, cap = _heatmap(
            loadings, item_labels, n_factors,
            "Heatmap of the factor loadings (items x factors)",
        )
        result.figures.append(FigureItem(name="efa_loadings_heatmap", figure=fig, caption=cap))
        fig, cap = _scree(
            eigenvalues,
            "Scree plot of the correlation-matrix eigenvalues (elbow + "
            "eigenvalue > 1 suggest how many factors to keep)",
        )
        result.figures.append(FigureItem(name="efa_scree", figure=fig, caption=cap))

        # --- summaries
        kmo_label = (
            "adequate"
            if kmo >= _KMO_ADEQUACY_FLOOR
            else "inadequate for stable factoring (< 0.6)"
        )
        result.summaries = {
            "items": f"{p} numeric item column(s)",
            "sample": f"n = {n} complete rows",
            "factors extracted": str(n_factors),
            "rotation": rotation,
            "KMO": f"{kmo:.3f} ({kmo_label})",
            "Bartlett's sphericity": (
                f"chi2 = {chi2:.2f}, p {('<' if bartlett_p < 0.001 else '=')} "
                f"{self.fmt_p(bartlett_p)}"
            ),
            "variance explained": (
                f"{variance_explained[0]:.1%} "
                f"(of {n_factors} factor{'s' if n_factors > 1 else ''})"
            ),
        }

        # --- methods sentences
        p_str = "p < 0.001" if bartlett_p < 0.001 else f"p = {bartlett_p:.3f}"
        methods = [
            f"An exploratory factor analysis was run on {p} standardised "
            f"numeric item column(s) ({', '.join(item_labels)}) with listwise "
            f"deletion, leaving n = {n} complete observations.",
            f"Sampling adequacy was checked with the Kaiser-Meyer-Olkin measure "
            f"(KMO = {kmo:.3f}) and Bartlett's test of sphericity "
            f"(chi2({p * (p - 1) // 2}) = {chi2:.2f}, {p_str}).",
            f"{n_factors} factor(s) were extracted with maximum-likelihood "
            f"factor analysis and given an orthogonal varimax rotation; the "
            f"extracted factors together account for "
            f"{cumulative[-1]:.1%} of the total variance."
            if rotation == "varimax"
            else f"{n_factors} factor(s) were extracted with maximum-likelihood "
            f"factor analysis (unrotated loadings); the extracted factors "
            f"together account for {cumulative[-1]:.1%} of the total variance.",
        ]
        if dropped_rows:
            methods.append(
                f"{dropped_rows} row(s) with missing item values were excluded; "
                "no missing values were imputed."
            )
        result.methods = methods

        # --- honest interpretation
        result.what_does_not_tell = (
            "EFA finds structure in the correlations between items; it does not "
            "prove that a latent factor caused the item responses (that would "
            "be a causal claim about unmeasured variables). The factor names "
            "are the analyst's interpretation of which items load together, not "
            "something the analysis outputs. EFA is not PCA: principal "
            "components summarise total variance while factors model shared "
            "variance, so they give different results and should not be "
            "confused."
        )

        return result

    def check_fit(
        self,
        profile: Any,
        params: dict[str, Any],
        inputs: dict[str, str],
    ) -> list[str]:
        del params, inputs
        refusals: list[str] = []
        # EFA needs several numeric columns; if the profile can already see few,
        # refuse up front (run() still re-checks on the actual DataFrame).
        try:
            cols = list(profile.all_columns())  # type: ignore[attr-defined]
        except AttributeError:
            try:
                cols = list(profile)  # type: ignore[call-overload]
            except Exception:  # noqa: BLE001
                return refusals
        numeric = sum(1 for c in cols if getattr(c, "kind", None) == "numeric")
        if numeric < _MIN_ITEMS:
            refusals.append(
                f"Exploratory factor analysis needs at least {_MIN_ITEMS} numeric "
                f"item columns; this file appears to have only {numeric}."
            )
        return refusals


# Module-level instance the registry looks for.
ANALYSIS = FactorAnalysisAnalysis()
