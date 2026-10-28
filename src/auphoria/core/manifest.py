"""Manifest loader and validator (pydantic).

Every analysis declares itself in ``manifest.yaml``. Before the registry trusts
any manifest it is validated here with pydantic so a malformed manifest fails
with a plain-English message instead of a mystifying exception later.

The schema is intentionally strict about shape but tolerant about content:
we validate the *fields and types* that drive the engine (inputs, parameters,
maturity, levels, ...) and keep the rich human fields (description, sources) as
free text. Nothing here edits the data or the manifest; it only checks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from auphoria.core.errors import ConfigError

ALL_COLUMN_KINDS = ("numeric-column", "categorical-column", "datetime-column", "any-column")
ALL_PARAM_TYPES = ("number", "integer", "boolean", "choice", "text")

#: The only allowed maturity tiers, from lowest to highest. "experimental" and
#: "tested" may be set by the build agent; "reviewed" and "validated" require a
#: named human reviewer in the manifest's `reviewer` field (enforced).
MATURITY_LEVELS = ("experimental", "tested", "reviewed", "validated")


class ManifestInput(BaseModel):
    """One declared column input."""

    model_config = ConfigDict(extra="allow")

    name: str
    kind: str = "any-column"
    required: bool = False
    description: str = ""
    constraints: str = ""
    accepts: list[str] | None = None

    @field_validator("kind")
    @classmethod
    def _kind_ok(cls, v: str) -> str:
        if v not in ALL_COLUMN_KINDS:
            raise ValueError(
                f"input kind '{v}' must be one of {', '.join(ALL_COLUMN_KINDS)}"
            )
        return v

    @field_validator("accepts")
    @classmethod
    def _accepts_ok(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        bad = [a for a in v if a not in ALL_COLUMN_KINDS]
        if bad:
            raise ValueError(f"accepts contains unknown kinds: {', '.join(bad)}")
        return v


class ManifestParameter(BaseModel):
    """One tunable parameter."""

    model_config = ConfigDict(extra="allow")

    name: str
    type: str = "number"
    default: Any | None = None
    description: str = ""
    required: bool = False
    choices: list[Any] = Field(default_factory=list)
    min: float | None = None
    max: float | None = None

    @field_validator("type")
    @classmethod
    def _type_ok(cls, v: str) -> str:
        if v not in ALL_PARAM_TYPES:
            raise ValueError(
                f"parameter type '{v}' must be one of {', '.join(ALL_PARAM_TYPES)}"
            )
        return v


class AnalysisManifest(BaseModel):
    """A validated analysis manifest (superset kept for rich human fields)."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    maturity: str
    description: str = ""
    levels: list[str] = Field(default_factory=list)
    disciplines: list[str] = Field(default_factory=list)
    inputs: list[ManifestInput] = Field(default_factory=list)
    parameters: list[ManifestParameter] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    test_data: list[str] = Field(default_factory=list)
    #: Optional discipline-pack membership (ids in auphoria.packs/packs.yaml).
    pack: list[str] = Field(default_factory=list)
    #: Optional heavy Python packages (module names) this analysis needs so it
    #: can refuse with an install hint when the pack extra is missing.
    requires: list[str] = Field(default_factory=list)
    #: Named human reviewer who has reviewed this analysis. REQUIRED when
    #: maturity is "reviewed" or "validated" (enforced in check_maturity).
    reviewer: str = ""
    #: Independent reference the analysis has been cross-checked against
    #: (e.g. "R: t.test; worked example: Zar 1999 Table 7.2").
    reference: str = ""
    #: Known issues / limitations recorded for this analysis (fills the
    #: validation dashboard "known issues" column).
    known_issues: list[str] = Field(default_factory=list)

    @field_validator("maturity")
    @classmethod
    def _maturity_ok(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("maturity cannot be empty")
        allowed = MATURITY_LEVELS
        if v not in allowed:
            raise ValueError(
                f"maturity must be one of {', '.join(allowed)} (got '{v}')"
            )
        return v

    # Allow unknown/extra human fields; they are preserved on the manifest dict
    # but we only validate the ones above are correctly typed.


def _load_yaml_raw(path: Path) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(
            f"Could not read manifest '{path}'.",
            hint="The file may be missing or contain invalid YAML.",
        ) from exc
    if not isinstance(data, dict):
        raise ConfigError(
            f"Manifest '{path}' is not a YAML mapping (a key/value list).",
            hint="A manifest.yaml must start with 'id:', 'name:', etc.",
        )
    return data


def validate_manifest(path: Path) -> dict[str, Any]:
    """Load and validate a manifest.yaml via pydantic.

    Returns the (validated, cleaned) manifest dict. Raises ConfigError with a
    plain-English message and pinpointed offending field when invalid.
    """
    data = _load_yaml_raw(path)
    try:
        manifest = AnalysisManifest(**data)
    except ValidationError as exc:
        # Build one readable message from the first few errors.
        problems = []
        for err in exc.errors():  # type: ignore[union-attr]
            loc = ".".join(str(x) for x in err.get("loc", [])) or "<top>"
            problems.append(f"  - {loc}: {err.get('msg', 'invalid')}")
        detail = "\n".join(problems[:6])
        more = "" if len(problems) <= 6 else f"\n  ... and {len(problems)-6} more"
        raise ConfigError(
            f"Manifest '{path}' is invalid.",
            hint=f"Fix the following fields:\n{detail}{more}",
        ) from exc

    # id must equal its folder name (checked by the registry too).
    return manifest.model_dump(exclude_unset=False)


def manifest_from_dict(data: dict[str, Any]) -> AnalysisManifest:
    """Validate an already-loaded manifest dict; raises ConfigError."""
    try:
        return AnalysisManifest(**data)
    except ValidationError as exc:
        problems = [
            f"  - {'.'.join(str(x) for x in err.get('loc', []))}: {err.get('msg','')}"
            for err in exc.errors()
        ]
        raise ConfigError(
            "Manifest is invalid.",
            hint="\n".join(problems[:6]),
        ) from exc


def check_maturity(manifest: dict[str, Any]) -> list[str]:
    """Return a list of validation problems for a manifest's maturity.

    Rules:
    - maturity must be one of MATURITY_LEVELS (already enforced by pydantic
      at load; this is the explicit check the dashboard/CI also run).
    - maturity "reviewed" or "validated" REQUIRES a named human reviewer.
    - an analysis claiming "reviewed"/"validated" must have a non-empty
      ``reference`` (what it was cross-checked against).

    Returns an empty list when the maturity is valid.
    """
    problems: list[str] = []
    maturity = str(manifest.get("maturity", "")).strip().lower()
    reviewer = str(manifest.get("reviewer", "")).strip()
    reference = str(manifest.get("reference", "")).strip()
    if maturity not in MATURITY_LEVELS:
        problems.append(
            f"maturity must be one of {', '.join(MATURITY_LEVELS)} (got '{maturity}')"
        )
        return problems
    if maturity in ("reviewed", "validated"):
        if not reviewer:
            problems.append(
                f"maturity '{maturity}' requires a named human reviewer "
                "(set the 'reviewer' field)."
            )
        if not reference:
            problems.append(
                f"maturity '{maturity}' requires a 'reference' describing the "
                "independent cross-check that was done."
            )
    return problems


def validate_maturity(manifest: dict[str, Any], analysis_id: str | None = None) -> None:
    """Raise ConfigError if the manifest's maturity is not acceptable.

    Called by the registry when loading an analysis and by the CLI dashboard
    regenerator, so a manifest claiming 'reviewed' or 'validated' without a
    reviewer is rejected.
    """
    problems = check_maturity(manifest)
    if not problems:
        return
    who = f"Analysis '{analysis_id}'" if analysis_id else "Manifest"
    raise ConfigError(
        f"{who} has a validation problem.",
        hint="\n".join(f"  - {p}" for p in problems),
    )
