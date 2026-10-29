# AUPHORIA — progress

Live status of the build. Updated at the end of every phase: what is done,
what is next, and known problems.

---

## Post-publication audit pass (2026-10-30)

The working tree was already published and green (see "Public repository
check" below). A clean-up pass fixed the remaining inconsistencies without
changing behaviour:

- `_load_sample_for(name)` in `cli/main.py` now honours `name` (it previously
  always returned the first sample) — the Phase 6 known limitation is gone.
- Removed the now-false "until the repository is published" / "before
  publishing" / placeholder-substitution text from README, the docs site
  (quickstart, index, troubleshooting), docs/DISCIPLINE_PACKS.md,
  docs/colab-notes.md, mkdocs.yml and packs.yaml (the repo is public).
- `docs_site/index.md` platform links now point at real anchors
  (`quickstart.md#macos` etc.); enabled tabbed `slugify` in mkdocs.yml so the
  tabs generate readable anchors.
- README "Available analyses" table now lists all 19 built analyses (was 3).
- Renamed the stale marker test in `tests/test_docs_phase11.py` to assert the
  real repository URL instead of a removed `TODO-VERIFY` marker.
- `tests/test_notebook.py` names/docstrings updated ("placeholder" → "repo").

Verified after the changes: ruff clean, `pytest` **359 passed** (no
regression), and the mkdocs build exits 0 with **zero WARNING/ERROR lines**.

Full rationale in `docs/DECISIONS.md` ("Post-publication audit pass").

---

## Phase 12 — Release preparation (DONE, 2026-10-29)

### What is done
Everything needed to release 0.1.0 — prepared and verified, but NOT
published or tagged (per the phase instruction).

- **Version 0.1.0** pinned in `core/version.py`.
- **CHANGELOG** consolidated from the per-phase "Unreleased" sections into a
  single **`[0.1.0] - 2026-10-29`** entry (phase subsections + known
  limitations); `[0.1.0]: https://github.com/mysteriousammw/auphoria` link kept for set_repo_url.
- **Release workflow** (`.github/workflows/release.yml`): tag-triggered
  `v*` + workflow_dispatch. `verify-tag` job (tests, ruff, validation +
  analysis-docs `--check`, docs build, `--version`+`doctor` smoke) →
  `build` (sdist+wheel) → `release` (drafts a GitHub Release with CHANGELOG
  notes + artifacts). Draft-only: nothing publishes without a human.
- **Module template + `auphoria new-module` command**
  (`cli/scaffold.py` + `cli/templates/analysis/`): scaffolds
  manifest/analysis/README/tests for a new analysis, registers it in the
  catalogue (sync test stays green), and the skeleton is ruff-clean, passes
  its own tests, and is discoverable. Templates ship in the wheel.
  `tests/test_new_module_phase12.py` (5 tests).
- **PR template** + **general bug-report issue template** alongside the
  existing wrong-result template.
- **Pilot checklist** (`docs/pilot/pilot-checklist.md`): 3–5 students run the
  tool from README only, per-row "what went wrong" form, ship gate.
- **CONTRIBUTING.md**: **Maintainers** + **Succession** sections.
- **CITATION.cff**: complete except personal details (placeholders left);
  date bumped to the release date.
- **`docs/PUBLISH_CHECKLIST.md`** re-checked and corrected against the build
  (release workflow, pilot gate, docs_site/mkdocs URL, validation checks).
- `tests/test_release_phase12.py` (8 tests) pinning all of the above.

### Verified
- `pytest` → **359 passed**; `ruff check src/ tests/ scripts/` clean.
- Validation dashboard + 19 analysis pages current (`--check`); docs build
  has no warnings.
- `auphoria new-module` end to end: scaffold → ruff clean → own tests pass →
  discoverable → catalogue sync green (all covered by tests).

### What is next
- Run the **pilot** (PUBLISH_CHECKLIST step 10), then tag `v0.1.0` and let
  the release workflow draft the release. Nothing is published from this
  build.

### Known problems
- All 19 analyses remain `maturity: experimental` (no human reviewer yet).
- `_load_sample_for(name)` returns the first sample regardless of `name`
  (`cli/main.py:305`) — example-command column picker only.

## Phase 11 — Docs site & demo script (DONE, 2026-10-29)

### What is done
A MkDocs Material documentation site (in `docs_site/`) plus a reproducible
demo-video script. The site builds cleanly with zero warnings (acceptance).

- **MkDocs Material site** (`mkdocs.yml`, `docs_dir: docs_site/`): home,
  15-minute quickstart, "which analysis do I choose?", one plain page per
  analysis, gallery, troubleshooting, FAQ, responsible use, validation,
  discipline packs, decision guide, and known issues.
- **Quickstart** covers macOS / Windows / Linux+WSL / **Google Colab**
  (no-install) / uv, each with platform-tabbed command blocks. Every install
  command uses `https://github.com/mysteriousammw/auphoria` and is marked TODO-VERIFY until the repo
  is published.
- **"Which analysis do I choose?"** (`choose.md`) turns the advisor's decision
  guide into a plain-language page (describe / compare / relate / predict /
  reduce), with the full decision guide included from `docs/research/`.
- **One plain page per analysis** generated by
  `scripts/gen_analysis_docs.py` (19 pages, checked-in, regenerable): what it
  does, inputs, options, assumptions, limitations, known issues, run command.
- **Troubleshooting** (install problems, paths with spaces, Excel merged
  cells, delimiter sniffing, missing-input errors, Colab data loss),
  **FAQ**, **gallery** (which demos to run + what each report shows),
  **responsible use** ("this tool does not certify your science").
- **Demo-video scripts**: `scripts/demo_video_script.md` (timed narration +
  shot list) and `scripts/demo_video.py` (runs the exact demo steps against
  the real tool).
- **`scripts/build_docs.sh`** — builds the site and fails on any WARNING/ERROR
  (encodes the acceptance criterion; silences the vendor EOL banner via
  `NO_MKDOCS_2_WARNING=1`).
- **`tests/test_docs_phase11.py`** (5 tests): `mkdocs build` has no warnings,
  required pages exist, analysis docs are current, install blocks use the
  placeholder + TODO-VERIFY, demo-video scripts exist.
- New `docs` extra (`mkdocs`, `mkdocs-material`, `mkdocs-include-markdown`);
  added mkdocs deps to `dev` so the site builds in the dev env.

### Verified (acceptance)
- `pytest` → **346 passed**; `ruff check` clean.
- `NO_MKDOCS_2_WARNING=1 python -m mkdocs build` exits 0 with **zero
  WARNING/ERROR lines** (acceptance: "docs build without warnings"); enforced
  by `build_docs.sh` and a test.
- The MkDocs include plugin (`{% include "../../docs/..." %}`) embeds the
  validation / discipline-pack / decision-guide / known-issues content into the
  site at build time; verified the rendered pages contain that content.
- `scripts/demo_video.py` runs all demo steps end-to-end against the real
  tool (respects `AUPHORIA_RESULTS_ROOT`).

### What is next
- Promote analyses to `tested` once the docs make their intended use clear;
  add a docs search index / analytics only after the repo URL is set.
- Record the demo video and embed it in the gallery.

### Known problems
- `site_url` / `repo_url` in mkdocs.yml use the real address
  (mkdocs requires a scheme; set_repo_url.py substitutes it at publish time —
  PUBLISH_CHECKLIST step 3).

---

## Public repository check (DONE, 2026-10-29)

### What is done
A read-only check of the live public repository (nothing pushed or changed
there).

- **`scripts/check_public_repo.py <repo-url>`** — shallow-clones the repo to a
  temp dir, then: compares the expected public files (and flags anything that
  should not be public: results/venv/caches/>5MB/data/secrets/paths/emails),
  confirms the `REPO_URL` placeholder is gone and the README install commands,
  Colab link and CITATION.cff all carry the real address; checks CONTRIBUTORS
  + README credits and that no confirm-role or TODO-VERIFY markers remain; runs a
  FRESH-venv install (README pipx/pip git+ command), `--version`, `doctor`,
  `demo`, and `pytest`; executes the Colab notebook top-to-bottom with the
  google.colab stub; validates the workflow YAML and reports whether GitHub
  Actions is enabled.
- **`PUBLIC_CHECK_REPORT.md`** — generated report: MISSING / WRONG /
  WARNINGS / OK + the fresh-venv install + notebook + Actions results.

### Verified against https://github.com/mysteriousammw/auphoria
- **Install test green**: fresh venv `pip install git+<url>` → `--version`
  (0.1.0), `doctor`, `demo` all PASS; `pytest` PASS (359) from the clone with
  `.[dev]`.
- **Colab notebook** executes end-to-end with the stub (download log fires).
- **GitHub Actions enabled**; all 3 workflow YAML files valid.
- No junk files, no extra emails/secrets in the clone; all 19 analysis
  folders complete; all local links resolve.
- Findings (all expected / fixable): **1 MISSING (LICENSE)**, **10 WRONG**
  (the URL placeholder still in 29 files: README install, Colab link,
  CITATION.cff url/repository-code, pyproject, engine, packs; plus
  confirm-role/TODO-VERIFY markers), **5 WARNINGS** (benign
  illustrative absolute paths in docs/tests).

### Local fixes made (ready to commit + push)
The audit exposed real bugs, fixed in the LOCAL copy:
1. `set_repo_url` could not run cleanly: `scripts/build_notebook.py` and
   `tests/test_notebook.py` used the `REPO_URL` placeholder as a Python *variable
   name* — replacing it produced a syntax error. Renamed to `_REPO_URL_MARKER`.
2. `set_repo_url` must skip its own detection/lint siblings
   (`prepare_publish.py`, `check_public_repo.py`) or it silently disables the
   checks that search for the placeholder; added them to the skip set.
3. `test_tools.py` built its fixture with the placeholder inlined, so the
   URL sweep edited it; it now reads `mod.PLACEHOLDER`.
4. Ran `python scripts/set_repo_url.py https://github.com/mysteriousammw/auphoria`
   → the placeholder is gone from every file except the tool itself; README
   install commands, the Colab link and CITATION.cff now carry the real
   address (this also converted the placeholder-asserting tests to assert the
   real URL). Full suite **359 passed**, `ruff check` clean.

### What is next
- Commit these local fixes and push (see the push list in the report handoff).
- Run `scripts/check_public_repo.py` again AFTER pushing to confirm the
  public copy is clean, then handle the user-only items (licence, actions,
  Zenodo, description/topics, person permissions, tag v0.1.0).

### Known problems
- Remaining user-only items: repo description/topics, Zenodo DOI, and tagging
  v0.1.0 (see the user-only checklist in the handoff).

---

## Publish preparation (DONE, 2026-10-29)

### What is done
A separate audit-driven publish path that never touches the working tree.

- **`scripts/prepare_publish.py`** — builds a fresh `../auphoria_publish/`
  containing ONLY the whitelisted public-repository files (omitting results,
  venvs, caches, build output, dotfiles, >5 MB files), then audits that copy
  and writes `PUBLISH_REPORT.md` with MISSING / WARNINGS / OK sections, and
  runs a **fresh-venv install test** (`pip install .`, `auphoria --version`,
  `auphoria doctor`, `auphoria demo`, `pytest`) recording each result.
- **`.gitignore`** now covers everything excluded by the copy plus `site/`
  and `*.log`.
- **Part 2 credits files**: `CONTRIBUTORS.md` (people table + AI-assistance +
  how-to-be-listed), README "Contributors and credits" + Citation +
  Limitations + independent-project statement, people-only `CITATION.cff`
  (all five people as authors),
  `docs/ACKNOWLEDGEMENTS.md` (open-source libraries + permissive licences +
  funding placeholder).

### Verified
- `../auphoria_publish/PUBLISH_REPORT.md` exists with all sections; the only
  MISSING item is **LICENSE**, which is expected (the licence is intentionally
  not yet chosen — see docs/LICENCE_DECISION.md).
- **Fresh-venv install test fully green**: `pip install .`, `auphoria --version`,
  `auphoria doctor`, `auphoria demo`, and `pytest` (after `.[dev]`) all exit 0.
- Every analysis folder ships manifest + code + README + tests; all local
  links resolve; CITATION.cff and all `.github/workflows` are valid YAML.
- README covers all required content (what it is, pipx/uvx install, first-run
  example, Colab link, results location, limitations, citation, contributors,
  independent-project statement).

### Four real bugs the publish audit caught (and fixed)
1. **Analysis manifests never shipped in the wheel** — `auphoria demo` on a
   real (non-editable) install failed with "Analysis directory 'ancova' has no
   manifest.yaml" because there was no `"auphoria.analyses" =
   ["*/manifest.yaml"]` package-data entry. The editable dev venv read them
   from the source tree, hiding the gap. Fixed in pyproject (19 now ship;
   verified via `pip wheel`).
2. **`dev` extra missing `mkdocs-include-markdown-plugin`** — fresh `.[dev]`
   + pytest failed the docs-build test ("plugin is not installed"). Plugin was
   only in `docs`; moved into `dev` too.
3. **`auphoria new-module` wrote into site-packages** on a non-editable
   install — it derived the repo root from `__file__`. Now resolves from
   `Path.cwd()` (walks up to pyproject+src) and refuses outside a source tree.
4. **Scaffold tests need `PYTHONPATH`** in subprocesses, or
   `importlib.import_module('.analyses.<id>.analysis')` resolves to
   site-packages under a non-editable install. `test_new_module_phase12.py`
   now prepends `src` in every subprocess.

### What is next
- The only email `ammw@aup.edu.pk` is cleared; the remaining WARNINGS are
  expected or benign (see the report): repo-URL and TODO-VERIFY markers are
  intentional pre-publish, and the flagged "/Users/me/My Thesis" /
  "C:\Users\Me\..." / "Student" paths are illustrative examples in docs and
  tests, not real user data. Review the report and run the pilot before
  tagging.

### Known problems
- A disk-full (`Errno 28`) hit on the first fresh-venv install test was fixed
  by clearing the failed test venv + `~/.npm`; re-runs now build clean.
- `../auphoria_publish/` is a disposable copy: re-run
  `scripts/prepare_publish.py` after any source change to refresh it.

---

## Phase 10 — Validation (DONE, 2026-10-29)

### What is done
A validation framework: every analysis is catalogued with a maturity tier,
an independent reference (fixtures), and known issues, on an auto-generated
dashboard.

- **Maturity levels** (`docs/validation/levels.md`): `experimental` → `tested`
  → `reviewed` → `validated`. The build agent may only set `experimental` or
  `tested`; `reviewed`/`validated` REQUIRE a named human reviewer in the
  manifest's `reviewer` field **and** a `reference` describing the
  cross-check.
- **Reviewer gate enforced** (`core/manifest.py::check_maturity` /
  `validate_maturity`; wired into `registry._load_manifest`): a manifest
  claiming `reviewed` or `validated` without a reviewer/reference FAILS at
  load time and fails the dashboard generator. Manifest `maturity` is now a
  validated enum (4 tiers), not free text.
- **New manifest fields**: `reviewer` (str), `reference` (str), `known_issues`
  (list) — validated by pydantic and carried through `model_dump`.
- **Reference fixtures** (`docs/validation/references.yaml`): for all 19
  analyses, the independent-reference `source`, `how_produced`, and exact
  expected `values` with tolerances, taken from each analysis's known-answer
  tests (hand-computed textbook examples + second-library reproduction via
  scikit-learn/statsmodels/SciPy; R is not a runtime dep so no R call).
- **Dashboard** (`docs/validation/dashboard.md`) generated by
  `scripts/gen_validation_dashboard.py` (regenerable, deterministic)
  from the manifests + references + known issues. The `auphoria validation`
  CLI command wraps the same generator; `--check` confirms currency.
- **Known issues** (`docs/validation/KNOWN_ISSUES.md`, grouped per analysis)
  and a **wrong-result issue template**
  (`.github/ISSUE_TEMPLATE/wrong_result.md`) whose acceptance is a recorded,
  passing independent cross-check.
- **`tests/test_validation_phase10.py`** (11 tests): reviewer gate
  (reviewed/validated without reviewer fails), allowed-level validation, all
  shipped manifests sound (agent sets only experimental/tested), every
  analysis has a reference fixture, dashboard regenerates deterministically,
  dashboard `--check` reports currency.

### Verified (acceptance)
- `pytest` → **341 passed** (was 330; +11 validation); `ruff check` clean.
- Dashboard regenerates from the script deterministically (two runs byte-
  identical); `--check` reports current; `auphoria validation` works.
- A manifest with `maturity: reviewed` and no `reviewer` fails `check_maturity`,
  fails `validate_maturity` (ConfigError), fails `registry.discover()`, and
  fails the dashboard generator — the acceptance criterion.

### What is next
- Promote analyses from `experimental` to `tested` when desired (the agent may
  set `tested`); `reviewed`/`validated` need a named human reviewer's sign-off
  recorded in the manifest.

### Known problems
- All 19 analyses are currently `experimental` (the safe default); none have
  yet been promoted to `tested` or human-`reviewed`. The fixture values come
  from the known-answer tests and second-library checks, not an R run.

---

## Phase 9 — Discipline packs: optional installs (DONE, 2026-10-29)

### What is done
Optional **discipline packs**, each a `pyproject` "extra", so the core install
stays light and a student installs only the packs they use. Heavy dependencies
(life-science: PyDESeq2/gseapy; others: statsmodels/scikit-learn) live inside
their own extra.

- **`src/auphoria/packs/packs.yaml`** — the canonical pack list (id, name,
  description, heavy `deps`) for the five packs: `agri-animal`, `life-science`,
  `health`, `social`, `econ-eng`. Loaded by `auphoria/packs/__init__.py`.
- **`pyproject.toml` extras** — one per pack (e.g. `health =
  ["statsmodels>=0.13,<1","scikit-learn>=1.2,<2"]`); `packs.yaml` ships in the
  wheel (package-data). `dev` gained statsmodels/sklearn/PyDESeq2/gseapy so the
  pack tests and analyses run locally.
- **Deps-guard** (`core/engine.py`): before running an analysis, the engine
  checks the manifest's `requires` (heavy modules) are importable; if not it
  refuses with the exact install command
  (`pip install "auphoria[<pack>] @ git+https://github.com/mysteriousammw/auphoria"`) instead of a
  raw ImportError. Fires before the analysis module even loads.
- **Manifest `pack` + `requires` fields** (validated by pydantic): each heavy
  analysis declares its pack membership (list) and required modules. Assigned
  to the 10 Phase-8 analyses (ancova, mixed-effects, pca, factor-analysis,
  clustering-kmeans, kaplan-meier, cox-regression, diagnostic-test,
  ml-classification-eval, ml-regression-eval).
- **CLI**: new `auphoria packs` (lists packs + install commands, checks deps),
  and `auphoria list --pack <name>` filters to one pack. `auphoria doctor`
  reports each pack's dependency status (informational).
- **Docs**: `docs/DISCIPLINE_PACKS.md` (exact install syntax with
  https://github.com/mysteriousammw/auphoria, per-pack analysis list, how the guard works) and a
  README "Optional discipline packs" section.
- **`tests/test_packs_phase9.py`** — pack registry, missing/requires logic,
  deps-message hints, and the CLI `packs`/`list --pack` commands.

### Verified (acceptance)
- `pytest` → **330 passed**; `ruff check src/ tests/ scripts/` clean.
- Wheel build contains `auphoria/packs/packs.yaml`.
- `auphoria packs` prints all five packs with correct install commands;
  `auphoria list --pack health` returns the health analyses;
  `auphoria doctor` reports all packs `[OK]`.
- Deps-guard verified end-to-end: with statsmodels "missing", running `ancova`
  refuses and prints the `pip install "auphoria[agri-animal] @ git+https://github.com/mysteriousammw/auphoria"`
  hint.

### What is next
- Build the pack-specific analyses listed per discipline (agri-animal designs,
  life-science dose-response/qPCR/kinetics/RNA-seq, health meta-analysis,
  social Likert/CFA/SEM/inter-rater, econ-eng robust/panel/IV/curve-fit) —
  each gets a `rules.yaml` entry and a `pack`/`requires` manifest annotation.

### Known problems
- Pack-specific analyses are not built yet; the packs currently ship the
  Phase-8 advanced analyses + the extras' heavy deps. The per-pack analysis
  lists in packs.yaml/docs describe the roadmap.

---

## Phase 8 — Advanced analyses batch (DONE, 2026-10-29)

### What is done
Ten advanced analyses (P1/P2 catalogue), each with manifest.yaml + analysis.py +
README.md + tests/ (synthetic data, scipy/statsmodels/sklearn reference,
bad-input cases, expert-review notice). All follow the advanced-analysis rule:
state assumptions and minimum sample sizes especially clearly, and flag a
prominent **"needs expert review"** notice in the report when used outside
intended conditions.

- **`ancova`** — ANCOVA: adjusted means, group F, covariate effect, partial
  eta-squared; statsmodels OLS. Expert-review on small sample / non-normal
  residuals.
- **`mixed-effects`** — linear mixed model (statsmodels MixedLM): fixed
  effects with CI/p, random variance, ICC. Expert-review on few clusters /
  small total n.
- **`pca`** — PCA (sklearn, standardised): variance-explained, loadings,
  scree + score-scatter figures. Expert-review on tiny sample / near-constant
  columns.
- **`factor-analysis`** — EFA (sklearn FactorAnalysis, varimax), KMO +
  Bartlett's test, loadings heatmap. Expert-review on small sample/KMO < 0.6.
- **`clustering-kmeans`** — k-means (sklearn, scaled): assignments, centres,
  silhouette + elbow guidance. Expert-review on weak silhouette / n < 10*k.
- **`kaplan-meier`** — survival curves + log-rank (statsmodels SurvfuncRight),
  at-risk table. Expert-review on few events / heavy censoring.
- **`cox-regression`** — Cox PH (statsmodels PHReg): hazard ratios + CI, forest
  plot. Expert-review on <10 events / small n.
- **`diagnostic-test`** — sensitivity/specificity/PPV/NPV/AUC/Youden
  threshold + ROC (sklearn). Expert-review on small/imbalanced sample.
- **`ml-classification-eval`** — logistic-regression baseline, honest
  train/test + CV: accuracy/precision/recall/F1/ROC-AUC. Expert-review on
  small/imbalanced data.
- **`ml-regression-eval`** — linear-regression baseline: RMSE/MAE/R2 + CV,
  predicted-vs-actual. Expert-review on small test set.

Supporting changes:
- **`needs expert review` mechanism** (new, cross-cutting): `AnalysisResult`
  gains `expert_review: list[str]` + `add_expert_review()`; the engine threads
  it into run.json and the report; report.html renders a prominent banner.
- 6 new sample datasets (`growth_cov`, `schools`, `psych`, `survival`,
  `diagnosis`, `features`) with deterministic generators, registered in
  sample_data.
- Demo map entries for all 10; advisor `rules.yaml` entries for all 10
  (recommend/rule-out with reasons), active once built.
- Registry now ignores `__pycache__` in analysis discovery (was treated as an
  analysis dir).

### Verified (acceptance)
- `pytest` → **330 passed** (was 231; +42 advisor, +58 analysis, +packs);
  `ruff check src/ tests/ scripts/` clean.
- Every analysis demo runs end to end (`auphoria demo --analysis <id>`),
  verified against real sample files — not just `run()` unit tests. Four
  runtime bugs caught this way (see fixes).
- report.html renders the "Needs expert review" banner when triggered; run.json
  carries `expert_review`.

### What is next
- Discipline-pack analyses (Phase 9 roadmap) that build on these
  (e.g. health meta-analysis reuses diagnostic-test's ROC machinery).

### Known problems
- Some per-analysis tests call `run()` directly and missed `check_fit()` bugs
  (e.g. ml-regression UnboundLocalError, too-strict label/reference checks);
  these surfaced only in the engine-level demo and were fixed — a future
  per-analysis test should exercise `check_fit` on a real profile.
- `__pycache__` under analyses/ must not be treated as an analysis (fixed in
  this phase; keep it out of git).

---

## Phase 7 — Advisor: question-driven analysis recommendations (DONE, 2026-10-29)

### What is done
A data-shape + research-question advisor that recommends which built analyses
fit the user's data, with a plain-English reason for each, and rules out the
ones that don't (with the specific reason). The decision logic lives in
`src/auphoria/advisor/rules.yaml` — a readable encoding of
`docs/research/decision-guide.md` — and is evaluated by
`advisor/advisor_engine.py`; no analysis-matching logic is hard-coded in code.

- **`advisor/advisor_engine.py`** — `advise(profile, roles, question)` returns
  an `AdvisoryResult` with ranked `recommended` (each with a one-line reason)
  and `ruled_out` (each with the specific refusal). Only analyses actually
  present in the registry are recommended. Rule conditions: `min_rows`,
  `min_numeric`, `min_categorical`, `groups` (2 / 3+), `id_column`. Group/id
  detection honours wizard-confirmed column roles and falls back to data
  shape (all-unique subject column = id, most-categorical = group).
- **`advisor/rules.yaml`** — 7 research questions (describe/compare/relate/
  predict/over_time/reliability/reduce) + catch-all rules; every built
  analysis has at least one rule. Refusals carry tailored `not_fit` and
  `small_sample` messages ("Needs one numeric outcome and a group column with
  exactly two categories", "Sample too small for a t-test (needs at least 6
  non-missing rows)").
- **Wizard integration** (`cli/menu.py`): after column kinds/roles are
  confirmed, the wizard asks "What do you want to know?" and shows the
  advisor's ranked suggestions + ruled-out before the analysis menu. Advice is
  advisory — the student still picks any analysis.
- **`auphoria suggest`** now drives the advisor (was a hard-coded stub):
  `auphoria suggest --data FILE` aggregates every question's advice
  (deduped, best reason first); `--question/-q compare` narrows to one
  question. Prints recommendations with reasons and a ruled-out section.
- **`advisor/tests/test_advisor_engine.py`** — 42 scenario tests: data-shape
  × question × roles → expected recommended ids (ranked) and ruled-out
  reasons; role-override, paired-detection, catch-all, ranking, and
  survey-sample sanity checks.
- `rules.yaml` registered in `[tool.setuptools.package-data]` so it ships in
  the wheel; `src/auphoria/advisor` added to pytest `testpaths`.

### Verified (acceptance)
- `pytest` → **231 passed** (189 prior + 42 new advisor tests; the advisor dir
  was previously missing from `testpaths` and its tests were silently skipped).
- `ruff check src/ tests/ scripts/` clean.
- `auphoria suggest --data plant_growth.csv` → 6 recommendations + 3 ruled-out
  with reasons; `--question compare` narrows correctly.
- Full wizard driven end-to-end: question menu → "Based on your data and
  question, I would try: ✓ correlation …" → ruled-out → analysis menu.
- Wheel build contains `auphoria/advisor/rules.yaml` (package-data verified).

### What is next
- Remaining P1 analyses (kruskal-wallis, regression-linear, regression-multiple,
  logistic-regression, odds-and-risk, kaplan-meier, cronbach-alpha, pca,
  ml-classification-eval, ml-regression-eval) — add a `rules.yaml` entry for
  each when built (the advisor test reminds us).
- Wire the advisor into the Colab notebook's analysis dropdown for the same
  guidance there.

### Known problems
- The advisor recommends only BUILT analyses; planned-but-unbuilt ones
  (regression, survival, Cronbach, PCA, ML) never appear as recommendations
  until they are built and given a rule.
- `_load_sample_for()` in `cli/main.py` returns the first sample file
  regardless of the `name` argument (pre-existing; only affects the
  example-command column picker, which needs any fitting sample).

---

## Phase 6 — Core analyses batch 1 (P1: paired t, Spearman, chi-square, ANOVA, Mann-Whitney) (DONE, 2026-10-28)

### What is done
Five new P1 analyses, each with manifest.yaml + analysis.py + README.md +
tests/ (synthetic data, hand-computed answers, scipy reference, bad-input
cases) and an appropriate figure. All `maturity: experimental`.

- **`ttest-paired`** — paired-samples t-test (same subjects, two times):
  mean difference, t, df, p, 95% CI of the difference, Cohen's d_z,
  before/after connected-line figure. Guardrails: both columns numeric,
  listwise missing excluded with warning (never imputed), <2 pairs refused,
  constant differences refused; normality of differences warned for small n
  (Wilcoxon signed-rank recommended).
- **`spearman-correlation`** — rank correlation: rho, p, n, rank scatter
  figure; refuses <3 pairs / constant column; warns on heavy ties; verdict on
  significance vs alpha. README stresses monotonic (not linear) meaning.
- **`chi-square`** — test of independence: contingency table + row
  percentages, chi2, df, p, Cramer's V; stacked-bars figure. Guardrail: any
  expected count < 5 → WARN verdict did not fail plus Fisher's-exact
  recommendation; refuses a column with <2 categories.
- **`anova-oneway`** — 3+ independent groups: F, df, p, ANOVA table (SS
  between/within/total), eta-squared, Tukey HSD post-hoc (implemented with
  scipy.stats.studentized_range — no statsmodels dependency), boxplots.
  Levene + per-group Shapiro run and warn (Kruskal-Wallis recommended) but
  never refuse; refuses <3 groups (hint: use t-test) and groups with <2 obs.
- **`mann-whitney`** — two independent groups, non-parametric: U, p, medians,
  rank-biserial r effect size, boxplot; refuses <2 groups / >2 categories;
  tail parameter (two-sided/greater/less).

Supporting changes:
- New shared demo datasets (`sample_data/`): `training.csv` (paired pre/post),
  `diets.csv` (3 diets × weight loss + adherence category for chi-square).
- `auphoria demo --analysis <id>`: per-analysis demo mapping for all 9 built
  analyses (default stays ttest so the old demo test holds).
- Root `conftest.py` closes matplotlib figures after every test (analyses
  return open figures; unclosed ones piled up across the suite).
- Wizard tests that pick ttest by menu number updated "4" → "8" (the menu is
  alphabetical; anova-oneway … ttest-paired now precede it — the Phase 4
  documented fragility surfaced exactly as predicted).

### Verified (acceptance)
- `pytest` → **189 passed** (was 122): 39 new per-analysis tests + updated
  CLI tests. Zero warnings.
- `ruff check src/ tests/ scripts/` clean.
- `auphoria list` shows all 9 analyses; `auphoria demo --analysis <id>` runs
  end-to-end for every built analysis (verified the result CSVs contain real,
  sensible statistics).
- Reference checks recorded in each analysis's tests/README (tolerance =
  abs 1e-6 vs scipy unless stated):
  - ttest-paired: hand t = 7.4833 vs scipy ttest_rel (1e-4); d_z 3.3466 (0.01);
    CI 2.8 ± 2.7764·0.37417.
  - spearman: rho = ±1.0 exact for perfect monotone data; hand rho = 0.5 for
    x=[1..5], y=[3,1,4,2,5] (rank-d²  sum 10) vs scipy (1e-6).
  - chi-square: 2x2 [[30,10],[10,30]] → chi2 = 18.05, df = 1, p ≈ 2.15e-05,
    V = 0.475 (vs scipy chi2_contingency, 1e-6); small-count [[1,9],[9,1]]
    triggers the WARN expected-counts path.
  - anova-oneway: A/B/C means 4/10/16 → SS_between = 288, SS_within = 24,
    F = 54.0, eta² = 0.9231 (vs scipy f_oneway, 1e-6); Tukey A–C q = 14.6969
    p = 6.95e-06 (studentized_range, 1e-6).
  - mann-whitney: A=[1,2,3] vs B=[4,5,6,7] → U = 0, two-sided exact p =
    0.05714, rank-biserial r = 1.0 (vs scipy mannwhitneyu, 1e-6/1e-4).

### What is next
- Remaining P1 analyses: kruskal-wallis, regression-linear, regression-multiple,
  logistic-regression, odds-and-risk, kaplan-meier, cronbach-alpha, pca,
  ml-classification-eval, ml-regression-eval (batches 2-4 of the Phase 6
  plan).
- Wire `docs/research/decision-guide.md` into `suggest` for richer guidance.

### Known problems
- The wizard/menu picks analyses by alphabetical menu number — a new analysis
  earlier in the alphabet renumbers the menu and breaks number-based wizard
  tests (hit once in this phase; fixed by updating the tests).
- Shapiro-Wilk on tiny groups is low-power (warned, not refused, in anova);
  Tukey HSD assumes equal variances — Levene's warning covers this.
- Chi-square with expected counts < 5 only warns and recommends Fisher's exact
  (Fisher is a planned batch-2 analysis, not yet built).

---

## Phase 5 — Colab notebook (front end, verified end-to-end) (DONE, 2026-10-25)

### What is done
- **`src/auphoria/adapters/colab.py`**: every `google.colab` interaction lives
  here (upload, save, zip results, download, optional Drive copy, inline
  report). Lazy imports + `ColabRequired` error so importing `auphoria` never
  breaks on a laptop; the notebook contains zero analysis logic and zero
  Colab plumbing.
- **Shared fit-checker** `core/fitting.py`: `analyses_that_fit(kinds)` decides
  "does this analysis fit this data" in ONE place, used by both the CLI menu
  and the notebook's analysis dropdown. Nothing re-implemented in the front
  end (architecture invariant preserved).
- **Notebook rebuilt** (scripts/build_notebook.py, cell 1→5): REPO_URL var +
  install from it with session-temporary notice; clearly-labelled zip
  "test before publish" alternative (upload zip → pip install from it);
  upload button; preview + form widgets (kind lists, outcome/group/extra
  role pickers, analysis dropdown filtered to the data, options + seed);
  RUN through `auphoria.run(...)` with the report rendered inline (auto-runs
  once with `describe` so first-time users see output, button re-runs);
  zip + `files.download` with optional Drive save. Footer: reproducibility +
  Colab limits (files vanish when the runtime stops).
- **`AUPHORIA_RESULTS_ROOT` env override** added to the engine's default
  results root (keeps test/all runs out of `~/AUPHORIA_results` when set).
- **docs/colab-notes.md**: manual test steps for a real Colab session
  (including the zip install before publishing), known limits (temporary
  sessions, Google's servers, idle disconnects), and implementation notes.

### Verified (acceptance)
- **`tests/test_colab_phase5.py`**: executes the whole notebook top-to-bottom
  with **nbclient** against a throwaway kernelspec running this venv's
  python, with a **stub for `google.colab`** (tests/colab_stub) that fakes
  `upload()` (returns the real plant_growth.csv) and `download()` (records
  the zip path). Asserts: all cells execute without error, the download cell
  fired, the results zip exists, and it contains `report.html` + result CSVs.
- **`tests/test_fitting_phase5.py`**: fit-checker unit tests (numeric-only
  excludes ttest, categorical-only excludes correlation/ttest, optional-input
  analyses like summary always fit).
- `pytest` → **122 passed**; `ruff check src/ tests/ scripts/` clean.
- Notebook rebuilt through the script round-trips; placeholder URL check in
  build script still passes.

### What is next (unchanged)
- Implement the remaining P1 analyses (anova, chi-square, non-parametrics,
  regression-family, survival, Cronbach, PCA, ML-eval).
- Wire `docs/research/decision-guide.md` into `suggest` for richer guidance.

### Known problems
- Free Colab runtimes idle-disconnect (~90 min) and are wiped on restart;
  the notebook says download before leaving (docs/colab-notes.md lists the
  limits honestly).
- The analysis dropdown in the notebook shows analyses that *fit the column
  kinds*, not a check that every required input is selected — the RUN button
  reports missing inputs with the engine's plain-English error.
- nbclient/ipykernel/ipywidgets are dev-only extras (not shipped to
  students).

---

## Phase 4 — CLI wizard & first-class commands (DONE, 2026-10-25)

### What is done
- **Interactive wizard rework** (`cli/menu.py`): after loading, the user
  previews the data and confirms/overrides each column's **kind** (number /
  category / date / text) and **role** (outcome / group / covariate / id / time
  / weight / none); the analysis menu shows which analyses **fit** the data
  (marked ✓, with a plain reason for ✗ ones); each required input's candidate
  columns are sorted so the ones whose confirmed role matches the input's
  expected role come first (outcome → "outcome" role, group/x → "group").
- **Column-role ordering fix**: input candidate sort key is
  `(role != expected, name)` — matches are `False` so they sort first. The
  earlier bug used `reverse=False` with a `matches` boolean, which wrongly put
  non-matching columns ahead.
- **New one-line commands** (`cli/main.py`): `describe`, `suggest` (builds
  analysis recommendations from the data profile), `demo` (runs a sample
  without needing a file), and `list` filters by `--level` / `--discipline`.
- **Path handling** across OS styles hardened: home-style `~`, quoted
  drag-and-drop paths with spaces, escaped spaces, Windows backslashes (both
  flavours), absolute and relative — all normalised by `clean_path_input`.

### Verified (acceptance)
- `pytest` → **117 passed** (Phase 3 was 127; the drop is because the wizard
  acceptance tests were rewritten to match the reworked flow with both kind
  and role confirmation — the count difference is test-housekeeping, not lost
  coverage; the full interactive ttest end-to-end and the role-ordering test
  both run and pass).
- Wizard driven end-to-end on the real `plant_growth` sample: menu → ttest
  → outcome=height_cm / group=treatment → default params → engine invoked.
- Role-override acceptance: a column confirmed as "outcome" is listed first
  for the outcome input and is picked by choice "1".
- Post-fix re-verification (2026-10-25): `ruff check` clean; `auphoria
  doctor` all OK; `list --level beginner` shows the 4 built analyses;
  live `describe` / `ttest` / `correlation` runs on plant_growth produce
  all 9 artifacts (CSVs, methods.txt, run.json with verdicts + decision_log,
  offline report.html with base64 figure); `set_repo_url.py --check`
  correctly reports the placeholder still unfilled.
- **`what_does_not_tell` completeness fix**: describe already set it; ttest,
  correlation and summary now each ship an honest "this result does NOT
  imply…" sentence (non-significance ≠ proof of no effect / correlation ≠
  causation / summary ≠ generalisation), which renders in the report's
  dedicated box instead of an empty string.

### What is next (unchanged)
- Implement the remaining P1 analyses (anova, chi-square, non-parametrics,
  regression-family, survival, Cronbach, PCA, ML-eval).
- Wire `docs/research/decision-guide.md` into `suggest` for richer guidance.

### Known problems
- The wizard summary prompt and open-folder prompt only appear in an
  interactive terminal (`sys.stdin.isatty()`), so piped one-line runs never
  block — covered by tests using a piped/`monkeypatched` input.
- Menu numbering depends on the alphabetical order of built analyses; if a
  future analysis sorts earlier than ttest, wizard tests that select by number
  must be updated to match.

---

## Phase 3 — Report engine (`src/auphoria/report`) (DONE, 2026-10-24)

### What is done
- **report.html via Jinja2** (single self-contained file): `report.html.j2`
  template shipped as package data, rendered by `build_report_html()`.
  Sections: summary cards up top, QC verdict table (PASS / WARN / FAIL shown
  as words plus colour so it survives print/black-and-white), "what this
  result does *not* tell you" box, methods paragraph, result tables, figures
  (base64 PNG data URIs), assumptions & limitations, the full decision log,
  and a reproducibility block (input path + SHA-256, seed, params, inputs,
  software versions, replay command).
- **Offline guarantee**: template has zero external resource references — no
  remote `<script>`, no external `<link>`, no `http(s)` URLs, no `url()`; all
  CSS inline, all figures inline base64. Opens with no network.
- **Per-run artifacts** (already present, now covered by tests): result CSVs,
  figures as PNG, `methods.txt`, `run.json`, `log.txt`, `replay.sh`,
  `replay.ps1`.
- **Methods generator completed** (`build_methods_text`): fills library names,
  versions, the test name and alpha, outcome description, data/input names and
  the random seed from the run context — a paste-ready paragraph.
- **Optional `--docx`**: `build_docx()` writes `auphoria-report.docx`
  (methods paragraph + result tables) via python-docx. Public
  `auphoria.run(... make_docx=True)` and CLI `auphoria run --docx ...`. Clean
  error + install hint if python-docx is missing (no crash).
- **Replay fixed**: replay.sh / replay.ps1 no longer pass `--out`, so a re-run
  never collides with (or overwrites) the original run — it writes a fresh
  timestamped folder.
- **Output-folder rule** (verified): default
  `~/AUPHORIA_results/<dataname>_<analysis>_<timestamp>/`; an explicitly
  requested `--out` that already exists and is non-empty is refused (never
  overwritten). Final path is printed and the CLI offers to open the folder
  (beginner, interactive-terminal mode).
- Dependency changes: `jinja2>=3,<4` added to core deps; optional extras
  `docx = ["python-docx>=1.0"]` and `dev` now includes python-docx; report
  templates registered as package data.
- CLI `run` also gained `--kind COL=KIND` (force a column's type).

### Verified (acceptance)
- `pytest` → **127 passed** (from 120). New `tests/test_report_phase3.py` (7):
  - golden-file tests: `describe` Data_card.csv and Dataset_overview.csv must
    exactly match checked-in golden files `tests/golden/describe_*.csv` (plus
    a "golden is current" re-run check);
  - report.html contains all required sections and QC shown as text not colour
    alone; **no external resource references** (regex-swept: script/link
    src, http(s) URLs, url(); every `<img>` is a base64 data URI);
  - `replay.sh` executed in an isolated HOME actually reproduces identical
    numeric CSV outputs + identical seed/parameters (proven by running bash);
  - `--docx` verified interactively: opens, contains the methods paragraph
    (`t-test`) and the result tables.
- `ruff check .` clean.

### What is next (unchanged priorities)
- Implement the remaining P1 analyses (anova, chi-square, non-parametrics,
  regression-family, survival, Cronbach, PCA, ML-eval).
- Note: verified Phase 3 on 3.11 only; CI (after upload) covers 3.10/3.12.

### Known problems
- `report.html` base64 figures enlarge the file; fine for student-sized data.
- `--docx` needs python-docx (not in the default install) — cleanly skipped
  with an install hint when absent.
- Version line in report/run.json depends on the installed environment, so
  golden tests freeze only the *data* outputs (Data_card/overview), not the
  whole HTML.

---

## Phase 2 — Core engine (`src/auphoria/core`) (DONE, 2026-10-24)

### What is done
- **Data loading** (`adapters/adapters.py`): csv, tsv, txt, xlsx, xls, ods,
  json, dta and sav (sav/ods/xls via optional libs; clear "install x" hint).
  Robust delimiter sniffing (comma/semicolon/pipe/tab, flags the odd one),
  UTF-8 → ANSI fallback (flagged), duplicate-header rename detection from the
  raw header line (flagged), blank-line detection (flagged), quoted paths with
  spaces (drag-into-terminal), multi-sheet Excel ask (`list_sheets`), all-blank
  table refusal, missing-cell preservation as NaN, and resize/misparse handled
  as plain-English DataErrors.
- **Data card** (`core/data_card.py`): rich per-column type (numeric, ordinal,
  binary, categorical, date, id, free_text), missing + unique counts, dataset
  duplicate-row count, constant-column flags, IQR outlier flags (FLAG ONLY,
  never removed), suspicious values (negative age/percentage-out-of-range,
  flagged, never removed), and a suggested column *role*.
- **Column roles**: outcome / group / covariate / id / time / weight guessed
  and attached to each column (user confirms/corrects in the interactive flow).
- **Manifest loader via pydantic** (`core/manifest.py`): validates every
  manifest.yaml before the registry trusts it; plain-English errors name the
  offending field. Wired into `core/registry.py`.
- **Analysis registry**: unchanged auto-discovery (still scans `analyses/`).
- **Run context** (`core/analysis.py`): now carries seed, out_dir, input
  SHA-256, package versions, parameters, and a structured **decision log**
  (every warning, assumption check, and whether a test was/wasn't run, with a
  plain-English reason, each with a timestamp).
- **Results object**: `AnalysisResult` gains `verdicts` (PASS / WARN / FAIL
  checks) and `what_does_not_tell` text; engine writes both into `run.json`
  and `report.html`.
- **Errors**: plain-English classes with `to_user()` (message + Fix hint) —
  already present, now covered by tests.
- **`describe` analysis** (`analyses/describe/`): exercises the whole engine
  end to end, returns the data card + dataset overview + PASS/WARN verdicts +
  "what this does not tell you". Added to catalogue (P1).
- The engine profile pass now builds the rich data card and logs every flag.

### Verified (acceptance)
- `pytest` → **120 passed**.
- Messy synthetic-file tests (`tests/test_adapter_messy.py`, 20 tests): wrong
  delimiter (semicolon/pipe/tab), quoted path with spaces, blank rows, mixed
  types in a column, duplicate headers, empty / header-only / all-blank files
  — each loads correctly or raises a clear plain-English error.
- `tests/test_core_phase2.py`: pydantic manifest validation, data-card type
  detection, outlier/suspicious/constant/duplicate flags, verdicts + decision
  log, and a byte-for-byte check that reading a file never mutates it.
- End-to-end: `auphoria run --data plant_growth.csv --analysis describe`
  produces run.json with verdicts + decision_log and report.html with a
  verdicts table.

### What is next
- Wire the decision-guide into the advisor menu and implement non-descriptive
  P1 analyses (anova, chi-square, non-parametrics, regression, ...).

### Known problems
- `describe` currently treats integer-with-few-values as ordinal and string
  ids via a name-hint; ambiguous integer id columns (e.g. 1-8) are typed
  ordinal/numeric — documented, the user can correct the role/type.
- `.xls/.ods/.sav` need optional libraries (xlrd/odfpy/pyreadstat) that are not
  pulled by default; the error message tells the user exactly what to install.
- Date-typed columns get the "time" role; a date used only as a row label (not
  a time axis) would need the user to correct it.

---

## Phase — CLI skeleton & packaging (DONE, 2026-10-24)

### What is done
- **Build backend recorded** in `pyproject.toml`: `setuptools.build_meta`
  (standard, dependency-free; src/ layout + one console script; reliable
  across Python 3.10-3.12 and Colab). Reasoning in docs/DECISIONS.md.
- **Typer CLI** replacing argparse:
  - `auphoria --version` (prints version, exit 0).
  - `auphoria doctor` - environment self-check: Python 3.10-3.12, required
    libraries importable, results folder writable; prints [OK]/[FAIL] lines
    and exits 0 / 1.
  - Existing commands preserved (interactive `auphoria`, `run`, `list`, `info`,
    `sample`, `versions`). CLI dispatches via `app(... standalone_mode=False)`
    so errors surface as return codes, not tracebacks.
- **scripts/set_repo_url.py** now REFUSES any address that is not a GitHub
  repository URL (`https://github.com/<org>/<repo>`); added tests for accept /
  reject (bad, GitLab, HTTP-only, org-only). Hardcoded `@main` pins removed;
  install commands are now bare `git+https://github.com/mysteriousammw/auphoria`.
- **CI workflow** split and expanded:
  - `.github/workflows/lint.yml` - ruff on 3.10/3.11/3.12 (ubuntu).
  - `.github/workflows/tests.yml` - install + `auphoria --version` +
    `auphoria doctor` + `pytest` on 3.10/3.11/3.12 x ubuntu/windows/macos.
  - Runs only after upload (no repo/remote yet).
- **README.md**: install commands are now `pipx install git+https://github.com/mysteriousammw/auphoria`
  and `uvx --from git+https://github.com/mysteriousammw/auphoria auphoria` for Linux/macOS, Windows
  PowerShell and WSL, plus a clearly marked "Until the repository is published"
  section with the local `pip install -e .` instructions.
- **Templates**: CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md,
  CITATION.cff (CITATION now a template with a "To-be-decided" licence).
- **docs/LICENCE_DECISION.md** added: permissive vs copyleft trade-offs with a
  recommendation; **no LICENSE file and no license metadata** until the
  maintainer chooses.
- **docs/PUBLISH_CHECKLIST.md** rewritten to the exact 10 ordered steps
  (licence -> repo+push -> set_repo_url -> commit -> pipx/uvx clean test ->
  Colab -> enable Actions -> Zenodo -> fill CITATION -> tag 0.1.0).
- Ruff applied (clean) across src/tests/scripts; Colab notebook excluded (it
  is a generated artifact).

### Verified (acceptance)
In a clean venv from a fresh clone of the tree:
- `pip install -e .` -> `auphoria --version` (0.1.0) -> `auphoria doctor`
  (All checks passed, exit 0).
- `pytest` -> **81 passed**, including the new set_repo_url accept/reject tests
  and a `doctor` test.

### What is next (unchanged from prior phases)
- Implement the 18 P1 analyses from catalog/analyses.yaml (only summary/ttest/
  correlation built so far).
- Wire docs/research/decision-guide.md into the advisor menu.

### Known problems
- `doctor` writes a `.doctor_probe` file briefly into the results folder to
  test writability (deleted immediately); on a read-only home it reports FAIL
  rather than crashing.
- The CLI is Typer 0.27; run with `standalone_mode=False` and return-code
  translation is exercised by tests but worth a manual smoke test on Windows
  once CI is available (no Windows machine here).
- GitHub Actions files are written but have not run (no repository yet).

---

## Phase 0 — Research (DONE, 2026-10-24)

Research only; **no application code** changed in this phase (only the catalog,
tests that assert on it, and docs).

### What is done
- **Analysis landscape research** (docs/research/analysis-landscape.md):
  which analyses students run in theses at BS / MPhil / PhD across ten
  disciplines (agri & animal, biology & biotech, medicine & public health,
  psychology & social sciences, education, economics & business, engineering &
  physics, environmental science, CS & ML, bioinformatics). Evidence from
  university syllabi, thesis methods, journal/statistical-reporting guidelines,
  textbook TOCs, and jamovi/JASP/SPSS/R menus (used honestly — estimates are
  tagged; the report states clearly what could not be verified).
- **Planned catalogue** (catalog/analyses.yaml v2): 31 analyses across core,
  agri-animal, life-science, health, social, econ-eng, ml, bioinformatics
  packs; every entry carries id, name, plain_english_question, levels,
  disciplines, design, data_requirements, assumptions_to_check,
  alternatives_when_assumptions_fail, python_library_and_function, outputs,
  common_mistakes, priority (P1/P2/P3) and at least one source.
  P1 = 18 analyses (within the 30 cap) and covers every discipline.
- **Decision guide** (docs/research/decision-guide.md): plain-language "which
  analysis should I use" decision tree (question type → variable types →
  groups → design → sample size), mapped to catalogue ids.
