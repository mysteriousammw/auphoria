# FAQ

## The tool

### Is AUPHORIA really free and offline?

Yes. It's open-source, runs entirely on your computer or in Google Colab, and
makes no network requests after installation. Your data never leaves your
machine.

### Do I need to know how to code or write statistics?

No to both. The guided form asks plain questions and picks the right analysis
for your column types. You don't write a single line of code or formula.

### I'm a supervisor — should my students use this?

It can help students who'd otherwise be paralysed by the tooling. But please
read [Responsible use](responsible-use.md): AUPHORIA computes honestly but does
not certify anyone's science. Advanced analyses flag "needs expert review"
when used outside their intended conditions — that flag is for you to take
seriously.

## Choosing an analysis

### How do I know which test to use?

Run the guided form and answer **"What do you want to know?"**, or read
[Which analysis should I use?](choose.md). AUPHORIA also checks assumptions and
warns or refuses when a test doesn't fit your data — it won't quietly run the
wrong test.

### What if my data doesn't fit a test's assumptions?

AUPHORIA checks the main assumptions (normality, equal variances, expected
counts) and tells you. If the parametric test is a poor fit, it recommends a
non-parametric alternative (e.g. Kruskal-Wallis instead of ANOVA) in its
warning.

## Your data

### What file formats can I use?

CSV, TSV/TXT, and Excel (.xlsx) as **input**. Word and PDF are **not** accepted
as inputs — paste or save those tables to a spreadsheet/CSV first. Output
includes `.html`, `.csv`, `.png`, `.txt`, and optionally `.docx`.

### Does AUPHORIA ever change my data?

**Never.** It counts and reports missing values and never imputes them; it
refuses text that can't be a number rather than dropping it; it warns about
duplicate headers and blank rows it found. If data is excluded, it tells you
exactly how many rows and why, and records it in the decision log.

### My Excel file has merged cells. Help.

See [Troubleshooting](troubleshooting.md#my-excel-file-has-merged-cells-and-auphoria-complains) —
you'll need to unmerge and flatten to a one-row header.

## The results

### What's in the report?

Every report has summary cards, a quality-check (PASS/WARN/FAIL) table, a
**"What this result does not tell you"** box, paste-ready methods, all tables
and figures, assumptions & limitations, a full decision log, and
reproducibility details (command + seed).

### How do I cite/use this in my thesis?

Paste the `methods.txt` paragraph from your run into your Methods section —
it describes exactly what was done and with which versions. Include the
command and seed (already in the report's reproducibility section).

### Can I reproduce a result later?

Yes. Every results folder has `replay.sh`/`replay.ps1`. Run it and you get the
same numbers, figures, and report in a fresh folder.

## Interpreting

### A significant p-value — does that prove my hypothesis?

No. AUPHORIA's report says this explicitly. A significant test says the result
is unlikely under the null, given the data and assumptions — it does not prove
that your treatment *caused* the difference, and it says nothing about
unmeasured confounders. Read the "what this does not tell you" box.

### A high R² or AUC — is my model good?

A high metric is not proof of a good or generalisable model. The ML analyses
report performance on data the model never trained on (honest train/test +
cross-validation) and still warn you not to over-read it.

### What does the "Needs expert review" banner mean?

Advanced analyses add it when they're run outside their intended conditions —
small sample, few events, heavy censoring, weak cluster structure,
imbalanced classes. It means: the tool ran, but a statistician or your
supervisor should judge the numbers before you rely on them.

## Where can I report a problem?

See the [Known issues](known-issues.md) list and the
[issue template](known-issues.md). For a *wrong number*, the
right fix is a recorded cross-check against an independent reference (R, or a
published worked example) — that's how the project validates every analysis.

## Requirements

### What Python version do I need?

Python 3.10, 3.11, or 3.12. `auphoria doctor` tells you if yours is unsupported.