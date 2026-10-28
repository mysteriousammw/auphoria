# Pilot test — student checklist

This is a short, read-the-README-only test of AUPHORIA by **3–5 students
before release**. The goal is to catch places where the instructions are
unclear or the tool misbehaves — **not** to test the statistics themselves.

**Your job:** follow the README and the steps below as if you had never seen
this tool. Do not ask for help from the people who built it. If you cannot
figure something out, that is exactly what we want to hear about — note it and
move on.

Please run this from a **clean computer or fresh virtual environment** (or in
Google Colab, if that is your platform) so we test the real install path.

---

## Before you start

- [ ] Pick your platform: macOS / Windows / Linux-WSL / Google Colab.
- [ ] You have an internet connection (only needed for install).
- [ ] Time needed: about 15–20 minutes.

## Part 1 — Install

Open the README and follow the **Quick start** for your platform. Mark what
you actually had to do:

- [ ] The install command I used was: (paste it)
- [ ] `auphoria --version` printed a version. (what did it print?)
- [ ] `auphoria doctor` reported everything OK. (if not, what did it say?)
- [ ] I would describe the install step as: (easy / OK / confusing) because: ...

## Part 2 — First run (guided)

Run `auphoria` and work through the wizard with the bundled sample data.

- [ ] I found the sample data without help. (how? via `auphoria sample`? README?)
- [ ] I answered the column-type questions.
- [ ] I answered the column-role questions.
- [ ] I answered **"What do you want to know?"** and understood the options.
- [ ] I picked an analysis and it ran to completion.
- [ ] I found and opened a `report.html`.
- [ ] I could read the summary numbers and the "what this result does NOT tell you" box.

## Part 3 — Second run (one line)

Run one analysis non-interactively, e.g.:

```bash
auphoria run --data survey.csv --analysis correlation --outcome score --extra x=hours_studied
```

- [ ] It worked the first time. (if not, paste the error)
- [ ] I found the results folder and the `methods.txt` file.

## Part 4 — A deliberate mistake

Run an analysis that does not fit, e.g. a t-test on a single-column file, or
`auphoria run --data survey.csv --analysis chi-square ...` without two
categorical columns.

- [ ] I got a clear, plain-English message telling me what was wrong and how to
      fix it (not a Python traceback).

## Part 5 — Your own data (optional but very useful)

Use a small CSV/Excel file of your own (any columns).

- [ ] It loaded. (if not, what happened?)
- [ ] AUPHORIA offered sensible analysis options for it.
- [ ] Nothing about your data was silently changed, removed, or "fixed".

---

## The "what went wrong" form

Please copy the table below into your report and fill it in. One row per
problem, however small.

| # | Where (install / wizard / run / report / README / other) | What you did | What you expected | What actually happened | How bad (blocking / annoying / nit) |
|---|----------------------------------------------------------|--------------|-------------------|------------------------|-------------------------------------|
| 1 | | | | | |

**Additional open questions** (answer any you can):

1. What was the single most confusing moment?
2. What was the single nicest thing about the experience?
3. If you were choosing a tool for your own coursework, would you pick
   AUPHORIA? Why or why not?
4. What one thing, if any, would stop a classmate from using it?
5. Did anything make you worried about your data's privacy or safety?

---

## For the maintainers — pilot sign-off

| Pilot (initials) | Platform | Date | Part 1 install | Parts 2–3 ran | Part 4 clear error | Form filled | Notes |
|------------------|----------|------|----------------|---------------|--------------------|-------------|-------|
| P1 | | | | | | | |
| P2 | | | | | | | |
| P3 | | | | | | | |
| P4 | | | | | | | |
| P5 | | | | | | | |

**Ship gate:** all 3–5 pilots can install and run Parts 2–3, Part 4 gives a
clear plain-English error, and no **blocking** row appears on their form. Any
**blocking** row must be fixed and re-tested before this is released.