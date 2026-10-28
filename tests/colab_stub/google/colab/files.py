"""Fake google.colab.files for local notebook tests.

``import google.colab.files`` resolves here when ``tests/colab_stub`` is on
the kernel PYTHONPATH. Mirrors the two AUPHORIA calls as module-level
functions (exactly how the real google.colab.files exposes them).

    upload()    -> {'<name>': bytes}  (bytes sourced from AUPHORIA_STUB_UPLOAD)
    download(p) -> no-op, records the path to AUPHORIA_STUB_DOWNLOAD_LOG
"""

from __future__ import annotations

import os
from pathlib import Path


def upload() -> dict[str, bytes]:
    src = Path(os.environ.get("AUPHORIA_STUB_UPLOAD", ""))
    if not src or not src.is_file():
        return {}
    return {src.name: src.read_bytes()}


def download(path: str) -> None:
    log = os.environ.get("AUPHORIA_STUB_DOWNLOAD_LOG")
    if log:
        Path(log).write_text(f"downloaded:{path}\n", encoding="utf-8")
