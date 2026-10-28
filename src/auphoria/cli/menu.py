"""The interactive, beginner-first flow behind `auphoria` (no subcommand).

Asks for a data file path (drag-and-drop / quoted / ~ / Windows tolerant) ->
previews -> confirms column kinds AND roles -> offers a menu of analyses that
fit -> asks for inputs/parameters in plain language -> summarises and asks for
confirmation -> runs via the engine -> prints the results folder and offers to
open it.

This is a thin front end too: every menu path ultimately calls
``auphoria.run(...)``.
"""

from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Any

from auphoria.adapters.adapters import clean_path_input
from auphoria.core.errors import InputValidationError
from auphoria.core.version import __version__

_KIND_LABELS = {"numeric": "number", "categorical": "category",
                "datetime": "date", "text": "text"}

# Plain-language role choices the user can type.
_ROLE_CHOICES = {
    "outcome": "outcome", "out": "outcome",
    "group": "group", "factor": "group", "category": "group",
    "covariate": "covariate", "cov": "covariate",
    "id": "id", "subject": "id", "key": "id",
    "time": "time", "date-axis": "time",
    "weight": "weight",
    "none": "none", "skip": "none", "ignore": "none", "": None,
}


class _Cancelled(Exception):
    """Internal signal for Ctrl+C / EOF in the wizard (maps to exit 130)."""


