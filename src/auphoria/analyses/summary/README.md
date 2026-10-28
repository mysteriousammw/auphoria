# Descriptive Summary (`summary`)

The "start here" analysis. It describes your data without running any
hypothesis test, so you can check units, ranges and how much is missing
before choosing a formal test.

## What you get

- **Numeric summary** for each numeric column: `n`, `missing`, mean, median,
  standard deviation, min, first quartile, third quartile, max, IQR, range.
- **Categorical counts** for each categorical column: count and percentage
  per category (with a `missing` row when applicable).
- **Histograms** of the numeric columns.
- A `methods.txt` paragraph.

## Options

- `--outcome COL` (optional): restrict the numeric summary to one column.
  If omitted, all numeric columns are summarised.

## Notes

- Missing values are always counted and reported; never imputed or
  silently dropped.
- A descriptive summary describes your sample. It is not a significance test.

## Check

`auphoria info summary` shows the manifest. Tests
(`tests/test_summary.py`) verify the mean, median, SD, quartiles and IQR
against hand-computed values for a small numeric column, and check that
missing-value counts are reported honestly.

> Maturity: **experimental** (not "validated").