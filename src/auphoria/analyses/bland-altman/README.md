# Bland-Altman Agreement (`bland-altman`)

Answers the question: **are two measurement methods close enough to be used
interchangeably on the same subjects?** You have two numeric columns that both
measure the same quantity (e.g. a new instrument vs the established method, or
your measurement vs the lab reference), recorded on the **same subjects** —
each row holds one subject measured by both.

Unlike a correlation (which ignores bias and can look great even when the two
methods systematically disagree), Bland-Altman looks directly at **how big the
disagreement is** for each pair.

## When to use it

- You have **two paired numeric columns** measuring the same quantity on the
  same subjects (one row = one subject, two methods).
- You are asking "do the two methods agree closely enough to swap between them?"
- You have at least three complete pairs (far more is much better).

## What you get

- **Agreement statistics**: n, the mean difference (**bias**), the SD of the
  differences, the **95% limits of agreement** (bias ± 1.96·SD), the standard
  error of the bias, and a 95% CI for the bias.
- **Limits of agreement (95% CI)**: confidence intervals for each limit so you
  can see how unstable they are with a small sample.
- **Proportional-bias check**: the correlation between |difference| and the
  pair mean (r and p). If it is significant, a WARN verdict is added — the
  disagreement grows with the size of the measurement.
- A **Bland-Altman plot**: difference against the pair mean, with the bias
  line, the two limits-of-agreement lines, a shaded band, and a linear
  regression line (its slope flags proportional bias).
- A normality check on the differences (the limits assume they are roughly
  normal).
- A `methods.txt` paragraph you can paste into a paper.

## Choices

- **alpha** (default `0.05`): used for the confidence intervals and the
  proportional-bias significance check.

## Assumptions & limitations

- The **limits of agreement are NOT a pass/fail verdict by themselves**. A bias
  of 0.5 mmHg with limits ±2 may be fine for blood pressure but disastrous for
  measuring a drug dose. **You must decide**, in advance and with a
  clinical/professional justification, what difference is acceptable.
- The differences should be **roughly normal**; if not, the limits are
  approximate (a Shapiro-Wilk check warns you).
- If the differences **grow with magnitude** (proportional bias), the limits
  are too wide at one end and too narrow at the other — consider a log-scale
  analysis.
- With fewer than ~10 pairs the limits are very unstable.
- Missing values are **counted and excluded** (never imputed).
- This analysis says **nothing about which method is more accurate** — only
  how well they agree with each other.

## When NOT to use it

- Your columns are not paired (different subjects per method). Use the
  independent-samples t-test instead.
- You want to know which method is *more correct* — that needs an external
  reference/gold standard, not two candidate methods.
- Your differences are proportional to magnitude and remain so — analyse on
  the log scale first.

## Common mistakes

- **Using correlation to claim agreement**: two methods can correlate 0.99 yet
  disagree by a large systematic offset (bias). Bland-Altman was designed to
  expose exactly this.
- Reading the limits as a pass/fail without an external acceptable-difference
  threshold.
- Reporting a significant t-test of the bias as "no agreement" (or an
  insignificant one as "good agreement") — significance of the bias and the
  *width* of the limits are different questions.

## Check

Run `auphoria info bland-altman` for the manifest (inputs, parameters,
assumptions). The automated tests (`tests/test_bland_altman.py`) verify the
bias, SD and limits against hand-computed values on synthetic data
(differences −0.2, 0.1, −0.1, 0.0, 0.1 → bias −0.02, SD 0.13038, limits
−0.2756 and 0.2356), cross-check a larger random dataset against a simple
in-test hand routine, and confirm the proportional-bias WARN fires when it is
engineered in.

> Maturity: **experimental** (not "validated").