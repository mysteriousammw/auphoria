"""Build notebooks/auphoria_colab.ipynb as a valid JSON notebook.

Kept as a build-time helper so the .ipynb is always produced as well-formed
JSON even when edited. Run:  python scripts/build_notebook.py

Phase 5 structure — short cells, plain-language headings, no analysis logic
in the notebook (it all lives behind auphoria.run and the
auphoria.adapters.colab helpers):

  1. Install AUPHORIA (REPO_URL var + privacy notice + zip "test before
     publish" alternative)
  2. Upload your data file
  3. Preview your data and pick columns, roles and analysis
  4. Run the analysis and see your report
  5. Download your results (and optional save to Drive)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_URL_MARKER = "https://github.com/mysteriousammw/auphoria"
NOTEBOOK_PATH = Path(__file__).resolve().parent.parent / "notebooks" / "auphoria_colab.ipynb"

# Shared code fragments ------------------------------------------------------

_INSTALL = f'''\
REPO_URL = "{_REPO_URL_MARKER}"   # your published GitHub repository

# 1) INSTALL FROM THE PUBLISHED REPO (normal case):
#    -----------------------------------------------
#    This pulls AUPHORIA from your GitHub repository and installs it into
#    this Colab session. _Colab sessions are temporary_: you install once per
#    session, and the install is undone when the runtime restarts.
# ---------------------------------------------------------------------------
import subprocess, sys

installed = False
try:
    import auphoria  # already installed this session -> skip re-install
    installed = True
except ImportError:
    pass

if not installed:
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "-q", "git+" + REPO_URL,
    ])
    import auphoria
print("AUPHORIA", auphoria.__version__, "ready.", "(already installed)" if installed else "")

# 2) ONLY for testing BEFORE your repository is published:
#    -----------------------------------------------------
#    If you have not pushed to GitHub yet, install straight from a zip of
#    this project instead. Steps:
#       a) On your laptop, zip the whole auphoria folder
#          (the one containing pyproject.toml), e.g.
#             zip -r auphoria_src.zip auphoria/ -x "*.venv/*" -x "*__pycache__*"
#       b) Run the UPLOAD cell below first (cell 2) and use it to upload
#          auphoria_src.zip, then uncomment and run these lines:
#       c) Re-run; AUPHORIA is then installed from your zip.
# ---------------------------------------------------------------------------
# import subprocess, sys
# subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
#                        "/content/auphoria_src.zip"])
# import auphoria
# print("AUPHORIA", auphoria.__version__, "ready. (installed from your zip)")'''

_UPLOAD = '''\
# 2) UPLOAD YOUR DATA FILE
#    ----------------------
#    Click the button and choose a CSV / TSV / TXT / XLSX file. It is copied
#    into this Colab session (to Google's temporary runtime, not your laptop).
# ---------------------------------------------------------------------------
from auphoria.adapters import colab

print("Choose a CSV / TSV / TXT / XLSX file:")
_uploaded = colab.upload()
assert _uploaded, "No file uploaded - run this cell again and pick a file."
_saved = colab.save_uploaded(_uploaded, ".")
DATA_FILE = _saved[0]
print("Saved as", DATA_FILE)'''

_PREVIEW = '''\
# 3) PREVIEW YOUR DATA, THEN PICK COLUMNS, ROLES AND ANALYSIS
#    --------------------------------------------------------
#    The form below previews your data and asks only the questions the
#    analysis needs. Choose here; everything runs through auphoria.run().
# ---------------------------------------------------------------------------
import pandas as pd
import ipywidgets as widgets
from IPython.display import display

from auphoria.adapters import colab
import auphoria

# --- preview the first rows ------------------------------------------------
_df = auphoria.data_types(DATA_FILE)          # {column: kind} (no analysis)
_preview = pd.read_csv(DATA_FILE, sep=None, engine="python") \\
    if not DATA_FILE.lower().endswith(("xlsx", "xlsm")) \\
    else pd.read_excel(DATA_FILE)
_dtypes = _df   # kinds: numeric / categorical / datetime / text
_num = [c for c, k in _dtypes.items() if k == "numeric"]
_cat = [c for c, k in _dtypes.items() if k == "categorical"]

print("Shape:", _preview.shape)
display(_preview.head(6))
print()
print("Kinds:  numeric =", _num)
print("        categorical =", _cat)
print()

# --- which analyses fit THESE columns (reuses the engine's own fit-checker)
_fitting = colab.fitting_analysis_ids(DATA_FILE)
print("Analyses that fit your data:", _fitting)
print()

# --- the form ---------------------------------------------------------------
_default_analysis = "describe" if "describe" in _fitting else _fitting[0]
_analysis = widgets.Dropdown(options=_fitting, value=_default_analysis,
                             description="Analysis:", style={"description_width":"130px"})
_outcome  = widgets.Dropdown(options=[None] + _num, value=None,
                             description="Outcome (numeric):",
                             style={"description_width":"130px"})
_group    = widgets.Dropdown(options=[None] + _cat, value=None,
                             description="Group (category):",
                             style={"description_width":"130px"})
_extra    = widgets.Dropdown(options=[None] + _num, value=None,
                             description="2nd numeric (extra):",
                             style={"description_width":"130px"})
_params   = widgets.Text(value="", placeholder="optional: alpha=0.05",
                         description="Options:", style={"description_width":"130px"})
_seed     = widgets.IntText(value=1, description="Random seed:",
                            style={"description_width":"130px"})
display(_analysis, _outcome, _group, _extra, _params, _seed)
print("Now go to cell 4 and press the RUN button.")'''

_RUN = '''\
# 4) RUN THE ANALYSIS AND SEE YOUR REPORT
#    -------------------------------------
#    Press RUN. AUPHORIA does the statistics, writes the report and shows it
#    right here. All analysis lives in the auphoria engine — this cell only
#    drives it.
# ---------------------------------------------------------------------------
import ipywidgets as widgets
from IPython.display import display
from auphoria.adapters import colab

_run_btn = widgets.Button(description="RUN analysis", button_style="primary")
_run_out = widgets.Output()
_last_results_dir = None


def run_now():
    """Call auphoria.run(...) with the current form choices (no option is
    skipped silently: missing required inputs are reported)."""
    global _last_results_dir
    import auphoria

    params = []
    if _params.value.strip():
        for tok in _params.value.replace(";", " ").split():
            if "=" in tok:
                params.append(tok)
    extra = {"x": _extra.value} if _extra.value else {}
    with _run_out:
        _run_out.clear_output()
        print("Running", _analysis.value, "...")
        try:
            _res = auphoria.run(
                data_path=DATA_FILE,
                analysis=_analysis.value,
                outcome=_outcome.value,
                group=_group.value,
                extra=extra,
                params=params,
                seed=_seed.value,
            )
        except Exception as exc:
            print("Could not run:", exc)
            return
        _last_results_dir = _res["results_dir"]
        for k, v in _res["summaries"].items():
            print(f"  {k}: {v}")
        for w in _res["warnings"]:
            print("  Heads-up:", w)
        print("Report:")
    colab.show_report(_last_results_dir)


def _on_click(_btn):
    run_now()


_run_btn.on_click(_on_click)
display(_run_btn, _run_out)

# Uncork the button below IF the cell did not run automatically.
# A first run executes immediately so you see output without any click.
run_now()'''

_DOWNLOAD = '''\
# 5) DOWNLOAD YOUR RESULTS (ZIP -> LAPTOP), OPTIONALLY SAVE TO DRIVE
#    --------------------------------------------------------------
#    Makes a zip of the results folder and downloads it to your computer.
#    The zip contains: report.html, result CSVs, figures, methods.txt,
#    run.json (reproducible). Optional: also copy it into Google Drive.
# ---------------------------------------------------------------------------
from auphoria.adapters import colab

if _last_results_dir:
    _zip = colab.zip_results(_last_results_dir)
    print("Zipped:", _zip)
    colab.download(zip_path=_zip)
    print("Download started - the zip should land in your Downloads folder.")

    # --- OPTIONAL: save a copy to Google Drive ---
    # Mount Drive in the left panel first (folder icon -> Drive -> Mount
    # Drive), then uncomment the next line and re-run this cell.
    # colab.save_to_drive(_zip)
else:
    print("No completed run yet - run cell 4 first.")'''

_FOOTER_MD = '''\
## Reproducibility & help

- Every run writes a **methods.txt** paragraph to paste into your paper, a
  **report.html**, tables (CSV), figures (PNG), **run.json** and a
  **replay command** — so you (or your supervisor) can reproduce the exact
  numbers on a laptop with `auphoria run ...`.
- AUPHORIA never drops or imputes your data; it counts missing values and
  warns when a test does not fit.
- All analysis logic lives in the AUPHORIA engine (`auphoria.run(...)`); this
  notebook is just a friendly button-driven front end.
- **Colab limits:** uploaded files live only in this temporary session and
  vanish when the runtime stops. Always download your results (cell 5) before
  you leave.

See the README at https://github.com/mysteriousammw/auphoria for the command-line tool and the
offline laptop install (recommended for confidential data).
'''


def _md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def _code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(keepends=True),
    }


def build() -> dict:
    nb = {
        "cells": [],
        "metadata": {
            "colab": {"name": "auphoria_colab.ipynb", "toc_visible": True},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 0,
    }

    nb["cells"].append(_md(
        "# AUPHORIA — data analysis without programming\n"
        "\n"
        "Run a real statistical analysis in a few clicks: **upload your data "
        "file, pick the analysis and columns, run, download your results** as a "
        "zip (report, tables, figures, methods.txt).\n"
        "\n"
        "AUPHORIA is free and open-source. It uses the same engine as the "
        "command-line tool (`auphoria run ...`).\n"
        "\n"
        "> **⚠️ Privacy notice:** this notebook runs on **Google Colab**, i.e. "
        "on Google's servers. Any file you upload goes to Google's temporary "
        "runtime and disappears when the session ends. **Do not upload "
        "confidential data here.** Use the laptop installer (see the README) "
        "for the private, fully-offline option.\n"
        "\n"
        "## 1) Install · 2) Upload · 3) Pick · 4) Run · 5) Download\n"
        "Run the numbered cells in order."
    ))

    nb["cells"].append(_code(_INSTALL))
    nb["cells"].append(_md(
        "# 2) Upload your data file\n"
        "Click the button and choose a **CSV**, **TSV/TXT** or **Excel "
        "(.xlsx)** file. It is copied into this Colab session."
    ))
    nb["cells"].append(_code(_UPLOAD))
    nb["cells"].append(_md(
        "# 3) Preview and pick your analysis\n"
        "This form tells AUPHORIA what is in your data and which analysis to "
        "run. You only choose; the engine does the statistics."
    ))
    nb["cells"].append(_code(_PREVIEW))
    nb["cells"].append(_md(
        "# 4) Run the analysis and see your report\n"
        "Press **RUN** below. A first run happens automatically so you can "
        "see the output; change a dropdown and press RUN again to re-run."
    ))
    nb["cells"].append(_code(_RUN))
    nb["cells"].append(_md(
        "# 5) Download your results\n"
        "Makes a zip of everything the run created and downloads it. "
        "Optional: save the same zip to your Google Drive."
    ))
    nb["cells"].append(_code(_DOWNLOAD))
    nb["cells"].append(_md(_FOOTER_MD))

    return nb


def main() -> int:
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    nb = build()
    NOTEBOOK_PATH.write_text(
        json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    # Validate it round-trips and carries the required markers.
    parsed = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    assert parsed["nbformat"] == 4
    code = "".join("".join(c.get("source", "")) for c in parsed["cells"] if c["cell_type"] == "code")
    assert "auphoria.run(" in code
    assert _REPO_URL_MARKER in code
    assert "colab.upload" in code
    assert "colab.download" in code or "files.download" in code
    print(f"Wrote {NOTEBOOK_PATH} ({len(parsed['cells'])} cells).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
