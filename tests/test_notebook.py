"""Tests that the Colab notebook is valid and uses only the engine (no logic)."""

from __future__ import annotations

import json
from pathlib import Path

REPO_URL_PLACEHOLDER = "REPO_URL_PLACEHOLDER"
NOTEBOOK_PATH = Path(__file__).resolve().parent.parent / "notebooks" / "auphoria_colab.ipynb"


def _has_repo_url(text: str) -> bool:
    """True if the text still carries the placeholder OR a real http(s) URL."""
    return REPO_URL_PLACEHOLDER in text or "http://" in text or "https://" in text


def _load():
    return json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))


def _code_text() -> str:
    """All code-cell source concatenated (source is a list of lines)."""
    return "".join(
        "".join(c.get("source", []))
        for c in _load()["cells"] if c["cell_type"] == "code"
    )


def test_notebook_is_valid_json():
    nb = _load()
    assert nb["nbformat"] == 4
    assert isinstance(nb["cells"], list) and len(nb["cells"]) >= 6


def test_notebook_installs_from_placeholder():
    code = _code_text()
    assert "install" in code and "git+" in code
    assert _has_repo_url(code)  # placeholder before set_repo_url, URL after


def test_notebook_calls_engine_not_custom_analysis():
    code = _code_text()
    assert "auphoria.run(" in code
    assert ".run(" in code
    # The notebook must not reimplement any statistics logic.
    assert "stats.ttest" not in code
    assert "scipy" not in code or "import auphoria" in code


def test_notebook_has_privacy_notice():
    md = " ".join(
        "".join(c.get("source", [])).lower()
        for c in _load()["cells"] if c["cell_type"] == "markdown"
    )
    assert "google" in md and ("privacy" in md or "confidential" in md)
    assert "upload" in md


def test_notebook_downloads_zip():
    code = _code_text()
    # The notebook delegates zipping + downloading to the colab adapter
    # (front-end chores live in src/auphoria/adapters/colab.py, not here).
    assert "colab.zip_results" in code
    assert "colab.download" in code
    assert "google.colab" in code or "auphoria.adapters import colab" in code
