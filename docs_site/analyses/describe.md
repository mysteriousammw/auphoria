# Describe My Data

`describe` · maturity: **experimental**

Validation reference: Hand-built mixed-type frame with deliberately inserted problems  


## What it does

The data card: a supervisor-style read of your whole data file before any test. It reports how many rows/columns, what each column is (number, category, date, id, text...), how much is missing, duplicate or constant columns, and flags suspected outliers and suspicious values (e.g. negative ages) for you to review. It never changes or removes anything.

## What you get out

- data card table (column, type, values, unique, missing, suggested role)
- dataset overview table (rows, columns, duplicate rows)
- flags list (duplicate rows, constant columns, outliers, suspicious values)
- methods.txt paragraph
- report.html

## Assumptions

- The data is already tidy - each column is one variable and each row is one observation.

## Limitations

- Type labels and role suggestions are best-effort guesses; the interactive flow asks you to confirm or correct them.
- Outliers and suspicious values are flagged for your review, never removed; a "flag" is not proof something is wrong.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis describe
```
