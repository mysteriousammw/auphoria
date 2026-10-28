"""K-Means clustering analysis for AUPHORIA.

Groups observations into ``k`` clusters using scikit-learn's
``sklearn.cluster.KMeans`` on **all** numeric columns. This is an
unsupervised technique — there is no outcome to predict; the goal is to
expose structure (groups) the data may already contain.

Because k-means is distance-based, every numeric column is standardised
to zero mean / unit variance (StandardScaler) before clustering by
default, so a variable with a large scale (e.g. income in thousands) does
not silently dominate a variable with a small scale (e.g. a 0-1 rating).
The user must *expect or seek* clusters: k-means will always produce ``k``
groups even from pure noise, so the quality checks (silhouette score, the
elbow comparison, and the width of the individual silhouette widths) are
the honest signal of whether the clusters mean anything.

Guardrails are enforced here, not in the front end:
- the analysis requires at least TWO numeric columns (refused otherwise)
  and uses every numeric column automatically;
- there must be more rows than clusters (k > n_rows is refused);
- missing numeric values are counted and excluded listwise with a warning,
  never imputed;
- a small sample (fewer than about 10*k rows) and a weak silhouette
  (< 0.25) are WARNED about and, along with near-constant columns, flagged
  for expert review through :meth:`AnalysisResult.add_expert_review`.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_samples, silhouette_score
from sklearn.preprocessing import StandardScaler

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError

#: Weak-cluster-structure threshold; this is a widely used rule of thumb.
#: 0.25-0.50 = weak/no real structure, 0.50-0.70 = reasonable, >0.70 =
#: strong. Below 0.25 the clusters are barely distinguishable from noise.
_WEAK_SILHOUETTE = 0.25
#: Rule of thumb: at least ~10 rows per cluster for stable centres.
_MIN_ROWS_PER_CLUSTER = 10
#: How many representative columns to preview in the assignments table.
_PREVIEW_COLS = 3


class ClusteringKmeansAnalysis(Analysis):
    id = "clustering-kmeans"
    name = "K-Means Clustering"

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        del inputs
        result = AnalysisResult()

        if data is None or data.empty:
            raise AssumptionError(
                "The data is empty, so there are no observations to cluster.",
                hint="Provide a file with at least a few rows of data.",
            )

        # --- use EVERY numeric column (this analysis has no input choice)
        numeric_cols = [
            col
            for col in data.columns
            if pd.api.types.is_numeric_dtype(data[col])
        ]
        ctx.log_decision(
            f"Found {len(numeric_cols)} numeric column(s): "
            f"{', '.join(map(str, numeric_cols)) or '(none)'}."
        )
        if len(numeric_cols) < 2:
            raise AssumptionError(
                f"K-means needs at least two numeric columns to form clusters, "
                f"but the data has only {len(numeric_cols)} "
                f"({'none' if not numeric_cols else str(numeric_cols[0])}).",
                hint=(
                    "Cluster distances need at least two numeric variables. "
                    "Add a numeric column or use a different analysis."
                ),
            )

        k = int(params["k"])
        standardize = bool(params["standardize"])
        random_state = int(params["random_state"])
        if k < 1:
            raise AssumptionError(
                f"The number of clusters k must be at least 1, got {k}.",
                hint="Choose a k of 1 or more (2 or more for a silhouette).",
            )

        subset = data[numeric_cols].copy()
        # --- handle missing values: count and drop listwise, never impute
        total_missing = int(subset.isna().sum().sum())
        ctx.log_decision(
            f"{total_missing} missing value(s) across the numeric columns "
            f"(row count before drop: {len(data)})."
        )
        rows_before = len(subset)
        complete = subset.dropna()
        dropped = rows_before - len(complete)
        if dropped:
            result.add_warning(
                f"{dropped} row(s) had a missing value in a numeric column and "
                "were left out of the clustering. They were counted, not "
                "changed or replaced — missing values are never imputed."
            )
            ctx.log_decision(
                f"Excluded {dropped} row(s) with missing numeric values "
                f"(listwise); {len(complete)} row(s) clusterable."
            )
        n_rows = len(complete)
        if n_rows == 0:
            raise AssumptionError(
                "After removing rows with missing numeric values there were no "
                "rows left to cluster.",
                hint="Check that your numeric columns have actual values.",
            )

        # --- we cannot have more clusters than points
        if k > n_rows:
            raise AssumptionError(
                f"You asked for k = {k} clusters but only {n_rows} row(s) are "
                f"left after dropping missing values — you cannot have more "
                "clusters than points.",
                hint=f"Lower k to at most {n_rows}, or add more data.",
            )
        ctx.log_decision(
            f"Clustering {n_rows} row(s) across {len(numeric_cols)} numeric "
            f"column(s) into k = {k} clusters "
            f"(standardize = {standardize}, random_state = {random_state})."
        )

        # --- near-constant column check (a constant column adds no signal)
        X = complete.to_numpy(dtype=float)
        constant_cols: list[str] = []
        for i, col in enumerate(numeric_cols):
            lo, hi = float(np.min(X[:, i])), float(np.max(X[:, i]))
            if np.isclose(lo, hi):
                constant_cols.append(str(col))
        if constant_cols:
            ctx.log_decision(
                f"Constant column(s) found (no variance): "
                f"{', '.join(constant_cols)}; they contribute no clustering "
                "signal."
            )

        # --- standardise (scaled to equal units) before clustering
        scaler = StandardScaler()
        if standardize:
            X_scaled = scaler.fit_transform(X)
            ctx.log_decision(
                "Standardised all numeric columns (zero mean, unit variance) "
                "so variables are on equal units before clustering."
            )
        else:
            X_scaled = X
            ctx.log_decision(
                "standardize = false: clustering on the raw (unscaled) "
                "columns, so variable scale will dominate the distance."
            )

        # --- k-means
        km = KMeans(n_clusters=k, n_init=10, random_state=random_state)
        labels = km.fit_predict(X_scaled)
        labels_arr = np.asarray(labels, dtype=int)
        ctx.log_decision(
            f"KMeans converged in {km.n_iter_} iteration(s) with inertia "
            f"{km.inertia_:.4f}."
        )

        # --- quality checks
        silhouette = float("nan")
        if k >= 2 and n_rows > k and n_rows > 1:
            try:
                silhouette = float(silhouette_score(X_scaled, labels_arr))
            except ValueError:
                silhouette = float("nan")
        # --- sample-size check (minimum ~10 rows per cluster)
        small_sample = n_rows < _MIN_ROWS_PER_CLUSTER * k
        weak_structure = np.isfinite(silhouette) and silhouette < _WEAK_SILHOUETTE
        ctx.log_decision(
            f"Silhouette score = {silhouette:.4f} ({'weak' if weak_structure else 'ok'}); "
            f"n_rows = {n_rows} vs 10*k = {10 * k} "
            f"({'small' if small_sample else 'adequate'})."
        )
        if small_sample:
            result.add_warning(
                f"Only {n_rows} row(s) for k = {k} clusters (that is fewer than "
                f"about {_MIN_ROWS_PER_CLUSTER} rows per cluster). The cluster "
                "centres may be unstable — treat the grouping as preliminary."
            )
            ctx.log_decision(
                f"Small sample for k = {k}: fewer than 10 rows per cluster "
                f"({n_rows} < {10 * k}); added a warning."
            )
        if weak_structure:
            result.add_warning(
                f"The average silhouette score is {silhouette:.3f}, below "
                f"0.25, which suggests the clusters are weak or poorly "
                "separated — the grouping may not reflect real structure."
            )
            ctx.log_decision(
                f"Silhouette {silhouette:.3f} < 0.25: cluster structure is weak."
            )
        if small_sample:
            result.add_expert_review(
                "K-means was run outside its intended conditions: fewer than "
                f"about 10 rows per cluster ({n_rows} rows for k = {k}). "
                "Cluster centres and membership may be unstable; treat the "
                "result as preliminary."
            )
        if weak_structure:
            result.add_expert_review(
                f"The average silhouette score is {silhouette:.3f} (< 0.25), "
                "so the identified clusters are weak or poorly separated. The "
                "grouping should be reviewed before it is interpreted."
            )
        if constant_cols:
            result.add_expert_review(
                f"The column(s) {', '.join(constant_cols)} are constant (no "
                "variance) and carry no clustering signal; a different "
                "cluster structure may be hidden."
            )

        # --- verdicts
        if np.isfinite(silhouette):
            result.add_verdict(
                "PASS" if not weak_structure else "WARN",
                "silhouette-quality",
                (
                    f"Average silhouette = {silhouette:.3f} "
                    "(>= 0.25 reasonable structure)."
                    if not weak_structure
                    else f"Average silhouette = {silhouette:.3f}, below 0.25, "
                    "indicating weak cluster structure."
                ),
            )
        else:
            result.add_verdict(
                "WARN", "silhouette-quality",
                "Silhouette could not be computed (needs at least two clusters "
                "and more rows than clusters).",
            )
        result.add_verdict(
            "PASS" if not small_sample else "WARN",
            "sample-size",
            (
                f"{n_rows} row(s) for k = {k} clusters "
                f"(>= {_MIN_ROWS_PER_CLUSTER} rows per cluster)."
                if not small_sample
                else f"Only {n_rows} row(s) for k = {k} clusters (< 10 per "
                "cluster) — unstable centres."
            ),
        )

        # --- cluster assignments table (row id + cluster + a few columns)
        preview_cols = [str(c) for c in numeric_cols[:_PREVIEW_COLS]]
        assignments = pd.DataFrame(
            {str(c): complete[c].to_numpy() for c in preview_cols},
            index=complete.index,
        )
        assignments.insert(0, "row", np.arange(1, n_rows + 1))
        assignments.insert(1, "cluster", labels_arr)
        result.tables["Cluster assignments"] = assignments

        # --- cluster centres (means of each variable per cluster, scaled space)
        centres = pd.DataFrame(
            km.cluster_centers_,
            columns=[str(c) for c in numeric_cols],
        )
        centres.insert(0, "cluster", np.arange(k))
        result.tables["Cluster centres"] = centres
        result.tables["Cluster sizes"] = pd.DataFrame(
            {
                "cluster": np.arange(k),
                "n": [int(np.sum(labels_arr == c)) for c in range(k)],
            }
        )

        cluster_means = pd.DataFrame(
            {
                "cluster": range(k),
                "mean scaled value": [
                    round(float(np.mean(X_scaled[labels_arr == c])), 4)
                    for c in range(k)
                ],
            }
        )
        result.tables["Cluster mean profiles"] = cluster_means

        # --- elbow guidance: inertia at k-1, k, k+1
        elbow_rows = []
        for ek in [k - 1, k, k + 1]:
            if ek >= 1 and ek <= n_rows:
                ekm = KMeans(
                    n_clusters=ek, n_init=10, random_state=random_state
                )
                ekm.fit(X_scaled)
                elbow_rows.append(
                    {"k": ek, "inertia (within-cluster sum of squares)":
                     float(ekm.inertia_)}
                )
        elbow_table = pd.DataFrame(elbow_rows)
        result.tables["Elbow guidance"] = elbow_table
        elbow_note = ""
        if len(elbow_rows) >= 2 and k in [r["k"] for r in elbow_rows]:
            inertia_by_k = {r["k"]: r["inertia (within-cluster sum of squares)"] for r in elbow_rows}
            curv = inertia_by_k.get(k - 1, 0.0) - 2 * inertia_by_k.get(k, 0.0) + inertia_by_k.get(k + 1, 0.0)
            elbow_note = (
                "Inertia falls as k grows; a large drop from k-1 to k followed "
                f"by a small drop from k to k+1 (discrete second difference "
                f"{curv:.4f}) signals k is near the 'elbow'."
            )
            result.notes.append(elbow_note)

        ctx.log_decision(
            "Elbow check: "
            + "; ".join(
                f"k={r['k']} -> inertia {r['inertia (within-cluster sum of squares)']:.4f}"
                for r in elbow_rows
            )
            + "."
        )

        # --- figures
        # 1) 2-D scatter of the first two PCs coloured by cluster
        pc_fig, pc_caption = self._pc_scatter(
            X_scaled, labels_arr, k, numeric_cols, silhouette
        )
        result.figures.append(FigureItem(name="km_pc_scatter", figure=pc_fig, caption=pc_caption))

        # 2) silhouette profile + elbow
        sil_fig, sil_caption = self._silhouette_elbow_figure(
            X_scaled, labels_arr, k, silhouette, elbow_rows
        )
        result.figures.append(FigureItem(name="km_silhouette_elbow", figure=sil_fig, caption=sil_caption))

        # --- summaries
        result.summaries = {
            "k": str(k),
            "clusters found": str(k),
            "n rows clustered": str(n_rows),
            "n numeric columns": str(len(numeric_cols)),
            "average silhouette": (
                "NA (silhouette needs k >= 2 and more rows than clusters)"
                if not np.isfinite(silhouette)
                else f"{silhouette:.4f}"
            ),
            "silhouette label": (
                "weak (< 0.25)" if weak_structure
                else ("reasonable (>= 0.25)" if np.isfinite(silhouette) else "NA")
            ),
            "elbow guidance": elbow_note.strip().split(";")[0] if elbow_note else "see Elbow guidance table",
            "cluster sizes": ", ".join(
                f"{c}: {int(np.sum(labels_arr == c))}" for c in range(k)
            ),
        }

        # --- methods sentences
        methods = [
            f"Observations were partitioned into k = {k} clusters using "
            f"k-means (sklearn.cluster.KMeans, n_init = 10, random_state = "
            f"{random_state}) applied to {len(numeric_cols)} numeric "
            f"variable(s): {', '.join(map(str, numeric_cols))}.",
            f"Before clustering, variables were standardised to zero mean and "
            f"unit variance (StandardScaler) so all variables had equal "
            "units; "
            f"the average silhouette score was "
            f"{silhouette:.3f}." if np.isfinite(silhouette) else
            "Before clustering, variables were standardised to zero mean and "
            "unit variance (StandardScaler) so all variables had equal units.",
        ]
        if dropped:
            methods.append(
                f"{dropped} row(s) with missing numeric values were excluded "
                "listwise; no missing values were imputed."
            )
        if np.isfinite(silhouette):
            methods.append(
                f"The average silhouette score of {silhouette:.3f} "
                f"({'indicates weak structure (< 0.25)' if weak_structure else 'suggests the clusters are reasonably well separated'})."
            )
        result.methods = methods

        # --- honest interpretation
        result.what_does_not_tell = (
            "K-means finds roughly spherical, equal-sized clusters: it will "
            "always form k groups even from random noise, so the clusters are "
            "descriptive groupings, not real categories or causes of anything. "
            "The result depends on scaling, the choice of k, and the random "
            "seed, and the cluster labels are arbitrary ordinals with no "
            "intrinsic meaning. Silhouette and elbow guidance are heuristics — "
            "verify with domain knowledge whether the clusters are meaningful."
        )
        return result

    # ------------------------------------------------------------- helpers
    def _pc_scatter(
        self,
        X_scaled: np.ndarray,
        labels: np.ndarray,
        k: int,
        numeric_cols: list[Any],
        silhouette: float,
    ):
        import matplotlib.pyplot as plt

        n_dims = min(2, X_scaled.shape[1])
        if n_dims == 2:
            score = X_scaled
        else:
            score = PCA(n_components=2, random_state=0).fit_transform(X_scaled)
        fig, ax = plt.subplots(figsize=(6.5, 5.0))
        cmap = plt.get_cmap("tab10")
        for c in range(k):
            m = labels == c
            ax.scatter(
                score[m, 0], score[m, 1], s=24, alpha=0.75,
                color=cmap(c % 10), edgecolor="white", linewidth=0.4,
                label=f"cluster {c}",
            )
        sil = f"{silhouette:.3f}" if np.isfinite(silhouette) else "NA"
        ax.set_title(
            f"K-means clusters (k = {k}), first two PC\nsilhouette = {sil}",
            fontsize=10,
        )
        ax.set_xlabel("PC 1")
        ax.set_ylabel("PC 2")
        ax.grid(ls=":", alpha=0.5)
        ax.legend(fontsize=8, loc="best")
        fig.tight_layout()
        caption = (
            f"Scatter of the first two principal components of the "
            f"standardised numeric columns, coloured by the k = {k} "
            f"cluster(s); average silhouette = {sil}."
        )
        return fig, caption

    def _silhouette_elbow_figure(
        self,
        X_scaled: np.ndarray,
        labels: np.ndarray,
        k: int,
        silhouette: float,
        elbow_rows: list[dict[str, Any]],
    ):
        import matplotlib.pyplot as plt

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.0, 4.5))
        # left: silhouette profile
        if np.isfinite(silhouette):
            sil_vals = silhouette_samples(X_scaled, labels)
            avg = float(np.mean(sil_vals))
            order = np.argsort(sil_vals)
            sil_vals_sorted = sil_vals[order]
            y_lower = 0.0
            for c in range(k):
                cluster_sils = sil_vals_sorted[labels[order] == c]
                if len(cluster_sils) == 0:
                    continue
                cluster_sils = np.sort(cluster_sils)
                y_upper = y_lower + len(cluster_sils)
                colour = plt.get_cmap("tab10")(c % 10)
                ax1.fill_betweenx(
                    np.arange(y_lower, y_upper), 0, cluster_sils,
                    facecolor=colour, edgecolor=colour, alpha=0.7,
                )
                ax1.text(-0.01, y_lower + 0.5 * len(cluster_sils), str(c),
                         fontsize=9)
                y_lower = y_upper
            ax1.axvline(x=avg, color="red", ls="--", lw=1.2)
            ax1.set_title(
                f"Silhouette profile (average {avg:.3f})", fontsize=10
            )
            ax1.set_xlabel("Silhouette coefficient")
            ax1.set_ylabel("Cluster label")
            ax1.set_ylim(0, y_lower)
        else:
            ax1.text(
                0.5, 0.5, "Silhouette unavailable\n(needs k >= 2 and n_rows > k)",
                ha="center", va="center", fontsize=10,
            )
            ax1.set_xticks([])
            ax1.set_yticks([])
        # right: elbow
        if elbow_rows:
            ks = [r["k"] for r in elbow_rows]
            inertias = [r["inertia (within-cluster sum of squares)"] for r in elbow_rows]
            ax2.plot(ks, inertias, "o-", color="#7fb4d8")
            ax2.axvline(x=k, color="red", ls=":", lw=1.2)
            ax2.set_title("Elbow guidance (inertia vs k)", fontsize=10)
            ax2.set_xlabel("k")
            ax2.set_ylabel("Inertia (within-cluster SS)")
            ax2.grid(ls=":", alpha=0.5)
        else:
            ax2.text(0.5, 0.5, "Elbow unavailable", ha="center", va="center")
            ax2.set_xticks([])
            ax2.set_yticks([])
        fig.tight_layout()
        return fig, (
            "Silhouette profile of the k = " + str(k) +
            " clusters (left; red dashed line = average) and inertia vs k for "
            "the elbow check (right; red dotted line marks the chosen k)."
        )

    # Module-level instance the registry looks for.
ANALYSIS = ClusteringKmeansAnalysis()

