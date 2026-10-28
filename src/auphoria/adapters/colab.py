"""Colab-specific front-end helpers for the notebook.

Everything that touches ``google.colab`` lives here so the notebook itself
stays a thin, beginner-readable set of cells. Each function imports
``google.colab`` lazily because the module only exists inside a Colab
runtime — importing ``auphoria`` or this module must never fail on a laptop.

No statistical logic lives here or in the notebook. This module only does
front-end chores (upload, filter the analysis list to what fits the data,
zip + download results, optionally copy to Drive). Analysis is delegated to
:func:`auphoria.run` and fit-checking to :func:`auphoria.core.fitting`.

Outside a Colab kernel every helper that needs the Colab bridge raises a
clear :class:`ColabRequired` error with a hint, so a student who copy-pastes
basically works and gets a useful message rather than a traceback.
"""

from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path

from auphoria.core.fitting import analyses_that_fit


class ColabRequired(RuntimeError):
    """Raised when a helper needs the google.colab bridge but we're not in it."""


def _files():
    """Return the google.colab.files module or raise a helpful error."""
    try:
        import google.colab.files as files  # type: ignore[import-not-found]
    except (ImportError, ModuleNotFoundError):
        raise ColabRequired(
            "This step only works inside a Google Colab runtime. Run this "
            "notebook in Colab (or use the laptop installer for offline "
            "analysis)."
        ) from None
    return files


def is_colab() -> bool:
    """True when running inside a Google Colab runtime."""
    try:
        import google.colab  # noqa: F401
    except (ImportError, ModuleNotFoundError):
        return False
    return True


def upload() -> dict[str, bytes]:
    """Open Colab's file picker; return {filename: bytes} (or {} if cancelled)."""
    return _files().upload()


def save_uploaded(uploaded: dict[str, bytes], dest: str | Path = ".") -> list[str]:
    """Write the uploaded files to ``dest``; return the absolute saved paths."""
    dest = Path(dest)
    saved: list[str] = []
    for name, data in uploaded.items():
        path = dest / name
        path.write_bytes(data)
        saved.append(str(path))
    return saved


def show_report(results_dir: str | Path) -> None:
    """Render report.html inline in the notebook."""
    from IPython.display import HTML, display

    html = (Path(results_dir) / "report.html").read_text(encoding="utf-8")
    display(HTML(html))


def zip_results(results_dir: str | Path, out: str | Path | None = None) -> Path:
    """Zip a results folder and return the zip path (sibling of results_dir)."""
    results_dir = Path(results_dir)
    if not results_dir.is_dir():
        raise FileNotFoundError(f"Results folder not found: {results_dir}")
    zip_path = Path(out) if out else results_dir.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(results_dir):
            for fn in sorted(files):
                full = Path(root) / fn
                zf.write(full, full.relative_to(results_dir))
    return zip_path


def download(results_dir: str | Path | None = None, zip_path: str | Path | None = None) -> str:
    """Zip (if not given) a results folder and trigger the browser download.

    Returns the zip path so callers can report it.
    """
    if zip_path is None:
        if results_dir is None:
            raise ValueError("Give either results_dir or zip_path.")
        zip_path = zip_results(results_dir)
    _files().download(str(zip_path))
    return str(zip_path)


def save_to_drive(archive: str | Path, drive_root: str = "/content/drive") -> Path | None:
    """Optionally copy a results archive into Google Drive.

    Only works when Drive is mounted (in Colab, run the Drive-mount snippet
    in the left panel first). Returns the destination path, or None if Drive
    is not mounted so the notebook can continue without erroring.
    """
    archive = Path(archive)
    drive_root = Path(drive_root)
    if not drive_root.is_dir():
        return None
    dest = drive_root / "MyDrive" / "AUPHORIA_results"
    dest.mkdir(parents=True, exist_ok=True)
    return shutil.copy2(archive, dest / archive.name)


def fitting_analysis_ids(data_path: str | Path) -> list[str]:
    """Analysis ids that can run on a data file, filtered to what fits.

    Reuses the same fit-checker as the CLI menu so the notebook never
    re-implements it.
    """
    from auphoria.adapters.adapters import read_data_frame
    from auphoria.advisor.advisor import profile_data_frame

    df, _warnings = read_data_frame(data_path)
    profile = profile_data_frame(df)
    kinds = [c.kind for c in profile.columns]
    return analyses_that_fit(kinds)
