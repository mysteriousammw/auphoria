"""Tests for the linear mixed-effects model analysis.

Uses a small synthetic nested dataset whose fixed-effect coefficient is
hand-computable, and compares every fitted quantity (coefficients, variance
components, ICC) against statsmodels MixedLM as the documented reference
implementation.

Design of the main dataset: 10 clusters, 4 rows each. Within each cluster the
fixed-effect group alternates so every cluster contains two group-A and two
group-B rows (a fully balanced nested/repeated design). Group B is offset by a
hand-set +3.0 against group A, so the fixed-effect coefficient for group B
(when statsmodels uses group A as the reference level) is +3.0 before
accounting for the random intercepts. Because the design is balanced and the
random intercepts sum to zero across clusters, the fitted coefficient matches
the hand-set offset to within the fit tolerance. The reference is always
statsmodels MixedLM itself, which is what the analysis wraps.
"""

from __future__ import annotations

import importlib

import numpy as np
import pandas as pd
import pytest

from auphoria.core.analysis import AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

# The analysis id contains a hyphen ('mixed-effects'), which is not valid
# Python syntax in an import statement, so load the module by name.
_ME_MODULE = importlib.import_module("auphoria.analyses.mixed-effects.analysis")
MixedEffectsAnalysis = _ME_MODULE.MixedEffectsAnalysis


def _ctx() -> RunContext:
    import logging

    logger = logging.getLogger("auphoria_mixed_test")
    logger.handlers = []
    return RunContext(
        seed=1,
        out_dir=__import__("pathlib").Path("."),
        data_name="test",
        expert=False,
        _log=logger,
        _log_decision=lambda m: None,
    )


def _make_main_df(
    n_clusters: int = 40,
    rows_per_cluster: int = 4,
    true_offset: float = 3.0,
    resid_sd: float = 0.5,
    seed: int = 99,
) -> pd.DataFrame:
    """Build a balanced nested dataset: n_clusters clusters, each with an even
    number of rows split between group A and group B."""
    rng = np.random.default_rng(seed)
    # Cluster-level random intercepts (normally shaped, sum ~ 0 across clusters).
    cluster_intercepts = rng.normal(0.0, 1.5, size=n_clusters)
    cluster_intercepts -= cluster_intercepts.mean()
    rows = []
    for c_idx, intercept in enumerate(cluster_intercepts):
        cluster_id = f"C{c_idx}"
        # Group B rows first, then group A rows, alternating to keep balance.
        sizes = {"B": rows_per_cluster // 2, "A": rows_per_cluster - rows_per_cluster // 2}
        for grp, n_ in sizes.items():
            for _ in range(n_):
                residual = rng.normal(0.0, resid_sd)
                y = intercept + (true_offset if grp == "B" else 0.0) + residual
                rows.append({"cluster": cluster_id, "group": grp, "outcome": float(y)})
    return pd.DataFrame(rows)


def _run(df: pd.DataFrame, **params) -> AnalysisResult:
    return MixedEffectsAnalysis().run(
        df, {"alpha": 0.05, **params},
        {"outcome": "outcome", "group": "group", "cluster": "cluster"},
        _ctx(),
    )


def _ref_fit(df: pd.DataFrame):
    """statsmodels MixedLM is the documented reference for this analysis."""
    import statsmodels.formula.api as smf

    model = smf.mixedlm("outcome ~ C(group)", df, groups=df["cluster"], re_formula="1")
    return model.fit(reml=True)


def test_coefficients_match_statsmodels_reference():
    df = _make_main_df()
    result = _run(df)
    ref = _ref_fit(df)

    coef = result.tables["Fixed effects"].set_index("Term")
    # Compare every fixed-effect coefficient (intercept + group levels).
    for term, ref_b in ref.params.items():
        label = "Intercept" if term == "Intercept" else term
        assert float(coef.loc[label, "Coefficient"]) == pytest.approx(
            float(ref_b), abs=1e-4
        )
    # Hand-set group offset reproduces.
    grp_B_coef = float(coef.loc["C(group)[T.B]", "Coefficient"])
    assert grp_B_coef == pytest.approx(3.0, abs=0.05)


def test_icc_computed_from_variance_components():
    df = _make_main_df()
    result = _run(df)
    ref = _ref_fit(df)

    var_intercept = float(np.diag(ref.cov_re)[0])
    var_residual = float(ref.scale)
    expected_icc = var_intercept / (var_intercept + var_residual)

    rates = result.tables["Random effects (variance components)"].set_index("Effect")
    got_between = float(rates.loc["Random intercept (between clusters)", "Variance"])
    got_within = float(rates.loc["Residual (within clusters)", "Variance"])
    assert got_between == pytest.approx(var_intercept, abs=1e-4)
    assert got_within == pytest.approx(var_residual, abs=1e-4)

    icc_row = result.tables["Intraclass correlation"].iloc[0]
    got_icc = float(icc_row["Value"])
    assert got_icc == pytest.approx(expected_icc, abs=1e-4)


def test_refuses_single_group():
    df = pd.DataFrame(
        {"outcome": [1.0, 2.0, 3.0, 4.0], "cluster": ["C0", "C1", "C2", "C3"],
         "group": ["A", "A", "A", "A"]}
    )
    with pytest.raises(AssumptionError):
        _run(df)


def test_refuses_fewer_than_two_clusters():
    df = pd.DataFrame(
        {"outcome": [1.0, 2.0, 3.0, 4.0], "cluster": ["C0", "C0", "C0", "C0"],
         "group": ["A", "A", "B", "B"]}
    )
    with pytest.raises(AssumptionError):
        _run(df)


def test_refuses_cluster_with_single_row():
    df = _make_main_df(n_clusters=6, rows_per_cluster=4)
    # Shrink one cluster to a single row.
    single_cluster_row = df.loc[df["cluster"] == "C0"].head(1)
    rest = df.loc[df["cluster"] != "C0"]
    bad = pd.concat([rest, single_cluster_row], ignore_index=True)
    with pytest.raises(AssumptionError, match="at least two observations"):
        _run(bad)


def test_missing_values_excluded_with_warning_not_imputed():
    df = _make_main_df(n_clusters=8, rows_per_cluster=4)
    n_before = len(df)
    df.loc[2, "outcome"] = np.nan  # a cluster-A row
    df.loc[30, "outcome"] = np.nan  # a cluster-B row
    result = _run(df)
    assert any("row(s)" in w and "missing" in w for w in result.warnings)
    # Listwise exclusion means y=2 and y=30 rows are gone, so n must be 2 fewer.
    assert int(result.summaries["total observations"]) == n_before - 2
    # No imputation: the methods sentence explicitly says nothing was imputed.
    assert any("imputed" in m for m in result.methods)


def test_figure_methods_and_what_does_not_tell():
    df = _make_main_df()
    result = _run(df)
    assert len(result.figures) == 1
    assert result.figures[0].name == "mixed_effects_boxplot"
    assert len(result.methods) >= 3
    methods_text = " ".join(result.methods)
    assert "mixed model" in methods_text or "MixedLM" in methods_text
    assert result.what_does_not_tell
    # Fixed-effects table present, random effects present, ICC present.
    assert "Fixed effects" in result.tables
    assert "Random effects (variance components)" in result.tables
    assert "Intraclass correlation" in result.tables


def test_expert_review_flag_on_small_total():
    df = _make_main_df(n_clusters=3, rows_per_cluster=4)  # total n = 12, < 30
    result = _run(df)
    assert result.expert_review, "expected an expert-review notice for small total n"
    assert any("sample size" in e or "cluster" in e for e in result.expert_review)
