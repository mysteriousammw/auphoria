"""Parameter and input definitions, parsed from each analysis's manifest.yaml.

The manifest declares ``parameters`` (tunable options like alpha) and
``inputs`` (which columns the analysis needs). This module builds typed
specs, coerces raw user strings/values, and validates them, always with a
plain-English error plus a fix hint.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from auphoria.core.errors import ConfigError, InputValidationError

# Column-kind keys used in manifests for ``inputs``.
KIND_NUMERIC = "numeric-column"
KIND_CATEGORICAL = "categorical-column"
KIND_DATETIME = "datetime-column"
KIND_ANY = "any-column"
ALL_COLUMN_KINDS = (KIND_NUMERIC, KIND_CATEGORICAL, KIND_DATETIME, KIND_ANY)


@dataclass
class InputSpec:
    """One column input the analysis needs."""

    name: str
    kind: str            # one of ALL_COLUMN_KINDS
    required: bool
    description: str = ""
    constraints: str = ""  # free text, human-readable (e.g. "exactly two groups")
    accepts: list[str] = field(default_factory=lambda: list(ALL_COLUMN_KINDS))

    @classmethod
    def from_manifest(cls, raw: dict[str, Any], index: int = 0) -> InputSpec:
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ConfigError(
                f"Invalid manifest: input #{index} has no 'name'.",
                hint="Add a 'name' key to each input in manifest.yaml.",
            )
        kind = raw.get("kind", KIND_ANY)
        if kind not in ALL_COLUMN_KINDS:
            raise ConfigError(
                f"Invalid manifest: input '{name}' has unknown kind '{kind}'.",
                hint=f"Kind must be one of: {', '.join(ALL_COLUMN_KINDS)}.",
            )
        accepts = raw.get("accepts") or [kind]
        accepts = [a for a in accepts if a in ALL_COLUMN_KINDS] or [kind]
        return cls(
            name=name.strip(),
            kind=kind,
            required=bool(raw.get("required", False)),
            description=str(raw.get("description", "")),
            constraints=str(raw.get("constraints", "")),
            accepts=accepts,
        )


@dataclass
class ParameterSpec:
    """One tunable parameter the analysis accepts."""

    name: str
    ptype: str                     # number | integer | boolean | choice | text
    default: Any
    description: str = ""
    required: bool = False
    choices: tuple[Any, ...] = ()
    min_value: Any = None
    max_value: Any = None

    @classmethod
    def from_manifest(cls, raw: dict[str, Any]) -> ParameterSpec:
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ConfigError("Invalid manifest: a parameter has no 'name'.")
        ptype = raw.get("type", "number")
        if ptype not in ("number", "integer", "boolean", "choice", "text"):
            raise ConfigError(
                f"Parameter '{name}' has unknown type '{ptype}' in manifest.",
                hint="Allowed types: number, integer, boolean, choice, text.",
            )
        choices = tuple(str(c) for c in raw.get("choices", []))
        default = raw.get("default")
        if ptype == "choice" and choices and default is not None and str(default) not in choices:
            raise ConfigError(
                f"Parameter '{name}' default '{default}' is not in its choices {choices}.",
            )
        return cls(
            name=name.strip(),
            ptype=ptype,
            default=default,
            description=str(raw.get("description", "")),
            required=bool(raw.get("required", False)),
            choices=choices,
            min_value=raw.get("min"),
            max_value=raw.get("max"),
        )

    def coerce(self, raw: Any) -> Any:
        """Turn a raw user string/value into the right Python type, with checks."""
        if self.ptype in ("choice", "text"):
            value = str(raw).strip()
        elif raw is None or (isinstance(raw, str) and raw.strip() == ""):
            raise InputValidationError(
                f"The option '{self.name}' cannot be blank.",
                hint=f"Give it a value, e.g. '{self.default}'.",
            )
        elif self.ptype == "boolean":
            value = self._coerce_bool(raw)
        elif self.ptype == "integer":
            value = self._coerce_int(raw)
        else:  # number
            value = self._coerce_float(raw)

        if self.ptype == "choice":
            if self.choices and value not in self.choices:
                raise InputValidationError(
                    f"For '{self.name}', '{value}' is not one of the allowed options.",
                    hint=f"Allowed options: {', '.join(self.choices)}.",
                )
            return value

        if self.ptype in ("number", "integer"):
            if self.min_value is not None and value < self.min_value:
                raise InputValidationError(
                    f"'{self.name}' must be at least {self.min_value} (you gave {value}).",
                    hint=f"Use a value >= {self.min_value}.",
                )
            if self.max_value is not None and value > self.max_value:
                raise InputValidationError(
                    f"'{self.name}' must be at most {self.max_value} (you gave {value}).",
                    hint=f"Use a value <= {self.max_value}.",
                )
        return value

    @staticmethod
    def _coerce_bool(raw: Any) -> bool:
        if isinstance(raw, bool):
            return raw
        low = str(raw).strip().lower()
        if low in ("true", "yes", "y", "1", "on"):
            return True
        if low in ("false", "no", "n", "0", "off"):
            return False
        raise InputValidationError(
            f"'{raw}' is not a yes/no value.",
            hint="Use 'true' or 'false'.",
        )

    @staticmethod
    def _coerce_int(raw: Any) -> int:
        try:
            return int(str(raw).strip())
        except ValueError:
            raise InputValidationError(
                f"'{raw}' is not a whole number.",
                hint="Use a whole number (no decimals), e.g. 42.",
            ) from None

    @staticmethod
    def _coerce_float(raw: Any) -> float:
        try:
            return float(str(raw).strip())
        except ValueError:
            raise InputValidationError(
                f"'{raw}' is not a number.",
                hint="Use a number, e.g. 0.05.",
            ) from None


def parse_params_raw(params: dict[str, Any] | Sequence[str] | None) -> dict[str, str]:
    """Normalise ``params`` to a {name: raw_value} dict (strings from CLI)."""
    if params is None:
        return {}
    if isinstance(params, dict):
        return {str(k): str(v) for k, v in params.items()}
    pairs: dict[str, str] = {}
    for token in params:
        if not isinstance(token, str) or "=" not in token:
            raise InputValidationError(
                f"Bad parameter '{token}'.",
                hint="Parameters look like 'name=value', e.g. 'alpha=0.01'.",
            )
        name, value = token.split("=", 1)
        name = name.strip()
        if not name:
            raise InputValidationError(
                f"Bad parameter '{token}' (empty name).",
                hint="Use 'name=value', e.g. 'alpha=0.01'.",
            )
        pairs[name] = value.strip()
    return pairs


def build_parameters(manifest: dict[str, Any]) -> list[ParameterSpec]:
    specs: list[ParameterSpec] = []
    for raw in manifest.get("parameters", []):
        try:
            specs.append(ParameterSpec.from_manifest(raw))
        except ConfigError:
            raise
    return specs


def resolve_parameters(
    specs: list[ParameterSpec],
    raw_overrides: dict[str, str],
) -> tuple[dict[str, Any], list[str]]:
    """Coerce overrides onto defaults.

    Returns:
        (resolved dict of {name: typed value} for every declared parameter,
         list of human-readable "used default" notes for beginner narration)
    """
    resolved: dict[str, Any] = {}
    notes: list[str] = []
    unknown = [k for k in raw_overrides if k not in {s.name for s in specs}]
    if unknown:
        valid = ", ".join(sorted(s.name for s in specs)) or "(none)"
        raise InputValidationError(
            f"Unknown option(s): {', '.join(sorted(unknown))}.",
            hint=f"This analysis accepts: {valid}.",
        )
    for spec in specs:
        if spec.name in raw_overrides:
            resolved[spec.name] = spec.coerce(raw_overrides[spec.name])
        else:
            resolved[spec.name] = spec.default
            if spec.default is not None and not spec.required:
                notes.append(f"using default {spec.name}={spec.default!r}")
    return resolved, notes


def build_inputs(manifest: dict[str, Any]) -> list[InputSpec]:
    return [InputSpec.from_manifest(raw, i) for i, raw in enumerate(manifest.get("inputs", []))]
