"""Root conftest: shared fixtures for the ENTIRE suite.

Applied to both ``tests/`` and every ``src/auphoria/analyses/*/tests/`` dir.
Autouse fixtures here run around every test in the repo.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _close_matplotlib_figures():
    """Analyses return open figures; tests call run() directly (bypassing the
    engine's plt.close), so close them per test to avoid piling up 20+."""
    import matplotlib.pyplot as plt

    yield
    plt.close("all")
