---
name: Wrong result / incorrect statistic
about: Report an analysis producing a number that does not match an independent reference.
title: "[wrong result] <analysis-id>: <short description>"
labels: bug, validation
assignees: ""
---

## Analysis

Which analysis produced the wrong result? (the id from `auphoria list`)

## What it should have produced

Paste the expected value and where it came from (a published worked example,
an R / scikit-learn / statsmodels reference call, a textbook table, or a
hand computation). State the expected value, tolerance, and the source:

```
expected:  <value>

source:    <e.g. "R: t.test(x, y)", "Zar 1999 Table 7.2",
           "hand-computed from ranks">
```

## What AUPHORIA produced

Paste the output table / number it gave, and the `run.json` for the run (or
the exact `auphoria run ...` command so it can be reproduced).

## Data

Attach or inline the minimal data that triggered it (a small CSV is ideal).
If it is sensitive, replace real values with a tiny equivalent that still
reproduces the discrepancy.

## Reproduce

```
auphoria run --data <file> --analysis <id> --outcome <col> [--group <col>] ...
```

## Analysis

- [ ] Results reproduced against an independent reference (R / published example)
- [ ] Added/updated the reference value in `docs/validation/references.yaml`
- [ ] Ped its dashboard: `python scripts/gen_validation_dashboard.py`
- [ ] Added a known-issue note if it cannot be fixed immediately

---

**Template note:** the acceptance for a "wrong result" fix is a passing
cross-check against an independent reference, recorded in
`docs/validation/references.yaml`, reported on the regenerated dashboard.
A fix is not done until that cross-check exists and passes.