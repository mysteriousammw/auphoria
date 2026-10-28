"""Analysis registry.

Discovers every installed analysis by scanning ``src/auphoria/analyses/*/``
for a ``manifest.yaml`` (shipped in the wheel), validates the manifest, and
loads the corresponding ``analysis.py`` module on demand. The human-facing
catalogue ``catalog/analyses.yaml`` at the repository root is kept in sync by
a test; at runtime the manifests are authoritative.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from auphoria.core.errors import ConfigError, InputValidationError
from auphoria.core.manifest import validate_manifest

_ANALYSES_DIR = Path(__file__).resolve().parent.parent / "analyses"

_REQUIRED_MANIFEST_KEYS = (
    "id",
    "name",
    "maturity",
    "description",
    "levels",
    "disciplines",
    "inputs",
    "parameters",
    "outputs",
    "assumptions",
    "limitations",
    "test_data",
)


@dataclass(frozen=True)
class AnalysisInfo:
    """Metadata about one analysis, read from its manifest."""

    id: str
    name: str
    maturity: str
    description: str
    levels: tuple[str, ...] = ()
    disciplines: tuple[str, ...] = ()
    manifest: dict[str, Any] = field(default_factory=dict, compare=False)
    directory: Path = field(default_factory=Path)


def _load_manifest(directory: Path) -> dict[str, Any]:
    manifest_path = directory / "manifest.yaml"
    if not manifest_path.is_file():
        raise ConfigError(
            f"Analysis directory '{directory.name}' has no manifest.yaml.",
            hint="Every analysis needs a manifest.yaml describing it.",
        )
    # Validate via pydantic (plain-English errors on malformed manifests).
    data = validate_manifest(manifest_path)

    missing = [k for k in _REQUIRED_MANIFEST_KEYS if k not in data]
    if missing:
        raise ConfigError(
            f"Manifest '{directory.name}/manifest.yaml' is missing required key(s): "
            f"{', '.join(missing)}.",
            hint="Add the missing keys (see an existing analysis for the format).",
        )
    id_value = str(data["id"]).strip()
    if id_value != directory.name:
        raise ConfigError(
            f"Manifest id '{id_value}' does not match its folder '{directory.name}'.",
            hint="The manifest 'id' must equal the analysis folder name.",
        )
    maturity = str(data.get("maturity", "")).strip().lower()
    if not maturity:
        raise ConfigError(
            f"Manifest '{directory.name}' has an empty 'maturity'.",
            hint="Set maturity to 'experimental' (never 'validated').",
        )
    # Enforce the maturity/reviewer rules (reviewed/validated need a reviewer).
    from auphoria.core.manifest import validate_maturity

    validate_maturity(data, directory.name)
    for key in ("levels", "disciplines"):
        value = data.get(key, [])
        if not isinstance(value, list):
            raise ConfigError(
                f"Manifest '{directory.name}' key '{key}' must be a list.",
            )
        data[key] = [str(v) for v in value]
    return data


def _discover_analysis_dirs() -> list[Path]:
    if not _ANALYSES_DIR.is_dir():
        raise ConfigError(
            f"Analyses directory not found: {_ANALYSES_DIR}",
            hint="Reinstall auphoria (pip install -e .).",
        )
    return sorted(
        child for child in _ANALYSES_DIR.iterdir()
        if child.is_dir()
        and not child.name.startswith(("_", "."))
        and child.name != "__pycache__"
    )


def discover() -> dict[str, AnalysisInfo]:
    """Build {analysis_id: AnalysisInfo} from installed manifests (no imports)."""
    result: dict[str, AnalysisInfo] = {}
    for directory in _discover_analysis_dirs():
        manifest = _load_manifest(directory)
        id_value = str(manifest["id"])
        result[id_value] = AnalysisInfo(
            id=id_value,
            name=str(manifest.get("name", id_value)),
            maturity=str(manifest.get("maturity", "experimental")),
            description=str(manifest.get("description", "")),
            levels=tuple(manifest.get("levels", [])),
            disciplines=tuple(manifest.get("disciplines", [])),
            manifest=manifest,
            directory=directory,
        )
    if not result:
        raise ConfigError("No analyses were discovered from installed manifests.")
    return result


def get(analysis_id: str) -> AnalysisInfo:
    """Return AnalysisInfo for one id, or raise a helpful InputValidationError."""
    info = discover()
    if analysis_id not in info:
        available = ", ".join(sorted(info)) or "(none)"
        raise InputValidationError(
            f"Unknown analysis '{analysis_id}'.",
            hint=f"Available analyses: {available}. Run 'auphoria list' to see them.",
        )
    return info[analysis_id]


def list_analyses() -> list[str]:
    """Return sorted analysis ids (used by front ends)."""
    return sorted(discover())


def load_analysis(analysis_id: str) -> Any:
    """Import and return the analysis instance for ``analysis_id``.

    The analysis module must define a module-level ``ANALYSIS`` object that is
    a subclass of ``auphoria.core.analysis.Analysis`` with matching ``id``.
    """
    get(analysis_id)
    module_name = f"auphoria.analyses.{analysis_id}.analysis"
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001 - reported to the log
        raise ConfigError(
            f"The analysis '{analysis_id}' could not be loaded "
            f"({type(exc).__name__}).",
            hint="See log.txt for the traceback; report this to the maintainers.",
        ) from exc
    instance = getattr(module, "ANALYSIS", None)
    if instance is None:
        raise ConfigError(
            f"Analysis '{analysis_id}' does not expose an 'ANALYSIS' object.",
            hint="Define ANALYSIS = MyAnalysis() at module level.",
        )
    if getattr(instance, "id", None) != analysis_id:
        raise ConfigError(
            f"Analysis instance id '{getattr(instance, 'id', None)}' does not "
            f"match '{analysis_id}'.",
            hint="Set the class/instance id to match the folder name.",
        )
    return instance
