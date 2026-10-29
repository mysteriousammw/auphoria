"""The AUPHORIA engine: one function does a whole analysis run.

This is the single code path behind both the CLI and the Colab notebook. It:

1. resolves the analysis (id -> manifest -> module),
2. reads and profiles the data,
3. maps outcome/group/extra columns onto the analysis's declared inputs,
4. coerces parameters and validates everything (refusing bad fits),
5. runs the analysis, capturing warnings/notes,
6. writes all outputs (CSVs, figures, report.html, methods.txt, run.json,
   replay.sh/ps1, log.txt) into the results folder,
7. returns a dict the front end can print.

Nothing here does statistics itself; it orchestrates and is honest about
every data decision it makes.
"""

from __future__ import annotations

import json
import os
import re
import shlex
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from auphoria.adapters.adapters import read_data_frame
from auphoria.advisor.advisor import profile_data_frame, render_column_summary
from auphoria.core import registry
from auphoria.core.analysis import RunContext
from auphoria.core.environment import environment_info
from auphoria.core.errors import (
    AssumptionError,
    AuphoriaError,
    EngineError,
    InputValidationError,
)
from auphoria.core.hashing import sha256_of_file
from auphoria.core.logging_core import (
    log_decision,
    log_traceback,
    setup_logging,
)
from auphoria.core.params import (
    KIND_CATEGORICAL,
    KIND_NUMERIC,
    build_inputs,
    build_parameters,
    parse_params_raw,
    resolve_parameters,
)
from auphoria.report.report import build_methods_text, build_report_html

DEFAULT_RESULTS_ROOT = Path(
    os.environ.get("AUPHORIA_RESULTS_ROOT", "") or Path.home() / "AUPHORIA_results"
)
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_name(text: str, fallback: str = "data") -> str:
    cleaned = _SAFE_NAME_RE.sub("_", str(text)).strip("._-")
    return cleaned or fallback


def _ascii(s: str) -> str:
    """Best-effort ASCII for filenames that must work on every OS."""
    out = s.encode("ascii", "replace").decode("ascii")
    return re.sub(r"[^A-Za-z0-9._-]+", "_", out)


def results_dir_name(data_name: str, analysis_id: str, timestamp: str) -> str:
    return f"{data_name}_{analysis_id}_{timestamp}"


def resolve_results_dir(
    data_name: str,
    analysis_id: str,
    timestamp: str,
    out: Path | None,
) -> Path:
    if out is not None:
        base = out.expanduser().resolve()
        if base.exists() and any(base.iterdir()):
            raise InputValidationError(
                f"The output folder '{out}' already exists and is not empty.",
                hint="Choose a new --out path, or let AUPHORIA make one for you.",
            )
        return base
    root = DEFAULT_RESULTS_ROOT
    candidate = root / results_dir_name(data_name, analysis_id, timestamp)
    suffix = 2
    while candidate.exists():
        candidate = root / f"{results_dir_name(data_name, analysis_id, timestamp)}-{suffix}"
        suffix += 1
    return candidate


def _find_input_candidates(
    profile: Any,
    input_spec: Any,
) -> list[str]:
    """Columns of a kind acceptable to this input (for menu / mapping)."""
    kinds = set(input_spec.accepts)
    # Fall back to the primary kind if 'accepts' is empty (shouldn't happen).
    if not kinds:
        kinds = {input_spec.kind}
    candidates: list[str] = []
    for col in profile.columns:
        if col.kind in kinds:
            candidates.append(col.name)
    return candidates


