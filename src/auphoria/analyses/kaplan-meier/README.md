# Kaplan-Meier survival analysis (`kaplan-meier`)

For **time-to-event data with censoring** — e.g. time until relapse, time to
failure of a component, time to dropout, survival after diagnosis. It plots a
**Kaplan-Meier survival curve** per group (the fraction of subjects who have
not yet had the event at each time), reports the **median survival** per
group, and compares the groups with a **log-rank test**.

The key idea: not every subject is observed until they have the event. Some
leave the study earlier ("censored") — we only know they were still event-free
up to that point. Kaplan-Meier uses every piece of that information.

## When to use it

- Your rows are subjects with a **time** and a **did-the-event-happen** flag.
- Some rows are **censored** (the event had not happened when the subject was
  last seen) and some observed (event happened).
- You have a **group** column (e.g. treatment / control, two or more levels).
- You want to know whether the groups' survival curves differ.

## What you get

- A **survival table per group**: at each event time, the number at risk, the
  number of events, and the Kaplan-Meier survival probability.
- **Median survival** per group ("not reached" if the curve never drops
  below 0.5).
- A **log-rank test**: chi-squared, degrees of freedom and p-value comparing
  the whole curves.
- A **survival-curve figure** with a **number-at-risk table** underneath.
- A `methods.txt` paragraph you can paste into a paper.

## Inputs and choice

- **time** — numeric, time since study entry (must be ≥ 0).
- **event** — numeric, **0 = censored, 1 = event**. Nothing else is accepted.
- **group** — categorical, two or more categories.
- **alpha** (default `0.05`) — significance level for the log-rank test.

Example command:

```
auphoria run --data FILE --analysis kaplan-meier \
  --outcome time_col --group GROUP --extra event=event_col
```

## Assumptions (checked and reported)

- **Right-censoring is non-informative** — subjects who drop out are no more
  and no less likely to have the event than those who remain. If drop-out is
  related to the outcome, the curves are biased.
- **Censoring is independent of survival time.**
- The **groups are comparable** and their curves estimated independently.
- **Minimum sample size: at least 20 complete observations overall and at
  least 5 observed events per group.** With fewer, the analysis still runs but
  flags an **expert review**.

## When NOT to use it

- The **event column is not 0/1** → the tool refuses (recode first).
- A **group has no events at all** → its curve is undefined; the tool refuses.
- Times can be **negative** → refused.
- **Single group** → you cannot compare survival curves with one group.

> Maturity: **experimental** (advanced analysis — a significant result should
> be reviewed by a statistician, especially with small samples or heavy
> censoring).