# Pairwise Sequence Alignment (`sequence-alignment`)

Aligns pairs of DNA, RNA or protein sequences with classic dynamic
programming — **Needleman-Wunsch** (global) or **Smith-Waterman** (local) —
from two text columns holding sequence_a and sequence_b per row.

## When to use it

- You cloned a sequence and want to check it against a reference gene.
- You have two homologues and want identity % and an alignment view.
- You need a quick pairwise comparison without leaving the spreadsheet.

## Expected input shape

Two text columns; each row is one pair:

| sequence_a     | sequence_b     |
|----------------|----------------|
| GATTACA        | GCATGCU        |
| ...            | ...            |

U is treated as T, so cDNA vs RNA comparisons align cleanly. Protein input
(amino-acid letters, including X/Z ambiguity codes) is auto-detected.

## What you get

- **Alignments table** per pair: score, identity %, aligned strings with
  match/mismatch/gap markers, and local-mode start/end coordinates.
- **Summary table** (n pairs, mean/max score, mean identity).
- An alignment visualisation figure for the first pair.
- `methods.txt` paragraph and `report.html`.

## Parameters

- `mode` (`global` / `local`), `match_score` (2), `mismatch_penalty` (-1),
  `gap_penalty` (-2).

## Guardrails

- Unsupported characters are refused with the offending letters named.
- Rows with an empty sequence are excluded with a warning.

## Honest limits

- Simple match/mismatch scoring is teaching-grade — no BLOSUM/PAM, no
  e-values. For real homology searches use BLAST. Pure-python DP is slow on
  very long sequences.
