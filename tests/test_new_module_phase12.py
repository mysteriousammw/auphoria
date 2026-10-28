"""Phase 12 tests: the `auphoria new-module` scaffold.

Covers: the CLI command scaffolds a valid, ruff-clean, discoverable analysis
module (manifest + code + README + tests), registers it in the catalogue, and
the generated skeleton passes its own tests.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ANALYSES = REPO_ROOT / "src" / "auphoria" / "analyses"


def _env() -> dict:
    """Subprocess env: put the source ``src`` on PYTHONPATH so the just-
    scaffolded module (written to the source tree) resolves no matter what
    install mode is in effect. Under an editable install this is harmless; under
    a non-editable install (publish audit's fresh venv) it is REQUIRED, else
    ``importlib.import_module('auphoria.analyses.<new-id>.analysis')`` resolves
    to site-packages, which does not yet contain the new module."""
    import os

    env = dict(os.environ)
    src = str(REPO_ROOT / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src if not existing else f"{src}{os.pathsep}{existing}"
    return env


@pytest.fixture()
def clean_scratch(tmp_path, monkeypatch):
    """Isolate catalog + analyses by monkeypatching repo paths is hard (they're
    module-level constants), so we instead scaffold into the real tree and
    clean up afterwards. This fixture returns the module id to use and always
    removes the created dir + catalogue entry on teardown."""
    module_id = "zzz-scaffold-test"

    def _cleanup():
        d = ANALYSES / module_id
        if d.exists():
            import shutil

            shutil.rmtree(d)
        cat_path = REPO_ROOT / "catalog" / "analyses.yaml"
        data = yaml.safe_load(cat_path.read_text(encoding="utf-8"))
        data["analyses"] = [a for a in data["analyses"] if a.get("id") != module_id]
        yaml.safe_dump(data, cat_path.open("w", encoding="utf-8"),
                       sort_keys=False, allow_unicode=True)

    yield module_id
    _cleanup()


def test_new_module_scaffolds_valid_module(clean_scratch):
    module_id = clean_scratch
    res = subprocess.run(
        [sys.executable, "-m", "auphoria", "new-module", module_id, "--name", "Zzz Scaffold"],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    d = ANALYSES / module_id
    for rel in ("manifest.yaml", "analysis.py", "README.md",
                "tests/test_zzz-scaffold-test.py"):
        assert (d / rel).is_file(), f"missing {rel}"


def test_scaffolded_module_is_ruff_clean(clean_scratch):
    subprocess.run(
        [sys.executable, "-m", "auphoria", "new-module", clean_scratch,
         "--name", "Zzz Scaffold"],
        capture_output=True, text=True,
    )
    r = subprocess.run(["ruff", "check", str(ANALYSES / clean_scratch)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_scaffolded_module_passes_its_own_tests(clean_scratch):
    subprocess.run(
        [sys.executable, "-m", "auphoria", "new-module", clean_scratch,
         "--name", "Zzz Scaffold"],
        capture_output=True, text=True, env=_env(),
    )
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q",
         str(ANALYSES / clean_scratch / "tests")],
        capture_output=True, text=True, env=_env(),
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert ("passed" in r.stdout) or ("100%" in r.stdout)


def test_scaffold_registers_in_catalogue_and_is_discoverable(clean_scratch):
    subprocess.run(
        [sys.executable, "-m", "auphoria", "new-module", clean_scratch,
         "--name", "Zzz Scaffold"],
        capture_output=True, text=True, env=_env(),
    )
    # Catalogue sync invariant holds.
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q",
         str(REPO_ROOT / "tests" / "test_core.py") + "::test_catalogue_in_sync_with_registry"],
        capture_output=True, text=True, env=_env(),
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_new_module_rejects_bad_id(clean_scratch):
    res = subprocess.run(
        [sys.executable, "-m", "auphoria", "new-module", "Bad ID!"],
        capture_output=True, text=True,
    )
    assert res.returncode != 0
    assert "Invalid analysis id" in (res.stdout + res.stderr)
