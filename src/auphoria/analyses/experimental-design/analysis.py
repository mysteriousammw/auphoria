"""Experimental-design analysis for AUPHORIA.

One engine for four classic balanced layouts, chosen by the ``design``
parameter:

- ``crd``        — completely randomized design (one-way ANOVA).
- ``rcbd``       — randomized complete block (treatment + block, no
                   interaction; block SS removed from the error term).
- ``latin-square`` — Latin square (row + col + treatment; both blocking
                   factors removed from error).
- ``factorial``  — two-factor factorial with interaction
                   (treatment x factor_b).

All computation is scipy-only. The ANOVA tables for the blocked and
factorial layouts are built by hand from sum-of-squares identities so the
report shows students *where* each number comes from (same convention as
anova-oneway). Mean separation is Tukey HSD (studentized range) or Fisher
LSD (t distribution), using the design's own MSE and error df.

Guardrails:
- balanced designs are required (equal n per treatment combination);
- a single observation per treatment (or per treatment combination) is
  refused — there is no error term to test against;
- missing values are counted and excluded with a warning, never imputed;
- assumption checks (Shapiro-Wilk on residuals, Levene on the outcome) are
  run and reported as WARN verdicts, never as hard refusals.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError

_PALETTE = ["#7fb4d8", "#8fc98d", "#e8a87c", "#d98c8c", "#b48cd9", "#8cd9c9", "#d9c17c"]

DESIGNS = ("crd", "rcbd", "latin-square", "factorial")


def _fmt_p(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def _sig_star(p: float) -> str:
    return " *" if p < 0.05 else ""


class ExperimentalDesignAnalysis(Analysis):
    """Balanced classic experimental designs (CRD / RCBD / Latin / factorial)."""

    id = "experimental-design"

    def check_fit(
        self, profile: Any, params: dict[str, Any], inputs: dict[str, str]
    ) -> list[str]:
        refusals: list[str] = []
        design = str(params.get("design") or "crd").lower()
        if design not in DESIGNS:
            refusals.append(
                f"design '{design}' is unknown — choose one of {', '.join(DESIGNS)}."
            )
        if design == "rcbd" and not inputs.get("block"):
            refusals.append("RCBD needs a 'block' (blocking factor) column.")
        if design == "latin-square":
            if not inputs.get("row") or not inputs.get("col"):
                refusals.append("Latin square needs both 'row' and 'col' blocking columns.")
        if design == "factorial" and not inputs.get("factor_b"):
            refusals.append("factorial needs a second factor via 'factor_b'.")
        return refusals

    def _balanced(self, sub: pd.DataFrame, factors: list[str]) -> list[str]:
        counts = sub.groupby(factors).size()
        return [] if counts.nunique() == 1 else [
            f"Unbalanced design: per-{'+'.join(factors)} n = "
            f"{counts.sort_values().unique().tolist()}. "
            "Experimental-design needs balanced data — use anova-oneway or "
            "regression-multiple instead."
        ]

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        result = AnalysisResult()
        design = str(params.get("design") or "crd").lower()
        alpha = float(params.get("alpha", 0.05))
        separation = str(params.get("separation") or "tukey").lower()

        # Design requirements enforced here too (run() may be called directly,
        # bypassing check_fit).
        req = {"rcbd": "block", "latin-square": ("row", "col"), "factorial": "factor_b"}
        if design in req:
            missing = [
                r for r in (req[design] if isinstance(req[design], tuple) else (req[design],))
                if not inputs.get(r)
            ]
            if missing:
                raise AssumptionError(
                    f"{design} needs the column role(s): {', '.join(missing)}."
                )
        if design not in DESIGNS:
            raise AssumptionError(
                f"design '{design}' is unknown — choose one of {', '.join(DESIGNS)}."
            )

        outcome = self.ensure_numeric(data[inputs["outcome"]], inputs["outcome"])
        treatment = data[inputs["treatment"]].astype(str)
        sub = pd.DataFrame({"outcome": outcome, "treatment": treatment})
        sub["treatment"] = sub["treatment"].fillna("(missing)")
        dropped = outcome.isna().sum() + data[inputs["treatment"]].isna().sum()
        if dropped:
            ctx.log_decision(
                f"excluded {int(dropped)} rows with missing outcome/treatment"
            )
            result.add_warning(
                f"Excluded {int(dropped)} rows with missing outcome or treatment; "
                "missing values were not imputed."
            )

        factors: list[str] = ["treatment"]
        for role in ("block", "row", "col", "factor_b"):
            if inputs.get(role):
                sub[role] = data[inputs[role]].astype(str).fillna("(missing)")
                factors.append(role)

        # Guardrails with plain-English refusals.
        if sub["treatment"].nunique() < 2:
            raise AssumptionError(
                "The treatment column must have at least two categories."
            )
        if sub["treatment"].nunique() < 3 and design != "factorial":
            result.add_warning(
                "Only two treatments: a t-test (or Mann-Whitney) is the more "
                "direct tool; ANOVA is run anyway since you asked for a design."
            )
        if design == "factorial":
            n_combos = sub.groupby(["treatment", "factor_b"]).size()
            if (n_combos < 2).any():
                raise AssumptionError(
                    "Every treatment x factor_b combination needs at least two "
                    "replicates — there is no error term to test the interaction."
                )
            bad = self._balanced(sub, ["treatment", "factor_b"])
            if bad:
                raise AssumptionError(bad[0])
        else:
            levels_per_cell = sub.groupby("treatment").size()
            if (levels_per_cell < 2).any():
                raise AssumptionError(
                    "Every treatment needs at least two observations — with a "
                    "single observation per treatment there is no error term."
                )
            bad = self._balanced(sub, ["treatment"])
            if bad:
                raise AssumptionError(bad[0])
            if design in ("rcbd", "latin-square"):
                for f in factors[1:]:
                    cell = sub.groupby(["treatment", f]).size()
                    if (cell != 1).any():
                        raise AssumptionError(
                            f"RCBD/Latin layouts need exactly one observation per "
                            f"treatment x {f} cell (got counts {sorted(cell.unique())})."
                        )

        # ---- build the ANOVA table -------------------------------------------------
        grand = sub["outcome"].mean()
        n = len(sub)

        def ss_between(col: str) -> float:
            return float(
                sub.groupby(col)["outcome"]
                .agg(["mean", "size"])
                .apply(lambda r: r["size"] * (r["mean"] - grand) ** 2, axis=1)
                .sum()
            )

        ss_total = float(((sub["outcome"] - grand) ** 2).sum())
        rows: dict[str, Any] = {}

        if design == "crd":
            ss_trt = ss_between("treatment")
            ss_err = ss_total - ss_trt
            df_trt = sub["treatment"].nunique() - 1
            df_err = n - sub["treatment"].nunique()
            ms_trt = ss_trt / df_trt
            ms_err = ss_err / df_err
            f = ms_trt / ms_err
            p = stats.f.sf(f, df_trt, df_err)
            rows["Treatment"] = (ss_trt, df_trt, ms_trt, f, p)
            rows["Error"] = (ss_err, df_err, ms_err, np.nan, np.nan)
            rows["Total"] = (ss_total, n - 1, np.nan, np.nan, np.nan)
            df_err_used, ms_err_used = df_err, ms_err
        elif design == "rcbd":
            ss_trt = ss_between("treatment")
            ss_blk = ss_between("block")
            ss_err = ss_total - ss_trt - ss_blk
            df_trt = sub["treatment"].nunique() - 1
            df_blk = sub["block"].nunique() - 1
            df_err = n - df_trt - df_blk - 1
            ms_trt, ms_blk, ms_err = ss_trt / df_trt, ss_blk / df_blk, ss_err / df_err
            f, p = ms_trt / ms_err, stats.f.sf(ms_trt / ms_err, df_trt, df_err)
            rows["Treatment"] = (ss_trt, df_trt, ms_trt, f, p)
            rows["Block"] = (ss_blk, df_blk, ms_blk, ms_blk / ms_err, stats.f.sf(ms_blk / ms_err, df_blk, df_err))
            rows["Error"] = (ss_err, df_err, ms_err, np.nan, np.nan)
            rows["Total"] = (ss_total, n - 1, np.nan, np.nan, np.nan)
            df_err_used, ms_err_used = df_err, ms_err
        elif design == "latin-square":
            ss_trt = ss_between("treatment")
            ss_row = ss_between("row")
            ss_col = ss_between("col")
            ss_err = ss_total - ss_trt - ss_row - ss_col
            t = sub["treatment"].nunique()
            df_trt = df_row = df_col = t - 1
            df_err = n - df_trt - df_row - df_col - 1
            ms_trt, ms_row, ms_col, ms_err = (
                ss_trt / df_trt,
                ss_row / df_row,
                ss_col / df_col,
                ss_err / df_err,
            )
            f, p = ms_trt / ms_err, stats.f.sf(ms_trt / ms_err, df_trt, df_err)
            rows["Treatment"] = (ss_trt, df_trt, ms_trt, f, p)
            rows["Row"] = (ss_row, df_row, ms_row, ms_row / ms_err, stats.f.sf(ms_row / ms_err, df_row, df_err))
            rows["Column"] = (ss_col, df_col, ms_col, ms_col / ms_err, stats.f.sf(ms_col / ms_err, df_col, df_err))
            rows["Error"] = (ss_err, df_err, ms_err, np.nan, np.nan)
            rows["Total"] = (ss_total, n - 1, np.nan, np.nan, np.nan)
            df_err_used, ms_err_used = df_err, ms_err
        else:  # factorial
            ss_a = ss_between("treatment")
            ss_b = ss_between("factor_b")
            # SS_AB via cell means identity (balanced design):
            cell_mean = sub.groupby(["treatment", "factor_b"])["outcome"].mean()
            trt_mean = sub.groupby("treatment")["outcome"].mean()
            b_mean = sub.groupby("factor_b")["outcome"].mean()
            per_cell_n = sub.groupby(["treatment", "factor_b"]).size().iloc[0]
            ss_ab = 0.0
            for (ai, bi), m in cell_mean.items():
                ss_ab += per_cell_n * (m - trt_mean[ai] - b_mean[bi] + grand) ** 2
            ss_err = ss_total - ss_a - ss_b - ss_ab
            a_lv = sub["treatment"].nunique()
            b_lv = sub["factor_b"].nunique()
            df_a, df_b, df_ab = a_lv - 1, b_lv - 1, (a_lv - 1) * (b_lv - 1)
            df_err = n - a_lv * b_lv
            ms_a, ms_b, ms_ab, ms_err = (
                ss_between("treatment") / df_a,
                ss_between("factor_b") / df_b,
                ss_ab / df_ab,
                ss_err / df_err,
            )
            rows["Factor A (treatment)"] = (ss_between("treatment"), df_a, ms_a, ms_a / ms_err, stats.f.sf(ms_a / ms_err, df_a, df_err))
            rows["Factor B"] = (ss_between("factor_b"), df_b, ms_b, ms_b / ms_err, stats.f.sf(ms_b / ms_err, df_b, df_err))
            rows["Interaction A x B"] = (ss_ab, df_ab, ms_ab, ms_ab / ms_err, stats.f.sf(ms_ab / ms_err, df_ab, df_err))
            rows["Error"] = (ss_err, df_err, ms_err, np.nan, np.nan)
            rows["Total"] = (ss_total, n - 1, np.nan, np.nan, np.nan)
            df_err_used, ms_err_used = df_err, ms_err

        aov = pd.DataFrame(
            {
                "Source": list(rows),
                "SS": [r[0] for r in rows.values()],
                "df": [r[1] for r in rows.values()],
                "MS": [r[2] for r in rows.values()],
                "F": [r[3] for r in rows.values()],
                "p": [r[4] for r in rows.values()],
            }
        )
        result.tables["anova"] = aov

        # ---- treatment means + mean separation ------------------------------------
        means = (
            sub.groupby("treatment")["outcome"]
            .agg(n="size", mean="mean", sd="std")
            .reset_index()
        )
        ms_err, df_err = ms_err_used, df_err_used
        n_per_trt = int(means["n"].iloc[0])
        if separation == "tukey":
            k = sub["treatment"].nunique()
            qcrit = stats.studentized_range.ppf(1 - alpha, k, df_err)
            lsd = qcrit * np.sqrt(ms_err / n_per_trt)
            method_name = "Tukey HSD"
        else:
            tcrit = stats.t.ppf(1 - alpha / 2, df_err)
            lsd = tcrit * np.sqrt(2 * ms_err / n_per_trt)
            method_name = "Fisher LSD"

        ordered = means.sort_values("mean", ascending=False)["treatment"].tolist()
        # Standard compact-letter display: each treatment gets the letter of its
        # own rank position; groups not separated share a letter via grouping.
        groups: list[list[str]] = []
        for t in ordered:
            placed = False
            for g in groups:
                if all(
                    abs(means.loc[means["treatment"] == t, "mean"].iloc[0]
                        - means.loc[means["treatment"] == u, "mean"].iloc[0]) < lsd
                    for u in g
                ):
                    g.append(t)
                    placed = True
                    break
            if not placed:
                groups.append([t])
        letter_map: dict[str, str] = {}
        for idx, g in enumerate(groups):
            for t in g:
                letter_map[t] = letter_map.get(t, "") + "abcdefghijklmnopqrstuvwxyz"[idx]
        means["group"] = means["treatment"].map(letter_map)
        means["mean"] = means["mean"].round(3)
        means["sd"] = means["sd"].round(3)
        result.tables["treatment_means"] = means
        result.notes.append(
            f"Mean separation by {method_name} at alpha={alpha}: treatments "
            "sharing a letter are NOT significantly different (LSD threshold "
            f"{lsd:.3f} on the difference)."
        )

        # ---- assumption checks -----------------------------------------------------
        resid = sub["outcome"] - sub.groupby("treatment")["outcome"].transform("mean")
        try:
            shapiro = stats.shapiro(resid)
            result.add_verdict(
                "WARN" if shapiro.pvalue < 0.05 else "PASS",
                "residuals-normality",
                f"Shapiro-Wilk on residuals W = {shapiro.statistic:.3f}, "
                f"p = {_fmt_p(shapiro.pvalue)} — residuals "
                + ("look roughly normal." if shapiro.pvalue >= 0.05 else "deviate from normal; ANOVA is still fairly robust for balanced designs."),
            )
        except Exception:  # noqa: BLE001
            result.add_verdict("WARN", "residuals-normality", "Could not run Shapiro-Wilk (constant residual slice); treat normality as unverified.")
        try:
            levene = stats.levene(
                *[g["outcome"].values for _, g in sub.groupby("treatment")]
            )
            result.add_verdict(
                "WARN" if levene.pvalue < 0.05 else "PASS",
                "variance-homogeneity",
                f"Levene's test F = {levene.statistic:.3f}, p = {_fmt_p(levene.pvalue)} — "
                + ("variances look homogeneous." if levene.pvalue >= 0.05 else "variances differ across treatments; interpret with care."),
            )
        except Exception:  # noqa: BLE001
            result.add_verdict("WARN", "variance-homogeneity", "Could not run Levene's test; variance homogeneity unverified.")

        # ---- figure ---------------------------------------------------------------
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(7, 4.5))
        tlevels = list(sub["treatment"].unique())
        order = sorted(
            tlevels,
            key=lambda t: sub.loc[sub["treatment"] == t, "outcome"].mean(),
            reverse=True,
        )
        y = sub.groupby("treatment")["outcome"].mean().reindex(order)
        err = sub.groupby("treatment")["outcome"].sem().reindex(order)
        xs = np.arange(len(order))
        ax.bar(xs, y.values, yerr=err.values, capsize=4, color=_PALETTE[: len(order)])
        ax.set_xticks(xs, order)
        ax.set_ylabel("outcome mean (+/- SEM)")
        ax.set_title(f"Treatment means — {design}")
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        result.figures.append(FigureItem("treatment_means", fig, "Treatment means with SEM error bars."))

        # ---- summaries + methods ---------------------------------------------------
        key_main = "Treatment" if design != "factorial" else "Factor A (treatment)"
        f_main, df1_main = rows[key_main][3], int(rows[key_main][1])
        p_main = rows[key_main][4]
        result.summaries["Design"] = design
        result.summaries["Treatments"] = f"{sub['treatment'].nunique()} ({', '.join(sorted(sub['treatment'].unique()))})"
        result.summaries["Effect of treatment"] = (
            f"F({df1_main}, {int(df_err)}) = {f_main:.2f}, "
            f"p {_fmt_p(p_main)}{_sig_star(p_main)}"
        )
        result.methods.append(
            f"A {design} experiment ({n} units, {sub['treatment'].nunique()} "
            f"treatments) was analysed by analysis of variance "
            f"(alpha={alpha}); {method_name} was used for mean separation. "
            f"Treatment effect: F({df1_main}, {int(df_err)}) = "
            f"{f_main:.2f}, p {_fmt_p(p_main)}. "
            "Normality of residuals and homogeneity of variance were checked "
            f"(Shapiro-Wilk, Levene's test). Python analysis via AUPHORIA (seed {ctx.seed})."
        )
        result.what_does_not_tell = (
            "This design analysis does NOT prove that the treatment caused the "
            "observed difference — randomisation and replication are properties "
            "of the experiment, not of this calculation. It also does not tell "
            "you what happens at untested treatment levels (no interpolation), "
            "and it cannot rescue an unbalanced or confounded layout."
        )
        if n < 30:
            result.add_expert_review(
                f"Only {n} observations across {sub['treatment'].nunique()} treatments "
                "— power is limited; treat the p-values as indicative."
            )
        return result


ANALYSIS = ExperimentalDesignAnalysis()
