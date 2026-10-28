"""Tests for the data adapters: reading CSV/TSV/TXT/XLSX and structural checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from auphoria.adapters.adapters import preview_text, read_data_frame
from auphoria.core.errors import DataError


def test_reads_sample_csv(sample_csv: Path):
    df, warnings = read_data_frame(sample_csv)
    assert df.shape[0] == 30
    assert {"treatment", "height_cm", "weight_g", "light_hours"} <= set(df.columns)
    # The sample includes 3 deliberate blanks in weight_g.
    assert int(df["weight_g"].isna().sum()) == 3
    assert warnings == []  # nothing unusual about a clean UTF-8 CSV


def test_preview_contains_shape_and_header(sample_csv: Path):
    df, _ = read_data_frame(sample_csv)
    text = preview_text(df)
    assert "30 rows x 4 columns" in text
    assert "treatment" in text


def test_missing_file_raises_friendly():
    with pytest.raises(DataError):
        read_data_frame("/does/not/exist.csv")


def test_unsupported_extension(tmp_path: Path):
    p = tmp_path / "data.pdf"
    p.write_text("not really")
    with pytest.raises(DataError) as ei:
        read_data_frame(p)
    assert ".pdf" in str(ei.value)


def test_legacy_xls_unsupported(tmp_path: Path):
    p = tmp_path / "old.xls"
    p.write_text("junk")
    with pytest.raises(DataError):
        read_data_frame(p)


def test_empty_csv_refused(tmp_path: Path):
    p = tmp_path / "empty.csv"
    p.write_text("a,b\n")
    with pytest.raises(DataError):
        read_data_frame(p)


def test_duplicate_columns_are_unique_after_read(tmp_path: Path):
    # pandas renames repeated headers (a, a.1, a.2); the guardrail is simply
    # that the returned frame has unique columns so menus never mis-address one.
    p = tmp_path / "dup.csv"
    p.write_text("a,a,b\n1,2,3\n4,5,6\n")
    df, _warnings = read_data_frame(p)
    assert len(df.columns) == 3
    assert len(set(df.columns)) == len(df.columns)  # all unique now


def test_tsv_and_txt_supported(tmp_path: Path):
    content = "x\ty\n1\t2\n3\t4\n"
    for suffix in (".tsv", ".txt", ".tab"):
        p = tmp_path / f"data{suffix}"
        p.write_text(content)
        df, _w = read_data_frame(p)
        assert df.shape == (2, 2)
        assert list(df.columns) == ["x", "y"]


def test_ansi_fallback_flagged(tmp_path: Path):
    # A Latin-1 encoded file (é encoded as 0xE9) that is not valid UTF-8.
    p = tmp_path / "ansi.csv"
    p.write_bytes(b"city,val\nMontr\xe9al,5\nM\xfcnchen,6\n")
    df, warnings = read_data_frame(p)
    assert df.shape[0] == 2
    assert any("encoding" in w.lower() for w in warnings)


def test_xlsx_reads_when_openpyxl_available(tmp_path: Path):
    import pandas as pd

    df_in = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    path = tmp_path / "book.xlsx"
    df_in.to_excel(path, index=False)
    df, _w = read_data_frame(path)
    assert df.shape == (3, 2)
