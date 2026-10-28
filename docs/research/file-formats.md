# Data file formats AUPHORIA reads (and the two it does NOT)

Verified locally in this environment on 2026-10-24 by actually writing each
format and reading it back with the reader AUPHORIA would use. "Py3.10 OK"
means the reader library resolves under `pip --dry-run --python-version 3.10`.

## Formats we support (version 1)

| Format | Extension | How we read it | Reader lib | Py3.10 OK | Notes |
|---|---|---|---|---|---|
| Comma-separated | `.csv` | `pandas.read_csv(sep=None, engine="python")` — auto-sniffs delimiter | pandas | ✓ | default / primary format |
| Tab-separated | `.tsv`, `.tab`, `.txt` (tabular) | same sniff path | pandas | ✓ | a tabular `.txt` is treated as TSV |
| Excel workbook | `.xlsx`, `.xlsm` | `pandas.read_excel` (reads first sheet) | openpyxl | ✓ | optional extra `auphoria[excel]` |
| Excel legacy | `.xls` | `pandas.read_excel` | xlrd (2.x) | ✓ | **NOT supported in v1**; see below |
| OpenDocument spreadsheet | `.ods` | `pandas.read_excel(engine="odf")` | odfpy | ✓ (pure-python 1.4.1) | optional — small extra |
| Stata | `.dta` | `pandas.read_stata` | pandas | ✓ | common for survey/social-science data |
| JSON (tabular) | `.json` | `pandas.read_json` | pandas | ✓ | only if it is a table of records |
| SPSS | `.sav` | `pyreadstat.read_sav` | pyreadstat | ✓ (1.3.6) | optional — common in psych/social theses |

All of the above were **verified to round-trip** (write → read → correct shape/
values) locally. Encoding falls back to UTF-8 → cp1252/latin-1 with a visible
warning (see Phase 1 adapters) rather than a silent garble.

## Formats students genuinely use but we do NOT read in v1

Two are called out because they are the *most common way* non-coding students
store data and the most misunderstood:

- **Word (.docx/.doc) — NOT a data source.**
  Word documents are not tabular data; they are text documents in which a
  table may be *embedded*. Reading analysis out of a Word file is unreliable
  and error-prone (merged cells, page breaks, captions interleaved with rows).
- **PDF (.pdf) — NOT a data source.**
  PDFs are a *presentation* format (for sharing, not analysis). Tables in a
  PDF have no guaranteed machine-readable structure (text may be reflowed,
  split across columns/pages).

### What to tell a student whose data is in a Word table or a PDF

Say, in plain English:

> "Your data needs to be in a 'table' file that a program can read reliably —
> like a spreadsheet or a CSV. AUPHORIA reads CSV, TSV/TXT, Excel (.xlsx), .ods,
> Stata .dta, SPSS .sav and JSON. It does **not** read Word or PDF files,
> because those are documents, not data tables, and reading numbers out of them
> often goes wrong.
>
> The quickest fix:
> 1. Open your Word document (or the PDF with Word/Excel or a reader).
> 2. Select the table inside it, copy it, and paste it into Excel.
> 3. Save that workbook as ''.xlsx'' — or use Excel's *File → Save As → CSV
>    (Comma delimited)* to get a ''.csv''.
>
> Then point AUPHORIA at that file. If it is a very large table in a PDF that
> you cannot copy-paste type, ask whoever created it for the original
> spreadsheet — it almost always exists."

Rationale for v1: Word/PDF parsing would add heavy, fragile dependencies
(python-docx, pdfplumber/pyPDF) with low reliability and would conflict with
the "never silently change data" guardrails. Pasted-and-saved-to-.xlsx is a
simple, dependable path for every student.

## Which to recommend as the default

- **Always prefer the CSV if you can.** Small, universal, no optional
  dependency, opens in Excel, no risk of hidden formatting corrupting values.
- **Excel .xlsx if your data already lives in a workbook** (and you want
  multiple sheets; we read the first).
- **.sav /.dta for psychology/social-science theses** that received their data
  in SPSS/Stata — we support them via optional extras so those students are
  not stuck, but we recommend exporting to CSV where possible.
- For anything you cannot read, present the Word/PDF guidance above and keep
  the student moving without silently mangling their data.