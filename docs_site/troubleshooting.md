# Troubleshooting

Common problems and how to fix them. If your issue isn't here, run
`auphoria doctor` (it checks Python version, required libraries, and the
results folder) and include its output when you ask for help.

## Installation

### `auphoria: command not found`

The console script isn't on your PATH. After installing, run
`pipx ensurepath` and reopen your terminal. If you installed into a venv,
use the full path:

=== "macOS / Linux / WSL"
    ```bash
    .venv/bin/auphoria --version
    ```
=== "Windows"
    ```powershell
    .venv\Scripts\auphoria --version
    ```

### `auphoria doctor` reports Python out of range

AUPHORIA supports **Python 3.10–3.12**. You have something else. Install a
supported Python (3.11 is a safe choice) and reinstall AUPHORIA under it. See
the [Quickstart](quickstart.md) for per-platform commands.

### `magic-command did not find module auphoria` / no module named `auphoria`

The package isn't installed (or the editable install's `.pth` points at a
deleted clone). Reinstall:

```bash
pip install -e ".[dev]"      # from the real repo folder, not a copy
```

### An analysis says it needs a package that "isn't installed"

This is the discipline-pack dependency guard. Advanced analyses (survival,
PCA, ML, mixed-effects, ...) need heavier libraries (statsmodels,
scikit-learn) that are **not** part of the lightweight core install. Install
the relevant pack:

```bash
pip install "auphoria[health] @ git+https://github.com/mysteriousammw/auphoria"
# or, if you are installing from a local source tree:
pip install -e ".[health]"
```

Run `auphoria packs` to see all packs. `auphoria doctor` reports which packs
are present.

## Paths and files

### My data file has **spaces** in its name or folder. It won't load.

AUPHORIA accepts quoted, drag-and-drop paths. Wrap the path in quotes
(most shells' drag-and-drop does this for you):

=== "macOS / Linux / WSL"
    ```bash
    auphoria run --data "/Users/me/My Thesis/data file.csv" --analysis ttest --outcome height_cm --group treatment
    ```
=== "Windows"
    ```powershell
    auphoria run --data "C:\Users\Me\My Thesis\data file.csv" --analysis ttest --outcome height_cm --group treatment
    ```

The guided form strips stray quotes automatically when you paste a path.

### My Excel file has **merged cells** and AUPHORIA complains.

Excel files with merged cells or multi-row headers need tidying first. AUPHORIA
expects a **flat, one-row header** table with no merged title rows. In Excel:
1. Unmerge any merged header cells (Home → Merge & Center → Unmerge).
2. Delete empty title rows above the header.
3. Delete rows used for notes below the data.
4. Save as **.xlsx** or "CSV (Comma delimited)".

AUPHORIA never silently drops or "fixes" your data — so a messy file is
refused with a plain reason rather than misunderstood.

### My CSV uses semicolons or tabs instead of commas.

AUPHORIA sniffs the delimiter automatically and **tells you** when it is not a
comma. It handles `;` `|` and tab. If a cell contains a stray delimiter, the
row count won't match the header and you'll get a plain warning naming the
problem.

### "This analysis needs a column for 'X' but none was provided."

One of the required inputs didn't get a column. Pass it by name:
```bash
auphoria run --data data.csv --analysis cox-regression --outcome time \
  --extra event=event_col --extra covariate=age
```
Run `auphoria info <analysis-id>` to see exactly which inputs an analysis
needs.

## Results

### My results folder is full of files — where do I look first?

Open the newest folder under `~/AUPHORIA_results/` and start with
`report.html`. Everything is also written as separate `.csv`, `.png`,
`methods.txt`, and `run.json` files.

### "Something unexpected went wrong" (EngineError)

Check `log.txt` inside that run's folder for the technical traceback, then
[report it](known-issues.md) with the log and the exact
command. Include the output of `auphoria doctor`.

### My results differ between two runs.

Unless you changed the input or seed, they shouldn't. Every run records its
random seed and replay command; running `replay.sh` reproduces the numbers
exactly. If two runs of the *same* command on the *same* file differ, that is a
bug — please report it.

### `auphoria doctor` says results folder isn't writable

AUPHORIA writes to `~/AUPHORIA_results/` by default. Point it elsewhere with
the environment variable:
```bash
export AUPHORIA_RESULTS_ROOT=/path/to/a/writable/folder
```

## Google Colab

### The notebook's install cell fails.

Make sure you're running the **first cell** and that Colab is online to fetch
the package. If you loaded the notebook from a local copy, prefer the
repository's hosted notebook (`https://github.com/mysteriousammw/auphoria`) so the install cell gets
the right source.

### I lost my results in Colab.

Free Colab runtimes idle-disconnect (~90 minutes) and are wiped. **Download the
results `.zip` before leaving** — see `docs/colab-notes.md`. There is no
server-side copy.

## Still stuck?

1. Run `auphoria doctor` and note the output.
2. Find the exact `auphoria run ...` command you used.
3. Include both in your report (the [wrong-result template](known-issues.md)
   is a good skeleton).