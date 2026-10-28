"""Tests for the Principal Component Analysis.

Uses small synthetic correlated data and compares against scikit-learn's
PCA as the documented reference (sklearn.decomposition.PCA), plus a
hand-computed check on a tiny perfectly-correlated 2-column dataset:

  x1 = [1,2,3,4,5,6,7,8,9,10], x2 = [2,4,6,8,10,12,14,16,18,20]

After standardising, the two columns are perfectly correlated, so the first
component explains all (100%) of the variance and its loading on each
variable is 1/sqrt(2) ≈ 0.7071.
"""

from __future__ import annotations

import importlib

import numpy as np
import pandas as pd
import pytest
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from auphoria.core.analysis import AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

# The analysis id is a single lowercase token ('pca') but load it by the same
# importable-module path the registry uses, which works for any id spelling.
_PCA_MODULE = importlib.import_module("auphoria.analyses.pca.analysis")
PcaAnalysis = _PCA_MODULE.PcaAnalysis


def _ctx() -> RunContext:
    import logging

    logger = logging.getLogger("auphoria_test_pca")
    logger.handlers = []
    return RunContext(
        seed=1,
        out_dir=__import__("pathlib").Path("."),
        data_name="test",
        expert=False,
        _log=logger,
        _log_decision=lambda m: None,
    )


def _df(**cols: list[float]) -> pd.DataFrame:
    return pd.DataFrame(cols)


def _run(df: pd.DataFrame, **params) -> AnalysisResult:
    return PcaAnalysis().run(
        df, {"n_components": 2, "standardize": True, **params}, {}, _ctx()
    )


# A small correlated dataset on two columns plus a third independent-ish one.
_CORR = {
    "x1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
    "x2": [2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0],
    "y": [5.0, 4.5, 5.5, 4.0, 6.0, 5.0, 6.5, 4.5, 7.0, 6.0],
}


def _reference_ratios(df: pd.DataFrame, k: int = 2):
    """Reference explained-variance ratios: standardise, then sklearn PCA."""
    X = StandardScaler().fit_transform(df)
    return PCA(n_components=k).fit(X).explained_variance_ratio_


def _reference_loadings(df: pd.DataFrame, k: int = 2):
    """Reference component loading matrix (components_), standardised."""
    X = StandardScaler().fit_transform(df)
    return PCA(n_components=k).fit(X).components_


def test_pca_explained_variance_matches_sklearn():
    result = _run(_df(**_CORR))
    tab = result.tables["Variance explained"].set_index("Component")
    ref = _reference_ratios(_df(**_CORR))
    for i in range(len(ref)):
        pct = float(tab.loc[f"PC{i + 1}", "Variance explained (%)"])
        assert pct / 100.0 == pytest.approx(float(ref[i]), abs=1e-4)
    # Cumulative column is a correct running sum of the per-component Pct.
    cum = tab["Cumulative (%)"].astype(float).to_numpy()
    per = tab["Variance explained (%)"].astype(float).to_numpy()
    assert np.allclose(cum, np.cumsum(per), atol=1e-4)


def test_pca_loadings_match_sklearn():
    result = _run(_df(**_CORR))
    load = result.tables["Component loadings"].set_index("Variable")
    ref = _reference_loadings(_df(**_CORR))
    # Compare cell by cell against the reference components_ matrix.
    for j, variable in enumerate(load.index):
        for i in range(ref.shape[0]):
            got = float(load.loc[variable, f"PC{i + 1}"])
            assert got == pytest.approx(float(ref[i, j]), abs=1e-4)


def test_pca_hand_computed_perfect_correlation():
    # x2 is exactly 2*x1 -> after standardising they are perfectly correlated.
    df = _df(x1=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
             x2=[2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0])
    result = _run(df)
    tab = result.tables["Variance explained"].set_index("Component")
    # PC1 explains ~100% of the variance.
    assert float(tab.loc["PC1", "Variance explained (%)"]) == pytest.approx(
        100.0, abs=1e-3
    )
    # PC1 loading on each variable is 1/sqrt(2).
    load = result.tables["Component loadings"].set_index("Variable")
    assert float(load.loc["x1", "PC1"]) == pytest.approx(
        1.0 / np.sqrt(2.0), abs=1e-4
    )
    assert float(load.loc["x2", "PC1"]) == pytest.approx(
        1.0 / np.sqrt(2.0), abs=1e-4
    )


def test_pca_refuses_less_than_two_numeric_columns():
    df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "grp": ["x", "y", "x"]})
    with pytest.raises(AssumptionError, match="two numeric columns"):
        _run(df)


def test_pca_missing_dropped_with_warning_never_imputed():
    df = _df(**_CORR)
    df.loc[0, "x1"] = np.nan
    df.loc[1, "x2"] = np.nan
    result = _run(df)
    # 2 rows dropped listwise -> 8 rows remain in the loadings index.
    load = result.tables["Component loadings"].set_index("Variable")
    assert len(load) == 3  # still all three variables
    # Output must not contain NaN anywhere (nothing imputed/carried through).
    for name, table in result.tables.items():
        assert not table.isna().any().any(), f"{name} has NaN"
    assert any("missing" in w and "imputed" in w for w in result.warnings)


def test_pca_figures_methods_and_what_does_not_tell():
    result = _run(_df(**_CORR))
    assert len(result.figures) == 2
    names = {f.name for f in result.figures}
    assert names == {"pca_scree", "pca_scores"}
    assert len(result.methods) >= 3
    methods_text = " ".join(result.methods)
    assert "PCA" in methods_text and "sklearn" in methods_text
    assert result.what_does_not_tell  # honest-interpretation sentence set
    assert "factor analysis" in result.what_does_not_tell
    assert "variables reduced" in result.summaries
    assert "recommended components to keep" in result.summaries


def test_pca_standardize_false_runs():
    # With standardize=False PCA should still run and report components.
    result = _run(_df(**_CORR), standardize=False)
    assert "Variance explained" in result.tables
    assert len(result.methods) >= 3


def test_pca_refuses_too_few_rows():
    df = _df(x1=[1.0, 2.0], x2=[3.0, 4.0])
    with pytest.raises(AssumptionError):
        _run(df)