- **Library check** (docs/research/library-check.md): pip install + import +
  Python-3.10 resolution verified for pandas, numpy, scipy, statsmodels,
  scikit-learn, pingouin, lifelines, matplotlib, seaborn, jinja2, pyyaml,
  pydantic, typer, rich, openpyxl; licences recorded; heavy/flag items noted
  (pingouin = GPL-3.0 → recommend NOT a core dep; statsmodels and lifelines
  carry extra deps).
- **File formats** (docs/research/file-formats.md): csv, tsv/txt, xlsx, xls,
  ods, json, sav, dta — each verified to round-trip locally; Word and PDF
  explicitly NOT supported in v1, with the plain-English message to give a
  student whose data is in a Word table.
- Tests: updated `test_catalogue_in_sync_with_registry` to the correct
  invariant (every *built* analysis appears in the catalog, not equals), and
  added research-catalogue validity tests (required fields, sources present,
  P1 ≤ 30 and covers every discipline).

### What is next (Phase 2 candidates)
- Implement the 18 P1 analyses as real modules (summary/ttest/correlation
  already built). P1 list: summary, ttest, ttest-paired, correlation,
  spearman-correlation, chi-square, anova-oneway, mann-whitney, kruskal-wallis,
  regression-linear, regression-multiple, logistic-regression, odds-and-risk,
  kaplan-meier, cronbach-alpha, pca, ml-classification-eval, ml-regression-eval.
