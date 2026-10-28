"""Phase 11 docs tests.

Enforces the acceptance criterion: the MkDocs site builds cleanly (no
warnings) and the per-analysis docs pages are generated (not stale).
Runs the build via `mkdocs build` with an isolated output dir so it never
writes into the repo's `site/`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def docs_build(tmp_path_factory) -> Path:
    """Run `mkdocs build` into an isolated dir; return (build_dir)."""
    out = tmp_path_factory.mktemp("mkdocs_site")
    env = dict(os.environ)
    env["NO_MKDOCS_2_WARNING"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "--site-dir", str(out)],
        cwd=REPO_ROOT,
        capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, f"mkdocs build failed:\n{proc.stdout}\n{proc.stderr}"
    return out


def test_docs_build_has_no_warnings(docs_build: Path, tmp_path) -> None:
    """Acceptance: `mkdocs build` prints no WARNING/ERROR lines."""
    env = dict(os.environ)
    env["NO_MKDOCS_2_WARNING"] = "1"
    out = tmp_path / "site"
    proc = subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "--site-dir", str(out)],
        cwd=REPO_ROOT, capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    # The vendor EOL banner is suppressed by NO_MKDOCS_2_WARNING; anything
    # remaining that says WARNING/ERROR is a real build warning.
    assert "WARNING" not in proc.stdout, proc.stdout
    assert "WARNING" not in proc.stderr, proc.stderr
    assert "ERROR" not in proc.stdout, proc.stdout
    assert "ERROR" not in proc.stderr, proc.stderr


def test_site_has_required_pages(docs_build: Path) -> None:
    for page in ("index.html", "quickstart/index.html", "choose/index.html",
                 "gallery/index.html", "troubleshooting/index.html",
                 "faq/index.html", "known-issues/index.html",
                 "responsible-use/index.html", "validation/index.html",
                 "analyses/index.html", "analyses/ttest/index.html"):
        assert (docs_build / page).exists(), f"missing built page: {page}"


def test_analysis_docs_are_generated_and_current() -> None:
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "gen_analysis_docs.py"), "--check"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "current" in (proc.stdout + proc.stderr).lower()


def test_install_commands_use_placeholder_and_are_marked() -> None:
    """Install blocks keep REPO_URL_PLACEHOLDER and carry a TODO-VERIFY note."""
    quickstart = (REPO_ROOT / "docs_site" / "quickstart.md").read_text(encoding="utf-8")
    mkdocs_yml = (REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    assert "REPO_URL_PLACEHOLDER" in quickstart
    assert "pipx install git+REPO_URL_PLACEHOLDER" in quickstart
    assert "TODO-VERIFY" in mkdocs_yml


def test_demo_video_scripts_exist() -> None:
    for name in ("demo_video.py", "demo_video_script.md"):
        assert (REPO_ROOT / "scripts" / name).exists(), f"missing {name}"
