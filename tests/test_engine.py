"""End-to-end tests of the engine: full runs with all outputs on disk."""

from __future__ import annotations

import json
from pathlib import Path

import auphoria


def test_ttest_full_run_writes_all_outputs(sample_csv: Path, tmp_results: Path):
    result = auphoria.run(
        data_path=sample_csv,
        analysis="ttest",
        outcome="height_cm",
        group="treatment",
        out=tmp_results,
    )
    d = Path(result["results_dir"])
    for fname in ("report.html", "methods.txt", "run.json", "log.txt",
                  "replay.sh", "replay.ps1", "ttest_boxplot.png",
                  "Group_statistics.csv", "Independent-samples_t-test.csv"):
        assert (d / fname).is_file(), f"missing {fname}"

    # run.json carries reproducibility fields
    run_info = json.loads((d / "run.json").read_text(encoding="utf-8"))
    assert run_info["analysis"]["id"] == "ttest"
    assert len(run_info["input_sha256"]) == 64
    assert run_info["seed"] == 1
    assert "numpy" in run_info["package_versions"]
    assert "replay_command" in run_info
    assert run_info["parameters"]["alpha"] == "0.05"

    # log recorded decisions
    log_txt = (d / "log.txt").read_text(encoding="utf-8")
    assert "DECISION:" in log_txt
    assert "Welch" in log_txt

    # report is self-contained: CSS inline and a base64 figure
    report = (d / "report.html").read_text(encoding="utf-8")
    assert "<style>" in report
    assert "data:image/png;base64," in report
    assert "AUPHORIA" in report

    # methods.txt is a paste-ready paragraph
    methods = (d / "methods.txt").read_text(encoding="utf-8")
    assert "t-test" in methods
    assert "numpy" in methods


def test_explicit_out_dir_reused(sample_csv: Path, tmp_results: Path):
    result = auphoria.run(data_path=sample_csv, analysis="ttest",
                          outcome="height_cm", group="treatment", out=tmp_results)
    assert Path(result["results_dir"]) == tmp_results


def test_out_dir_must_be_empty(tmp_path: Path):
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "hi.txt").write_text("hi")
    import pytest

    from auphoria.core.errors import InputValidationError

    with pytest.raises(InputValidationError):
        auphoria.run(data_path=tmp_path / "x", analysis="ttest", out=occupied)


def test_correlation_full_run(survey_csv: Path, tmp_results: Path):
    result = auphoria.run(
        data_path=survey_csv, analysis="correlation",
        extra={"x": "hours_studied", "y": "score"}, out=tmp_results,
    )
    d = Path(result["results_dir"])
    assert (d / "report.html").is_file()
    assert (d / "Pearson_correlation.csv").is_file()
    assert (d / "correlation_scatter.png").is_file()
    assert "r" in result["summaries"] or "correlation r" in result["summaries"]


def test_summary_full_run(sample_csv: Path, tmp_results: Path):
    result = auphoria.run(
        data_path=sample_csv, analysis="summary", out=tmp_results,
    )
    d = Path(result["results_dir"])
    assert (d / "Numeric_summary.csv").is_file()
    assert (d / "Categorical_counts.csv").is_file()
    assert "height_cm" in (d / "Numeric_summary.csv").read_text(encoding="utf-8")


def test_unknown_analysis_raises_friendly(sample_csv: Path, tmp_results: Path):
    import pytest

    from auphoria.core.errors import InputValidationError

    with pytest.raises(InputValidationError) as ei:
        auphoria.run(data_path=sample_csv, analysis="definitely_not_a_test",
                     out=tmp_results)
    assert "definitely_not_a_test" in str(ei.value)


def test_ttest_with_too_many_groups_refuses(sample_csv: Path, tmp_results: Path):
    """The sample only has 2 treatment groups, so build a 3-group file."""
    import pandas as pd
    import pytest

    from auphoria.core.errors import AssumptionError

    df = pd.DataFrame({
        "v": [1, 2, 3, 4, 5, 6, 7, 8, 9],
        "g": ["a", "a", "a", "b", "b", "b", "c", "c", "c"],
    })
    path = tmp_results.parent / "three.csv"
    df.to_csv(path, index=False)
    with pytest.raises(AssumptionError):
        auphoria.run(data_path=path, analysis="ttest",
                     outcome="v", group="g", out=tmp_results / "x")


def test_non_numeric_outcome_text_refuses(tmp_path: Path):
    import pandas as pd
    import pytest

    from auphoria.core.errors import AssumptionError

    df = pd.DataFrame({
        "v": ["1", "2", "three", "4", "5", "6"],
        "g": ["a", "a", "a", "b", "b", "b"],
    })
    path = tmp_path / "text.csv"
    df.to_csv(path, index=False)
    with pytest.raises(AssumptionError) as ei:
        auphoria.run(data_path=path, analysis="ttest", outcome="v",
                     group="g", out=tmp_path / "out")
    assert "cannot become a number" in str(ei.value)


def test_seed_recorded_and_replay_sh_has_seed(sample_csv: Path, tmp_results: Path):
    result = auphoria.run(
        data_path=sample_csv, analysis="ttest", outcome="height_cm",
        group="treatment", seed=77, out=tmp_results,
    )
    d = Path(result["results_dir"])
    run_info = json.loads((d / "run.json").read_text(encoding="utf-8"))
    assert run_info["seed"] == 77
    assert "--seed 77" in run_info["replay_command"]
    assert "--seed 77" in (d / "replay.sh").read_text(encoding="utf-8")
    assert "--seed 77" in (d / "replay.ps1").read_text(encoding="utf-8")


def test_missing_values_warn_not_imputed(sample_csv: Path, tmp_results: Path):
    # Run the summary analysis; weight_g has 3 blanks; the warning/none should
    # reflect counting, not drop.
    import pandas as pd

    result = auphoria.run(data_path=sample_csv, analysis="summary",
                          outcome="weight_g", out=tmp_results)
    d = Path(result["results_dir"])
    csv = pd.read_csv(d / "Numeric_summary.csv")
    row = csv[csv["Column"] == "weight_g"].iloc[0]
    assert int(row["missing"]) == 3
    assert int(row["n"]) == 27  # 30 - 3, never imputed
