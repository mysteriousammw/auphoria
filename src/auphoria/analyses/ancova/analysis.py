"""ANCOVA (analysis of covariance) analysis for AUPHORIA.

Tests whether independent groups differ on a numeric outcome after adjusting
for one numeric covariate, using statsmodels OLS:

    outcome ~ covariate + C(group)

Because covariate-adjustment is the whole point of ANCOVA, the group effect is
reported as a *partial* F test computed by comparing the full model to the
reduced model that drops only the group term (equivalent to the covariate-
adjusted sum of squares for group). The covariate coefficient and its p-value
come from the full-model summary.

Guardrails are enforced here, not in the front end:
- outcome and covariate are confirmed numeric (refusing any text that cannot
  become a number);
- the group must have at least two categories (a single category is refused);
- any group with fewer than two observations is refused; small groups warn;
- missing values are counted and excluded with a warning, never imputed;
- assumption checks (linearity via the covariate coefficient, homogeneity of
  regression slopes via the group-by-covariate interaction, normality of the
  residuals via Shapiro-Wilk) are RUN and REPORTED as PASS/WARN verdicts but
  never refuse the analysis.

Because this is an advanced analysis it also flags a prominent *needs expert
review* notice whenever it is run outside its intended conditions: fewer than
about 12 complete rows in total, any very small group, or clearly non-normal
residuals.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.formula.api import ols

from auphoria.core.analysis import (
    Analysis,
    AnalysisResult,
    FigureItem,
    RunContext,
)
from auphoria.core.errors import AssumptionError

# Recommended minimum total sample size for a covariate-adjusted comparison.
_MIN_TOTAL_N = 12
# Below this many observations per group the analysis is sensitive to the
# assumptions and is flagged for expert review.
_SMALL_GROUP_N = 5

_PALETTE = ["#7fb4d8", "#e8a87c", "#8fc98d", "#d98c8c", "#b48cd9", "#8cd9c9"]


def _p_str(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def _f_p(f_stat: float, dfn: float, dfd: float) -> float:
    """Two-sided p for an F statistic from the central F distribution."""
    return float(stats.f.sf(f_stat, dfn, dfd))


class AncovaAnalysis(Analysis):
    id = "ancova"
    name = "ANCOVA (Analysis of Covariance)"

    def check_fit(
        self,
        profile: Any,
        params: dict[str, Any],
        inputs: dict[str, str],
    ) -> list[str]:
        del params
        refusals: list[str] = []
        # Confirm the group column, if we can see it, is categorical.
        group_col = inputs.get("group")
        if group_col is not None:
            col = profile.by_name(group_col)
            if col is not None and col.kind not in ("categorical", "text"):
                refusals.append(
                    f"'{group_col}' looks like a {col.kind} column, not a "
                    "group. ANCOVA needs a grouping column with two or more "
                    "categories (e.g. treatment / control)."
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
        group_col = inputs["group"]
        cov_col = inputs["covariate"]

        for role, col in (
            ("outcome", outcome_col),
            ("group", group_col),
            ("covariate", cov_col),
        ):
            if col not in data.columns:
                raise AssumptionError(
                    f"The data has no column named '{col}'.",
                    hint=f"Pick a {role} column from your file.",
                )

        # Numeric guarantee on outcome and covariate (refuses text cells).
        outcome = self.ensure_numeric(data[outcome_col], outcome_col)
        covariate = self.ensure_numeric(data[cov_col], cov_col)
        for col, s in ((outcome_col, outcome), (cov_col, covariate)):
            ctx.log_decision(
                f"'{col}' treated as numeric; "
                f"{self.count_missing(s, col)} missing value(s)."
            )

        group_raw = data[group_col]
        self.describe_missing(group_raw, group_col, ctx)

        # Combine and listwise-exclude rows missing ANY of the three columns.
        work = pd.DataFrame(
            {outcome_col: outcome, group_col: group_raw, cov_col: covariate}
        )
        dropped = int(work.isna().any(axis=1).sum())
        work = work.dropna()
        if dropped:
            result.add_warning(
                f"{dropped} row(s) had a missing value in '{outcome_col}', "
                f"'{group_col}' or '{cov_col}' and were left out of this "
                "analysis. They were counted, not changed or replaced."
            )
            ctx.log_decision(
                f"Excluded {dropped} row(s) with missing outcome/group/covariate "
                f"(listwise); {len(work)} complete row(s) remain."
            )

        if work.empty:
            raise AssumptionError(
                "After removing rows with missing values there were no complete "
                "rows left to analyse.",
                hint="Check that your outcome, group and covariate columns "
                     "have actual values.",
            )

        groups = sorted(work[group_col].dropna().unique().tolist())
        if len(groups) < 2:
            raise AssumptionError(
                f"The group column '{group_col}' has only {len(groups)} distinct "
                "value(s), so a covariate-adjusted comparison between groups is "
                "impossible. ANCOVA needs at least two groups.",
                hint="Choose a group column with two or more categories "
                     "(treatment vs control), or fit a plain regression if you "
                     "have no grouping.",
            )

        alpha = float(params["alpha"])
        ctx.log_decision(
            f"Running ANCOVA (alpha = {alpha:.3f}): '{outcome_col}' ~ "
            f"'{cov_col}' + group '{group_col}' with {len(groups)} groups: "
            f"{', '.join(map(str, groups))}. Total complete n = {len(work)}."
        )

        # Per-group counts; refuse single-observation groups, warn small ones.
        group_counts: dict[Any, int] = {}
        for g in groups:
            n = int((work[group_col] == g).sum())
            group_counts[g] = n
            if n < 2:
                raise AssumptionError(
                    "Each group needs at least two observations.",
                    hint=f"Group '{g}' has {n} observation(s). Add data or "
                         "choose another grouping.",
                )
        for g, n in group_counts.items():
            if n < _SMALL_GROUP_N:
                result.add_warning(
                    f"Group '{g}' is small (n = {n}). ANCOVA still runs, but a "
                    "covariate-adjusted mean for this group is sensitive to the "
                    "linearity and normality assumptions — treat it as "
                    "preliminary."
                )
                ctx.log_decision(
                    f"Group '{g}' has fewer than {_SMALL_GROUP_N} observations "
                    f"({n}); added a small-group warning."
                )

        # Expert-review banner for small total sample.
        if len(work) < _MIN_TOTAL_N:
            result.add_expert_review(
                f"The total number of complete rows is only {len(work)} "
                f"(below the recommended minimum of about {_MIN_TOTAL_N} for a "
                f"covariate-adjusted comparison). The adjusted means and "
                f"p-values should be reviewed by a statistician before use."
            )
            ctx.log_decision(
                f"Total n = {len(work)} < {_MIN_TOTAL_N}; flagged for expert "
                "review."
            )
        for g, n in group_counts.items():
            if n < _SMALL_GROUP_N:
                result.add_expert_review(
                    f"Group '{g}' has only {n} row(s) (recommended minimum "
                    f"about {_SMALL_GROUP_N} per group). Its adjusted mean is "
                    "unstable; the whole result needs expert review."
                )

        # --- fit ANCOVA with statsmodels OLS
        # Rename columns to safe identifiers so patsy never misparses names.
        safe = pd.DataFrame(
            {
                "out": work[outcome_col].to_numpy(dtype=float),
                "grp": work[group_col],
                "cov": work[cov_col].to_numpy(dtype=float),
            }
        )
        full = ols("out ~ cov + C(grp)", data=safe).fit()
        ctx.log_decision(
            "Fitted OLS: out ~ cov + C(grp) (statsmodels). "
            f"n = {int(full.nobs)}, df_resid = {int(full.df_resid)}."
        )

        # Reduced models for partial F tests (the actual ANCOVA comparisons).
        red_group = ols("out ~ cov", data=safe).fit()          # drop group
        red_cov = ols("out ~ C(grp)", data=safe).fit()         # drop covariate

        sse_full = float(full.ssr)
        sse_no_group = float(red_group.ssr)
        sse_no_cov = float(red_cov.ssr)

        # Group effect: fully covariate-adjusted (this is THE ANCOVA test).
        dfn_g = int(full.df_model - red_group.df_model)
        dfd = int(full.df_resid)
        ss_group = sse_no_group - sse_full
        ms_group = ss_group / dfn_g
        ms_error = sse_full / dfd
        F_group = float(ms_group / ms_error)
        p_group = _f_p(F_group, dfn_g, dfd)

        # Covariate effect: adjusted for group.
        dfn_c = int(full.df_model - red_cov.df_model)
        ss_cov = sse_no_cov - sse_full
        ms_cov = ss_cov / dfn_c
        F_cov = float(ms_cov / ms_error)
        p_cov = _f_p(F_cov, dfn_c, dfd)

        cov_coef = float(full.params["cov"])
        cov_se = float(full.bse["cov"])
        cov_t = float(cov_coef / cov_se)
        cov_p = float(full.pvalues["cov"])

        # Partial eta-squared for the group effect.
        partial_eta2 = ss_group / (ss_group + sse_full)
        ctx.log_decision(
            f"Group effect (covariate-adjusted): F({dfn_g}, {dfd}) = "
            f"{F_group:.4f}, p = {p_group:.4g}, SS_group = {ss_group:.4f}. "
            f"Covariate: coefficient = {cov_coef:.4f}, t = {cov_t:.4f}, "
            f"p = {cov_p:.4g}. Partial eta-squared = {partial_eta2:.4f}."
        )

        # --- assumption checks: RUN and REPORT, never refuse
        # (1) homogeneity of regression slopes: group-by-covariate interaction.
        interactive = ols("out ~ cov + C(grp) + cov:C(grp)", data=safe).fit()
        try:
            int_t = interactive.f_test("cov:C(grp)")
            F_int = float(int_t.fvalue)
            p_int = float(int_t.pvalue)
        except Exception:  # noqa: BLE001 - singular design, cannot test
            F_int, p_int = float("nan"), float("nan")
            ctx.log_decision(
                "Homogeneity-of-slopes test skipped: singular or un-testable "
                "interaction design."
            )
            result.add_verdict(
                "WARN", "homogeneity-of-slopes",
                "The group-by-covariate interaction could not be tested on this "
                "data (singular design); assume you must verify visually.",
            )
        else:
            ctx.log_decision(
                f"Homogeneity of slopes (cov:C(grp) interaction): "
                f"F = {F_int:.4f}, p = {p_int:.4g} (alpha = {alpha:.3f})."
            )
            if not np.isnan(p_int) and p_int < alpha:
                result.add_verdict(
                    "WARN", "homogeneity-of-slopes",
                    "The group-by-covariate slope interaction is significant "
                    f"(p = {self.fmt_p(p_int)} < alpha = {alpha:.3f}). The "
                    "assumption of parallel slopes is violated, so the "
                    "covariate-adjusted group comparison is hard to interpret. "
                    "ANCOVA is reported but needs expert review.",
                )
                result.add_expert_review(
                    "The homogeneity-of-regression-slopes assumption is "
                    "violated (significant covariate-by-group interaction). "
                    "The adjusted means and group effect should be reviewed by "
                    "a statistician."
                )
            else:
                result.add_verdict(
                    "PASS", "homogeneity-of-slopes",
                    f"No evidence that the outcome-covariate slope differs "
                    f"across groups (interaction p = {self.fmt_p(p_int)}). "
                    "Parallel-slope ANCOVA is reasonable.",
                )

        # (2) normality of residuals (Shapiro-Wilk).
        resid = pd.Series(full.resid)
        n_resid = len(resid)
        if 3 <= n_resid <= 5000 and np.ptp(resid.to_numpy()) != 0:
            w_stat, w_p = stats.shapiro(resid)
            if np.isnan(w_stat) or np.isnan(w_p):
                ctx.log_decision(
                    f"Shapiro-Wilk on residuals returned no usable p-value "
                    f"(W = {w_stat}); skipped."
                )
            else:
                ctx.log_decision(
                    f"Shapiro-Wilk normality of residuals: W = {w_stat:.4f}, "
                    f"p = {w_p:.4g} (alpha = {alpha:.3f})."
                )
                if w_p < alpha:
                    result.add_verdict(
                        "WARN", "normality",
                        f"The model residuals deviate from a normal "
                        f"distribution (Shapiro-Wilk, p = {self.fmt_p(w_p)} < "
                        f"alpha = {alpha:.3f}). ANCOVA is still reported but "
                        "the normality assumption is violated.",
                    )
                    result.add_expert_review(
                        "The residuals deviate significantly from normality "
                        "(Shapiro-Wilk). p-values and confidence intervals "
                        "should be reviewed by a statistician."
                    )
                else:
                    result.add_verdict(
                        "PASS", "normality",
                        f"The model residuals are roughly normally distributed "
                        f"(Shapiro-Wilk, p = {self.fmt_p(w_p)}).",
                    )
        else:
            ctx.log_decision("Shapiro-Wilk skipped for residuals (unsuitable n "
                             "or constant residuals).")

        # --- covariate linearity (scatter + slope is meaningful vs zero)
        try:
            if abs(cov_t) > 0 and not np.isnan(cov_p):
                if cov_p < alpha:
                    result.add_verdict(
                        "PASS", "linearity",
                        f"The covariate is linearly related to the outcome "
                        f"(coefficient = {cov_coef:.3f}, p = {self.fmt_p(cov_p)} "
                        f"< alpha = {alpha:.3f}).",
                    )
                else:
                    result.add_verdict(
                        "WARN", "linearity",
                        f"The covariate does not show a significant linear "
                        f"relationship with the outcome (p = {self.fmt_p(cov_p)} "
                        f">= alpha = {alpha:.3f}). The covariate adds little "
                        "adjustment; consider whether it was a sensible choice.",
                    )
        except Exception:  # noqa: BLE001
            ctx.log_decision("Linearity verdict skipped (no usable covariate "
                             "t-statistic).")

        # --- adjusted means (predict at the covariate grand mean)
        cov_mean = float(safe["cov"].mean())
        grid_rows = []
        for g in groups:
            grid_rows.append({"cov": cov_mean, "grp": g})
        grid = pd.DataFrame(grid_rows)
        adj_means = full.predict(grid)
        adjusted = pd.DataFrame(
            {
                "Group": [str(g) for g in groups],
                "n": [group_counts[g] for g in groups],
                "Raw mean": [round(float(safe.loc[safe["grp"] == g, "out"].mean()), 4)
                             for g in groups],
                "Adjusted mean": [round(float(a), 4) for a in adj_means],
                "Covariate mean": [
                    round(float(safe.loc[safe["grp"] == g, "cov"].mean()), 4)
                    for g in groups
                ],
            }
        )
        result.tables["Adjusted means"] = adjusted
        ctx.log_decision(
            f"Adjusted group means computed at covariate mean = {cov_mean:.4f}: "
            + ", ".join(f"{g} = {m:.4f}" for g, m in zip(groups, adj_means, strict=False))
            + "."
        )

        ancova_table = pd.DataFrame(
            {
                "Source": ["Group (covariate-adjusted)", "Covariate", "Residual"],
                "SS": [ss_group, ss_cov, sse_full],
                "df": [dfn_g, dfn_c, dfd],
                "MS": [ms_group, ms_cov, ms_error],
                "F": [F_group, F_cov, ""],
                "p": [p_group, p_cov, ""],
            }
        )
        result.tables["ANCOVA table"] = ancova_table

        effect_size = pd.DataFrame(
            {
                "Measure": [
                    "partial eta-squared (group)",
                    "effect size label",
                    "covariate coefficient (slope)",
                ],
                "Value": [
                    round(partial_eta2, 6),
                    _eta_label(partial_eta2),
                    round(cov_coef, 6),
                ],
            }
        )
        result.tables["Effect size"] = effect_size

        # --- figure: outcome vs covariate by group, parallel ANCOVA lines
        fig, caption = _scatter_with_lines(
            safe, groups, full, outcome_col, cov_col, group_col,
            F_group, p_group, alpha,
        )
        result.figures.append(
            FigureItem(name="ancova_scatter", figure=fig, caption=caption)
        )

        # --- plain-English summaries
        significant = bool(p_group < alpha)
        result.summaries = {
            "group effect": f"F({dfn_g}, {dfd}) = {F_group:.2f}",
            "p-value": self.fmt_p(p_group),
            "covariate coefficient": f"{cov_coef:.3f}",
            "covariate p": self.fmt_p(cov_p),
            "adjusted group means": " vs ".join(
                f"{g}: {m:.2f}" for g, m in zip(groups, adj_means, strict=False)
            ),
            "effect size (partial eta-squared)": (
                f"{partial_eta2:.3f} ({_eta_label(partial_eta2)})"
            ),
            "significant at alpha": (
                f"{alpha:.3f} \u2192 {'Yes' if significant else 'No'}"
            ),
            "total n": str(len(work)),
        }

        # --- methods.txt sentences
        methods = [
            f"An analysis of covariance (ANCOVA) compared '{outcome_col}' "
            f"across {len(groups)} independent groups "
            f"({', '.join(map(str, groups))}) while adjusting for the numeric "
            f"covariate '{cov_col}', at alpha = {alpha:.3f}, fit by ordinary "
            "least squares.",
            f"After adjusting for the covariate, the group effect was "
            f"F({dfn_g}, {dfd}) = {F_group:.2f}, p = {_p_str(p_group)}, with a "
            f"partial eta-squared of {partial_eta2:.3f} "
            f"({_eta_label(partial_eta2)}).",
            f"The covariate '{cov_col}' had a coefficient of {cov_coef:.3f} "
            f"(p = {_p_str(cov_p)}).",
        ]
        if dropped:
            methods.append(
                f"{dropped} row(s) with missing values in these columns were "
                "excluded (listwise); no missing values were imputed."
            )
        result.methods = methods

        if not significant:
            result.notes.append(
                "The covariate-adjusted group effect was not significant, so "
                "the group averages cannot be shown to differ beyond chance "
                "after controlling for the covariate at this alpha."
            )

        # --- honest interpretation
        result.what_does_not_tell = (
            "A significant ANCOVA does not prove causation: the covariate "
            "adjusts statistically for a single, pre-specified covariate, and "
            "unmeasured or poorly measured confounders can still explain the "
            "group difference. For the adjustment to be meaningful the "
            "covariate must be measured before (or independently of) the "
            "treatment and must not itself be affected by the group. ANCOVA "
            "does not test whether the covariate is the 'true' cause of any "
            "effect, and it cannot correct for non-parallel slopes, missing "
            "data, or groups that overlap on the covariate range."
        )
        return result


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


def _scatter_with_lines(
    safe: pd.DataFrame,
    groups: list[Any],
    model,
    outcome_col: str,
    cov_col: str,
    group_col: str,
    F_group: float,
    p_group: float,
    alpha: float,
):
    import matplotlib.pyplot as plt

    # Uniquish per-group names (for the figure legend).
    label_of = {g: str(g) for g in groups}

    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    x_min, x_max = float(safe["cov"].min()), float(safe["cov"].max())
    pad = (x_max - x_min) * 0.05 or 0.1
    xs = np.linspace(x_min - pad, x_max + pad, 50)

    cov_coef = float(model.params["cov"])
    intercept = float(model.params["Intercept"])
    for i, g in enumerate(groups):
        colour = _PALETTE[i % len(_PALETTE)]
        sub = safe.loc[safe["grp"] == g]
        ax.scatter(
            sub["cov"], sub["out"],
            color=colour, s=34, alpha=0.85, edgecolor="white", linewidth=0.5,
            label=label_of[g],
        )
        # Parallel ANCOVA line for this group.
        grp_param = float(model.params.get(f"C(grp)[T.{g}]", 0.0))
        line_y = intercept + grp_param + cov_coef * xs
        ax.plot(xs, line_y, color=colour, lw=1.6, alpha=0.9)

    p_s = "- < 0.001" if p_group < 0.001 else f"= {p_group:.3f}"
    ax.set_title(
        f"{outcome_col} vs {cov_col} by {group_col}\n"
        f"adjusted group effect F = {F_group:.2f}, p{p_s} "
        f"(alpha = {alpha:.3f})",
        fontsize=10,
    )
    ax.set_xlabel(cov_col)
    ax.set_ylabel(outcome_col)
    ax.grid(ls=":", alpha=0.5)
    ax.legend(title=group_col, fontsize=8)
    fig.tight_layout()
    caption = (
        f"Scatter of '{outcome_col}' against '{cov_col}' coloured by "
        f"'{group_col}', with the parallel ANCOVA fitted lines "
        f"(adjusted group effect F = {F_group:.2f}, p{p_s})."
    )
    return fig, caption


# Module-level instance the registry looks for.
ANALYSIS = AncovaAnalysis()
