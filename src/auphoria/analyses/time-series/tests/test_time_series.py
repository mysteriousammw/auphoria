"""Tests for the time-series decomposition analysis.

Builds a deterministic reference series
``value = 0.2*t + 3*sin(2*pi*t/12) + noise`` over 120 points with a fixed seed
(seasonal_period=12). The additive decomposition should recover a seasonal
amplitude of about 6 (max - min of ``3*sin`` over one period) and the fitted
linear trend slope should be about 0.2. The module is loaded the way the
registry does (importlib) because the folder name contains a hyphen and cannot
be imported directly.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from auphoria.core.analysis import RunContext
from auphoria.core.errors import AssumptionError

MOD = importlib.import_module("auphoria.analyses.time-series.analysis")
TimeSeriesAnalysis = MOD.TimeSeriesAnalysis

SEASONAL_PERIOD = 12
N = 120  # 10 full cycles


def _reference_series() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    t = np.arange(N, dtype=float)
    value = 0.2 * t + 3.0 * np.sin(2 * np.pi * t / 12.0) + rng.normal(0, 0.2, size=N)
    dates = pd.date_range("2020-01-01", periods=N, freq="MS")
    return pd.DataFrame({"date": dates, "value": value})


def _ctx() -> RunContext:
    logger = logging.getLogger("auphoria_test_time_series")
    logger.handlers = []
    return RunContext(
        seed=1, out_dir=Path("."), data_name="test", expert=False,
        _log=logger, _log_decision=lambda m: None,
    )


def _run(df: pd.DataFrame, params: dict | None = None):
    analysis = TimeSeriesAnalysis()
    return analysis.run(
        df,
        params or {"seasonal_period": SEASONAL_PERIOD},
        {"period": "date", "value": "value"},
        _ctx(),
    )


def test_matches_trend_slope_and_seasonal_amplitude():
    """Reference series -> trend slope ~0.2 and seasonal amplitude ~6."""
    result = _run(_reference_series())

    summary = result.tables["Decomposition summary"].set_index("Measure")
    slope = float(summary.loc["trend slope (per observation)", "Value"])
    amplitude = float(summary.loc["seasonal amplitude", "Value"])

    assert slope == pytest.approx(0.2, abs=0.01)
    assert amplitude == pytest.approx(6.0, abs=0.3)

    # Trend slope also matches scipy on the observation index.
    df = _reference_series()
    vals = df["value"].to_numpy(dtype=float)
    ref_slope = float(stats.linregress(np.arange(N, dtype=float), vals).slope)
    assert slope == pytest.approx(ref_slope, abs=1e-4)  # table stores 5 dp

    # Trend p-value is very small for a clear upward drift.
    p_text = str(summary.loc["trend slope p-value", "Value"])
    assert p_text == "< 0.001" or float(p_text) < 0.01


def test_decomposition_components_right_length():
    """trend / seasonal / resid rows line up with the (sorted) input rows."""
    result = _run(_reference_series())
    # The four panels in the figure correspond to observed/trend/seasonal/resid.
    assert len(result.figures) == 1
    fig = result.figures[0].figure
    assert len(fig.axes) == 4

    # seasonal statistics cover exactly one season.
    seasonal_stats = result.tables["Seasonal statistics"]
    assert len(seasonal_stats) == SEASONAL_PERIOD

    # seasonal component is fully filled (periodic) -> no NaN.
    detail = _decomposed(result)
    assert not np.isnan(detail["seasonal"]).all()


def _decomposed(result):
    """Re-run the deterministic decomposition to introspect component arrays."""
    from statsmodels.tsa.seasonal import seasonal_decompose

    df = _reference_series()
    series = pd.Series(
        df["value"].to_numpy(dtype=float), index=df["date"]
    )
    decomp = seasonal_decompose(series, model="additive", period=SEASONAL_PERIOD)
    return {
        "trend": decomp.trend.to_numpy(),
        "seasonal": decomp.seasonal.to_numpy(),
        "resid": decomp.resid.to_numpy(),
    }


def test_refuses_too_few_rows():
    """Fewer than 2 x seasonal_period rows is refused."""
    analysis = TimeSeriesAnalysis()
    df = _reference_series().iloc[: 2 * SEASONAL_PERIOD - 1]
    with pytest.raises(AssumptionError):
        analysis.run(
            df, {"seasonal_period": SEASONAL_PERIOD},
            {"period": "date", "value": "value"}, _ctx(),
        )


def test_refuses_constant_value():
    """A constant value column (zero range) is refused."""
    analysis = TimeSeriesAnalysis()
    dates = pd.date_range("2020-01-01", periods=N, freq="MS")
    df = pd.DataFrame({"date": dates, "value": np.full(N, 5.0)})
    with pytest.raises(AssumptionError):
        analysis.run(
            df, {"seasonal_period": SEASONAL_PERIOD},
            {"period": "date", "value": "value"}, _ctx(),
        )


def test_refuses_non_datetime_period():
    """A non-date period column is refused with AssumptionError."""
    analysis = TimeSeriesAnalysis()
    over_time = pd.date_range("2020-01-01", periods=N, freq="MS")
    df = pd.DataFrame(
        {"date": ["not-a-date"] * N, "value": np.arange(N, dtype=float)},
        index=over_time,
    )
    with pytest.raises(AssumptionError):
        analysis.run(
            df, {"seasonal_period": SEASONAL_PERIOD},
            {"period": "date", "value": "value"}, _ctx(),
        )


def test_dropna_warns_and_never_imputes():
    analysis = TimeSeriesAnalysis()
    df = _reference_series()
    df.iloc[0, 1] = np.nan
    result = analysis.run(
        df, {"seasonal_period": SEASONAL_PERIOD},
        {"period": "date", "value": "value"}, _ctx(),
    )
    summary = result.tables["Decomposition summary"].set_index("Measure")
    assert int(summary.loc["sample size (n)", "Value"]) == N - 1
    assert any("missing" in w for w in result.warnings)
    assert any("not imputed" in m or "imputed" in m for m in result.methods)


def test_figure_methods_and_what_does_not_tell_present():
    result = _run(_reference_series())
    names = [f.name for f in result.figures]
    assert names == ["time_series_decomposition"]
    # four subplots: observed, trend, seasonal, residual.
    assert len(result.figures[0].figure.axes) == 4
    assert any("decompos" in m for m in result.methods)
    text = result.what_does_not_tell
    assert text  # non-empty
    assert "forecast" in text.lower()
    assert "causal" in text.lower()


def test_expert_review_when_season_too_short():
    """seasonal_period >= n/2 => WARN verdict + expert review banner."""
    # 24 rows with seasonal_period = 12 -> 12 >= 24//2 -> flagged.
    df = _reference_series().iloc[:24]
    analysis = TimeSeriesAnalysis()
    outcome = analysis.run(
        df, {"seasonal_period": SEASONAL_PERIOD},
        {"period": "date", "value": "value"}, _ctx(),
    )
    verdicts = {v.check: v.level for v in outcome.verdicts}
    assert verdicts["season-length"] == "WARN"
    assert outcome.expert_review


def test_adequate_season_length_pass_verdict():
    result = _run(_reference_series())  # 120 rows, period 12 -> no flag.
    verdicts = {v.check: v.level for v in result.verdicts}
    assert verdicts["season-length"] == "PASS"
    assert not result.expert_review