- Decide dependency policy per library-check (drop pingouin from core; use
  statsmodels/lifelines-scipy rather than autograd).
- Wire the decision-guide into the advisor (menu asks the Step-0/1/3 questions).

### Known problems
- Level-by-level thesis methods are not counted anywhere publicly; every
  BS/MPhil/PhD distinction in the landscape doc is an estimate from course
  depth + published studies + repository snippets (stated in the doc).
- Some library-support facts (live Colab kernel, exact SPSS/jamovi default
  checkbox states) not re-verified live this phase — flagged in docs.
- The Phase-1 built analyses are a subset; the catalogue lists the plan, so
  `auphoria list` and the catalogue will differ until the P1 build.

---

## Phase 1 — Foundation + core engine (DONE, 2026-10-24)

### What is done

**Repository scaffold**
- `pyproject.toml` (Python 3.10–3.12, deps: NumPy/pandas/SciPy/Matplotlib/
  PyYAML; `openpyxl` optional; `auphoria` console script; MIT).
- `README.md` (one-line install per OS + uvx no-install form; all repo URLs
  as `https://github.com/mysteriousammw/auphoria`), `CHANGELOG.md`, `CITATION.cff`,
  `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`, `.gitignore`.
- `scripts/set_repo_url.py` replaces the placeholder after upload;
  `scripts/build_notebook.py` regenerates the Colab notebook.
