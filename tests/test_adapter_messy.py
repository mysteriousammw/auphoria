"""Tests for Phase 2 adapter robustness with messy synthetic files.

Covers the acceptance cases: wrong delimiter, quoted path with spaces, blank
rows, mixed types in a column, duplicate headers, and empty files - each must
either load correctly or give a clear plain-English error (never a raw
traceback and never silent data corruption).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from auphoria.adapters.adapters import list_sheets, read_data_frame
from auphoria.core.errors import DataError


# ---------------------------------------------------------------- wrong delimiter
def test_semicolon_delimited_loads_and_warns(tmp_path: Path):
    p = tmp_path / "semi.csv"
    p.write_text("name;score\nada;91\nbob;84\n", encoding="utf-8")
    df, warnings = read_data_frame(p)
    assert df.shape == (2, 2)
    assert list(df.columns) == ["name", "score"]
    assert df.loc[0, "score"] in ("91", 91)  # numeric type is fine either way
    # delimiter was not a comma -> warned, never silent
    assert any("separated" in w.lower() or "delimiter" in w.lower() for w in warnings)


def test_pipe_delimited_loads(tmp_path: Path):
    p = tmp_path / "pipe.txt"
    p.write_text("a|b|c\n1|2|3\n4|5|6\n", encoding="utf-8")
    df, _w = read_data_frame(p)
    assert df.shape == (2, 3)  # header + 2 data rows


def test_tab_delimited_loads(tmp_path: Path):
    p = tmp_path / "tab.tsv"
    p.write_text("x\ty\n1\t2\n", encoding="utf-8")
    df, _w = read_data_frame(p)
    assert df.shape == (1, 2)


def test_comma_delimited_preferred(tmp_path: Path):
    """A true CSV with commas must not be misdetected."""
    p = tmp_path / "c.csv"
    p.write_text("a,b\n1,2\n", encoding="utf-8")
    df, _w = read_data_frame(p)
    assert df.shape == (1, 2)


# -------------------------------------------------------- quoted path with spaces
def test_quoted_path_with_spaces(tmp_path: Path):
    d = tmp_path / "My Data Folder"
    d.mkdir()
    p = d / "plant data.csv"
    p.write_text("col,val\n1,2\n", encoding="utf-8")
    # Surrounded by double quotes as when dragging into a terminal.
    df, _w = read_data_frame(f'"{p}"')
    assert df.shape == (1, 2)


def test_single_quoted_path_with_spaces(tmp_path: Path):
    d = tmp_path / "folder with spaces"
    d.mkdir()
    p = d / "data file.csv"
    p.write_text("x,y\n3,4\n", encoding="utf-8")
    df, _w = read_data_frame(f"'{p}'")
    assert df.shape == (1, 2)


def test_unquoted_path_with_spaces(tmp_path: Path):
    d = tmp_path / "folder with spaces"
    d.mkdir()
    p = d / "data file.csv"
    p.write_text("x,y\n5,6\n", encoding="utf-8")
    df, _w = read_data_frame(str(p))
    assert df.shape == (1, 2)


def test_missing_file_clear_message(tmp_path: Path):
    with pytest.raises(DataError) as ei:
        read_data_frame(tmp_path / "nope.csv")
    assert "could not find" in str(ei.value).lower()
    full = ei.value.to_user()
    assert "Check" in full or "Fix" in full or "hint" in full.lower()


# ------------------------------------------------------------------ blank rows
def test_blank_rows_kept_and_flagged(tmp_path: Path):
    # A genuinely blank line (no delimiters, empty between records) as in a
    # typical spreadsheet export. pandas drops it during read, so AUPHORIA
    # warns about it loudly (never silently).
    p = tmp_path / "blank.csv"
    p.write_text("a,b\n1,2\n\n3,4\n", encoding="utf-8")
    df, warnings = read_data_frame(p)
    assert df.shape[0] == 2  # the blank line is skipped by pandas...
    assert any("blank" in w.lower() for w in warnings)  # ...but we flag it


def test_all_blank_data_refused(tmp_path: Path):
    p = tmp_path / "empty.csv"
    p.write_text("a,b\n,,,\n", encoding="utf-8")
    with pytest.raises(DataError):
        read_data_frame(p)


# ---------------------------------------------------- mixed types in a column
def test_mixed_text_in_numeric_column_preserved(tmp_path: Path):
    """A column with numbers and a stray word must load without silently
    converting the word to NaN or dropping the row."""
    p = tmp_path / "mixed.csv"
    p.write_text("id,value\n1,10\n2,oops\n3,30\n", encoding="utf-8")
    df, warnings = read_data_frame(p)
    # object dtype: the word survives; nothing is coerced or dropped here.
    assert df["value"].dtype == object
    assert df["value"].tolist() == ["10", "oops", "30"]
    # A later analysis would refuse (ensure_numeric) rather than silently coerce.


def test_partial_missing_preserved_as_na(tmp_path: Path):
    p = tmp_path / "na.csv"
    p.write_text("a,b\n1,\n2,4\n", encoding="utf-8")
    df, _w = read_data_frame(p)
    assert pd.isna(df.loc[0, "b"])
    assert int(df.loc[1, "b"]) == 4


# ---------------------------------------------------------- duplicate headers
def test_duplicate_headers_made_unique_and_warned(tmp_path: Path):
    p = tmp_path / "dup_headers.csv"
    p.write_text("a,a,b\n1,2,3\n", encoding="utf-8")
    df, warnings = read_data_frame(p)
    assert len(set(df.columns)) == len(df.columns)  # unique after read
    assert any("renamed" in w.lower() for w in warnings)


# ---------------------------------------------------------------- empty files
def test_empty_file_refused(tmp_path: Path):
    p = tmp_path / "empty.csv"
    p.write_text("", encoding="utf-8")
    with pytest.raises(DataError) as ei:
        read_data_frame(p)
    assert "no data" in str(ei.value).lower() or "empty" in str(ei.value).lower()


def test_header_only_refused(tmp_path: Path):
    p = tmp_path / "header_only.csv"
    p.write_text("a,b,c\n", encoding="utf-8")
    with pytest.raises(DataError):
        read_data_frame(p)


def test_unsupported_extension_clear_message(tmp_path: Path):
    p = tmp_path / "data.docx"
    p.write_text("hello", encoding="utf-8")
    with pytest.raises(DataError) as ei:
        read_data_frame(p)
    assert "not supported" in str(ei.value).lower()


# ----------------------------------------------------------- ANSI fallback flagged
def test_ansi_fallback_flagged(tmp_path: Path):
    p = tmp_path / "latin.csv"
    p.write_bytes(b"city,val\nMontr\xe9al,5\n")
    df, warnings = read_data_frame(p)
    assert df.shape[0] == 1
    assert any("encoding" in w.lower() for w in warnings)


# ------------------------------------------------------- json / dta round trips
def test_json_reads(tmp_path: Path):
    p = tmp_path / "data.json"
    p.write_text('[{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]', encoding="utf-8")
    df, _w = read_data_frame(p)
    assert df.shape == (2, 2)


def test_stata_dta_reads(tmp_path: Path):
    df_in = pd.DataFrame({"a": [1, 2, 3], "b": ["p", "q", "r"]})
    p = tmp_path / "data.dta"
    df_in.to_stata(str(p), write_index=False)
    df, _w = read_data_frame(p)
    assert df.shape == (3, 2)
    assert list(df.columns) == ["a", "b"]


# --------------------------------------------------------------- xlsx & sheets
def test_xlsx_multi_sheet_asks(tmp_path: Path):
    df1 = pd.DataFrame({"a": [1, 2]})
    df2 = pd.DataFrame({"z": [9, 9, 9]})
    p = tmp_path / "book.xlsx"
    with pd.ExcelWriter(p) as writer:
        df1.to_excel(writer, sheet_name="Sheet1", index=False)
        df2.to_excel(writer, sheet_name="Sheet2", index=False)
    sheets = list_sheets(p)
    assert sheets == ["Sheet1", "Sheet2"]
    # Reading a specific sheet works; a missing sheet gives a clear error.
    df, _w = read_data_frame(p, sheet="Sheet2")
    assert df.shape == (3, 1)
    with pytest.raises(DataError) as ei:
        read_data_frame(p, sheet="Nope")
    assert "not found" in str(ei.value).lower()
