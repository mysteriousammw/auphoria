# DNA/RNA Sequence Composition (`sequence-composition`)

Computes per-sequence composition statistics from a text column of DNA or
RNA sequences: **length, GC content (%), base counts**, plus an aggregate
summary and a GC-histogram. The first sanity check on any sequence data:
is the sequence plausible, how long is it, does its GC% look right?

## When to use it

- You downloaded or sequenced sequences and want a quick QC pass.
- You need per-sequence length / GC% columns for a downstream table.
- You are comparing sequence sets (e.g. gene vs intergenic, two species).

## Expected input shape

A single text column; each row is one sequence:

| sequence       |
|----------------|
| ATGCGCGTAACGTT |
| ACGTU...       |

No FASTA `>` headers — remove header lines before loading (or the letters
will be flagged as non-IUPAC).

## What you get

- **Per-sequence composition table**: length, GC%, counts of A/C/G/T/U/N.
- **Summary table**: n, mean/min/max length, mean/median GC%.
- **GC-histogram figure**.
- `methods.txt` paragraph and `report.html`.

## Parameters

- `mode` (`auto` / `dna` / `rna`): force an alphabet. `auto` refuses a mix
  of T and U; `dna` refuses U; `rna` refuses T.

## Guardrails

- Only IUPAC letters A/C/G/T/U/N; anything else (spaces, digits, `>`,
  `?`) is refused with the offending letters named.
- Blank rows are skipped and counted in a warning.
- A mix of T and U (DNA and RNA together) is refused.
