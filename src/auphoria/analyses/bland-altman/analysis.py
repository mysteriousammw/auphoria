"""Bland-Altman agreement analysis for AUPHORIA.

Assesses how well two measurement methods agree on the same quantity measured
on the same subjects (one row per subject). For each pair it computes the
difference ``d = method_a - method_b`` and the mean
``m = (method_a + method_b) / 2``, then reports:

- the mean difference (the **bias**);
- the SD of the differences and the **95% limits of agreement**
  (bias +/- 1.96 * SD) — the range within which most (about 95%) of the
  differences between the two methods should fall;
- the standard error of the bias and approximate 95% confidence intervals
  for the bias and each limit of agreement;
- a Bland-Altman plot (difference vs mean) with the bias line, the two
  limits-of-agreement lines and a shaded band, plus a linear regression line
  of difference on mean to flag **proportional bias** (a difference whose
  size scales with the magnitude being measured);
- a proportional-bias check: the correlation between |difference| and the
  mean (reporting r and p, with a WARN verdict when significant).

Guardrails are enforced here, not in the front end:
- both columns must exist and be numeric (refusing if text cannot become a
  number);
- at least three complete pairs are required (fewer makes the limits wildly
  unreliable);
- rows missing either measurement are counted and excluded with a warning,
  never imputed.

The limits of agreement are NOT a pass/fail check by themselves — whether the
two methods agree closely enough is a clinical/professional decision that must
be judged against an externally chosen acceptable difference.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError

_MIN_PAIRS = 3


def _ci_name(alpha: float) -> str:
    return f"{int(round((1 - alpha) * 100))}% CI"


def _loa_label(k: int, alpha: float) -> str:
    """Label for a limit of agreement, e.g. '95% LoA lower'."""
    return f"{int(round((1 - alpha) * 100))}% LoA {'lower' if k == -1 else 'upper'}"


class BlandAltmanAnalysis(Analysis):
    id = "bland-altman"
    name = "Bland-Altman Agreement"

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        result = AnalysisResult()
        a_col = inputs["method_a"]
        b_col = inputs["method_b"]

        if a_col not in data.columns:
            raise AssumptionError(
                f"The data has no column named '{a_col}'.",
                hint="Pick a 'method A' column from your file.",
            )
        if b_col not in data.columns:
            raise AssumptionError(
                f"The data has no column named '{b_col}'.",
                hint="Pick a 'method B' column from your file.",
            )

        # Numeric guarantee on both columns (refuses non-numeric text cells).
        a = self.ensure_numeric(data[a_col], a_col)
        b = self.ensure_numeric(data[b_col], b_col)
        self.describe_missing(a, a_col, ctx)
        self.describe_missing(b, b_col, ctx)

        # Combine and drop rows missing EITHER measurement (listwise), warning.
        both = pd.DataFrame({a_col: a, b_col: b})
        dropped = int(both.isna().any(axis=1).sum())
        both = both.dropna()
        if dropped:
            result.add_warning(
                f"{dropped} row(s) had a missing value in '{a_col}' or "
                f"'{b_col}' and were left out of this analysis. They were "
                "counted, not changed or replaced."
            )
            ctx.log_decision(
                f"Excluded {dropped} row(s) with a missing A/B value "
                f"(listwise); {len(both)} complete pair(s) remain."
            )

        n = len(both)
        if n < _MIN_PAIRS:
            raise AssumptionError(
                f"After removing rows with missing values fewer than "
                f"{_MIN_PAIRS} complete pairs were left, so the Bland-Altman "
                "analysis cannot run.",
                hint=(
                    "With fewer than 3 pairs the limits of agreement are far "
                    "too unstable to mean anything. Each row must hold one "
                    "subject measured by both methods; check that your two "
                    "columns overlap on at least 3 rows."
                ),
            )

        alpha = float(params["alpha"])
        a_arr = both[a_col].to_numpy(dtype=float)
        b_arr = both[b_col].to_numpy(dtype=float)
        diff = a_arr - b_arr
        mean = (a_arr + b_arr) / 2.0

        ctx.log_decision(
            f"Running Bland-Altman agreement (alpha={alpha}) on {n} complete "
            f"pairs: '{a_col}' (method A) vs '{b_col}' (method B)."
        )

        bias = float(diff.mean())
        sd = float(np.std(diff, ddof=1))
        z = 1.96  # conventional 95% coverage factor for the limits
        loa_lower = bias - z * sd
        loa_upper = bias + z * sd
        se_bias = sd / np.sqrt(n)
        df = n - 1
        t_val = float(stats.t.ppf(1 - alpha / 2, df))
        bias_ci_low, bias_ci_high = (
            bias - t_val * se_bias,
            bias + t_val * se_bias,
        )
        # Approximate SE of a limit of agreement (Bland & Altman, 1986).
        se_loa = sd * np.sqrt(3.0 / n)
        loa_lo_ci_low, loa_lo_ci_high = loa_lower - t_val * se_loa, loa_lower + t_val * se_loa
        loa_up_ci_low, loa_up_ci_high = loa_upper - t_val * se_loa, loa_upper + t_val * se_loa

        # --- tables
        agreement = pd.DataFrame(
            {
                "Item": [
                    "number of pairs (n)",
                    "mean difference (bias)",
                    "SD of differences",
                    f"{_loa_label(-1, alpha)}",
                    f"{_loa_label(1, alpha)}",
                    "SE of bias",
                    f"{_ci_name(alpha)} for the bias (lower)",
                    f"{_ci_name(alpha)} for the bias (upper)",
                ],
                "Value": [
                    n,
                    round(bias, 4),
                    round(sd, 4),
                    round(loa_lower, 4),
                    round(loa_upper, 4),
                    round(se_bias, 4),
                    round(bias_ci_low, 4),
                    round(bias_ci_high, 4),
                ],
            }
        )
        result.tables["Agreement statistics"] = agreement

        limits_ci = pd.DataFrame(
            {
                "Item": [
                    _loa_label(-1, alpha),
                    f"{_ci_name(alpha)} lower for the lower LoA",
                    f"{_ci_name(alpha)} upper for the lower LoA",
                    _loa_label(1, alpha),
                    f"{_ci_name(alpha)} lower for the upper LoA",
                    f"{_ci_name(alpha)} upper for the upper LoA",
                ],
                "Value": [
                    round(loa_lower, 4),
                    round(loa_lo_ci_low, 4),
                    round(loa_lo_ci_high, 4),
                    round(loa_upper, 4),
                    round(loa_up_ci_low, 4),
                    round(loa_up_ci_high, 4),
                ],
            }
        )
        result.tables["Limits of agreement (95% CI)"] = limits_ci

        # --- proportional-bias check: correlation between |diff| and mean.
        abs_diff = np.abs(diff)
        prop_flag = False
        r_prop = 0.0
        p_prop = 1.0
        if np.ptp(abs_diff) > 1e-12 and np.ptp(mean) > 1e-12:
            r_prop, p_prop = stats.pearsonr(abs_diff, mean)
            ctx.log_decision(
                f"Proportional-bias check: correlation(|difference|, mean) = "
                f"r = {r_prop:.4f}, p = {p_prop:.4g} "
                + ("(differences scale with magnitude — look at the plot)."
                   if p_prop < alpha else
                   "(no strong evidence the differences scale with magnitude)."),
            )
            prop_flag = bool(p_prop < alpha)
            prop_table = pd.DataFrame(
                {
                    "Item": [
                        "Pearson r (|difference| vs mean)",
                        "p-value",
                        "alpha",
                        "significant at alpha? (proportional bias?)",
                    ],
                    "Value": [
                        round(float(r_prop), 4),
                        self.fmt_p(float(p_prop)),
                        f"{alpha:.3f}",
                        "Yes" if prop_flag else "No",
                    ],
                }
            )
            result.tables["Proportional-bias check"] = prop_table
            if prop_flag:
                result.add_verdict(
                    "WARN",
                    "proportional-bias",
                    "The size of the differences grows with the measured "
                    f"magnitude (correlation |difference| vs mean r = "
                    f"{r_prop:.2f}, p {self.fmt_p(float(p_prop))} < alpha = "
                    f"{alpha:.3f}). The limits of agreement are then too wide "
                    "at one end and too narrow at the other — consider "
                    "analysis on the log scale.",
                )
        else:
            ctx.log_decision(
                "Proportional-bias check skipped: the absolute differences or "
                "the pair means are constant."
            )
            result.tables["Proportional-bias check"] = pd.DataFrame(
                {
                    "Item": ["note"],
                    "Value": [
                        "Skipped — the differences (or the pair means) are "
                        "constant, so a correlation cannot be computed."
                    ],
                }
            )

        # Normality of the differences matters for the LoA interpretation.
        if 3 <= n <= 5000:
            _, shapiro_p = stats.shapiro(diff)
            ctx.log_decision(
                f"Shapiro-Wilk on the {n} differences: "
                + (f"p = {shapiro_p:.4g} (consistent with normal)."
                   if shapiro_p >= alpha else
                   f"p = {shapiro_p:.4g} (differences look non-normal)."),
            )
            if shapiro_p < alpha:
                result.add_warning(
                    "The differences look non-normal (Shapiro-Wilk "
                    f"p = {self.fmt_p(float(shapiro_p))} < alpha = {alpha:.3f}). "
                    "The limits of agreement assume the differences are roughly "
                    "normal — treat them as approximate, and consider analysis "
                    "on the log scale."
                )
        else:
            ctx.log_decision(
                f"Shapiro-Wilk skipped (n = {n} is outside the reliable "
                "3-5000 range)."
            )

        # --- figure
        fig = _bland_altman_plot(
            mean, diff, bias, loa_lower, loa_upper, a_col, b_col, alpha
        )
        result.figures.append(
            FigureItem(
                name="bland_altman_plot",
                figure=fig,
                caption=(
                    "Bland-Altman plot: difference (A - B) against the pair "
                    f"mean. Solid line = bias ({bias:.2f}); dashed lines = "
                    f"95% limits of agreement ({loa_lower:.2f}, "
                    f"{loa_upper:.2f}); shaded band = the region inside the "
                    "limits."
                ),
            )
        )

        # --- summaries
        result.summaries = {
            "n": f"{n} pairs",
            "bias (mean difference)": f"{bias:+.2f}",
            "SD of differences": f"{sd:.2f}",
            f"{_loa_label(-1, alpha)}": f"{loa_lower:.2f}",
            f"{_loa_label(1, alpha)}": f"{loa_upper:.2f}",
            "proportional bias": (
                "flagged (WARN)" if prop_flag else "no evidence detected"
            ),
        }

        # --- methods.txt
        methods = [
            f"A Bland-Altman agreement analysis compared '{a_col}' (method A) "
            f"with '{b_col}' (method B) on the same subjects (n = {n} pairs).",
            f"The mean difference (bias, A - B) was {bias:+.2f} with SD of "
            f"differences {sd:.2f}, giving 95% limits of agreement from "
            f"{loa_lower:.2f} to {loa_upper:.2f} "
            f"(bias +/- 1.96 * SD; bias {_ci_name(alpha)} "
            f"{bias_ci_low:.2f} to {bias_ci_high:.2f}).",
        ]
        if prop_flag:
            methods.append(
                "The differences scaled with the measured magnitude "
                f"(correlation |difference| vs mean r = {r_prop:.2f}, "
                f"p = {self.fmt_p(float(p_prop))}), so the limits of agreement "
                "are width-dependent; analysis on the log scale may be "
                "more appropriate.",
            )
        if dropped:
            methods.append(
                f"{dropped} row(s) with missing values in these columns were "
                "excluded; no missing values were imputed."
            )
        result.methods = methods

        result.what_does_not_tell = (
            "The limits of agreement are NOT a pass/fail verdict by themselves "
            "— whether the observed bias and limits are 'close enough' must be "
            "judged against a clinically or professionally acceptable "
            "difference that you choose in advance, based on the context. The "
            "limits assume the differences are roughly normally distributed "
            "(otherwise they are approximate), and a significant t-test "
            "showing the bias differs from zero is not the same as poor "
            "agreement, nor does an insignificant one prove good agreement."
        )
        return result


def _bland_altman_plot(
    mean: np.ndarray,
    diff: np.ndarray,
    bias: float,
    loa_lower: float,
    loa_upper: float,
    a_col: str,
    b_col: str,
    alpha: float,
):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.5, 4.8))
    ax.axhspan(
        loa_lower, loa_upper, color="#d0bfff", alpha=0.35, zorder=1,
        label="inside 95% limits",
    )
    ax.scatter(mean, diff, s=30, color="#364fc7", edgecolor="white",
               linewidth=0.5, zorder=4, label="pair (A - B)")
    ax.axhline(bias, color="#2b8a3e", linewidth=1.6, zorder=3,
               label=f"bias = {bias:.2f}")
    ax.axhline(loa_lower, color="#c92a2a", linewidth=1.2, ls="--", zorder=3,
               label=f"lower 95% LoA = {loa_lower:.2f}")
    ax.axhline(loa_upper, color="#c92a2a", linewidth=1.2, ls="--", zorder=3,
               label=f"upper 95% LoA = {loa_upper:.2f}")

    # Regression of difference on mean (reveals proportional bias as a slope).
    if np.ptp(mean) > 1e-12:
        slope, intercept, *_ = stats.linregress(mean, diff)
        xs = np.linspace(float(mean.min()), float(mean.max()), 50)
        ax.plot(
            xs, intercept + slope * xs, color="#e8590c", linewidth=1.4,
            zorder=5, label=f"regression line (slope {slope:.3f})",
        )
        ax.text(
            0.99, 0.02, f"slope = {slope:+.3f}", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=8, color="#e8590c", zorder=6,
        )

    ax.set_xlabel(f"Mean of {a_col} and {b_col}")
    ax.set_ylabel(f"Difference ({a_col} - {b_col})")
    ax.set_title(
        f"Bland-Altman plot ({int(round((1 - alpha) * 100))}% limits)",
        fontsize=10,
    )
    ax.grid(axis="y", ls=":", alpha=0.5)
    ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    return fig


# Module-level instance the registry looks for.
ANALYSIS = BlandAltmanAnalysis()
