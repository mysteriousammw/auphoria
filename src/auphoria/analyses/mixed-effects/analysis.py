"""Linear mixed-effects model (multilevel) analysis for AUPHORIA.

Models a numeric outcome with fixed effects (a categorical predictor, e.g.
treatment) plus a random intercept per grouping unit (subject, classroom,
plot, site), so it can account for clustered, nested or repeated data where
observations within the same cluster are not independent. Estimation is done
with ``statsmodels.regression.mixed_linear_model.MixedLM`` (the permissive
statsmodels licence); the fixed-effect coefficients, standard errors, z and
p-values come straight from that fit, and the random-effect variances plus the
intraclass correlation (ICC = intercept variance / total variance) are derived
from ``model.cov_re`` and ``model.scale``.

Guardrails are enforced here, not in the front end:
- the outcome is confirmed numeric (refusing if it contains non-numeric text);
- the group (fixed-effect predictor) must have two or more categories;
- the cluster (random grouping id) must have two or more distinct units, and
  every cluster must contain at least two observations (a one-row cluster
  carries no within-cluster information and is refused);
- missing values are counted and excluded listwise with a warning, never
  imputed;
- few clusters (< 5) and small clusters warn; total n below ~30, fewer than 5
  clusters, severe cluster imbalance or a convergence warning all flag a
  "needs expert review" notice through result.add_expert_review.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError

#: Small colour palette for the boxplot figure (cycled if more groups).
_PALETTE = ["#7fb4d8", "#8fc98d", "#e8a87c", "#d98c8c", "#b48cd9", "#8cd9c9"]

#: Fewer than this many clusters -> the variance components are too unreliable
#: to interpret on their own; flag a expert-review notice.
_MIN_CLUSTERS_EXPERT = 5
#: Fewer than this many total rows -> flag a expert-review notice.
_MIN_TOTAL_EXPERT = 30
#: A cluster size below this warrants a warn-level verdict about imbalance.
_MIN_CLUSTER_SIZE = 2


def _p_expr(p: float) -> str:
    return ("p < 0.001" if p < 0.001 else f"p = {p:.3f}")


def _ci_str(low: float, high: float, digits: int = 2) -> str:
    return f"[{low:.{digits}f}, {high:.{digits}f}]"


def _icc(var_between: float, var_within: float) -> float:
    total = var_between + var_within
    return np.nan if total <= 0 else var_between / total


class MixedEffectsAnalysis(Analysis):
    id = "mixed-effects"
    name = "Linear Mixed-Effects Model"

    def check_fit(
        self,
        profile: Any,
        params: dict[str, Any],
        inputs: dict[str, str],
    ) -> list[str]:
        del params
        refusals: list[str] = []
        # Confirm the group column, if we can see it, is categorical.
        group_col = inputs.get("group")
        if group_col is not None:
            col = profile.by_name(group_col)
            if col is not None and col.kind not in ("categorical", "text"):
                refusals.append(
                    f"'{group_col}' looks like a {col.kind} column, not a group. "
                    "The fixed-effect predictor needs a categorical column with "
                    "two or more categories (e.g. treatment A / B)."
                )
        return refusals

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        result = AnalysisResult()
        outcome_col = inputs["outcome"]
        group_col = inputs["group"]
        cluster_col = inputs["cluster"]

        for name in (outcome_col, group_col, cluster_col):
            if name not in data.columns:
                raise AssumptionError(
                    f"The data has no column named '{name}'.",
                    hint="Pick the columns from your file: an outcome, a group, "
                         "and a cluster id.",
                )

        # Numeric guarantee on the outcome (refuses non-numeric text cells).
        outcome = self.ensure_numeric(data[outcome_col], outcome_col)
        ctx.log_decision(
            f"Outcome '{outcome_col}' treated as numeric; "
            f"{self.count_missing(outcome, outcome_col)} missing value(s)."
        )

        group_raw = data[group_col]
        cluster_raw = data[cluster_col]
        self.describe_missing(group_raw, group_col, ctx)
        self.describe_missing(cluster_raw, cluster_col, ctx)

        # Combine and drop rows missing ANY of the three columns (listwise),
        # with a warning; never impute.
        both = pd.DataFrame(
            {outcome_col: outcome, group_col: group_raw, cluster_col: cluster_raw}
        )
        dropped = int(both.isna().any(axis=1).sum())
        both = both.dropna()
        if dropped:
            result.add_warning(
                f"{dropped} row(s) had a missing value in '{outcome_col}', "
                f"'{group_col}' or '{cluster_col}' and were left out of this "
                "analysis. They were counted, not changed or replaced."
            )
            ctx.log_decision(
                f"Excluded {dropped} row(s) with missing values (listwise); "
                f"{len(both)} row(s) remain for the analysis."
            )

        if both.empty:
            raise AssumptionError(
                "After removing rows with missing values there were no complete "
                "rows left to analyse.",
                hint="Check that your outcome, group and cluster columns have "
                     "actual values.",
            )

        # --- group (fixed-effect predictor) must have >= 2 categories
        groups = sorted(both[group_col].dropna().unique().tolist())
        if len(groups) < 2:
            raise AssumptionError(
                f"The group column '{group_col}' has only {len(groups)} distinct "
                f"categor{'y' if len(groups) == 1 else 'ies'}, so the fixed-effect "
                "predictor cannot be estimated. A mixed model needs at least two "
                "group categories.",
                hint="Choose a group column with two or more categories.",
            )

        # --- cluster (random grouping id) must have >= 2 distinct units and
        #     every cluster must have >= 2 rows (else no within-cluster variance)
        clusters = sorted(both[cluster_col].dropna().unique().tolist())
        if len(clusters) < 2:
            raise AssumptionError(
                f"The cluster column '{cluster_col}' has only {len(clusters)} "
                "distinct unit(s), so there is no grouping to model as a random "
                "effect.",
                hint="Choose a cluster id column with two or more distinct units "
                     "(e.g. subject, classroom, plot, site).",
            )
        cluster_sizes = {
            str(c): int((both[cluster_col] == c).sum()) for c in clusters
        }
        tiny = {c: n for c, n in cluster_sizes.items() if n < _MIN_CLUSTER_SIZE}
        if tiny:
            first = ", ".join(f"'{c}' (n = {n})" for c, n in list(tiny.items())[:5])
            raise AssumptionError(
                "Every cluster needs at least two observations so that a "
                f"within-cluster variance can be estimated. These clusters are "
                f"too small: {first}.",
                hint="Use a cluster id where each unit has two or more rows, or "
                     "drop the single-observation units if that is sensible for "
                     "your design.",
            )

        alpha = float(params["alpha"])
        ctx.log_decision(
            f"Running a linear mixed model (alpha = {alpha:.3f}): outcome "
            f"'{outcome_col}' ~ 1 + '{group_col}' with a random intercept per "
            f"'{cluster_col}' ({len(clusters)} clusters, {len(both)} rows)."
        )

        # --- cluster / sample-size checks (verdicts + expert-review notices)
        # Total sample size.
        result.add_verdict(
            "PASS" if len(both) >= _MIN_TOTAL_EXPERT else "WARN",
            "sample-size",
            (f"Total sample size is {len(both)} (rule of thumb: ~30+). "
             "Fewer than that makes the variance components uncertain.")
            if len(both) < _MIN_TOTAL_EXPERT
            else f"Total sample size is {len(both)}.",
        )
        if len(both) < _MIN_TOTAL_EXPERT:
            result.add_expert_review(
                f"The total sample size is only {len(both)} (below ~30). The "
                "random-effect variances and ICC are very uncertain with so few "
                "observations; please have a statistician review this result."
            )
        # Number of clusters.
        result.add_verdict(
            "PASS" if len(clusters) >= _MIN_CLUSTERS_EXPERT else "WARN",
            "number-of-clusters",
            (f"The model has only {len(clusters)} clusters (fewer than 5). "
             "The between-cluster variance and ICC are poorly determined.")
            if len(clusters) < _MIN_CLUSTERS_EXPERT
            else f"The model has {len(clusters)} clusters.",
        )
        if len(clusters) < _MIN_CLUSTERS_EXPERT:
            result.add_expert_review(
                f"The model has only {len(clusters)} clusters (fewer than 5). "
                "Estimation of the random-intercept variance relies on having "
                "enough clusters; please have a statistician review this result."
            )
        # Warning on any cluster smaller than a comfortable size.
        for c in sorted(cluster_sizes, key=lambda k: cluster_sizes[k]):
            n = cluster_sizes[c]
            if n < 5:
                result.add_warning(
                    f"Cluster '{c}' is small (n = {n}). A small cluster has "
                    "little within-cluster information, so its influence on the "
                    "random-intercept variance is limited."
                )
                ctx.log_decision(
                    f"Cluster '{c}' has fewer than 5 observations ({n}); added "
                    "a small-cluster warning."
                )
        # Severe cluster imbalance -> expert review.
        sizes = np.asarray(list(cluster_sizes.values()), dtype=float)
        if len(sizes) >= 2:
            max_size = float(sizes.max())
            if max_size > 0:
                ratio = float(sizes.min() / max_size)
                ctx.log_decision(
                    f"Cluster sizes range {sizes.min():.0f}..{max_size:.0f} "
                    f"(smallest/largest = {ratio:.3f})."
                )
                if ratio < 0.2:
                    result.add_expert_review(
                        f"Cluster sizes are severely imbalanced (smallest is "
                        f"{ratio:.2f}x the largest). The random-intercept "
                        "variance estimate may be dominated by the larger "
                        "clusters; please have a statistician review this result."
                    )

        # --- fit the linear mixed model (REML) with statsmodels MixedLM
        import statsmodels.formula.api as smf

        # Reference-level coding: statsmodels uses patsy, which sets the first
        # category as the reference level. We use '1 + C(group)' so the
        # coefficient table gives one row per non-reference level plus the
        # (grand) intercept.
        formula = f"{outcome_col} ~ 1 + C({group_col})"
        try:
            model = smf.mixedlm(
                formula, both, groups=both[cluster_col], re_formula="1"
            )
            fit = model.fit(reml=True)
        except Exception as exc:  # noqa: BLE001 - surface a plain-English refusal
            raise AssumptionError(
                "The mixed model could not be fitted on this data.",
                hint="Check for constant predictor columns, a single cluster, "
                     "or severe imbalance; the traceback is in the log.",
            ) from exc

        convergence_ok = bool(getattr(fit, "converged", True))
        if not convergence_ok:
            result.add_expert_review(
                "The optimizer reported a convergence problem. The variance "
                "components may not be reliable; please have a statistician "
                "review this result."
            )
            result.add_verdict(
                "WARN", "convergence",
                "The mixed-model optimizer did not fully converge; treat the "
                "variance components as approximate.",
            )
        else:
            result.add_verdict(
                "PASS", "convergence",
                "The mixed-model optimizer converged.",
            )

        param_names = fit.params.index.tolist()
        # The intercept name is 'Intercept' in statsmodels 0.14+ (was 'Group
        # Var Intercept' pre-0.14 is only for the random part; the fixed part
        # intercept is always 'Intercept' in mixedlm results here).
        intercept_names = [p for p in param_names if p == "Intercept"]
        intercept_name = intercept_names[0] if intercept_names else param_names[0]

        # --- fixed-effect coefficients with CI and p
        b = fit.params
        se = fit.bse
        z = fit.tvalues
        p = fit.pvalues
        ci_low = fit.conf_int(alpha=alpha)[0]
        ci_high = fit.conf_int(alpha=alpha)[1]

        coef_rows = []
        for param in param_names:
            is_intercept = param == intercept_name
            label = "Intercept" if is_intercept else param
            coef_rows.append(
                {
                    "Term": label,
                    "Coefficient": round(float(b[param]), 4),
                    "SE": round(float(se[param]), 4),
                    "95% CI": _ci_str(float(ci_low[param]), float(ci_high[param])),
                    "z": round(float(z[param]), 3),
                    "p": float(p[param]),
                }
            )
        coef_table = pd.DataFrame(coef_rows)
        coef_table["significant at alpha?"] = coef_table["p"].apply(
            lambda pp: "Yes" if pp < alpha else "No"
        )
        result.tables["Fixed effects"] = coef_table

        # --- random-effect variance + ICC
        # For a random-intercept model cov_re is a single scalar (the
        # between-cluster variance of intercepts); scale is the residual
        # (within-cluster) variance.
        var_intercept = float(np.diag(fit.cov_re)[0])
        var_residual = float(fit.scale)
        icc = _icc(var_intercept, var_residual)
        var_table = pd.DataFrame(
            {
                "Effect": ["Random intercept (between clusters)", "Residual (within clusters)"],
                "Variance": [
                    round(var_intercept, 4),
                    round(var_residual, 4),
                ],
            }
        )
        result.tables["Random effects (variance components)"] = var_table
        icc_table = pd.DataFrame(
            {
                "Measure": ["Intraclass correlation (ICC)"],
                "Value": [round(icc, 4) if not np.isnan(icc) else "NA"],
                "Interpretation": [
                    "fraction of total outcome variation between clusters"
                ],
            }
        )
        result.tables["Intraclass correlation"] = icc_table
        ctx.log_decision(
            f"Mixed model fitted: var_intercept = {var_intercept:.4f}, "
            f"var_residual = {var_residual:.4f}, ICC = "
            f"{icc if np.isnan(icc) else round(icc, 4)}."
        )

        # --- expert-review notice for a tiny ICC-relevant design warning
        if len(clusters) < _MIN_CLUSTERS_EXPERT:
            result.add_warning(
                f"The model has only {len(clusters)} clusters. The ICC is very "
                "uncertain with so few clusters — interpret it cautiously."
            )

        # --- figure: boxplot of outcome by group (side by side)
        fig, caption = _boxplot(
            both, outcome_col, group_col, groups, var_intercept, var_residual, icc
        )
        result.figures.append(
            FigureItem(name="mixed_effects_boxplot", figure=fig, caption=caption)
        )

        # --- summaries (plain-English highlights)
        significant_levels = [
            r["Term"] for _, r in coef_table.iterrows()
            if r["Term"] != "Intercept" and r["significant at alpha?"] == "Yes"
        ]
        result.summaries = {
            "model": f"outcome ~ 1 + {group_col}, random intercept per {cluster_col}",
            "number of clusters": str(len(clusters)),
            "total observations": str(len(both)),
            "fixed-effect predictor": group_col,
            "intraclass correlation (ICC)": (
                "NA" if np.isnan(icc)
                else f"{icc:.3f} ({int(round(icc * 100))}% of variation is "
                     f"between {cluster_col} units)"
            ),
            "significant at alpha": (
                f"{alpha:.3f} → "
                + (", ".join(significant_levels) if significant_levels else "no fixed-effect level")
            ),
        }

        # --- methods.txt sentences (2-3+)
        icc_str = "NA" if np.isnan(icc) else f"{icc:.3f}"
        methods = [
            f"A linear mixed-effects model regressed '{outcome_col}' on the "
            f"fixed effect '{group_col}' (categorical) at a significance level "
            f"of alpha = {alpha:.3f}, with a random intercept per "
            f"'{cluster_col}' unit ({len(clusters)} clusters), estimated by "
            "restricted maximum likelihood (statsmodels MixedLM).",
            f"The model estimated var_intercept = {var_intercept:.4f} and "
            f"var_residual = {var_residual:.4f}, giving an intraclass "
            f"correlation of ICC = {icc_str}.",
        ]
        for _, r in coef_table.iterrows():
            if r["Term"] == "Intercept":
                continue
            methods.append(
                f"Relative to the reference {group_col} level, the coefficient "
                f"for {r['Term']} was {r['Coefficient']:.4f} (SE {r['SE']:.4f}, "
                f"z = {r['z']:.3f}, p = {self.fmt_p(float(r['p']))})."
            )
        if dropped:
            methods.append(
                f"{dropped} row(s) with missing values in these columns were "
                "excluded listwise; no missing values were imputed."
            )
        result.methods = methods

        # --- honest interpretation
        result.what_does_not_tell = (
            "A linear mixed model does not prove that the fixed-effect "
            "predictor caused the difference in the outcome — it only models "
            "association, and unmeasured confounders could explain the effect. "
            "The random intercept assumes within-cluster residuals are "
            "exchangeable given the model; if observations within a cluster are "
            "ordered over time, an autocorrelation structure would be needed. "
            "And the coefficient on a level-1 (within-cluster) predictor is not "
            "a level-2 (between-cluster) effect — interpreting one as the other "
            "is the ecological fallacy."
        )
        return result


def _boxplot(
    df: pd.DataFrame,
    outcome_col: str,
    group_col: str,
    groups: list[Any],
    var_intercept: float,
    var_residual: float,
    icc: float,
):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    data = [
        df.loc[df[group_col] == g, outcome_col].to_numpy(dtype=float)
        for g in groups
    ]
    bp = ax.boxplot(data, patch_artist=True, widths=0.55)
    # Set the category labels (avoids the matplotlib labels/tick_labels rename
    # that changed across 3.8/3.9, so we stay compatible with 3.7-3.12).
    ax.set_xticks(range(1, len(groups) + 1), [str(g) for g in groups])
    colours = [_PALETTE[i % len(_PALETTE)] for i in range(len(groups))]
    for patch, color in zip(bp["boxes"], colours, strict=False):
        patch.set_facecolor(color)
    rng = np.random.default_rng(0)
    for i, arr in enumerate(data, start=1):
        if len(arr):
            ax.scatter(
                np.full_like(arr, i) + rng.uniform(-0.08, 0.08, len(arr)),
                arr, alpha=0.5, s=18, color="#333", edgecolor="white", linewidth=0.4,
            )
    icc_str = "NA" if np.isnan(icc) else f"{icc:.3f}"
    ax.set_title(
        f"{outcome_col} by {group_col}\n"
        f"var_between = {var_intercept:.2f}, var_within = {var_residual:.2f}, "
        f"ICC = {icc_str}",
        fontsize=10,
    )
    ax.set_ylabel(outcome_col)
    ax.grid(axis="y", ls=":", alpha=0.5)
    fig.tight_layout()
    caption = (
        f"Distribution of '{outcome_col}' by '{group_col}' "
        f"(ICC = {icc_str})"
    )
    return fig, caption


# Module-level instance the registry looks for.
ANALYSIS = MixedEffectsAnalysis()
