---
name: Pull request
about: Propose a change to AUPHORIA.
title: ""
labels: ""
assignees: ""
---

## What and why

<!-- One or two sentences: what this changes and the problem it solves. -->

## Type of change

- [ ] New analysis
- [ ] Bug fix
- [ ] Docs
- [ ] Tooling / CI / release
- [ ] Other

## Evidence

This project has a **"never claim it passed unless you ran it"** policy. Do
not tick a box you did not run.

- [ ] `pytest` passes (I ran: `pytest -q`)
- [ ] `ruff check src/ tests/ scripts/` is clean
- [ ] If I touched analyses: every affected `auphoria demo --analysis <id>`
      runs end to end
- [ ] If I added an analysis: `auphoria new-module`-style file set is present
      (manifest + analysis + README + tests), catalogue sync test is green,
      and the analysis appears in `auphoria list`
- [ ] If I touched validation: `docs/validation/dashboard.md` is current
      (`python scripts/gen_validation_dashboard.py --check`)
- [ ] If I touched docs: `./scripts/build_docs.sh` reports no warnings
- [ ] `docs/DECISIONS.md` records any non-obvious decision I made
- [ ] `CHANGELOG.md` updated for user-visible changes

## Behaviour notes

<!-- Anything a reviewer should check by hand, especially data-honesty rules
(no imputation, warn/refuse on bad fits, plain-English errors). -->

## Checklist before requesting review

- [ ] I have read CONTRIBUTING.md.
- [ ] No `REPO_URL_PLACEHOLDER` was introduced where a real address is needed
      (it stays only in install-literal spots).
- [ ] No new runtime dependencies unless truly required and permissive
      (detected by the dependency policy).