"""File hashing for reproducibility. We hash the raw bytes of the input file
BEFORE any parsing, so the SHA-256 is independent of how columns are read."""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK = 1024 * 1024


def sha256_of_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 of ``path``'s raw bytes."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
