"""Tests for scripts/set_repo_url.py and the interactive menu (thin front end)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "set_repo_url.py"


def _make_fake_trees(tmp_path: Path):
    """Two tiny trees: one with the placeholder, one without; never the script."""
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.txt").write_text("pip install REPO_URL_PLACEHOLDER@main")
    (tmp_path / "sub" / ".git").mkdir()           # skippable dir
    (tmp_path / "sub" / ".git" / "c.txt").write_text("REPO_URL_PLACEHOLDER")
    (tmp_path / "b.md").write_text("no placeholder here")
    return tmp_path


def _run_script(args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True
    )


# ---- independent of the fake-tree trickery, test on a copied temp repo ------
def test_replace_in_tree_and_check(tmp_path: Path):
    # Import the module directly.
    import importlib.util

    spec = importlib.util.spec_from_file_location("set_repo_url", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    tree = _make_fake_trees(tmp_path)
    # --check path (no writes)
    changes = mod.replace_in_tree(tree, "https://github.com/o/r", check_only=True)
    assert len(changes) == 1  # only the real text file; .git and b.md excluded
    # Real replacement
    changes = mod.replace_in_tree(tree, "https://github.com/o/r")
    assert len(changes) == 1
    assert (tmp_path / "sub" / "a.txt").read_text() == \
        "pip install https://github.com/o/r@main"
    # Now nothing left
    assert mod.replace_in_tree(tree, "https://github.com/o/r") == []


def test_set_repo_url_script_rejects_bad_url(tmp_path: Path):
    out = _run_script(["not-a-url"])
    assert out.returncode == 1
    assert "GitHub repository" in out.stderr


def test_set_repo_url_script_rejects_non_github_url(tmp_path: Path):
    """A non-GitHub address must be refused (e.g. a typo'd or GitLab URL)."""
    for bad in ["https://example.org/org/repo", "https://gitlab.com/org/repo",
                "https://github.com/only-org", "http://github.com/org/repo"]:
        out = _run_script([bad])
        assert out.returncode == 1, bad
        assert "GitHub repository" in out.stderr, bad


def test_set_repo_url_script_accepts_github_url(tmp_path: Path):
    out = _run_script(["--check", "https://github.com/org/repo"])
    # Reaches into the tree (exit 0 = up to date; 2 = found placeholders) and
    # is never refused, which is what this test guards.
    assert out.returncode in (0, 2)
    assert "GitHub repository" not in out.stderr


# ------------------------------------------------------------------ menu
def test_interactive_menu_runs_ttest_end_to_end(monkeypatch, capsys, sample_csv, tmp_path):
    """Drive the interactive flow with canned answers; it must call the engine."""
    from auphoria.core import engine as engine_mod

    monkeypatch.setattr(engine_mod, "DEFAULT_RESULTS_ROOT", tmp_path)

    # Inputs: data path, then confirm every column type (just Enter = accept),
    # then confirm every column role (Enter = accept suggestion), then pick
    # ttest (its alphabetical menu index is derived so a new analysis never
    # renumbers it), then outcome col (1), group col (1), then params (blank
    # for all), then confirm run, then answer "n" to the open-folder prompt.
    from auphoria.adapters.adapters import read_data_frame
    from auphoria.advisor.advisor import profile_data_frame
    from auphoria.core.fitting import analyses_that_fit

    _df, _ = read_data_frame(sample_csv)
    _kinds = {c.kind for c in profile_data_frame(_df).columns}
    _labels = {"numeric": "numeric", "categorical": "categorical", "datetime": "datetime"}
    _menu = sorted(analyses_that_fit([_labels.get(k, k) for k in _kinds]))
    _ttest_idx = str(_menu.index("ttest") + 1)

    inputs = [
        str(sample_csv),   # data path
        "", "", "", "",    # confirm 4 column kinds
        "", "", "", "",    # confirm 4 column roles
        "",                # skip advisor question (blank)
        _ttest_idx,        # choose ttest from the (alphabetical) menu
        "1",               # outcome = height_cm
        "1",               # group = treatment
        "",                # alpha default
        "",                # equal_var default
        "",                # tail default
        "",                # confirm the run (Enter = yes)
        "n",               # don't open folder
    ]
    captured: list[str] = []
    it = iter(inputs)

    def fake_input(prompt=""):
        captured.append(prompt)
        return next(it, "")

    monkeypatch.setattr("builtins.input", fake_input)
    # Do not actually open a browser.
    monkeypatch.setattr("webbrowser.open", lambda *a, **k: None)

    from auphoria.cli.menu import run_interactive

    run_interactive(expert=False)
    out = capsys.readouterr().out
    assert "AUPHORIA" in out
    assert "Results are saved" in out or "results_dir" in out
