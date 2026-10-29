"""Time-series decomposition and trend analysis for AUPHORIA.

Splits a single numeric ``value`` column observed over a ``period`` column
(dates or datetimes) into additive **trend / seasonal / residual** components
using `statsmodels.tsa.seasonal.seasonal_decompose`, and fits a simple linear
trend (scipy.stats.linregress on the observation index) so the student can
judge whether there is an upward/downward drift.

Guardrails are enforced here, not in the front end:
- ``period`` must be datetime-like and both columns must exist;
- rows are sorted by ``period`` before decomposition;
- at least ``2 * seasonal_period`` rows are required (seasonality needs at
  least two full cycles);
- a constant ``value`` column (zero range) is refused;
- missing values in either column are counted and excluded with a warning,
  never imputed.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError


class TimeSeriesAnalysis(Analysis):
    id = "time-series"
    name = "Time-Series Decomposition & Trend"

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        result = AnalysisResult()
        period_name = inputs["period"]
        value_name = inputs["value"]

        for col in (period_name, value_name):
            if col not in data.columns:
                raise AssumptionError(
                    f"The data has no column named '{col}'.",
                    hint="Pick a column from your file.",
                )

        seasonal_period = int(params.get("seasonal_period", 12))
        if seasonal_period < 2:
            raise AssumptionError(
                "The seasonal period must be at least 2.",
                hint="Choose a period (e.g. 12 for monthly data over a year).",
            )

        # --- period must be datetime-like --------------------------------
        raw_period = data[period_name]
        if pd.api.types.is_datetime64_any_dtype(raw_period):
            period = pd.Series(pd.to_datetime(raw_period), name=period_name)
        else:
            parsed = pd.to_datetime(raw_period, errors="coerce")
            nonnull = raw_period.notna() & parsed.isna()
            if nonnull.any() or parsed.isna().all():
                raise AssumptionError(
                    "The period column must be dates or datetimes "
                    f"(column '{period_name}' could not be read as dates).",
                    hint=(
                        "Make sure that column holds dates/times (e.g. "
                        "2024-01-15), then choose it as the period column."
                    ),
                )
            period = pd.Series(parsed, name=period_name)
        ctx.log_decision(
            f"Period column '{period_name}' was read as datetime."
        )

        value = self.ensure_numeric(data[value_name], value_name)
        self.describe_missing(value, value_name, ctx)

        # --- pair rows, dropna (counted, never imputed) -------------------
        frame = pd.DataFrame({period_name: period, value_name: value})
        dropped = int(frame.isna().any(axis=1).sum())
        frame = frame.dropna().sort_values(period_name).reset_index(drop=True)
        if dropped:
            result.add_warning(
                f"{dropped} row(s) had a missing value in '{value_name}' or "
                f"'{period_name}' and were left out of the analysis. They "
                "were counted, not changed or replaced."
            )
            ctx.log_decision(
                f"Dropped {dropped} row(s) with missing period/value; "
                f"{len(frame)} complete row(s) kept. Missing values are "
                "never imputed."
            )

        n = len(frame)
        min_rows = 2 * seasonal_period
        if n < min_rows:
            raise AssumptionError(
                f"Time-series decomposition needs at least "
                f"{min_rows} rows (2 x seasonal_period = 2 x "
                f"{seasonal_period}), but only {n} complete row(s) were "
                "available.",
                hint=(
                    "Provide at least two full seasonal cycles, or lower the "
                    "seasonal period in the parameters."
                ),
            )
        ctx.log_decision(
            f"{n} complete rows sorted by '{period_name}' "
            f"(>= {min_rows} required for seasonal_period={seasonal_period})."
        )

        vals = frame[value_name].to_numpy(dtype=float)
        if np.ptp(vals) == 0:
            raise AssumptionError(
                "The value column is constant (every value the same), so "
                "there is no trend or seasonality to decompose.",
                hint="Choose a value column that actually varies over time.",
            )
        ctx.log_decision(
            f"Value column '{value_name}' has non-zero range "
            f"(ptp = {np.ptp(vals):.6g})."
        )

        # --- decomposition (additive) ------------------------------------
        series = pd.Series(vals, index=frame[period_name], name=value_name)
        decomp = _decompose(series, seasonal_period)

        trend = decomp.trend  # pandas Series with same index
        seasonal = decomp.seasonal
        resid = decomp.resid
        ctx.log_decision(
            "Additive seasonal decomposition applied via "
            "statsmodels.tsa.seasonal.seasonal_decompose with "
            f"period={seasonal_period}."
        )

        seasonal_amp = float(seasonal.max() - seasonal.min())
        overall_mean = float(vals.mean())
        trend_mean = float(trend.mean())

        # --- simple linear trend (value vs observation index) -------------
        time_idx = np.arange(float(n))
        lin: Any = stats.linregress(time_idx, vals)
        slope = float(lin.slope)
        p_value = float(lin.pvalue)
        ctx.log_decision(
            "Linear trend fitted by scipy.stats.linregress on the "
            f"observation index: slope = {slope:.4f} (p = {p_value:.4g})."
        )

        # --- decomposition summary table ----------------------------------
        summary_rows = pd.DataFrame(
            {
                "Measure": [
                    "sample size (n)",
                    "overall mean",
                    "trend mean",
                    "seasonal amplitude",
                    "trend slope (per observation)",
                    "trend slope p-value",
                ],
                "Value": [
                    str(n),
                    self.fmt_float(overall_mean, 4),
                    self.fmt_float(trend_mean, 4),
                    self.fmt_float(seasonal_amp, 4),
                    self.fmt_float(slope, 5),
                    self.fmt_p(p_value),
                ],
            }
        )
        result.tables["Decomposition summary"] = summary_rows

        # --- seasonal statistics (mean seasonal component per period) -----
        per_pos = np.arange(n) % seasonal_period
        season_period_stats = []
        for pos in range(seasonal_period):
            pos_values = seasonal.to_numpy()[per_pos == pos]
            season_period_stats.append(
                {"Seasonal position": int(pos) + 1, "Mean seasonal component": round(float(pos_values.mean()), 6)}
            )
        result.tables["Seasonal statistics"] = pd.DataFrame(season_period_stats)

        # --- decomposition figure (4 subplots) ----------------------------
        fig, caption = _decomposition_figure(
            series, trend, seasonal, resid, value_name, period_name
        )
        result.figures.append(
            FigureItem(name="time_series_decomposition", figure=fig, caption=caption)
        )

        # --- summaries -----------------------------------------------------
        direction = "positive" if slope > 0 else ("negative" if slope < 0 else "no")
        result.summaries = {
            "seasonal period": str(seasonal_period),
            "seasonal amplitude": self.fmt_float(seasonal_amp, 3),
            "trend slope": self.fmt_float(slope, 4),
            "trend p-value": self.fmt_p(p_value),
            "trend direction": direction,
            "sample size": str(n),
        }

        # --- methods.txt sentences -----------------------------------------
        methods = [
            "The time series was sorted by the period column "
            f"'{period_name}' and decomposed into additive trend, seasonal "
            f"and residual components using statsmodels seasonal_decompose "
            f"with period = {seasonal_period}, on {n} complete "
            "observations.",
            f"The seasonal component had amplitude "
            f"{seasonal_amp:.3f} (peak-to-trough), with an overall mean of "
            f"{overall_mean:.3f}.",
            f"A simple linear trend fitted to the observation index gave a "
            f"slope of {slope:.4f} per observation (p = {self.fmt_p(p_value)}).",
        ]
        if dropped:
            methods.append(
                f"{dropped} row(s) with missing period/value were excluded "
                "and counted; none were imputed."
            )
        methods.append("No missing values were imputed in this analysis.")
        result.methods = methods

        # --- verdicts + expert review --------------------------------------
        if seasonal_period >= n // 2:
            result.add_verdict(
                "WARN", "season-length",
                f"With only {n} observations and a seasonal period of "
                f"{seasonal_period}, there are fewer than two full seasonal "
                "cycles, so the estimated seasonality is unreliable.",
            )
            result.add_expert_review(
                f"The seasonal period ({seasonal_period}) is large relative "
                f"to the number of observations ({n}); the decomposition "
                "rests on fewer than two full cycles and the seasonal "
                "component should be reviewed by a statistician before "
                "conclusions are drawn."
            )
        else:
            result.add_verdict(
                "PASS", "season-length",
                f"The series has {n} observations for a seasonal period of "
                f"{seasonal_period}, providing at least two full cycles — "
                "seasonal_decompose is appropriate.",
            )

        ctx.log_decision(
            f"Decomposition produced seasonal amplitude {seasonal_amp:.4f} "
            f"and linear-trend slope {slope:.4f} (p = {p_value:.4g})."
        )

        result.what_does_not_tell = (
            "Decomposition only describes how this series splits into "
            "trend, seasonal and residual parts — it does not forecast "
            "future values. The seasonal component is the periodic average "
            "of this series, not evidence of a causal seasonal driver. "
            "Strongly non-stationary series (changing variance or level) "
            "need differencing or modelling before the trend slope is "
            "interpreted as a reliable rate of change."
        )
        return result


def _decompose(series: pd.Series, seasonal_period: int):
    """Run additive seasonal decomposition, importing statsmodels lazily."""
    from statsmodels.tsa.seasonal import seasonal_decompose

    return seasonal_decompose(series, model="additive", period=seasonal_period)


def _decomposition_figure(series, trend, seasonal, resid, value_name, period_name):
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(4, 1, sharex=True, figsize=(9, 10))
    axes[0].plot(series.index, series.to_numpy(), ls="-", lw=1.2, color="#2a6f97")
    axes[0].set_ylabel("observed")
    axes[0].set_title(f"Time-series decomposition of '{value_name}'", fontsize=11)
    axes[0].grid(ls=":", alpha=0.4)

    axes[1].plot(trend.index, trend.to_numpy(), ls="-", lw=1.5, color="#b4552d")
    axes[1].set_ylabel("trend")
    axes[1].grid(ls=":", alpha=0.4)

    axes[2].plot(seasonal.index, seasonal.to_numpy(), ls="-", lw=1.2, color="#6a994e")
    axes[2].set_ylabel("seasonal")
    axes[2].grid(ls=":", alpha=0.4)

    axes[3].plot(resid.index, resid.to_numpy(), ls="-", lw=1.0, color="#8d99ae")
    axes[3].set_ylabel("residual")
    axes[3].set_xlabel(period_name)
    axes[3].grid(ls=":", alpha=0.4)

    fig.tight_layout()
    caption = (
        "Four-panel decomposition: observed series, the smoothed trend, the "
        "repeatable seasonal pattern, and the leftover residual (noise). A "
        "trend panel that slopes up/down indicates drift; a roughly "
        "horizontal residual around zero suggests the additive split is "
        "reasonable."
    )
    return fig, caption


# Module-level instance the registry looks for.
ANALYSIS = TimeSeriesAnalysis()
