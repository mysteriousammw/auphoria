# AUPHORIA 3-minute demo video — script

This script walks through recording a ~3-minute demo of AUPHORIA. It is written
as a shot list with the on-screen action and the narration. Record at 1080p,
keep it under 3:30 total. A plain CLI recording plus a short screen-cap of the
`report.html` in a browser is enough — no animation needed.

Timing is a guide; hit the beats below and trim the fat.

**Prereq on screen:** a terminal with the `auphoria` command available
(`auphoria --version` printed). Use a bright terminal theme and a large font.

---

## Shot 0 — Title card (0:00–0:08)

**On screen:** "AUPHORIA — data analysis without coding. Runs offline. No
accounts. No uploads."

**Narration:** "AUPHORIA is free, open-source data analysis for students who
don't code — and it runs right here on your computer, offline."

---

## Shot 1 — Meet the tool (0:08–0:25)

**On screen:** run `auphoria doctor` and show it reporting everything OK.
Then `auphoria list` and scroll a little.

**Narration:** "`auphoria doctor` checks that your machine is ready. And
`auphoria list` shows every analysis we ship — t-tests, ANOVA, survival
analysis, PCA, machine learning evaluation, and more."

---

## Shot 2 — The guided flow (0:25–1:20)

**On screen:** type `auphoria` and walk the wizard on the bundled sample
dataset (`survey.csv`). Steps:

1. When asked for a path, type `survey.csv` (or the absolute sample path —
   `auphoria sample` shows it).
2. Press Enter to accept the detected column types (`group`, `score`, `age`,
   `hours_studied`).
3. Press Enter to accept the suggested roles.
4. At **"What do you want to know?"** pick `2` (Compare groups).
5. AUPHORIA suggests: *"You have a numeric outcome and two groups — this
   compares their averages (Welch t-test by default)."* Pick `ttest`.
6. Choose `score` as outcome, `group` as group; accept defaults; confirm.

**Narration:** "Just run `auphoria`. It asks plain questions — what kind of
data, what do you want to know — and picks the right test for you. Here it
recognises a numeric outcome and two groups, and recommends a t-test. I press
enter and it runs."

---

## Shot 3 — The results (1:20–2:30)

**On screen:** the console summary (t, df, p, Cohen's d), then open the newest
folder under `~/AUPHORIA_results/` and show `report.html` in a browser.

Point out (cursor/zoom as you name each):

- the **summary cards** (t, p, effect size);
- the **quality-checks table** (PASS/WARN/FAIL verdicts);
- the **"what this result does not tell you"** box;
- the **methods** paragraph — copy-paste ready.

**Narration:** "AUPHORIA writes a complete report: the numbers, the figures,
the assumption checks, and the honest caveats — including what this result does
*not* prove. And the methods paragraph is copy-paste ready for your thesis."

---

## Shot 4 — Reproducibility (2:30–2:55)

**On screen:** in the results folder show `replay.sh` and `run.json`; run
`bash replay.sh` and show a fresh folder with the same numbers.

**Narration:** "Every run is reproducible. The folder has the exact command and
the random seed, so a marker — or future you — can re-run it and get the same
numbers, every time."

---

## Shot 5 — Responsible-use close (2:55–3:15)

**On screen:** return to the wizard `auphoria`, pick a *survival* analysis
(`kaplan-meier` on `survival.csv`) and let it print the **"Needs expert
review"** notice.

**Narration:** "AUPHORIA is honest about its limits. Advanced analyses tell you
when a statistician should look at the numbers, and nothing is ever silently
'validated'. It does your calculation — not your judgement."

---

## Shot 6 — End card (3:15–3:30)

**On screen:** "AUPHORIA — auphoria.run — free & offline."

**Narration:** "Try it. It runs on Windows, macOS, Linux, and Google Colab —
with no accounts and no uploads."

---

## Checklist before recording

- [ ] Virtualenv with AUPHORIA installed; `auphoria --version` works.
- [ ] Terminal font large and readable; no window obstructing the command.
- [ ] The sample `survey.csv` and `survival.csv` are on hand (or their
      absolute paths copied).
- [ ] `~/AUPHORIA_results/` cleaned so "newest folder" is obvious.
- [ ] Browser ready to open a `report.html` from disk (no internet needed).
- [ ] Rehearse the narration once aloud; aim < 3:30.

## Tips

- Record screen + mic in one take; cut silence between shots.
- If a shot runs long, trim the mid-steps (auto-accept defaults), never the
  results or the responsible-use close.
- Add captions for accessibility; keep on-screen type clean and uncluttered.
- Store the final video in `docs_site/assets/` if you want it embedded in the
  docs, and link it from the [Gallery](gallery.md) page.