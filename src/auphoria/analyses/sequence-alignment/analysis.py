"""Pairwise sequence alignment for AUPHORIA.

Needleman-Wunsch (global) and Smith-Waterman (local) implemented in pure
python with dynamic programming. U is treated as T for DNA/RNA input so a
cDNA and its RNA reference align cleanly; protein input (20-letter alphabet)
is auto-detected.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError

_AA = set("ACDEFGHIKLMNPQRSTVWY")
_NT = set("ACGTU")
# X (any/unknown) and Z (Glu/Gln ambiguity) are tolerated protein codes.
_AA_X = _AA | set("XZ")


def _norm(s: str) -> str:
    return s.upper().replace("U", "T")


def _alphabet(seqs: list[str]) -> str:
    letters = {c for s in seqs for c in s}
    if letters <= _NT:
        return "nucleotide"
    if letters <= _AA_X | _NT:
        return "protein-or-nucleotide"
    bad = sorted(letters - _AA_X - _NT)
    raise AssumptionError(
        "Sequence contains unsupported characters: " + ", ".join(bad[:8])
        + ". Use nucleotide (A/C/G/T/U) or amino-acid letters.",
    )


def _align(a: str, b: str, mode: str, match: float, mismatch: float, gap: float):
    """DP alignment returning (score, aligned_a, aligned_b, markers, start, end).

    ``start``/``end`` are 0-based bounds of the aligned region in the ORIGINAL
    (ungapped) coordinates of a and b for local mode (inclusive start,
    exclusive end); for global mode they span the whole sequences.
    """
    n, m = len(a), len(b)
    score = [[0.0] * (m + 1) for _ in range(n + 1)]
    local = mode == "local"
    if not local:
        for i in range(1, n + 1):
            score[i][0] = i * gap
        for j in range(1, m + 1):
            score[0][j] = j * gap
    best = 0.0
    best_i = best_j = 0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            diag = score[i - 1][j - 1] + (match if a[i - 1] == b[j - 1] else mismatch)
            up = score[i - 1][j] + gap
            left = score[i][j - 1] + gap
            if local:
                score[i][j] = max(0.0, diag, up, left)
                if score[i][j] > best:
                    best, best_i, best_j = score[i][j], i, j
            else:
                score[i][j] = max(diag, up, left)
    total = best if local else score[n][m]

    def _diag_v(i: int, j: int) -> float:
        return score[i - 1][j - 1] + (match if a[i - 1] == b[j - 1] else mismatch)

    # ---- local: locate the start of the best region ------------------------
    start_i = start_j = 0
    if local:
        i, j = best_i, best_j
        while i > 0 and j > 0 and score[i][j] > 0:
            if abs(score[i][j] - _diag_v(i, j)) < 1e-9:
                i, j = i - 1, j - 1
            elif abs(score[i][j] - (score[i - 1][j] + gap)) < 1e-9:
                i -= 1
            else:
                j -= 1
        start_i, start_j = i, j

    # ---- traceback (from best for local, from the corner for global) -------
    i, j = (best_i, best_j) if local else (n, m)
    a_out: list[str] = []
    b_out: list[str] = []
    while True:
        if local and score[i][j] <= 0:
            break
        if i > 0 and j > 0 and abs(score[i][j] - _diag_v(i, j)) < 1e-9:
            a_out.append(a[i - 1])
            b_out.append(b[j - 1])
            i, j = i - 1, j - 1
        elif i > 0 and abs(score[i][j] - (score[i - 1][j] + gap)) < 1e-9:
            a_out.append(a[i - 1])
            b_out.append("-")
            i -= 1
        elif j > 0 and abs(score[i][j] - (score[i][j - 1] + gap)) < 1e-9:
            a_out.append("-")
            b_out.append(b[j - 1])
            j -= 1
        else:
            break
    a_out.reverse()
    b_out.reverse()
    a_aln = "".join(a_out)
    b_aln = "".join(b_out)
    markers = "".join(
        "|" if x == y else (" " if x == "-" or y == "-" else ":")
        for x, y in zip(a_aln, b_aln, strict=False)
    )
    matches = sum(1 for x, y in zip(a_aln, b_aln, strict=False) if x == y and x != "-")
    aligned_cols = sum(
        1 for x, y in zip(a_aln, b_aln, strict=False) if x != "-" and y != "-"
    )
    identity = 100.0 * matches / aligned_cols if aligned_cols else 0.0
    return {
        "score": total,
        "identity_percent": round(identity, 2),
        "aligned_a": a_aln,
        "aligned_b": b_aln,
        "markers": markers,
        "start_a": start_i if local else 0,
        "end_a": (best_i if local else n),
        "start_b": start_j if local else 0,
        "end_b": (best_j if local else m),
    }


class SequenceAlignmentAnalysis(Analysis):
    """Pairwise global/local alignment of two sequence columns."""

    id = "sequence-alignment"

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
        mode = str(params.get("mode") or "global").lower()
        if mode not in ("global", "local"):
            raise AssumptionError("mode must be 'global' or 'local'.")
        match = float(params.get("match_score", 2))
        mismatch = float(params.get("mismatch_penalty", -1))
        gap = float(params.get("gap_penalty", -2))

        a_raw = data[inputs["sequence_a"]].astype(str).str.strip()
        b_raw = data[inputs["sequence_b"]].astype(str).str.strip()
        keep = a_raw.ne("") & b_raw.ne("")
        if not keep.any():
            raise AssumptionError("Both sequence columns are empty in every row.")
        if int((~keep).sum()):
            ctx.log_decision("rows with an empty sequence excluded")
            result.add_warning(f"Excluded {int((~keep).sum())} row(s) with an empty sequence.")
        a_all = [_norm(s) for s in a_raw[keep].tolist()]
        b_all = [_norm(s) for s in b_raw[keep].tolist()]
        _alphabet(a_all + b_all)

        rows: list[dict[str, Any]] = []
        for idx, (sa, sb) in enumerate(zip(a_all, b_all, strict=False)):
            r = _align(sa, sb, mode, match, mismatch, gap)
            r["row"] = idx
            r["sequence_a"] = sa
            r["sequence_b"] = sb
            rows.append(r)
        tbl = pd.DataFrame(rows)
        result.tables["alignments"] = tbl.drop(columns=["sequence_a", "sequence_b"])

        summary = pd.DataFrame(
            {
                "statistic": ["n_pairs", "mean_score", "max_score", "mean_identity_percent"],
                "value": [
                    len(rows),
                    round(float(tbl["score"].mean()), 2),
                    round(float(tbl["score"].max()), 2),
                    round(float(tbl["identity_percent"].mean()), 2),
                ],
            }
        )
        result.tables["summary"] = summary

        # one alignment figure for the first non-trivial pair
        nontrivial = [r for r in rows if len(r["aligned_a"]) > 3]
        if nontrivial:
            r = nontrivial[0]
            fig, ax = _alignment_figure(r, mode)
            result.figures.append(FigureItem("alignment", fig, f"Alignment of pair 0 ({mode})."))

        result.summaries["mode"] = mode
        result.summaries["pairs"] = str(len(rows))
        result.summaries["mean identity %"] = f"{float(tbl['identity_percent'].mean()):.1f}"
        result.methods.append(
            f"Pairwise {mode} alignment ({'Needleman-Wunsch' if mode == 'global' else 'Smith-Waterman'}) "
            f"with match={match}, mismatch={mismatch}, gap={gap} was computed for "
            f"{len(rows)} sequence pair(s); identity is % matching aligned "
            f"columns (seed {ctx.seed}). Python analysis via AUPHORIA."
        )
        result.what_does_not_tell = (
            "An alignment score and identity % do NOT prove homology or "
            "function: short high-identity regions occur by chance, raw "
            "identity ignores amino-acid similarity (no BLOSUM/PAM), and "
            "e-value/significance — the measure BLAST reports — is not "
            "computed here. Treat the alignment as a visual comparison, not "
            "as evolutionary evidence."
        )
        return result


def _alignment_figure(r: dict, mode: str) -> tuple[Any, Any]:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(max(5, len(r["aligned_a"]) * 0.12), 2.2))
    ax.text(
        0.02, 0.6, r["aligned_a"], family="monospace", fontsize=11,
        verticalalignment="center",
    )
    ax.text(
        0.02, 0.4, r["markers"], family="monospace", fontsize=11,
        verticalalignment="center", color="#555555",
    )
    ax.text(
        0.02, 0.2, r["aligned_b"], family="monospace", fontsize=11,
        verticalalignment="center",
    )
    ax.axis("off")
    ax.set_title(f"Pairwise {mode} alignment (identity {r['identity_percent']}%)")
    fig.tight_layout()
    return fig, ax


ANALYSIS = SequenceAlignmentAnalysis()
