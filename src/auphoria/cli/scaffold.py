"""Scaffolding for new AUPHORIA analysis modules.

`auphoria new-module <id>` generates a complete analysis skeleton that follows
the project conventions and is discoverable by the registry:

    src/auphoria/analyses/<id>/
        manifest.yaml
        analysis.py
        README.md
        tests/test_<id>.py

The template lives in ``auphoria/cli/templates/analysis/`` (shipped in the
wheel via package-data). Placeholders are substituted, and the analysis is
registered in ``catalog/analyses.yaml`` so the "every built analysis appears in
the catalogue" sync test stays green.

This is a DEVELOPER/MAINTAINER command for building new analyses; end users do
not need it. It only writes inside the repository working tree it is run from.
"""

from __future__ import annotations

import re
from importlib.resources import files as _pkg_files
from pathlib import Path

from auphoria.core.errors import InputValidationError

#: Place-holder tokens in the template files and their substitution values.
#: MODULE_ID    -> the id (folder name), used in code/tests/manifest.
#: MODULE_PATH_ID -> a filesystem-safe variant of the id for logger names etc.
#: MODULE_NAME  -> the human name.
#: MODULE_CLASS -> the CamelCase class name derived from the id.
_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def validate_module_id(module_id: str) -> str:
    """Normalise and validate a new analysis id (must be a kebab-case id)."""
    module_id = module_id.strip().lower()
    if not _ID_RE.match(module_id):
        raise InputValidationError(
            f"Invalid analysis id '{module_id}'.",
            hint="Use lowercase letters, digits and hyphens only, e.g. "
                 "'my-analysis'.",
        )
    return module_id


def class_for(module_id: str) -> str:
    """Turn a kebab-case id into a CamelCase class name.

    ``my-analysis`` -> ``MyAnalysis``; ``ttest`` -> ``TtestAnalysis``.
    ``chi-square-test`` -> ``ChiSquareTestAnalysis``.
    """
    parts = module_id.split("-")
    return "".join(p.title() for p in parts) + "Analysis"


def _template_dir() -> Path:
    try:
        return Path(_pkg_files("auphoria.cli").joinpath("templates", "analysis"))
    except (ModuleNotFoundError, FileNotFoundError):  # editable/odd layouts
        return Path(__file__).resolve().parent / "templates" / "analysis"


def _substitute(text: str, module_id: str, module_name: str) -> str:
    replacements = {
        "{{ MODULE_ID }}": module_id,
        "{{ MODULE_NAME }}": module_name,
        "{{ MODULE_CLASS }}": class_for(module_id),
        "{{ MODULE_PATH_ID }}": module_id.replace("-", "_"),
    }
    for token, value in replacements.items():
        text = text.replace(token, value)
    return text


def _register_in_catalogue(module_id: str, module_name: str, repo_root: Path) -> None:
    """Append a catalogue entry so the built-analysis sync test stays green."""
    import yaml

    cat_path = repo_root / "catalog" / "analyses.yaml"
    data = yaml.safe_load(cat_path.read_text(encoding="utf-8"))
    if any(a.get("id") == module_id for a in data.get("analyses", [])):
        return  # already registered
    entry = {
        "id": module_id,
        "name": module_name,
        "plain_english_question": "TODO-VERIFY: one-sentence research question this analysis answers.",
        "levels": ["BS", "MPhil"],
        "disciplines": ["life-sciences"],
        "design": "TODO-VERIFY: study design this analysis fits.",
        "data_requirements": "TODO-VERIFY: required columns/shape.",
        "assumptions_to_check": ["TODO-VERIFY: assumptions."],
        "alternatives_when_assumptions_fail": ["TODO-VERIFY: alternatives."],
        "python_library_and_function": "TODO-VERIFY: library.function",
        "outputs": ["TODO-VERIFY: outputs."],
        "common_mistakes": ["TODO-VERIFY: common mistakes."],
        "priority": "P3",
        "pack": ["core"],
        "sources": [],
    }
    data.setdefault("analyses", []).append(entry)
    yaml.safe_dump(data, cat_path.open("w", encoding="utf-8"), sort_keys=False,
                   allow_unicode=True)


def _repo_root() -> Path:
    """Find the repository root from the CURRENT DIRECTORY, not from
    ``__file__``. ``auphoria new-module`` is a developer command that must be
    run from a source tree; deriving the root from the installed module's path
    lands in site-packages for a non-editable install and would silently write
    analysis code into your Python installation.
    """
    cwd = Path.cwd()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "pyproject.toml").is_file() and \
           (candidate / "src" / "auphoria" / "analyses").is_dir():
            return candidate
    raise InputValidationError(
        "auphoria new-module must be run from the AUPHORIA source tree.",
        hint=f"cd into a git clone of the repository, then re-run it here ('{cwd}' "
             "is not inside a source tree).",
    )


def new_module(module_id: str, module_name: str) -> tuple[Path, list[Path]]:
    """Create a new analysis module directory and return (dir, written paths)."""
    module_id = validate_module_id(module_id)
    module_name = module_name.strip() or module_id.replace("-", " ").title()

    repo_root = _repo_root()
    analyses_dir = repo_root / "src" / "auphoria" / "analyses"
    target = analyses_dir / module_id
    if target.exists():
        raise InputValidationError(
            f"Analysis '{module_id}' already exists at {target}.",
            hint="Choose a different id, or edit the existing module.",
        )
    target.mkdir(parents=True, exist_ok=True)
    (target / "tests").mkdir(exist_ok=True)

    written: list[Path] = []
    template_dir = _template_dir()
    test_rel = Path("tests") / f"test_{module_id}.py"
    files = [
        ("manifest.yaml", "manifest.yaml.tpl"),
        ("analysis.py", "analysis.py.tpl"),
        ("README.md", "README.md.tpl"),
        (str(test_rel), "tests/test_{{ MODULE_ID }}.py.tpl"),
    ]
    for rel, tpl_name in files:
        tpl_src = template_dir / tpl_name
        text = tpl_src.read_text(encoding="utf-8")
        out = target / rel
        out.write_text(_substitute(text, module_id, module_name), encoding="utf-8")
        written.append(out)

    _register_in_catalogue(module_id, module_name, repo_root)
    return target, written
