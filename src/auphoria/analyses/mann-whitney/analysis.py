"""Mann-Whitney U test analysis for AUPHORIA.

Compares the distribution of a numeric or ordinal outcome between two
independent groups using SciPy's `mannwhitneyu` — a rank-based test that
does not require normally distributed data. Group medians are reported for
context, and the effect size is the rank-biserial correlation r, computed
from U so its sign shows which group tends to score higher.

Guardrails are enforced here, not in the front end:
- the outcome is confirmed numeric (refusing if it contains non-numeric text);
- the group must have exactly two categories (otherwise we refuse, pointing
  to Kruskal-Wallis when more than two are present);
- missing values are counted and excluded with a warning, never imputed.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError


def _rank_biserial_r(u1: float, n1: int, n2: int) -> float:
    """Rank-biserial r = 1 - 2*U1/(n1*n2).

    Positive means group 1 (the alphabetically first group) tends to have
    higher values; negative means group 1 tends lower.
    """
    total = n1 * n2
    if total == 0:
        return float("nan")
    return 1.0 - 2.0 * u1 / total


def _effect_label(r: float) -> str:
    ar = abs(r)
    if ar < 0.1:
        return "negligible"
    if ar < 0.3:
        return "small"
    if ar < 0.5:
        return "medium"
    return "large"


def _tail_text(tail: str) -> str:
    return {"two-sided": "two-sided", "greater": "one-sided (greater)",
            "less": "one-sided (less)"}[tail]


def _p_expr(p: float) -> str:
    return f"p {_p_rel(p)} {_p_num(p)}"


def _p_num(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def _p_rel(p: float) -> str:
    return "<" if p < 0.001 else "="


def _p_rel_num(p: float, alpha: float) -> str:
    """Plain comparison operator vs a stated alpha for a methods sentence."""
    return "<" if p < alpha else ">="


class MannWhitneyAnalysis(Analysis):
    id = "mann-whitney"
    name = "Mann-Whitney U Test"

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
                    "The Mann-Whitney test needs a grouping column with exactly "
                    "two categories (e.g. control / treatment)."
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
                f"'{group_col}' and were left out of this test. They were counted, "
                "not changed or replaced."
            )
            ctx.log_decision(
                f"Excluded {dropped} row(s) with missing outcome/group (listwise); "
                f"{len(both)} row(s) remain for the test."
            )

        if both.empty:
            raise AssumptionError(
                "After removing rows with missing values there were no complete "
                "rows left to test.",
                hint="Check that your outcome and group columns have actual values.",
            )

        groups = sorted(both[group_col].dropna().unique().tolist())
        if len(groups) < 2:
            raise AssumptionError(
                f"The group column '{group_col}' has only 1 distinct category "
                f"('{groups[0] if groups else ''}'), so a comparison is impossible.",
                hint="Choose a group column with two categories.",
            )
        if len(groups) > 2:
            raise AssumptionError(
                f"The group column '{group_col}' has {len(groups)} categories "
                f"({', '.join(map(str, groups[:6]))}{'...' if len(groups) > 6 else ''}). "
                "The Mann-Whitney U test compares exactly TWO groups.",
                hint="Keep only the two groups you want to compare (or use a "
                     "Kruskal-Wallis test when one is available for 3+ groups).",
            )

        g1, g2 = groups
        a = both.loc[both[group_col] == g1, outcome_col].to_numpy(dtype=float)
        b = both.loc[both[group_col] == g2, outcome_col].to_numpy(dtype=float)
        na, nb = len(a), len(b)
        if na < 2 or nb < 2:
            raise AssumptionError(
                "Each group needs at least two observations.",
                hint=f"Group '{g1}' has {na}, group '{g2}' has {nb}. Add data or "
                     "choose another grouping.",
            )

        alpha = float(params["alpha"])
        tail = str(params["tail"])

        ctx.log_decision(
            f"Running Mann-Whitney U test (alpha={alpha}, {_tail_text(tail)}). "
            f"Groups '{g1}' (n={na}) vs '{g2}' (n={nb})."
        )

        u1, p_val = stats.mannwhitneyu(
            a, b, alternative=tail, method="auto"
        )
        u1 = float(u1)
        p_val = float(p_val)
        u2 = na * nb - u1
        r = _rank_biserial_r(u1, na, nb)
        r_na = bool(np.isnan(r))

        # --- tables
        group_stats = pd.DataFrame(
            {
                "Group": [g1, g2],
                "n": [na, nb],
                "Median": [round(float(np.median(a)), 4), round(float(np.median(b)), 4)],
            }
        )
        significant = bool(p_val < alpha)
        result_table = pd.DataFrame(
            {
                "Item": [
                    "U statistic", "p-value", "n1", "n2",
                    "rank-biserial r (effect size)", "effect size label",
                    "test", "significance level (alpha)", "significant at alpha?",
                ],
                "Value": [
                    round(u1, 6), round(p_val, 6), na, nb,
                    "NA" if r_na else round(r, 4),
                    _effect_label(r) if not r_na else "NA",
                    f"Mann-Whitney U ({_tail_text(tail)})", f"{alpha:.3f}",
                    "Yes" if significant else "No",
                ],
            }
        )
        result.tables["Group statistics"] = group_stats
        result.tables["Mann-Whitney U test"] = result_table

        # --- figure (boxplot by group)
        fig = _boxplot(both, outcome_col, group_col, g1, g2, u1, p_val, alpha)
        result.figures.append(
            FigureItem(
                name="mann_whitney_boxplot",
                figure=fig,
                caption=(
                    f"Distribution of '{outcome_col}' by '{group_col}' "
                    f"(U = {u1:.2f}, p = {self.fmt_p(p_val)})"
                ),
            )
        )

        # --- summaries (plain-English highlights)
        med_hi = max(float(np.median(a)), float(np.median(b)))
        hi_group = g1 if float(np.median(a)) > float(np.median(b)) else g2
        result.summaries = {
            "U": f"{u1:.2f}",
            "p-value": self.fmt_p(p_val),
            "median group 1": f"{np.median(a):.2f}",
            "median group 2": f"{np.median(b):.2f}",
            "effect size (rank-biserial r)": (
                "NA" if r_na else f"{r:.2f} ({_effect_label(r)})"
            ),
            "significant at alpha": f"{alpha:.3f} → {'Yes' if significant else 'No'}",
            "higher median group": (
                f"{hi_group} ({med_hi:.2f})"
                if abs(float(np.median(a)) - float(np.median(b))) > 0 else "equal"
            ),
        }

        # --- methods.txt sentences
        methods = [
            f"A Mann-Whitney U test compared the distribution of '{outcome_col}' "
            f"between the '{g1}' (n = {na}) and '{g2}' (n = {nb}) groups.",
            f"The test was {_tail_text(tail)} at a significance level of alpha = "
            f"{alpha:.3f} and gave U = {u1:.2f}, {_p_expr(p_val)}.",
            f"Group medians were {np.median(a):.2f} ('{g1}') and "
            f"{np.median(b):.2f} ('{g2}').",
        ]
        if not r_na:
            methods.append(
                f"The effect size was a rank-biserial r = {r:.2f}, interpreted "
                f"as {_effect_label(r)}."
            )
        if significant:
            methods.append(
                f"Because p {_p_rel_num(p_val, alpha)} alpha, the difference "
                f"between the groups is described as statistically significant — "
                f"in everyday terms, a distributional difference at least this "
                f"large would be unlikely under chance alone."
            )
        else:
            methods.append(
                f"Because p {_p_rel_num(p_val, alpha)} alpha, we do not have "
                f"enough evidence to call the difference statistically "
                f"significant."
            )
        if dropped:
            methods.append(
                f"{dropped} row(s) with missing values in these columns were "
                f"excluded; no missing values were imputed."
            )
        result.methods = methods

        # --- notes (reproducibility / interpretation)
        ctx.log_decision(
            f"U1 = {u1:.4f} (for '{g1}'), U2 = {u2:.4f}, p = {p_val:.4g}, "
            f"rank-biserial r = {r:.4g}."
        )
        result.what_does_not_tell = (
            "This is not a test of means, and a significant result does not "
            "automatically mean the medians differ: it shows the groups' "
            "distributions sit apart (one group tends to produce higher values "
            "than the other, called stochastic superiority). To read it as a "
            "location shift (one group's values are shifted up or down), the "
            "two distributions should have a similar shape; with very different "
            "spreads the result is about ordering, not medians."
        )
        return result


def _boxplot(
    df: pd.DataFrame,
    outcome_col: str,
    group_col: str,
    g1: str,
    g2: str,
    u1: float,
    p_val: float,
    alpha: float,
):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    order = [g1, g2]
    data = [df.loc[df[group_col] == g, outcome_col].to_numpy(dtype=float) for g in order]
    bp = ax.boxplot(data, patch_artist=True, widths=0.5)
    # Set the category labels (avoids the matplotlib labels/tick_labels
    # rename that changed across 3.8/3.9, so we stay compatible with 3.7-3.12).
    ax.set_xticks(range(1, len(order) + 1), order)
    for patch, color in zip(bp["boxes"], ["#7fb4d8", "#8fc98d"], strict=False):
        patch.set_facecolor(color)
    rng = np.random.default_rng(0)
    for i, arr in enumerate(data, start=1):
        if len(arr):
            ax.scatter(np.full_like(arr, i) + rng.uniform(-0.08, 0.08, len(arr)),
                       arr, alpha=0.5, s=18, color="#333", edgecolor="white", linewidth=0.4)
    p_str = "p < 0.001" if p_val < 0.001 else f"p = {p_val:.3f}"
    ax.set_title(
        f"{outcome_col} by {group_col}\n"
        f"U = {u1:.2f}, {p_str} (alpha = {alpha:.3f})",
        fontsize=10,
    )
    ax.set_ylabel(outcome_col)
    ax.grid(axis="y", ls=":", alpha=0.5)
    fig.tight_layout()
    return fig


# Module-level instance the registry looks for.
ANALYSIS = MannWhitneyAnalysis()
