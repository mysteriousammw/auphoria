"""Principal Component Analysis (PCA) for AUPHORIA.

Reduces many numeric columns into a few combined scores (principal
components) that capture most of the variation, using scikit-learn's
``sklearn.decomposition.PCA``. The variance-explained table, component
loadings and how-many-components guidance expose exactly what PCA does so
students can see where the numbers come from and decide how many components
to keep.

Guardrails are enforced here, not in the front end:
- the analysis uses ALL numeric columns of the data automatically (it needs
  no explicit column inputs), refusing wholesale if fewer than two numeric
  columns exist or fewer than three complete rows remain;
- missing values are counted and excluded with a warning (listwise), never
  imputed;
- variables are standardised (centred and scaled to unit variance) by
  default, which is the recommended treatment when columns live on wildly
  different scales;
- near-constant (zero variance) columns are dropped with a warning, because
  they cannot contribute information;
- small samples, near-constant columns and a dominant single variable are
  surfaced through expert_review and PASS/WARN verdicts, never silent.

PCA is implemented by scikit-learn (permissive BSD-3-Clause), so no
additional dependency is introduced.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError

#: Keep a component when its eigenvalue exceeds 1 (Kaiser/Guttman heuristic).
_EIGENVALUE_CUTOFF = 1.0
#: Aim to keep components until this much of the variance is captured.
_CUMULATIVE_TARGET = 80.0
#: Standardized-data gives eigenvalue = explained_variance; small stability floor.
#: A component that dominates on its own may reflect one variable, not structure.
#: Threshold used to flag an exceedingly dominant first component.
_ONE_DOMINANT_THRESHOLD = 0.9


class PcaAnalysis(Analysis):
    id = "pca"
    name = "Principal Component Analysis"

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, Any],
        ctx: RunContext,
    ) -> AnalysisResult:
        del inputs  # PCA needs no explicit column inputs; it uses all numeric columns.
        result = AnalysisResult()

        if data.shape[0] < 3:
            raise AssumptionError(
                f"The data has only {data.shape[0]} row(s); PCA needs at least "
                "three complete rows to run.",
                hint="Provide a file with at least three rows of data.",
            )

        # --- collect all numeric columns -------------------------------------
        numeric_cols = [
            c for c in data.columns if pd.api.types.is_numeric_dtype(data[c])
        ]
        if len(numeric_cols) < 2:
            raise AssumptionError(
                f"PCA needs at least two numeric columns, but the data only has "
                f"{len(numeric_cols)}. Non-numeric columns are not used.",
                hint="Choose a file with several numeric columns (e.g. gene "
                     "expression, soil chemistry, questionnaire items).",
            )
        ctx.log_decision(
            f"Using all {len(numeric_cols)} numeric columns automatically: "
            f"{', '.join(numeric_cols)}."
        )

        # --- missing values: count, then drop rows listwise with a warning ----
        working = data[numeric_cols].copy()
        total_missing = int(working.isna().sum().sum())
        dropped = int(working.isna().any(axis=1).sum())
        if total_missing:
            result.add_warning(
                f"{dropped} row(s) had at least one missing numeric value and "
                f"were left out of the PCA. Missing values were counted, not "
                f"changed or replaced (never imputed)."
            )
            ctx.log_decision(
                f"Counted {total_missing} missing value(s) across the numeric "
                f"columns; dropped {dropped} row(s) listwise, so "
                f"{len(working) - dropped} complete row(s) remain. No imputation."
            )
        working = working.dropna()
        if working.shape[0] < 3:
            raise AssumptionError(
                f"After removing rows with missing values only "
                f"{working.shape[0]} complete row(s) remain; PCA needs at least "
                "three.",
                hint="Check that most rows have values in the numeric columns.",
            )

        # --- near-constant columns: zero variance contributes nothing ---------
        constant = [
            c for c in working.columns if working[c].nunique(dropna=True) <= 1
        ]
        if constant:
            ctx.log_decision(
                f"Dropping {len(constant)} near-constant column(s) "
                f"({', '.join(constant)}) that have zero variance."
            )
            result.add_warning(
                f"These column(s) contain no variation and were dropped: "
                f"{', '.join(constant)}."
            )
            result.add_expert_review(
                "Some columns were constant (no variance) and dropped. Verify "
                "they were not measurement or coding errors before reporting."
            )
            working = working.drop(columns=constant)
        if working.shape[1] < 2:
            raise AssumptionError(
                "After removing near-constant columns fewer than two usable "
                "numeric columns remain, so no PCA is possible.",
                hint="Provide data with at least two varying numeric columns.",
            )

        n_rows, n_features = working.shape
        ctx.log_decision(
            f"PCA input: {n_rows} complete row(s) x {n_features} variables."

        )

        # --- warn if variables live on wildly different scales ---------------
        stds = working.std(ddof=0)
        pos_stds = stds[stds > 0]
        if len(pos_stds) >= 2:
            ratio = float(pos_stds.max() / pos_stds.min())
            if ratio > 1000.0:
                result.add_warning(
                    "The variables span a very wide range of scales "
                    f"(largest/smallest standard deviation ≈ {ratio:.0f}). "
                    "Variables are being standardised to unit variance before "
                    "PCA so none of them dominates purely by its units."
                )
                ctx.log_decision(
                    "Scale ratio > 1000 detected; standardisation equalises "
                    "the variables before PCA."
                )

        # --- small sample: expert review below 10 rows ------------------------
        if n_rows < 10:
            result.add_expert_review(
                f"The sample is small (n = {n_rows}). Principal components and "
                "their loadings are unstable with this few observations; the "
                "result should be treated as exploratory."
            )
            ctx.log_decision(
                f"n = {n_rows} < 10; flagged sample as too small for reliable PCA."
            )

        # --- standardise (optional) and fit PCA -------------------------------
        standardize = bool(params["standardize"])
        if standardize:
            scaler = StandardScaler()
            X = scaler.fit_transform(working)
            ctx.log_decision(
                "Standardising variables (centre and unit-variance scale) "
                "before PCA."
            )
        else:
            X = working.to_numpy(dtype=float)
            ctx.log_decision(
                "standardize = false: PCA computed on the raw (unscaled) "
                "variables. High-variance variables will dominate."
            )

        k = int(min(params["n_components"], n_features))
        pca = PCA(n_components=k)
        pca.fit(X)
        ctx.log_decision(
            f"Fitted sklearn PCA with n_components = {k}; "
            f"explained_variance_ratio = "
            f"{np.round(pca.explained_variance_ratio_, 4).tolist()}."
        )

        # --- variance-explained table -----------------------------------------
        cumulative = np.cumsum(pca.explained_variance_ratio_) * 100.0
        var_rows = []
        for i in range(k):
            var_rows.append(
                {
                    "Component": f"PC{i + 1}",
                    "Eigenvalue": round(float(pca.explained_variance_[i]), 4),
                    "Variance explained (%)": round(
                        float(pca.explained_variance_ratio_[i]) * 100.0, 2
                    ),
                    "Cumulative (%)": round(float(cumulative[i]), 2),
                }
            )
        var_table = pd.DataFrame(var_rows)
        result.tables["Variance explained"] = var_table

        # --- component loadings (components_ as-is: weights of each variable) --
        loadings = pd.DataFrame(
            pca.components_.T,
            index=working.columns,
            columns=[f"PC{i + 1}" for i in range(k)],
        )
        result.tables["Component loadings"] = loadings.reset_index().rename(
            columns={"index": "Variable"}
        )

        # --- how-many-components guidance --------------------------------------
        eigen_keep = int(np.sum(pca.explained_variance_ > _EIGENVALUE_CUTOFF))
        # First index where cumulative >= target (1-based count), else all.
        over_target = int(np.argmax(cumulative >= _CUMULATIVE_TARGET)) + 1
        cum_keep = over_target if cumulative[-1] >= _CUMULATIVE_TARGET else k
        recommended = max(1, min(eigen_keep, cum_keep)) if eigen_keep > 0 else cum_keep
        ctx.log_decision(
            f"Retention guidance: {eigen_keep} component(s) pass eigenvalue > "
            f"{_EIGENVALUE_CUTOFF}; {cum_keep} reach {_CUMULATIVE_TARGET:.0f}% "
            f"cumulative variance; recommended to keep {recommended}."
        )
        result.add_verdict(
            "PASS" if eigen_keep >= 1 else "WARN",
            "components-retained",
            "Keep components until the cumulative variance reaches "
            f"{_CUMULATIVE_TARGET:.0f}% or the eigenvalue exceeds "
            f"{_EIGENVALUE_CUTOFF:.0f}; on this data that suggests keeping "
            f"{recommended} component(s).",
        )

        # --- Bartlett's test of sphericity (only if the matrix is invertible) --
        self._bartlett(result, X, n_rows, n_features, ctx)

        # --- dominant-first-component expert flag ------------------------------
        first_ratio = float(pca.explained_variance_ratio_[0])
        if first_ratio > _ONE_DOMINANT_THRESHOLD:
            result.add_expert_review(
                f"The first component explains {first_ratio * 100:.1f}% of all "
                "variance. This often means one variable dominates rather than "
                "that the variables share genuine structure; interpret with "
                "caution and inspect the loadings."
            )

        # --- figures: scree plot + score scatter --------------------------------
        scree = _scree_figure(
            var_table["Component"].astype(str).tolist(),
            var_table["Eigenvalue"].astype(float).tolist(),
            var_table["Cumulative (%)"].astype(float).tolist(),
            recommended,
        )
        result.figures.append(
            FigureItem(name="pca_scree", figure=scree, caption=(
                "Scree plot: eigenvalue per principal component with the "
                "cumulative variance explained."
            ))
        )

        scores = pca.transform(X)
        scatter = _score_scatter(
            scores,
            f"PC1 ({pca.explained_variance_ratio_[0]*100:.1f}%)",
            f"PC2 ({pca.explained_variance_ratio_[1] * 100:.1f}%)" if k >= 2 else "PC2",
            working.index,
        )
        result.figures.append(
            FigureItem(name="pca_scores", figure=scatter, caption=(
                "Score scatter of the first two principal components; each "
                "point is one observation projected onto the combined scores."
            ))
        )

        # --- summaries ----------------------------------------------------------
        kept_var = float(cumulative[recommended - 1])
        result.summaries = {
            "variables reduced": (
                f"{n_features} numeric columns → {k} principal components"
            ),
            "variance explained by PC1": f"{first_ratio * 100:.1f}%",
            "variance explained by recommended components": f"{kept_var:.1f}%",
            "recommended components to keep": str(recommended),
            "standardised before PCA": "Yes" if standardize else "No",
        }

        # --- methods sentences ---------------------------------------------------
        methods = [
            f"Principal Component Analysis reduced {n_features} numeric "
            f"variables to {k} principal component(s) "
            f"({'after standardising each to unit variance' if standardize else 'on the raw scale'}).",
            f"The first component PC1 explained {first_ratio * 100:.1f}% of the "
            f"total variance, and using the eigenvalue > "
            f"{_EIGENVALUE_CUTOFF:.0f} / cumulative "
            f"{_CUMULATIVE_TARGET:.0f}% rules the analysis suggests keeping "
            f"{recommended} component(s) for "
            f"{kept_var:.1f}% of the variance.",
            "Analyses were performed in Python with scikit-learn's PCA "
            "(sklearn.decomposition.PCA).",
        ]
        if dropped:
            methods.append(
                f"{dropped} row(s) with missing values were excluded; no "
                "missing values were imputed."
            )
        result.methods = methods

        # --- honest interpretation ----------------------------------------------
        result.what_does_not_tell = (
            "PCA is NOT factor analysis: components are linear combinations "
            "that maximise variance, not latent constructs you can name, and "
            "they are not causes of your variables. The result depends on the "
            "scaling you choose (standardising changes it), and components are "
            "computed from your own data, so they may not generalise to new "
            "samples without validation. Large loadings describe association "
            "with the combined score, not a causal link between two variables."
        )
        return result

    def _bartlett(
        self,
        result: AnalysisResult,
        X: np.ndarray,
        n_rows: int,
        n_features: int,
        ctx: RunContext,
    ) -> None:
        """Bartlett's test of sphericity on the correlation matrix.

        Tests whether the correlation matrix is close to the identity (i.e.
        whether the variables are correlated enough to reduce). Requires an
        invertible correlation matrix, so it only runs when there are more
        rows than variables; otherwise it is skipped with a logged decision.
        """
        from scipy import stats

        if n_rows <= n_features:
            ctx.log_decision(
                "Bartlett's test skipped: needs more rows than variables "
                f"(n = {n_rows} <= p = {n_features})."
            )
            return
        R = np.corrcoef(X, rowvar=False)
        sign, logdet = np.linalg.slogdet(R)
        if sign <= 0 or not np.isfinite(logdet) or logdet >= 0.0:
            ctx.log_decision(
                "Bartlett's test skipped: correlation matrix is not positive "
                "definite / is effectively the identity (no shared variance)."
            )
            return
        df = int(n_features * (n_features - 1) / 2)
        stat = -(n_rows - 1 - (2.0 * n_features + 5.0) / 6.0) * logdet
        p_value = float(stats.chi2.sf(stat, df))
        ctx.log_decision(
            f"Bartlett's test of sphericity: chi2({df}) = {stat:.4f}, "
            f"p = {p_value:.4g}."
        )
        if p_value < 0.05:
            result.add_verdict(
                "PASS",
                "sphericity",
                f"The variables are correlated enough to reduce (Bartlett's "
                f"test of sphericity, p = {self.fmt_p(p_value)} < 0.05).",
            )
        else:
            result.add_verdict(
                "WARN",
                "sphericity",
                f"The variables show little evidence of shared correlation "
                f"(Bartlett's test, p = {self.fmt_p(p_value)}); PCA may not "
                "find meaningful structure here.",
            )


def _scree_figure(
    components: list[str],
    eigenvalues: list[float],
    cumulative: list[float],
    recommended: int,
):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    x = np.arange(len(components)) + 1
    ax.bar(x, eigenvalues, color="#7fb4d8", label="Eigenvalue")
    ax.set_xticks(x)
    ax.set_xticklabels(components)
    ax.set_xlabel("Principal component")
    ax.set_ylabel("Eigenvalue")
    ax2 = ax.twinx()
    ax2.plot(x, cumulative, "o-", color="#c2574e", label="Cumulative %")
    ax2.set_ylabel("Cumulative variance explained (%)")
    if recommended:
        ax.axvline(recommended + 0.5, ls="--", color="#555", lw=1)
    ax.grid(axis="y", ls=":", alpha=0.5)
    fig.tight_layout()
    if recommended:
        ax.set_title(f"Scree plot — keep ≈ {recommended} component(s)", fontsize=10)
    else:
        ax.set_title("Scree plot", fontsize=10)
    return fig


def _score_scatter(
    scores: np.ndarray,
    xlabel: str,
    ylabel: str,
    index: pd.Index,
):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.5, 6.0))
    ax.scatter(
        scores[:, 0],
        scores[:, 1],
        s=30, alpha=0.6, color="#8fc98d", edgecolor="white", linewidth=0.4,
    )
    ax.axhline(0, color="#999", lw=0.8)
    ax.axvline(0, color="#999", lw=0.8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title("Score scatter (first two components)", fontsize=10)
    ax.grid(ls=":", alpha=0.5)
    fig.tight_layout()
    return fig


# Module-level instance the registry looks for.
ANALYSIS = PcaAnalysis()
