# Time-Series Decomposition & Trend

`time-series` · maturity: **experimental**

Discipline packs: `econ-eng`, `life-science`  

Validation reference: Hand-computed reference on a deterministic series value = 0.2*t + 3*sin(2*pi*t/12) + noise over 120 points (seasonal_period=12): the fitted trend slope recovers ~0.2 and the seasonal amplitude recovers the sine's 6 (max-min over one period). Verified in tests/test_time_series.py and cross-checked vs scipy.stats.linregress.  


## What it does

Splits a single numeric value column observed over a date/datetime period column into additive trend, seasonal and residual components, and fits a simple linear trend so you can judge whether the series drifts up, down or stays flat. Reports a decomposition summary, seasonal statistics, and a four-panel decomposition figure.

## What you need

- **period** (datetime-column, required): The date/datetime column that orders your observations (e.g. date).
- **value** (numeric-column, required): The numeric value measured at each period (e.g. monthly_sales).

## Options

- `seasonal_period` (default 12): Number of observations in one full seasonal cycle (e.g. 12 for monthly data over a year).

## What you get out

- decomposition summary table (n, mean, trend mean, seasonal amplitude, trend slope + p)
- seasonal statistics table (mean seasonal component per period)
- four-panel decomposition figure (observed, trend, seasonal, residual)
- methods.txt paragraph
- report.html

## Assumptions

- Both columns must exist; the period column must be dates or datetimes.
- The value is measured at equally spaced periods; at least two full seasonal cycles (2 x seasonal_period rows) are required.
- The seasonal pattern repeats additively over time (additive model); a pattern whose size grows with the level may need a multiplicative model.
- The series is roughly stationary apart from trend/seasonality; strong changes in variance or level need differencing or modelling first.

## Limitations

- Decomposition is descriptive, not forecasting; it does not predict future values.
- The seasonal component is a periodic average, not evidence of a causal seasonal driver.
- With fewer than two full seasonal cycles the seasonal component is unreliable.
- The linear-trend slope describes this series only and should not be extrapolated far beyond the observed range.
- Missing values are excluded (and reported), never imputed.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis time-series --extra period=<period> --extra value=<value>
```
