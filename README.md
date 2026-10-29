# AUPHORIA

**AUPHORIA** is a free, open-source tool that lets university students run
real data analyses **without programming**. You have a data file and a
research question; AUPHORIA asks what your columns mean, offers a menu of
analyses that fit your data, runs the test, and saves a full report — on
**your own computer** or in **Google Colab**. No AI, no accounts, no API
keys, no telemetry, and it works fully offline after installation.

Built for BS, MPhil and PhD students and their supervisors in agriculture,
animal and life sciences, health, psychology and social sciences, education,
economics, engineering, environmental science and computer science.

> **Independent project.** AUPHORIA is an independent, community-maintained
> open-source project. It is not an official initiative of any university,
> department, funding body, or institution. See
> [CONTRIBUTING.md](CONTRIBUTING.md) for who maintains it.

---

## Quick start

> Requires **Python 3.10 to 3.12** and (for `pipx`) the
> [`pipx`](https://pipx.pypa.io/stable/install/) installer. Open a terminal
> (Terminal on macOS, Terminal/Command Prompt in **WSL**, or **PowerShell** on
> Windows) and paste **one** line. These commands install AUPHORIA from its
> repository and make the `auphoria` command available.

**Linux / macOS / WSL**

```
pipx install git+https://github.com/mysteriousammw/auphoria
```

**Windows PowerShell**

```
py -m pipx install git+https://github.com/mysteriousammw/auphoria
```

**No-install form (uv)** — if you have
[`uv`](https://docs.astral.sh/uv/), you can run AUPHORIA without installing
anything:

```
uvx --from git+https://github.com/mysteriousammw/auphoria auphoria
```

> On Windows `uvx` works the same way inside PowerShell or WSL.

### Until the repository is published

The `https://github.com/mysteriousammw/auphoria` above is replaced with the real address in a later
step (see `docs/PUBLISH_CHECKLIST.md`). Until then, install **locally** from
the source tree:

```
cd auphoria                     # the folder with pyproject.toml
python -m venv .venv            # Python 3.10, 3.11 or 3.12
.venv/bin/pip install -e .      # Windows: .venv\Scripts\pip install -e .
.venv/bin/auphoria --version    # Windows: .venv\Scripts\auphoria --version
.venv/bin/auphoria doctor
```

`pip install -e .` installs AUPHORIA in editable ("development") mode so the
code on disk is exactly what you run. This is only for the local build; once
the repository is public, use the `pipx` / `uvx` commands above.

### Optional discipline packs

The core install is deliberately light (numpy, pandas, scipy, matplotlib,
...). Specialised, heavier analyses (survival, PCA, ML, RNA-seq, designs, ...)
live in optional **discipline packs** — each is a `pyproject` "extra" and its
heavy dependencies install with it. Add the packs you need:

```bash
# Linux / macOS / WSL (inside the same venv where AUPHORIA is installed):
pip install "auphoria[health] @ git+https://github.com/mysteriousammw/auphoria"
pip install "auphoria[agri-animal] @ git+https://github.com/mysteriousammw/auphoria"
```

**Windows PowerShell**

```powershell
py -m pip install "auphoria[health] @ git+https://github.com/mysteriousammw/auphoria"
```

Available packs: `agri-animal`, `life-science`, `health`, `social`, `econ-eng`.
Install several at once with `auphoria[health,agri-animal]`. See
`docs/DISCIPLINE_PACKS.md` for exactly which analyses each pack adds. If you
try an analysis whose pack isn't installed, AUPHORIA tells you the exact
command to run instead of crashing — `auphoria packs` lists them all, and
`auphoria list --pack health` shows a pack's analyses.

**Locally (before publishing)** the same extras install from the source tree:

```bash
.venv/bin/pip install -e ".[health]"
```

The `https://github.com/mysteriousammw/auphoria` is replaced with the real address after upload
(see `docs/PUBLISH_CHECKLIST.md`).

---

## Start with the guided form

Type:

```
auphoria
```

AUPHORIA will:

1. Ask for the path to your data file (CSV, TSV/TXT, or Excel).
2. Preview it and confirm what each column is (numeric / categorical /
   date / text).
3. Offer a menu of analyses that fit your data.
4. Ask for the options (which column is the outcome, which is the group, a
   significance level, and so on).
5. Run it, explain the results, and save everything.

---

## One-line form (for people who know what they want)

```
auphoria run --data PATH --analysis ID --outcome COL --group COL
```

Examples:

```
auphoria run --data plant_growth.csv --analysis ttest --outcome height_cm --group treatment
auphoria run --data survey.csv --analysis correlation --extra x=hours_studied --extra y=score
auphoria run --data height.csv --analysis summary --outcome height_cm
```

Try it on the bundled sample data:

```
auphoria sample
auphoria run --data ./plant_growth.csv --analysis ttest --outcome height_cm --group treatment
```

### Available analyses (maturity: experimental)

| ID            | Name                        | What it does                                   |
|---------------|-----------------------------|------------------------------------------------|
| `summary`     | Descriptive summary         | Mean, median, SD, quartiles; counts/percentages|
| `ttest`       | Independent-samples t-test  | Compare a numeric outcome across two groups    |
| `correlation` | Pearson correlation         | Strength/direction of a linear relationship    |

List all analyses and their details with:

```
auphoria list
auphoria info ttest
```

---

## Where results are saved

Results are written **on your computer**, by default into:

```
~/AUPHORIA_results/<dataname>_<analysis>_<timestamp>/
```

(That is your home folder, `C:\Users\<you>\AUPHORIA_results\...\` on Windows
too.) Every run writes:

| File            | Contents                                                           |
|-----------------|--------------------------------------------------------------------|
| `report.html`   | One self-contained, human-readable report                         |
| `methods.txt`   | Paste-ready methods paragraph for a paper                          |
| *.csv           | Result tables                                                      |
| *.png           | Figures                                                            |
| `run.json`      | Everything needed to reproduce the run                             |
| `replay.sh` / `replay.ps1` | Exact command to re-run and get the same numbers       |
| `log.txt`       | Every decision made, plus any technical traceback                  |

The exact folder is printed at the end of every run, and AUPHORIA offers to
open it.

---

## Reproducibility & honesty by design

- AUPHORIA **never silently drops, changes, or imputes your data.** If a
  value is missing, it counts it and tells you. If a test would be harmed,
  it refuses and explains why in plain English.
- Every run records the package versions, the random seed, the resolved
  parameters, and a SHA-256 of your input file.
- A test warns or refuses when it does not fit your data or design — it
  never quietly runs something meaningless.

---

## Run in Google Colab (no install on your laptop)

1. Open the notebook: `https://github.com/mysteriousammw/auphoria` → `notebooks/auphoria_colab.ipynb`
   (or run directly in Colab from the same link).
2. Run the install cell, upload your file with the button, pick the analysis
   and columns, click **Run**, and a zip of your results downloads to your
   laptop.

> **Privacy note for Colab:** the notebook runs on Google's servers. Any
> file you upload goes to Google's temporary runtime and is deleted when the
> session ends, but you should not upload confidential data there. Your
> laptop is the private option.

---

## Installing from source / developing

```
git clone https://github.com/mysteriousammw/auphoria
cd auphoria
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/auphoria
```

Every analysis is its own module under `src/auphoria/analyses/<id>/` with a
`manifest.yaml`, `analysis.py`, `README.md` and `tests/`. Add a new analysis
by copying an existing one — the engine picks it up from the manifest.

---

## License

AUPHORIA's licence is **not yet chosen** — see
[docs/LICENCE_DECISION.md](docs/LICENCE_DECISION.md) for the options and
trade-offs, which the maintainer will decide before publication. Research-grade
scientific computing libraries (NumPy, pandas, SciPy, Matplotlib) power the
analyses. Analysis maturity is always marked — nothing in AUPHORIA is labeled
"validated".

## Contributors and credits

AUPHORIA was conceived and directed by the people below. Full credits and
how to be listed are in [CONTRIBUTORS.md](CONTRIBUTORS.md).

- **Abdul Momin Muhammad Wisal** — MPhil researcher; Founder, Research
  Solution. Project lead: developed the idea into a concept, defined the
  requirements and the student experience, and directed the build.
- **Dr. Ihtesham Ul Haq** — Assistant Professor. Originator of the AUPHORIA
  idea; reviewed and supervised the project.
- **Dr. Sher Hayat Khan** — Associate Professor; PhD, China Agricultural
  University, Beijing. Reviewed and supervised the project.
- **Ahmad Farid Moheb** — MPhil researcher. Helped refine the AUPHORIA idea
  and tested it.
- **Mudassir Anayat** — MPhil research student. Helped refine the AUPHORIA
  idea and tested it.

> **AI assistance.** AI tools helped create this project. All results the
> software produces come from deterministic open-source libraries, not from an
> AI model. Maintainers are responsible for the content and for checking it.
> See [CONTRIBUTORS.md](CONTRIBUTORS.md) for the "AI assistance" section.

## Limitations

AUPHORIA is a teaching and analysis tool, not a substitute for statistical
judgement. In particular:

- Every analysis is tagged with its **maturity**; analyses outside their
  intended conditions show a "needs expert review" notice in the report.
- The tool checks assumptions and warns rather than silently doing something
  meaningless, but some checks need a statistician's (or your supervisor's)
  judgement.
- Results depend on the quality of the input file; AUPHORIA refuses or flags
  problems it can detect but cannot repair a poorly designed study.
- AUPHORIA does **not** certify your science — a report here is a starting
  point for discussion with a supervisor or statistician, not a publication
  ready-made.

## Citation

If you use AUPHORIA in your work, please cite it (APA style):

> Wisal, A. M. M., Haq, I. U., Khan, S. H., Moheb, A. F., & Anayat, M.
> (2026). *AUPHORIA: Beginner-friendly data analysis for university students
> who cannot code* (Version 0.1.0) [Computer software].
> `https://github.com/mysteriousammw/auphoria`

The full author/credit metadata is in [CITATION.cff](CITATION.cff) and all
contributors are listed in [CONTRIBUTORS.md](CONTRIBUTORS.md). Project
contact: `ammw@aup.edu.pk`.

## Acknowledgements

AUPHORIA is built on NumPy, pandas, SciPy, Matplotlib, PyYAML, Typer,
Pydantic and Jinja2 — see [docs/ACKNOWLEDGEMENTS.md](docs/ACKNOWLEDGEMENTS.md)
for the full list and licences.

## Contributing & security

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) and the
[Code of Conduct](CODE_OF_CONDUCT.md). Contributors are credited in
[CONTRIBUTORS.md](CONTRIBUTORS.md).