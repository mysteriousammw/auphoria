"""Tests for hashing, parameter coercion, and the advisor profiling."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from auphoria.advisor.advisor import profile_data_frame
from auphoria.core.errors import InputValidationError
from auphoria.core.hashing import sha256_of_file
from auphoria.core.params import (
    InputSpec,
    ParameterSpec,
    parse_params_raw,
    resolve_parameters,
)
from auphoria.core.registry import discover, list_analyses


# ------------------------------------------------------------------ hashing
def test_sha256_hex_and_stable(tmp_path: Path):
    p = tmp_path / "a.txt"
    p.write_text("auphoria", encoding="utf-8")
    h1 = sha256_of_file(p)
    h2 = sha256_of_file(p)
    assert len(h1) == 64
    assert h1 == h2
    assert set(h1) <= set("0123456789abcdef")


def test_sha256_changes_with_content(tmp_path: Path):
    p = tmp_path / "b.txt"
    p.write_text("one", encoding="utf-8")
    h1 = sha256_of_file(p)
    p.write_text("two", encoding="utf-8")
    assert sha256_of_file(p) != h1


# ------------------------------------------------------------------ params
def test_parameter_coercion_number_and_bounds():
    spec = ParameterSpec(name="alpha", ptype="number", default=0.05,
                         min_value=0.001, max_value=0.5)
    assert spec.coerce("0.01") == pytest.approx(0.01)
    assert spec.coerce("0.05") == pytest.approx(0.05)
    with pytest.raises(InputValidationError):
        spec.coerce("0.9")  # above max


def test_parameter_boolean_coercion():
    spec = ParameterSpec(name="flag", ptype="boolean", default=False)
    assert spec.coerce("true") is True
    assert spec.coerce("no") is False
    assert spec.coerce("1") is True
    with pytest.raises(InputValidationError):
        spec.coerce("maybe")


def test_parameter_choice_rejects_bad():
    spec = ParameterSpec(name="tail", ptype="choice", default="two-sided",
                         choices=("two-sided", "greater", "less"))
    assert spec.coerce("greater") == "greater"
    with pytest.raises(InputValidationError):
        spec.coerce("both")


def test_parse_params_raw_and_unknown_rejected():
    assert parse_params_raw(["a=1", "b=2"]) == {"a": "1", "b": "2"}
    assert parse_params_raw({"c": 3}) == {"c": "3"}
    assert parse_params_raw(None) == {}
    with pytest.raises(InputValidationError):
        parse_params_raw(["no_equals"])


def test_resolve_parameters_defaults_and_overrides():
    from auphoria.core.params import ParameterSpec

    specs = [
        ParameterSpec(name="alpha", ptype="number", default=0.05,
                      min_value=0.001, max_value=0.5),
        ParameterSpec(name="tail", ptype="choice", default="two-sided",
                      choices=("two-sided", "greater", "less")),
    ]
    resolved, notes = resolve_parameters(specs, {"alpha": "0.01"})
    assert resolved["alpha"] == pytest.approx(0.01)
    assert resolved["tail"] == "two-sided"
    assert len(notes) == 1  # one default noted
    with pytest.raises(InputValidationError):
        resolve_parameters(specs, {"alpha": "0.01", "nope": "1"})


def test_param_resolution_unknown_raises():
    from auphoria.core.params import ParameterSpec

    specs = [ParameterSpec(name="alpha", ptype="number", default=0.05)]
    with pytest.raises(InputValidationError):
        resolve_parameters(specs, {"bogus": "1"})


def test_input_spec_required_defaults():
    spec = InputSpec.from_manifest({"name": "outcome", "kind": "numeric-column",
                                    "required": True})
    assert spec.required is True
    assert spec.name == "outcome"


# ------------------------------------------------------------------ advisor
def test_profile_detects_kinds(sample_csv: Path):
    df = pd.read_csv(sample_csv)
    profile = profile_data_frame(df)
    by_name = {c.name: c.kind for c in profile.columns}
    assert by_name["treatment"] == "categorical"
    assert by_name["height_cm"] == "numeric"
    assert by_name["light_hours"] == "numeric"
    assert by_name["weight_g"] == "numeric"


def test_profile_reports_missing(sample_csv: Path):
    df = pd.read_csv(sample_csv)
    profile = profile_data_frame(df)
    w = profile.by_name("weight_g")
    assert w is not None and w.n_missing == 3


def test_profile_kind_overrides(sample_csv: Path):
    df = pd.read_csv(sample_csv)
    profile = profile_data_frame(df, {"light_hours": "categorical"})
    assert profile.by_name("light_hours").kind == "categorical"


def test_profile_bad_override_raises(sample_csv: Path):
    df = pd.read_csv(sample_csv)
    with pytest.raises(InputValidationError):
        profile_data_frame(df, {"light_hours": "not-a-kind"})


# ------------------------------------------------------------------ registry
def test_registry_discovers_all(sample_csv: Path):
    infos = discover()
    assert {"summary", "ttest", "correlation"} <= set(infos)
    for a_id, info in infos.items():
        assert info.id == a_id
        assert info.maturity == "experimental"
        assert isinstance(info.levels, tuple)
    assert list_analyses() == sorted(list_analyses())


def test_catalogue_in_sync_with_registry():
    """Every *built* (discovered) analysis must appear in catalog/analyses.yaml.

    The catalogue deliberately lists more analyses than are built (it is the
    research-backed roadmap); the invariant is that nothing built is missing
    from it, so a built analysis can never be unadvertised.
    """
    from pathlib import Path

    import yaml

    catalog_path = Path(__file__).resolve().parent.parent / "catalog" / "analyses.yaml"
    data = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    cat_ids = {a["id"] for a in data["analyses"]}
    assert set(discover()) <= cat_ids


# ------------------------------------------------------------------ research catalogue invariants
_REQUIRED_CATALOG_FIELDS = {
    "id", "name", "plain_english_question", "levels", "disciplines", "design",
    "data_requirements", "assumptions_to_check", "alternatives_when_assumptions_fail",
    "python_library_and_function", "outputs", "common_mistakes", "priority", "pack",
    "sources",
}


def _catalogue() -> dict:
    from pathlib import Path

    import yaml

    path = Path(__file__).resolve().parent.parent / "catalog" / "analyses.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_catalogue_is_valid_and_well_formed():
    data = _catalogue()
    assert data["catalogue_version"] == 2
    assert isinstance(data["analyses"], list) and data["analyses"]
    for entry in data["analyses"]:
        missing = _REQUIRED_CATALOG_FIELDS - set(entry)
        assert not missing, f"{entry.get('id')} missing fields: {missing}"
        assert entry["priority"] in {"P1", "P2", "P3"}
        assert isinstance(entry["pack"], list) and entry["pack"]
        assert isinstance(entry["sources"], list) and entry["sources"], \
            f"{entry.get('id')} has no source"
        assert entry["levels"], f"{entry.get('id')} has no levels"
        assert entry["disciplines"], f"{entry.get('id')} has no disciplines"


def test_p1_list_is_bounded_and_covers_all_disciplines():
    """P1 must have at most 30 analyses and cover every discipline listed."""
    data = _catalogue()
    p1 = [a for a in data["analyses"] if a["priority"] == "P1"]
    assert 0 < len(p1) <= 30, f"P1 count {len(p1)} must be <= 30"
    all_p1_disciplines = {d for a in p1 for d in a["disciplines"]}
    # Every advertised discipline in the whole catalogue must be reachable via P1.
    for entry in data["analyses"]:
        for disc in entry["disciplines"]:
            assert disc in all_p1_disciplines, \
                f"discipline '{disc}' (from {entry['id']}) not covered by any P1 analysis"


def test_every_analysis_has_manifest_and_module():
    for a_id in list_analyses():
        import importlib

        module = importlib.import_module(f"auphoria.analyses.{a_id}.analysis")
        instance = getattr(module, "ANALYSIS", None)
        assert instance is not None, f"{a_id} has no ANALYSIS object"
        assert instance.id == a_id
