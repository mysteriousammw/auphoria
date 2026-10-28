"""Pearson correlation analysis for AUPHORIA.

Computes the Pearson product-moment correlation r between two numeric columns
using SciPy's `pearsonr`, with a p-value. Missing values are excluded pairwise
(with a warning) and never imputed. A scatter figure with a labelled trend
line is produced; the trend line is clearly a visual aid, not a fitted model.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError


def _strength_label(r: float) -> str:
    ar = abs(r)
    if ar < 0.2:
        return "negligible"
    if ar < 0.4:
        return "weak"
    if ar < 0.6:
        return "moderate"
    if ar < 0.8:
        return "strong"
    return "very strong"


def _direction(r: float) -> str:
    if r > 0:
        return "positive"
    if r < 0:
        return "negative"
    return "no"


class CorrelationAnalysis(Analysis):
    id = "correlation"
    name = "Pearson Correlation"

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        result = AnalysisResult()
        x_name, y_name = inputs["x"], inputs["y"]

        if x_name not in data.columns:
            raise AssumptionError(
                f"The data has no column named '{x_name}'.",
                hint="Pick a numeric column for the first variable.",
            )
        if y_name not in data.columns:
            raise AssumptionError(
                f"The data has no column named '{y_name}'.",
                hint="Pick a numeric column for the second variable.",
            )

        x = self.ensure_numeric(data[x_name], x_name)
        y = self.ensure_numeric(data[y_name], y_name)
        self.describe_missing(x, x_name, ctx)
        self.describe_missing(y, y_name, ctx)

        both = pd.DataFrame({"x": x, "y": y})
        dropped = int(both.isna().any(axis=1).sum())
        both = both.dropna()
        if dropped:
            result.add_warning(
                f"{dropped} row(s) had a missing value in '{x_name}' or "
                f"'{y_name}' and were left out of the correlation. They were "
                "counted, not changed or replaced."
            )
            ctx.log_decision(
                f"Pairwise exclusion of {dropped} row(s) with missing x/y; "
                f"{len(both)} complete row(s) used."
            )

        if len(both) < 3:
            raise AssumptionError(
                "Correlation needs at least three complete pairs of values.",
                hint="Check that both columns have enough non-missing pairs.",
            )

        xv = both["x"].to_numpy(dtype=float)
        yv = both["y"].to_numpy(dtype=float)
        # A constant column has zero variance; Pearson r is undefined -> refuse.
        if np.std(xv) == 0 or np.std(yv) == 0:
            raise AssumptionError(
                "At least one of the variables is constant (every value the "
                "same), so a correlation coefficient cannot be computed.",
                hint="Choose columns that actually vary, or fix your data.",
            )

        tail = str(params["tail"])
        r_stat, p_val = stats.pearsonr(xv, yv, alternative=tail)
        n = int(len(xv))

        # --- result table
        result_table = pd.DataFrame(
            {
                "Variable": ["X", "Y", "Pearson correlation (r)", "p-value",
                             "sample size (n)", "direction", "strength"],
                "Value": [
                    x_name, y_name, round(float(r_stat), 6),
                    self.fmt_p(p_val), n, f"{_direction(r_stat)}",
                    f"{_strength_label(r_stat)}",
                ],
            }
        )
        result.tables["Pearson correlation"] = result_table

        # --- scatter figure
        fig = _scatter(xv, yv, x_name, y_name, r_stat, p_val)
        result.figures.append(
            FigureItem(
                name="correlation_scatter",
                figure=fig,
                caption=(
                    f"Scatter of '{y_name}' vs '{x_name}' "
                    f"(r = {r_stat:.2f}, p = {self.fmt_p(p_val)})"
                ),
            )
        )

        # --- summaries
        result.summaries = {
            "correlation r": f"{r_stat:.3f}",
            "direction": _direction(r_stat),
            "strength": _strength_label(r_stat),
            "p-value": self.fmt_p(p_val),
            "sample size": str(n),
        }

        # --- methods
        direction = _direction(r_stat)
        strength = _strength_label(r_stat)
        methods = [
            f"A Pearson product-moment correlation ({_tail_text(tail)}, n = {n}) "
            f"was computed between '{x_name}' and '{y_name}'.",
            f"The correlation was r = {r_stat:.3f}, a {strength} {direction} "
            f"relationship, with p = {self.fmt_p(p_val)}.",
        ]
        if dropped:
            methods.append(
                f"{dropped} row(s) with missing values in these columns were "
                f"excluded pairwise; no missing values were imputed."
            )
        result.methods = methods

        # --- notes
        ctx.log_decision(
            f"Pearson r = {r_stat:.4f}, p = {p_val:.4g}, n = {n} "
            f"({strength} {direction})."
        )
        result.what_does_not_tell = (
            "Correlation does not imply causation, and Pearson r only measures "
            "straight-line association — a strong non-linear relationship could "
            "hide behind a near-zero r. Outliers can also dominate the single "
            "correlation coefficient."
        )
        return result


def _tail_text(tail: str) -> str:
    return {"two-sided": "two-sided", "greater": "one-sided (greater)",
            "less": "one-sided (less)"}[tail]


def _scatter(
    xv: np.ndarray, yv: np.ndarray, x_name: str, y_name: str,
    r_stat: float, p_val: float,
):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    ax.scatter(xv, yv, alpha=0.6, s=26, color="#2a6f97", edgecolor="white", linewidth=0.4)
    # Labelled trend line: visual aid only, not a modelled fit with residuals.
    ax.plot(
        np.unique(xv),
        np.poly1d(np.polyfit(xv, yv, 1))(np.unique(xv)),
        ls="--", lw=1.5, color="#b4552d",
        label="trend line (visual aid)",
    )
    p_str = "p < 0.001" if p_val < 0.001 else f"p = {p_val:.3f}"
    ax.set_title(f"Correlation of '{y_name}' vs '{x_name}'\nr = {r_stat:.2f}, {p_str}",
                 fontsize=10)
    ax.set_xlabel(x_name)
    ax.set_ylabel(y_name)
    ax.legend(fontsize=8, loc="best")
    ax.grid(ls=":", alpha=0.4)
    fig.tight_layout()
    return fig


# Module-level instance the registry looks for.
ANALYSIS = CorrelationAnalysis()
