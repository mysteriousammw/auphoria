# Pairwise Sequence Alignment

`sequence-alignment` · maturity: **experimental**

Validation reference: Hand-computed: 'GATTACA' vs 'GCATGCU' global alignment score checked by hand-trace of the DP matrix; identity and alignment strings verified in the test.  


## What it does

Aligns pairs of DNA, RNA or protein sequences from two text columns using classic dynamic programming: Needleman-Wunsch (global alignment of the whole sequences) and Smith-Waterman (local alignment of the best matching region). Reports score, identity %, the aligned strings with match/mismatch markers, and for local alignment the start/end of the matched region. This is what a student needs to compare a cloned sequence against a reference gene, or two homologues, without leaving the spreadsheet.

## What you need

- **sequence_a** (categorical-column, required): First sequence of each pair (letters A/C/G/T/U or amino-acid codes).
- **sequence_b** (categorical-column, required): Second sequence of each pair (same alphabet as sequence_a).

## Options

- `mode` (default global): global = Needleman-Wunsch (whole sequences); local = Smith-Waterman (best region).
- `match_score` (default 2): Score for a matching pair of letters.
- `mismatch_penalty` (default -1): Score for a mismatching pair of letters.
- `gap_penalty` (default -2): Score per inserted gap.

## What you get out

- alignment table per pair (score, identity %, aligned strings, markers)
- summary (mean/max score, mean identity)
- alignment visualisation figure for the first non-trivial pair
- methods.txt paragraph
- report.html

## Assumptions

- Sequences are compared as raw strings; case is ignored.
- DNA/RNA alphabets allow T/U equivalence (U is treated as T).
- Protein sequences (20-letter alphabet) are auto-detected; score matrices are simple match/mismatch (no BLOSUM/PAM).
- Identical lengths are not required — dynamic programming handles gaps.

## Limitations

- Simple match/mismatch scoring is a teaching-grade model; for real homology searches use BLAST with substitution matrices.
- Only pairwise alignment; multiple-sequence alignment and phylogenetic trees are separate tools.
- Long sequences (thousands of bases) are slow in pure python; keep pairs under a few hundred for interactive use.
- A high identity % does not prove functional equivalence.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis sequence-alignment --extra sequence_a=<sequence_a> --extra sequence_b=<sequence_b>
```
