"""Simple linear regression analysis for AUPHORIA.

Fits a straight line predicting a numeric ``outcome`` from one numeric
``predictor`` using SciPy's `linregress` (a light, permissive dependency). The
result reports the slope, intercept, standard error, p-value, r, R2 and a
95% confidence interval for the slope, plus a scatter with the best-fit line
and a residuals-vs-fitted figure so the student can judge whether a straight
line is reasonable.

Guardrails are enforced here, not in the front end:
- both columns must exist and be numeric;
- at least three complete (outcome, predictor) pairs are required;
- a constant predictor (zero range, every value the same) is refused;
- small samples (under 10 pairs) get a WARN verdict;
- missing values are counted and excluded pairwise with a warning, never
  imputed.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError


class RegressionLinearAnalysis(Analysis):
    id = "regression-linear"
    name = "Simple Linear Regression"

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        result = AnalysisResult()
        outcome_name = inputs["outcome"]
        predictor_name = inputs["predictor"]

        for col in (outcome_name, predictor_name):
            if col not in data.columns:
                raise AssumptionError(
                    f"The data has no column named '{col}'.",
                    hint="Pick a numeric column from your file.",
                )

        outcome = self.ensure_numeric(data[outcome_name], outcome_name)
        predictor = self.ensure_numeric(data[predictor_name], predictor_name)
        self.describe_missing(outcome, outcome_name, ctx)
        self.describe_missing(predictor, predictor_name, ctx)

        both = pd.DataFrame({"outcome": outcome, "predictor": predictor})
        dropped = int(both.isna().any(axis=1).sum())
        both = both.dropna()
        if dropped:
            result.add_warning(
                f"{dropped} row(s) had a missing value in '{outcome_name}' or "
                f"'{predictor_name}' and were left out of the regression. They "
                "were counted, not changed or replaced."
            )
            dropped_msg = (
                f"Pairwise exclusion of {dropped} row(s) with missing "
                f"outcome/predictor; {len(both)} complete row(s) used."
            )
            ctx.log_decision(dropped_msg)

        if len(both) < 3:
            raise AssumptionError(
                "Simple linear regression needs at least three complete "
                "(outcome, predictor) pairs.",
                hint="Check that both columns have enough non-missing pairs.",
            )

        yv = both["outcome"].to_numpy(dtype=float)
        xv = both["predictor"].to_numpy(dtype=float)
        # A constant predictor has zero range -> the slope is undefined.
        if np.ptp(xv) == 0:
            raise AssumptionError(
                "The predictor column is constant (every value the same), so "
                "a regression slope cannot be computed.",
                hint="Choose a predictor that actually varies across rows.",
            )
        ctx.log_decision(
            f"Predictor '{predictor_name}' has non-zero range "
            f"(ptp = {np.ptp(xv):.6g}); the slope is defined."
        )

        alpha = float(params["alpha"])
        fit: Any = stats.linregress(xv, yv)

        slope = float(fit.slope)
        intercept = float(fit.intercept)
        r = float(fit.rvalue)
        r2 = float(r * r)
        p = float(fit.pvalue)
        se_slope = float(fit.stderr)
        se_intercept = float(fit.intercept_stderr)
        n = int(len(xv))
        df = n - 2

        t_crit = float(stats.t.ppf(1.0 - alpha / 2.0, df))
        slope_ci_lo = slope - t_crit * se_slope
        slope_ci_hi = slope + t_crit * se_slope
        intercept_ci_lo = intercept - t_crit * se_intercept
        intercept_ci_hi = intercept + t_crit * se_intercept

        ctx.log_decision(
            "Ordinary least squares via scipy.stats.linregress on "
            f"{n} complete rows, {df} residual degrees of freedom."
        )

        # --- coefficients table
        coeff = pd.DataFrame(
            {
                "Term": [
                    "Intercept",
                    f"Slope ({predictor_name})",
                ],
                "Estimate": [round(intercept, 6), round(slope, 6)],
                "Std. error": [round(se_intercept, 6), round(se_slope, 6)],
                "p-value": [self.fmt_p(p), self.fmt_p(p)],
                f"{(1 - alpha) * 100:.0f}% CI lower": [
                    round(intercept_ci_lo, 6),
                    round(slope_ci_lo, 6),
                ],
                f"{(1 - alpha) * 100:.0f}% CI upper": [
                    round(intercept_ci_hi, 6),
                    round(slope_ci_hi, 6),
                ],
            }
        )
        # The intercept and slope share the same regression p-value.
        result.tables["Coefficients"] = coeff

        # --- fit statistics table
        fit_stats = pd.DataFrame(
            {
                "Measure": [
                    "correlation (r)",
                    "R-squared",
                    "slope standard error",
                    "p-value (slope)",
                    "residual degrees of freedom",
                    "sample size (n)",
                ],
                "Value": [
                    round(r, 6),
                    round(r2, 6),
                    round(se_slope, 6),
                    self.fmt_p(p),
                    str(df),
                    str(n),
                ],
            }
        )
        result.tables["Fit statistics"] = fit_stats

        predicted = intercept + slope * xv
        residuals = yv - predicted

        # --- scatter with best-fit line
        scatter_fig = _scatter(
            xv, yv, predictor_name, outcome_name, slope, intercept, r2, self.fmt_p(p)
        )
        result.figures.append(
            FigureItem(
                name="regression_scatter",
                figure=scatter_fig,
                caption=(
                    f"Scatter of '{outcome_name}' vs '{predictor_name}' with "
                    f"the best-fit line y = {slope:.3f}x + {intercept:.3f} "
                    f"(R2 = {r2:.3f})"
                ),
            )
        )

        # --- residual figure (residuals vs fitted values)
        resid_fig, resid_caption = _residuals(predicted, residuals, outcome_name)
        result.figures.append(
            FigureItem(name="regression_residuals", figure=resid_fig, caption=resid_caption)
        )

        # --- summaries
        direction = "positive" if slope > 0 else ("negative" if slope < 0 else "no")
        result.summaries = {
            "slope": self.fmt_float(slope, 3),
            "intercept": self.fmt_float(intercept, 3),
            "R-squared": self.fmt_float(r2, 3),
            "p-value": self.fmt_p(p),
            "sample size": str(n),
            "slope direction": direction,
        }

        # --- methods.txt sentences
        methods = [
            "A simple linear regression was fitted to predict the outcome "
            f"'{outcome_name}' from the single predictor '{predictor_name}' "
            f"using ordinary least squares (scipy.stats.linregress) on "
            f"{n} complete rows (alpha = {alpha:.3g}).",
            f"The fitted slope was {slope:.3f} (95% CI "
            f"[{slope_ci_lo:.3f}, {slope_ci_hi:.3f}], p = {self.fmt_p(p)}), "
            f"with intercept {intercept:.3f} and R2 = {r2:.3f}.",
            f"The correlation between the two columns was r = {r:.3f}.",
        ]
        if dropped:
            methods.append(
                f"{dropped} row(s) had a missing value and were excluded "
                f"pairwise."
            )
        methods.append("No missing values were imputed in this analysis.")
        result.methods = methods

        # --- small-sample verdict
        if n < 10:
            result.add_verdict(
                "WARN", "sample-size",
                f"The regression used only {n} complete pairs. With fewer "
                "than about 10 points the slope and its confidence interval "
                "are unstable and should be treated as preliminary.",
            )
            result.add_expert_review(
                f"Only {n} complete pairs were available for the regression. "
                "Results on very small samples are unstable; please have a "
                "statistician review them before drawing conclusions."
            )
        else:
            result.add_verdict(
                "PASS", "sample-size",
                f"The regression used {n} complete pairs, a reasonable sample "
                "for an exploratory linear fit.",
            )

        ctx.log_decision(
            f"Regression fit: slope = {slope:.4f}, intercept = {intercept:.4f}, "
            f"r = {r:.4f}, R2 = {r2:.4f}, p = {p:.4g}, n = {n}."
        )

        result.what_does_not_tell = (
            "Linear regression does not prove causation: even a significant "
            "slope only shows association in this sample. R2 is not a "
            "prediction-accuracy score and says nothing about how well the "
            "line predicts new, unseen data. The fitted line is only "
            "meaningful inside the observed range of the predictor — you "
            "must not extrapolate it beyond the data."
        )
        return result


def _scatter(
    xv: np.ndarray,
    yv: np.ndarray,
    predictor_name: str,
    outcome_name: str,
    slope: float,
    intercept: float,
    r2: float,
    p_str: str,
):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    ax.scatter(xv, yv, alpha=0.6, s=26, color="#2a6f97",
               edgecolor="white", linewidth=0.4)
    xs = np.linspace(float(np.min(xv)), float(np.max(xv)), 100)
    ax.plot(xs, intercept + slope * xs, ls="--", lw=1.5, color="#b4552d",
            label="best-fit line")
    ax.set_title(
        f"'{outcome_name}' vs '{predictor_name}'\n"
        f"y = {slope:.2f}x + {intercept:.2f}, R2 = {r2:.2f}, {p_str}",
        fontsize=10,
    )
    ax.set_xlabel(predictor_name)
    ax.set_ylabel(outcome_name)
    ax.legend(fontsize=8, loc="best")
    ax.grid(ls=":", alpha=0.4)
    fig.tight_layout()
    return fig


def _residuals(predicted: np.ndarray, residuals: np.ndarray, outcome_name: str):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    ax.scatter(predicted, residuals, alpha=0.6, s=26, color="#8fc98d",
               edgecolor="white", linewidth=0.4)
    ax.axhline(0.0, color="#b4552d", lw=1.2, ls="--")
    ax.set_xlabel("fitted value")
    ax.set_ylabel("residual")
    ax.set_title(f"Residuals vs fitted values for '{outcome_name}'", fontsize=10)
    ax.grid(ls=":", alpha=0.4)
    fig.tight_layout()
    caption = (
        "Residuals against fitted values: points scattered roughly evenly "
        "around zero with no obvious curved pattern suggest a straight line "
        "is reasonable."
    )
    return fig, caption


# Module-level instance the registry looks for.
ANALYSIS = RegressionLinearAnalysis()
