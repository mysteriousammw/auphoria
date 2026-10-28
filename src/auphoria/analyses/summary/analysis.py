"""Descriptive summary analysis for AUPHORIA.

Reports how your data looks before any formal test: counts, missing-value
counts, central tendency and spread for numeric columns, and counts /
percentages for categorical columns. No hypothesis test is run.

This is the "start here" analysis: it lets a student sanity-check their data
(units, ranges, how much is missing) before choosing a formal test.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from auphoria.advisor.advisor import profile_data_frame
from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext


def _describe(series: pd.Series, name: str) -> dict:
    """Robust descriptive stats for one numeric series.

    ``n`` is the number of non-missing values used; ``missing`` is the count
    of blanks (never imputed). Statistics are computed on non-missing values.
    """
    a_all = series.to_numpy(dtype=float)
    a = a_all[~np.isnan(a_all)]
    n = int(len(a))
    missing = int(len(a_all) - n)
    if n == 0:
        return {
            "Column": name, "n": 0, "missing": missing,
            "mean": None, "median": None, "sd": None,
            "min": None, "q1": None, "q3": None, "max": None,
        }
    return {
        "Column": name,
        "n": n,
        "missing": missing,
        "mean": round(float(np.mean(a)), 4),
        "median": round(float(np.median(a)), 4),
        "sd": round(float(np.std(a, ddof=1)), 4) if n > 1 else None,
        "min": round(float(np.min(a)), 4),
        "q1": round(float(np.quantile(a, 0.25)), 4),
        "q3": round(float(np.quantile(a, 0.75)), 4),
        "max": round(float(np.max(a)), 4),
    }


class SummaryAnalysis(Analysis):
    id = "summary"
    name = "Descriptive Summary"

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        del params
        result = AnalysisResult()

        profile = profile_data_frame(data)
        numeric_cols = [c.name for c in profile.numeric()]
        categorical_cols = [c.name for c in profile.categorical()]

        # Optional restriction to one outcome column.
        restricted = inputs.get("outcome")
        if restricted:
            if restricted not in data.columns:
                from auphoria.core.errors import AssumptionError
                raise AssumptionError(
                    f"Could not find the column '{restricted}'.",
                    hint="Available columns: " + ", ".join(map(str, data.columns)) + ".",
                )
            if restricted not in numeric_cols:
                # It exists but is not numeric: try hard, refuse if text.
                from auphoria.core.errors import AssumptionError
                if self.ensure_numeric(data[restricted], restricted).notna().sum() < 1:
                    raise AssumptionError(
                        f"Column '{restricted}' has no numeric values to summarise.",
                        hint="Pick a numeric column for the outcome.",
                    )
                numeric_cols = [restricted]
            else:
                numeric_cols = [restricted]

        # ---- numeric stats table
        if numeric_cols:
            rows = []
            for col in numeric_cols:
                series = self.ensure_numeric(data[col], col)
                self.describe_missing(series, col, ctx)
                stats_row = _describe(series, col)
                stats_row["iqr"] = round(float(np.quantile(series.dropna(), 0.75)
                                               - np.quantile(series.dropna(), 0.25)), 4)
                stats_row["range"] = round(float(np.max(series.dropna())
                                                 - np.min(series.dropna())), 4)
                rows.append(stats_row)
            t = pd.DataFrame(rows)[
                ["Column", "n", "missing", "mean", "median", "sd",
                 "min", "q1", "q3", "max", "iqr", "range"]
            ]
            result.tables["Numeric summary"] = t

        # ---- categorical counts table
        if categorical_cols:
            count_rows = []
            for col in categorical_cols:
                vc = data[col].value_counts(dropna=False)
                total = int(vc.sum())
                for value, count in vc.items():
                    label = "missing" if pd.isna(value) else str(value)
                    count_rows.append({
                        "Column": col, "Category": label,
                        "count": int(count),
                        "percent": round(100.0 * count / total, 2) if total else 0.0,
                    })
            result.tables["Categorical counts"] = pd.DataFrame(count_rows)[
                ["Column", "Category", "count", "percent"]
            ]

        # ---- figures
        fig = _histograms(data, numeric_cols, restricted)
        if fig is not None:
            result.figures.append(
                FigureItem(
                    name="summary_histograms",
                    figure=fig,
                    caption="Histograms of the numeric column(s) described"
                            + (f": {restricted}" if restricted else "s"),
                )
            )

        # ---- summaries card
        if numeric_cols:
            result.summaries = {
                "numeric columns": ", ".join(numeric_cols) if len(numeric_cols) <= 4
                else f"{len(numeric_cols)} columns",
                "categorical columns": ", ".join(categorical_cols) if categorical_cols
                else "none",
                "missing values": str(int(data.isna().sum().sum())),
            }

        # ---- methods
        methods = [
            "Descriptive statistics were computed for each numeric column: "
            "n, missing count, mean, median, standard deviation, minimum, "
            "first quartile, third quartile, maximum, interquartile range and "
            "range. Counts and percentages are reported for categorical "
            "columns. All statistics were computed on available (non-missing) "
            "values; missing values were counted and reported, never imputed."
        ]
        if restricted:
            methods.append(
                f"The summary was restricted to the outcome column "
                f"'{restricted}'."
            )
        result.methods = methods
        ctx.log_decision(
            f"Summarised numeric columns {numeric_cols}, categorical "
            f"{categorical_cols}; {int(data.isna().sum().sum())} total missing cell(s)."
        )
        result.what_does_not_tell = (
            "Descriptive statistics describe this dataset only; they are not a "
            "significance test and cannot be generalised to a wider population. "
            "Outliers and small samples can make means and ranges misleading — "
            "read them alongside the QC flags."
        )
        return result


def _histograms(data: pd.DataFrame, numeric_cols: list[str], restricted: str | None):
    import matplotlib.pyplot as plt

    cols = numeric_cols
    if not cols:
        return None
    n = len(cols)
    if n > 8:
        return None  # keep the report light for very wide data
    ncols = 2
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(9, 3 * nrows + 1))
    axes = np.atleast_1d(axes).ravel()
    for ax, col in zip(axes, cols, strict=False):
        a = pd.to_numeric(data[col], errors="coerce").dropna()
        ax.hist(a, bins="auto", color="#2a6f97", edgecolor="white", alpha=0.85)
        ax.set_title(col, fontsize=9)
        ax.set_xlabel(col)
        ax.set_ylabel("count")
        ax.grid(axis="y", ls=":", alpha=0.4)
    for j in range(n, len(axes)):
        axes[j].axis("off")
    fig.suptitle("Distributions of numeric columns", fontsize=11)
    fig.tight_layout()
    return fig


# Module-level instance the registry looks for.
ANALYSIS = SummaryAnalysis()
