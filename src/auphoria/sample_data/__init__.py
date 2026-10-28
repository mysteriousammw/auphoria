"""AUPHORIA sample-data package: small, educational datasets used for demos
and as test fixtures. Each CSV is deterministic via a fixed seed so tests can
hand-check answers against known reference values.
"""

from __future__ import annotations

from importlib.resources import files as _files
from pathlib import Path

import pandas as pd

# Package data directory (ships CSVs in the wheel via package-data).
_DATA_DIR = Path(_files("auphoria.sample_data").joinpath("data"))

_DATASETS = {
    "plant_growth": "plant_growth.csv",
    "survey": "survey.csv",
    "training": "training.csv",
    "diets": "diets.csv",
    "growth_cov": "growth_cov.csv",
    "schools": "schools.csv",
    "psych": "psych.csv",
    "survival": "survival.csv",
    "diagnosis": "diagnosis.csv",
    "features": "features.csv",
}


def sample_files() -> list[str]:
    """Names of the bundled sample datasets."""
    return sorted(_DATASETS)


def sample_path(name: str) -> Path:
    """Return the on-disk path of a sample dataset CSV."""
    if name not in _DATASETS:
        raise KeyError(
            f"Unknown sample dataset '{name}'. Available: {', '.join(sample_files())}"
        )
    return _DATA_DIR / _DATASETS[name]


def load(name: str) -> pd.DataFrame:
    """Load a sample dataset as a DataFrame."""
    return pd.read_csv(sample_path(name))


__all__ = ["sample_files", "sample_path", "load"]
