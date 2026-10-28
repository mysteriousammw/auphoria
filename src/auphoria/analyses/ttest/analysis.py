"""Independent-samples t-test analysis for AUPHORIA.

Compares the mean of a numeric outcome between two independent groups using
SciPy's `ttest_ind`. The default is Welch's variant (equal_var=False), which
does not assume equal population variances; the pooled Student variant is
available via the `equal_var` parameter. Cohen's d is reported as the effect
size so students can gauge practical importance beyond the p-value.

Guardrails are enforced here, not in the front end:
- the outcome is confirmed numeric (refusing if it contains non-numeric text);
- the group must have exactly two categories (otherwise we refuse);
- missing values are counted and excluded with a warning, never imputed.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError


def _cohens_d(a: np.ndarray, b: np.ndarray, equal_var: bool) -> float:
    """Cohen's d: standardized mean difference between two groups."""
    na, nb = len(a), len(b)
    ma, mb = a.mean(), b.mean()
    va, vb = np.var(a, ddof=1), np.var(b, ddof=1)
    if na < 2 or nb < 2 or (equal_var and na + nb <= 2):
        return float("nan")
    if equal_var:
        pooled_var = ((na - 1) * va + (nb - 1) * vb) / (na + nb - 2)
        sd = np.sqrt(pooled_var) if pooled_var > 0 else 0.0
    else:
        sd = np.sqrt((va + vb) / 2) if (va + vb) > 0 else 0.0
    if sd == 0:
        return float("nan")
    return float((ma - mb) / sd)


def _effect_label(d: float) -> str:
    ad = abs(d)
    if ad < 0.2:
        return "negligible"
    if ad < 0.5:
        return "small"
    if ad < 0.8:
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


