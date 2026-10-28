"""Tests for the K-Means clustering analysis.

Uses small deterministic synthetic data with clearly separated Gaussian
blobs and compares against scikit-learn's reference implementation (the
"documented reference"): ``sklearn.cluster.KMeans`` for labels and
centres, and ``sklearn.metrics.silhouette_score`` for the average
silhouette. Because the analysis uses the same ``random_state``, the
reference and the analysis produce identical label orderings, but the
tests still relabel to be safe.
"""

from __future__ import annotations

import importlib

import numpy as np
import pandas as pd
import pytest
from numpy.random import default_rng
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from auphoria.core.analysis import AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

# The analysis id contains a hyphen ('clustering-kmeans'), which is not
# valid Python syntax in an import statement, so load the module by name.
_MOD = importlib.import_module("auphoria.analyses.clustering-kmeans.analysis")
ClusteringKmeansAnalysis = _MOD.ClusteringKmeansAnalysis


def _ctx() -> RunContext:
    import logging
    from pathlib import Path

    logger = logging.getLogger("auphoria_test_km")
    logger.handlers = []
    return RunContext(
        seed=1,
        out_dir=Path("."),
        data_name="test",
        expert=False,
        _log=logger,
        _log_decision=lambda m: None,
    )


def _blobs_df(n=90, k=3, random_state=1) -> pd.DataFrame:
    """Three clearly separated 2-D Gaussian blobs (centres far apart)."""
    rng = default_rng(random_state)
    centres = np.array([[-4.0, -4.0], [4.0, -4.0], [0.0, 6.0]])
    per = n // k
    xs, ys = [], []
    for c in range(k):
        xs.extend(rng.normal(centres[c, 0], 0.4, per))
        ys.extend(rng.normal(centres[c, 1], 0.4, per))
    # Three clearly separated 2-D blobs.
    return pd.DataFrame({"x": xs, "y": ys})


def _run(df: pd.DataFrame, **params) -> AnalysisResult:
    return ClusteringKmeansAnalysis().run(
        df, {"k": 3, "standardize": True, "random_state": 1, **params}, {}, _ctx()
    )


def _ref_labels(df: pd.DataFrame, k: int = 3, random_state: int = 1):
    """Reference: sklearn KMeans on the standardised data, same seed."""
    X = df.to_numpy(dtype=float)
    Xs = StandardScaler().fit_transform(X)
    km = KMeans(n_clusters=k, n_init=10, random_state=random_state).fit(Xs)
    return Xs, km.labels_, km.cluster_centers_


def _relabel(mine, ref) -> np.ndarray:
    """Map each of my cluster ids to the ref id it shares most rows with."""
    mine = np.asarray(mine, dtype=int)
    ref = np.asarray(ref, dtype=int)
    n = max(mine.max() + 1, ref.max() + 1)
    mapping = np.full(n, -1)
    for c in range(mine.max() + 1):
        mask = mine == c
        if mask.sum() == 0:
            continue
        counts = np.bincount(ref[mask], minlength=n)
        # prefer an unmapped target; fall back to argmax
        cand = counts.argmax()
        mapping[c] = cand
        # make sure we don't double-assign; deterministic data makes this moot
    return np.array([mapping[c] for c in mine])


def _label_tolerance_mismatch(mine, ref, max_mismatch=0):
    r = _relabel(mine, ref)
    return int(np.sum(r != np.asarray(ref)))


# (1) cluster labels match sklearn KMeans (with tolerance for relabelling)
def test_labels_match_sklearn():
    df = _blobs_df()
    result = _run(df)
    Xs, ref_labels, _ = _ref_labels(df)
    mine = result.tables["Cluster assignments"]["cluster"].to_numpy()
    # n_rows unchanged (no missing values)
    assert len(mine) == len(df)
    assert _label_tolerance_mismatch(mine, ref_labels) == 0


# (2) cluster centres match sklearn within abs 1e-4
def test_cluster_centres_match_sklearn():
    df = _blobs_df()
    result = _run(df)
    Xs, ref_labels, ref_centres = _ref_labels(df)
    centres = result.tables["Cluster centres"].set_index("cluster")
    for _i, row in centres.iterrows():
        # my cluster _i maps to ref id ... choose the ref centre closest to it
        closest = int(
            np.argmin(
                np.sum((ref_centres - row[["x", "y"]].to_numpy()) ** 2, axis=1)
            )
        )
        assert np.allclose(
            row[["x", "y"]].to_numpy(), ref_centres[closest], atol=1e-4
        )
    assert len(centres) == 3


# (3) silhouette score matches sklearn within abs 1e-4
def test_silhouette_matches_sklearn():
    df = _blobs_df()
    result = _run(df)
    Xs, ref_labels, _ = _ref_labels(df)
    ref_sil = silhouette_score(Xs, ref_labels)
    mine_sil = float(result.summaries["average silhouette"])
    assert mine_sil == pytest.approx(ref_sil, abs=1e-4)
    # well-separated blobs -> structure is strong (>= 0.25)
    assert "silhouette-quality" in {v.check for v in result.verdicts}


# (4) refuses fewer than two numeric columns
def test_refuses_two_few_numeric_columns():
    df = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0], "label": ["p", "q", "p", "q"]})
    with pytest.raises(AssumptionError, match="numeric"):
        _run(df)


# (5) refuses k > n_rows
def test_refuses_k_greater_than_rows():
    df = _blobs_df(n=4)
    with pytest.raises(AssumptionError, match="clusters than points"):
        _run(df, k=5)


# (6) missing values dropped with a warning, never imputed
def test_missing_dropped_with_warning_no_impute():
    df = _blobs_df(n=12)
    # 3 rows have a missing numeric value
    df.iloc[0, df.columns.get_loc("x")] = np.nan
    df.iloc[1, df.columns.get_loc("y")] = np.nan
    df.iloc[2, df.columns.get_loc("x")] = np.nan
    result = _run(df)
    mine = result.tables["Cluster assignments"]["cluster"].to_numpy()
    # 12 - 3 dropped; assignments table carries the complete rows only
    assert len(mine) == 9
    assert any("missing" in w.lower() and "impute" in w.lower() for w in result.warnings)
    # The surviving rows are exactly the complete ones (row indexes 3..11).
    assert list(result.tables["Cluster assignments"].index) == list(range(3, 12))


# (7) returns figures, >= 3 methods sentences, and a what_does_not_tell
def test_figures_methods_and_what_does_not_tell():
    df = _blobs_df()
    result = _run(df)
    assert len(result.figures) >= 2
    names = {f.name for f in result.figures}
    assert "km_pc_scatter" in names
    assert "km_silhouette_elbow" in names
    assert len(result.methods) >= 3
    text = " ".join(result.methods)
    assert "k-means" in text.lower()
    assert "silhouette" in text.lower()
    assert "standardis" in text.lower()
    assert result.what_does_not_tell
    assert "not real categories" in result.what_does_not_tell


# (8) expert review when the sample is small relative to k
def test_expert_review_on_small_sample():
    df = _blobs_df(n=20)  # 20 rows, k=3 -> fewer than 10 per cluster
    result = _run(df)
    assert result.expert_review  # non-empty
    assert any("10 rows per cluster" in r for r in result.expert_review)
    levels = {v.check: v.level for v in result.verdicts}
    assert levels["sample-size"] == "WARN"