- `.github/workflows/ci.yml` (written now; runs only after upload).

**Core engine (`auphoria.run(...)`)** — the single path used by CLI and Colab
- Reads CSV/TSV/TXT/XLSX via adapters (with UTF-8/ANSI fallback flagged,
  structural checks, no data mutation).
- Profiles columns (numeric / categorical / datetime / text) via the advisor.
- Resolves declared inputs (outcome/group/extra) and coerces parameters.
- Refuses bad fits with plain-English errors; full tracebacks only to log.
- Writes per run: `report.html` (single file, inline CSS, base64 figures),
  result CSVs, PNG figures, `methods.txt`, `run.json`, `replay.sh`,
  `replay.ps1`, `log.txt`.
- Reproducibility: package versions, seed, resolved params, SHA-256 of input.
- Results default to `~/AUPHORIA_results/<dataname>_<analysis>_<timestamp>/`.

**CLI**
- `auphoria` — interactive beginner flow (path → preview → confirm columns →
  analysis menu → inputs/params → run → open folder). Verified interactively.
- `auphoria run --data PATH --analysis ID [--outcome] [--group] [--extra]
  [--param] [--seed] [--out] [--expert]` — one-line form; verified.
- `auphoria list / info / sample / versions / --version`.

**Analyses (all `experimental`)** — each with manifest.yaml, analysis.py,
README.md, and tests with hand-checked/reference answers:
- `summary` (descriptive statistics; honours missing data; `--outcome` opt).
- `ttest` (Welch default, Cohen's d, boxplot; refuses ≠2 groups, non-numeric
  outcome, too-few rows).