class TTestAnalysis(Analysis):
    id = "ttest"
    name = "Independent-Samples t-Test"

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
                    "The t-test needs a grouping column with exactly two categories "
                    "(e.g. control / treatment)."
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
                "The independent-samples t-test compares exactly TWO groups.",
                hint="Keep only the two groups you want to compare (or use a "
                     "multi-group analysis when one is available).",
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
        equal_var = bool(params["equal_var"])
        tail = str(params["tail"])

        test_name = "Welch" if not equal_var else "Student (pooled)"
        ctx.log_decision(
            f"Running {test_name} t-test (alpha={alpha}, {_tail_text(tail)}). "
            f"Groups '{g1}' (n={na}) vs '{g2}' (n={nb})."
        )

        t_stat, p_val = stats.ttest_ind(
            a, b, equal_var=equal_var, alternative=tail, nan_policy="raise"
        )
        df = na + nb - 2 if equal_var else _welch_df(na, nb, a.var(ddof=1), b.var(ddof=1))
        d = _cohens_d(a, b, equal_var)
        mean_diff = float(a.mean() - b.mean())

        # --- tables
        group_stats = pd.DataFrame(
            {
                "Group": [g1, g2],
                "n": [na, nb],
                "Mean": [round(float(a.mean()), 4), round(float(b.mean()), 4)],
                "SD": [round(float(a.std(ddof=1)), 4), round(float(b.std(ddof=1)), 4)],
            }
        )
        significant = bool(p_val < alpha)
        result_table = pd.DataFrame(
            {
                "Item": [
                    "t statistic", "degrees of freedom", "p-value",
                    "mean difference", "Cohen's d (effect size)",
                    "effect size label", "test", "significance level (alpha)",
                    "significant at alpha?",
                ],
                "Value": [
                    round(t_stat, 6), round(df, 1), self.fmt_p(p_val),
                    round(mean_diff, 4),
                    "NA" if np.isnan(d) else round(d, 4),
                    _effect_label(d) if not np.isnan(d) else "NA",
                    test_name, f"{alpha:.3f}", "Yes" if significant else "No",
                ],
            }
        )
        result.tables["Group statistics"] = group_stats
        result.tables["Independent-samples t-test"] = result_table

        # --- figure (boxplot by group)
        fig = _boxplot(both, outcome_col, group_col, g1, g2, t_stat, p_val, alpha)
        result.figures.append(
            FigureItem(
                name="ttest_boxplot",
                figure=fig,
                caption=(
                    f"Distribution of '{outcome_col}' by '{group_col}' "
                    f"(t = {t_stat:.2f}, p = {self.fmt_p(p_val)})"
                ),
            )
        )

        # --- summaries (plain-English highlights)
        mean_hi = max(a.mean(), b.mean())
        hi_group = g1 if a.mean() > b.mean() else g2
        result.summaries = {
            "t": f"t = {t_stat:.2f}",
            "degrees of freedom": f"df = {df:.0f}",
            "p-value": self.fmt_p(p_val),
            "mean difference": f"{mean_diff:+.2f}",
            "effect size (Cohen's d)": (
                "NA" if np.isnan(d) else f"{d:.2f} ({_effect_label(d)})"
            ),
            "significant at alpha": f"{alpha:.3f} → {'Yes' if significant else 'No'}",
            "larger mean group": (
                f"{hi_group} ({mean_hi:.2f})" if abs(a.mean() - b.mean()) > 0 else "equal"
            ),
        }

        # --- methods.txt sentences
        methods = [
            f"An independent-samples {test_name} t-test compared '{outcome_col}' "
            f"between the '{g1}' (n = {na}) and '{g2}' (n = {nb}) groups.",
            f"The test was {_tail_text(tail)} at a significance level of alpha = "
            f"{alpha:.3f} and gave t({df:.0f}) = {t_stat:.2f}, {_p_expr(p_val)}.",
        ]
        if not np.isnan(d):
            methods.append(
                f"The mean difference was {mean_diff:+.2f} with an effect size of "
                f"Cohen's d = {d:.2f}, interpreted as {_effect_label(d)}."
            )
        if significant:
            methods.append(
                f"Because p {_p_rel_num(p_val, alpha)} alpha, the difference "
                f"between the groups is described as statistically significant — "
                f"in everyday terms, an average difference at least this large "
                f"would be unlikely under chance alone."
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
            f"t = {t_stat:.4f}, df = {df:.2f}, p = {p_val:.4g}, Cohen's d = {d:.4g}."
        )
        if na < 5 or nb < 5:
            result.add_warning(
                "One or both groups are small (under 5). The t-test still runs, "
                "but results are sensitive to the normality assumption — treat "
                "them as preliminary."
            )
        result.what_does_not_tell = (
            "A significant p-value does not prove the treatment caused the "
            "difference — groups could differ for unmeasured reasons, and a "
            "small sample or unequal variances can exaggerate the result. "
            "This test does not establish causality."
        )
        return result


def _welch_df(na: int, nb: int, va: float, vb: float) -> float:
    denom_numer = (va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1)
    if denom_numer <= 0:
        return float(na + nb - 2)
    return (va / na + vb / nb) ** 2 / denom_numer


def _boxplot(
    df: pd.DataFrame,
    outcome_col: str,
    group_col: str,
    g1: str,
    g2: str,
    t_stat: float,
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
    for i, arr in enumerate(data, start=1):
        if len(arr):
            ax.scatter(np.full_like(arr, i) + np.random.default_rng(0).uniform(-0.08, 0.08, len(arr)),
                       arr, alpha=0.5, s=18, color="#333", edgecolor="white", linewidth=0.4)
    p_str = "p < 0.001" if p_val < 0.001 else f"p = {p_val:.3f}"
    ax.set_title(
        f"{outcome_col} by {group_col}\n"
        f"t = {t_stat:.2f}, {p_str} (alpha = {alpha:.3f})",
        fontsize=10,
    )
    ax.set_ylabel(outcome_col)
    ax.grid(axis="y", ls=":", alpha=0.5)
    fig.tight_layout()
    return fig


# Module-level instance the registry looks for.
ANALYSIS = TTestAnalysis()
