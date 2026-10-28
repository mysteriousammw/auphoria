# Publication checklist

The exact steps to take AFTER the build, in order. Do them one at a time;
most are online actions that this terminal build cannot perform for you.
Re-checked against what shipped in Phase 12 (0.1.0): the release workflow,
module scaffolder, pilot gate, docs site and validation stack are all
accounted for below.

## 1. Choose a licence and add `LICENSE`
- [ ] Read `docs/LICENCE_DECISION.md` and pick a licence (MIT / BSD-3-Clause /
      Apache-2.0 are the permissive defaults; GPL for copyleft).
- [ ] Add the licence text as `LICENSE` at the repository root.
- [ ] Set `license` metadata + the matching `License ::` classifier in
      `pyproject.toml`.
- [ ] Set the `license` field in `CITATION.cff` (currently "To-be-decided").

## 2. Create the GitHub repository and push
- [ ] Create an empty repository on GitHub (owner/name chosen by you).
- [ ] Push the current tree to it:
      `git remote add origin <git-url>` then `git push -u origin main`.
- [ ] No `REPO_URL_PLACEHOLDER` should have leaked before this point; it is
      replaced next. This includes the **docs site**: `mkdocs.yml` holds
      `site_url`/`repo_url` and `docs_site/` install blocks, all using the
      placeholder.

## 3. Run `scripts/set_repo_url.py` with the repository address
- [ ] `python scripts/set_repo_url.py https://github.com/<owner>/<repo>`
- [ ] It replaces `REPO_URL_PLACEHOLDER` everywhere it appears: `README.md`,
      `CITATION.cff`, `pyproject.toml`, `docs/`, `docs_site/`, and `mkdocs.yml`
      (site_url/repo_url), plus the engine/pack install hints.
- [ ] Verify nothing is left (the `--check` exit code 0 means nothing to
      replace):
      `python scripts/set_repo_url.py --check https://github.com/<owner>/<repo>`
- [ ] Rebuild the docs so the rendered pages show the real address:
      `./scripts/build_docs.sh`.

## 4. Commit that change
- [ ] `git add -A && git commit -m "Set repository URL"` and `git push`.
- [ ] Confirm the README install commands and the built docs site now show the
      real address.

## 5. Test the install commands on a clean machine
- [ ] On a clean machine/environment (fresh Python 3.10–3.12):
      `pip install "git+https://github.com/<owner>/<repo>"` then
      `auphoria --version` and `auphoria doctor`.
- [ ] `pipx install git+...` and `uvx --from git+... auphoria` work
      (no-install form).
- [ ] Windows PowerShell and WSL variants from the README / quickstart work.
- [ ] `auphoria run` completes on the bundled sample data.

## 6. Open the Colab notebook and run it
- [ ] Open `notebooks/auphoria_colab.ipynb` in Google Colab from GitHub.
- [ ] Run the install cell; upload a CSV; pick an analysis; click RUN; download
      the results zip.
- [ ] Confirm the privacy notice shows and shutdown loses no work without the
      Drive-save option.

## 7. Enable GitHub Actions and watch the workflows
- [ ] Enable Actions (usually on by default).
- [ ] `tests.yml` and `lint.yml` pass on the supported Python versions across
      ubuntu / windows / macos.
- [ ] Also confirm the **validation checks** are wired into CI: the dashboard
      and analysis-docs `--check` scripts (see `scripts/gen_validation_dashboard.py`
      and `scripts/gen_analysis_docs.py`) and `./scripts/build_docs.sh` (docs
      build fails on any warning). These are exercised by `release.yml`'s
      `verify-tag` job before a release is drafted.

## 8. Connect Zenodo for a DOI
- [ ] zenodo.org → GitHub integration: connect the AUPHORIA repository.
- [ ] The DOI mints automatically on the next tag (see step 11).

## 9. Fill in `CITATION.cff`
- [ ] Replace the placeholder author entry with the real authors/ORCIDs/
      affiliations (personal detail placeholders were left for you).
- [ ] Confirm it is valid `cff-version: 1.2.0` under the "cite this repository"
      widget.

## 10. Run the pilot test (release gate)
- [ ] Recruit 3–5 students who have never seen the tool.
- [ ] Give them ONLY the README + `docs/pilot/pilot-checklist.md`.
- [ ] Collect their "what went wrong" forms; fix every **blocking** item before
      release.
- [ ] All pilots can install and complete Parts 2–3, and Part 4 gives a clear
      plain-English error.

## 11. Tag version 0.1.0 (release workflow)
- [ ] `git tag v0.1.0 && git push origin v0.1.0`. The `release.yml` workflow
      (`on: push tags: ['v*']`) then: verifies the tag (tests, ruff,
      validation + docs `--check`, docs build), builds the sdist + wheel, and
      drafts a **GitHub Release** with CHANGELOG notes and artifacts attached.
- [ ] Review the drafted release, correct the notes if needed, and publish it.
- [ ] Confirm `pip install "git+https://github.com/<owner>/<repo>@v0.1.0"`
      is stable for students (pin the tag, not `@main`).
- [ ] Verify the Zenodo DOI is attached to this release.
- [ ] Record the release date in `CHANGELOG.md` (the `[0.1.0]` entry already
      consolidates every phase; just confirm the date is right).

## After release
- [ ] Record the demo video (`scripts/demo_video_script.md` + `demo_video.py`)
      and embed it in the gallery.
- [ ] Promote analyses from `experimental` to `tested` as real users report
      they worked (`maturity` + `reviewer`/`reference` per the phase-10 gate).
- [ ] Keep the validation dashboard and per-analysis docs regenerated on every
      manifest change (`--check`) so the site never drifts.