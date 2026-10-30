# DNA/RNA Sequence Composition

`sequence-composition` · maturity: **experimental**

Validation reference: Hand-computed: sequence 'ATGCGC' -> length 6, GC% = 66.67, counts A1 T1 G2 C2; 'AUGC' -> GC% 50 with U detected as RNA.  


## What it does

Computes per-sequence composition statistics for DNA or RNA sequences held in one text column: sequence length, GC content (%), base counts (A/T/C/G/U/N), and an aggregate summary across all sequences. This is the first thing a student checks when a sequencing run or a downloaded gene comes back — is the sequence plausible, how long is it, is the GC content in the expected range?

## What you need

- **sequence** (categorical-column, required): A text column holding one DNA/RNA sequence per row (letters A, C, G, T and/or U; N allowed for ambiguity).

## Options

- `mode` (default auto): auto = accept both T and U; dna/rna force an alphabet.

## What you get out

- per-sequence composition table (length, GC%, counts of each base)
- aggregate summary (total sequences, mean/min/max length, mean GC%)
- GC-content histogram figure
- methods.txt paragraph
- report.html

## Assumptions

- Each row holds a single sequence as plain letters (no FASTA headers; remove '>' lines first).
- Only IUPAC ambiguity letter N is accepted; other letters are flagged.
- Skips empty/blank sequences with a warning rather than failing the whole run.

## Limitations

- Composition is descriptive — it cannot tell you what the sequence does or whether it is coding.
- GC% is reported as G+C over the whole sequence length, not per window; for GC-window plots use a genome browser.
- U (RNA) and T (DNA) are counted separately; in 'auto' mode a sequence containing both is refused.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis sequence-composition --extra sequence=<sequence>
```
