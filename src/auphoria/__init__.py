"""AUPHORIA - beginner-friendly data analysis for university students.

The public interface is deliberately small:

    import auphoria
    auphoria.run(data_path="my_data.csv", analysis="ttest",
                 outcome="height_cm", group="treatment")

Everything a user can do in the terminal or the Colab notebook goes through
:func:`auphoria.run`; the analysis logic itself lives in analysis modules.

AUPHORIA works fully offline after install. It makes no network calls at
run time, uses no AI, and never silently drops or changes your data.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from auphoria.core import errors as _errors

# Avoid importing the heavy engine / pandas at import time unless a caller
# actually needs it. `run` and `list_analyses` are what Colab/the CLI use.
from auphoria.core.registry import list_analyses as _list_analyses  # noqa: E402
from auphoria.core.version import __version__  # noqa: F401

__all__ = [
    "__version__",
    "run",
    "list_analyses",
    "data_types",
    "DataProfileError",
    "AuphoriaError",
]

# Re-export for convenience so front ends can print the canonical analysis list.
list_analyses = _list_analyses


def data_types(path: str | Path) -> dict[str, str]:
    """Return a {column: detected_kind} mapping for a data file (no analysis).

    Kinds are one of: numeric, categorical, datetime, text.

    Front ends (CLI and Colab) use this to build their column dropdowns. It
    does not itself run any statistical analysis.
    """
    from auphoria.adapters.adapters import read_data_frame
    from auphoria.advisor.advisor import profile_data_frame

    df, _warnings = read_data_frame(path)
    profile = profile_data_frame(df)
    return {c.name: c.kind for c in profile.columns}


def run(
    data_path: str | Path,
    analysis: str,
    outcome: str | None = None,
    group: str | None = None,
    extra: dict[str, Any] | None = None,
    params: dict[str, Any] | Sequence[str] | None = None,
    seed: int = 1,
    out: str | Path | None = None,
    expert: bool = False,
    column_kinds: dict[str, str] | None = None,
    make_docx: bool = False,
) -> dict[str, Any]:
    """Run one analysis end to end and write a reproducible result set.

    Args:
        data_path: path to a CSV, TSV/TXT or Excel (.xlsx) file.
        analysis: analysis id, e.g. ``"ttest"`` (see :func:`list_analyses`).
        outcome: name of the column to treat as the outcome. Mapped to the
            analysis's first matching numeric input if no exact name matches.
        group: name of the column to treat as the group/category. Mapped to
            the analysis's first matching categorical input if needed.
        extra: a dict of additional named columns, e.g. a second predictor
            for correlation: ``{"x": "height_cm", "y": "mass_g"}``.
        params: dict of parameter values, or a sequence of ``"name=value"``
            strings (as the CLI passes); unknown names raise an error.
        seed: random seed, recorded for reproducibility (default 1).
        out: where to write results. Defaults to
            ``~/AUPHORIA_results/<dataname>_<analysis>_<timestamp>/``.
        expert: suppress beginner-facing explanations (default False).
        column_kinds: optional overrides for detected column kinds, e.g.
            ``{"treatment": "categorical"}``. Only used where it matters.

    Returns:
        A dict describing the run (results_dir, analysis, summaries,
        warnings, run_info, etc.). The result files are the deliverable.

    Raises:
        AuphoriaError subclasses with plain-English messages; the full
        traceback is written to ``log.txt`` in the results folder.
    """
    from auphoria.core.engine import Engine

    engine = Engine(expert=expert)
    return engine.run(
        data_path=data_path,
        analysis=analysis,
        outcome=outcome,
        group=group,
        extra=extra or {},
        params=params,
        seed=seed,
        out=out,
        column_kinds=column_kinds or {},
        make_docx=make_docx,
    )


# Convenience aliases for front ends that want explicit names.
AuphoriaError = _errors.AuphoriaError
DataProfileError = _errors.InputValidationError
