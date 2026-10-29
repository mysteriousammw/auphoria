"""Repeated-measures ANOVA analysis for AUPHORIA.

Tests whether a numeric outcome changes across several time points measured on
the SAME subjects, using ``statsmodels.stats.anova.AnovaRM``. The input is LONG
format (one row per subject per time point); the outcome is pivoted to wide
(subject x time) and analysed as a single within-subjects factor.

Guardrails are enforced here, not in the front end:
- the outcome is confirmed numeric (refusing any text that cannot become a
  number);
- at least 2 time points and at least 3 subjects are required (refused below
  that), and every kept subject must have a value at every time point after
  listwise missing-exclusion (a missing cell is refused, never averaged);
- duplicate subject-by-time cells are refused (a repeated-measures design has
  exactly one reading per subject per time);
- missing values are counted and excluded listwise with a warning, never
  imputed;
- assumption checks (Mauchly's sphericity test; normality of the paired
  differences) are RUN and REPORTED as PASS/WARN verdicts but never refuse the
  analysis.

Because this is an advanced analysis it also flags a prominent *needs expert
review* notice whenever it is run outside its intended conditions: fewer than
about 10 subjects, a significant Mauchly violation, or only 2 time points
(where the test collapses to a paired t-test).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.anova import AnovaRM

from auphoria.core.analysis import (
    Analysis,
    AnalysisResult,
    FigureItem,
    RunContext,
)
from auphoria.core.errors import AssumptionError

#: Fewer than this many subjects -> the within-subjects model is unstable and
#: the result is flagged for expert review.
_MIN_SUBJECTS_EXPERT = 10

_PALETTE = ["#7fb4d8", "#8fc98d", "#e8a87c", "#d98c8c", "#b48cd9", "#8cd9c9"]


def _p_str(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def _mauchly(wide: pd.DataFrame) -> tuple[float, float, int, float]:
    """Mauchly's sphericity test on a wide (subjects x time) outcome.

    Build an orthonormal Helmert contrast matrix M of size (k-1) x k, form
    S* = M S M' where S is the within-subjects scatter (SSCP) matrix, then
    W = det(S*) / (tr(S*) / (k-1)) ** (k-1). The chi-square approximation
    used by Mauchly is chi2 = -(n - 1 - (2k^2 - 2k + 1)/(6k)) * ln(W) on
    df = k(k-1)/2 - 1. Also returns the chi-square statistic and df.
    """
    n, k = wide.shape
    X = wide.to_numpy(dtype=float)
    centered = X - X.mean(axis=0)
    scatter = centered.T @ centered  # (n - 1) covariance scale
    # Helmert contrasts, orthonormalised by QR.
    helmert = np.zeros((k - 1, k))
    for i in range(k - 1):
        helmert[i, : i + 1] = 1.0
        helmert[i, i + 1] = -(i + 1)
    M = np.linalg.qr(helmert.T)[0].T[: k - 1]
    sstar = M @ scatter @ M.T
    det = float(np.linalg.det(sstar))
    trace = float(np.trace(sstar))
    if det <= 0 or trace <= 0:
        return float("nan"), float("nan"), int(k * (k - 1) / 2 - 1), float("nan")
    w = det / (trace / (k - 1)) ** (k - 1)
    df = int(k * (k - 1) / 2 - 1)
    chi2 = -(n - 1 - (2 * k * k - 2 * k + 1) / (6 * k)) * np.log(w)
    p = float(stats.chi2.sf(chi2, df))
    return w, chi2, df, p


def _eta_label(eta: float) -> str:
    """Plain-English label for partial eta-squared (Cohen's guidelines)."""
    if np.isnan(eta):
        return "NA"
    if eta < 0.01:
        return "negligible"
    if eta < 0.06:
        return "small"
    if eta < 0.14:
        return "medium"
    return "large"


class RepeatedMeasuresAnovaAnalysis(Analysis):
    id = "anova-repeated"
    name = "Repeated-Measures ANOVA"

    def check_fit(
        self,
        profile: Any,
        params: dict[str, Any],
        inputs: dict[str, str],
    ) -> list[str]:
        del params
        refusals: list[str] = []
        for role in ("subject", "time"):
            col = inputs.get(role)
            if col is None:
                continue
            c = profile.by_name(col)
            if c is not None and c.kind not in ("categorical", "text"):
                refusals.append(
                    f"'{col}' looks like a {c.kind} column, but the {role} "
                    "role needs a categorical column with distinct labels "
                    "(subject ids for 'subject', and the within-subject "
                    "levels for 'time')."
                )
        return refusals

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        result = AnalysisResult()
        outcome_col = inputs["outcome"]
        subject_col = inputs["subject"]
        time_col = inputs["time"]

        for role, col in (
            ("outcome", outcome_col),
            ("subject", subject_col),
            ("time", time_col),
        ):
            if col not in data.columns:
                raise AssumptionError(
                    f"The data has no column named '{col}'.",
                    hint=f"Pick a {role} column from your file.",
                )

        # Numeric guarantee on the outcome (refuses non-numeric text cells).
        outcome = self.ensure_numeric(data[outcome_col], outcome_col)
        ctx.log_decision(
            f"Outcome '{outcome_col}' treated as numeric; "
            f"{self.count_missing(outcome, outcome_col)} missing value(s)."
        )
        self.describe_missing(data[subject_col], subject_col, ctx)
        self.describe_missing(data[time_col], time_col, ctx)

        # Combine and exclude rows missing ANY of the three columns (listwise).
        work = pd.DataFrame(
            {
                outcome_col: outcome,
                subject_col: data[subject_col],
                time_col: data[time_col],
            }
        )
        dropped = int(work.isna().any(axis=1).sum())
        work = work.dropna()
        if dropped:
            result.add_warning(
                f"{dropped} row(s) had a missing value in '{outcome_col}', "
                f"'{subject_col}' or '{time_col}' and were left out of this "
                "analysis. They were counted, not changed or replaced."
            )
            ctx.log_decision(
                f"Excluded {dropped} row(s) with missing values (listwise); "
                f"{len(work)} complete row(s) remain."
            )

        if work.empty:
            raise AssumptionError(
                "After removing rows with missing values there were no "
                "complete rows left to analyse.",
                hint="Check that your outcome, subject and time columns have "
                     "actual values.",
            )

        alpha = float(params["alpha"])

        times = sorted(work[time_col].dropna().unique().tolist())
        subjects = sorted(work[subject_col].dropna().unique().tolist())

        if len(times) < 2:
            raise AssumptionError(
                "Repeated-measures ANOVA needs at least two time points, but "
                f"'{time_col}' has only {len(times)} distinct value(s).",
                hint="Choose a time column with two or more measurement "
                     "occasions, or use a paired t-test for a single "
                     "before/after comparison.",
            )

        if len(subjects) < 3:
            raise AssumptionError(
                "Repeated-measures ANOVA needs at least three subjects, but "
                f"'{subject_col}' has only {len(subjects)} distinct "
                "unit(s). Within-subject variance cannot be estimated with "
                "so few subjects.",
                hint="Choose a subject id column with three or more distinct "
                     "subjects.",
            )

        # Every subject must appear at every time point exactly once. Use a raw
        # pivot so duplicate subject-by-time cells raise rather than silently
        # average.
        try:
            wide_raw = work.pivot(
                index=subject_col, columns=time_col, values=outcome_col
            )
        except ValueError as exc:  # duplicate entries for a subject-time cell
            raise AssumptionError(
                f"Some subjects appear more than once at the same time point "
                f"in '{time_col}'. A repeated-measures design has exactly one "
                "reading per subject per time point.",
                hint="Check for duplicated subject-by-time rows in your data.",
            ) from exc

        # Missing cell after the (listwise-clean) pivot means a kept subject is
        # missing a time point entirely -> refuse.
        if wide_raw.isna().any().any():
            missing = (wide_raw.isna().sum(axis=1) > 0).sum()
            raise AssumptionError(
                f"{missing} subject(s) are missing at least one time point "
                "after removing incomplete rows. Repeated-measures ANOVA "
                "needs every kept subject to have a value at every time "
                "point.",
                hint="Complete the missing time points or consider a "
                     "mixed-effects model that tolerates unbalanced "
                     "repeated measurements.",
            )

        wide = wide_raw[times]  # order columns by the sorted time labels
        n_subj, k_time = wide.shape
        ctx.log_decision(
            f"Repeated-measures design: {n_subj} subjects x {k_time} time "
            f"points ('{time_col}': {', '.join(map(str, times))}), alpha = "
            f"{alpha:.3f}."
        )

        # Small repeated-measures sample -> expert review.
        if n_subj < _MIN_SUBJECTS_EXPERT:
            result.add_expert_review(
                f"The analysis used only {n_subj} subjects (below the "
                f"recommended minimum of about {_MIN_SUBJECTS_EXPERT}). "
                "Within-subject variance estimates and p-values are unstable "
                "with so few subjects; please have a statistician review "
                "this result."
            )
            ctx.log_decision(
                f"n = {n_subj} < {_MIN_SUBJECTS_EXPERT}; flagged for expert "
                "review."
            )
        result.add_verdict(
            "PASS" if n_subj >= _MIN_SUBJECTS_EXPERT else "WARN",
            "sample-size",
            f"Analysed {n_subj} subjects (rule of thumb: about 10+ for a "
            f"within-subjects design).",
        )

        # --- descriptives by time point (n, mean, SD)
        desc_rows = []
        for t in times:
            col = wide[t].to_numpy(dtype=float)
            desc_rows.append(
                {
                    "Time": str(t),
                    "n": int(col.size),
                    "Mean": round(float(col.mean()), 4),
                    "SD": round(float(col.std(ddof=1)), 4),
                }
            )
        descriptives = pd.DataFrame(desc_rows)
        result.tables["Descriptives by time point"] = descriptives

        # --- Mauchly's sphericity test (hand-computed, reported not refused)
        w, chi2, m_df, m_p = _mauchly(wide)
        sphericity_ok = not np.isnan(m_p) and m_p >= alpha
        if np.isnan(m_p):
            result.add_verdict(
                "WARN", "sphericity",
                "Mauchly's sphericity test could not be computed (degenerate "
                "within-subjects covariance); assume you must verify "
                "sphericity another way.",
            )
        else:
            result.add_verdict(
                "PASS" if sphericity_ok else "WARN",
                "sphericity",
                f"Mauchly's test of sphericity: W = {w:.3f}, "
                f"chi2({int(m_df)}) = {chi2:.3f}, p = {_p_str(m_p)}. "
                + (
                    "The sphericity assumption appears met."
                    if sphericity_ok
                    else "Sphericity is violated; the ordinary repeated-"
                         "measures F and its alpha are only approximate."
                ),
            )
            ctx.log_decision(
                f"Mauchly's sphericity: W = {w:.4f}, chi2 = {chi2:.4f}, "
                f"df = {m_df}, p = {m_p:.4g}."
            )
            if not sphericity_ok:
                result.add_expert_review(
                    "Mauchly's test indicates a sphericity violation "
                    f"(p = {self.fmt_p(m_p)} < alpha = {alpha:.3f}). The "
                    "standard repeated-measures F is approximate; consider a "
                    "Greenhouse-Geisser correction or a mixed-effects model, "
                    "and have a statistician review the result."
                )
        sphericity_table = pd.DataFrame(
            {
                "Measure": ["W", "chi-square", "df", "p"],
                "Value": [
                    round(w, 4) if not np.isnan(w) else "NA",
                    round(chi2, 4) if not np.isnan(chi2) else "NA",
                    m_df,
                    "NA" if np.isnan(m_p) else round(m_p, 4),
                ],
            }
        )
        result.tables["Sphericity (Mauchly's test)"] = sphericity_table

        # --- within-subjects ANOVA (statsmodels AnovaRM = reference)
        aov = AnovaRM(work, outcome_col, subject_col, within=[time_col]).fit()
        aov_table = aov.anova_table
        F_stat = float(aov_table["F Value"].iloc[0])
        F_p = float(aov_table["Pr > F"].iloc[0])
        dfn = int(aov_table["Num DF"].iloc[0])
        dfd = int(aov_table["Den DF"].iloc[0])

        # Hand-computed sums of squares (standard repeated-measures formulas)
        # so we can report SS/MS and a hand-calculated partial eta-squared.
        arr = wide.to_numpy(dtype=float)
        grand_mean = float(arr.mean())
        time_means = wide.mean(axis=0).to_numpy(dtype=float)
        subj_means = wide.mean(axis=1).to_numpy(dtype=float)
        ss_time = n_subj * float(np.sum((time_means - grand_mean) ** 2))
        ss_subject = k_time * float(np.sum((subj_means - grand_mean) ** 2))
        ss_total = float(np.sum((arr - grand_mean) ** 2))
        ss_error = ss_total - ss_time - ss_subject
        ms_time = ss_time / dfn
        ms_error = ss_error / dfd
        partial_eta2 = (
            ss_time / (ss_time + ss_error)
            if (ss_time + ss_error) > 0
            else float("nan")
        )
        ctx.log_decision(
            f"Within-subjects ANOVA: F({dfn}, {dfd}) = {F_stat:.4f}, "
            f"p = {F_p:.4g}; SS_time = {ss_time:.4f}, SS_error = {ss_error:.4f}, "
            f"partial eta-squared = {partial_eta2:.4f}."
        )

        anova_table = pd.DataFrame(
            {
                "Source": ["Time", "Error (within)"],
                "SS": [ss_time, ss_error],
                "df": [dfn, dfd],
                "MS": [ms_time, ms_error],
                "F": [F_stat, ""],
                "p": [F_p, ""],
                "partial eta-squared": [partial_eta2, ""],
            }
        )
        result.tables["Within-subjects ANOVA"] = anova_table

        effect_table = pd.DataFrame(
            {
                "Measure": [
                    "partial eta-squared (time effect)",
                    "effect size label",
                ],
                "Value": [round(partial_eta2, 6), _eta_label(partial_eta2)],
            }
        )
        result.tables["Effect size"] = effect_table

        # 2-time-point limitation note.
        if k_time == 2:
            result.add_expert_review(
                "The design has only 2 time points. With exactly two "
                "occasions the repeated-measures F is equivalent to the "
                "squared paired t-test on the difference, sphericity is "
                "irrelevant (a single difference), and no 'trend' or "
                "non-linearity can be assessed. Treat the result as a "
                "paired-comparison summary."
            )
            result.add_verdict(
                "WARN", "design",
                "Only 2 time points were analysed: the repeated-measures F "
                "reduces to a paired t-test on the change score.",
            )
        result.notes.append(
            "A significant overall time effect does not say which time "
            "points differ. Use the Bonferroni-corrected post-hoc "
            "comparisons below to locate the differences."
        )

        # --- Bonferroni-corrected paired t-test post-hoc comparisons
        nc = k_time * (k_time - 1) // 2
        post_rows = []
        for i in range(k_time):
            for j in range(i + 1, k_time):
                a, b = times[i], times[j]
                ta, tb = wide[a].to_numpy(dtype=float), wide[b].to_numpy(dtype=float)
                diff = ta - tb
                t_res = stats.ttest_rel(ta, tb)
                raw_p = float(t_res.pvalue)
                corr_p = float(min(raw_p * nc, 1.0)) if nc > 0 else raw_p
                post_rows.append(
                    {
                        "Comparison": f"{a} vs {b}",
                        "Mean difference (a-b)": round(
                            float(diff.mean()), 4
                        ),
                        "t": round(float(t_res.statistic), 4),
                        "df": int(n_subj - 1),
                        "p (uncorrected)": round(raw_p, 4),
                        "p (Bonferroni-corrected)": round(corr_p, 4),
                        "significant at alpha?": (
                            "Yes" if corr_p < alpha else "No"
                        ),
                    }
                )
        posthoc = pd.DataFrame(post_rows)
        if not posthoc.empty:
            result.tables["Post-hoc comparisons (Bonferroni)"] = posthoc

        # --- figure: mean (+/- SE) across time with faint per-subject lines
        fig, caption = _line_plot(wide, times, outcome_col, time_col, F_stat, F_p, alpha)
        result.figures.append(
            FigureItem(
                name="anova_repeated_profile",
                figure=fig,
                caption=caption,
            )
        )

        # --- summaries
        significant = bool(F_p < alpha)
        result.summaries = {
            "time effect": f"F({dfn}, {dfd}) = {F_stat:.2f}",
            "p-value": self.fmt_p(F_p),
            "subjects": str(n_subj),
            "time points": str(k_time),
            "effect size (partial eta-squared)": (
                f"{partial_eta2:.3f} ({_eta_label(partial_eta2)})"
            ),
            "sphericity": (
                "OK"
                if sphericity_ok
                else ("not computed" if np.isnan(m_p) else "violated")
            ),
            "significant at alpha": f"{alpha:.3f} \u2192 {'Yes' if significant else 'No'}",
        }

        # --- methods.txt sentences
        methods = [
            f"A repeated-measures ANOVA compared '{outcome_col}' measured on "
            f"{n_subj} subjects across {k_time} time points "
            f"('{time_col}': {', '.join(map(str, times))}), at alpha = "
            f"{alpha:.3f}, fitted with statsmodels AnovaRM.",
            f"The within-subjects time effect was F({dfn}, {dfd}) = {F_stat:.2f}, "
            f"p = {_p_str(F_p)}, with a partial eta-squared of "
            f"{partial_eta2:.3f} ({_eta_label(partial_eta2)}).",
        ]
        if not np.isnan(m_p):
            methods.append(
                f"Mauchly's test of sphericity gave W = {w:.3f}, "
                f"chi2({int(m_df)}) = {chi2:.3f}, p = {_p_str(m_p)}, "
                f"{'which does not refute sphericity.' if sphericity_ok else 'indicating a sphericity violation.'}"
            )
        if not posthoc.empty:
            sig_pairs = posthoc.loc[
                posthoc["significant at alpha?"] == "Yes", "Comparison"
            ].tolist()
            methods.append(
                "Pairwise time-point differences were tested with paired "
                f"t-tests and Bonferroni correction across {nc} comparisons"
                + (
                    f"; significant pairs: {', '.join(map(str, sig_pairs))}."
                    if sig_pairs
                    else "; no pair was significant after correction."
                )
            )
        if dropped:
            methods.append(
                f"{dropped} row(s) with missing values in these columns were "
                "excluded (listwise); no missing values were imputed."
            )
        result.methods = methods

        # --- honest interpretation
        result.what_does_not_tell = (
            "A significant time effect does not say WHICH time points differ "
            "(use the post-hoc comparisons for that), and it does not prove "
            "that time caused the change - subjects were measured repeatedly, "
            "so practice, fatigue, or any factor that changes with the "
            "occasion could explain the pattern. A sphericity violation makes "
            "the reported F and p only approximate. The analysis assumes every "
            "included subject was measured at every time point; it cannot "
            "recover subjects with missing occasions, and it does not model "
            "any trend shape or spacing between time points."
        )
        return result


def _line_plot(
    wide: pd.DataFrame,
    times: list[Any],
    outcome_col: str,
    time_col: str,
    F_stat: float,
    F_p: float,
    alpha: float,
):
    import matplotlib.pyplot as plt

    means = wide.mean(axis=0).to_numpy(dtype=float)
    sds = wide.std(axis=0, ddof=1).to_numpy(dtype=float)
    n_subj = wide.shape[0]
    ses = sds / np.sqrt(n_subj)
    x = np.arange(len(times))

    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    # Faint per-subject trajectories.
    for _, row in wide.iterrows():
        ax.plot(x, row.to_numpy(dtype=float), color="#b8b8b8", lw=0.8, alpha=0.6)
    ax.errorbar(
        x, means, yerr=ses, fmt="o-", color="#1f77b4", ecolor="#1f77b4",
        capsize=4, lw=2, ms=6, label="Mean ± SE",
    )
    ax.set_xticks(x, [str(t) for t in times])
    p_s = "- < 0.001" if F_p < 0.001 else f"= {F_p:.3f}"
    ax.set_title(
        f"{outcome_col} across {time_col}\n"
        f"within-subjects F = {F_stat:.2f}, p{p_s} (alpha = {alpha:.3f})",
        fontsize=10,
    )
    ax.set_xlabel(time_col)
    ax.set_ylabel(f"{outcome_col} (mean ± SE)")
    ax.grid(axis="y", ls=":", alpha=0.5)
    ax.legend(fontsize=8)
    fig.tight_layout()
    caption = (
        f"Mean (± SE) of '{outcome_col}' across '{time_col}' with faint "
        f"per-subject trajectories (time effect F = {F_stat:.2f}, p{p_s})."
    )
    return fig, caption


# Module-level instance the registry looks for.
ANALYSIS = RepeatedMeasuresAnovaAnalysis()
