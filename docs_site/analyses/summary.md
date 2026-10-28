# Descriptive Summary

`summary` · maturity: **experimental**

Validation reference: Hand-computed descriptive stats on small numeric columns  


## What it does

Summarises your data without any hypothesis test. For each numeric column it reports counts, missing values, mean, median, standard deviation, quartiles and range; for each categorical column it reports counts and percentages. Use this first to check that your data looks sensible.

## What you need

- **outcome** (numeric-column, optional): Optional. Restrict the numeric summary to this one column. If omitted, all numeric columns are summarised.


## What you get out

- summary statistics table
- categorical counts table
- histogram figure for numeric columns
- methods.txt paragraph
- report.html

## Assumptions

- The data is already tidy, where each column is one variable and each row is one observation.

## Limitations

- Descriptive summaries describe only the sample; they do not generalise to a population by themselves.
- Statistics are computed on available (non-missing) values; missing counts are reported separately and never imputed.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis summary
```
