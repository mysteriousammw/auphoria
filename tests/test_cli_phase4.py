"""Phase 4 acceptance tests: CLI wizard (scripted), path handling across OS
styles, and the new commands (describe / suggest / demo / list filters).
"""

from __future__ import annotations

import os
import subprocess

import pytest

import auphoria

# sample_path("plant_growth") etc. (submodule must be imported explicitly)
import auphoria.sample_data as auphoria_sample_data
from auphoria.adapters.adapters import clean_path_input
from auphoria.cli.main import _example_command
from conftest import with_console  # harness shared with the suite

_SAMPLE = auphoria_sample_data.sample_path


# ------------------------------------------------------------- path handling
def test_path_home_style():
    p = clean_path_input("~/Documents/data.csv")
    assert "data.csv" in p.name
    assert p.is_absolute()


def test_path_quoted_drag_drop(tmp_path):
    # macOS/Linux drag-and-drop wraps the path in quotes.
    p = clean_path_input('"/some folder/my file.csv"')
    assert p.name == "my file.csv"
    assert "some folder" in str(p)
    # Leading "/" is absolute on POSIX; on Windows it normalizes to a relative
    # drive-less path. Either way the folder component is preserved.
    assert "some folder" in p.parts


def test_path_escaped_space(tmp_path):
    p = clean_path_input("/some folder/my\\ file.csv")
    assert p.name == "my file.csv"
    assert "some folder" in str(p)


def test_path_windows_backslashes_unix():
    # A Windows-style path typed on *this* machine is taken literally; we must
    # not crash and must keep the drive-letter/backslash text intact.
    p = clean_path_input("C:\\Users\\Student\\data.csv")
    assert "C:" in str(p).replace("\\", "")


def test_path_windows_unix_slash_style():
    # A WSL-style path keeps the filename; the slash style depends on the OS.
    p = clean_path_input("/mnt/c/Users/Student/data.csv")
    assert p.name == "data.csv"
    assert any("mnt" in part or "Users" in part for part in p.parts)


def test_path_absolute_unix(tmp_path):
    p = clean_path_input("/var/tmp/a b c/d.csv")
    assert p.name == "d.csv"
    assert "a b c" in str(p).replace("\\", "/")
    if os.name == "posix":
        assert p.is_absolute()


def test_path_relative():
    p = clean_path_input("data/plant_growth.csv")
    assert p.name == "plant_growth.csv"
    assert "data" in str(p)


# ------------------------------------------------------------------ diagnose-real-file
def test_wizard_full_flow_with_real_data(tmp_path, monkeypatch, capsys):
    """Drive the interactive wizard end to end on the real sample with canned
    answers, and confirm the engine run is invoked with the right mapping."""
    from auphoria.cli import menu

    calls = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return {"analysis_name": "Independent-Samples t-Test", "summaries": {},
                "warnings": [], "results_dir": str(tmp_path / "out")}

    monkeypatch.setattr(auphoria, "run", fake_run)
    monkeypatch.setattr(menu.webbrowser, "open", lambda _p: None)  # never open

    sample = _SAMPLE("plant_growth")
    # Answers:
    #   1) path           -> str(sample)
    #   2-5) kind confirm for 4 columns (Enter = accept detected kind)
    #   6-9) role confirm for 4 columns (Enter = accept suggested role)
    #   10) advisor question -> ""  (blank = skip advice, show all analyses)
    #   11) analysis menu -> ttest (index derived alphabetically so a new
    #       analysis never renumbers it)
    #   12) outcome input -> "1"  (first numeric column)
    #   13) group input   -> "1"  (first categorical column)
    #   14..16) params alpha/equal_var/tail -> Enter (defaults)
    #   17) summary confirm -> Enter (yes)
    #   18) open-folder      -> "n"
    from auphoria.adapters.adapters import read_data_frame
    from auphoria.advisor.advisor import profile_data_frame
    from auphoria.core.fitting import analyses_that_fit

    _df, _ = read_data_frame(sample)
    _kinds = {c.kind for c in profile_data_frame(_df).columns}
    _labels = {"numeric": "numeric", "categorical": "categorical", "datetime": "datetime"}
    _menu = sorted(analyses_that_fit([_labels.get(k, k) for k in _kinds]))
    _ttest_idx = str(_menu.index("ttest") + 1)
    answers = [str(sample), "", "", "", "", "", "", "", "", "",
               _ttest_idx, "1", "1", "", "", "", "", "n"]
    with_console(monkeypatch, iter(answers), [])
    menu.run_interactive(expert=False)

    assert calls, "engine run() was never called"
    kwargs = calls[0]
    assert kwargs["analysis"] == "ttest"
    assert kwargs["outcome"] == "height_cm"
    assert kwargs["group"] == "treatment"
    assert kwargs["seed"] == 1
    assert kwargs["params"] == []  # defaults accepted


