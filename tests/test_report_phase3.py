"""Phase 3 report-engine acceptance tests.

- golden-file test for "describe" (data card + overview CSVs must match the
  checked-in golden output exactly);
- report.html is single-file and opens offline with no external requests;
- the replay scripts reproduce identical numeric results.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

import auphoria

GOLDEN = Path(__file__).resolve().parent / "golden"


@pytest.fixture(scope="module")
def describe_result(tmp_path_factory):
    """Run describe once into a scratch folder; reuse across tests in module."""
    out_dir = tmp_path_factory.mktemp("describe_golden")
    sample = Path("src/auphoria/sample_data/data/plant_growth.csv").resolve()
    result = auphoria.run(data_path=sample, analysis="describe", out=out_dir)
    return Path(result["results_dir"])


# ---------------------------------------------------------------- golden files
def test_describe_data_card_matches_golden(describe_result: Path):
    got = describe_result / "Data_card.csv"
    assert got.is_file()
    golden = pd.read_csv(GOLDEN / "describe_Data_card.csv")
    produced = pd.read_csv(got)
    pd.testing.assert_frame_equal(produced, golden)
    # A sniff-check that the golden is genuinely describe output.
    assert "Suggested role" in produced.columns
    assert {"Column", "Type", "Values", "Unique", "Missing"} <= set(produced.columns)


def test_describe_overview_matches_golden(describe_result: Path):
    got = describe_result / "Dataset_overview.csv"
    golden = pd.read_csv(GOLDEN / "describe_Dataset_overview.csv")
    produced = pd.read_csv(got)
    pd.testing.assert_frame_equal(produced, golden)


def test_describe_golden_files_are_current(tmp_path: Path):
    """If the engine changes, the golden must be regenerated deliberately."""
    sample = Path("src/auphoria/sample_data/data/plant_growth.csv").resolve()
    out = tmp_path / "out"
    r = auphoria.run(data_path=sample, analysis="describe", out=out)
    d = Path(r["results_dir"])
    produced_card = pd.read_csv(d / "Data_card.csv")
    pd.testing.assert_frame_equal(produced_card, pd.read_csv(GOLDEN / "describe_Data_card.csv"))


# ------------------------------------------------- report.html small artifact set
def test_report_contains_all_required_sections(describe_result: Path):
    html = (describe_result / "report.html").read_text(encoding="utf-8")
    # summary, verdicts, results, decision log, methods, "does not tell", versions
    for needle in (
        "<h2>Summary</h2>",
        "Quality checks (verdicts)",
        "<h2>Results</h2>",
        "<h2>Decision log</h2>",
        "What was done (methods)",
        "tell you",
        "software versions",
    ):
        assert needle in html, f"missing section: {needle}"
    # QC shown as text words, not colour alone.
    assert "PASS" in html and "WARN" in html
    assert "verdict-PASS" in html and "verdict-WARN" in html


def test_report_has_no_external_requests(describe_result: Path):
    html = (describe_result / "report.html").read_text(encoding="utf-8")
    # No remote <script>, no external <link>, no http(s) URLs, no url() refs.
    assert "<script" not in html
    assert "src=\"http" not in html and "src='http" not in html
    assert "url(http" not in html and "url('http" not in html
    import re

    assert not re.search(r"href=[\"']https?", html)
    # Any <img> must be an inline base64 data URI (no file:// either).
    for m in re.finditer(r"src=\"([^\"]+)\"", html):
        assert m.group(1).startswith("data:image/png;base64,"), m.group(1)
    # Single self-contained file: has a full HTML skeleton and inline <style>.
    assert "<!doctype html" in html
    assert "<style>" in html


def test_report_mentions_methods_and_reproducibility(describe_result: Path):
    run_info = json.loads((describe_result / "run.json").read_text(encoding="utf-8"))
    assert "decision_log" in run_info
    assert "verdicts" in run_info
    assert "input_sha256" in run_info
    # replay command in report
    html = (describe_result / "report.html").read_text(encoding="utf-8")
    assert run_info["replay_command"][:20] in html


# ------------------------------------------------------- replay reproduction
def _sh_available() -> bool:
    return shutil.which("bash") is not None


def test_replay_sh_reproduces_identical_results(tmp_path: Path):
    """Run describe, then execute replay.sh in a fresh HOME and confirm the
    numeric outputs match byte-for-byte."""
    sample = Path("src/auphoria/sample_data/data/plant_growth.csv").resolve()
    first = tmp_path / "first"
    r1 = auphoria.run(data_path=sample, analysis="describe", out=first)
    d1 = Path(r1["results_dir"])
    replay_sh = d1 / "replay.sh"
    assert replay_sh.is_file()
    text = replay_sh.read_text(encoding="utf-8")
    assert "auphoria run --data" in text
    assert "--seed 1" in text

    if not _sh_available():
        pytest.skip("bash not available on this platform")

    # Run the replay in an isolated HOME + PATH so it writes a fresh folder.
    fresh_home = tmp_path / "home"
    fresh_home.mkdir()
    venv_bin = str(Path(sys.executable).parent)
    env = dict(os.environ)
    env["HOME"] = str(fresh_home)
    env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")
    proc = subprocess.run(
        ["bash", str(replay_sh)],
        capture_output=True, text=True, env=env, cwd=tmp_path, timeout=180,
    )
    assert proc.returncode == 0, proc.stderr

    # The replayed run landed under fresh_home/AUPHORIA_results/<...>_describe_<ts>.
    results_root = fresh_home / "AUPHORIA_results"
    assert results_root.is_dir()
    replay_dirs = sorted(results_root.glob("*_describe_*"))
    assert replay_dirs, "no replay output folder found"
    d2 = replay_dirs[-1]

    # Identical numeric outputs.
    pd.testing.assert_frame_equal(
        pd.read_csv(d1 / "Data_card.csv"), pd.read_csv(d2 / "Data_card.csv")
    )
    pd.testing.assert_frame_equal(
        pd.read_csv(d1 / "Dataset_overview.csv"), pd.read_csv(d2 / "Dataset_overview.csv")
    )
    # run.json seeds match.
    j1 = json.loads((d1 / "run.json").read_text(encoding="utf-8"))
    j2 = json.loads((d2 / "run.json").read_text(encoding="utf-8"))
    assert j1["seed"] == j2["seed"]
    assert j1["parameters"] == j2["parameters"]
