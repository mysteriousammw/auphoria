"""Paired-samples t-test analysis for AUPHORIA.

Compares measurements taken on the same subjects (e.g. before vs after a
treatment) using SciPy's `ttest_rel` on the pair differences. Reports the mean
difference, t, df, p, a confidence interval for the mean difference, and
Cohen's d_z (standardised mean difference) as the effect size, plus a
before/after connected-line figure.

Guardrails are enforced here, not in the front end:
- both columns must exist and be numeric (refusing if text cannot become a
  number);
- rows missing either measurement are counted and excluded with a warning,
  never imputed;
- at least two complete pairs are required;
- the pair differences must vary (a constant difference makes t undefined);
- normality of the differences is checked with Shapiro-Wilk when the sample
  size allows, and a small sample triggers a plain-English caution.
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


def _ci_name(alpha: float) -> str:
    return f"{int(round((1 - alpha) * 100))}% CI"


class PairedTTestAnalysis(Analysis):
    id = "ttest-paired"
    name = "Paired-Samples t-Test"

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        result = AnalysisResult()
        before_col = inputs["before"]
        after_col = inputs["after"]

        if before_col not in data.columns:
            raise AssumptionError(
                f"The data has no column named '{before_col}'.",
                hint="Pick a 'before' column from your file.",
            )
        if after_col not in data.columns:
            raise AssumptionError(
                f"The data has no column named '{after_col}'.",
                hint="Pick an 'after' column from your file.",
            )

        # Numeric guarantee on both columns (refuses non-numeric text cells).
        before = self.ensure_numeric(data[before_col], before_col)
        after = self.ensure_numeric(data[after_col], after_col)
        self.describe_missing(before, before_col, ctx)
        self.describe_missing(after, after_col, ctx)

        # Combine and drop rows missing EITHER measurement, with a warning.
        both = pd.DataFrame({before_col: before, after_col: after})
        dropped = int(both.isna().any(axis=1).sum())
        both = both.dropna()
        if dropped:
            result.add_warning(
                f"{dropped} row(s) had a missing value in '{before_col}' or "
                f"'{after_col}' and were left out of this test. They were counted, "
                "not changed or replaced."
            )
            ctx.log_decision(
                f"Excluded {dropped} row(s) with a missing before/after value "
                f"(listwise); {len(both)} complete pair(s) remain for the test."
            )

        n = len(both)
        if n < 2:
            raise AssumptionError(
                "After removing rows with missing values fewer than 2 complete "
                "pairs were left, so the paired t-test cannot run.",
                hint="Each row must hold one subject measured twice; check that "
                     "your before/after columns overlap on at least 2 rows.",
            )

        before_arr = both[before_col].to_numpy(dtype=float)
        after_arr = both[after_col].to_numpy(dtype=float)
        diffs = after_arr - before_arr

        # A constant difference (including identical columns) makes t undefined.
        diff_std = float(np.std(diffs, ddof=1))
        if diff_std <= 1e-12:
            raise AssumptionError(
                "The pair differences are identical for every subject, so the "
                "paired t-test is undefined.",
                hint="The before and after values never differ (or differ by the "
                     "same amount each time). Check that you picked two genuinely "
                     "different measurement columns, one per time point.",
            )

        alpha = float(params["alpha"])
        ctx.log_decision(
            f"Running paired-samples t-test (two-sided, alpha={alpha}) on "
            f"{n} complete pairs: '{before_col}' vs '{after_col}'."
        )

        mean_diff = float(diffs.mean())
        t_stat, p_val = stats.ttest_rel(after_arr, before_arr)  # two-sided
        df = n - 1
        stderr = diff_std / np.sqrt(n)
        ci_low, ci_high = stats.t.interval(1 - alpha, df, loc=mean_diff, scale=stderr)
        d_z = mean_diff / diff_std

        # --- normality check on the differences (Shapiro-Wilk)
        if 3 <= n <= 5000:
            shapiro_w, shapiro_p = stats.shapiro(diffs)
            sounds_normal = shapiro_p >= alpha
            ctx.log_decision(
                f"Shapiro-Wilk on the {n} pair differences: W = {shapiro_w:.4f}, "
                f"p = {shapiro_p:.4g} "
                + ("(consistent with normal differences)."
                   if sounds_normal
                   else "(differences look non-normal)."),
            )
            if not sounds_normal:
                result.add_verdict(
                    "WARN",
                    "normality",
                    "The pair differences look non-normal (Shapiro-Wilk "
                    f"p = {self.fmt_p(shapiro_p)} < alpha = {alpha:.3f}). "
                    "Consider the Wilcoxon signed-rank test on the differences "
                    "instead of this t-test.",
                )
        else:
            ctx.log_decision(
                f"Shapiro-Wilk skipped (n = {n} is outside the reliable "
                "3-5000 range)."
            )
        if n < 10:
            result.add_warning(
                f"Only {n} complete pair(s) — too few to verify the normality "
                "assumption reliably. The t-test still runs, but treat the "
                "result as preliminary."
            )

        # --- tables
        paired_stats = pd.DataFrame(
            {
                "n": [n],
                "Mean before": [round(float(before_arr.mean()), 4)],
                "Mean after": [round(float(after_arr.mean()), 4)],
                "Mean difference": [round(mean_diff, 4)],
                "SD of differences": [round(diff_std, 4)],
            }
        )
        result.tables["Paired statistics"] = paired_stats

        significant = bool(p_val < alpha)
        result_table = pd.DataFrame(
            {
                "Item": [
                    "t statistic",
                    "degrees of freedom",
                    "p-value",
                    f"{_ci_name(alpha)} lower",
                    f"{_ci_name(alpha)} upper",
                    "Cohen's d_z (effect size)",
                    "significance level (alpha)",
                    "significant at alpha?",
                ],
                "Value": [
                    round(t_stat, 6),
                    round(df, 1),
                    self.fmt_p(p_val),
                    round(ci_low, 4),
                    round(ci_high, 4),
                    round(d_z, 4),
                    f"{alpha:.3f}",
                    "Yes" if significant else "No",
                ],
            }
        )
        result.tables["Paired-samples t-test"] = result_table

        # --- figure (before/after connected lines, one per subject)
        fig = _paired_lines(both, before_col, after_col, t_stat, p_val, alpha)
        result.figures.append(
            FigureItem(
                name="ttest_paired_lines",
                figure=fig,
                caption=(
                    f"Each line connects one subject's '{before_col}' and "
                    f"'{after_col}' value; green = increase, red = decrease "
                    f"(t = {t_stat:.2f}, p = {self.fmt_p(p_val)})"
                ),
            )
        )

        # --- summaries (plain-English highlights)
        result.summaries = {
            "t": f"t = {t_stat:.2f}",
            "degrees of freedom": f"df = {df:.0f}",
            "p-value": self.fmt_p(p_val),
            "mean difference": f"{mean_diff:+.2f}",
            "Cohen's d_z": f"{d_z:.2f}",
            "significant at alpha": f"{alpha:.3f} → {'Yes' if significant else 'No'}",
        }

        # --- methods.txt sentences
        methods = [
            f"A paired-samples t-test compared '{after_col}' with '{before_col}' "
            f"on the same subjects (n = {n} complete pairs).",
            f"The test was two-sided at a significance level of alpha = "
            f"{alpha:.3f} and gave t({df:.0f}) = {t_stat:.2f}, {_p_expr(p_val)}.",
            f"The mean difference ({after_col} - {before_col}) was "
            f"{mean_diff:+.2f} ({_ci_name(alpha)} {ci_low:.2f} to {ci_high:.2f}), "
            f"with an effect size of Cohen's d_z = {d_z:.2f}.",
        ]
        if significant:
            methods.append(
                f"Because p {_p_rel_num(p_val, alpha)} alpha, the change is "
                f"described as statistically significant."
            )
        if dropped:
            methods.append(
                f"{dropped} row(s) with missing values in these columns were "
                f"excluded; no missing values were imputed."
            )
        result.methods = methods

        # --- notes (reproducibility / interpretation)
        ctx.log_decision(
            f"t = {t_stat:.4f}, df = {df:.1f}, p = {p_val:.4g}, "
            f"mean difference = {mean_diff:.4g}, Cohen's d_z = {d_z:.4g}."
        )
        result.what_does_not_tell = (
            "A significant p-value does not prove the treatment caused the "
            "change — the same subjects could have changed naturally over time "
            "(growth, learning, regression to the mean), and there is no "
            "control group to rule that out. This test only says whether the "
            "average difference is unlikely to be chance."
        )
        return result


def _paired_lines(
    df: pd.DataFrame,
    before_col: str,
    after_col: str,
    t_stat: float,
    p_val: float,
    alpha: float,
):
    import matplotlib.pyplot as plt

    rng = np.random.default_rng(0)  # deterministic jitter
    b = df[before_col].to_numpy(dtype=float)
    a = df[after_col].to_numpy(dtype=float)
    n = len(df)
    jx = rng.uniform(-0.05, 0.05, n)
    jy = rng.uniform(-0.08, 0.08, n)

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    for i in range(n):
        if a[i] > b[i]:
            color = "#2f9e44"
        elif a[i] < b[i]:
            color = "#c92a2a"
        else:
            color = "#868e96"
        x1, x2 = 1 + jx[i], 2 + jx[i]
        y1, y2 = b[i] + jy[i], a[i] + jy[i]
        ax.plot([x1, x2], [y1, y2], color=color, linewidth=1.0, alpha=0.7, zorder=1)
        ax.scatter([x1, x2], [y1, y2], s=22, color=color,
                   edgecolor="white", linewidth=0.4, zorder=2)
    # Positional labels form works across matplotlib 3.7-3.12.
    ax.set_xticks([1, 2], [before_col, after_col])
    ax.set_ylabel("Value")
    p_str = "p < 0.001" if p_val < 0.001 else f"p = {p_val:.3f}"
    ax.set_title(
        f"{before_col} -> {after_col} (paired)\n"
        f"t = {t_stat:.2f}, {p_str} (alpha = {alpha:.3f})",
        fontsize=10,
    )
    ax.grid(axis="y", ls=":", alpha=0.5)
    fig.tight_layout()
    return fig


# Module-level instance the registry looks for.
ANALYSIS = PairedTTestAnalysis()
