"""Reading student data files into pandas DataFrames, with guardrails.

Supported formats (Phase 2):
    plain text   .csv .tsv .txt .tab   (delimiter auto-sniffed)
    Excel        .xlsx .xlsm .xls .ods
    JSON         .json                 (tabular array-of-objects, or similar)
    Stata        .dta
    SPSS         .sav                  (optional, via pyreadstat)

Reading is careful:

- the file must exist, be readable and not empty;
- paths may contain spaces and may arrive wrapped in quotes because the user
  dragged the file into the terminal - both are handled;
- encodings: UTF-8 first, then a documented Windows ANSI fallback (flagged,
  never silent);
- headers: a possible title/merged header row is detected and WRITTEN about
  (we never silently drop a row); duplicate/blank header names are made unique
  and the renames are reported;
- multi-sheet workbooks: callers first ask which sheet (see ``list_sheets``);
- missing cells are preserved as NaN (never imputed, never dropped here);
- a file with zero data rows is refused with plain-English guidance.

Returns (dataframe, warnings) so the caller can surface every caveat.
``warnings`` is the plain-English record of anything the reader adjusted -
nothing is done silently.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from auphoria.core.errors import DataError

_EXCEL_SUFFIXES = {".xlsx", ".xlsm", ".xls", ".ods"}
_CSV_SUFFIXES = {".csv", ".tsv", ".txt", ".tab"}
_JSON_SUFFIXES = {".json"}
_JSONL_SUFFIXES = {".jsonl", ".ndjson"}
_STATA_SUFFIXES = {".dta"}
_SPSS_SUFFIXES = {".sav"}
_SUPPORTED = sorted(
    _EXCEL_SUFFIXES | _CSV_SUFFIXES | _JSON_SUFFIXES | _JSONL_SUFFIXES
    | _STATA_SUFFIXES | _SPSS_SUFFIXES
)

_ANSI_FALLBACKS = ["cp1252", "latin-1"]


def clean_path_input(raw: str | Path) -> Path:
    """Normalise a user-typed file path the way people really type them.

    Accepts Windows and POSIX styles, ~ expansions, surrounding quotes (from
    drag-and-drop), and a space escaped as ``\\ `` in a terminal. Does NOT
    check existence (that is the caller's job).
    """
    text = str(raw).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
        text = text[1:-1]
    text = text.replace("\\ ", " ") if " " in text else text
    # A leading ~ is an OS-level tilde; let pathlib expand it.
    return Path(text).expanduser()


def _resolve_path(path: str | Path) -> Path:
    raw = str(path).strip()
    # Strip a pair of surrounding quotes (people drag paths into a terminal,
    # which often includes quotes). Only strip a matching pair.
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
        raw = raw[1:-1]
    raw = raw.replace("\\ ", " ") if " " in raw else raw  # tolerate escaped space
    p = Path(raw).expanduser()
    if not p.exists():
        raise DataError(
            f"I could not find a data file at '{p}'.",
            hint="Check the spelling, folder name, and that you are in the "
                 "right directory. If the path has spaces you can drag the file "
                 "into the terminal and press Enter.",
        )
    if not p.is_file():
        raise DataError(
            f"'{p}' is not a file (it seems to be a folder).",
            hint="Point at a real data file.",
        )
    return p


def _suffix_check(suffix: str) -> None:
    if suffix not in _SUPPORTED:
        raise DataError(
            f"The file type '.{suffix}' is not supported.",
            hint=(
                "Save your data as CSV, TSV/TXT, Excel (.xlsx), OpenDocument "
                "(.ods), JSON, Stata (.dta) or SPSS (.sav), then retry."
            ),
        )


# ------------------------------------------------------------------ readers
def _read_text(handle_path: Path) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    try:
        df, used_sep, header_warnings = _read_text_with_delimiter(handle_path)
        warnings.extend(header_warnings)
    except UnicodeDecodeError:
        for encoding in _ANSI_FALLBACKS:
            try:
                df = pd.read_csv(handle_path, sep=None, engine="python",
                                 encoding=encoding)
                warnings.append(
                    f"The file did not read as plain UTF-8 text, so AUPHORIA "
                    f"fell back to the '{encoding}' encoding. This is common "
                    f"for Windows-saved files but can garble accents - check "
                    f"your values in the preview."
                )
                return df, warnings
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
        raise DataError(
            "The file could not be read as text in UTF-8 or a common Windows "
            "encoding.",
            hint="Re-save the file as UTF-8 CSV (File > Save As, Encoding UTF-8).",
        ) from None
    except Exception as exc:  # noqa: BLE001 - other parse failures
        raise DataError(
            f"Your data file could not be parsed as a table: {exc}",
            hint="Ensure it is a rectangular table (a header row, then data rows).",
        ) from exc

    if df is None or df.shape[0] == 0:
        raise DataError(
            "The file contains no data rows.",
            hint="Check the file has at least one row of data below the header.",
        )
    if used_sep is not None and used_sep in (";", "|"):
        warnings.append(
            f"Your file is mostly separated by '{used_sep}' rather than a comma; "
            f"AUPHORIA read it that way. This is common for data saved in "
            f"regions where the comma is the decimal separator."
        )
    return df, warnings


def _read_text_with_delimiter(
    path: Path,
) -> tuple[pd.DataFrame, str | None, list[str]]:
    """Read a delimited file, choosing the delimiter by majority sample.

    Returns (df, used_delimiter, header_warnings). header_warnings notes
    duplicate header names seen in the FIRST line (pandas would rename them to
    unique names like ``a.1`` without telling us, which we refuse to do silently).
    """
    try:
        sample = path.read_text(encoding="utf-8", errors="strict").splitlines()
    except UnicodeDecodeError:
        raise
    all_lines = [ln for ln in sample]
    sample = [ln for ln in sample[:8] if ln.strip()]
    if not sample:
        raise DataError("The file appears to be empty.")

    blank_count = sum(1 for ln in all_lines if ln.strip() == "")
    blank_warning = (
        [f"{blank_count} completely blank line(s) were found in the file; "
         f"AUPHORIA skipped them while reading (pandas does this automatically) "
         f"and will mention it here so nothing is silently dropped. Delete them "
         f"in your spreadsheet if they are not intentional."]
        if blank_count
        else []
    )

    def _count(sep: str) -> int:
        return min(line.count(sep) for line in sample)

    # Detect a consistent delimiter (treat quote-safe comma as priority).
    tab = "\t"
    delims = {tab: _count(tab), ";": _count(";"), "|": _count("|"), ",": _count(",")}
    best = [d for d, c in delims.items() if c > 0]
    header_warnings: list[str] = blank_warning
    if best:
        chosen = max(best, key=lambda d: delims[d])
        sep = "\t" if chosen == tab else chosen
        try:
            df = pd.read_csv(path, sep=sep, engine="python")
        except pd.errors.ParserError as exc:
            raise DataError(
                f"Your data file has rows with different numbers of columns "
                f"({exc}).",
                hint="Check for stray commas/semicolons, trailing delimiters, or "
                     "lines that wrap onto two rows in the file.",
            ) from exc
        seen_names = _header_names(sample[0], sep)
        dups = _duplicate_names(seen_names)
        if dups:
            header_warnings.append(
                "Some column names in the first row are repeated; AUPHORIA "
                f"renamed them to be unique ({', '.join(dups)} -> e.g. 'a.1') "
                "so you can tell them apart."
            )
        return df, (None if sep == "," else sep), header_warnings

    # Try pandas' own sniffing for odd-but-consistent delimiters.
    df = pd.read_csv(path, sep=None, engine="python")
    return df, None, header_warnings


def _header_names(first_line: str, sep: str) -> list[str]:
    """Split a header line into (stripped) column name strings."""
    parts = first_line.split(sep)
    return [p.strip().strip('"').strip("'") for p in parts if p.strip()]


def _duplicate_names(names: list[str]) -> list[str]:
    """Return header names that occur more than once, in order."""
    from collections import Counter

    counts = Counter(names)
    return [n for n, c in counts.items() if c > 1]


def _read_excel(handle_path: Path) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    suffix = handle_path.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            raise DataError(
                "Reading Excel .xlsx files needs the optional 'openpyxl' package.",
                hint="Install it with: pip install auphoria[excel] (or 'pip install openpyxl').",
            ) from None
    elif suffix == ".xls":
        try:
            import xlrd  # noqa: F401
        except ImportError:
            raise DataError(
                "Reading legacy Excel .xls files needs the 'xlrd' package.",
                hint="Install it with: pip install xlrd  (or open the file in "
                     "Excel and File > Save As .xlsx).",
            ) from None
    else:  # .ods
        try:
            import odf  # noqa: F401
        except ImportError:
            raise DataError(
                "Reading OpenDocument (.ods) files needs the 'odfpy' package.",
                hint="Install it with: pip install odfpy (or save as .xlsx/.csv).",
            ) from None

    try:
        df = pd.read_excel(handle_path)  # first sheet by default
    except Exception as exc:  # noqa: BLE001
        raise DataError(
            f"The spreadsheet could not be read: {exc}",
            hint="Ensure it is a supported workbook (.xlsx/.xls/.ods) with data "
                 "on the first sheet.",
        ) from exc

    _warn_title_or_merged_header(df, warnings, handle_path)
    if df is None or df.shape[0] == 0:
        raise DataError(
            "The workbook's first sheet has no data rows.",
            hint="Put your data on the first sheet, or export to CSV (.csv).",
        )
    return df, warnings


def _warn_title_or_merged_header(df: pd.DataFrame, warnings: list[str], path: Path) -> None:
    """If the first row looks like a title / merged header rather than column
    labels, say so (we never silently drop it). Heuristic: columns whose names
    are generic 'Unnamed: N' mean the real headers are lower, OR every value in
    row 0 is text while the columns below are numeric.
    """
    unnamed = [c for c in df.columns if str(c).startswith("Unnamed:")]
    if unnamed and df.shape[0] > 0:
        warnings.append(
            f"The first row of '{path.name}' looks like a title or a merged "
            f"header, not column labels ({len(unnamed)} column name(s) came out "
            f"blank). The real headers are probably in the next row. AUPHORIA "
            f"kept the data as-is; if the first row is a title, delete it or "
            f"re-save with a single header row."
        )
        return
    # A single leading all-text title row where the rest is numeric.
    if df.shape[0] >= 2:
        first_all_text = all(
            isinstance(v, str) and not _looks_numeric(v) for v in df.iloc[0]
        )
        later_is_numeric = sum(
            1 for c in df.columns if pd.api.types.is_numeric_dtype(df[c])
        ) >= max(1, len(df.columns) // 2)
        if first_all_text and later_is_numeric:
            warnings.append(
                f"The first row of '{path.name}' appears to be a title or "
                f"merged header (all text) while the data below are numbers. "
                f"AUPHORIA kept everything as-is. If the first row is not real "
                f"data, delete it before analysing."
            )


def _looks_numeric(value: str) -> bool:
    try:
        float(value.replace(",", "").replace("%", "").strip())
        return True
    except ValueError:
        return False


def _read_json(handle_path: Path) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    try:
        if handle_path.suffix.lower() in _JSONL_SUFFIXES:
            df = pd.read_json(handle_path, lines=True)
        else:
            df = pd.read_json(handle_path)
    except Exception as exc:  # noqa: BLE001
        raise DataError(
            f"The JSON file could not be read as a table: {exc}",
            hint="AUPHORIA needs JSON that is a list of objects, an array of "
                 "arrays, or an array of rows (e.g. [{'a':1,'b':2}, ...]). "
                 "Export your data as CSV for the simplest path.",
        ) from exc
    if isinstance(df, dict):  # pragma: no cover - read_json returns DF for tables
        raise DataError(
            "The JSON file is a nested object, not a flat table.",
            hint="Flatten it or export as CSV.",
        )
    if df is None or df.shape[0] == 0:
        raise DataError(
            "The JSON file contains no data rows.",
            hint="Check the file has at least one row of objects.",
        )
    return df, warnings


def _read_stata(handle_path: Path) -> tuple[pd.DataFrame, list[str]]:
    try:
        df = pd.read_stata(handle_path)
    except Exception as exc:  # noqa: BLE001
        raise DataError(
            f"The Stata .dta file could not be read: {exc}",
            hint="Confirm it is a .dta file (version 105-119).",
        ) from exc
    if df is None or df.shape[0] == 0:
        raise DataError("The Stata file contains no data rows.")
    return df, []


def _read_spss(handle_path: Path) -> tuple[pd.DataFrame, list[str]]:
    try:
        import pyreadstat
    except ImportError:
        raise DataError(
            "Reading SPSS .sav files needs the 'pyreadstat' package.",
            hint="Install it with: pip install pyreadstat",
        ) from None
    try:
        df, _meta = pyreadstat.read_sav(str(handle_path))
    except Exception as exc:  # noqa: BLE001
        raise DataError(
            f"The SPSS .sav file could not be read: {exc}",
            hint="Confirm it is a valid SPSS .sav file.",
        ) from exc
    if df is None or df.shape[0] == 0:
        raise DataError("The SPSS file contains no data rows.")
    return df, []


def _check_structure(df: pd.DataFrame, path: Path) -> list[str]:
    """Structural checks after reading; returns extra warnings."""
    warnings: list[str] = []

    # Drop fully-blank trailing/leading rows is NOT done silently (never drop
    # data without saying so), but blank ROWS inside cause a warning.
    blank_rows = int(df.isna().all(axis=1).sum())
    if blank_rows:
        warnings.append(
            f"{blank_rows} row(s) in '{path.name}' are completely blank. "
            f"AUPHORIA kept them (it never drops data silently) but you may "
            f"want to delete them in your spreadsheet before analysis."
        )

    # Duplicate / blank column names are made unique and reported.
    seen: dict[str, int] = {}
    duplicates: list[str] = []
    new_columns: list[str] = []
    for col in df.columns:
        name = str(col).strip()
        if name == "":
            name = "unnamed"
        if name in seen:
            seen[name] += 1
            dup_name = f"{name}_{seen[name]}"
            duplicates.append(str(col))
            new_columns.append(dup_name)
        else:
            seen[name] = 1
            new_columns.append(name)
    if duplicates:
        df.columns = new_columns
        warnings.append(
            f"Some column names were blank or repeated; AUPHORIA renamed them "
            f"to be unique ({', '.join(sorted(set(duplicates)))}) so you can "
            f"tell them apart."
        )
    return warnings


# ---------------------------------------------------------------- public API
def _reject_if_no_usable_rows(df: pd.DataFrame, path: Path) -> None:
    """Refuse a table whose every row is blank (no usable observation)."""
    usable = df.dropna(how="all")
    if df.shape[0] == 0 or usable.shape[0] == 0:
        raise DataError(
            f"'{path.name}' has no row with actual values (every row is blank).",
            hint="Check the file - it looks like only headers (or blank lines) "
                 "were imported.",
        )


def list_sheets(path: str | Path) -> list[str]:
    """Return the sheet names of an Excel/ODS workbook (for multi-sheet files).

    Raises DataError for non-workbook files. Used so the CLI can ASK the user
    which sheet to use instead of silently reading the first.
    """
    p = _resolve_path(path)
    suffix = p.suffix.lower()
    if suffix not in _EXCEL_SUFFIXES:
        raise DataError(
            f"'{p.suffix or p.name}' is not a spreadsheet, so asking for sheets "
            f"does not apply.",
            hint="This is a text/data file; read it directly.",
        )
    try:
        book = pd.ExcelFile(p)
        sheets = [str(s) for s in book.sheet_names]
        if len(sheets) == 1:
            return sheets
        return sheets
    except Exception as exc:  # noqa: BLE001
        raise DataError(
            f"Could not read the sheet list of '{p}': {exc}",
            hint="Confirm it is a valid .xlsx/.xls/.ods workbook.",
        ) from exc


def read_data_frame(
    path: str | Path,
    sheet: int | str | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Read ``path`` (optionally a named sheet) into a DataFrame.

    Returns (df, warnings). A ``warnings`` entry documents every adjustment
    (encoding fallback, delimiter choice, header/title detection, renames) so
    nothing is done to the user's data without telling them.

    Raises DataError with a plain-English message + fix when the file is
    missing, unsupported, empty, or unparseable.
    """
    p = _resolve_path(path)
    suffix = p.suffix.lower()
    _suffix_check(suffix)

    if suffix in _EXCEL_SUFFIXES:
        if sheet is not None:
            try:
                book = pd.ExcelFile(p)
            except Exception as exc:  # noqa: BLE001
                raise DataError(f"Could not open the workbook: {exc}") from exc
            try:
                df = pd.read_excel(book, sheet_name=sheet)
                warnings = [f"Read the '{sheet}' sheet of '{p.name}'."]
                _warn_title_or_merged_header(df, warnings, p)
            except ValueError as exc:
                raise DataError(
                    f"Sheet '{sheet}' was not found. Available sheets: "
                    f"{', '.join(str(s) for s in book.sheet_names)}.",
                ) from exc
        else:
            df, warnings = _read_excel(p)
    elif suffix in _CSV_SUFFIXES:
        df, warnings = _read_text(p)
    elif suffix in _JSON_SUFFIXES or suffix in _JSONL_SUFFIXES:
        df, warnings = _read_json(p)
    elif suffix in _STATA_SUFFIXES:
        df, warnings = _read_stata(p)
    elif suffix in _SPSS_SUFFIXES:
        df, warnings = _read_spss(p)
    else:  # pragma: no cover - _suffix_check already refused
        raise DataError(f"Unsupported file type '{suffix}'.")

    if df.shape[0] == 0:
        raise DataError(
            "The file contains no data rows.",
            hint="Check the file has at least one row of data below the header.",
        )
    _reject_if_no_usable_rows(df, p)
    warnings.extend(_check_structure(df, p))
    return df, warnings


def preview_text(
    df: pd.DataFrame,
    rows: int = 6,
    max_col_width: int = 28,
    max_cols: int = 12,
) -> str:
    """Human-friendly preview: shape + first rows (truncated for width)."""
    n, m = df.shape
    shown = df.head(rows)
    cols = list(df.columns)[:max_cols]
    truncated_col = m > max_cols
    header = " | ".join(str(c) for c in cols) + (" | …" if truncated_col else "")
    lines = [f"{n} rows x {m} columns", "", "Columns: " + ", ".join(map(str, df.columns))]
    lines.append("")
    lines.append(header)
    for _, row in shown.iterrows():
        cells: list[str] = []
        for c in cols:
            v = row[c]
            text = "" if pd.isna(v) else str(v)
            if len(text) > max_col_width:
                text = text[: max_col_width - 1] + "…"
            cells.append(text)
        lines.append(" | ".join(cells) + (" | …" if truncated_col else ""))
    return "\n".join(lines)
