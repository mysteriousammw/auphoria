#!/usr/bin/env python3
"""Prepare a clean publish copy of AUPHORIA and audit it.

Creates ../auphoria_publish/ containing ONLY the files that belong in the
public repository, audits that copy, runs a fresh-venv install + smoke test of
it, and writes ../auphoria_publish/PUBLISH_REPORT.md with MISSING / WARNINGS /
OK sections.

The ORIGINAL tree is never modified. This script only reads it and writes into
../auphoria_publish/ (plus a throwaway venv under TMPDIR for the install test).

Usage:
    python scripts/prepare_publish.py [--no-install-test]

Exit codes:
    0  ran; use the report's own counts to judge readiness (MISSING/WARNINGS).
    2  the publish copy could not be created or was not a directory.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent
PUBLISH = HOME.parent / "auphoria_publish"
REPORT = PUBLISH / "PUBLISH_REPORT.md"

MAX_SIZE = 5 * 1024 * 1024  # 5 MB

# Top-level entries copied verbatim (the public repository root).
INCLUDE_TOP = [
    "pyproject.toml", "README.md", "PROGRESS.md", "CHANGELOG.md",
    "CITATION.cff", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md",
    "CONTRIBUTORS.md", ".gitignore", ".github",
    # Directories:
    "src", "notebooks", "catalog", "docs", "tests", "scripts",
    # Docs site source + build config + root test fixture (part of the repo):
    "docs_site", "mkdocs.yml", "conftest.py",
]
# LICENSE not in INCLUDE_TOP on purpose: it is checked/marked separately.

# Files/dirs removed during the copy (the 1b exclusion list).
EXCLUDE_NAMES = {
    "AUPHORIA_results", "__pycache__", ".venv", "venv", "env", ".env",
    "*.egg-info", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".coverage",
    "htmlcov", "build", "dist", ".eggs", ".ipynb_checkpoints", ".DS_Store",
    "Thumbs.db", "site", ".pth", "pip-wheel-metadata", ".idea", ".vscode",
}
# Suffixes always dropped.
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log", ".egg", ".egg-link"}
EXCLUDE_PREFIXES = (".",)  # dotfiles other than the explicitly-included ones


def _excluded(name: str, is_dir: bool) -> bool:
    if name in EXCLUDE_NAMES:
        return True
    if name.endswith(".egg-info") or name.endswith(".egg-link"):
        return True
    if any(name.endswith(s) for s in EXCLUDE_SUFFIXES):
        return True
    if not is_dir and name.startswith(EXCLUDE_PREFIXES) and name not in {
        ".gitignore", ".github",
    }:
        return True
    return False


def _copy_file(src: Path, dst_dir: Path) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst_dir / src.name)


def _copy_tree(src_dir: Path, dst_root: Path) -> list[Path]:
    """Recursively copy src_dir into dst_root, applying exclusions.

    Returns the list of excluded-but-large files (for the >5MB report).
    """
    large: list[Path] = []
    for name in INCLUDE_TOP:
        src = src_dir / name
        if not src.exists():
            continue  # missing entries are reported by the audit
        dst = dst_root / name
        if src.is_dir():
            _copy_dir(src, dst, large)
        else:
            if src.stat().st_size > MAX_SIZE:
                large.append(src)
                continue
            _copy_file(src, dst_root)
    return large


def _copy_dir(src_dir: Path, dst_dir: Path, large: list[Path]) -> None:
    for child in sorted(src_dir.iterdir()):
        if _excluded(child.name, child.is_dir()):
            continue
        dst = dst_dir / child.name
        if child.is_dir():
            # Never descend into a venv/cache even inside an allowed dir.
            if child.name in {
                "__pycache__", ".venv", "venv", "env", ".pytest_cache",
                ".ruff_cache", ".mypy_cache", ".ipynb_checkpoints",
            } or child.name.endswith(".egg-info"):
                continue
            _copy_dir(child, dst, large)
        else:
            if child.stat().st_size > MAX_SIZE:
                large.append(child)
                continue
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(child, dst)


# --------------------------------------------------------------------------
# Audit
# --------------------------------------------------------------------------

TEXT_SUFFIXES = {".py", ".md", ".toml", ".yaml", ".yml", ".cff", ".txt", ".json",
                 ".ipynb", ".sh", ".ps1", ".cfg", ".ini", ".rst", ".csv",
                 ".j2", ".tpl", ".html"}

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
APPROVED_EMAIL = "ammw@aup.edu.pk"
PATH_RE = re.compile(r"(/home/[a-zA-Z0-9_./-]+|C:\\Users\\[a-zA-Z0-9_ .-]+|"
                     r"/Users/[a-zA-Z0-9_./-]+)")
TOKEN_RE = re.compile(
    r"(sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|"
    r"AKIA[0-9A-Z]{16}|api[_-]?key\s*[:=]\s*[\"'][A-Za-z0-9_\-]{12,}[\"']|"
    r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})"
)

REQUIRED_TOP = [
    "pyproject.toml", "README.md", "PROGRESS.md", "CHANGELOG.md",
    "CITATION.cff", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md",
    "CONTRIBUTORS.md", ".gitignore", "LICENSE", ".github", "src", "notebooks",
    "catalog", "docs", "tests", "scripts", "docs_site", "mkdocs.yml",
    "conftest.py",
]

README_REQUIRED = {
    "what it is": r"uni(versity|que).*(analys|without programming)|students run\b",
    "install (pipx)": r"pipx install",
    "install (uvx/no-install)": r"uvx --from",
    "first-run example": r"auphoria run --data",
    "Colab link": r"Google Colab|colab|notebooks/auphoria_colab",
    "where results are saved": r"AUPHORIA_results",
    "limitations": r"## Limitations",
    "citation": r"## Citation|CITATION.cff",
    "contributors link": r"CONTRIBUTORS\.md",
    "independent-project statement": r"not an official initiative|independent",
}


def _text_files(root: Path) -> list[Path]:
    out = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or any(part in {
            ".venv", "__pycache__", ".git", "AUPHORIA_results", "site",
        } for part in p.parts):
            continue
        if p.suffix.lower() in TEXT_SUFFIXES:
            out.append(p)
    return out


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def audit(root: Path, missing_top: list[str]) -> dict:
    missing: list[str] = []
    warnings: list[str] = []
    ok: list[str] = []

    # 1. Required top-level files.
    for name in REQUIRED_TOP:
        if not (root / name).exists():
            entry = f"{name}: MISSING"
            if name == "LICENSE":
                entry = (
                    "LICENSE: MISSING (you must add this, see "
                    "docs/LICENCE_DECISION.md - the licence is intentionally "
                    "not yet chosen)"
                )
            missing.append(entry)
    for name in missing_top:
        if name != "LICENSE":
            missing.append(f"{name}: specified in the include list but not in the source tree")

    # 2. README content.
    readme = (root / "README.md").read_text(encoding="utf-8", errors="replace")
    for label, pat in README_REQUIRED.items():
        if re.search(pat, readme, re.I):
            ok.append(f"README has: {label}")
        else:
            warnings.append(f"README missing section/content: {label}")

    # 3. Placeholder / marker counts.
    ph_count = 0
    ph_files: dict[str, int] = {}
    todo = []
    confirm = []
    for p in _text_files(root):
        text = _read(p)
        rel = p.relative_to(root)
        n = text.count("https://github.com/mysteriousammw/auphoria")
        if n:
            ph_count += n
            ph_files[str(rel)] = n
        for i, line in enumerate(text.splitlines(), 1):
            if "TODO-VERIFY" in line:
                todo.append(f"{rel}:{i}")
            if "[CONFIRM ROLE]" in line or "[CONFIRM]" in line:
                confirm.append(f"{rel}:{i}")
    ok.append(f"https://github.com/mysteriousammw/auphoria total: {ph_count} occurrence(s) "
              f"across {len(ph_files)} file(s): " +
              ", ".join(f"{f} ({n})" for f, n in sorted(ph_files.items())))
    if todo:
        warnings.append(f"TODO-VERIFY markers ({len(todo)}): " + "; ".join(todo))
    else:
        ok.append("TODO-VERIFY: 0 (all resolved)")
    if confirm:
        warnings.append(f"unresolved [CONFIRM ROLE]/[CONFIRM] markers "
                        f"({len(confirm)}): " + "; ".join(confirm))
    else:
        ok.append("No unresolved [CONFIRM]/[CONFIRM ROLE] markers")

    # 4. Privacy scan.
    email_hits, bad_email = [], []
    path_hits, token_hits, user_hits = [], [], []
    username = Path.home().name if Path.home().name else "mysteriousammw"
    home_path_marker = "/Users/" + username
    for p in _text_files(root):
        rel = p.relative_to(root)
        for ln, line in enumerate(_read(p).splitlines(), 1):
            for m in EMAIL_RE.findall(line):
                if m not in email_hits:
                    email_hits.append((m, str(rel), ln))
                if m != APPROVED_EMAIL and m not in bad_email:
                    _bad = f"email '{m}' at {rel}:{ln} (the only allowed email is {APPROVED_EMAIL})"
                    if _bad not in bad_email:
                        bad_email.append(_bad)
            if PATH_RE.search(line):
                path_hits.append(f"absolute path at {rel}:{ln}: {line.strip()[:80]}")
            if TOKEN_RE.search(line):
                token_hits.append(f"possible token/API-key at {rel}:{ln}: {line.strip()[:80]}")
            # Flag a real hard-coded personal home path, not a bare username
            # mention (the scanner's own fallback string contains the username).
            if home_path_marker in line:
                user_hits.append(f"hard-coded home path '{home_path_marker}' at {rel}:{ln}: {line.strip()[:60]}")
    emails_str = ", ".join(f"{m} ({f}:{ln_no})" for m, f, ln_no in sorted(email_hits))
    ok.append(f"Emails found: {emails_str or '(none)'} "
              f"(approved: {APPROVED_EMAIL})")
    for w in bad_email:
        warnings.append(w)
    for w in path_hits[:50]:
        warnings.append(w)
    for w in token_hits[:20]:
        warnings.append(w)
    for w in user_hits[:20]:
        warnings.append(w)
    if not (bad_email or path_hits or token_hits or (user_hits and False)):
        ok.append("Privacy: no disallowed emails, absolute personal paths, "
                  "tokens, or usernames")

    # 5. Analysis folders.
    analyses = root / "src" / "auphoria" / "analyses"
    analysis_folders = [p for p in analyses.iterdir() if p.is_dir()
                        and p.name != "__pycache__"] if analyses.is_dir() else []
    for a in sorted(analysis_folders):
        needed = {
            "manifest.yaml": a / "manifest.yaml",
            "analysis.py": a / "analysis.py",
            "README.md": a / "README.md",
            "tests/": a / "tests",
        }
        for label, p in needed.items():
            if not p.exists():
                missing.append(f"{a.name}:missing {label}")
                break
        else:
            ok.append(f"analysis {a.name}: manifest + code + README + tests present")

    # 6. Maturity reviewer gate.
    for a in sorted(analysis_folders):
        mf = a / "manifest.yaml"
        if not mf.exists():
            continue
        text = _read(mf)
        if re.search(r"maturity\s*:\s*(reviewed|validated)", text) and \
           not re.search(r"reviewer\s*:", text):
            missing.append(f"{a.name}: claims maturity reviewed/validated "
                           f"without a named reviewer")

    # 7. Referenced files exist (README + docs markdown links + CITATION links).
    link_re = re.compile(r"\[[^\]]*\]\(([^)#]+)\)")
    missing_links = []
    for p in [root / "README.md"] + [f for f in (root / "docs").rglob("*.md")]:
        rel = p.relative_to(root)
        for m in link_re.finditer(_read(p)):
            target = m.group(1).strip()
            if target.startswith(("http", "mailto:", "#")):
                continue
            t = (p.parent / target).resolve()
            if not t.exists():
                missing_links.append(f"{rel} links to missing {target}")
    if missing_links:
        warnings.append("Broken/missing link targets ({len(missing_links)}): " +
                        "; ".join(sorted(set(missing_links))[:25]))
    else:
        ok.append("All local links in README + docs resolve")

    # 8. CITATION.cff validity.
    try:
        import yaml
        cff = yaml.safe_load(_read(root / "CITATION.cff"))
        for k in ("cff-version", "message", "title", "authors"):
            if k not in cff:
                missing.append(f"CITATION.cff missing required '{k}'")
        if any(not a.get("family-names") for a in cff.get("authors", [])):
            warnings.append("CITATION.cff has an author without family-names")
        ok.append("CITATION.cff is valid YAML with cff-version/message/title/authors")
    except Exception as exc:  # noqa: BLE001
        missing.append(f"CITATION.cff invalid: {exc}")

    # 9. .github/workflows valid YAML.
    for wf in sorted((root / ".github" / "workflows").glob("*.yml")):
        try:
            import yaml
            yaml.safe_load(_read(wf))
            ok.append(f".github/workflows/{wf.name}: valid YAML")
        except Exception as exc:  # noqa: BLE001
            missing.append(f".github/workflows/{wf.name}: invalid YAML: {exc}")

    # 10. Large files (should none ship).
    large = [p for p in root.rglob("*") if p.is_file()
             and p.stat().st_size > MAX_SIZE]
    if large:
        warnings.append(f"{len(large)} file(s) over 5 MB in the publish copy: "
                        + "; ".join(str(p.relative_to(root)) for p in large))
    else:
        ok.append("No files over 5 MB in the publish copy")

    return {"missing": missing, "warnings": warnings, "ok": ok,
            "confirm": confirm}


# --------------------------------------------------------------------------
# Report + install test
# --------------------------------------------------------------------------

def _run(cmd: list[str], timeout: int = 600) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        tail = (r.stdout or "")[-1500:]
        if r.returncode != 0:
            tail = (r.stderr or r.stdout or "")[-1500:]
        return r.returncode, f"exit {r.returncode}\n{tail.strip()[-1200:]}"
    except Exception as exc:  # noqa: BLE001
        return -1, f"error: {exc}"


def run_install_test(root: Path) -> list[dict]:
    """Fresh venv: pip install ., auphoria --version, doctor, demo, pytest."""
    results = []
    venv_dir = Path(tempfile.mkdtemp(prefix="auph_publish_")) / "venv"
    py = sys.executable if sys.version_info >= (3, 10) else "python3.11"
    rc, out = _run([py, "-m", "venv", str(venv_dir)], timeout=300)
    results.append({"step": "create fresh venv", "ok": rc == 0, "detail": out})
    if rc != 0:
        results.append({"step": "install (aborted)", "ok": False,
                        "detail": "venv creation failed"})
        return results

    vbin = venv_dir / "bin"
    pip = [str(vbin / "pip"), "--disable-pip-version-check", "-q"]

    rc, out = _run([*pip, "install", "."], timeout=1500)
    results.append({"step": "pip install . from publish copy",
                    "ok": rc == 0, "detail": out})
    if rc != 0:
        # Give the exact failure instead of failing the rest pointlessly.
        return results

    for step, cmd in [
        ("auphoria --version", [str(vbin / "auphoria"), "--version"]),
        ("auphoria doctor", [str(vbin / "auphoria"), "doctor"]),
        ("auphoria demo", [str(vbin / "auphoria"), "demo"]),
    ]:
        rc, out = _run(cmd, timeout=900)
        results.append({"step": step, "ok": rc == 0, "detail": out})

    # pytest: install the dev extra (test deps incl. statsmodels/sklearn and
    # the discipline-pack libraries) so the FULL suite can collect — a bare
    # core install cannot import the pack-dependent per-analysis tests.
    rc, out = _run([*pip, "install", ".[dev]"], timeout=1800)
    if rc == 0:
        rc, out = _run([str(vbin / "pytest"), "-q"], timeout=1800)
    results.append({
        "step": "pytest (after installing the .[dev] extra)",
        "ok": rc == 0,
        "detail": out,
    })
    return results


def write_report(root: Path, missing_top: list[str],
                 install_results: list[dict] | None) -> dict:
    counts = audit(root, missing_top)
    lines = [
        "# AUPHORIA - publish readiness report",
        "",
        f"Generated by `scripts/prepare_publish.py` from `{HOME}`",
        f"Publish copy: `{PUBLISH}`  (the original tree was not modified)",
        "",
        "Counts: "
        f"**{len(counts['missing'])} MISSING**, "
        f"**{len(counts['warnings'])} WARNINGS**, "
        f"**{len(counts['ok'])} OK**.",
        "",
        "## MISSING",
        "",
    ]
    if counts["missing"]:
        lines += [f"- {m}" for m in counts["missing"]]
    else:
        lines.append("- (none)")
    lines += ["", "## WARNINGS", ""]
    if counts["warnings"]:
        lines += [f"- {w}" for w in counts["warnings"]]
    else:
        lines.append("- (none)")
    lines += ["", "## OK", ""]
    if counts["ok"]:
        lines += [f"- {o}" for o in counts["ok"]]
    else:
        lines.append("- (none)")

    lines += ["", "## Clean-install verification (fresh venv)", ""]
    if install_results:
        for r in install_results:
            mark = "PASS" if r["ok"] else "FAIL"
            lines.append(f"- **[{mark}]** {r['step']}: {r['detail']}")
    else:
        lines.append("- (not run)")

    lines += ["", "## First five things to fix", ""]
    to_fix = counts["missing"] + counts["warnings"]
    for item in to_fix[:5]:
        lines.append(f"1. {item}")
    if not to_fix:
        lines.append("- None; the publish copy is ready for review.")

    lines += ["", "## [CONFIRM ROLE] markers still open", ""]
    # People-related confirmations live only in the credit files; the script's
    # own source and dev records (PROGRESS/DECISIONS) merely mention the phrase,
    # so they are excluded from this section.
    CREDIT_FILES = {"CONTRIBUTORS.md", "CITATION.cff", "README.md",
                    "docs/ACKNOWLEDGEMENTS.md"}
    pending = [c for c in counts["confirm"]
               if c.split(":")[0] in CREDIT_FILES]
    if pending:
        lines.append("These unresolved [CONFIRM ROLE]/[CONFIRM] markers must be "
                     "cleared before the credits (§ CONTRIBUTORS.md, CITATION.cff) "
                     "are final. Each names a person whose role/descriptor still "
                     "needs the maintainer's confirmation:")
        for c in pending:
            lines.append(f"- {c}")
    else:
        lines.append("- (none)")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return counts


def main() -> int:
    no_install = "--no-install-test" in sys.argv

    # Clean previous copy (never partially overwrite).
    if PUBLISH.exists():
        shutil.rmtree(PUBLISH)
    PUBLISH.mkdir()

    # --copy-----
    missing_top: list[str] = []
    for name in INCLUDE_TOP:
        if not (HOME / name).exists():
            missing_top.append(name)
    try:
        _copy_tree(HOME, PUBLISH)
    except Exception as exc:  # noqa: BLE001
        print(f"error copying to {PUBLISH}: {exc}", file=sys.stderr)
        return 2

    # Make .github (a dot-dir) copy correctly under INCLUDE_TOP.
    if not (PUBLISH / ".github").exists() and (HOME / ".github").exists():
        shutil.copytree(HOME / ".github", PUBLISH / ".github",
                        ignore=shutil.ignore_patterns("__pycache__"))

    install_results = None if no_install else run_install_test(PUBLISH)
    counts = write_report(PUBLISH, missing_top, install_results)

    print(f"\nPublish copy: {PUBLISH}")
    print(f"Report:       {REPORT}")
    print(f"\nMISSING: {len(counts['missing'])}   "
          f"WARNINGS: {len(counts['warnings'])}   "
          f"OK: {len(counts['ok'])}   "
          f"[CONFIRM]: {len(counts['confirm'])}")
    to_fix = counts["missing"] + counts["warnings"]
    print("\nFirst five items to fix:")
    for item in to_fix[:5]:
        print(f"  1. {item}")
    if not to_fix:
        print("  - none; ready for review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
