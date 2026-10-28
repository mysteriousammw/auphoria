"""Tests for the shared fit-checker used by the CLI menu and Colab notebook."""

from __future__ import annotations

from auphoria.core.fitting import analyses_that_fit


def test_all_analyses_fit_rich_numeric_dataset():
    """A dataset with numeric + categorical columns fits everything built."""
    ids = analyses_that_fit(["numeric", "categorical"])
    assert "describe" in ids
    assert "summary" in ids
    assert "ttest" in ids
    assert "correlation" in ids


def test_numeric_only_dataset_excludes_ttest():
    """ttest needs a categorical (group) column; without one it must not fit."""
    ids = analyses_that_fit(["numeric"])
    assert "ttest" not in ids
    assert "correlation" in ids  # two numeric columns suffice
    assert "describe" in ids


def test_categorical_only_dataset_excludes_most():
    """No numeric column -> nothing needing a numeric outcome fits."""
    ids = analyses_that_fit(["categorical"])
    assert "correlation" not in ids
    assert "ttest" not in ids
    # describe needs nothing -> always fits
    assert "describe" in ids


def test_empty_dataset_only_analyse_without_required_inputs():
    # describe + summary have no required inputs -> always fit; any analysis
    # with a required input (ttest/correlation) must not.
    ids = analyses_that_fit([])
    assert "describe" in ids
    assert "summary" in ids
    assert "ttest" not in ids
    assert "correlation" not in ids
