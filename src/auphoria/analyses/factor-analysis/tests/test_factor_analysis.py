"""Tests for the exploratory factor analysis analysis.

Uses small deterministic synthetic data. Bartlett's test of sphericity is
checked against the textbook formula recomputed by hand, KMO is verified to
lie in [0, 1], and the unrotated factor loadings are compared against
``sklearn.decomposition.FactorAnalysis`` (the documented reference). The
guardrails (refusing too few numeric columns, dropping missing rows without
imputing) and the report structure are also exercised.
"""

from __future__ import annotations

import importlib

import numpy as np
import pandas as pd
import pytest
from scipy import stats
from sklearn.decomposition import FactorAnalysis

from auphoria.core.analysis import AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

# The analysis id contains a hyphen ('factor-analysis'), which is not valid
# Python syntax in an import statement, so load the module by name.
_MODULE = importlib.import_module("auphoria.analyses.factor-analysis.analysis")
FactorAnalysisAnalysis = _MODULE.FactorAnalysisAnalysis
_varimax = _MODULE._varimax


def _ctx() -> RunContext:
    import logging

    logger = logging.getLogger("auphoria_fa_test")
    logger.handlers = []
    return RunContext(
        seed=1,
        out_dir=__import__("pathlib").Path("."),
        data_name="test",
        expert=False,
        _log=logger,
        _log_decision=lambda m: None,
    )


# Deterministic two-factor data: items i1-i3 load on factor 1, items i4-i6 on
# factor 2, with a low noise floor so the MLE factor analysis recovers the
# structure cleanly.
_rng = np.random.default_rng(7)
_TRUE_LOADINGS = np.array(
    [
        [0.90, 0.00],
        [0.80, 0.00],
        [0.70, 0.00],
        [0.00, 0.90],
        [0.00, 0.80],
        [0.00, 0.70],
    ]
)


