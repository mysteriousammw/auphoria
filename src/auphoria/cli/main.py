"""AUPHORIA command-line interface (Typer).

Command tree:
    auphoria                 interactive guided flow (beginner default)
    auphoria --version       show version and exit
    auphoria doctor          environment self-check (Python, libraries, writable folder)
    auphoria run --data PATH --analysis ID [--outcome COL] [--group COL] ...
    auphoria list
    auphoria info ID
    auphoria sample [NAME]
    auphoria versions

The CLI is a thin front end: it collects arguments and calls the engine
``auphoria.run(...)``. No analysis logic lives here.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import typer

from auphoria.core.errors import AuphoriaError
from auphoria.core.logging_core import log_traceback
from auphoria.core.version import __version__

_VERSION_EPILOG = f"auphoria {__version__}"

app = typer.Typer(
    name="auphoria",
    help="AUPHORIA - beginner-friendly data analysis for students who cannot code.\n"
    "Runs offline on your computer or in Google Colab.",
    add_completion=False,
    no_args_is_help=False,  # no command -> interactive flow (handled in callback)
    pretty_exceptions_show_locals=False,
)


def _require_python() -> None:
    """Friendly note if python is outside the supported range (warn, keep going
    so dev/testing on 3.13 still works; pyproject enforces the real bound)."""
    if sys.version_info < (3, 10) or sys.version_info >= (3, 13):
        typer.echo(
            "Note: AUPHORIA officially supports Python 3.10-3.12; you are on "
            f"{sys.version_info.major}.{sys.version_info.minor}. "
            "Install under 3.10-3.12 for the tested configuration.",
            err=True,
        )


@app.callback(invoke_without_command=True)
def _main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show version and exit."),
) -> None:
    if version:
        typer.echo(_VERSION_EPILOG)
        raise typer.Exit()
    # No subcommand chosen -> interactive beginner flow.
    if ctx.invoked_subcommand is None:
        from auphoria.cli.menu import run_interactive

        try:
            run_interactive(expert=False)
        except AuphoriaError as exc:
            typer.echo(f"\n{exc.to_user()}\n", err=True)
            raise typer.Exit(code=1) from None
        except (KeyboardInterrupt, EOFError):
            typer.echo("\nCancelled.", err=True)
            raise typer.Exit(code=130) from None
        raise typer.Exit()


def _handle_error(exc: AuphoriaError) -> None:
    typer.echo(f"{exc.to_user()}\n", err=True)
    raise typer.Exit(code=1) from None


@app.command("version")
def version_command() -> None:
    """Show AUPHORIA version (also available as --version)."""
    typer.echo(_VERSION_EPILOG)


@app.command("run")
def run_command(
    data: str = typer.Option(..., "--data", help="Path to your data file (CSV/TSV/TXT/XLSX)."),
    analysis: str = typer.Option(..., "--analysis", "-a", help="Analysis id, e.g. 'ttest'."),
    outcome: str | None = typer.Option(None, "--outcome", help="Column to treat as the outcome."),
    group: str | None = typer.Option(None, "--group", help="Column to treat as the group/category."),
    extra: list[str] = typer.Option(
        [], "--extra", metavar="ROLE=COL",
        help="Map another declared input, e.g. --extra x=height_cm (repeatable).",
    ),
    param: list[str] = typer.Option(
        [], "--param", metavar="NAME=VALUE",
        help="Set a parameter, e.g. --param alpha=0.01 (repeatable).",
    ),
    seed: int = typer.Option(1, "--seed", help="Random seed (default 1)."),
    out: str | None = typer.Option(None, "--out", help="Explicit output folder (default is auto-created)."),
    expert: bool = typer.Option(False, "--expert", help="Suppress beginner-facing explanations."),
    docx: bool = typer.Option(
        False, "--docx",
        help="Also write a Word (.docx) file with the methods paragraph and result tables.",
    ),
    kind: list[str] = typer.Option(
        [], "--kind", metavar="COL=KIND",
        help="Force a column's kind: numeric/categorical/datetime/text (repeatable).",
    ),
) -> None:
    """Run one analysis non-interactively; results go to ~/AUPHORIA_results/."""
    import auphoria

    extra_map: dict[str, str] = {}
    for tok in extra:
        if "=" not in tok:
            _handle_error(AuphoriaError(f"--extra must be ROLE=COL, got '{tok}'."))
        role, col = tok.split("=", 1)
        extra_map[role.strip()] = col.strip()

    kinds: dict[str, str] = {}
    for tok in kind:
        if "=" not in tok:
            _handle_error(AuphoriaError(f"--kind must be COL=KIND, got '{tok}'."))
        col, k = tok.split("=", 1)
        kinds[col.strip()] = k.strip()

    try:
        result = auphoria.run(
            data_path=data,
            analysis=analysis,
            outcome=outcome,
            group=group,
            extra=extra_map,
            params=param,
            seed=seed,
            out=out,
            expert=expert,
            column_kinds=kinds,
            make_docx=docx,
        )
    except AuphoriaError as exc:
        _handle_error(exc)

    _print_result(result, expert=expert)


def _print_result(result: dict, expert: bool) -> None:
    typer.echo()
    typer.echo("=" * 62)
    typer.echo(f"Analysis: {result['analysis_name']}  (data: {result['input_file']})")
    typer.echo("=" * 62)
    if result["summaries"]:
        for label, value in result["summaries"].items():
            typer.echo(f"  {label}: {value}")
    if result["warnings"]:
        typer.echo()
        typer.echo("Heads-up:")
        for w in result["warnings"]:
            typer.echo(f"  * {w}")
    typer.echo()
    typer.echo(f"Results saved in:\n  {result['results_dir']}")
    if not expert:
        typer.echo("\nReproduce these exact numbers with:")
        typer.echo(f"  {result['replay_command']}")
    if not expert and sys.stdin.isatty():
        try:
            answer = typer.prompt("Open the results folder now?", default="n").strip().lower()
            if answer in ("y", "yes"):
                import webbrowser

                webbrowser.open(str(Path(result["results_dir"]).resolve()))
        except typer.Abort:
            pass


@app.command("list")
def list_command(
    level: str | None = typer.Option(
        None, "--level", "-l",
        help="Filter by study level (beginner/intermediate/advanced; repeatable via comma).",
    ),
    discipline: str | None = typer.Option(
        None, "--discipline", "-d",
        help="Filter by discipline (e.g. health, agriculture; comma-separated).",
    ),
    pack: str | None = typer.Option(
        None, "--pack", "-p",
        help="Filter to one discipline pack (e.g. health; see 'auphoria packs').",
    ),
) -> None:
    """List available analyses, optionally filtered by level, discipline or pack."""
    from auphoria.core import registry

    wanted_levels = {s.strip().lower() for s in (level or "").split(",") if s.strip()}
    wanted_disciplines = {s.strip().lower() for s in (discipline or "").split(",") if s.strip()}
    wanted_pack = (pack or "").strip().lower()

    try:
        infos = registry.discover()
    except AuphoriaError as exc:
        _handle_error(exc)

    shown = 0
    lines = []
    for a_id in sorted(infos):
        info = infos[a_id]
        m = info.manifest
        levels = {str(x).lower() for x in m.get("levels", [])}
        disciplines = {str(x).lower() for x in m.get("disciplines", [])}
        if wanted_levels and not (levels & wanted_levels):
            continue
        if wanted_disciplines and not (disciplines & wanted_disciplines):
            continue
        if wanted_pack:
            manifest_packs = {str(x) for x in (m.get("pack") or [])}
            if wanted_pack not in {p.lower() for p in manifest_packs}:
                continue
        lines.append((a_id, info.name, info.maturity))
        shown += 1
    if not lines:
        typer.echo("No analyses match that filter. Try 'auphoria list' to see all.")
        return
    typer.echo(f"{'ID':<14} {'Name':<32} Maturity")
    typer.echo("-" * 62)
    for a_id, name, maturity in lines:
        typer.echo(f"{a_id:<14} {name:<32} {maturity}")
    typer.echo()
    typer.echo(f"{shown} analyses shown. "
               "Run 'auphoria run --data YOURFILE.csv --analysis <ID> --outcome <COL>'."
               "\nFilters: --level beginner/intermediate/advanced, --discipline <name>, "
               "--pack <name> (see 'auphoria packs').")


@app.command("packs")
def packs_command() -> None:
    """List the optional discipline packs and their install commands."""
    from auphoria.packs import (
        install_command,
        install_command_git,
        load_packs,
        missing_pack_deps,
    )

    packs = load_packs()
    typer.echo("AUPHORIA discipline packs (optional installs):")
    typer.echo("-" * 62)
    for pid in sorted(packs):
        p = packs[pid]
        missing = missing_pack_deps(p.get("deps", []))
        status = "[OK]" if not missing else f"[needs {', '.join(missing)[:40]}]"
        typer.echo(f"{pid:<12} {status}  {p['name']}")
        typer.echo(f"             install:  {install_command_git(pid)}")
        typer.echo(f"             local:    {install_command(pid)}")
        desc = (str(p.get("description", "")) or "").replace("\n", " ").strip()
        if desc:
            typer.echo(f"             {desc}")
        typer.echo()
    typer.echo("Packs keep heavy dependencies optional so the core install stays "
               "light. The https://github.com/mysteriousammw/auphoria is replaced after upload "
               "(scripts/set_repo_url.py).")


@app.command("validation")
def validation_command() -> None:
    """Regenerate the validation dashboard and check maturity rules."""
    from scripts.gen_validation_dashboard import main as _gen_main

    code = _gen_main([])  # empty argv -> default --out
    if code == 0:
        typer.echo("Validation dashboard regenerated and maturity checks passed.")
    else:
        raise typer.Exit(code) from None


@app.command("new-module")
def new_module_command(
    analysis_id: str = typer.Argument(..., help="New analysis id, e.g. 'my-analysis'."),
    name: str = typer.Option(
        None, "--name", help="Human-readable analysis name (default: the id, title-cased)."
    ),
) -> None:
    """Scaffold a new analysis module (manifest, code, tests, README).

    Creates src/auphoria/analyses/<id>/ with a working skeleton and registers
    the id in catalog/analyses.yaml so the built-analysis sync test stays
    green. A DEVELOPER command for building new analyses — end users do not
    need it. Run it from the repository root.
    """
    from auphoria.cli.scaffold import new_module

    try:
        target, written = new_module(analysis_id, name)
    except AuphoriaError as exc:
        _handle_error(exc)
    typer.echo(f"Created new analysis module at {target}:")
    for p in written:
        rel = p.relative_to(target.parent)
        typer.echo(f"  - {rel}")
    typer.echo("\nNext steps:")
    typer.echo("  1. Implement run() in analysis.py and check_fit() if needed.")
    typer.echo("  2. Replace the tests with real known-answer tests.")
    typer.echo("  3. Fill in manifest assumptions/limitations and the README.")
    typer.echo('  4. Register a demo entry in `cli/main.py` (auphoria demo).')
    typer.echo(f"  5. Run:  pytest src/auphoria/analyses/{target.name}/tests  and  ruff check .")


@app.command("describe")
def describe_command(
    analysis_id: str = typer.Argument(..., help="Analysis id, e.g. 'ttest'."),
) -> None:
    """Explain one analysis in plain language: what it does, assumptions,
    limitations, and a worked example."""
    from auphoria.core import registry

    try:
        info = registry.get(analysis_id)
    except AuphoriaError as exc:
        _handle_error(exc)
    m = info.manifest
    typer.echo(f"=== {info.name}  [id: {info.id}, maturity: {info.maturity}] ===")
    if info.description:
        typer.echo(f"\nWhat it does:\n  {info.description}")
    typer.echo("\nWhat you need (inputs):")
    for raw in m.get("inputs", []):
        req = "required" if raw.get("required") else "optional"
        typer.echo(f"  - {raw.get('name')} ({raw.get('kind')}, {req}): "
                   f"{raw.get('description', '')}")
    typer.echo("\nOptions (parameters):")
    for raw in m.get("parameters", []):
        typer.echo(f"  - {raw.get('name')} (default {raw.get('default')}): "
                   f"{raw.get('description', '')}")
    typer.echo("\nAssumptions:")
    for a in m.get("assumptions", []):
        typer.echo(f"  • {a}")
    typer.echo("\nLimitations:")
    for limitation in m.get("limitations", []):
        typer.echo(f"  • {limitation}")
    if m.get("outputs"):
        typer.echo("\nWhat you get out:")
        for o in m["outputs"]:
            typer.echo(f"  - {o}")
    typer.echo("\nExample:")
    typer.echo(f"  {_example_command(analysis_id, info.name)}")


def _example_command(analysis_id: str, name: str) -> str:
    """A realistic, runnable example for 'describe', using bundled sample data."""
    from auphoria.core import registry

    info = registry.get(analysis_id)
    m = info.manifest
    # Pick sample columns that fit the inputs by kind.
    try:
        df = _load_sample_for(name)
    except Exception:  # noqa: BLE001 - fall back to a generic example
        df = None

    def pick(kindish: str) -> str:
        if df is None:
            return "<COLUMN>"
        import pandas as pd

        for col in df.columns:
            if kindish == "numeric" and pd.api.types.is_numeric_dtype(df[col]):
                return col
            if kindish == "categorical" and not pd.api.types.is_numeric_dtype(df[col]):
                return col
        return "<COLUMN>"

    parts = ["auphoria run", "--data <YOUR FILE>", f"--analysis {analysis_id}"]
    for raw in m.get("inputs", []):
        kind = raw.get("kind", "numeric-column")
        kindish = "categorical" if "categorical" in kind else (
            "numeric"
        )
        if not raw.get("required"):
            continue
        if raw.get("name") in ("outcome", "group"):
            parts.append(f"--{raw.get('name')} {pick(kindish)}")
        else:
            parts.append(f"--extra {raw.get('name')}={pick(kindish)}")
    return " ".join(parts)


def _load_sample_for(name: str):
    """Return the sample DataFrame best matching an analysis name, if any.

    Tries the sample with the same name first, then falls back to the first
    available sample so the example-command column picker always has data.
    """
    from auphoria.adapters.adapters import read_data_frame
    from auphoria.sample_data import sample_files, sample_path

    for fname in sorted(sample_files()):
        if fname == name:
            df, _ = read_data_frame(sample_path(fname))
            return df
    # No sample shares the analysis name: fall back to the first available
    # sample so the example-command column picker always has data.
    if sample_files():
        df, _ = read_data_frame(sample_path(sorted(sample_files())[0]))
        return df
    return None


@app.command("suggest")
def suggest_command(
    data: str = typer.Option(..., "--data", help="Path to your data file."),
    question: str = typer.Option(
        None, "--question", "-q",
        help="Narrow the advice to one research question "
             "(describe/compare/relate/predict/over_time/reliability/reduce).",
    ),
) -> None:
    """Recommend which analyses fit your data, based on its variable types.

    Uses the same decision rules as the interactive wizard (the advisor's
    rules.yaml — a plain-language encoding of docs/research/decision-guide.md).
    Without --question, the advice spans every research question the data can
    support.
    """
    from auphoria.adapters.adapters import clean_path_input, read_data_frame
    from auphoria.advisor.advisor import profile_data_frame
    from auphoria.advisor.advisor_engine import (
        Recommendation,
        advise,
        question_menu,
    )

    path = clean_path_input(data)
    try:
        df, _warnings = read_data_frame(path)
    except AuphoriaError as exc:
        _handle_error(exc)
    profile = profile_data_frame(df)

    qids = [qid for qid, _label in question_menu()]
    if question is not None and question not in qids:
        typer.echo(f"--question must be one of: {', '.join(qids)}", err=True)
        raise typer.Exit(code=2) from None

    if question is None:
        # No question: aggregate every question's advice so the student sees
        # everything this data shape can support (deduped, best reason first).
        recommended: list[Recommendation] = []
        seen_ids: set[str] = set()
        ruled_out: list[Recommendation] = []
        for qid in qids:
            result = advise(profile, question=qid)
            for rec in result.recommended:
                if rec.analysis not in seen_ids:
                    seen_ids.add(rec.analysis)
                    recommended.append(rec)
            for ro in result.ruled_out:
                if ro.analysis not in seen_ids:
                    seen_ids.add(ro.analysis)
                    ruled_out.append(ro)
    else:
        result = advise(profile, question=question)
        recommended = result.recommended
        ruled_out = result.ruled_out

    typer.echo(f"Suggested analyses for {path.name} ({df.shape[0]} rows x "
               f"{df.shape[1]} columns):")
    typer.echo("-" * 62)
    if recommended:
        for rec in recommended:
            typer.echo(f"  {rec.analysis:<18} {rec.name}")
            typer.echo(f"      {rec.reason}")
    else:
        typer.echo("  (No built analysis fits this data and question yet.)")
    if ruled_out:
        typer.echo("\n  Ruled out for this data:")
        for ro in ruled_out:
            typer.echo(f"  x {ro.analysis:<18} {ro.reason}")
    typer.echo("\nRun any of these with:  auphoria run --data PATH --analysis <ID> ...")


@app.command("demo")
def demo_command(
    analysis: str = typer.Option(
        "ttest", "--analysis", "-a", help="Analysis id to demo (default: ttest)."
    ),
) -> None:
    """Run a complete example on bundled synthetic data (no file needed)."""
    import auphoria
    from auphoria.sample_data import sample_path

    # Per-analysis demo: sample dataset + engine kwargs. Keeping one source of
    # truth so every built analysis has a working, documented demo.
    demos: dict[str, tuple[str, dict]] = {
        "describe": ("plant_growth", {}),
        "summary": ("plant_growth", {"outcome": "height_cm"}),
        "correlation": ("plant_growth", {"outcome": "height_cm",
                                         "extra": {"x": "weight_g"}}),
        "ttest": ("plant_growth", {"outcome": "height_cm",
                                   "group": "treatment"}),
        "ttest-paired": ("training", {"outcome": "before",
                                      "extra": {"after": "after"}}),
        "spearman-correlation": ("survey", {"outcome": "score",
                                            "extra": {"x": "hours_studied"}}),
        "chi-square": ("diets", {"group": "diet",
                                 "extra": {"var2": "adherence"}}),
        "anova-oneway": ("diets", {"outcome": "weight_loss_kg",
                                   "group": "diet"}),
        "mann-whitney": ("plant_growth", {"outcome": "height_cm",
                                          "group": "treatment"}),
        "kruskal-wallis": ("diets", {"outcome": "weight_loss_kg",
                                     "group": "diet"}),
        "regression-linear": ("features", {"outcome": "target",
                                         "extra": {"predictor": "x1"}}),
        "regression-multiple": ("features", {"outcome": "target"}),
        "logistic-regression": ("features", {"group": "label"}),
        "odds-and-risk": ("cohort", {"extra": {"exposure": "exposure",
                                     "outcome": "disease"},
                             "params": {"event_level": "yes"}}),
        "cronbach-alpha": ("psych", {}),
        "ancova": ("growth_cov", {"outcome": "final_cm", "group": "group",
                                  "extra": {"covariate": "baseline_cm"}}),
        "mixed-effects": ("schools", {"outcome": "score", "group": "method",
                                      "extra": {"cluster": "school"}}),
        "pca": ("psych", {}),
        "factor-analysis": ("psych", {}),
        "clustering-kmeans": ("psych", {}),
        "kaplan-meier": ("survival", {"outcome": "time_months",
                                      "group": "group",
                                      "extra": {"event": "event"}}),
        "cox-regression": ("survival", {"outcome": "time_months",
                                        "extra": {"event": "event",
                                                  "covariate": "age"}}),
        "diagnostic-test": ("diagnosis", {"outcome": "test_score",
                                          "extra": {"reference": "true_status"}}),
        "ml-classification-eval": ("features", {"group": "label"}),
        "ml-regression-eval": ("features", {"outcome": "target"}),
        "anova-repeated": ("repeated", {"outcome": "score", "group": "subject",
                                        "extra": {"time": "time"}}),
        "bland-altman": ("bland_altman", {"outcome": "method_a",
                                          "extra": {"method_b": "method_b"}}),
        "friedman": ("repeated", {"outcome": "score", "group": "subject",
                                  "extra": {"time": "time"}}),
        "panel-regression": ("panel", {"outcome": "profit", "group": "firm",
                                       "extra": {"time": "year"}}),
        "time-series": ("time_series", {"outcome": "value",
                                        "extra": {"period": "period"}}),
        "differential-expression": ("counts", {"group": "condition"}),
        "sem": ("sem_items", {}),
    }
    if analysis not in demos:
        _handle_error(AuphoriaError(
            f"No demo defined for analysis '{analysis}'.",
            hint=f"Available demos: {', '.join(sorted(demos))}. "
                 "Note: auphoria run works for every built analysis.",
        ))
    data, kwargs = demos[analysis]
    path = sample_path(data)
    typer.echo(f"AUPHORIA demo — running '{analysis}' on the built-in "
               f"'{data}' dataset.")
    typer.echo()
    result = auphoria.run(data_path=path, analysis=analysis, seed=1, **kwargs)
    _print_result(result, expert=False)


@app.command("info")
def info_command(analysis_id: str = typer.Argument(..., help="Analysis id, e.g. 'ttest'.")) -> None:
    """Show details of one analysis."""
    from auphoria.core import registry

    try:
        info = registry.get(analysis_id)
    except AuphoriaError as exc:
        _handle_error(exc)
    m = info.manifest
    typer.echo(f"{info.name}  [id: {info.id}, maturity: {info.maturity}]")
    if info.description:
        typer.echo(f"\n{info.description}\n")
    if m.get("inputs"):
        typer.echo("Inputs:")
        for raw in m["inputs"]:
            req = "required" if raw.get("required") else "optional"
            typer.echo(f"  - {raw.get('name')} ({raw.get('kind')}, {req}): {raw.get('description','')}")
        typer.echo()
    if m.get("parameters"):
        typer.echo("Parameters:")
        for raw in m["parameters"]:
            typer.echo(f"  - {raw.get('name')} (default {raw.get('default')}): {raw.get('description','')}")
        typer.echo()
    if m.get("outputs"):
        typer.echo("Outputs:")
        for o in m["outputs"]:
            typer.echo(f"  - {o}")
    typer.echo("\nAssumptions:")
    for a in m.get("assumptions", []):
        typer.echo(f"  - {a}")
    typer.echo("\nLimitations:")
    for limitation in m.get("limitations", []):
        typer.echo(f"  - {limitation}")
    typer.echo("\nTest data / validation:")
    for td in m.get("test_data", []):
        typer.echo(f"  - {td}")


@app.command("sample")
def sample_command(name: str = typer.Argument("plant_growth", help="Sample name.")) -> None:
    """Copy a sample dataset into the current folder to try AUPHORIA."""
    import auphoria.sample_data as sd

    try:
        src = sd.sample_path(name)
    except KeyError as exc:
        _handle_error(AuphoriaError(
            str(exc), hint=f"Available: {', '.join(sd.sample_files())}."
        ))
    dest = Path.cwd() / src.name
    shutil.copy2(src, dest)
    typer.echo(f"Copied sample dataset '{name}' to:\n  {dest}")
    typer.echo("\nTry it:")
    typer.echo(f"  auphoria run --data {dest.name} --analysis ttest --outcome height_cm --group treatment")


@app.command("versions")
def versions_command() -> None:
    """Show AUPHORIA and dependency versions."""
    from auphoria.core.environment import environment_info

    info = environment_info()
    typer.echo("AUPHORIA environment")
    typer.echo("-" * 40)
    for key, value in info.items():
        typer.echo(f"  {key:<12} {value}")


@app.command("doctor")
def doctor_command() -> None:
    """Check that this machine can run AUPHORIA (Python, libraries, writable folder)."""
    import platform

    from auphoria.core import environment
    from auphoria.core.engine import DEFAULT_RESULTS_ROOT

    problems: list[str] = []

    # 1. Python version
    py_info = sys.version_info
    ok_python = (3, 10) <= (py_info.major, py_info.minor) <= (3, 12)
    typer.echo(f"[{'OK' if ok_python else 'FAIL'}] Python {platform.python_version()} "
               f"(supported: 3.10-3.12)")
    if not ok_python:
        problems.append("python-version-out-of-range")

    # 2. Required libraries importable
    import importlib

    required = {
        "numpy": "numpy",
        "pandas": "pandas",
        "scipy": "scipy",
        "matplotlib": "matplotlib",
        "yaml": "pyyaml",
        "typer": "typer",
    }
    for module_name, label in required.items():
        try:
            module = importlib.import_module(module_name)
            version = getattr(module, "__version__", "?")
            typer.echo(f"[OK]   library: {label} {version}")
        except ImportError:
            typer.echo(f"[FAIL] library: {label} is not installed")
            problems.append(f"missing-{label}")

    # 3. Results folder writable
    try:
        DEFAULT_RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
        probe = DEFAULT_RESULTS_ROOT / ".doctor_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception as exc:  # noqa: BLE001 - report failure, don't crash
        typer.echo(f"[FAIL] results folder not writable: {DEFAULT_RESULTS_ROOT} ({exc})")
        problems.append("results-folder-not-writable")
    else:
        typer.echo(f"[OK]   results folder writable: {DEFAULT_RESULTS_ROOT}")

    # 4. Optional discipline packs (informational - core works without them).
    from auphoria.packs import load_packs, missing_pack_deps

    for pid in sorted(load_packs()):
        missing = missing_pack_deps(load_packs()[pid].get("deps", []))
        if missing:
            typer.echo(f"[NOTE] pack '{pid}' not fully installed "
                       f"(missing {', '.join(missing)}) - install with "
                       f"pip install \"auphoria[{pid}] @ git+https://github.com/mysteriousammw/auphoria\"")
        else:
            typer.echo(f"[OK]   pack '{pid}' dependencies present")

    # Show all package versions for reference.
    for name, version in environment.package_versions().items():
        typer.echo(f"  {name}: {version}")

    typer.echo()
    if problems:
        typer.echo("AUPHORIA found the following problems:")
        for p in problems:
            typer.echo(f"  - {p}")
        raise typer.Exit(code=1)
    typer.echo("All checks passed - AUPHORIA is ready to use.")


def main(argv: list[str] | None = None) -> int:
    """Entry point for the console script and `python -m auphoria`."""
    _require_python()
    # Force UTF-8 on Windows: the default cp1252 console cannot encode Unicode
    # characters used in output (e.g. "→", "✓", "✗"), which otherwise raise
    # UnicodeEncodeError -> the generic error guard. Reconfigure both streams so
    # the CLI output is readable on every platform.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # not reconfigurable (e.g. pytest capture)
            pass
    try:
        # standalone_mode=False: click returns the exit code as a value instead
        # of calling sys.exit, letting us surface it as a normal return.
        code = _invoke_app(argv)
        if isinstance(code, int):
            return code
        return 0
    except typer.Exit as exc:  # defensive: some paths still raise it
        return exc.exit_code or 0
    except AuphoriaError as exc:
        typer.echo(f"{exc.to_user()}\n", err=True)
        return 1
    except SystemExit as exc:  # other packages may still call sys.exit
        return int(exc.code) if isinstance(exc.code, int) else 1
    except Exception as exc:  # noqa: BLE001 - last-resort guard
        import logging

        logger = logging.getLogger("auphoria")
        log_traceback(logger, exc)
        typer.echo(
            "\nSomething unexpected went wrong. The technical traceback is in "
            "the log (see AUPHORIA_results/). Please report this to the "
            "maintainers (https://github.com/mysteriousammw/auphoria).\n",
            err=True,
        )
        return 1


def _invoke_app(argv: list[str] | None) -> object:
    """Run the Typer app in non-standalone mode (returns the exit code)."""
    if argv is not None:
        return app(argv, standalone_mode=False)
    return app(None, standalone_mode=False)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
