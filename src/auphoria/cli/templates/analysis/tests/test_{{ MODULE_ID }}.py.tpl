"""Tests for the {{ MODULE_NAME }} analysis.

REPLACE with small synthetic data that has KNOWN answers (hand-computed, or
from a documented reference example), compared against a reference
implementation (SciPy / statsmodels / scikit-learn). Follow the pattern in
src/auphoria/analyses/summary/tests/ or mann-whitney/tests/:

- facts a small deterministic dataset produces;
- a bad-input case (e.g. a non-numeric outcome) to prove it is refused;
- a missing-value case to prove nothing is imputed and the count is reported;
- a figure and methods sentences are returned;
- what_does_not_tell is set.

The scaffold below keeps the suite green so `auphoria new-module` output runs
out of the box; expand it as you implement run().
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

import pandas as pd
import pytest

from auphoria.core.analysis import RunContext
from auphoria.core.errors import AssumptionError

# The folder name is imported via string so a hyphenated id works.
_analysis_module = importlib.import_module(
    "auphoria.analyses.{{ MODULE_ID }}.analysis"
)
AnalysisClass = _analysis_module.{{ MODULE_CLASS }}


def _ctx() -> RunContext:
    logger = logging.getLogger("auphoria_test_{{ MODULE_PATH_ID }}")
    logger.handlers = []
    return RunContext(
        seed=1,
        out_dir=Path("."),
        data_name="test",
        expert=False,
        _log=logger,
        _log_decision=lambda m: None,
    )


def _df() -> pd.DataFrame:
    return pd.DataFrame({"value": [1.0, 2.0, 3.0, 4.0], "group": ["a", "a", "b", "b"]})


def test_runs_and_returns_a_table() -> None:
    analysis = AnalysisClass()
    result = analysis.run(_df(), {}, {"outcome": "value"}, _ctx())
    assert "Summary" in result.tables
    assert len(result.methods) >= 1


def test_refuses_missing_outcome_column() -> None:
    analysis = AnalysisClass()
    with pytest.raises(AssumptionError):
        analysis.run(_df(), {}, {"outcome": "nope"}, _ctx())


def test_sets_what_does_not_tell() -> None:
    analysis = AnalysisClass()
    result = analysis.run(_df(), {}, {"outcome": "value"}, _ctx())
    assert result.what_does_not_tell.strip()
