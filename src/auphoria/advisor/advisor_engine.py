"""The AUPHORIA advisor: recommend analyses from data shape + question.

The decision logic is NOT in this file — it lives in
``src/auphoria/advisor/rules.yaml``, which lists every rule as readable YAML
(question, required column kinds/counts, and the plain-English reason). This
module just evaluates those rules against a :class:`DataProfile` (plus
optional column roles) and sorts the outcome.

Public entry point: :func:`advise` — returns an :class:`AdvisoryResult` with
``recommended`` (ranked, each with a one-line reason) and ``ruled_out`` (each
with the reason the rule refused: typically the ``not_fit`` or
``small_sample`` text from the YAML).

Only analyses that are actually BUILT (present in the registry) are
recommended; planned-but-unbuilt analyses never appear as recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.resources import files as _pkg_files
from pathlib import Path
from typing import Any

import yaml

from auphoria.advisor.advisor import DataProfile
from auphoria.core import registry

# Roles that mark a column as a per-unit id (paired/repeated design).
_ID_ROLES = {"id"}

_RULES_PACKAGE = "auphoria.advisor"
_RULES_RESOURCE = "rules.yaml"


@dataclass
class Rule:
    """One YAML rule: when this question + data shape match, recommend."""

    analysis: str
    question: str | None      # None = catch-all (any question)
    priority: int = 100
    reason: str = ""
    needs: dict[str, Any] = field(default_factory=dict)
    not_fit: str = ""
    small_sample: str = ""
    name: str = ""


@dataclass
class Recommendation:
    analysis: str
    name: str
    reason: str


@dataclass
class AdvisoryResult:
    recommended: list[Recommendation] = field(default_factory=list)
    ruled_out: list[Recommendation] = field(default_factory=list)

    def recommendation_ids(self) -> list[str]:
        return [r.analysis for r in self.recommended]

    def ruled_out_ids(self) -> list[str]:
        return [r.analysis for r in self.ruled_out]


def _default_rules_path() -> Path:
    try:
        return Path(_pkg_files(_RULES_PACKAGE).joinpath(_RULES_RESOURCE))
    except (ModuleNotFoundError, FileNotFoundError):  # editable/odd layouts
        return Path(__file__).resolve().parent / _RULES_RESOURCE


def load_rules(rules_path: str | Path | None = None) -> list[Rule]:
    """Load and validate the rules YAML file into Rule objects."""
    path = Path(rules_path) if rules_path else _default_rules_path()
    with path.open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)

    rules: list[Rule] = []
    for raw in doc.get("rules", []):
        analysis = str(raw["analysis"])
        needs = dict(raw.get("needs", {}))
        rules.append(
            Rule(
                analysis=analysis,
                question=raw.get("question"),          # None = catch-all
                priority=int(raw.get("priority", 100)),
                reason=str(raw.get("reason", "")),
                needs=needs,
                not_fit=str(raw.get("not_fit", "")),
                small_sample=str(raw.get("small_sample", "")),
                name=analysis,
            )
        )
    return rules


def question_menu() -> list[tuple[str, str]]:
    """[(question_id, label)] for the 'what do you want to know?' menu."""
    path = _default_rules_path()
    with path.open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    return [(str(q["id"]), str(q["label"])) for q in doc.get("questions", [])]


# ------------------------------------------------------------------ helpers
def _count_kind(profile: DataProfile, kind: str) -> int:
    return len(profile.of_kind(kind))


def _group_categories(profile: DataProfile, roles: dict[str, str] | None) -> int:
    """Number of categories in the group column.

    Uses the role-annotated group column when available; otherwise the
    categorical column with the most (2..50) categories acts as the group.
    All-unique columns (ids) and id-role columns are never treated as groups
    — a group is something with repeated values.
    """
    roles = roles or {}
    for col in profile.columns:
        if roles.get(col.name) == "group":
            return int(col.n_unique)
    cats = [
        c for c in profile.of_kind("categorical")
        if 2 <= c.n_unique <= 50 and c.n_unique < profile.n_rows
        and roles.get(c.name) not in _ID_ROLES
    ]
    cats.sort(key=lambda c: c.n_unique, reverse=True)
    return int(cats[0].n_unique) if cats else 0


def _has_id_column(profile: DataProfile, roles: dict[str, str] | None) -> bool:
    roles = roles or {}
    for col in profile.columns:
        if roles.get(col.name) in _ID_ROLES:
            return True
        # All-unique categorical column (e.g. subject codes) is an id.
        if (col.kind in ("categorical", "text")
                and col.n_unique == profile.n_rows
                and profile.n_rows > 1):
            return True
    return False


def _rule_matches(rule: Rule, profile: DataProfile, roles: dict[str, str] | None) -> tuple[bool, str]:
    """Return (matches, failure_kind) where failure_kind is 'small',
    'not_fit', or '' when it matches."""
    needs = rule.needs
    if "min_rows" in needs and profile.n_rows < int(needs["min_rows"]):
        return False, "small"
    if "min_numeric" in needs and _count_kind(profile, "numeric") < int(needs["min_numeric"]):
        return False, "not_fit"
    if "min_categorical" in needs and _count_kind(profile, "categorical") < int(needs["min_categorical"]):
        return False, "not_fit"
    if "groups" in needs:
        want = str(needs["groups"])
        got = _group_categories(profile, roles)
        ok = (got == 2) if want == "2" else (got >= 3)
        if not ok:
            return False, "not_fit"
    if needs.get("id_column") and not _has_id_column(profile, roles):
        return False, "not_fit"
    return True, ""


def advise(
    profile: DataProfile,
    roles: dict[str, str] | None = None,
    question: str | None = None,
    rules: list[Rule] | None = None,
) -> AdvisoryResult:
    """Rank analyses for this data (and question, if given).

    ``roles`` maps column name -> role (outcome / group / id / ...) as
    confirmed in the wizard; it sharpens group/id detection. Only analyses
    present in the registry (built) are recommended or ruled out.
    """
    rules = rules or load_rules()
    built: set[str] = set(registry.discover()) if registry is not None else set()

    applicable = [
        r for r in rules
        if (r.question is None or r.question == question) and r.analysis in built
    ]
    applicable.sort(key=lambda r: r.priority)

    recommended: list[Recommendation] = []
    ruled_out: list[Recommendation] = []
    seen: set[str] = set()

    for rule in applicable:
        # Name comes from the registry manifest (friendly, stable).
        name = rule.name
        try:
            name = registry.get(rule.analysis).name
        except Exception:  # noqa: BLE001 - registry unavailable in tests
            pass

        matches, failure = _rule_matches(rule, profile, roles)
        if matches:
            if rule.analysis not in seen:
                recommended.append(Recommendation(rule.analysis, name, rule.reason))
                seen.add(rule.analysis)
            continue
        # Ruled out — attribute to the MOST specific reason available.
        if failure == "small" and rule.small_sample:
            reason = rule.small_sample
        elif rule.not_fit:
            reason = rule.not_fit
        else:
            reason = "The data do not fit this analysis."
        if rule.analysis not in seen:
            ruled_out.append(Recommendation(rule.analysis, name, reason))
            seen.add(rule.analysis)

    return AdvisoryResult(recommended=recommended, ruled_out=ruled_out)
