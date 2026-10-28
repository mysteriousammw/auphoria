# K-Means Clustering (`clustering-kmeans`)

Groups your observations into **k clusters** based on all the numeric
columns, using the classic **k-means** algorithm. Think of it as letting
the computer look at your rows and say "these points are similar to each
other, those points are similar to each other" — and draw the dividing
lines. It is an **unsupervised** technique: there is no "correct answer"
to check against, so you must *expect or seek* clusters and judge whether
the groups it finds make sense.

## When to use it

- You have several numeric columns and want to see whether the rows fall
  into natural groupings (e.g. customers by spending habits, genes by
  expression, samples by chemical measurement).
- You want a compact "profile" of each group (its average on every
  variable) so you can label and study the groups.
- You are willing to choose `k` (the number of groups) thoughtfully and to
  interpret the groups with domain knowledge.

## Inputs

- **All numeric columns** are used automatically — you don't pick any. A
  column counts as numeric if pandas reads it as numbers (float / int /
  bool). A row with a missing value in any numeric column is **excluded**
  (reported, never imputed). The analysis refuses if there are **fewer
  than two** numeric columns.

## What you get

- A **cluster assignments** table: every row, its cluster, and a few of
  its columns.
- **Cluster centres**: the average of every variable in each cluster, plus
  the size of each cluster and a mean profile table.
- An **average silhouette score** (roughly 0–1): how well separated the
  clusters are. Above ~0.5 is reasonable; below ~0.25 is weak.
- An **elbow guidance** table/figure: within-cluster inertia at `k-1`, `k`
  and `k+1`, so you can judge whether your `k` is sensible.
- A **2-D scatter** of the first two principal components coloured by
  cluster, and a **silhouette profile** figure.
- A `methods.txt` paragraph you can paste into a paper.

## Choices

- **k** (default `3`, min `2`): how many clusters to form. Choose it from
  the elbow / silhouette / your domain — never at random.
- **standardize** (default `true`): scale all numeric columns to equal
  units before clustering, so a big-scale variable doesn't dominate.
- **random_state** (default `1`): seed for k-means initialisation, for
  reproducibility.

## Assumptions (checked and reported, never silently ignored)

- You are **expecting or seeking clusters**; the algorithm always returns
  `k` groups even from pure noise. The silhouette score is your honest
  check.
- Variables are **scaled to equal units** (done by default), so no single
  variable dominates the distances.
- `k` is chosen **carefully** and the clusters are **meaningful in your
  domain**, not an artefact of the algorithm, scaling, or an unlucky `k`.
- **Sample size**: you need more rows than clusters (refused otherwise),
  and ideally about **10 rows per cluster** (warned below that; the result
  is flagged for expert review).

## When NOT to use it

- **Fewer than two numeric columns** → k-means can't form clusters; use a
  different analysis.
- **You want to test a hypothesis** (e.g. "do these groups differ?") → use
  a t-test or ANOVA; k-means doesn't test anything.
- **Clusters that aren't round/blob-shaped** (elongated, spirals, nested)
  → k-means misses those; consider DBSCAN or hierarchical clustering.
- **Outliers are important** → k-means is sensitive to them and pulls
  centres toward outliers.

## How to read the output

1. **Silhouette score first**: a value well above 0.25 means the clusters
   are reasonably separated. Below 0.25 the groupings are weak — treat
   them sceptically.
2. **Cluster profiles**: look at the cluster centres to characterise each
   group (e.g. "cluster 0 = high spend, low engagement").
3. **Elbow**: if adding a cluster barely reduces inertia (i.e. `k` already
   captures the structure), your `k` is probably large enough.
4. **Cluster labels are arbitrary** — "cluster 0" vs "cluster 2" has no
   intrinsic order or meaning; only the grouping of rows matters.

> Maturity: **experimental** (not "validated").

## Example

```bash
auphoria run --data my_data.csv --analysis clustering-kmeans
```