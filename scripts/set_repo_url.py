#!/usr/bin/env python3
"""Replace the REPO_URL_PLACEHOLDER literal with the real repository URL.

AUPHORIA is developed without a fixed repository address, so every place a
real URL is needed (README install commands, the Colab notebook, pyproject
URLs, CITATION.cff) uses the literal string REPO_URL_PLACEHOLDER. After the
repository is uploaded to GitHub, run this once to substitute the address:

    python scripts/set_repo_url.py https://github.com/<org>/<repo>

It scans every plain-text file under the repository root (respecting
.gitignore-style exclusions plus common tool directories), replaces every
occurrence of the placeholder, and reports what it changed.

It REFUSES to run unless the argument looks like a GitHub repository address
(https://github.com/<org>/<repo>), so a typo cannot silently mis-route the
install commands in the README.

Usage:
    python scripts/set_repo_url.py <github-url>
    python scripts/set_repo_url.py --check <github-url>   # dry run: only report

Exit codes:
    0  all good (or, with --check, everything already/found to be replaced)
    1  no URL given or invalid
    2  --check found a mismatch
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PLACEHOLDER = "REPO_URL_PLACEHOLDER"

# A GitHub repository address: https://github.com/<org>/<repo>[/...]
_GITHUB_RE = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(/.*)?$")

# Directories we never touch (git, caches, build output, virtualenvs).
SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "env", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "build", "dist", ".eggs", ".idea", ".vscode",
    "node_modules", "htmlcov", "AUPHORIA_results", ".hermes",
}

# Text extensions we always inspect; any other file is only inspected if it
# decodes cleanly as UTF-8 text.
TEXT_SUFFIXES = {
    ".py", ".md", ".toml", ".yaml", ".yml", ".cff", ".txt", ".json",
    ".ipynb", ".sh", ".ps1", ".cfg", ".ini", ".rst", ".csv", ".svg", ".html",
}


def _is_skippable(path: Path) -> bool:
    if str(path).endswith(".egg-info"):
        return True
    if path.name in SKIP_DIRS and path.is_dir():
        return True
    # Skip this script itself so we never corrupt the tool.
    if path.name == "set_repo_url.py" and path.parent.name == "scripts":
        return True
    return False


def _is_text(path: Path) -> bool:
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    try:
        path.read_bytes().decode("utf-8")
        return True
    except (UnicodeDecodeError, OSError):
        return False


def collect_files(root: Path) -> list[Path]:
    """Return every candidate file under ``root`` that may contain the placeholder."""
    out: list[Path] = []
    for child in sorted(root.rglob("*")):
        if any(p in SKIP_DIRS for p in child.parts):
            continue
        if not child.is_file():
            continue
        if child.name == "set_repo_url.py":
            continue
        if _is_text(child):
            out.append(child)
    return out


def replace_in_tree(root: Path, url: str, check_only: bool = False) -> list[str]:
    replaced: list[str] = []
    for path in collect_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if PLACEHOLDER not in text:
            continue
        if check_only:
            replaced.append(f"[would change] {path}")
            continue
        new_text = text.replace(PLACEHOLDER, url)
        path.write_text(new_text, encoding="utf-8")
        replaced.append(f"[changed] {path}")
    return replaced


def is_github_url(url: str) -> bool:
    """True iff ``url`` looks like a GitHub repository address."""
    return bool(_GITHUB_RE.match(url))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/set_repo_url.py",
        description="Replace REPO_URL_PLACEHOLDER with the real repository URL.",
    )
    parser.add_argument("url", help="GitHub repository URL, e.g. https://github.com/org/repo")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Dry run: report files that would change without writing anything.",
    )
    args = parser.parse_args(argv)

    url = args.url.strip().rstrip("/")
    if not is_github_url(url):
        print(
            "error: the address does not look like a GitHub repository.\n"
            f"  got:  {url}\n"
            "  want: https://github.com/<org>/<repo>",
            file=sys.stderr,
        )
        return 1

    root = Path(__file__).resolve().parent.parent
    changes = replace_in_tree(root, url, check_only=args.check)

    if args.check:
        if changes:
            print(f"Would replace '{PLACEHOLDER}' in {len(changes)} file(s):")
            for c in changes:
                print(f"  {c}")
            return 2
        print(f"No '{PLACEHOLDER}' occurrences found. Repository URL is up to date.")
        return 0

    if changes:
        print(f"Replaced '{PLACEHOLDER}' with '{url}' in {len(changes)} file(s):")
        for c in changes:
            print(f"  {c}")
    else:
        print(f"No '{PLACEHOLDER}' occurrences found. Nothing to do.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
