"""Friedman test analysis for AUPHORIA.

Tests whether at least one time point differs from the others for a numeric
outcome measured on the SAME subjects at two or more times, using SciPy's
`friedmanchisquare`. It is the non-parametric counterpart of repeated-measures
ANOVA (it works on the ranks within each subject, so it does not require
normal data).

The data are expected in LONG format: one row per (subject, time) pair with
an outcome column, a subject column, and a time column. The analysis pivots
to a wide subject x time table internally.

Guardrails are enforced here, not in the front end:
- the outcome is confirmed numeric (refusing non-numeric text);
- there must be at least 2 time points and at least 3 subjects;
- a subject with ANY missing cell cannot be used (Friedman needs a complete
  block per subject) - incomplete subjects are dropped with a warning,
  never imputed; at least 4 complete subjects are required;
- pairwise post-hoc comparisons use Wilcoxon signed-rank on the wide columns
  with a Bonferroni correction.
"""
from __future__ import annotations

from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError


def _p_expr(p: float) -> str:
    return f"p {_p_rel(p)} {_p_num(p)}"


def _p_num(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def _p_rel(p: float) -> str:
    return "<" if p < 0.001 else "="


def _p_rel_num(p: float, alpha: float) -> str:
    """Plain comparison operator vs a stated alpha for a methods sentence."""
    return "<" if p < alpha else ">="


class FriedmanAnalysis(Analysis):
    id = "friedman"
    name = "Friedman Test"

    def check_fit(
        self,
        profile: Any,
        params: dict[str, Any],
        inputs: dict[str, str],
    ) -> list[str]:
        del params
        refusals: list[str] = []
        # Confirm the subject and time columns, if visible, are categorical.
        for role in ("subject", "time"):
            col_name = inputs.get(role)
            if col_name is None:
                continue
            col = profile.by_name(col_name)
            if col is not None and col.kind not in ("categorical", "text"):
                refusals.append(
                    f"'{col_name}' ({role}) looks like a {col.kind} column, "
                    "not a categorical one. The Friedman test needs a column "
                    "that identifies each subject and a column identifying "
                    "each time point."
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

        for col in (outcome_col, subject_col, time_col):
            if col not in data.columns:
                raise AssumptionError(
                    f"The data has no column named '{col}'.",
                    hint="Pick a column from your file.",
                )

        # Numeric guarantee on the outcome (refuses non-numeric text cells).
        outcome = self.ensure_numeric(data[outcome_col], outcome_col)
        ctx.log_decision(
            f"Outcome '{outcome_col}' treated as numeric; "
            f"{self.count_missing(outcome, outcome_col)} missing value(s)."
        )
        subject_raw = data[subject_col]
        time_raw = data[time_col]
        self.describe_missing(subject_raw, subject_col, ctx)
        self.describe_missing(time_raw, time_col, ctx)

        alpha = float(params["alpha"])

        # Combine the three columns and drop rows missing ANY of them, with a
        # warning. Listwise deletion on row-level missingness first.
        frame = pd.DataFrame(
            {
                outcome_col: outcome,
                subject_col: subject_raw,
                time_col: time_raw,
            }
        )
        row_dropped = int(frame.isna().any(axis=1).sum())
        frame = frame.dropna()
        if row_dropped:
            reason = (
                f"{row_dropped} row(s) had a missing value in one of the chosen "
                "columns and were left out of this test. They were counted, "
                "not changed or replaced."
            )
            result.add_warning(reason)
            ctx.log_decision(
                f"Dropped {row_dropped} row(s) missing outcome/subject/time "
                "(listwise)."
            )

        if frame.empty:
            raise AssumptionError(
                "After removing rows with missing values there were no complete "
                "rows left to test.",
                hint="Check that your outcome, subject and time columns have values.",
            )

        # Time points.
        times = sorted(frame[time_col].dropna().unique().tolist())
        if len(times) < 2:
            raise AssumptionError(
                f"The time column '{time_col}' has only 1 distinct value "
                f"('{times[0] if times else ''}'), so no repeated-measures "
                "comparison is possible.",
                hint="Choose a time column with two or more time points.",
            )
        if len(times) < 2:
            # Defensive; len(times) must be >= 2 by now.
            raise AssumptionError(
                f"The time column '{time_col}' has only {len(times)} time "
                "point(s). The Friedman test compares TWO or more times.",
            )

        # Subjects present in the data.
        subjects = sorted(frame[subject_col].dropna().unique().tolist())
        if len(subjects) < 3:
            raise AssumptionError(
                f"The subject column '{subject_col}' identifies only "
                f"{len(subjects)} subject(s). The Friedman test needs at least "
                "three subjects.",
                hint="Use a column that identifies each repeated measurement's "
                     "owner, e.g. an id.",
            )

        # Pivot to wide subject x time. Incomplete subjects (missing ANY time
        # cell) cannot contribute a complete rank-block: drop them with a
        # warning, never impute.
        wide = frame.pivot_table(
            index=subject_col,
            columns=time_col,
            values=outcome_col,
            aggfunc="first",
        )
        complete_mask = wide.notna().all(axis=1)
        n_incomplete = int((~complete_mask).sum())
        if n_incomplete:
            result.add_warning(
                f"{n_incomplete} subject(s) had at least one missing time point "
                "and so could not take part in the Friedman test. Missing cells "
                "cannot be filled in for this test, so those subjects were left "
                "out (counted, never imputed)."
            )
            ctx.log_decision(
                f"Dropped {n_incomplete} incomplete subject(s) with a missing "
                "time cell; kept as complete blocks."
            )
        wide = wide.loc[complete_mask]

        if len(wide) < 4:
            raise AssumptionError(
                f"Only {len(wide)} subject(s) had a value at every time point. "
                "The Friedman test needs at least FOUR complete subjects.",
                hint="Add more subjects or fix missing outcomes at some times.",
            )

        valid_subjects = sorted(wide.index.tolist())
        arrays = [wide[t].to_numpy(dtype=float) for t in times]

        ctx.log_decision(
            f"Running Friedman test (alpha={alpha}) across {len(times)} time "
            f"points with {len(valid_subjects)} complete subject(s)."
        )

        chi2, p_val = stats.friedmanchisquare(*arrays)
        chi2 = float(chi2)
        p_val = float(p_val)
        df = len(times) - 1
        n_subjects = len(valid_subjects)
        significant = bool(p_val < alpha)

        # --- spread/IQR helper per time
        def _run_summary(vals: np.ndarray) -> tuple[int, float, float]:
            return (
                int(len(vals)),
                float(np.median(vals)),
                float(np.subtract(*np.percentile(vals, [75, 25]))),
            )

        # --- descriptives by time
        stats_rows = []
        for t, arr in zip(times, arrays, strict=True):
            n, med, iqr = _run_summary(arr)
            stats_rows.append(
                {"Time": t, "n": n, "Median": round(med, 4), "IQR": round(iqr, 4)}
            )
        descriptives = pd.DataFrame(stats_rows)

        # --- main test table
        test_table = pd.DataFrame(
            {
                "Item": [
                    "chi2 (Friedman statistic)",
                    "degrees of freedom (df)",
                    "p-value",
                    "n (subjects)",
                    "number of time points",
                    "test",
                    "significance level (alpha)",
                    "significant at alpha?",
                ],
                "Value": [
                    round(chi2, 6),
                    df,
                    round(p_val, 6),
                    n_subjects,
                    len(times),
                    "Friedman test",
                    f"{alpha:.3f}",
                    "Yes" if significant else "No",
                ],
            }
        )
        result.tables["Descriptives by time"] = descriptives
        result.tables["Friedman test"] = test_table

        # --- pairwise post-hoc: Wilcoxon signed-rank on the wide columns
        # with a Bonferroni correction for the number of comparisons.
        n_comp = len(times) * (len(times) - 1) // 2
        posthoc_rows = []
        for t1, t2 in combinations(times, 2):
            a = wide[t1].to_numpy(dtype=float)
            b = wide[t2].to_numpy(dtype=float)
            diff = a - b
            if float(np.ptp(diff)) == 0:
                # Constant difference slice: Wilcoxon is degenerate.
                stat = 0.0
                raw_p = 1.0
            else:
                with np.errstate(invalid="ignore", divide="ignore"):
                    wres = stats.wilcoxon(a, b)
                stat = float(wres.statistic)
                raw_p = float(wres.pvalue)
            corr_p = min(1.0, raw_p * n_comp)
            posthoc_rows.append(
                {
                    "Time 1": t1,
                    "Time 2": t2,
                    "Wilcoxon W": round(stat, 4),
                    "raw p": round(raw_p, 4),
                    "Bonferroni p": round(corr_p, 4),
                    "significant (Bonf) at alpha?": (
                        "Yes" if corr_p < alpha else "No"
                    ),
                }
            )
        if posthoc_rows:
            result.tables["Pairwise comparisons"] = pd.DataFrame(posthoc_rows)

        # --- figure: median-by-time line + box
        fig = _median_figure(arrays, times, outcome_col, time_col, chi2, p_val, alpha)
        result.figures.append(
            FigureItem(
                name="friedman_by_time",
                figure=fig,
                caption=(
                    f"Median of '{outcome_col}' by '{time_col}' "
                    f"(chi2 = {chi2:.2f}, df = {df}, p = {self.fmt_p(p_val)})"
                ),
            )
        )

        # --- summaries
        meds = [float(np.median(a)) for a in arrays]
        hidx = max(range(len(meds)), key=lambda i: meds[i])
        lidx = min(range(len(meds)), key=lambda i: meds[i])
        result.summaries = {
            "chi2 (Friedman)": f"{chi2:.2f}",
            "degrees of freedom": f"{df}",
            "p-value": self.fmt_p(p_val),
            "n (complete subjects)": f"{n_subjects}",
            "significant at alpha": f"{alpha:.3f} → {'Yes' if significant else 'No'}",
            "highest median time": f"{times[hidx]} ({meds[hidx]:.2f})",
            "lowest median time": f"{times[lidx]} ({meds[lidx]:.2f})",
        }

        # --- methods.txt sentences
        methods = [
            f"A Friedman test compared the distribution of '{outcome_col}' "
            f"across {len(times)} time points ({', '.join(map(str, times))}) "
            f"measured on the same {n_subjects} subject(s) (repeated measures).",
            f"The test was run at a significance level of alpha = {alpha:.3f} "
            f"and gave chi2 = {chi2:.2f} with df = {df}, {_p_expr(p_val)}.",
            "Median by time was "
            + ", ".join(
                f"{meds[i]:.2f} (at '{times[i]}')" for i in range(len(times))
            )
            + ".",
        ]
        if significant:
            methods.append(
                f"Because p {_p_rel_num(p_val, alpha)} alpha, at least one time "
                "point is described as statistically different from the "
                "others — a spread of within-subject ranks at least this large "
                "would be unlikely under chance alone."
            )
        else:
            methods.append(
                f"Because p {_p_rel_num(p_val, alpha)} alpha, we do not have "
                "enough evidence to call a difference between the time points "
                "statistically significant."
            )
        methods.append(
            "A significant Friedman test does not say which time points differ; "
            "the pairwise comparisons use a Wilcoxon signed-rank test on each "
            "pair of time points with a Bonferroni correction."
        )
        if row_dropped or n_incomplete:
            methods.append(
                "Rows/subjects with missing values were counted and excluded; "
                "no missing values were imputed."
            )
        result.methods = methods

        # --- notes / expert review for small samples
        ctx.log_decision(
            f"chi2 = {chi2:.4f}, df = {df}, p = {p_val:.4g}, "
            f"n complete subjects = {n_subjects} across {len(times)} times."
        )
        low_subjects = int(n_subjects < 6)
        if low_subjects:
            result.add_expert_review(
                f"The Friedman test ran on only {n_subjects} complete "
                "subject(s) — below the suggested minimum of 6. The "
                "chi-squared approximation is unreliable with so few blocks, "
                "so these results need a statistician's (or your supervisor's) "
                "judgement."
            )
            ctx.log_decision(
                f"Flagged for expert review: only {n_subjects} complete "
                "subjects (< 6)."
            )

        result.what_does_not_tell = (
            "A significant Friedman test does NOT say which time points "
            "differ — it only shows that at least one time point tends to be "
            "ranked higher or lower than the others, so use the pairwise "
            "post-hoc comparisons to locate the differences. Because it works "
            "on within-subject ranks it is not a test of the medians "
            "themselves (a shift in medians needs a similar spread at each "
            "time to be read that way), and it does not measure the size of "
            "any difference. As with any observational comparison it also "
            "does not prove that time (or treatment order) caused the change."
        )
        return result


def _median_figure(
    arrays: list[np.ndarray],
    times: list,
    outcome_col: str,
    time_col: str,
    chi2: float,
    p_val: float,
    alpha: float,
):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    x = np.arange(len(times))
    medians = [float(np.median(a)) for a in arrays]
    boxes = ax.boxplot(
        arrays,
        positions=x,
        patch_artist=True,
        widths=0.45,
        medianprops=dict(color="black", linewidth=1.5),
    )
    colors = ["#7fb4d8", "#8fc98d", "#e3b877", "#d88ba0", "#9d8fc9"]
    for patch, color in zip(boxes["boxes"], colors, strict=False):
        patch.set_facecolor(color)
    rng = np.random.default_rng(0)
    for i, arr in enumerate(arrays):
        if len(arr):
            ax.scatter(
                np.full_like(arr, i * 1.0) + rng.uniform(-0.12, 0.12, len(arr)),
                arr,
                alpha=0.45,
                s=18,
                color="#333",
                edgecolor="white",
                linewidth=0.4,
            )
    ax.plot(x, medians, color="#444", marker="o", linewidth=1.6, linestyle="--")
    ax.set_xticks(x, labels=[str(t) for t in times])
    p_str = "p < 0.001" if p_val < 0.001 else f"p = {p_val:.3f}"
    ax.set_title(
        f"{outcome_col} by {time_col}\n"
        f"Friedman chi2 = {chi2:.2f}, {p_str} (alpha = {alpha:.3f})",
        fontsize=10,
    )
    ax.set_xlabel(str(time_col))
    ax.set_ylabel(outcome_col)
    ax.grid(axis="y", ls=":", alpha=0.5)
    fig.tight_layout()
    return fig


# Module-level instance the registry looks for.
ANALYSIS = FriedmanAnalysis()
