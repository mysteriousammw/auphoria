"""Hardy-Weinberg equilibrium test for AUPHORIA.

Classic biallelic HWE chi-square goodness-of-fit test. Each row of the
input is one locus/marker with observed genotype counts (AA, Aa, aa).
Expected counts under HWE are E(AA)=n*p^2, E(Aa)=2*n*p*q, E(aa)=n*q^2,
with p = allele A frequency, q = allele a frequency. df = 1 because one
parameter (p) is estimated from the data.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from auphoria.core.analysis import Analysis, AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError


class HardyWeinbergAnalysis(Analysis):
    """Test biallelic genotype counts against Hardy-Weinberg equilibrium."""

    id = "hardy-weinberg"

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
        alpha = float(params.get("alpha", 0.05))

        def _counts(role: str) -> pd.Series:
            s = self.ensure_numeric(data[inputs[role]], inputs[role])
            return s

        aa = _counts("n_homo_ref")
        aabb = _counts("n_het")
        aa2 = _counts("n_homo_alt")

        # ---- validate ---------------------------------------------------------
        neg = (aa < 0) | (aabb < 0) | (aa2 < 0)
        if neg.any():
            raise AssumptionError("Genotype counts cannot be negative.")
        all_zero = (aa + aabb + aa2) == 0
        if all_zero.any():
            raise AssumptionError(
                "A marker with n = 0 total genotypes cannot be tested for HWE."
            )
        decl = (aa % 1 != 0) | (aabb % 1 != 0) | (aa2 % 1 != 0)
        if decl.any():
            ctx.log_decision("non-integer genotype counts rounded")
            result.add_warning(
                "Some genotype counts are not whole numbers; they were rounded "
                "to the nearest integer for the allele-frequency calculation."
            )

        n = (aa + aabb + aa2).astype(float)
        p = (2 * aa + aabb) / (2 * n)  # frequency of A
        q = 1 - p  # frequency of a

        exp_aa = n * p * p
        exp_het = 2 * n * p * q
        exp_aabb = n * q * q

        rows: list[dict[str, Any]] = []
        for i in range(len(data)):
            obs = np.array([aa.iloc[i], aabb.iloc[i], aa2.iloc[i]], dtype=float)
            exp = np.array([exp_aa.iloc[i], exp_het.iloc[i], exp_aabb.iloc[i]])
            n_i = n.iloc[i]
            # standard HWE chi-square with continuity correction-free exact
            # expected counts; df = 1 (one allele-frequency parameter)
            chi2 = float(((obs - exp) ** 2 / exp).sum()) if n_i > 0 else float("nan")
            pval = stats.chi2.sf(chi2, 1)
            smallest_exp = float(exp.min())
            if smallest_exp < 5:
                result.add_verdict(
                    "WARN",
                    "expected-counts",
                    f"Marker row {i + 1}: smallest expected genotype count is "
                    f"{smallest_exp:.1f} (< 5) — the chi-square approximation "
                    "is unreliable; consider Fisher's exact test.",
                )
            rows.append(
                {
                    "row": i + 1,
                    "n": int(n_i),
                    "obs_AA": int(round(aa.iloc[i])),
                    "obs_Aa": int(round(aabb.iloc[i])),
                    "obs_aa": int(round(aa2.iloc[i])),
                    "freq_A_p": round(p.iloc[i], 4),
                    "freq_a_q": round(q.iloc[i], 4),
                    "exp_AA": round(exp_aa.iloc[i], 2),
                    "exp_Aa": round(exp_het.iloc[i], 2),
                    "exp_aa": round(exp_aabb.iloc[i], 2),
                    "chi2": round(chi2, 4),
                    "p_value": pval,
                    "hwe": "consistent" if pval >= alpha else "deviation",
                }
            )
        tbl = pd.DataFrame(rows)
        result.tables["hwe_test"] = tbl

        n_dev = int((tbl["hwe"] == "deviation").sum())
        result.summaries["markers tested"] = str(len(tbl))
        result.summaries["deviation from HWE"] = str(n_dev)
        result.methods.append(
            "Hardy-Weinberg equilibrium was tested at each biallelic locus by "
            "chi-square goodness-of-fit (1 df) between observed genotype "
            "counts and expectations E(AA)=n p^2, E(Aa)=2 n p q, E(aa)=n q^2 "
            f"derived from observed allele frequencies (alpha={alpha}, seed "
            f"{ctx.seed}). Python analysis via AUPHORIA."
        )
        result.what_does_not_tell = (
            "A HWE test does NOT establish random mating or the absence of "
            "selection: it only compares genotype counts with what one "
            "expects under equilibrium, and failing to reject is not proof "
            "of equilibrium (low power with small n). It also cannot say "
            "WHY a locus deviates — inbreeding, population stratification, "
            "genotyping error and selection all look similar in this single "
            "statistic."
        )
        return result


ANALYSIS = HardyWeinbergAnalysis()
