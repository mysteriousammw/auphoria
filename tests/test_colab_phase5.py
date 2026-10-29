"""Acceptance test for the Phase 5 Colab notebook.

Executes notebooks/auphoria_colab.ipynb top-to-bottom with nbclient in the
project venv, injecting a fake ``google.colab`` package (see tests/colab_stub)
so the upload/download cells run outside Colab. This proves the notebook is a
valid, runnable front end — the same check done by hand in Colab (see
docs/colab-notes.md).

The upload stub returns plant_growth.csv (from AUPHORIA_STUB_UPLOAD env); the
download stub records the zip it was asked to send. The notebook runs ttest by
default, so cell 4 must produce a results dir with a report.html, and cell 5
must zip + "download" it.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import nbformat
from nbclient import NotebookClient

REPO = Path(__file__).resolve().parent.parent
NOTEBOOK = REPO / "notebooks" / "auphoria_colab.ipynb"
STUB_DIR = Path(__file__).resolve().parent / "colab_stub"
SAMPLE = REPO / "src" / "auphoria" / "sample_data" / "data" / "plant_growth.csv"

_KERNEL_ARGV = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
_KERNEL_SPEC = {
    "argv": _KERNEL_ARGV,
    "display_name": "auphoria-test",
    "language": "python",
}


def test_notebook_executes_end_to_end():
    save_env = dict(os.environ)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # Throwaway kernelspec that runs this venv's python.
        spec_dir = td / "kernels" / "auphoria-test"
        spec_dir.mkdir(parents=True, exist_ok=True)
        (spec_dir / "kernel.json").write_text(json.dumps(_KERNEL_SPEC), encoding="utf-8")

        download_log = td / "download.log"
        # Stub google.colab + point the stub at the real sample. The kernel is
        # started as a child of this process, so it inherits os.environ.
        os.environ["PYTHONPATH"] = str(STUB_DIR) + os.pathsep + os.environ.get("PYTHONPATH", "")
        os.environ["JUPYTER_PATH"] = str(td)  # td/kernels/<name>/kernel.json
        os.environ["AUPHORIA_STUB_UPLOAD"] = str(SAMPLE)
        os.environ["AUPHORIA_STUB_DOWNLOAD_LOG"] = str(download_log)
        os.environ["AUPHORIA_RESULTS_ROOT"] = str(td / "results")  # keep runs in tmp

        nb = nbformat.read(NOTEBOOK, as_version=4)
        client = NotebookClient(
            nb,
            kernel_name="auphoria-test",
            timeout=120,
            resources={"metadata": {"path": str(td)}},
            allow_errors=False,
        )
        executed = client.execute()

        # The download cell must have fired (zip -> stub download), which only
        # happens when a real engine run set _last_results_dir.
        assert download_log.exists(), "google.colab stub download() was never called"
        dl = download_log.read_text(encoding="utf-8").strip()
        assert dl.startswith("downloaded:"), f"unexpected download log: {dl!r}"

        # The run cell must have produced a results folder (cell 5 only runs
        # when _last_results_dir was set by a successful auphoria.run) and the
        # zip must exist somewhere the stub "downloaded" (we also keep it).
        text_out = " ".join(
            out.get("text", "")
            for c in executed.cells
            if c.cell_type == "code"
            for out in c.get("outputs", [])
            if out.get("output_type") == "stream"
        )
        assert "Download started" in text_out, f"download cell never ran: {text_out[:400]}"
        zip_name = dl.split(":", 1)[1]
        assert Path(zip_name).is_file(), f"zip not found at {zip_name}"

        # The zip must contain the report + a results csv.
        import zipfile

        with zipfile.ZipFile(zip_name) as zf:
            names = zf.namelist()
        assert "report.html" in names, f"zip missing report.html: {names}"
        assert any(n.endswith(".csv") for n in names), f"zip missing CSVs: {names}"

        # Every code cell ran without error (client.execute raises otherwise)
        # and the notebook must mention the engine call + privacy notice.
        code = " ".join(
            "".join(c.get("source", [])) for c in executed.cells if c.cell_type == "code"
        )
        assert "auphoria.run(" in code
        assert "https://github.com/mysteriousammw/auphoria" in code
    os.environ.clear()
    os.environ.update(save_env)
