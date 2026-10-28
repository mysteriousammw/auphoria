"""One-way ANOVA analysis for AUPHORIA.

Tests whether three or more independent groups differ in their average
numeric outcome using SciPy's `f_oneway`. The F statistic, degrees of
freedom and p-value come from SciPy; the report also shows the classic
ANOVA table (sum of squares between / within / total) built by hand so
students can see where the numbers come from, an eta-squared effect size,
and a Tukey HSD post-hoc comparison (q statistics with p-values from the
studentized range distribution, without statsmodels).

Guardrails are enforced here, not in the front end:
- the outcome is confirmed numeric (refusing if it contains non-numeric text);
- the group must have three or more categories (two groups mean the
  independent-samples t-test is the right tool, so we refuse with that hint);
- any group with a single observation is refused; small groups warn;
- missing values are counted and excluded with a warning, never imputed;
- assumption checks (Shapiro-Wilk per group, Levene's test) are RUN and
  REPORTED as WARN verdicts but never refuse the analysis.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError

#: Small colour palette for the boxplot figure (cycled if more groups).
_PALETTE = ["#7fb4d8", "#8fc98d", "#e8a87c", "#d98c8c", "#b48cd9", "#8cd9c9"]


def _eta_label(eta: float) -> str:
    """Plain-English label for eta-squared (Cohen's guidelines)."""
    if np.isnan(eta):
        return "NA"
    if eta < 0.01:
        return "negligible"
    if eta < 0.06:
        return "small"
    if eta < 0.14:
        return "medium"
    return "large"


def _p_expr(p: float) -> str:
    return f"p {_p_rel(p)} {_p_num(p)}"


def _p_num(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def _p_rel(p: float) -> str:
    return "<" if p < 0.001 else "="


def _p_rel_num(p: float, alpha: float) -> str:
    """Plain comparison operator vs a stated alpha for a methods sentence."""
    return "<" if p < alpha else ">="


def _tukey_table(
    group_names: list[Any],
    means: list[float],
    counts: list[int],
    ms_within: float,
    k: int,
    df_within: int,
    alpha: float,
) -> pd.DataFrame | None:
    """Tukey HSD post-hoc table without statsmodels.

    q = (mean_i - mean_j) / sqrt(MS_within * (1/n_i + 1/n_j) / 2) and the
    two-sided p-value is the studentized range survival function at |q|
    with k groups and df_within error degrees of freedom. Returns None if
    the studentized range distribution is unavailable.
    """
    sf = getattr(getattr(stats, "studentized_range", None), "sf", None)
    if sf is None:
        return None
    rows = []
    for i in range(k):
        for j in range(i + 1, k):
            denom = np.sqrt(ms_within * (1.0 / counts[i] + 1.0 / counts[j]) / 2.0)
            q = float((means[i] - means[j]) / denom) if denom > 0 else float("nan")
            p = float(sf(abs(q), k, df_within)) if not np.isnan(q) else float("nan")
            rows.append(
                {
                    "Pair": f"{group_names[i]} vs {group_names[j]}",
                    "Mean difference": round(means[i] - means[j], 4),
                    "q": round(abs(q), 6),
                    "p (Tukey)": p,
                    "significant at alpha?": "Yes" if p < alpha else "No",
                }
            )
    return pd.DataFrame(rows)


class AnovaOnewayAnalysis(Analysis):
    id = "anova-oneway"
    name = "One-Way ANOVA"

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
                    "One-way ANOVA needs a grouping column with three or more "
                    "categories (e.g. treatment A / B / C)."
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

        if outcome_col not in data.columns:
            raise AssumptionError(
                f"The data has no column named '{outcome_col}'.",
                hint="Pick an outcome column from your file.",
            )
        if group_col not in data.columns:
            raise AssumptionError(
                f"The data has no column named '{group_col}'.",
                hint="Pick a group column from your file.",
            )

        # Numeric guarantee on the outcome (refuses non-numeric text cells).
        outcome = self.ensure_numeric(data[outcome_col], outcome_col)
        ctx.log_decision(
            f"Outcome '{outcome_col}' treated as numeric; "
            f"{self.count_missing(outcome, outcome_col)} missing value(s)."
        )

        group_raw = data[group_col]
        self.describe_missing(group_raw, group_col, ctx)

        # Combine and drop rows missing EITHER outcome or group, with a warning.
        both = pd.DataFrame({outcome_col: outcome, group_col: group_raw})
        dropped = int(both.isna().any(axis=1).sum())
        both = both.dropna()
        if dropped:
            result.add_warning(
                f"{dropped} row(s) had a missing value in '{outcome_col}' or "
                f"'{group_col}' and were left out of this analysis. They were "
                "counted, not changed or replaced."
            )
            ctx.log_decision(
                f"Excluded {dropped} row(s) with missing outcome/group (listwise); "
                f"{len(both)} row(s) remain for the analysis."
            )

        if both.empty:
            raise AssumptionError(
                "After removing rows with missing values there were no complete "
                "rows left to analyse.",
                hint="Check that your outcome and group columns have actual values.",
            )

        groups = sorted(both[group_col].dropna().unique().tolist())
        if len(groups) < 3:
            raise AssumptionError(
                f"The group column '{group_col}' has only {len(groups)} distinct "
                f"categor{'y' if len(groups) == 1 else 'ies'}, so a three-or-more "
                "group comparison is impossible. With exactly two groups, use the "
                "independent-samples t-test instead.",
                hint="Choose a group column with three or more categories (or run "
                     "the t-test for a two-group comparison).",
            )

        alpha = float(params["alpha"])
        ctx.log_decision(
            f"Running one-way ANOVA (alpha = {alpha:.3f}) on '{outcome_col}' by "
            f"'{group_col}' with {len(groups)} groups: "
            f"{', '.join(map(str, groups))}."
        )

        group_arrays: list[np.ndarray] = []
        group_names: list[Any] = []
        group_counts: list[int] = []
        for g in groups:
            arr = both.loc[both[group_col] == g, outcome_col].to_numpy(dtype=float)
            group_arrays.append(arr)
            group_names.append(g)
            group_counts.append(len(arr))
            if len(arr) < 2:
                raise AssumptionError(
                    "Each group needs at least two observations.",
                    hint=f"Group '{g}' has {len(arr)} observation(s). Add data or "
                         "choose another grouping.",
                )
        for g, n in zip(group_names, group_counts, strict=False):
            if n < 5:
                result.add_warning(
                    f"Group '{g}' is small (n = {n}). ANOVA still runs, but the "
                    "result is sensitive to the normality assumption and to "
                    "unequal variances — treat it as preliminary."
                )
                ctx.log_decision(
                    f"Group '{g}' has fewer than 5 observations ({n}); added a "
                    "small-group warning."
                )

        # --- assumption checks: RUN and REPORT, never refuse
        levene_stat, levene_p = stats.levene(*group_arrays)
        ctx.log_decision(
            f"Levene's test for equal variances: W = {levene_stat:.4f}, "
            f"p = {levene_p:.4g} (alpha = {alpha:.3f})."
        )
        if levene_p < alpha:
            result.add_verdict(
                "WARN", "equal-variances",
                "The group variances are significantly unequal (Levene's test, "
                f"p = {self.fmt_p(levene_p)} < alpha = {alpha:.3f}). ANOVA is still "
                "reported but the equal-variance assumption is violated.",
            )
            result.add_warning(
                "Levene's test found significantly unequal group variances. "
                "Consider the Kruskal-Wallis test instead, which does not assume "
                "equal variances or normality."
            )
        else:
            result.add_verdict(
                "PASS", "equal-variances",
                f"No evidence of unequal group variances (Levene's test, "
                f"p = {self.fmt_p(levene_p)} vs alpha = {alpha:.3f}).",
            )

        normality_warned = False
        for g, arr in zip(group_names, group_arrays, strict=False):
            n = len(arr)
            if not (3 <= n <= 5000):
                ctx.log_decision(
                    f"Shapiro-Wilk skipped for group '{g}' "
                    f"(n = {n}; needs 3..5000 observations)."
                )
                continue
            if np.ptp(arr) == 0:
                ctx.log_decision(
                    f"Shapiro-Wilk skipped for group '{g}': the group is "
                    "constant (all values identical), so normality is moot."
                )
                continue
            w_stat, w_p = stats.shapiro(arr)
            if np.isnan(w_stat) or np.isnan(w_p):
                ctx.log_decision(
                    f"Shapiro-Wilk for group '{g}' returned no usable p-value "
                    f"(W = {w_stat}); skipped."
                )
                continue
            ctx.log_decision(
                f"Shapiro-Wilk normality check for group '{g}': "
                f"W = {w_stat:.4f}, p = {w_p:.4g} (alpha = {alpha:.3f})."
            )
            if w_p < alpha:
                normality_warned = True
                result.add_verdict(
                    "WARN", "normality",
                    f"Group '{g}' deviates from a normal distribution "
                    f"(Shapiro-Wilk, p = {self.fmt_p(w_p)} < alpha = {alpha:.3f}). "
                    "ANOVA is still reported but the normality assumption is "
                    "violated for this group.",
                )
            else:
                result.add_verdict(
                    "PASS", "normality",
                    f"Group '{g}' is roughly normally distributed "
                    f"(Shapiro-Wilk, p = {self.fmt_p(w_p)}).",
                )
        if normality_warned:
            result.add_warning(
                "Shapiro-Wilk found at least one group that deviates from a normal "
                "distribution. Consider the Kruskal-Wallis test, which does not "
                "assume normality."
            )

        # --- compute: F from SciPy, ANOVA table built by hand
        F_stat, p_val = stats.f_oneway(*group_arrays)
        k = len(groups)
        n_total = int(sum(group_counts))
        df_between = k - 1
        df_within = n_total - k
        grand_mean = float(np.concatenate(group_arrays).mean())
        means = [float(arr.mean()) for arr in group_arrays]
        ss_between = float(
            sum(n_i * (m_i - grand_mean) ** 2 for n_i, m_i in zip(group_counts, means, strict=False))
        )
        ss_within = float(
            sum(float(((arr - m_i) ** 2).sum()) for arr, m_i in zip(group_arrays, means, strict=False))
        )
        ss_total = ss_between + ss_within
        ms_between = ss_between / df_between if df_between > 0 else float("nan")
        ms_within = ss_within / df_within if df_within > 0 else float("nan")
        eta_squared = ss_between / ss_total if ss_total > 0 else float("nan")
        significant = bool(p_val < alpha)
        ctx.log_decision(
            f"f_oneway: F = {F_stat:.4f}, p = {p_val:.4g}; df_between = "
            f"{df_between}, df_within = {df_within}. Hand-built SS: between = "
            f"{ss_between:.4f}, within = {ss_within:.4f}, total = {ss_total:.4f}; "
            f"eta-squared = {eta_squared:.4f}."
        )

        # --- tables
        group_stats = pd.DataFrame(
            {
                "Group": group_names,
                "n": group_counts,
                "Mean": [round(m, 4) for m in means],
                "SD": [round(float(arr.std(ddof=1)), 4) for arr in group_arrays],
            }
        )
        anova_table = pd.DataFrame(
            {
                "Source": ["Between", "Within", "Total"],
                "SS": [ss_between, ss_within, ss_total],
                "df": [df_between, df_within, n_total - 1],
                "MS": [ms_between, ms_within, ""],
                "F": [F_stat, "", ""],
                "p": [p_val, "", ""],
            }
        )
        effect_size = pd.DataFrame(
            {
                "Measure": [
                    "eta-squared (SS_between / SS_total)",
                    "effect size label",
                ],
                "Value": [
                    round(eta_squared, 6),
                    _eta_label(eta_squared),
                ],
            }
        )
        result.tables["Group statistics"] = group_stats
        result.tables["ANOVA table"] = anova_table
        result.tables["Effect size"] = effect_size

        tukey = _tukey_table(
            group_names, means, group_counts, ms_within, k, df_within, alpha
        )
        if tukey is None:
            result.notes.append(
                "Tukey post-hoc could not be computed because the studentized "
                "range distribution is unavailable in this SciPy version; only "
                "the overall ANOVA result is reported."
            )
            ctx.log_decision(
                "Tukey post-hoc skipped: scipy.stats.studentized_range unavailable."
            )
        else:
            result.tables["Tukey post-hoc"] = tukey
            ctx.log_decision(
                f"Tukey HSD post-hoc computed for {len(tukey)} group pairs "
                f"(q from MS_within = {ms_within:.4f}, df_within = {df_within})."
            )

        # --- figure (side-by-side boxplots, one per group)
        fig, caption = _boxplot(
            both, outcome_col, group_col, group_names, F_stat, p_val, alpha
        )
        result.figures.append(
            FigureItem(name="anova_boxplots", figure=fig, caption=caption)
        )

        # --- summaries (plain-English highlights)
        result.summaries = {
            "F": f"F({df_between}, {df_within}) = {F_stat:.2f}",
            "degrees of freedom": f"({df_between}, {df_within})",
            "p-value": self.fmt_p(p_val),
            "effect size (eta-squared)": (
                "NA" if np.isnan(eta_squared)
                else f"{eta_squared:.3f} ({_eta_label(eta_squared)})"
            ),
            "significant at alpha": (
                f"{alpha:.3f} → {'Yes' if significant else 'No'}"
            ),
            "most different groups": _most_different_hint(
                tukey, group_names, means, significant
            ),
        }

        # --- methods.txt sentences (2-3)
        methods = [
            f"A one-way ANOVA compared '{outcome_col}' across {k} independent "
            f"groups ({', '.join(map(str, group_names))}), at a significance "
            f"level of alpha = {alpha:.3f}.",
            f"The test gave F({df_between}, {df_within}) = {F_stat:.2f}, "
            f"{_p_expr(p_val)}, with an effect size of eta-squared = "
            f"{eta_squared:.3f} ({_eta_label(eta_squared)}).",
        ]
        if tukey is not None and not tukey.empty:
            sig_pairs = tukey.loc[tukey["significant at alpha?"] == "Yes", "Pair"]
            if len(sig_pairs):
                methods.append(
                    "A Tukey post-hoc comparison (studentized range) showed the "
                    "following pairs differ at alpha = "
                    f"{alpha:.3f}: {', '.join(map(str, sig_pairs.tolist()))}."
                )
            else:
                methods.append(
                    "A Tukey post-hoc comparison found no pair of groups that "
                    "differed at alpha = "
                    f"{alpha:.3f}."
                )
        if dropped:
            methods.append(
                f"{dropped} row(s) with missing values in these columns were "
                "excluded; no missing values were imputed."
            )
        result.methods = methods

        if not significant:
            result.notes.append(
                "The overall F test was not significant, so the group averages "
                "cannot be shown to differ beyond chance at this alpha. "
            )

        # --- honest interpretation
        result.what_does_not_tell = (
            "A significant F only says that at least one of the groups differs "
            "from the others — it does not say which groups differ or by how "
            "much (look at the Tukey post-hoc table for that). ANOVA does not "
            "prove causation: the groups could differ for unmeasured reasons, "
            "and the assumptions (normality, equal variances) are only "
            "approximately true for real data."
        )
        return result


def _most_different_hint(
    tukey: pd.DataFrame | None,
    group_names: list[Any],
    means: list[float],
    significant: bool,
) -> str:
    """Hint naming the pair with the largest significant mean difference."""
    if tukey is None or tukey.empty or not significant:
        return (
            "no pairs examined (or no overall effect); the F test was not "
            "significant"
        )
    sig = tukey.copy()
    sig["|mean difference|"] = sig["Mean difference"].abs()
    sig = sig.loc[sig["significant at alpha?"] == "Yes"]
    if sig.empty:
        return "the F test is significant but no single pair reached significance"
    best = sig.loc[sig["|mean difference|"].idxmax()]
    return (
        f"{best['Pair']} (mean difference {best['Mean difference']:+.2f}, "
        f"q = {best['q']:.2f})"
    )


def _boxplot(
    df: pd.DataFrame,
    outcome_col: str,
    group_col: str,
    groups: list[Any],
    F_stat: float,
    p_val: float,
    alpha: float,
):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    data = [
        df.loc[df[group_col] == g, outcome_col].to_numpy(dtype=float) for g in groups
    ]
    bp = ax.boxplot(data, patch_artist=True, widths=0.55)
    # Set the category labels (avoids the matplotlib labels/tick_labels
    # rename that changed across 3.8/3.9, so we stay compatible with 3.7-3.12).
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
    p_str = "p < 0.001" if p_val < 0.001 else f"p = {p_val:.3f}"
    ax.set_title(
        f"{outcome_col} by {group_col}\n"
        f"F = {F_stat:.2f}, {p_str} (alpha = {alpha:.3f})",
        fontsize=10,
    )
    ax.set_ylabel(outcome_col)
    ax.grid(axis="y", ls=":", alpha=0.5)
    fig.tight_layout()
    caption = (
        f"Distribution of '{outcome_col}' by '{group_col}' "
        f"(F = {F_stat:.2f}, p = {p_str})"
    )
    return fig, caption


# Module-level instance the registry looks for.
ANALYSIS = AnovaOnewayAnalysis()
