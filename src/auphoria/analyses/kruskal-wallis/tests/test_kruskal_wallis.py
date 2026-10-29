"""Tests for the Kruskal-Wallis H test analysis.

Uses small synthetic data with known, hand-computable answers, and compares
against SciPy's reference implementation (the "documented reference").

Hand-computed example: group A = [1, 2, 3], B = [4, 5, 6], C = [7, 8, 9].
Combined ranks: A holds ranks 1, 2, 3 (sum 6); B holds 4, 5, 6 (sum 15);
C holds 7, 8, 9 (sum 24).  k = 3 groups, n_j = 3 each, N = 9.

H = 12/(N(N+1)) * sum(R_j^2/n_j) - 3(N+1)
  = 12/(9*10) * (36/3 + 225/3 + 576/3) - 3*10
  = 0.133333 * (12 + 75 + 192) - 30
  = 0.133333 * 279 - 30
  = 37.2 - 30
  = 7.2
df = k - 1 = 2.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from auphoria.core.analysis import RunContext
from auphoria.core.errors import AssumptionError

# The folder name contains a hyphen, so it cannot appear in an import
# statement; import the module via string and grab the class from it.
_analysis_module = importlib.import_module(
    "auphoria.analyses.kruskal-wallis.analysis"
)
KruskalWallisAnalysis = _analysis_module.KruskalWallisAnalysis


def _ctx() -> RunContext:
    logger = logging.getLogger("auphoria_test_kw")
    logger.handlers = []
    return RunContext(
        seed=1,
        out_dir=Path("."),
        data_name="test",
        expert=False,
        _log=logger,
        _log_decision=lambda m: None,
    )


def _df(groups: dict[str, list[float]]) -> pd.DataFrame:
    rows: list[tuple[float, str]] = []
    for g, vals in groups.items():
        rows += [(v, g) for v in vals]
    return pd.DataFrame(rows, columns=["value", "group"])


# Hand-computed example: A = [1,2,3], B = [4,5,6], C = [7,8,9] -> rank sums
# 6, 15, 24, N = 9, n_j = 3 -> H = 7.2, df = 2.
A = [1.0, 2.0, 3.0]
B = [4.0, 5.0, 6.0]
C = [7.0, 8.0, 9.0]


def test_kruskal_wallis_matches_scipy() -> None:
    analysis = KruskalWallisAnalysis()
    df = _df({"A": A, "B": B, "C": C})
    result = analysis.run(
        df, {"alpha": 0.05},
        {"outcome": "value", "group": "group"}, _ctx(),
    )
    ref = stats.kruskal(np.asarray(A), np.asarray(B), np.asarray(C))
    table = result.tables["Kruskal-Wallis test"]
    got_h = float(table.loc[table["Item"] == "H statistic", "Value"].iloc[0])
    got_p = float(table.loc[table["Item"] == "p-value", "Value"].iloc[0])
    got_df = int(table.loc[table["Item"] == "degrees of freedom (df)", "Value"].iloc[0])
    # Cross-check against SciPy's reference implementation.
    assert got_h == pytest.approx(float(ref.statistic), abs=1e-6)
    assert got_p == pytest.approx(float(ref.pvalue), abs=1e-4)
    # Hand-computed values: H = 7.2, df = k - 1 = 2.
    assert got_h == pytest.approx(7.2, abs=1e-6)
    assert got_df == 2


def test_kruskal_wallis_group_and_result_tables() -> None:
    analysis = KruskalWallisAnalysis()
    df = _df({"A": A, "B": B, "C": C})
    result = analysis.run(
        df, {"alpha": 0.05},
        {"outcome": "value", "group": "group"}, _ctx(),
    )
    gs = result.tables["Group statistics"].set_index("Group")
    assert int(gs.loc["A", "n"]) == 3
    assert int(gs.loc["B", "n"]) == 3
    assert int(gs.loc["C", "n"]) == 3
    assert float(gs.loc["A", "Median"]) == pytest.approx(2.0, abs=1e-4)
    assert float(gs.loc["B", "Median"]) == pytest.approx(5.0, abs=1e-4)
    assert float(gs.loc["C", "Median"]) == pytest.approx(8.0, abs=1e-4)
    table = result.tables["Kruskal-Wallis test"]
    assert int(table.loc[table["Item"] == "n (total)", "Value"].iloc[0]) == 9
    assert int(table.loc[table["Item"] == "number of groups", "Value"].iloc[0]) == 3
    assert table.loc[table["Item"] == "test", "Value"].iloc[0] == "Kruskal-Wallis H"


def test_kruskal_wallis_refuses_single_group() -> None:
    analysis = KruskalWallisAnalysis()
    df = pd.DataFrame({"value": [1.0, 2.0, 3.0], "group": ["A", "A", "A"]})
    with pytest.raises(AssumptionError):
        analysis.run(
            df, {"alpha": 0.05},
            {"outcome": "value", "group": "group"}, _ctx(),
        )


def test_kruskal_wallis_refuses_two_groups() -> None:
    """Two groups are not enough for Kruskal-Wallis (needs 3+)."""
    analysis = KruskalWallisAnalysis()
    df = pd.DataFrame({"value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
                       "group": ["A", "A", "B", "B", "C", "C"]})
    # Three groups: fine.
    result = analysis.run(
        df, {"alpha": 0.05},
        {"outcome": "value", "group": "group"}, _ctx(),
    )
    assert result.tables["Kruskal-Wallis test"] is not None

    df2 = pd.DataFrame({"value": [1.0, 2.0, 3.0, 4.0],
                        "group": ["A", "A", "B", "B"]})
    with pytest.raises(AssumptionError):
        analysis.run(
            df2, {"alpha": 0.05},
            {"outcome": "value", "group": "group"}, _ctx(),
        )


def test_kruskal_wallis_refuses_non_numeric_outcome_with_text() -> None:
    analysis = KruskalWallisAnalysis()
    df = pd.DataFrame({
        "value": ["1", "2", "three", "4", "5", "6", "7", "8", "9"],
        "group": ["A", "A", "A", "B", "B", "B", "C", "C", "C"],
    })
    with pytest.raises(AssumptionError):
        analysis.run(
            df, {"alpha": 0.05},
            {"outcome": "value", "group": "group"}, _ctx(),
        )


def test_kruskal_wallis_handles_missing_without_imputation() -> None:
    analysis = KruskalWallisAnalysis()
    df = _df({"A": A, "B": B, "C": C})
    # Drop 1 row from group A via a missing outcome value.
    df.iloc[0, df.columns.get_loc("value")] = np.nan
    result = analysis.run(
        df, {"alpha": 0.05},
        {"outcome": "value", "group": "group"}, _ctx(),
    )
    # Group A now has n = 2, the others n = 3; none imputed.
    gs = result.tables["Group statistics"].set_index("Group")
    assert int(gs.loc["A", "n"]) == 2
    assert int(gs.loc["B", "n"]) == 3
    assert int(gs.loc["C", "n"]) == 3
    assert any("row(s)" in w and "missing" in w for w in result.warnings)
    assert any("excluded" in m and "imputed" in m for m in result.methods)


def test_kruskal_wallis_missing_in_group_column_excluded() -> None:
    """Missingness in the group column is also excluded and counted."""
    analysis = KruskalWallisAnalysis()
    df = _df({"A": A, "B": B, "C": C})
    df.loc[0, "group"] = np.nan
    result = analysis.run(
        df, {"alpha": 0.05},
        {"outcome": "value", "group": "group"}, _ctx(),
    )
    gs = result.tables["Group statistics"].set_index("Group")
    assert int(gs.loc["A", "n"]) == 2
    assert int(gs.loc["B", "n"]) == 3
    assert int(gs.loc["C", "n"]) == 3


def test_kruskal_wallis_returns_figure_and_methods_and_honest_limits() -> None:
    analysis = KruskalWallisAnalysis()
    df = _df({"A": A, "B": B, "C": C})
    result = analysis.run(
        df, {"alpha": 0.05},
        {"outcome": "value", "group": "group"}, _ctx(),
    )
    assert len(result.figures) == 1
    assert result.figures[0].name == "kruskal_wallis_boxplot"
    assert len(result.methods) >= 3
    assert any("kruskal-wallis" in m.lower() for m in result.methods)
    # Honest limits: the result does not locate which groups differ.
    assert result.what_does_not_tell
    assert "which" in result.what_does_not_tell.lower() or "WHICH" in result.what_does_not_tell


def test_kruskal_wallis_check_fit_refuses_nonnumeric_group() -> None:
    analysis = KruskalWallisAnalysis()

    class _Col:
        def __init__(self, kind: str) -> None:
            self.kind = kind

    class _Profile:
        def by_name(self, name: str):
            del name
            return _Col("numeric")

    refusals = analysis.check_fit(
        _Profile(), {"alpha": 0.05}, {"outcome": "value", "group": "group"}
    )
    assert len(refusals) == 1
    assert "not a group" in refusals[0] or "not a group" in refusals[0]