class Engine:
    def __init__(self, expert: bool = False) -> None:
        self.expert = bool(expert)

    # ------------------------------------------------------------------ run
    def run(
        self,
        *,
        data_path: str | Path,
        analysis: str,
        outcome: str | None,
        group: str | None,
        extra: dict[str, str],
        params: dict[str, Any] | Sequence[str] | None,
        seed: int,
        out: str | Path | None,
        column_kinds: dict[str, str],
        make_docx: bool = False,
    ) -> dict[str, Any]:
        logger = None
        results_dir: Path | None = None
        try:
            return self._run_impl(
                data_path=data_path,
                analysis=analysis,
                outcome=outcome,
                group=group,
                extra=extra,
                params=params,
                seed=seed,
                out=out,
                column_kinds=column_kinds,
                make_docx=make_docx,
            )
        except AuphoriaError:
            raise
        except Exception as exc:  # noqa: BLE001
            # Unexpected bug: report plainly; traceback into log if we have one.
            if logger is not None and results_dir is not None:
                log_traceback(logger, exc)
            raise EngineError(
                "Something unexpected went wrong while running the analysis.",
                hint=(
                    "Details were written to log.txt in the results folder. "
                    "Report this to the AUPHORIA maintainers (https://github.com/mysteriousammw/auphoria)."
                    if results_dir is not None
                    else "Please retry and report this to the maintainers."
                ),
            ) from exc

    def _run_impl(
        self,
        *,
        data_path: str | Path,
        analysis: str,
        outcome: str | None,
        group: str | None,
        extra: dict[str, str],
        params: dict[str, Any] | Sequence[str] | None,
        seed: int,
        out: str | Path | None,
        column_kinds: dict[str, str],
        make_docx: bool = False,
    ) -> dict[str, Any]:
        # ---- resolve analysis
        info = registry.get(analysis)
        # Deps-guard: refuse before importing the module if a required heavy
        # dependency (pack-specific) is missing, showing the exact install cmd.
        from auphoria.packs import deps_message, missing_requires

        required = [str(r) for r in (info.manifest.get("requires") or [])]
        if missing_requires(required):
            pack = info.manifest.get("pack") or []
            pack_hint = pack[0] if isinstance(pack, list) and pack else None
            raise InputValidationError(
                "A package this analysis needs is not installed.",
                hint=deps_message(required, pack_hint),
            )
        analysis_instance = registry.load_analysis(analysis)
        manifest = info.manifest

        # ---- hash the raw file (before any parsing)
        data_path = str(data_path)
        input_file = Path(data_path).expanduser()
        input_sha = sha256_of_file(input_file) if input_file.is_file() else None

        # ---- prepare the results folder + logging FIRST so log.txt exists
        data_name = sanitize_name(input_file.stem)
        run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = Path(out).expanduser() if out else None
        results_dir = resolve_results_dir(data_name, analysis, run_timestamp, out_path)
        results_dir.mkdir(parents=True, exist_ok=True)
        logger = setup_logging(log_file=results_dir / "log.txt", expert=self.expert)
        versions = environment_info()
        log_decision(logger, f"Starting analysis '{analysis}' on '{input_file}'.")
        log_decision(logger, f"Jobs are written into '{results_dir}'.")

        # ---- read + profile data
        df, adapter_warnings = read_data_frame(input_file)
        for warn in adapter_warnings:
            log_decision(logger, f"Data notice: {warn}")
        profile = profile_data_frame(df, column_kinds)
        log_decision(
            logger,
            f"Data loaded: {df.shape[0]} rows x {df.shape[1]} columns. "
            f"Column kinds:\n{render_column_summary(profile)}",
        )

        # ---- build the rich data card (never modifies df) and log every flag
        from auphoria.core.data_card import profile_data_card

        data_card = profile_data_card(df)
        log_decision(
            logger,
            f"Data card: {data_card.n_rows} rows x {data_card.n_cols} cols, "
            f"{data_card.n_duplicate_rows} duplicate row(s).",
        )
        for flag in data_card.flags:
            log_decision(logger, f"Data-card [{flag.level}] {flag.message}")

        # ---- resolve inputs (outcome/group/extra -> declared input names)
        inputs, input_notes = self._resolve_inputs(
            manifest, df, profile, outcome, group, extra, logger
        )

        # ---- resolve parameters
        raw_params = parse_params_raw(params)
        param_specs = build_parameters(manifest)
        resolved_params, param_notes = resolve_parameters(param_specs, raw_params)
        for note in param_notes + input_notes:
            log_decision(logger, note)

        # ---- fit check (refuse/warn early)
        self._check_fit(profile, analysis_instance, resolved_params, inputs, logger)

        # ---- build context and run
        ctx = RunContext(
            seed=seed,
            out_dir=results_dir,
            data_name=data_name,
            expert=self.expert,
            _log=logger,
            _log_decision=lambda m: log_decision(logger, m),
            input_sha256=input_sha or "",
            package_versions=versions,
            parameters=dict(resolved_params),
        )
        try:
            result = analysis_instance.run(df, resolved_params, inputs, ctx)
        except AuphoriaError:
            raise
        except Exception as exc:  # noqa: BLE001
            log_traceback(logger, exc)
            raise EngineError(
                "The analysis ran into an unexpected error.",
                hint=(
                    "The technical details are in log.txt. Report this to the "
                    "maintainers (https://github.com/mysteriousammw/auphoria)."
                ),
            ) from exc

        # ---- write outputs
        tables = result.tables or {}
        figures = result.figures or []
        warnings = list(result.warnings)
        notes = list(result.notes)

        # CSV tables
        written_files: list[str] = []
        csv_records: list[dict[str, Any]] = []
        for name, df_table in tables.items():
            safe_name = f"{_ascii(name)}.csv"
            table_path = results_dir / safe_name
            df_table.to_csv(table_path, index=False)
            written_files.append(safe_name)
            csv_records.append(
                {"name": safe_name, "rows": int(df_table.shape[0]),
                 "cols": int(df_table.shape[1])}
            )
            log_decision(logger, f"Wrote results table '{safe_name}'.")

        # PNG figures
        figure_records: list[dict[str, str]] = []
        for item in figures:
            fname = f"{_ascii(item.name)}.png"
            fig_path = results_dir / fname
            item.figure.savefig(fig_path, dpi=150, bbox_inches="tight")

            from auphoria.report.report import _png_base64
            src = _png_base64(fig_path)
            figure_records.append({"name": fname, "src": src, "caption": item.caption})
            import matplotlib.pyplot as plt
            plt.close(item.figure)
            written_files.append(fname)
            log_decision(logger, f"Wrote figure '{fname}'.")

        # methods.txt - fill library names, versions, test name, alpha from context
        methods_text = build_methods_text(
            analysis_name=info.name,
            methods=result.methods or [],
            data_name=data_name,
            inputs={k: v for k, v in inputs.items()},
            versions=versions,
            seed=seed,
            test_name=info.name,
            alpha=resolved_params.get("alpha"),
        )
        (results_dir / "methods.txt").write_text(methods_text, encoding="utf-8")
        written_files.append("methods.txt")

        # replay scripts
        replay = self._replay_command(input_file, analysis, inputs, resolved_params, seed, results_dir)
        (results_dir / "replay.sh").write_text(self._replay_sh(replay), encoding="utf-8")
        (results_dir / "replay.ps1").write_text(self._replay_ps1(replay), encoding="utf-8")
        written_files.extend(["replay.sh", "replay.ps1"])

        # run.json (reproducibility manifest)
        run_timestamp_iso = datetime.now().isoformat(timespec="seconds")
        # Verdicts + decision log (every assumption check, data decision, and
        # whether a test was/wasn't run with the plain reason).
        verdicts = [v.as_dict() for v in (result.verdicts or [])]
        decision_log = ctx.decision_log_dicts()
        expert_review = list(result.expert_review or [])
        run_info = {
            "auphoria_version": versions.get("auphoria"),
            "analysis": {"id": analysis, "name": info.name, "maturity": info.maturity},
            "input_file": str(input_file),
            "input_sha256": input_sha,
            "data": {"rows": int(df.shape[0]), "cols": int(df.shape[1])},
            "seed": int(seed),
            "inputs": {k: str(v) for k, v in inputs.items()},
            "parameters": {k: str(v) for k, v in resolved_params.items()},
            "package_versions": versions,
            "timestamp": run_timestamp_iso,
            "replay_command": replay,
            "outputs": written_files,
            "tables": csv_records,
            "verdicts": verdicts,
            "decision_log": decision_log,
            "expert_review": expert_review,
            "what_does_not_tell": result.what_does_not_tell or "",
        }
        (results_dir / "run.json").write_text(
            json.dumps(run_info, indent=2, default=str), encoding="utf-8"
        )
        written_files.append("run.json")

        # report.html
        report_html = build_report_html(
            analysis_name=info.name,
            data_name=data_name,
            data_path=str(input_file),
            maturity=info.maturity,
            run_timestamp=run_timestamp_iso,
            summaries=result.summaries or {},
            tables=tables,
            figures=figure_records,
            methods=result.methods or [],
            warnings=warnings,
            notes=notes,
            verdicts=verdicts,
            what_does_not_tell=result.what_does_not_tell or "",
            expert_review=expert_review,
            decision_log=decision_log,
            assumptions=[str(a) for a in manifest.get("assumptions", [])],
            limitations=[str(x) for x in manifest.get("limitations", [])],
            params=resolved_params,
            inputs=inputs,
            run_info=run_info,
            versions=versions,
            expert=self.expert,
        )
        (results_dir / "report.html").write_text(report_html, encoding="utf-8")
        log_decision(logger, "Wrote report.html.")

        # Optional Word file (methods paragraph + result tables) for a thesis.
        if make_docx:
            from auphoria.report.report import build_docx

            try:
                build_docx(
                    title=f"{info.name} — AUPHORIA results",
                    methods_text=methods_text,
                    tables=tables,
                    out_path=results_dir / "auphoria-report.docx",
                )
                written_files.append("auphoria-report.docx")
                log_decision(logger, "Wrote auphoria-report.docx.")
            except AuphoriaError as exc:
                log_decision(logger, f"DOCX skipped: {exc.message}")
                from auphoria.core.logging_core import get_logger

                get_logger().warning(
                    "Skipped Word output (missing python-docx). Install with "
                    "pip install auphoria[docx] to enable --docx."
                )
        logger.info("Run complete. Results in: %s", results_dir)

        return {
            "results_dir": str(results_dir),
            "analysis": analysis,
            "analysis_name": info.name,
            "seed": int(seed),
            "input_file": str(input_file),
            "input_sha256": input_sha,
            "summaries": result.summaries or {},
            "warnings": warnings,
            "notes": notes,
            "methods": result.methods or [],
            "tables": list(tables.keys()),
            "figures": [f["name"] for f in figure_records],
            "replay_command": replay,
            "run_info": run_info,
            "verdicts": verdicts,
            "decision_log": decision_log,
            "what_does_not_tell": result.what_does_not_tell or "",
            "data": {"rows": int(df.shape[0]), "cols": int(df.shape[1])},
        }

    # ------------------------------------------------------------- helpers
    def _resolve_inputs(
        self,
        manifest: dict[str, Any],
        df: pd.DataFrame,
        profile: Any,
        outcome: str | None,
        group: str | None,
        extra: dict[str, str],
        logger: Any,
    ) -> tuple[dict[str, str], list[str]]:
        """Map the analysis's declared inputs to concrete columns.

        Mapping rules (in priority order, per input):
          - an exact match by name in ``extra`` (e.g. {"x": ..., "y": ...});
          - ``outcome`` -> the first input whose accepts-kind is numeric;
          - ``group``   -> the first input whose accepts-kind is categorical;
          - otherwise -> error if required, else skipped.
        """
        inputs: dict[str, str] = {}
        notes: list[str] = []
        input_specs = build_inputs(manifest)
        numeric_inputs = [s for s in input_specs if KIND_NUMERIC in s.accepts]
        categorical_inputs = [s for s in input_specs if KIND_CATEGORICAL in s.accepts]

        outcome_used = False
        group_used = False

        for spec in input_specs:
            # 1. exact extra mapping
            if spec.name in extra:
                inputs[spec.name] = extra[spec.name]
                continue

            # 2. outcome/group convenience
            if outcome and spec in numeric_inputs and not outcome_used:
                inputs[spec.name] = outcome
                outcome_used = True
                continue
            if group and spec in categorical_inputs and not group_used:
                inputs[spec.name] = group
                group_used = True
                continue

            # 3. required without a value -> error; optional -> skip
            if spec.required:
                candidates = _find_input_candidates(profile, spec)
                hint = (
                    f"Pass a column for '{spec.name}' (e.g. --outcome/--group or "
                    f"--extra {spec.name}=COL). Suitable columns: "
                    f"{', '.join(candidates) or '(none found)'}."
                    if candidates
                    else (
                        f"No suitable column found for '{spec.name}'. It needs: "
                        f"{spec.kind}."
                    )
                )
                raise InputValidationError(
                    f"The analysis needs a column for '{spec.name}' but none "
                    f"was provided.",
                    hint=hint,
                )
            # optional input with no match -> note only
            notes.append(
                f"(optional input '{spec.name}' not provided; it will be skipped)"
            )

        if outcome and not outcome_used:
            notes.append("A --outcome column was given, but this analysis has no "
                         "numeric input that accepts it; it was ignored.")
        if group and not group_used:
            notes.append("A --group column was given, but this analysis has no "
                         "categorical input that accepts it; it was ignored.")
        return inputs, notes

    def _check_fit(
        self,
        profile: Any,
        analysis_instance: Any,
        params: dict[str, Any],
        inputs: dict[str, str],
        logger: Any,
    ) -> None:
        """Validate columns exist and that this data satisfies the analysis's
        declared input kinds, then call the analysis's own check_fit."""
        # Every mapped input column must exist.
        for role, colname in inputs.items():
            if colname not in [c.name for c in profile.columns]:
                raise InputValidationError(
                    f"Could not find the column '{colname}' (used for '{role}').",
                    hint="Available columns: "
                    + ", ".join(c.name for c in profile.columns) + ".",
                )
        # Declared kind match is advisory for numeric; the analysis's
        # ensure_numeric will refuse text masquerading as numbers.
        refusals = analysis_instance.check_fit(profile, params, inputs) or []
        for msg in refusals:
            log_decision(logger, f"Fit refusal: {msg}")
        if refusals:
            raise AssumptionError(
                "This analysis does not fit your data the way it is set up.",
                hint="\n".join(refusals),
            )

    @staticmethod
    def _replay_command(
        input_file: Path,
        analysis: str,
        inputs: dict[str, str],
        params: dict[str, Any],
        seed: int,
        results_dir: Path,
    ) -> str:
        cmd_parts = ["auphoria", "run", "--data", str(input_file), "--analysis", analysis]
        for role, col in inputs.items():
            if role in ("outcome", "group"):
                cmd_parts += [f"--{role}", col]
            else:
                cmd_parts += ["--extra", f"{role}={col}"]
        for k, v in params.items():
            cmd_parts += ["--param", f"{k}={v}"]
        # NOTE: no --out, so the replay writes a fresh timestamped folder and
        # can never collide with (or overwrite) the original run.
        cmd_parts += ["--seed", str(seed)]
        return " ".join(shlex.quote(p) for p in cmd_parts)

    @staticmethod
    def _replay_sh(replay: str) -> str:
        return (
            "#!/usr/bin/env bash\n"
            "# AUPHORIA replay command. Run this to reproduce the exact run.\n"
            "# (Runs on your machine; it re-reads the original data file.)\n\n"
            f"{replay}\n"
        )

    @staticmethod
    def _replay_ps1(replay: str) -> str:
        return (
            "# AUPHORIA replay command (PowerShell). Reproduces the exact run.\n"
            f"{replay}\n"
        )
