"""DNA/RNA sequence composition analysis for AUPHORIA.

Pure-python composition stats (no bioinformatics dependency): length, GC
content, per-base counts, aggregate summary and a GC histogram. Sequences
arrive as a text column; every row is one sequence.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError

_VALID = set("ACGTUN")
_DNA = set("ACGTN")
_RNA = set("ACGUN")


def _gc_content(seq: str) -> float:
    if not seq:
        return float("nan")
    return 100.0 * (seq.count("G") + seq.count("C")) / len(seq)


class SequenceCompositionAnalysis(Analysis):
    """Per-sequence length, GC%, and base counts for a text column."""

    id = "sequence-composition"

    def check_fit(
        self, profile: Any, params: dict[str, Any], inputs: dict[str, str]
    ) -> list[str]:
        return []  # validated in run() on the actual rows

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        result = AnalysisResult()
        col = inputs["sequence"]
        raw = data[col].astype(str)
        mode = str(params.get("mode") or "auto").lower()

        # ---- row handling: blanks skipped, invalid letters flagged ----------
        blank_mask = raw.str.strip().eq("")
        n_blank = int(blank_mask.sum())
        if n_blank:
            ctx.log_decision(f"skipped {n_blank} blank sequence rows (reported)")
            result.add_warning(f"Skipped {n_blank} blank sequence row(s); blank cells cannot be sequenced.")
        seqs = raw[~blank_mask].str.strip().str.upper()
        if seqs.empty:
            raise AssumptionError(
                "The sequence column contains no non-blank values."
            )

        bad_letters = sorted(
            {ch for s in seqs for ch in set(s) if ch not in _VALID}
        )
        if bad_letters:
            raise AssumptionError(
                "Sequence column contains non-IUPAC letters: "
                + ", ".join(bad_letters)
                + ". Only A, C, G, T, U and N are accepted — check for "
                "spaces, digits, or FASTA headers in the column.",
                hint="Remove '>' header rows and anything that is not a base letter.",
            )

        if mode == "dna":
            u_count = int(seqs.str.count("U").sum())
            if u_count:
                raise AssumptionError(
                    f"mode=dna but the data contains {u_count} U (RNA) base(s)."
                )
        elif mode == "rna":
            t_count = int(seqs.str.count("T").sum())
            if t_count:
                raise AssumptionError(
                    f"mode=rna but the data contains {t_count} T (DNA) base(s)."
                )

        has_t = bool(seqs.str.contains("T").any())
        has_u = bool(seqs.str.contains("U").any())
        if has_t and has_u and mode == "auto":
            raise AssumptionError(
                "Sequences contain BOTH T (DNA) and U (RNA) bases. Set "
                "mode=dna or mode=rna — a mixed alphabet is not a valid "
                "sequence.",
                hint="Double-check the column: it may mix two datasets.",
            )
        alphabet = "RNA" if (has_u and not has_t) or mode == "rna" else "DNA"

        # ---- per-sequence table -------------------------------------------------
        rows: list[dict[str, Any]] = []
        for s in seqs:
            rows.append(
                {
                    "sequence": s,
                    "length": len(s),
                    "gc_percent": round(_gc_content(s), 2),
                    "A": s.count("A"),
                    "C": s.count("C"),
                    "G": s.count("G"),
                    "T": s.count("T") if alphabet == "DNA" else s.count("U"),
                    "U": s.count("U"),
                    "N": s.count("N"),
                }
            )
        per_seq = pd.DataFrame(rows).reset_index(drop=True)
        per_seq.index.name = "row"
        result.tables["per_sequence_composition"] = per_seq
        result.tables["base_counts"] = per_seq[
            ["A", "C", "G", "T", "U", "N"] if alphabet == "DNA" else ["A", "C", "G", "U", "N"]
        ]

        # ---- aggregate -------------------------------------------------------
        agg = pd.DataFrame(
            {
                "statistic": ["n_sequences", "mean_length", "min_length", "max_length", "mean_gc_percent", "median_gc_percent", "total_gc"],
                "value": [
                    len(per_seq),
                    round(float(per_seq["length"].mean()), 2),
                    int(per_seq["length"].min()),
                    int(per_seq["length"].max()),
                    round(float(per_seq["gc_percent"].mean()), 2),
                    round(float(per_seq["gc_percent"].median()), 2),
                    f"{alphabet} ({'T' if alphabet == 'DNA' else 'U'}/U bases)",
                ],
            }
        )
        result.tables["summary"] = agg

        # ---- figure (GC histogram) --------------------------------------------
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(6.5, 4))
        ax.hist(per_seq["gc_percent"], bins=min(15, int(len(per_seq) // 2) or 1), color="#7fb4d8", edgecolor="white")
        ax.set_xlabel("GC content (%)")
        ax.set_ylabel("sequences")
        ax.set_title("GC-content distribution")
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        result.figures.append(FigureItem("gc_histogram", fig, "Histogram of per-sequence GC content."))

        # ---- summaries / methods / what-not-tell ------------------------------
        result.summaries["alphabet"] = alphabet
        result.summaries["sequences"] = str(len(per_seq))
        result.summaries["mean GC%"] = f"{float(per_seq['gc_percent'].mean()):.1f}%"
        result.methods.append(
            f"Sequence composition was computed for {len(per_seq)} "
            f"{alphabet} sequences: length, GC content and base counts per "
            f"sequence ({ctx.seed=}). Python analysis via AUPHORIA."
        )
        result.what_does_not_tell = (
            "Composition statistics do NOT tell you whether a sequence is "
            "coding, functional, or correctly assembled — two sequences with "
            "identical GC% can be entirely unrelated. They only describe the "
            "letters present; contamination or assembly errors that preserve "
            "base composition will not be detected."
        )
        return result


ANALYSIS = SequenceCompositionAnalysis()
