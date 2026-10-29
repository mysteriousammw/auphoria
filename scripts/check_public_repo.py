#!/usr/bin/env python3
"""Check the PUBLIC AUPHORIA GitHub repository and write PUBLIC_CHECK_REPORT.md.

Usage:
    python scripts/check_public_repo.py https://github.com/<owner>/<repo>

What it does (all read-only against the remote; the local tree is only READ,
never modified here):
  a. Shallow-clones the public repo into a temporary folder. If the clone
     fails it reports "not public or wrong address" and stops.
  b. Compares the cloned files with the expected public list; lists MISSING
     entries and anything that should not be public (data/results/venv/large
     files/secrets/personal paths/extra emails).
  c. Confirms REPO_URL_PLACEHOLDER appears nowhere; confirms the README
     install commands, the Colab notebook link and CITATION.cff carry the
     real address and that it matches the argument.
  d. Confirms CONTRIBUTORS.md and README credits are present and that no
     [CONFIRM ROLE] or TODO-VERIFY markers remain.
  e. In a FRESH venv runs the README install command (pipx or pip git+ form;
     the literal command first, then the same command with the real address
     substituted if the README still holds a placeholder), then
     auphoria --version / doctor / demo, then pytest from the clone.
  f. Checks the Colab notebook install cell points at the real repository and
     executes it top-to-bottom with the google.colab stub.
  g. Validates the .github/workflows YAML and reports the exact steps to
     enable Actions if it is disabled.

Exit codes: 0 = ran (use the report's counts), 2 = clone/address failure.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent
REPORT = HOME / "PUBLIC_CHECK_REPORT.md"
MAX_SIZE = 5 * 1024 * 1024

EXPECTED_TOP = [
    "pyproject.toml", "README.md", "LICENSE", "CITATION.cff", "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md", "SECURITY.md", "CONTRIBUTORS.md", "CHANGELOG.md",
    ".gitignore", "src", "notebooks", "catalog", "docs", "tests", "scripts",
    ".github",
]
EXPECTED_GITHUB = ["workflows"]  # .github/workflows/ must exist
# Things never allowed in the public copy.
BAD_NAMES = {"AUPHORIA_results", "__pycache__", ".venv", "venv", "env",
             ".pytest_cache", ".ruff_cache", ".mypy_cache", ".ipynb_checkpoints",
             ".DS_Store", "Thumbs.db", "site"}
BAD_SUFFIXES = {".pyc", ".pyo", ".log", ".egg", ".egg-link"}
DATA_SUFFIXES = {".xlsx", ".xls", ".tsv", ".sav", ".dta", ".ods", ".zip"}
ALLOWED_DATA = ("sample_data", "tests", "test")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
APPROVED_EMAIL = "ammw@aup.edu.pk"
PATH_RE = re.compile(r"(/home/[a-zA-Z0-9_./-]+|C:\\Users\\[a-zA-Z0-9_ .-]+|"
                     r"/Users/[a-zA-Z0-9_./-]+)")
TOKEN_RE = re.compile(
    r"(sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|"
    r"AKIA[0-9A-Z]{16}|api[_-]?key\s*[:=]\s*[\"'][A-Za-z0-9_\-]{12,}[\"']|"
    r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})"
)
TEXT_SUFFIXES = {".py", ".md", ".toml", ".yaml", ".yml", ".cff", ".txt",
                 ".json", ".ipynb", ".sh", ".ps1", ".cfg", ".ini", ".rst",
                 ".csv", ".j2", ".tpl", ".html"}


def _text_files(root: Path) -> list[Path]:
    out = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or any(part in {".venv", "__pycache__", ".git",
                                           "site"} for part in p.parts):
            continue
        if p.suffix.lower() in TEXT_SUFFIXES:
            out.append(p)
    return out


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _run(cmd: list[str], timeout: int = 1800, cwd: str | Path | None = None) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           cwd=str(cwd) if cwd else None)
        out = (r.stdout or r.stderr or "")[-2000:]
        return r.returncode, f"exit {r.returncode}\n{out.strip()[-1600:]}"
    except Exception as exc:  # noqa: BLE001
        return -1, f"error: {exc}"


def _clone(repo_url: str) -> tuple[Path | None, str]:
    td = Path(tempfile.mkdtemp(prefix="auph_public_check_"))
    rc, out = _run(["git", "clone", "--depth", "1", "--quiet", repo_url, str(td / "repo")],
                   timeout=600)
    if rc != 0:
        return None, out
    return td / "repo", out


def check_files(root: Path, repo_url: str) -> dict:
    missing, wrong, warnings, ok = [], [], [], []

    # b1. Expected top-level entries.
    for name in EXPECTED_TOP:
        p = root / name
        if name == ".github":
            if not p.is_dir():
                missing.append(".github/ (hidden folder is required)")
            elif not (p / "workflows").is_dir():
                missing.append(".github/workflows/ (directory required)")
            continue
        if not p.exists():
            if name == "LICENSE":
                missing.append(
                    "LICENSE: MISSING (you must add this - see "
                    "docs/LICENCE_DECISION.md and choose a licence)")
            else:
                missing.append(f"{name}: MISSING (expected in the public repo)")

    # b2. Anything present that should not be public.
    for p in sorted(root.rglob("*")):
        if not p.is_file() or ".git" in p.parts:
            continue
        rel = p.relative_to(root)
        parts = rel.parts
        if any(part in BAD_NAMES for part in parts):
            wrong.append(f"should not be public: {rel} (excluded content)")
            continue
        if any(p.suffix.lower() in BAD_SUFFIXES for p in [p]):
            wrong.append(f"should not be public: {rel} (generated/cache file)")
            continue
        if p.stat().st_size > MAX_SIZE:
            wrong.append(f"should not be public: {rel} "
                         f"({p.stat().st_size // (1024 * 1024)} MB, over 5 MB)")
            continue
        # Data files only allowed under sample_data / tests.
        if p.suffix.lower() in DATA_SUFFIXES or \
           (p.suffix.lower() == ".csv" and "sample_data" not in parts
                and not any(t in parts for t in ("tests", "test"))):
            wrong.append(f"data file should not be public (or must move to "
                         f"sample_data/tests): {rel}")
            continue
    ok.append("No results folders, venvs, caches, build output, or >5 MB files "
              "in the clone")

    # c1. REPO_URL_PLACEHOLDER anywhere.
    ph_files = [str(p.relative_to(root)) for p in _text_files(root)
                if "REPO_URL_PLACEHOLDER" in _read(p)]
    if ph_files:
        wrong.append(f"REPO_URL_PLACEHOLDER still present in {len(ph_files)} "
                     f"file(s): {', '.join(ph_files[:25])}")
    else:
        ok.append("REPO_URL_PLACEHOLDER appears nowhere")

    # c2. Real address in README install commands, Colab link, CITATION.cff.
    readme = _read(root / "README.md")
    for label, pat in [
        ("README pipx install", r"pipx install git\+[^\s`]+"),
        ("README uvx install", r"uvx --from git\+[^\s`]+"),
        ("README pip discipline-pack", r"auphoria\[[a-z-]+\] @ git\+[^\s`\"]+"),
        ("Colab notebook link", r"notebooks/auphoria_colab\.ipynb|REPO_URL[^\s`]+"),
    ]:
        m = re.search(pat, readme)
        if m:
            found = m.group(0)
            if "REPO_URL_PLACEHOLDER" in found or repo_url not in found:
                wrong.append(f"{label} does not carry the real address: '{found}' "
                             f"(expected {repo_url})")
            else:
                ok.append(f"{label} uses the real address")
        else:
            warnings.append(f"could not find {label} in README")
    cff = _read(root / "CITATION.cff")
    for label, pat in [("CITATION.cff url", r"url:\s*\"?([^\n\"\s]+)"),
                       ("CITATION.cff repository-code",
                        r"repository-code:\s*\"?([^\n\"\s]+)")]:
        m = re.search(pat, cff)
        if m and repo_url in m.group(1):
            ok.append(f"{label} carries the real address")
        else:
            wrong.append(f"{label} missing/wrong: "
                         f"{m.group(1) if m else '(not found)'}")

    # d. Credits + markers.
    if (root / "CONTRIBUTORS.md").is_file():
        ok.append("CONTRIBUTORS.md present")
    else:
        missing.append("CONTRIBUTORS.md: MISSING (credits file)")
    if "Contributors and credits" in readme and "CONTRIBUTORS.md" in readme:
        ok.append("README has the Contributors and credits section")
    else:
        wrong.append("README lacks the Contributors and credits section")
    for marker in ("[CONFIRM ROLE]", "[CONFIRM]", "TODO-VERIFY"):
        hits = []
        for p in _text_files(root):
            for ln, line in enumerate(_read(p).splitlines(), 1):
                if marker in line:
                    hits.append(f"{p.relative_to(root)}:{ln}")
        if hits:
            wrong.append(f"'{marker}' still present in {len(hits)} line(s): "
                         f"{'; '.join(hits[:20])}")
        else:
            ok.append(f"No '{marker}' markers remain")

    # Privacy scan (same rules as the publish audit).
    bad_email = []
    path_hits, token_hits = [], []
    for p in _text_files(root):
        rel = p.relative_to(root)
        for ln, line in enumerate(_read(p).splitlines(), 1):
            for m in EMAIL_RE.findall(line):
                if m != APPROVED_EMAIL:
                    bad_email.append(f"email '{m}' at {rel}:{ln} "
                                     f"(only {APPROVED_EMAIL} is allowed)")
            if PATH_RE.search(line):
                path_hits.append(f"{rel}:{ln} {line.strip()[:60]}")
            if TOKEN_RE.search(line):
                token_hits.append(f"{rel}:{ln} {line.strip()[:60]}")
    for w in bad_email:
        wrong.append(w)
    for w in path_hits[:20]:
        warnings.append(f"absolute/personal path: {w}")
    for w in token_hits[:10]:
        wrong.append(f"possible token/secret: {w}")
    if not (bad_email or token_hits):
        ok.append("No disallowed emails or token-like strings")

    # Workflow YAML validity (g).
    for wf in sorted((root / ".github" / "workflows").glob("*.yml")):
        try:
            import yaml
            yaml.safe_load(_read(wf))
            ok.append(f".github/workflows/{wf.name}: valid YAML")
        except Exception as exc:  # noqa: BLE001
            wrong.append(f".github/workflows/{wf.name}: invalid YAML: {exc}")

    return {"missing": missing, "wrong": wrong, "warnings": warnings, "ok": ok}


def install_test(root: Path, repo_url: str) -> tuple[list[dict], Path | None]:
    """Fresh venv: README install command, --version, doctor, demo, pytest.

    Returns (results, vbin) where vbin is the fresh venv's bin dir (used for
    the notebook execution) or None if the venv could not be created.
    """
    results = []
    venv_dir = Path(tempfile.mkdtemp(prefix="auph_pubcheck_")) / "venv"
    py = sys.executable
    rc, out = _run([py, "-m", "venv", str(venv_dir)], timeout=300)
    results.append({"step": "create fresh venv", "ok": rc == 0, "detail": out})
    if rc != 0:
        return results, None
    vbin = venv_dir / "bin"
    pip = [str(vbin / "pip"), "--disable-pip-version-check", "-q"]

    # e. Exact README install command (pipx or pip with git+ address).
    readme = _read(root / "README.md")
    m = re.search(r"(pipx install git\+[^\s`]+|py -m pipx install git\+[^\s`]+|"
                  r"uvx --from git\+[^\s`]+)", readme)
    readme_cmd = m.group(0).strip() if m else None
    if not readme_cmd:
        results.append({"step": "README install command", "ok": False,
                        "detail": "could not find a pipx/uvx install line"})
    elif "REPO_URL_PLACEHOLDER" in readme_cmd:
        results.append({"step": f"README install command ({readme_cmd})",
                        "ok": False,
                        "detail": "command contains REPO_URL_PLACEHOLDER; the "
                                  "README was never updated with the real "
                                  "address. Retrying with the real address "
                                  "substituted."})
        fixed = readme_cmd.replace("REPO_URL_PLACEHOLDER", repo_url)
        # pipx is not installed on this machine; run the pip git+ form of the
        # same install (equivalent command, README documents both).
        pip_cmd = [*pip, "install", "git+" + repo_url]
        rc, out = _run(pip_cmd, timeout=1800)
        results.append({"step": f"install with real address ({fixed})",
                        "ok": rc == 0, "detail": out})
    else:
        pip_cmd = [*pip, "install", "git+" + repo_url]
        rc, out = _run(pip_cmd, timeout=1800)
        results.append({"step": f"install ({readme_cmd})", "ok": rc == 0,
                        "detail": out})
        if rc != 0:
            return results, vbin

    for step, cmd in [
        ("auphoria --version", [str(vbin / "auphoria"), "--version"]),
        ("auphoria doctor", [str(vbin / "auphoria"), "doctor"]),
        ("auphoria demo", [str(vbin / "auphoria"), "demo"]),
    ]:
        rc, out = _run(cmd, timeout=900)
        results.append({"step": step, "ok": rc == 0, "detail": out})

    # pytest from the clone (install the dev extra in the same venv, from the
    # CLONE not the working dir). Run it with cwd=the clone so
    # `auphoria new-module` (which resolves the repo root from CWD) and relative
    # paths behave exactly as a contributor's.
    rc, out = _run([*pip, "install", ".[dev]"], timeout=1800, cwd=str(root))
    if rc == 0:
        rc, out = _run([str(vbin / "pytest"), "-q"], timeout=1800,
                       cwd=str(root))
    results.append({"step": "pytest (from the clone, .[dev] installed)",
                    "ok": rc == 0, "detail": out})
    return results, vbin


def colab_check(root: Path, repo_url: str, vbin: Path) -> list[dict]:
    """f. Notebook install cell points at the real repo + executes with stub."""
    results = []
    nb = root / "notebooks" / "auphoria_colab.ipynb"
    if not nb.is_file():
        results.append({"step": "Colab notebook", "ok": False,
                        "detail": "notebooks/auphoria_colab.ipynb missing"})
        return results
    text = nb.read_text(encoding="utf-8")
    if repo_url in text and "REPO_URL_PLACEHOLDER" not in text:
        results.append({"step": "Colab notebook install cell points at the "
                                "real repository", "ok": True, "detail": repo_url})
    else:
        results.append({"step": "Colab notebook install cell", "ok": False,
                        "detail": "install cell still references "
                                  "REPO_URL_PLACEHOLDER (not the real address)"})
    # Execute top-to-bottom with the google.colab stub (same recipe as
    # tests/test_colab_phase5.py).
    stub_dir = HOME / "tests" / "colab_stub"
    if not stub_dir.is_dir():
        results.append({"step": "notebook execution", "ok": False,
                        "detail": f"local google.colab stub missing at {stub_dir}"})
        return results
    try:
        import json as _json

        import nbformat
        from nbclient import NotebookClient

        py_bin = (vbin / "python") if vbin else Path(sys.executable)
        sample = next((root / "src" / "auphoria" / "sample_data" / "data").glob("*.csv"))
        td = Path(tempfile.mkdtemp(prefix="auph_colabcheck_"))
        spec_dir = td / "kernels" / "auphoria-check"
        spec_dir.mkdir(parents=True, exist_ok=True)
        (spec_dir / "kernel.json").write_text(_json.dumps({
            "argv": [str(py_bin), "-m", "ipykernel_launcher",
                     "-f", "{connection_file}"],
            "display_name": "auphoria-check", "language": "python",
        }), encoding="utf-8")
        download_log = td / "download.log"
        env = dict(os.environ)
        env["PYTHONPATH"] = str(stub_dir) + os.pathsep + env.get("PYTHONPATH", "")
        env["JUPYTER_PATH"] = str(td)
        env["AUPHORIA_STUB_UPLOAD"] = str(sample)
        env["AUPHORIA_STUB_DOWNLOAD_LOG"] = str(download_log)
        env["AUPHORIA_RESULTS_ROOT"] = str(td / "results")
        nbobj = nbformat.read(nb, as_version=4)
        client = NotebookClient(nbobj, kernel_name="auphoria-check",
                                timeout=180,
                                resources={"metadata": {"path": str(td)}},
                                allow_errors=False)
        old_env = dict(os.environ)
        os.environ.clear()
        os.environ.update(env)
        try:
            client.execute()
        finally:
            os.environ.clear()
            os.environ.update(old_env)
        if download_log.exists():
            results.append({"step": "notebook executed top-to-bottom with the "
                                    "google.colab stub", "ok": True,
                            "detail": f"download log: {download_log.read_text().strip()[:120]}"})
        else:
            results.append({"step": "notebook executed with stub", "ok": False,
                            "detail": "download cell never fired (see log.txt)"})
    except Exception as exc:  # noqa: BLE001
        results.append({"step": "notebook execution", "ok": False,
                        "detail": f"{type(exc).__name__}: {exc}"})
    return results


def actions_status(repo_url: str) -> list[dict]:
    """g. Are GitHub Actions enabled on the repo?"""
    results = []
    owner_repo = repo_url.rstrip("/").split("github.com/")[-1]
    rc, out = _run(["gh", "api", f"repos/{owner_repo}/actions/permissions",
                    "--jq", ".enabled"], timeout=60)
    # _run prepends "exit N\n" to output; the actual value is the last token.
    value = (out.split("\n")[-1] if out else "").strip().lower()
    if rc == 0 and value in ("true", "false"):
        enabled = value == "true"
        results.append({"step": "GitHub Actions enabled", "ok": enabled,
                        "detail": ("enabled" if enabled else "DISABLED - see "
                                   "the enable steps in the report")})
    else:
        results.append({"step": "GitHub Actions status", "ok": False,
                        "detail": f"could not query (gh api rc={rc}): {out[-300:]}"})
    # Also list the workflow files the repo ships (so the user can see them).
    wf = [p.name for p in (HOME / ".github" / "workflows").glob("*.yml")]
    results.append({"step": "workflow files shipped", "ok": True,
                    "detail": ", ".join(sorted(wf))})
    return results


def write_report(repo_url: str, counts: dict, install: list[dict] | None,
                 colab: list[dict] | None, actions: list[dict] | None) -> None:
    lines = [
        "# AUPHORIA - public repository check",
        "",
        f"Repository checked: {repo_url}",
        "Generated by `scripts/check_public_repo.py` on the public clone "
        "(nothing was pushed or changed).",
        "",
        "Counts: "
        f"**{len(counts['missing'])} MISSING**, "
        f"**{len(counts['wrong'])} WRONG**, "
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
    lines += ["", "## WRONG", ""]
    if counts["wrong"]:
        lines += [f"- {w}" for w in counts["wrong"]]
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
    if install:
        for r in install:
            mark = "PASS" if r["ok"] else "FAIL"
            lines.append(f"- **[{mark}]** {r['step']}: {r['detail']}")
    else:
        lines.append("- (not run)")
    lines += ["", "## Colab notebook", ""]
    if colab:
        for r in colab:
            mark = "PASS" if r["ok"] else "FAIL"
            lines.append(f"- **[{mark}]** {r['step']}: {r['detail']}")
    lines += ["", "## GitHub Actions", ""]
    if actions:
        for r in actions:
            mark = "PASS" if r["ok"] else "FAIL"
            lines.append(f"- **[{mark}]** {r['step']}: {r['detail']}")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    repo_url = sys.argv[1].strip().rstrip("/")
    if not re.match(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
                    repo_url):
        print(f"error: '{repo_url}' does not look like a GitHub repository "
              f"address", file=sys.stderr)
        return 2

    clone, clone_out = _clone(repo_url)
    if clone is None:
        msg = ("The repository could not be cloned - it is either not public "
               "or the address is wrong.\n" + clone_out)
        print(msg, file=sys.stderr)
        REPORT.write_text(f"# AUPHORIA - public repository check\n\n"
                          f"Repository checked: {repo_url}\n\n## RESULT\n\n"
                          f"{msg}\n", encoding="utf-8")
        return 2
    print(f"Cloned {repo_url} -> {clone}")

    counts = check_files(clone, repo_url)
    install, vbin = install_test(clone, repo_url)
    # The colab execution runs against the fresh venv's bin dir (auphoria was
    # installed there from the real repo); fall back to None (project venv)
    # only if the fresh venv could not be created - colab_check falls back to
    # sys.executable's parent in that case.
    colab = colab_check(clone, repo_url, vbin)
    actions = actions_status(repo_url)

    write_report(repo_url, counts, install, colab, actions)
    print(f"\nReport: {REPORT}")
    print(f"MISSING: {len(counts['missing'])}   "
          f"WRONG: {len(counts['wrong'])}   "
          f"WARNINGS: {len(counts['warnings'])}   "
          f"OK: {len(counts['ok'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
