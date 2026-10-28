# Responsible use

**AUPHORIA does not certify your science.** It is a careful, honest
calculator — but no software can certify that your study was designed well,
your data were collected correctly, or your conclusions are sound. Those
judgements are yours, and your supervisor's.

## What AUPHORIA does for you

- Computes standard statistical quantities using established, permissive
  libraries (SciPy, statsmodels, scikit-learn).
- Checks assumptions where it can (normality, equal variances, expected
  counts) and warns or refuses when a test clearly doesn't fit.
- Applies **missing-data honesty**: it never imputes or silently drops data;
  it counts what it excludes and records the reason.
- Always tells you **what the result does not imply**, and flags advanced
  analyses with a **"needs expert review"** notice when they are run outside
  their intended conditions.

## What AUPHORIA does NOT do — and you must not let it do

- **It does not approve your study design.** Garbage in, garbage out. A
  significant p-value from a biased sample is still meaningless.
- **It does not prove causation.** Correlation, regression, and even ANOVA do
  not establish cause. AUPHORIA's reports say so; so should your thesis.
- **It does not certify your science.** Nothing produced by any analysis tool
  should be presented as "validated" unless a qualified human reviewed the
  method and the data. See [Validation](validation.md) for the project's own
  maturity levels — none of them are set by the tool itself.
- **It does not replace a statistician.** For a thesis or a journal, the
  "needs expert review" notices and the assumption checks exist precisely
  because a human statistician's judgement is required. Treat them as genuine
  requirements, not decorations.

## The house rules

1. **Understand the test you run.** Use the [decision guide](choose.md) and
   read the analysis page. If you can't explain why ANOVA instead of a t-test,
   ask someone before running it.
2. **Report honestly.** Paste the real `methods.txt` and the real numbers. Do
   not cherry-pick the significant rows.
3. **Report limitations.** Copy the "what this does not tell you" caveats into
   your discussion. A thesis that acknowledges its limits is stronger, not
   weaker.
4. **Reproduce.** Save your data, your command, and your seed so anyone —
   including future you — can reproduce the exact numbers.
5. **Flag, don't hide, warnings.** If AUPHORIA says your sample is too small or
   an assumption is violated, that is information about your study, not an
   inconvenience to work around.

## Validation and trustworthiness

Every analysis is catalogued with a **maturity** level and an **independent
reference** it is cross-checked against (see [Validation](validation.md) and
the [validation dashboard](validation.md)). The layout of
trust:

- **experimental / tested** — has automated known-answer tests; safe for
  learning and exploration.
- **reviewed / validated** — additionally reproduced against an independent
  reference **and signed off by a named human reviewer**. Nothing in AUPHORIA
  reaches this tier by itself.

So when you see a number, you can trust *that AUPHORIA computed it correctly
given its inputs and assumptions.* Whether those inputs and assumptions are
appropriate for *your* science is a human question — and that part is on you,
and on the statistician you consult.

## If something looks wrong

Do not silently use a suspicious result. Consult the
[Known issues](known-issues.md) and report it using the
[wrong-result template](known-issues.md). The project's
definition of a correct fix is a recorded cross-check against an independent
reference — that is how the tool earns your trust, one analysis at a time.