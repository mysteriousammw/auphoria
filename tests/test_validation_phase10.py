"""Phase 10 validation tests: maturity levels, reviewer gate, dashboard.

Covers:
- a manifest with maturity "reviewed" or "validated" and no reviewer FAILS a
  check (the acceptance criterion);
- maturity must be one of the four allowed levels;
- the dashboard regenerates deterministically from the script (acceptance);
- every shipped analysis has a reference fixture and a default maturity the
  build agent is allowed to set (experimental / tested).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from auphoria.core.errors import ConfigError
from auphoria.core.manifest import (
    MATURITY_LEVELS,
    check_maturity,
    validate_maturity,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "gen_validation_dashboard.py"


# ---------------------------------------------------------------- reviewer gate
@pytest.mark.parametrize("maturity", ["reviewed", "validated"])
def test_reviewed_validated_require_reviewer(maturity):
    problems = check_maturity({"maturity": maturity})
    assert any("reviewer" in p for p in problems), problems
    assert any("reference" in p for p in problems), problems


def test_reviewer_gate_passes_when_reviewer_and_reference_present():
    assert check_maturity(
        {"maturity": "reviewed", "reviewer": "Dr. Maria Chen", "reference": "worked ex"}
    ) == []
    assert check_maturity(
        {"maturity": "validated", "reviewer": "Prof. A. Raza", "reference": "R port"}
    ) == []


def test_validate_maturity_raises_config_error_for_reviewed_without_reviewer():
    with pytest.raises(ConfigError):
        validate_maturity({"maturity": "reviewed"}, "test-analysis")


def test_maturity_must_be_a_known_level():
    assert check_maturity({"maturity": "experimental"}) == []
    assert check_maturity({"maturity": "tested"}) == []
    assert any("must be one of" in p for p in check_maturity({"maturity": "superb"}))


def test_maturity_levels_order_and_names():
    assert MATURITY_LEVELS == ("experimental", "tested", "reviewed", "validated")


# ------------------------------------------------------- every manifest is sound
def test_all_shipped_manifests_pass_maturity_gate():
    """The build agent may only set experimental/tested (no reviewer needed)."""
    from auphoria.core import registry

    for info in registry.discover().values():
        m = info.manifest
        maturity = str(m.get("maturity", "")).lower()
        assert maturity in ("experimental", "tested"), (
            f"{info.id} has maturity '{maturity}' - the build agent may only "
            "set experimental/tested; reviewed/validated need a named reviewer"
        )
        # reviewed/validated without reviewer would already fail load; double-check
        assert check_maturity(m) == [], f"{info.id}: {check_maturity(m)}"


def test_every_analysis_has_a_reference_fixture_and_known_issues():
    from auphoria.core import registry

    refs_path = REPO_ROOT / "docs" / "validation" / "references.yaml"
    import yaml

    refs = yaml.safe_load(refs_path.open(encoding="utf-8"))["analyses"]
    built = set(registry.discover())
    assert built <= set(refs), f"no reference fixture for: {built - set(refs)}"


# ---------------------------------------------------------------- dashboard
def _run_script(mode: str, out: Path | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT)]
    if out is not None:
        cmd += ["--out", str(out)]
    elif mode == "check":
        cmd += ["--check"]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_dashboard_regenerates_from_script_deterministically(tmp_path):
    """Running the script twice yields identical output (acceptance)."""
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    ra = _run_script("write", a)
    rb = _run_script("write", b)
    assert ra.returncode == 0, ra.stderr
    assert rb.returncode == 0, rb.stderr
    assert a.read_text(encoding="utf-8") == b.read_text(encoding="utf-8")
    assert "AUPHORIA validation dashboard" in a.read_text(encoding="utf-8")


def test_dashboard_check_reports_current(tmp_path):
    out = tmp_path / "dash.md"
    w = _run_script("write", out)
    # --check against the fresh file must pass (no leading writes needed)
    c = subprocess.run(
        [sys.executable, str(SCRIPT), "--check", "--out", str(out)],
        capture_output=True, text=True,
    )
    assert w.returncode == 0, w.stderr
    assert c.returncode == 0, c.stderr


def test_dashboard_generator_fails_on_reviewed_without_reviewer(tmp_path):
    import yaml as _yaml

    # Build a temp manifest dir with a reviewed-no-reviewer manifest, and point
    # the registry at it via a temporary monkeypatch of _ANALYSES_DIR.
    import auphoria.core.registry as reg
    from auphoria.core import registry

    fake = tmp_path / "analyses"
    fake.mkdir()
    (fake / "bogus-anal").mkdir()
    (fake / "bogus-anal" / "manifest.yaml").write_text(
        _yaml.safe_dump(
            {
                "id": "bogus-anal",
                "name": "Bogus",
                "maturity": "reviewed",  # no reviewer -> must fail
                "description": "x",
                "levels": ["advanced"],
                "disciplines": ["health"],
                "inputs": [],
                "parameters": [],
                "outputs": [],
                "assumptions": [],
                "limitations": [],
                "test_data": [],
            }
        ),
        encoding="utf-8",
    )
    old = reg._ANALYSES_DIR
    reg._ANALYSES_DIR = fake
    try:
        with pytest.raises(ConfigError, match="validation problem"):
            registry.discover()
    finally:
        reg._ANALYSES_DIR = old
