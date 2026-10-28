# {{ MODULE_NAME }}

`{{ MODULE_ID }}`

REPLACE: a plain-English description — what the analysis does, when to use it,
and one example sentence. Copy the tone of the other README files in
`src/auphoria/analyses/`.

## When to use it

- Replace this with the study designs / data shapes this analysis fits.
- State what it is **not** for (e.g. "not for paired/repeated measures on the
  same subjects").

## What you need

- `outcome` (numeric column) — the measurement you are analysing (e.g.
  `height_cm`). *(Replace with the analysis's real inputs.)*

## What you get out

- A results table.
- An optional figure.
- A paste-ready methods paragraph (`methods.txt`) and a
  [report](../index.md).

## Assumptions to check

- List each assumption and how AUPHORIA checks it (or warns).
- State a minimum sample size if relevant.

## Limitations

- What this result does **not** imply.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis {{ MODULE_ID }} --outcome <column>
```

## Example

```bash
auphoria demo --analysis {{ MODULE_ID }}
```

(Make sure a demo entry exists for this analysis in `cli/main.py` before
claiming the demo works.)