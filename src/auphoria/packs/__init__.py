"""AUPHORIA discipline packs package.

Each discipline pack is an OPTIONAL install (a pyproject "extra"). The core
install stays light (numpy/pandas/scipy/matplotlib/...); a student who needs a
discipline's advanced or specialised analyses installs the pack they want:

    pip install "auphoria[health] @ git+REPO_URL_PLACEHOLDER"

Every analysis carries an optional ``pack`` and ``requires`` list in its
manifest. ``requires`` names the Python packages that analysis needs; the pack
extra declares them so ``pip install auphoria[<pack>]`` pulls them all in.
The engine refuses to run an analysis whose ``requires`` are not importable,
showing the exact pack to install instead of a raw ImportError.
"""

from __future__ import annotations

from importlib.resources import files as _pkg_files
from pathlib import Path

import yaml


def _packs_path() -> Path:
    try:
        return Path(_pkg_files("auphoria.packs").joinpath("packs.yaml"))
    except (ModuleNotFoundError, FileNotFoundError):  # editable/odd layouts
        return Path(__file__).resolve().parent / "packs.yaml"


def load_packs() -> dict[str, dict]:
    """Return {pack_id: pack_def} read from packs.yaml."""
    with _packs_path().open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    return {p["id"]: p for p in doc.get("packs", [])}


def pack_ids() -> list[str]:
    return sorted(load_packs())


def install_command(pack_id: str) -> str:
    """The exact pip command to install one discipline pack (local form)."""
    return f'pip install -e ".[{pack_id}]"'


def install_command_git(pack_id: str) -> str:
    """The public install command, using the REPO_URL_PLACEHOLDER literal."""
    return f'pip install "auphoria[{pack_id}] @ git+REPO_URL_PLACEHOLDER"'


def missing_requires(requires: list[str] | None) -> list[str]:
    """Return the names in ``requires`` that cannot be imported.

    ``requires`` are module names (e.g. "statsmodels", "sklearn",
    "pydeseq2", "gseapy"). An empty result means every required package is
    available.
    """
    missing: list[str] = []
    for name in requires or []:
        try:
            __import__(name)
        except Exception:  # noqa: BLE001 - any failure means the dep is unusable
            missing.append(name)
    return missing


# pip distribution name -> import module name (used to check pack deps).
_PIP_TO_MODULE = {
    "scikit-learn": "sklearn",
    "PyDESeq2": "pydeseq2",
    "statsmodels": "statsmodels",
    "gseapy": "gseapy",
}


def _base_pip_name(spec: str) -> str:
    """Extract the bare distribution name from a spec like 'statsmodels>=0.13,<1'."""
    import re

    return re.split(r"[<>=!~\[; ]", spec.split()[0], maxsplit=1)[0]


def missing_pack_deps(pip_specs: list[str] | None) -> list[str]:
    """Return the pip names in ``pip_specs`` (version specs) that are not importable."""
    missing: list[str] = []
    for spec in pip_specs or []:
        name = _base_pip_name(str(spec))
        module = _PIP_TO_MODULE.get(name, name)
        if module in missing_requires([module]):
            missing.append(name)
    return missing


def deps_message(requires: list[str], pack_id: str | None) -> str:
    """A plain-English 'how to fix this' message for a missing dependence."""
    readable = " ".join(x.replace("-", "_") for x in requires)
    if pack_id and pack_id in load_packs():
        hint = (
            f"Install the '{pack_id}' pack to get these:  "
            f"{install_command_git(pack_id)}"
        )
        local = f"   (or, during development: {install_command(pack_id)})"
    else:
        hint = f"Install the missing package(s):  pip install {readable}"
        local = ""
    return f"The analysis needs: {', '.join(requires)}. {hint}.\n{local}".rstrip()
