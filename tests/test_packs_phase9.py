"""Tests for the discipline-packs packaging (Phase 9).

Covers: the pack registry (packs.yaml), the deps-guard (missing_requires /
deps_message), the CLI `packs` and `list --pack` commands, and that the
https://github.com/mysteriousammw/auphoria install syntax is what the guard teaches.
"""

from __future__ import annotations

import subprocess

from auphoria.packs import (
    deps_message,
    install_command,
    install_command_git,
    load_packs,
    missing_pack_deps,
    missing_requires,
)


def test_packs_yaml_has_the_five_discipline_packs():
    packs = load_packs()
    for pid in ("agri-animal", "life-science", "health", "social", "econ-eng"):
        assert pid in packs, f"missing pack {pid}"
        assert packs[pid]["name"]
        assert packs[pid]["deps"], f"pack {pid} has no deps"


def test_pack_deps_are_heavy_and_optional():
    """Packs carry heavy deps; core should NOT require them."""
    packs = load_packs()
    all_deps = {d.split(">")[0].split("<")[0].split("=")[0]
                for p in packs.values() for d in p["deps"]}
    # These are the heavy, pack-only dependencies.
    assert "statsmodels" in all_deps
    assert "scikit-learn" in all_deps


def test_install_commands_use_placeholder():
    cmd = install_command_git("health")
    assert "https://github.com/mysteriousammw/auphoria" in cmd
    assert "auphoria[health]" in cmd
    # Local form has no placeholder.
    assert "https://github.com/mysteriousammw/auphoria" not in install_command("health")


def test_missing_requires_detects_absent_module():
    # A module that does not exist must be reported missing.
    assert "auphoria_no_such_pkg_xyz" in missing_requires(
        ["numpy", "auphoria_no_such_pkg_xyz"]
    )
    # Present modules are not reported.
    assert missing_requires(["numpy", "pandas"]) == []


def test_missing_pack_deps_maps_pip_to_module():
    # scikit-learn is the pip name; sklearn is the module.
    missing = missing_pack_deps(["scikit-learn", "statsmodels"])
    assert "scikit-learn" not in missing  # sklearn is present in this venv
    assert "statsmodels" not in missing


def test_deps_message_teaches_the_pack_install():
    msg = deps_message(["statsmodels"], "health")
    assert "statsmodels" in msg
    assert "health" in msg
    assert "https://github.com/mysteriousammw/auphoria" in msg
    assert "pip install" in msg


def test_deps_message_without_pack_gives_plain_pip_hint():
    msg = deps_message(["someheavy"], None)
    assert "pip install someheavy" in msg


def test_packs_cli_lists_all_packs(cli_python):
    proc = subprocess.run(
        cli_python + ["packs"], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr
    for pid in ("agri-animal", "life-science", "health", "social", "econ-eng"):
        assert pid in proc.stdout
    assert "https://github.com/mysteriousammw/auphoria" in proc.stdout


def test_list_pack_filter(cli_python):
    proc = subprocess.run(
        cli_python + ["list", "--pack", "health"], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr
    assert "analyses shown" in proc.stdout
