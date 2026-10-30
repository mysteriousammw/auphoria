# DNA Translation and ORF Finding (`sequence-translation`)

Translates DNA sequences to protein with the **standard genetic code**
(table 1, start ATG, stops TAA/TAG/TGA) and finds **open reading frames**
on the forward strand across all three reading frames.

## When to use it

- You have a DNA stretch (a clone, an unknown gene, a predicted CDS) and
  need the protein it could encode.
- You want the longest ORF of each sequence and its frame/coordinates.
- Checking that a sequence actually contains a plausible gene (start →
  long stretch → stop) before cloning or expression work.

## Expected input shape

A single text column; each row is one DNA sequence:

| dna             |
|-----------------|
| ATGGCCATGTTTTAA |
| ...             |

RNA input (U) is auto-converted to T.

## What you get

- **Translations table**: the amino-acid string for each of the three
  forward reading frames.
- **ORFs table**: frame, start, end, length (aa), peptide, `longest` flag
  per sequence.
- Summary counts and a warning when no ORF of the minimum length is found.

## Parameters

- `min_orf_length` (default 30 aa): ORFs shorter than this are dropped.

## Guardrails

- Ambiguous bases (N) are **refused** — use `sequence-composition` for
  exploratory QC first.
- Every sequence must be at least 3 bases.
- Blank rows are skipped with a warning.

## Honest limits

- ORF finding is heuristic: no splicing, no reverse strand, no alternate
  genetic codes. A long ORF is *not* proof of a real gene.