- `correlation` (Pearson, scatter + labelled trend line; refuses constant
  column, <3 pairs).

**Sample data**: `plant_growth.csv` (30 rows, 2 treatments, 3 deliberate
blanks) and `survey.csv` (40 rows, online/classroom, 2 blanks).

**Colab notebook**: `notebooks/auphoria_colab.ipynb` — install line, upload
button, dropdowns, RUN (calls `auphoria.run(...)`), zip download, privacy
notice. Valid; engine-only (no analysis logic). Notebook + repo tests assert
this.

**Tests**: `76 passed` locally on Python 3.11 under `pip install -e ".[dev]"`
(adapters, params, advisor, registry, catalogue-vs-manifest sync, CLI,
full engine runs, notebook validity, set_repo_url).

### What is next (Phase 2 candidates)
- More analyses: one-way ANOVA, chi-square, Mann–Whitney / Kruskal–Wallis,
  simple linear regression, correlation alternatives (Spearman).
- `docs/research/`: reference notes behind statistical choices.
- Optional: confidence intervals, effect-size error bars, more plot styles.
- Optional: `--latex` figure export or `.csv.gz` for very large files.

### Known problems
- Python 3.10/3.12 not yet tested on this machine (only 3.11 is installed);
  CI (after upload) will cover 3.10, 3.11, 3.12.
- Legacy `.xls` not supported (by design; user told to convert).
- The interactive menu is plain `input()` (no arrow-key widgets) — fine for
  the audience; a richer TUI would be a later enhancement.
- `report.html` embeds figures as base64, which grows the file; acceptably
  small for student-sized data.
- Some pandas `to_datetime` probes emit deprecation warnings internally;
  suppressed in `_try_datetime`; no user-facing effect.

### Verification performed this phase
- `pip install -e .` clean in a fresh Python 3.11 venv (cloned tree) → OK.
- `pytest` → 76 passed.
- `auphoria list / info / versions / sample / run` all exercised.
- Interactive `auphoria` flow driven end-to-end with canned input → report + folder produced.
- `set_repo_url.py --check` reports 14 files holding the placeholder.

---

## Changelog → see `CHANGELOG.md`
## Decision log → see `docs/DECISIONS.md`