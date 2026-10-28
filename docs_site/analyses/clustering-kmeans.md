# K-Means Clustering

`clustering-kmeans` · maturity: **experimental**

Discipline packs: `agri-animal`  

Validation reference: Three well-separated blobs; cross-checked vs sklearn.cluster.KMeans + silhouette_score  


## What it does

Groups observations into k clusters based on all numeric columns, using the k-means algorithm. The numeric columns are standardised (scaled to equal units) before clustering so a large-valued variable does not dominate. The report shows the cluster assignment of every row, the cluster centres, an average silhouette score (how well separated the clusters are), an elbow check on the number of clusters, a 2-D scatter of the first two principal components coloured by cluster, and a silhouette profile figure.

## Options

- `k` (default 3): Number of clusters to form (choose with the elbow/silhouette guidance).
- `standardize` (default True): Scale all numeric columns to equal units before clustering.
- `random_state` (default 1): Seed for the k-means initialisation so results are reproducible.

## What you get out

- cluster assignments table (each row, its cluster, a few columns)
- cluster centres table (mean of each variable per cluster)
- average silhouette score (0..1): higher = better separated clusters
- elbow guidance (inertia at k-1, k and k+1 to judge whether k is sensible)
- 2-D scatter of the first two principal components coloured by cluster
- silhouette profile / elbow figure
- methods.txt paragraph
- report.html

## Assumptions

- You are expecting or seeking clusters in the data (unsupervised learning); k-means does not test whether clusters "really" exist.
- All clustering columns are numeric (the analysis uses every numeric column automatically and refuses if fewer than two).
- Variables should be scaled to equal units (done automatically by default) so no single variable dominates the distance.
- The number of clusters k is chosen carefully (elbow / silhouette / domain reasoning), not picked at random.
- Clusters should be meaningful in your domain, not just an artefact of the algorithm, scaling, or an unlucky k.
- Minimum sample size: at least 10 times k rows after missing values are removed (a warning, not a refusal); you must have more rows than clusters (a refusal).

## Limitations

- k-means finds roughly spherical, equal-sized clusters; elongated or highly irregular cluster shapes are missed (consider DBSCAN / hierarchical clustering instead).
- The result depends on scaling, on the choice of k and on the random seed; different choices give different clusters.
- Cluster labels are arbitrary (cluster "0" has no intrinsic meaning) and ordering can change between runs.
- k-means is sensitive to outliers, which can pull centres toward them.
- A low silhouette (< 0.25) means the clusters are weak / poorly separated, so read the grouping sceptically; silhouette is undefined when k equals 1.
- Missing values in the numeric columns are excluded listwise with a warning, never imputed.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis clustering-kmeans
```
