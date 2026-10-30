"""DNA translation and ORF finding for AUPHORIA.

Standard genetic code (table 1), start ATG, stops TAA/TAG/TGA. Forward-strand
only; three reading frames scanned for ORFs. Pure python (no BioPython — the
project's permissive, light-dependency policy).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from auphoria.core.analysis import Analysis, AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

CODON_TABLE = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}
STOPS = {"TAA", "TAG", "TGA"}


def translate_frame(dna: str, frame: int) -> str:
    """Translate one reading frame (0, 1, 2) to amino-acid string."""
    peptide: list[str] = []
    for i in range(frame, len(dna) - 2, 3):
        codon = dna[i : i + 3]
        if len(codon) < 3:
            break
        aa = CODON_TABLE.get(codon, "X")
        peptide.append(aa)
        if aa == "*":
            break
    return "".join(peptide)


def find_orfs(dna: str, min_aa: int) -> list[dict[str, Any]]:
    """All forward-strand ORFs (start ATG -> first in-frame stop), 3 frames.

    Returns a list of dicts with 1-based frame, start, end, length_aa and the
    translated peptide (peptide includes the stop '*' when one was found).
    ORFs shorter than min_aa are dropped.
    """
    orfs: list[dict[str, Any]] = []
    for frame in range(3):
        i = frame
        while i < len(dna) - 2:
            if dna[i : i + 3] != "ATG":
                i += 3
                continue
            # in-frame scan from this ATG: advance by codons until a stop
            j = i + 3
            has_stop = False
            while j < len(dna) - 2:
                codon = dna[j : j + 3]
                if codon in STOPS:
                    has_stop = True
                    break
                j += 3
            if j >= len(dna) - 2:
                j = len(dna)  # run-on to the end of the sequence
            end = j + 3 if has_stop else j  # include the stop codon in the span
            length_aa = (end - i) // 3
            if length_aa >= min_aa:
                peptide = translate_frame(dna[i:end], 0)
                orfs.append(
                    {
                        "frame": frame + 1,
                        "start": i + 1,
                        "end": end,
                        "length_aa": length_aa,
                        "peptide": peptide,
                    }
                )
            i = j + 3 if j + 3 < len(dna) else len(dna)
    return orfs


class SequenceTranslationAnalysis(Analysis):
    """Translate DNA to protein; find and rank forward-strand ORFs."""

    id = "sequence-translation"

    def check_fit(
        self, profile: Any, params: dict[str, Any], inputs: dict[str, str]
    ) -> list[str]:
        return []

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        result = AnalysisResult()
        col = inputs["sequence"]
        min_orf_length = int(params.get("min_orf_length", 30))
        if min_orf_length < 3:
            raise AssumptionError("min_orf_length must be at least 3 amino acids.")

        raw = data[col].astype(str).str.strip().str.upper()
        blank = raw.eq("")
        if blank.any():
            ctx.log_decision("blank sequence rows skipped")
            result.add_warning(f"Skipped {int(blank.sum())} blank sequence row(s).")
        raw = raw[~blank]
        if raw.empty:
            raise AssumptionError("The sequence column contains no non-blank rows.")

        seqs = raw.str.replace("U", "T", regex=False)
        bad = {ch for s in seqs for ch in set(s) if ch not in "ACGT"}
        if bad:
            raise AssumptionError(
                "Translation needs unambiguous DNA (A/C/G/T only). Found: "
                + ", ".join(sorted(bad))
                + ". Run sequence-composition first to inspect, or remove "
                "ambiguous/header rows.",
                hint="N (ambiguous) bases cannot be translated; remove those cells.",
            )
        if seqs.str.len().min() < 3:
            raise AssumptionError(
                "Every sequence must be at least 3 bases long to translate."
            )

        orf_rows: list[dict[str, Any]] = []
        trans_rows: list[dict[str, Any]] = []
        for s in seqs:
            for frame in range(3):
                trans_rows.append(
                    {
                        "sequence": s,
                        "frame": frame + 1,
                        "translation": translate_frame(s, frame),
                    }
                )
            orfs = find_orfs(s, min_orf_length)
            longest = max((o["length_aa"] for o in orfs), default=0)
            for o in orfs:
                o["sequence"] = s
                o["longest"] = "yes" if o["length_aa"] == longest else ""
                orf_rows.append(o)

        trans_df = pd.DataFrame(trans_rows)
        if orf_rows:
            orf_df = pd.DataFrame(orf_rows).sort_values(
                ["sequence", "length_aa"], ascending=[True, False]
            )
        else:
            orf_df = pd.DataFrame(
                columns=["sequence", "frame", "start", "end", "length_aa", "peptide", "longest"]
            )
        orf_df = orf_df.reset_index(drop=True)
        result.tables["translations"] = trans_df
        result.tables["orfs"] = orf_df

        n_orfs = len(orf_df)
        n_seq_with_orf = (orf_df.groupby("sequence").size() > 0).sum() if n_orfs else 0

        # summaries + methods
        result.summaries["sequences"] = str(len(seqs))
        result.summaries["ORFs found"] = str(n_orfs)
        result.summaries[f"sequences with ORF >= {min_orf_length} aa"] = str(n_seq_with_orf)
        result.methods.append(
            f"DNA sequences ({len(seqs)}) were translated with the standard "
            "genetic code (table 1, forward strand, start ATG, stops "
            "TAA/TAG/TGA). Open reading frames were scanned in all three "
            f"forward frames with a minimum length of {min_orf_length} amino "
            f"acids; {n_orfs} ORF(s) were found (seed {ctx.seed}). Python "
            "analysis via AUPHORIA."
        )
        if n_orfs == 0:
            result.add_warning(
                f"No ORF of at least {min_orf_length} amino acids was found "
                "on the forward strand — the sequences may be non-coding, "
                "reverse-strand, or contain sequencing errors (N, stops)."
            )
        result.what_does_not_tell = (
            "Finding an ORF does NOT prove the sequence is a real gene: "
            "chance ORFs are common in random DNA, real genes have splice "
            "sites and regulatory context this tool does not model, and a "
            "stop-free stretch can appear in non-coding sequence. Translation "
            "of an ORF predicts a peptide only under the standard code on "
            "the forward strand."
        )
        return result


ANALYSIS = SequenceTranslationAnalysis()
