# Describe My Data (`describe`)

The "look before you leap" analysis. It reads your whole data file and reports
a **data card**: how many rows and columns, what each column probably is, how
much is missing, duplicate or constant columns, and any value-level concerns
flagged for your review (suspected outliers, suspicious values like negative
ages).

It never tests a hypothesis and never changes or removes anything.

## What you get

- **Data card table**: one row per column with its detected type
  (numeric / ordinal / binary / categorical / date / id / free text), value
  count, unique count, missing count, and a *suggested role*
  (outcome / group / covariate / id / time / weight).
- **Dataset overview**: rows, columns, duplicate rows.
- **Verdicts (PASS / WARN / FAIL)**: whether rows are present, whether
  duplicates or missing values exist, whether any constant columns or flagged
  values are present.
- **A plain-English "what this does not tell you"** so you do not over-read it.

## When to run it

Always, before anything else. It is the fastest way to notice a typo, an
impossible value, a renamed column, or the fact that a column never changes —
before that quietly produces a wrong analysis.

## Notes

- Types and roles are *guesses* for you to confirm or correct.
- Outliers are flagged by the 1.5× IQR rule; a flag means "please look", never
  "this is wrong" — and AUPHORIA will not delete the value.
- Duplicate rows and missing cells are counted and kept, never silently
  dropped.

## Check

`auphoria info describe` shows the manifest. Tests
(`tests/test_describe.py`) use a hand-built mixed-type data frame with
deliberately inserted missing values, a duplicate row, a constant column, an
outlier and a negative age, and confirm every one is caught and reported while
the data are left untouched.

> Maturity: **experimental** (not "validated").