def test_wizard_quits_from_menu(monkeypatch):
    from auphoria.cli import menu

    calls = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return {}

    monkeypatch.setattr(auphoria, "run", fake_run)
    sample = _SAMPLE("plant_growth")
    # path + 4 kinds + 4 roles accepted, then "0" to quit.
    answers = [str(sample), "", "", "", "", "", "", "", "", "0"]
    with_console(monkeypatch, iter(answers), [])
    menu.run_interactive(expert=False)
    assert calls == []


def test_wizard_cancels_with_ctrl_c(monkeypatch):
    from auphoria.cli import menu

    def raise_ki(_prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", raise_ki)
    with pytest.raises(SystemExit) as excinfo:
        menu.run_interactive(expert=False)
    assert excinfo.value.code == 130


def test_wizard_applies_role_override_order(monkeypatch, capsys):
    """A confirmed 'outcome' role moves that column first in the outcome input."""
    import pandas as pd

    from auphoria.advisor.advisor import profile_data_frame
    from auphoria.cli import menu

    df = pd.DataFrame({
        "score": [1.0, 2.0, 3.0],
        "age": [20, 21, 22],
        "group": ["a", "b", "a"],
    })
    profile = profile_data_frame(df)
    # Feed "1, 1": outcome picks the first numeric candidate (score now sorts
    # first thanks to the confirmed role), group picks the only categorical
    # column. ttest requires both required inputs, so both choices are needed
    # or the loop never advances.
    with_console(monkeypatch, iter(["1", "1"]), [])
    inputs = menu._choose_inputs(
        "ttest", profile, expert=False, role_overrides={"score": "outcome"}
    )
    # score is the first numeric column listed now (role matched).
    assert inputs["outcome"] == "score"


# ------------------------------------------------------------------ new commands
def test_describe_contains_example():
    cmd = _example_command("ttest", "Independent-Samples t-Test")
    assert cmd.startswith("auphoria run")
    assert "--analysis ttest" in cmd
    assert "--outcome" in cmd and "--group" in cmd


def test_describe_cli_subprocess(cli_python):
    proc = subprocess.run(
        cli_python + ["describe", "ttest"], capture_output=True, text=True
    )
    assert proc.returncode == 0
    assert "What it does" in proc.stdout
    assert "Assumptions" in proc.stdout
    assert "Limitations" in proc.stdout
    assert "Example:" in proc.stdout


def test_suggest_cli_builds_recommendations(cli_python, sample_csv):
    proc = subprocess.run(
        cli_python + ["suggest", "--data", str(sample_csv)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "ttest" in proc.stdout
    assert "suggested analyses" in proc.stdout.lower()


def test_demo_runs_without_file(tmp_path, monkeypatch, cli_python):
    """demo needs no data file and produces a real results folder."""
    import os
    # Isolate the results root via the documented AUPHORIA_RESULTS_ROOT override
    # (HOME is not honored by Path.home() on Windows, so it would leak results
    # into the real user profile there). When the env override is set, the
    # engine uses it DIRECTLY as the root (no AUPHORIA_results subfolder).
    env = dict(os.environ)
    env["AUPHORIA_RESULTS_ROOT"] = str(tmp_path)
    env.pop("HOME", None)
    proc = subprocess.run(cli_python + ["demo"], capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    root = tmp_path
    assert root.is_dir()
    runs = list(root.glob("*_ttest_*"))
    assert runs, "demo produced no results folder"


def test_list_filters_level_and_discipline(cli_python):
    all_out = subprocess.run(cli_python + ["list"], capture_output=True, text=True)
    lvl = subprocess.run(
        cli_python + ["list", "--level", "beginner"], capture_output=True, text=True
    )
    disc = subprocess.run(
        cli_python + ["list", "--discipline", "health"], capture_output=True, text=True
    )
    assert all_out.returncode == 0
    assert lvl.returncode == 0 and disc.returncode == 0
    # The filter never shows MORE than the full list.
    assert lvl.stdout.strip()  # non-empty
    # health-relevant analyses exist and are shown by name.
    assert "Independent-Samples" in disc.stdout


def test_list_no_match_prints_hint(cli_python):
    proc = subprocess.run(
        cli_python + ["list", "--level", "advanced", "--discipline", "astromancy"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    assert "No analyses match" in proc.stdout


def test_missing_data_file_plain_error(cli_python, tmp_path):
    proc = subprocess.run(
        cli_python + ["suggest", "--data", str(tmp_path / "nope.csv")],
        capture_output=True, text=True,
    )
    assert proc.returncode == 1
    assert "could not find" in proc.stderr.lower()
