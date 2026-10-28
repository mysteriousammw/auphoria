# Colab notebook — manual test steps & known limits

`notebooks/auphoria_colab.ipynb` is the student-facing front end for Google
Colab. This page is the human checklist the automated test
(`tests/test_colab_phase5.py`) cannot replace, plus what the notebook can and
cannot promise.

## Before publishing (local check, 2 minutes)

The automated suite already executes the notebook end-to-end with a fake
`google.colab` (see `tests/test_colab_phase5.py`). For a quick human pass:

```
python scripts/build_notebook.py      # regenerate the .ipynb from source
python -m pytest tests/test_colab_phase5.py -q
```

Both must pass before touching a real Colab session.

## Real Colab session — manual test steps

1. **Open** https://colab.research.google.com → Upload → pick
   `notebooks/auphoria_colab.ipynb`.
2. **Runtime → Run all** (or run the numbered cells one by one).
3. **Cell 1 (install):** wait for `AUPHORIA <version> ready.` If the
   repository is not yet published, use the zip install:

   - On your laptop: `zip -r auphoria_src.zip auphoria/ -x "*.venv/*"
     -x "*__pycache__*"` from the folder containing `pyproject.toml`.
   - In Colab cell 2, upload `auphoria_src.zip` when the file picker opens.
   - Uncomment the "install from zip" lines in cell 1 and re-run cell 1.
   - Verify the version banner prints; delete the local zip afterwards.
4. **Cell 2 (upload):** upload `plant_growth.csv` (ships in
   `src/auphoria/sample_data/data/`). Confirm the cell prints
   `Saved as plant_growth.csv`.
5. **Cell 3 (preview/pick):** confirm the preview table shows the 7 data
   rows, the numeric/categorical column lists look right, the analysis
   dropdown lists only analyses that fit the data, and the defaults are
   sensible (`describe` selected).
6. **Cell 4 (run):** confirm a report renders inline below the RUN button
   without needing a click, and that switching the dropdown to `ttest`,
   setting Outcome = `height_cm`, Group = `treatment` and pressing RUN
   re-runs and re-renders.
7. **Cell 5 (download):** confirm the zip downloads to the laptop's
   Downloads folder, contains `report.html`, `methods.txt`, result CSVs,
   figures and `run.json`, and the HTML opens offline.
8. **Optional Drive save:** mount Drive from the left panel, uncomment
   `colab.save_to_drive(_zip)` in cell 5, re-run, confirm the zip appears
   under `MyDrive/AUPHORIA_results/`.
9. **Error paths to try:** upload a file with no numeric column and check
   the message is plain English; press RUN with no outcome selected and
   check it fails with a clear message (not a traceback).

## Known limits (tell students in the notebook/docs)

- **Sessions are temporary.** Everything uploaded or produced lives in the
  Colab VM and **vanishes when the runtime stops or disconnects**. The
  install (cell 1) must be re-run for every new session, and results should
  be downloaded (cell 5) before leaving.
- **Google's servers.** Uploaded files go to Google's runtime, not the
  laptop. Confidential or patient data must be analysed with the offline
  laptop install instead; the notebook's privacy notice says this.
- **Runtime limits.** Free Colab runtimes idle-disconnect (~90 min) and can
  be interrupted; long analyses should be re-run after reconnecting.
- **Attachments are not the runtime.** Files uploaded via Colab's file
  panel are separate from `google.colab.files.upload()`; this notebook uses
  the latter so the cell receives the bytes directly.
- **No internet at analysis time.** After cell 1's install, runs never call
  the network; the only network step is the initial pip install.

## Implementation notes

- All `google.colab` interaction lives in
  `src/auphoria/adapters/colab.py` so the notebook contains zero analysis
  logic and zero Colab-specific plumbing beyond calling those helpers.
- The analysis dropdown is filtered with the same fit-checker
  (`auphoria.core.fitting.analyses_that_fit`) the CLI menu uses — one
  source of truth for "does this analysis fit this data".
- Cell 4 auto-runs once with the default form state (`describe`) so a
  first-time user sees the report immediately; the RUN button re-runs with
  their choices.
- The automatic test stubs `google.colab` (tests/colab_stub/) and executes
  the whole notebook with nbclient, asserting the run finishes, the zip is
  produced, and it contains `report.html` + result CSVs.
- `AUPHORIA_RESULTS_ROOT` env var overrides where results land — the test
  uses it to keep runs inside a temp dir instead of `~/AUPHORIA_results`.
