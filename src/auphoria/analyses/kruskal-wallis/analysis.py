"""Kruskal-Wallis H test analysis for AUPHORIA.

Compares the distribution of a numeric or ordinal outcome across three or
more independent groups using SciPy's `kruskal` — a rank-based test that does
not require normally distributed data. It is the non-parametric counterpart
of one-way ANOVA. Group medians are reported for context.

Guardrails are enforced here, not in the front end:
- the outcome is confirmed numeric (refusing if it contains non-numeric text);
- the group must have three or more categories (with fewer than three we
  refuse, pointing to the paired t-test / Mann-Whitney alternatives);
- missing values are counted and excluded with a warning, never imputed.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError


def _p_expr(p: float) -> str:
    return f"p {_p_rel(p)} {_p_num(p)}"


def _p_num(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def _p_rel(p: float) -> str:
    return "<" if p < 0.001 else "="


def _p_rel_num(p: float, alpha: float) -> str:
    """Plain comparison operator vs a stated alpha for a methods sentence."""
    return "<" if p < alpha else ">="


class KruskalWallisAnalysis(Analysis):
    id = "kruskal-wallis"
    name = "Kruskal-Wallis H Test"

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
                    "The Kruskal-Wallis test needs a grouping column with three "
                    "or more categories (e.g. control / treatment A / treatment B)."
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
                hint="Choose a group column with two or more categories.",
            )
        if len(groups) < 3:
            raise AssumptionError(
                f"The group column '{group_col}' has just {len(groups)} category "
                f"({', '.join(map(str, groups))}). The Kruskal-Wallis test compares "
                "THREE or more independent groups.",
                hint="For exactly two groups use a t-test or Mann-Whitney test, "
                     "or add a third group.",
            )

        alpha = float(params["alpha"])

        ctx.log_decision(
            f"Running Kruskal-Wallis H test (alpha={alpha}) across "
            f"{len(groups)} groups."
        )

        # Per-group numeric arrays, in the sorted group order.
        arrays = [
            both.loc[both[group_col] == g, outcome_col].to_numpy(dtype=float)
            for g in groups
        ]
        n_per = [len(a) for a in arrays]
        for g, n in zip(groups, n_per, strict=True):
            if n < 1:
                raise AssumptionError(
                    f"Group '{g}' has no observations after removing missing "
                    "values.",
                    hint="Check the grouping column for this group.",
                )

        h_stat, p_val = stats.kruskal(*arrays)
        h_stat = float(h_stat)
        p_val = float(p_val)
        df = len(groups) - 1
        n_total = int(sum(n_per))

        significant = bool(p_val < alpha)

        # --- tables
        group_stats = pd.DataFrame(
            {
                "Group": groups,
                "n": n_per,
                "Median": [round(float(np.median(a)), 4) for a in arrays],
            }
        )
        result_table = pd.DataFrame(
            {
                "Item": [
                    "H statistic",
                    "degrees of freedom (df)",
                    "p-value",
                    "n (total)",
                    "number of groups",
                    "test",
                    "significance level (alpha)",
                    "significant at alpha?",
                ],
                "Value": [
                    round(h_stat, 6), df, round(p_val, 6), n_total, len(groups),
                    "Kruskal-Wallis H", f"{alpha:.3f}",
                    "Yes" if significant else "No",
                ],
            }
        )
        result.tables["Group statistics"] = group_stats
        result.tables["Kruskal-Wallis test"] = result_table

        # --- figure (boxplot by group)
        fig = _boxplot(both, outcome_col, group_col, groups, h_stat, p_val, alpha)
        result.figures.append(
            FigureItem(
                name="kruskal_wallis_boxplot",
                figure=fig,
                caption=(
                    f"Distribution of '{outcome_col}' by '{group_col}' "
                    f"(H = {h_stat:.2f}, df = {df}, p = {self.fmt_p(p_val)})"
                ),
            )
        )

        # --- summaries (plain-English highlights)
        meds = [float(np.median(a)) for a in arrays]
        hi = max(range(len(meds)), key=lambda i: meds[i])
        lo = min(range(len(meds)), key=lambda i: meds[i])
        result.summaries = {
            "H statistic": f"{h_stat:.2f}",
            "degrees of freedom": f"{df}",
            "p-value": self.fmt_p(p_val),
            "n (total)": f"{n_total}",
            "significant at alpha": f"{alpha:.3f} → {'Yes' if significant else 'No'}",
            "highest median group": f"{groups[hi]} ({meds[hi]:.2f})",
            "lowest median group": f"{groups[lo]} ({meds[lo]:.2f})",
        }

        # --- methods.txt sentences
        methods = [
            f"A Kruskal-Wallis H test compared the distribution of "
            f"'{outcome_col}' across {len(groups)} independent groups "
            f"({', '.join(f'{g} (n = {n})' for g, n in zip(groups, n_per, strict=True))}).",
            f"The test was run at a significance level of alpha = {alpha:.3f} and "
            f"gave H = {h_stat:.2f} with df = {df}, {_p_expr(p_val)}.",
            "Group medians were "
            + ", ".join(f"{meds[i]:.2f} ('{groups[i]}')" for i in range(len(groups)))
            + ".",
        ]
        if significant:
            methods.append(
                f"Because p {_p_rel_num(p_val, alpha)} alpha, the difference "
                "between the groups is described as statistically significant — "
                "in everyday terms, a distributional difference at least this "
                "large would be unlikely under chance alone."
            )
        else:
            methods.append(
                f"Because p {_p_rel_num(p_val, alpha)} alpha, we do not have "
                "enough evidence to call the difference statistically significant."
            )
        methods.append(
            "The test does not say which groups differ; a significant result "
            "calls for a post-hoc comparison (e.g. Dunn's test) to locate the "
            "differences."
        )
        if dropped:
            methods.append(
                f"{dropped} row(s) with missing values in these columns were "
                "excluded; no missing values were imputed."
            )
        result.methods = methods

        # --- notes (reproducibility / interpretation)
        ctx.log_decision(
            f"H = {h_stat:.4f}, df = {df}, p = {p_val:.4g}, "
            f"n_total = {n_total} across {len(groups)} groups."
        )
        result.what_does_not_tell = (
            "This is not a test of means and does not tell you WHICH groups "
            "differ: a significant H only shows that the groups' distributions "
            "are not all the same. It does not locate the difference — a "
            "post-hoc test (such as Dunn's) is needed to find which pairs of "
            "groups differ — and it does not measure the size of any difference. "
            "As with any observational comparison, it also does not prove that "
            "the group variable caused the difference."
        )
        return result


def _boxplot(
    df: pd.DataFrame,
    outcome_col: str,
    group_col: str,
    groups: list[str],
    h_stat: float,
    p_val: float,
    alpha: float,
):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    data = [
        df.loc[df[group_col] == g, outcome_col].to_numpy(dtype=float)
        for g in groups
    ]
    bp = ax.boxplot(data, patch_artist=True, widths=0.5)
    # Set the category labels (avoids the matplotlib labels/tick_labels
    # rename that changed across 3.8/3.9, so we stay compatible with 3.7-3.12).
    ax.set_xticks(range(1, len(groups) + 1), groups)
    colors = ["#7fb4d8", "#8fc98d", "#e3b877", "#d88ba0", "#9d8fc9"]
    for patch, color in zip(bp["boxes"], colors, strict=False):
        patch.set_facecolor(color)
    rng = np.random.default_rng(0)
    for i, arr in enumerate(data, start=1):
        if len(arr):
            ax.scatter(np.full_like(arr, i) + rng.uniform(-0.08, 0.08, len(arr)),
                       arr, alpha=0.5, s=18, color="#333", edgecolor="white",
                       linewidth=0.4)
    p_str = "p < 0.001" if p_val < 0.001 else f"p = {p_val:.3f}"
    ax.set_title(
        f"{outcome_col} by {group_col}\n"
        f"H = {h_stat:.2f}, {p_str} (alpha = {alpha:.3f})",
        fontsize=10,
    )
    ax.set_ylabel(outcome_col)
    ax.grid(axis="y", ls=":", alpha=0.5)
    fig.tight_layout()
    return fig


# Module-level instance the registry looks for.
ANALYSIS = KruskalWallisAnalysis()

