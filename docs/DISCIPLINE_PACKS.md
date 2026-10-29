# Discipline packs — optional installs

AUPHORIA's core install is deliberately light: numpy, pandas, scipy,
matplotlib and the small CLI/report stack. Everything heavier — survival,
PCA, clustering, ML evaluation, RNA-seq, experimental designs and the other
specialised analyses — lives in one of the optional **discipline packs**.
Each pack is a `pyproject` "extra": installing the pack pulls in that
discipline's heavy dependencies *and* unlocks its analyses.

The `https://github.com/mysteriousammw/auphoria` below is replaced with the real repository address
after upload (`scripts/set_repo_url.py`).

## Install syntax

One pack, inside the virtualenv where AUPHORIA is installed:

```bash
pip install "auphoria[health] @ git+https://github.com/mysteriousammw/auphoria"
```

Several packs at once:

```bash
pip install "auphoria[health,agri-animal] @ git+https://github.com/mysteriousammw/auphoria"
```

Windows PowerShell:

```powershell
py -m pip install "auphoria[health] @ git+https://github.com/mysteriousammw/auphoria"
```

If you are developing from a local source tree, the same extras install with
editable mode:

```bash
.venv/bin/pip install -e ".[health]"          # or -e ".[health,agri-animal]"
```

## The five packs

Run `auphoria packs` for the live list (with per-pack install commands), or
`auphoria list --pack <name>` to see an installed pack's analyses.

| Pack | Analyses it adds | Heavy dependencies |
|------|------------------|--------------------|
| `agri-animal` | CRD, RCBD, Latin square, split-plot, factorial designs, mean separation (Tukey, LSD, Duncan), heritability & variance components, growth curves, feed-trial designs | statsmodels, scikit-learn |
| `life-science` | dose-response, qPCR relative quantification, enzyme kinetics, RNA-seq differential expression (PyDESeq2), enrichment | statsmodels, scikit-learn, PyDESeq2, gseapy |
| `health` | 2x2 epidemiology tables (RR/OR), diagnostic accuracy, meta-analysis, Kaplan-Meier survival | statsmodels, scikit-learn |
| `social` | Likert scale handling, confirmatory factor analysis, structural equation basics, inter-rater agreement | statsmodels, scikit-learn |
| `econ-eng` | regression with robust errors, panel data, instrumental variables, curve fitting, error propagation | statsmodels, scikit-learn |

## How the guard works

Every analysis's manifest may carry two extra fields:

```yaml
pack: health               # which optional pack ships it
requires: [statsmodels]    # heavy modules it needs, installed by the pack
```

When you run an analysis whose `requires` are not importable, AUPHORIA refuses
**before** running and prints the exact command to install the pack — no raw
`ImportError`, no half-computed results:

```
A package this analysis needs is not installed.
  The analysis needs: statsmodels. Install the 'health' pack to get these:
  pip install "auphoria[health] @ git+https://github.com/mysteriousammw/auphoria"
```

`auphoria doctor` reports which packs are fully present and which are missing
dependencies (informational — the core install always works).

## Design notes (see docs/DECISIONS.md)

- Heavy dependencies stay inside their own extra so `pip install auphoria`
  stays light and fast; a student installs only the packs they use.
- The `pack`/`requires` fields on each manifest keep the mapping next to the
  analysis it describes; `packs/packs.yaml` holds the canonical pack list and
  its dependency sets, and `catalog/analyses.yaml`'s `pack` field records the
  roadmap membership.