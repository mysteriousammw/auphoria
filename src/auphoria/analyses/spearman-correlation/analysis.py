"""Spearman rank correlation analysis for AUPHORIA.

Computes Spearman's rank correlation coefficient rho between two numeric
columns using SciPy's `spearmanr` (which works on the ranks), with a p-value
and the requested tail. Missing values are excluded pairwise (with a warning)
and never imputed. A scatter figure of the *ranks* is produced, annotated
with rho; a light trend line is a visual aid only.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError


def _strength_label(rho: float) -> str:
    ar = abs(rho)
    if ar < 0.2:
        return "negligible"
    if ar < 0.5:
        return "weak"
    if ar < 0.8:
        return "moderate"
    return "strong"


def _direction(rho: float) -> str:
    if rho > 0:
        return "positive"
    if rho < 0:
        return "negative"
    return "no"


class SpearmanCorrelationAnalysis(Analysis):
    id = "spearman-correlation"
    name = "Spearman Rank Correlation"

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
                "Spearman correlation needs at least three complete pairs "
                "of values.",
                hint="Check that both columns have enough non-missing pairs.",
            )

        xv = both["x"].to_numpy(dtype=float)
        yv = both["y"].to_numpy(dtype=float)
        # A constant column has zero variance; a rank correlation is undefined
        # (every value ranks equal) -> refuse.
        if np.std(xv) == 0 or np.std(yv) == 0:
            raise AssumptionError(
                "At least one of the variables is constant (every value the "
                "same), so a correlation coefficient cannot be computed.",
                hint="Choose columns that actually vary, or fix your data.",
            )

        tail = str(params["tail"])
        alpha = float(params["alpha"])

        rho_stat, p_val = stats.spearmanr(xv, yv, alternative=tail)
        rho_stat = float(rho_stat)
        p_val = float(p_val)
        n = int(len(xv))
        significant = bool(not np.isnan(p_val) and p_val < alpha)

        p_display = self.fmt_p(p_val)
        if np.isnan(p_val):
            # All ranks tied -> SciPy cannot produce a p-value; report NA.
            p_display = "NA"
            result.add_warning(
                "All ranks were tied, so no p-value could be computed "
                "(reported as 'NA'). Treat rho as descriptive only."
            )

        # Heavy ties distort rho: warn whenever under half the observations
        # have distinct values in either column.
        for col, name in ((xv, x_name), (yv, y_name)):
            ties = n - len(np.unique(col))
            if n and ties / n >= 0.5:
                result.add_warning(
                    f"'{name}' has many tied values ({ties} of {n} "
                    "observations share ranks). Heavy ties can distort "
                    "Spearman's rho, so treat it with caution."
                )

        # --- result table
        result_table = pd.DataFrame(
            {
                "Variable": ["X", "Y", "Spearman rho", "p-value",
                             "sample size (n)", "direction", "strength"],
                "Value": [
                    x_name, y_name, round(rho_stat, 6), p_display, n,
                    f"{_direction(rho_stat)}", f"{_strength_label(rho_stat)}",
                ],
            }
        )
        result.tables["Spearman correlation"] = result_table

        # --- scatter figure of the ranks
        fig = _rank_scatter(xv, yv, x_name, y_name, rho_stat, p_display)
        result.figures.append(
            FigureItem(
                name="spearman_rank_scatter",
                figure=fig,
                caption=(
                    f"Scatter of the ranks of '{y_name}' vs the ranks of "
                    f"'{x_name}' (rho = {rho_stat:.2f}, p = {p_display})"
                ),
            )
        )

        # --- summaries
        result.summaries = {
            "Spearman rho": f"{rho_stat:.3f}",
            "direction": _direction(rho_stat),
            "strength": _strength_label(rho_stat),
            "p-value": p_display,
            "sample size": str(n),
            "significant at alpha": f"{alpha:.3f} → {'Yes' if significant else 'No'}",
        }

        # --- methods
        direction = _direction(rho_stat)
        strength = _strength_label(rho_stat)
        methods = [
            f"A Spearman rank correlation ({_tail_text(tail)}, n = {n}) "
            f"was computed between '{x_name}' and '{y_name}', working on the "
            "ranks of both variables.",
            f"The correlation was rho = {rho_stat:.3f}, a {strength} "
            f"{direction} monotonic relationship, with p = {p_display}.",
            "Spearman relies on ranks, so it does not assume a straight-line "
            "relationship or normality, only a steady (monotonic) tendency.",
        ]
        if dropped:
            methods.append(
                f"{dropped} row(s) with missing values in these columns were "
                f"excluded pairwise; no missing values were imputed."
            )
        result.methods = methods

        # --- notes
        ctx.log_decision(
            f"Spearman rho = {rho_stat:.4f}, p = {p_val:.4g}, n = {n} "
            f"({strength} {direction}); worked on ranks, "
            f"alternative={tail}."
        )
        result.what_does_not_tell = (
            "Correlation does not imply causation, and Spearman's rho only "
            "captures monotonic association — a U-shaped or otherwise "
            "curved relationship could hide behind a near-zero rho. rho "
            "also measures whether variables move together when ranked, not "
            "how *much* they move: ranks hide effect sizes, so a strong rho "
            "does not tell you the size of the effect."
        )
        return result


def _tail_text(tail: str) -> str:
    return {"two-sided": "two-sided", "greater": "one-sided (greater)",
            "less": "one-sided (less)"}[tail]


def _rank_scatter(
    xv: np.ndarray, yv: np.ndarray, x_name: str, y_name: str,
    rho_stat: float, p_display: str,
):
    import matplotlib.pyplot as plt

    xr = stats.rankdata(xv)
    yr = stats.rankdata(yv)
    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    ax.scatter(xr, yr, alpha=0.6, s=26, color="#2a6f97", edgecolor="white",
               linewidth=0.4)
    # Light trend line on the ranks: visual aid only, not a modelled fit.
    ax.plot(
        np.unique(xr),
        np.poly1d(np.polyfit(xr, yr, 1))(np.unique(xr)),
        ls="--", lw=1.5, color="#b4552d",
        label="rank trend (visual aid)",
    )
    ax.set_title(
        f"Ranks of '{y_name}' vs ranks of '{x_name}'\nrho = {rho_stat:.2f}, "
        f"p = {p_display}",
        fontsize=10,
    )
    ax.set_xlabel(f"rank of '{x_name}'")
    ax.set_ylabel(f"rank of '{y_name}'")
    ax.legend(fontsize=8, loc="best")
    ax.grid(ls=":", alpha=0.4)
    fig.tight_layout()
    return fig


# Module-level instance the registry looks for.
ANALYSIS = SpearmanCorrelationAnalysis()
