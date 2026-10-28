---
name: Bug report (not a wrong result)
about: The tool crashed, errored, or behaved unexpectedly (not a specific wrong statistic — use the "wrong result" template for that).
title: "[bug] <short description>"
labels: bug
assignees: ""
---

## What did you run?

Paste the exact command or the steps:

```
auphoria run --data <file> --analysis <id> --outcome <col> [--group <col>] ...
```

## What expected / what happened

- **Expected:** ...
- **Happened:** ... (paste the error message or `EngineError` text)

Include the output of `auphoria doctor`, and for a run, the `log.txt` from the
results folder (it has the technical traceback).

## Repro

The smallest data + command that reproduces it. A tiny CSV is ideal.

## Environment

- OS: (macOS / Windows / Linux / WSL / Colab)
- Python: (`python --version`)
- AUPHORIA version: (`auphoria --version`)

## Checklist

- [ ] I ran `auphoria doctor` and included its output
- [ ] I gave the exact command and the smallest repro data
- [ ] I included `log.txt` (or said it's a crash before results were written)