def _input(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise _Cancelled() from None


def _banner() -> None:
    print("=" * 62)
    print(f"  AUPHORIA v{__version__} — data analysis without programming")
    print("  For BS / MPhil / PhD students and supervisors.")
    print("  Offline, private, reproducible. No accounts, no AI, no uploads.")
    print("=" * 62)
    print()


def _ask_path() -> Path:
    """Ask for a data file; tolerant of drag-and-drop, quotes, ~, Windows paths."""
    while True:
        raw = _input("Path to your data file (CSV/TSV/TXT/XLSX): ")
        if not raw:
            print("  You must give a file path. Type it and press Enter.")
            continue
        path = clean_path_input(raw)
        if not path.exists():
            print(f"  I couldn't find '{path}'. Check the spelling and folder.")
            continue
        if not path.is_file():
            print(f"  '{path}' is a folder, not a file. Give the file path.")
            continue
        return path


def _preview_and_confirm(
    df: Any, path: Path, expert: bool
) -> tuple[dict[str, str], dict[str, str]]:
    """Show the preview and confirm/override column kinds and roles.

    Returns ``(kind_overrides, role_overrides)``.
    """
    from auphoria.adapters.adapters import preview_text
    from auphoria.advisor.advisor import profile_data_frame
    from auphoria.core.data_card import ROLE_UNKNOWN, profile_data_card

    print()
    print("Here is a preview of your data:")
    print("-" * 62)
    print(preview_text(df))
    print("-" * 62)

    kind_overrides: dict[str, str] = {}
    role_overrides: dict[str, str] = {}
    if expert:
        return kind_overrides, role_overrides

    profile = profile_data_frame(df)
    card = profile_data_card(df)  # has the role *suggestions*

    def _role_suggestion(name: str) -> str:
        cc = card.by_name(name)
        if cc and cc.suggested_role != ROLE_UNKNOWN:
            return cc.suggested_role
        return "none"

    print()
    print("I checked each column. Confirm what it is (types), then the role it "
          "plays in your study.")
    kind_inputs = {"number": "numeric", "numeric": "numeric", "n": "numeric",
                   "category": "categorical", "categorical": "categorical",
                   "c": "categorical", "date": "datetime", "datetime": "datetime",
                   "d": "datetime", "text": "text", "t": "text"}

    for col in profile.columns:
        detected = _KIND_LABELS.get(col.kind, col.kind)
        prompt = (
            f"  {col.name}: is it a {detected}? (Enter = yes, or "
            f"type number/category/date/text): "
        )
        answer = _input(prompt).lower()
        if not answer:
            pass
        elif answer not in kind_inputs:
            print("    (Ignored — use: number/category/date/text)")
        else:
            kind_overrides[col.name] = kind_inputs[answer]

    print()
    print("Now the role each column plays in your study. Suggestions are in "
          "[brackets]; press Enter to accept.")
    print("  Choices: outcome, group, covariate, id, time, weight, none")
    for col in profile.columns:
        suggested = _role_suggestion(col.name)
        prompt = f"  {col.name}: role? [{suggested}] (Enter = yes, or type one): "
        answer = _input(prompt).lower()
        if not answer:
            confirmed = suggested
        elif answer not in _ROLE_CHOICES:
            print(f"    (Ignored — use: {', '.join(c for c in _ROLE_CHOICES if c)}).")
            continue
        else:
            confirmed = _ROLE_CHOICES[answer]
        if confirmed in (None, "none"):
            continue
        role_overrides[col.name] = confirmed

    if kind_overrides or role_overrides:
        print()
        if kind_overrides:
            print(f"  Applied kind corrections: {kind_overrides}")
        if role_overrides:
            print(f"  Applied role choices: {role_overrides}")
    return kind_overrides, role_overrides


def _compute_fits(profile: Any) -> list[tuple[str, bool, list[str]]]:
    """Return [(id, fits, reasons)] where fits means 'can at least attempt'."""
    from auphoria.core import registry
    from auphoria.core.params import KIND_CATEGORICAL, KIND_DATETIME, KIND_NUMERIC

    # Advisor column-kind labels (numeric/categorical/datetime) vs the
    # manifest's *-column constants: map the manifest kind to the advisor label.
    _to_label = {
        KIND_NUMERIC: "numeric",
        KIND_CATEGORICAL: "categorical",
        KIND_DATETIME: "datetime",
    }
    results: list[tuple[str, bool, list[str]]] = []
    infos = registry.discover()
    for a_id in sorted(infos):
        manifest = infos[a_id].manifest
        reasons: list[str] = []
        fits = True
        for raw in manifest.get("inputs", []):
            needs = set(raw.get("accepts") or [raw.get("kind", KIND_NUMERIC)])
            wanted_labels = {_to_label.get(k, "numeric") for k in needs}
            available = sum(
                1 for col in profile.columns if col.kind in wanted_labels
            )
            need_name = "numeric" if KIND_NUMERIC in needs else (
                "categorical" if KIND_CATEGORICAL in needs else "other"
            )
            if raw.get("required") and available == 0:
                fits = False
                reasons.append(
                    f"needs a {need_name} column ('{raw.get('name')}') — none found"
                )
        results.append((a_id, fits, reasons))
    return results


def _choose_analysis(fits: list[tuple[str, bool, list[str]]]) -> str | None:
    print()
    print("Which analysis would you like to run?")
    print("  (analyses that fit your data are marked ✓)")
    numbered = []
    for i, (a_id, ok, reasons) in enumerate(fits, start=1):
        mark = "✓" if ok else "✗"
        note = "" if ok else f"  — won't fit: {'; '.join(reasons)}"
        numbered.append((a_id, ok))
        print(f"  {i:>2}. {mark} {a_id}{note}")
    print("  0. Quit")
    while True:
        choice = _input("\nType a number and press Enter: ")
        if choice == "0" or choice == "":
            return None
        if not choice.isdigit() or not (1 <= int(choice) <= len(numbered)):
            print(f"  Please choose a number from 1-{len(numbered)}, or 0 to quit.")
            continue
        a_id, ok = numbered[int(choice) - 1]
        if ok:
            return a_id
        print("  That analysis does not fit this data the way it is set up; pick ✓ one.")
        continue


def _choose_inputs(
    analysis_id: str, profile: Any, expert: bool, role_overrides: dict[str, str]
) -> dict[str, str]:
    """Ask the user which columns fill each required input.

    Columns whose confirmed role matches the input's expected role are listed
    first (nicer defaults), the rest follow.
    """
    from auphoria.core import registry
    from auphoria.core.params import KIND_CATEGORICAL, KIND_NUMERIC, build_inputs

    info = registry.get(analysis_id)
    inputs: dict[str, str] = {}
    spec_list = build_inputs(info.manifest)
    for spec in spec_list:
        if not spec.required:
            continue
        needs = set(spec.accepts)
        numeric_needed = KIND_NUMERIC in needs
        wanted_kind: str = "numeric" if numeric_needed else (
            "categorical" if KIND_CATEGORICAL in needs else ""
        )
        candidates = [
            col for col in profile.columns if col.kind == wanted_kind
        ]
        if not candidates:
            if expert:
                # no friendly note in expert mode
                pass
            need = "numeric" if numeric_needed else "categorical"
            print(f"  No suitable {need} column for '{spec.name}'. Skipping.")
            continue
        # Sort: columns whose confirmed role matches this input first.
        expected_role = "outcome" if spec.name in ("outcome", "y") else (
            "group" if spec.name in ("group", "x") else ""
        )
        if expected_role:
            # Match = True sorts first: key (role != expected, name).
            candidates = sorted(
                candidates,
                key=lambda col: (role_overrides.get(col.name, "") != expected_role, col.name),
            )
        print(f"\n  For '{spec.name}' ({spec.description}):")
        for i, col in enumerate(candidates, start=1):
            miss = f"  [{col.n_missing} missing]" if col.has_missing else ""
            role = role_overrides.get(col.name, "")
            role_s = f" (role: {role})" if role else ""
            print(f"    {i}. {col.name}{role_s}{miss}")
        while True:
            choice = _input(f"    Choose (1-{len(candidates)}): ")
            if not choice.isdigit() or not (1 <= int(choice) <= len(candidates)):
                print("    Pick a valid number.")
                continue
            inputs[spec.name] = candidates[int(choice) - 1].name
            break
    return inputs


def _choose_params(analysis_id: str, expert: bool) -> list[str]:
    """Ask for parameters, returning ['name=value', ...] for non-defaults."""
    from auphoria.core import registry
    from auphoria.core.params import build_parameters

    info = registry.get(analysis_id)
    specs = build_parameters(info.manifest)
    chosen: list[str] = []
    for spec in specs:
        if spec.required or spec.description:
            default_txt = f" (default: {spec.default})" if spec.default is not None else ""
            desc = f" [{spec.description}]" if spec.description else ""
            while True:
                answer = _input(f"  {spec.name}{default_txt}{desc}: ")
                if not answer:
                    break  # use default
                try:
                    spec.coerce(answer)  # validate
                    chosen.append(f"{spec.name}={answer}")
                    break
                except InputValidationError as exc:
                    print(f"    {exc.message}")
    return chosen


def _summarise_confirm(
    analysis_id: str, inputs: dict[str, str], params: list[str]
) -> bool:
    """Plain-language recap; ask for confirmation before running."""
    from auphoria.core import registry

    info = registry.get(analysis_id)
    print()
    print("Ready to run. Here is what I will do:")
    print(f"  Analysis: {info.name}")
    for role_name, col in inputs.items():
        print(f"  - {role_name}: {col}")
    for p in params:
        name, _, value = p.partition("=")
        print(f"  - option {name} = {value}")
    print()
    while True:
        answer = _input("Run it now? (Enter = yes, n = no): ").lower()
        if answer in ("", "y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("  Please answer yes (Enter) or no (n).")


def _print_report(result: dict[str, Any]) -> None:
    print()
    print("=" * 62)
    print(f"  {result['analysis_name']} — done")
    print("=" * 62)
    if result["summaries"]:
        for label, value in result["summaries"].items():
            print(f"  {label}: {value}")
    if result["warnings"]:
        print("\n  Heads-up:")
        for w in result["warnings"]:
            print(f"    * {w}")
    print(f"\n  Results are saved in:\n    {result['results_dir']}")
    print("  Open the folder now? (Enter = yes, n = no) ", end="")
    answer = _input("").lower()
    if answer in ("", "y", "yes"):
        try:
            webbrowser.open(str(result["results_dir"]))
        except Exception:  # noqa: BLE001 - opening a browser is best-effort
            pass


def _ask_question_and_advice(
    profile: Any,
    role_overrides: dict[str, str],
    expert: bool,
) -> str | None:
    """Ask what the student wants to know, then show the advisor's advice.

    Returns the chosen question id, or None if the student skips ('s' / blank
    in expert mode). The student still gets the full analysis menu afterwards;
    the advice only helps them pick.
    """
    from auphoria.advisor.advisor_engine import advise, question_menu

    questions = question_menu()
    if expert:
        return None

    print()
    print("What do you want to know? (Enter a number — advice only, you can "
          "still pick any analysis next)")
    for i, (_qid, label) in enumerate(questions, start=1):
        print(f"  {i:>2}. {label}")
    print("  (blank = skip advice, show me all analyses)")
    choice = _input("Your question: ").strip()
    if not choice:
        return None
    if not choice.isdigit() or not (1 <= int(choice) <= len(questions)):
        print("  (Skipping advice — that wasn't a number in range.)")
        return None
    qid = questions[int(choice) - 1][0]

    result = advise(profile, roles=role_overrides, question=qid)
    print()
    print("Based on your data and question, I would try:")
    if result.recommended:
        for rec in result.recommended:
            print(f"  ✓ {rec.analysis:<20} {rec.name}")
            print(f"      {rec.reason}")
    else:
        print("  (No built analysis fits this question and data yet.)")
    if result.ruled_out:
        print("Ruled out for this data:")
        for ro in result.ruled_out:
            print(f"  ✗ {ro.analysis:<20} {ro.reason}")
    print()
    return qid


def run_interactive(expert: bool = False) -> None:
    try:
        _run_interactive(expert=expert)
    except _Cancelled:
        print("\nCancelled.")
        raise SystemExit(130) from None


def _run_interactive(expert: bool = False) -> None:
    import auphoria
    from auphoria.adapters.adapters import read_data_frame
    from auphoria.advisor.advisor import profile_data_frame

    _banner()

    path = _ask_path()
    df, _warnings = read_data_frame(path)
    kind_overrides, role_overrides = _preview_and_confirm(df, path, expert)
    profile = profile_data_frame(df, kind_overrides)

    _ask_question_and_advice(profile, role_overrides, expert)

    fits = _compute_fits(profile)
    analysis_id = _choose_analysis(fits)
    if analysis_id is None:
        print("No analysis chosen. Goodbye.")
        return

    inputs = _choose_inputs(analysis_id, profile, expert, role_overrides)
    params = _choose_params(analysis_id, expert)

    if not _summarise_confirm(analysis_id, inputs, params):
        print("Cancelled — nothing was run.")
        return

    print()
    print("Running ...")
    result = auphoria.run(
        data_path=str(path),
        analysis=analysis_id,
        outcome=inputs.get("outcome"),
        group=inputs.get("group"),
        extra={k: v for k, v in inputs.items() if k not in ("outcome", "group")},
        params=params,
        seed=1,
        column_kinds=kind_overrides,
        expert=expert,
    )
    _print_report(result)
