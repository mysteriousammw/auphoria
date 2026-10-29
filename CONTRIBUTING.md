# Contributing to AUPHORIA

Thanks for helping build a tool that lets non-programmers analyse their own
data responsibly. Here is how to contribute well.

## Code of conduct

Read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) first. Be kind and assume good
intent — contributors come from many disciplines.

## How contributions are reviewed

This project follows an evidence-based, "never claim it passed unless you
ran it" policy. A pull request is merged only when:

- it is accompanied by the changes to `docs/DECISIONS.md` that record what
  changed and why;
- automated tests demonstrate the behaviour (run with `pytest`);
- nothing is labeled "validated" — new analyses begin with `maturity:
  experimental`.

## Setting up

```
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

The repository must stay installable with `pip install -e .` and the console
command must work offline.

## Coding conventions

- Support Python 3.10-3.12 only. Do not add dependencies beyond NumPy,
  pandas, SciPy, Matplotlib and PyYAML unless they are truly required; heavy
  or AI/network dependencies are not accepted.
- Open-source libraries only. No AI, no API keys, no telemetry, no network
  at run time. Work purely offline after install.
- Errors must be plain English with a suggested fix. Tracebacks go only to
  the log, never to the user's screen.
- Never silently drop, change, or impute data. If a test does not fit the
  data or design, warn or refuse.
- The CLI and the Colab notebook are thin front ends. **All analysis logic
  lives in the engine (`auphoria.run(...)`) or in an analysis module.**

## Adding a new analysis

Every analysis is a module under `src/auphoria/analyses/<id>/` with four
pieces:

1. `manifest.yaml` — id, name, levels, disciplines, inputs, parameters,
   outputs, assumptions, limitations, test data, and `maturity:
   experimental`.
2. `analysis.py` — a subclass of `auphoria.core.analysis.Analysis`.
3. `README.md` — what it does, when to use it, limitations.
4. `tests/test_<id>.py` — tests with small synthetic data and known answers
   (hand-calculated or from a documented reference example).

Copy an existing analysis as your starting point, then register it in
`catalog/analyses.yaml`. The engine discovers it from the manifest.

## Reporting bugs and security issues

See [SECURITY.md](SECURITY.md) for how to disclose issues.

## Commit hygiene

Small, focused commits. Write `docs/DECISIONS.md` entries for any decision
you make. Update `CHANGELOG.md` for user-visible changes.

## Maintainers

### Current maintainer

- **AUPHORIA maintainers** (`docs/PUBLISH_CHECKLIST.md`).
- Role: owns the release process, merges PRs, triages issues, and keeps the
  build green (`pytest`, `ruff`, validation dashboard, docs build, the pilot
  gate). The maintainer is the person who can promote an analysis's
  `maturity` to `reviewed` or `validated` (with a named reviewer recorded in
  the manifest); contributors and the build agent may only set
  `experimental`/`tested`.

### How to reach the maintainers

- Open an issue (see `.github/ISSUE_TEMPLATE/`).
- For a **wrong result**: use the `wrong_result` template — the acceptance
  for a fix is a recorded cross-check against an independent reference,
  added to `docs/validation/references.yaml`.

### Becoming a maintainer

- Demonstrated, consistent, high-quality contributions (code, docs, or
  validation) over time.
- Agreement on the project's values: honest statistics, no claim of
  "validation" without a reviewer, permissive/open dependencies, offline
  operation, plain-English errors, and the "never claim it passed unless you
  ran it" policy.
- New maintainers are added by consensus of the existing maintainers, and
  recorded here.

## Succession

If the maintainer(s) become unreachable or step down, this is how the project
is handed over:

1. **Preferred:** a named successor (or small successor team) is already
   listed below, or is chosen by the current maintainers before they leave.
2. **If no successor is named:** any contributor with repository access who
   has made substantive contributions may step forward; the choice is made by
   the most recent active maintainers if they can be reached, otherwise by
   the other contributors with write access, and is recorded here.
3. **Handover checklist** for the successor:
   - Take ownership of the **release process** (`docs/PUBLISH_CHECKLIST.md`)
     and the **pilot gate** (`docs/pilot/pilot-checklist.md`).
   - Verify the pipeline end to end once: `pip install -e ".[dev]"`,
     `pytest`, `ruff check src/ tests/ scripts/`,
     `python scripts/gen_validation_dashboard.py --check`,
     `./scripts/build_docs.sh`, and one `auphoria demo --analysis <id>`.
   - Confirm you can run `scripts/set_repo_url.py` and cut a tag/release (see
     `.github/workflows/release.yml`).
   - If repositories/accounts change, update every URL that currently uses
     `https://github.com/mysteriousammw/auphoria` (run `scripts/set_repo_url.py` with the new
     address).
4. **If the project is abandoned (no maintainer reachable for a sustained
   period):** the repository may be forked by the community under a
   permissive licence (see `docs/LICENCE_DECISION.md`); this succession
   section exists to make that fork as smooth as possible by keeping the build
   reproducible and the records complete.

### Successor record

| Date | Successor / team | Notes |
|------|------------------|-------|
|      | (none yet)        | Add the named successor here when this happens. |