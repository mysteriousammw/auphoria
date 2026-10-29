# Time-Series Decomposition & Trend

Splits a single numeric **value** column observed over a **period** column
(real dates or datetimes) into additive **trend**, **seasonal** and
**residual** components, and fits a simple linear trend so you can judge
whether the series drifts up, down or stays flat over time.

One figure is produced: a four-panel decomposition — observed series, trend,
seasonal pattern, and residual (noise).

## When to use it

Use it when you have **one numeric value measured repeatedly over time** — for
example monthly sales, daily temperature, or quarterly revenue — and you want
to separate the underlying drift from a repeating seasonal pattern.

Requires `statsmodels`: `pip install "auphoria[life-science]"`.

## Inputs

| Role     | Kind             | Required | Description                                          |
|----------|------------------|----------|------------------------------------------------------|
| `period` | datetime-column  | yes      | The date/datetime column ordering the observations.  |
| `value`  | numeric-column   | yes      | The numeric value measured at each period.           |

## Parameter

| Name             | Type    | Default | Description                                                         |
|------------------|---------|---------|---------------------------------------------------------------------|
| `seasonal_period`| integer | 12      | Observations in one full seasonal cycle (12 = monthly over a year). |

## Outputs

- **Decomposition summary** — sample size, overall mean, trend mean, seasonal
  amplitude (peak-to-trough), and the fitted linear-trend slope + p-value.
- **Seasonal statistics** — the mean seasonal component for each position in
  the cycle.
- **Decomposition figure** — observed, trend, seasonal, and residual panels.
- **methods.txt** paragraph and **report.html**.

## Under the hood

The series is sorted by period and split with
`statsmodels.tsa.seasonal.seasonal_decompose` using an **additive** model
(`observed = trend + seasonal + residual`). A simple linear trend is also fit
with `scipy.stats.linregress` on the observation index to report the average
change per observation and its p-value.

## Guardrails

- The **period column must be dates/datetimes**; otherwise the analysis is
  refused.
- At least **2 × `seasonal_period`** rows are required (two full seasonal
  cycles); fewer is refused.
- A **constant value** column (zero range) is refused.
- Missing values are counted and excluded (with a warning), **never imputed**.
- When `seasonal_period ≥ n / 2` the decomposition rests on fewer than two
  full cycles and flags for statistician review.

## What this result does NOT tell you

Decomposition only describes how this series splits into trend, seasonal and
residual parts — it does **not** forecast future values. The seasonal
component is the periodic average of *this* series, not evidence of a causal
seasonal driver, and a non-stationary series (changing level or variance)
needs differencing or modelling before the trend slope is read as a reliable
rate of change.

## Dependencies

`requires: [statsmodels]` — statsmodels (seasonal_decompose) plus the core
permissive stack (numpy, pandas, scipy, matplotlib).