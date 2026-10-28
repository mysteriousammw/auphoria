"""Shared fixtures for the AUPHORIA test suite."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the package importable even if not pip-installed.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import auphoria.sample_data as sd  # noqa: E402


@pytest.fixture(scope="session")
def sample_csv() -> Path:
    """Path to the plant-growth sample CSV (includes deliberate blanks)."""
    return sd.sample_path("plant_growth")


@pytest.fixture(scope="session")
def survey_csv() -> Path:
    return sd.sample_path("survey")


@pytest.fixture()
def tmp_results(tmp_path: Path) -> Path:
    """A fresh scratch results dir per test."""
    return tmp_path / "results"


@pytest.fixture()
def cli_python() -> list[str]:
    """Invocation that runs the auphoria CLI through this interpreter."""
    return [sys.executable, "-m", "auphoria"]


@pytest.fixture(autouse=True)
def _reset_environment(monkeypatch: pytest.MonkeyPatch):
    """Never let a test write into the real ~/AUPHORIA_results."""
    from auphoria.core import engine as engine_mod

    monkeypatch.setattr(engine_mod, "DEFAULT_RESULTS_ROOT", Path("/tmp/auphoria_test_root"))
    yield


@pytest.fixture(autouse=True)
def _close_matplotlib_figures():
    """Analyses return open figures; tests call run() directly (bypassing the
    engine's plt.close), so close them per test to avoid piling up 20+."""
    import matplotlib.pyplot as plt

    yield
    plt.close("all")


def with_console(monkeypatch, inputs, outputs):
    """Feed inputs to input(); capture printed lines into `outputs` list."""
    iterator = iter(inputs)

    def fake_input(prompt="", *a, **k):
        outputs.append(prompt)
        return next(iterator, "")

    monkeypatch.setattr("builtins.input", fake_input)
    return monkeypatch
