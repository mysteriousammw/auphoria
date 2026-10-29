# Cronbach's Alpha (`cronbach-alpha`)

Cronbach's alpha measures the **internal consistency (reliability)** of a set
of **numeric item columns** that are supposed to measure one scale or
construct — the classic questionnaire / survey reliability statistic. If you
have several items that should all be tapping, say, "anxiety", alpha tells
you how consistently they score respondents.

## When to use it

- You have **several numeric columns** (questionnaire/survey items) that
  should measure one construct and want a single reliability figure.
- You are **developing or validating a scale** and want to know whether the
  items hang together before summing or averaging them into one score.
- You want to see **which items are weakest** (low corrected item-total
  correlation, response "alpha if deleted" rises).

The tool uses **every numeric column** it finds in your file as an item.

## What you get

- **Overall Cronbach's alpha** (raw) computed by hand with the textbook
  formula `alpha = (k/(k-1)) * (1 - sum(item variance)/total(row-sum variance))`.
- The **standardised alpha** (computed on standardised items) — useful when
  items are on very different scales.
- A **per-item table**: n, mean, SD, the **corrected item-total correlation**
  (each item vs the sum of the remaining items) and the **alpha if that item
  were deleted** — this shows which items are most consistent with the rest.
- A plain-English **interpretation** of the alpha:
  - `< 0.6` — unacceptable
  - `0.6–0.7` — questionable
  - `0.7–0.8` — acceptable
  - `0.8–0.9` — good
  - `>= 0.9` — excellent
- A `methods.txt` paragraph you can paste into a paper.

## Choices

- **acceptable_threshold** (default `0.7`): the alpha value at or above which
  the overall verdict is recorded as acceptable. Choosing `0.8` is common in
  high-stakes settings, `0.6` in exploratory work.

## Assumptions and minimum sample size (checked and reported)

- Each item column must be **numeric**.
- At least **2 numeric item columns** are required; fewer is refused.
- A sample of at least **30 complete observations** is recommended. With fewer
  rows the analysis still runs, but the result is flagged for **expert
  review** because the estimate carries substantial sampling error.
- Missing values are **counted, reported and excluded** (row-wise / listwise),
  **never imputed**.
- If the raw and standardised alphas differ by more than **0.1**, the items
  have very heterogeneous variances; the analysis warns and flags expert
  review, because a single alpha may mislead.

## ⚠ Important: AUPHORIA does NOT reverse-code items

AUPHORIA **never automatically reverse-codes** any item. If some of your items
are worded in the opposite direction to the rest (e.g. negatively-worded
items on a questionnaire), you must **reverse their scoring yourself** before
running the analysis — otherwise the items correlate negatively and alpha is
artificially low, even when the scale is actually consistent.

## When NOT to use it

- Fewer than 2 numeric columns → refused.
- Items meant to measure **different constructs** would give a misleadingly
  low alpha; alpha assumes the items all tap the same thing.
- If all rows sum to the same value (no variance in the total score), alpha is
  undefined and the analysis is refused.
- If you want to know whether the items collapse onto **one dimension** or
  **how many dimensions they have**, use **factor analysis** or **PCA**
  instead — alpha does not measure unidimensionality.

## How to read the output

1. **Overall alpha / interpretation**: the headline reliability. `>= 0.7`
   with your chosen threshold is usually taken as acceptable.
2. **Item statistics table**: look at each item's corrected item-total
   correlation. Items with a low (or negative) correlation attenuate alpha.
   If removing an item clearly raises alpha, that item is the weakest link.
3. **Standardised alpha**: if it differs a lot from the raw value, item
   variances are unequal — report both and interpret cautiously.

## Example

```bash
auphoria run --data my_questionnaire.csv --analysis cronbach-alpha
```

> Maturity: **experimental** (not "validated"). This is an **advanced-level**
> analysis; small-sample or heterogeneous-scale results are preliminary and
> should be reviewed by your supervisor or a statistician. Remember that a
> high alpha does **not** prove the scale is unidimensional or valid.