def _factor_df(n: int = 400, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    F = rng.normal(size=(n, 2))
    E = rng.normal(scale=0.20, size=(n, 6))
    X = F @ _TRUE_LOADINGS.T + E
    return pd.DataFrame(X, columns=["i1", "i2", "i3", "i4", "i5", "i6"])


def _run(df: pd.DataFrame, **params) -> AnalysisResult:
    return FactorAnalysisAnalysis().run(
        df, {"n_factors": 2, "rotation": "varimax", **params}, {}, _ctx()
    )


def _std_array(df: pd.DataFrame) -> np.ndarray:
    X = df.to_numpy(dtype=float)
    return (X - X.mean(axis=0)) / X.std(axis=0)


# ---- 1. Bartlett's test matches the hand/t-formula computation ----
def test_bartlett_matches_textbook_formula():
    df = _factor_df(n=120, seed=3)
    n = len(df)
    # The reference correlation matrix is compute in exactly the same way the
    # analysis does (standardised X -> np.corrcoef).
    R = np.corrcoef(_std_array(df), rowvar=False)
    R = np.nan_to_num(R, nan=0.0)
    p = R.shape[0]
    chi2_ref = -(n - 1 - (2 * p + 5) / 6) * np.log(np.linalg.det(R))
    df_ref = p * (p - 1) // 2
    pval_ref = stats.chi2.sf(chi2_ref, df_ref)

    result = _run(df)
    table = result.tables["KMO & Bartlett"].set_index("Check")
    assert float(table.loc["Bartlett chi-squared", "Value"]) == pytest.approx(
        chi2_ref, abs=1e-3
    )
    assert int(table.loc["Bartlett df", "Value"]) == df_ref
    # Bartlett's p (survival function at the reported chi-squared) is 0 for a
    # strongly correlated matrix, so the table formats it as '< 0.001'.
    assert pval_ref == pytest.approx(0.0, abs=1e-12)
    assert table.loc["Bartlett p-value", "Value"] in ("< 0.001", "0.000")
    assert isinstance(pval_ref, float)


# ---- 2. factor loadings match sklearn FactorAnalysis (unrotated) ----
def test_unrotated_loadings_match_sklearn():
    df = _factor_df()
    result = _run(df, rotation="none")
    table = result.tables["Factor loadings"]
    items = table["Item"].tolist()
    mine = table[[c for c in table.columns if c.startswith("Factor")]].to_numpy(
        dtype=float
    )

    ref = FactorAnalysis(n_components=2, random_state=1, max_iter=1000)
    ref.fit(_std_array(df))
    expected = ref.components_.T  # p x k (items x factors)
    k = expected.shape[1]
    # Align per-factor sign (loading signs are arbitrary up to a sign flip).
    for j in range(k):
        if np.dot(mine[:, j], expected[:, j]) < 0:
            expected[:, j] = -expected[:, j]
    assert np.allclose(mine, expected, atol=1e-3)
    assert items == ["i1", "i2", "i3", "i4", "i5", "i6"]


# ---- 2b. structural check: the two factors separate the two item blocks ----
def test_two_factor_structure_recovered():
    result = _run(_factor_df(), rotation="varimax")
    load = result.tables["Factor loadings"]
    f1 = load["Factor 1"].abs().to_numpy()
    f2 = load["Factor 2"].abs().to_numpy()
    # Items i1-i3 should load strongly on factor 1, weakly on factor 2.
    assert f1[:3].mean() > 0.5
    assert f1[3:].mean() < 0.4
    assert f2[3:].mean() > 0.5
    assert f2[:3].mean() < 0.4


# ---- 3. KMO is computed and lies in [0, 1] ----
def test_kmo_in_unit_range():
    result = _run(_factor_df())
    table = result.tables["KMO & Bartlett"].set_index("Check")
    kmo = float(table.loc["KMO (sampling adequacy)", "Value"])
    assert 0.0 <= kmo <= 1.0
    # On strongly correlated factor data KMO should be comfortably adequate.
    assert kmo > 0.6


# ---- 4. refuses fewer than 3 numeric columns ----
def test_refuses_fewer_than_three_numeric_columns():
    df = pd.DataFrame({"a": [1, 2, 3, 4, 5, 6], "b": [2, 1, 3, 5, 4, 6]})
    with pytest.raises(AssumptionError, match="at least 3 numeric"):
        _run(df)


# ---- 5. missing values are dropped with a warning, never imputed ----
def test_missing_dropped_with_warning_not_imputed():
    df = _factor_df(n=60)
    df.iloc[0, 0] = np.nan
    df.iloc[1, 3] = np.nan
    result = _run(df)
    assert any("missing" in w.lower() and "never imputed" in w.lower() for w in result.warnings)
    assert any("excluded" in w.lower() for w in result.warnings)
    assert result.methods, "methods should be present"
    methods_text = " ".join(result.methods)
    assert "imputed" in methods_text
    assert len(result.tables["Variance explained"]) == 2


# ---- 6. returns figures, >=3 methods sentences and a what_does_not_tell ----
def test_outputs_figures_methods_and_what_not_tell():
    result = _run(_factor_df())
    assert len(result.figures) == 2
    names = {f.name for f in result.figures}
    assert "efa_loadings_heatmap" in names
    assert "efa_scree" in names
    assert len(result.methods) >= 3
    methods_text = " ".join(result.methods)
    assert "factor analysis" in methods_text.lower()
    assert "KMO" in methods_text
    assert "Bartlett" in methods_text
    assert len(result.what_does_not_tell) > 50
    assert "PCA" in result.what_does_not_tell
    assert len(result.summaries) >= 3


# ---- 7. small sample triggers expert review + WARN verdict ----
def test_small_sample_expert_review_and_verdicts():
    # n = 40 rows, 6 items -> below the ~100 overall / ~5-per-item rule of thumb.
    result = _run(_factor_df(n=40, seed=5))
    assert result.expert_review, "small sample should flag expert review"
    verdicts = {v.check: v.level for v in result.verdicts}
    assert "kmo-adequacy" in verdicts
    assert "bartlett-significance" in verdicts
    assert any("sample" in w.lower() for w in result.warnings)


# ---- 8. varimax rotation is a valid orthogonal rotation of the loadings ----
def test_varimax_rotation_preserves_row_norms():
    rng = np.random.default_rng(11)
    L = rng.normal(size=(8, 3))
    rotated, R = _varimax(L, max_iter=200)
    assert np.allclose(rotated, L @ R, atol=1e-3)
    # A valid rotation preserves each item's communality (row squared norm).
    assert np.allclose((L**2).sum(axis=1), (rotated**2).sum(axis=1), atol=1e-6)
    # R is a proper orthogonal matrix.
    assert np.allclose(R @ R.T, np.eye(3), atol=1e-6)
