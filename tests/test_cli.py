"""Tests for the CLI (auphoria command) via subprocess and direct calls."""

from __future__ import annotations

import subprocess
from pathlib import Path

from auphoria.core.version import __version__


def test_version_flag(cli_python):
    out = subprocess.run(cli_python + ["--version"], capture_output=True, text=True)
    assert out.returncode == 0
    assert __version__ in out.stdout


def test_doctor_ok_on_this_machine(cli_python):
    out = subprocess.run(cli_python + ["doctor"], capture_output=True, text=True)
    assert out.returncode == 0
    assert "All checks passed" in out.stdout
    assert "AUPHORIA" in out.stdout or "Python" in out.stdout


def test_list_prints_analyses(cli_python):
    out = subprocess.run(cli_python + ["list"], capture_output=True, text=True)
    assert out.returncode == 0
    assert "ttest" in out.stdout
    assert "correlation" in out.stdout
    assert "summary" in out.stdout


def test_info_prints_manifest(cli_python):
    out = subprocess.run(cli_python + ["info", "ttest"], capture_output=True, text=True)
    assert out.returncode == 0
    assert "Independent-Samples t-Test" in out.stdout
    assert "alpha" in out.stdout


def test_info_unknown_id_errors(cli_python):
    out = subprocess.run(cli_python + ["info", "nope"], capture_output=True, text=True)
    assert out.returncode == 1
    assert "Unknown analysis" in out.stderr


def test_run_one_liner_cli(sample_csv: Path, tmp_path: Path, cli_python):
    out_dir = tmp_path / "cli_out"
    out = subprocess.run(
        cli_python + [
            "run", "--data", str(sample_csv), "--analysis", "ttest",
            "--outcome", "height_cm", "--group", "treatment",
            "--out", str(out_dir),
        ],
        capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr
    assert "Results saved" in out.stdout
    assert (out_dir / "report.html").is_file()
    assert (out_dir / "run.json").is_file()


def test_run_unknown_param_cli_errors(sample_csv: Path, tmp_path: Path, cli_python):
    out = subprocess.run(
        cli_python + ["run", "--data", str(sample_csv), "--analysis", "ttest",
                      "--outcome", "height_cm", "--group", "treatment",
                      "--param", "nonsense=1", "--out", str(tmp_path / "x")],
        capture_output=True, text=True,
    )
    assert out.returncode == 1
    assert "Unknown option" in out.stderr


def test_sample_command_copies_csv(tmp_path: Path, cli_python, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = subprocess.run(cli_python + ["sample", "plant_growth"],
                         capture_output=True, text=True)
    assert out.returncode == 0
    assert (tmp_path / "plant_growth.csv").is_file()


def test_main_direct_with_args():
    """Call main() directly with argv (no subprocess) for fast coverage."""
    from auphoria.cli.main import main

    assert main(["list"]) == 0
    assert main(["versions"]) == 0


def test_no_traceback_leaks_to_console(cli_python, sample_csv: Path, tmp_path: Path):
    """A non-numeric outcome must print plain English, NOT a traceback."""
    import pandas as pd

    bad = tmp_path / "bad.csv"
    pd.DataFrame(
        {"v": ["1", "2", "three", "4", "5", "6"],
         "g": ["a", "a", "a", "b", "b", "b"]}
    ).to_csv(bad, index=False)
    out = subprocess.run(
        cli_python + ["run", "--data", str(bad), "--analysis", "ttest",
                      "--outcome", "v", "--group", "g", "--out", str(tmp_path / "o")],
        capture_output=True, text=True,
    )
    assert out.returncode == 1
    assert "Traceback" not in out.stdout and "Traceback" not in out.stderr
    assert "cannot become a number" in out.stderr
