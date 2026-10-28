"""Rendering the run's outputs: report.html (Jinja2), methods.txt, and .docx.

``report.html`` is a single self-contained file rendered from a Jinja2
template: inline CSS, base64-embedded figures, a QC verdict table, the
decision log, the methods paragraph, a "what this result does not tell you"
box, and software versions. It opens offline with no external requests.
``methods.txt`` is a paste-ready methods paragraph for a paper.
``auphoria-report.docx`` is the same methods paragraph + result tables for
students who need a Word file to paste into a thesis.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import pandas as pd
from jinja2 import Environment, PackageLoader, select_autoescape

from auphoria.core.version import __version__ as AUPHORIA_VERSION

_TEMPLATE_ENV = Environment(
    loader=PackageLoader("auphoria.report", "templates"),
    autoescape=select_autoescape()
)


def _fmt(v: Any) -> str:
    if v is None:
        return "NA"
    if isinstance(v, float):
        if v != v:  # NaN
            return "NA"
        return f"{v:.4g}"
    return str(v)


def _table_to_html(table: pd.DataFrame) -> str:
    """Render a small result table with inline styling (no external CSS)."""
    try:
        return table.to_html(
            index=False,
            border=0,
            classes="auphoria-table",
            float_format=lambda x: f"{x:.4g}",
        )
    except Exception:  # noqa: BLE001 - never let formatting break the report
        return "<p><em>(table could not be rendered)</em></p>"


def _png_base64(path: Path) -> str:
    data = path.read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def build_report_html(
    *,
    analysis_name: str,
    data_name: str,
    data_path: str,
    maturity: str,
    run_timestamp: str,
    summaries: dict[str, str],
    tables: dict[str, pd.DataFrame],
    figures: list[dict[str, str]],      # [{name, src (data URI), caption}]
    methods: list[str],
    warnings: list[str],
    notes: list[str],
    verdicts: list[dict[str, str]] | None = None,
    what_does_not_tell: str = "",
    expert_review: list[str] | None = None,
    decision_log: list[dict[str, Any]] | None = None,
    assumptions: list[str] | None = None,
    limitations: list[str] | None = None,
    params: dict[str, Any] | None = None,
    inputs: dict[str, str] | None = None,
    run_info: dict[str, Any] | None = None,
    versions: dict[str, str] | None = None,
    expert: bool = False,
) -> str:
    """Assemble the single self-contained HTML report."""
    run_info = run_info or {}
    params = params or {}
    inputs = inputs or {}
    versions = versions if versions is not None else run_info.get("package_versions", {})
    assumptions = assumptions or []
    limitations = limitations or []
    decision_log = decision_log or []
    expert_review = expert_review or []

    # Render each table to HTML strings the template can insert verbatim.
    rendered_tables = {name: _table_to_html(df) for name, df in tables.items()}

    template = _TEMPLATE_ENV.get_template("report.html.j2")
    return template.render(
        analysis_name=analysis_name,
        data_name=data_name,
        data_path=data_path,
        maturity=maturity,
        run_timestamp=run_timestamp,
        summaries=summaries or {},
        tables=rendered_tables,
        figures=figures or [],
        methods=methods or [],
        warnings=warnings or [],
        notes=notes or [],
        verdicts=verdicts or [],
        what_does_not_tell=what_does_not_tell,
        expert_review=expert_review,
        decision_log=decision_log,
        assumptions=assumptions,
        limitations=limitations,
        params={k: _fmt(v) for k, v in params.items()},
        inputs={k: v for k, v in inputs.items()},
        input_sha256=run_info.get("input_sha256", ""),
        seed=run_info.get("seed", ""),
        replay=run_info.get("replay_command", ""),
        versions=versions,
        auphoria_version=AUPHORIA_VERSION,
        expert=expert,
    )


def build_methods_text(
    *,
    analysis_name: str,
    methods: list[str],
    data_name: str,
    inputs: dict[str, str],
    versions: dict[str, str],
    seed: int,
    test_name: str | None = None,
    alpha: float | None = None,
    outcome_desc: str = "",
) -> str:
    """A paste-ready methods paragraph (plain text, no math rendered).

    Fills library names, versions, the test name and alpha (where present)
    from the run context so a student can paste it straight into their thesis.
    """
    parts: list[str] = []

    opening = (
        f"Analysis was performed in AUPHORIA v{AUPHORIA_VERSION} "
        f"(open-source, offline) with Python {versions.get('python', '?')}."
    )
    parts.append(opening)

    # Named test and alpha, when the analysis tells us.
    if test_name:
        alpha_bit = f" at alpha = {alpha:.3f}" if alpha is not None else ""
        parts.append(f"Statistical approach: {test_name}{alpha_bit}.")
    if outcome_desc:
        parts.append(outcome_desc)

    # The analysis's own sentences (result sentences, effect sizes, etc.).
    parts.extend(methods)

    if inputs:
        input_desc = "; ".join(f"{k}: {v}" for k, v in inputs.items())
        parts.append(f"Inputs — {input_desc}. Data file: {data_name}.")

    # Software/library versions + seed for reproducibility.
    core_libs = [k for k in ("numpy", "pandas", "scipy", "scikit-learn",
                             "statsmodels", "matplotlib", "lifelines") if k in versions]
    versions_txt = "; ".join(f"{k} {versions[k]}" for k in core_libs)
    parts.append(
        "Missing values were not imputed or deleted other than the analysis's "
        "own documented handling. "
        f"Software: {versions_txt or 'standard scientific stack'}; "
        f"random seed {seed}. Python {versions.get('python', '?')}."
    )
    return "\n\n".join(p for p in parts if p.strip()) + "\n"


def build_docx(
    *,
    title: str,
    methods_text: str,
    tables: dict[str, pd.DataFrame],
    out_path: Path,
) -> None:
    """Write a Word (.docx) file with the methods paragraph + result tables.

    Raises AuphoriaError-style ImportError message if python-docx is missing.
    """
    try:
        from docx import Document  # type: ignore[import-not-found]
    except ImportError:
        raise_import_hint()
        return  # pragma: no cover - raise_import_hint never returns

    document = Document()
    document.add_heading("AUPHORIA analysis", level=0)
    document.add_heading(title, level=2)
    document.add_heading("Methods", level=2)
    for para in methods_text.strip().split("\n\n"):
        document.add_paragraph(para)
    document.add_heading("Results", level=2)
    for name, df in tables.items():
        document.add_heading(name, level=3)
        _table_to_docx(document, df)
    document.save(str(out_path))


def _table_to_docx(document: Any, df: pd.DataFrame) -> None:
    """Insert a DataFrame as a small Word table."""
    rows = df.astype(object).where(pd.notna(df), None)
    cols = [str(c) for c in rows.columns]
    table = document.add_table(rows=1, cols=len(cols))
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    for i, c in enumerate(cols):
        hdr[i].text = c
    for _, row in rows.iterrows():
        cells = table.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = "" if v is None else _fmt(v)


def raise_import_hint() -> None:
    from auphoria.core.errors import DataError

    raise DataError(
        "Word output (.docx) needs the optional 'python-docx' package.",
        hint="Install it with:  pip install auphoria[docx]  (or 'pip install python-docx').",
    )
