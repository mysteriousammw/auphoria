# Quickstart — 15 minutes to your first analysis

This page takes you from "nothing installed" to a completed, report-ready
analysis in about 15 minutes. Pick your platform below.

=== "macOS"

    1. **Install Python 3.10–3.12** if you don't have it. On a Mac, the
       easiest is [Homebrew](https://brew.sh):
       ```bash
       brew install python@3.11
       ```
    2. **Install `pipx`** (isolates the tool so it never breaks your other
       Python):
       ```bash
       brew install pipx
       pipx ensurepath
       ```
    3. **Install AUPHORIA**:
       ```bash
       pipx install git+https://github.com/mysteriousammw/auphoria
       ```
    4. **Check it works**:
       ```bash
       auphoria --version
       auphoria doctor
       ```

=== "Windows"

    1. **Install Python 3.10–3.12** from [python.org](https://python.org).
       Tick **"Add Python to PATH"** during install.
    2. **Install `pipx`** in PowerShell (run as your normal user):
       ```powershell
       py -m pip install --user pipx
       py -m pipx ensurepath
       ```
       Close and reopen PowerShell so `pipx` is on your PATH.
    3. **Install AUPHORIA**:
       ```powershell
       py -m pipx install git+https://github.com/mysteriousammw/auphoria
       ```
    4. **Check it works**:
       ```powershell
       auphoria --version
       auphoria doctor
       ```

=== "Linux / WSL"

    1. **Install Python 3.10–3.12** (Ubuntu/Debian):
       ```bash
       sudo apt update && sudo apt install -y python3.11 python3.11-venv
       ```
       (On WSL, run these inside your WSL terminal.)
    2. **Install `pipx`**:
       ```bash
       sudo apt install -y pipx
       pipx ensurepath
       ```
    3. **Install AUPHORIA**:
       ```bash
       pipx install git+https://github.com/mysteriousammw/auphoria
       ```
    4. **Check it works**:
       ```bash
       auphoria --version
       auphoria doctor
       ```

=== "No-install (uv)"

    With [uv](https://docs.astral.sh/uv/) you can run AUPHORIA **without
    installing anything**:
    ```bash
    uvx --from git+https://github.com/mysteriousammw/auphoria auphoria
    ```
    On Windows, use `uvx` the same way inside PowerShell or WSL.

=== "Install locally (developers)"

    If you are developing AUPHORIA itself (or prefer an editable install
    from a source tree), clone the repository and install it in editable
    mode:
    === "macOS / Linux / WSL"
        ```bash
        git clone https://github.com/mysteriousammw/auphoria
        cd auphoria                 # the folder with pyproject.toml
        python3.11 -m venv .venv
        .venv/bin/pip install -e .
        .venv/bin/auphoria --version
        ```
    === "Windows"
        ```powershell
        git clone https://github.com/mysteriousammw/auphoria
        cd auphoria
        py -3.11 -m venv .venv
        .venv\Scripts\pip install -e .
        .venv\Scripts\auphoria --version
        ```

## Google Colab (no install on your laptop)

If you don't want to install anything at all, run AUPHORIA in Google Colab's
free notebook — it already has Python and the scientific stack. Click the
button to open it directly in Colab:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/mysteriousammw/auphoria/blob/main/notebooks/auphoria_colab.ipynb)

1. The notebook opens in Colab (see also **File ▸ Open notebook ▸ GitHub** →
   `mysteriousammw/auphoria`).
2. **Run the install cell** (first cell). Colab's environment is not disturbed.
3. **Upload your file** with the button, pick the analysis, and press **RUN**.
4. A **download** cell saves your results as a `.zip` (report + figures + CSV
   tables).

!!! warning "Download before you leave"
    Free Colab runtimes idle-disconnect after ~90 minutes and are wiped on
    restart. Download your results archive before walking away
    (see `docs/colab-notes.md`).

## Your first run

Now that AUPHORIA is installed, let's do a real analysis on the sample data it
ships with.

=== "Guided (recommended)"

    Just run it and press Enter through the questions:
    ```bash
    auphoria
    ```
    You'll be asked for a data file. Use the bundled example by pointing at the
    sample path if you know it, or follow these steps:
    1. When asked for a path, type `plant_growth.csv` from the samples (or the
       absolute path shown in `auphoria sample`).
    2. Confirm each column's type with Enter (it guesses right).
    3. Answer **"What do you want to know?"** with `2` (Compare groups).
    4. Pick `ttest` from the analysis menu.
    5. Pick `height_cm` as the outcome and `treatment` as the group.
    6. Press Enter to accept defaults, then confirm.
    7. See the results, and choose to open the folder.

=== "Command line (one line)"

    To see what's available:
    ```bash
    auphoria list
    auphoria sample
    ```
    Then run one analysis non-interactively:
    ```bash
    auphoria run --data survey.csv --analysis ttest --outcome score --group group
    ```
    Results are written to `~/AUPHORIA_results/` (open the latest folder and
    look at `report.html`).

=== "Demo (no file needed)"

    Every built analysis has a self-contained demo you can run on bundled
    synthetic data:
    ```bash
    auphoria demo --analysis ttest
    ```

## What's in a results folder

Each run writes a new timestamped folder under `~/AUPHORIA_results/` (or your
`AUPHORIA_RESULTS_ROOT`):

- `report.html` — the full, single-file report (open it in any browser).
- `run.json` — machine-readable results + all decisions + the random seed.
- `methods.txt` — a paste-ready methods paragraph for your thesis.
- `*.csv` — every result table.
- `*.png` — every figure.
- `replay.sh` / `replay.ps1` — the exact command to re-run and reproduce it.

## What's next

- [Which analysis should I choose?](choose.md) — the plain-language decision guide.
- [Browse every analysis](analyses/index.md).
- [Troubleshooting](troubleshooting.md) if anything above hiccups.