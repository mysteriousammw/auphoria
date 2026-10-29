"""Relative risk and odds ratio analysis for AUPHORIA.

Builds a 2x2 table from two binary categorical columns (exposure x
outcome) and reports two measures of association with Woolf-log 95%
confidence intervals:

- Relative risk (RR): how much more/frequently the event occurs in the
  exposed group relative to the unexposed group.
- Odds ratio (OR): the odds of the event in the exposed group divided by
  the odds in the unexposed group.

Significance is cross-checked two ways: Pearson's chi-square with Yates'
continuity correction and Fisher's exact test (the exact alternative for
small cell counts).

Guardrails are enforced here, not in the front end:
- both columns must exist;
- rows missing either value are counted and excluded with a warning, never
  imputed;
- each column must have exactly two distinct non-null categories (this is a
  2x2 analysis);
- when any expected cell count is small, a warning verdict records it;
- when any observed cell is zero, a Haldane 0.5 continuity correction is
  applied (with a warning) so the odds ratio and its interval stay finite.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError


def _two_categories(values: pd.Series) -> list[Any]:
    """Distinct non-null categories, sorted for a stable 2x2 layout."""
    return sorted(
        (v for v in values.dropna().unique()),
        key=lambda v: str(v),
    )


def _wald_log_ci(estimate: float, se: float, alpha: float) -> tuple[float, float]:
    """Woolf-style normal-approx 95% CI on the log scale, back-transformed."""
    z = float(stats.norm.ppf(1 - alpha / 2))
    lo = float(np.exp(np.log(estimate) - z * se))
    hi = float(np.exp(np.log(estimate) + z * se))
    return lo, hi


def _finish_2x2(a: float, b: float, c: float, d: float) -> tuple[float, float, float, float]:
    """Return (rr, rr_lo_hi, or, or_lo_hi) as plain floats, guarding zeros."""
    rr = (a / (a + b)) / (c / (c + d)) if c / (c + d) else float("inf")
    ori = a * d / (b * c)

    # Standard errors on the log scale (Woolf). RR uses 1/a - 1/(a+b) terms.
    se_rr = np.sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d))
    se_or = np.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    return rr, ori, se_rr, se_or


class OddsAndRiskAnalysis(Analysis):
    id = "odds-and-risk"
    name = "Relative Risk & Odds Ratio (2x2)"

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        result = AnalysisResult()
        exposure_col = inputs["exposure"]
        outcome_col = inputs["outcome"]

        for col in (exposure_col, outcome_col):
            if col not in data.columns:
                raise AssumptionError(
                    f"The data has no column named '{col}'.",
                    hint="Pick a column from your file.",
                )

        # Categorical columns are used raw (no numeric coercion).
        exposure_raw = data[exposure_col]
        outcome_raw = data[outcome_col]
        self.describe_missing(exposure_raw, exposure_col, ctx)
        self.describe_missing(outcome_raw, outcome_col, ctx)

        # Combine and drop rows missing EITHER value, with a warning.
        both = pd.DataFrame({exposure_col: exposure_raw, outcome_col: outcome_raw})
        dropped = int(both.isna().any(axis=1).sum())
        both = both.dropna()
        if dropped:
            result.add_warning(
                f"{dropped} row(s) had a missing value in '{exposure_col}' or "
                f"'{outcome_col}' and were left out of this analysis. They were "
                "counted, not changed or replaced."
            )
            ctx.log_decision(
                f"Excluded {dropped} row(s) with missing values (listwise); "
                f"{len(both)} row(s) remain for the 2x2 table."
            )

        if both.empty:
            raise AssumptionError(
                "After removing rows with missing values there were no complete "
                "rows left to analyse.",
                hint="Check that both columns have actual values.",
            )

        # A 2x2 analysis needs exactly two categories in each column.
        exposed_cats = _two_categories(both[exposure_col])
        outcome_cats = _two_categories(both[outcome_col])
        for col, cats in ((exposure_col, exposed_cats), (outcome_col, outcome_cats)):
            if len(cats) != 2:
                raise AssumptionError(
                    f"The column '{col}' has {len(cats)} distinct "
                    f"categor{'y' if len(cats) == 1 else 'ies'} "
                    f"({', '.join(str(v) for v in cats)} or fewer is available), "
                    "but this analysis builds a 2x2 table and needs exactly two.",
                    hint="The 2x2 relative-risk / odds-ratio analysis needs two "
                    "columns that each contain exactly two groups.",
                )
            ctx.log_decision(
                f"Column '{col}' has exactly 2 categories: "
                f"{', '.join(str(v) for v in cats)}."
            )

        exposed_label, unexposed_label = exposed_cats
        event_label, no_event_label = outcome_cats
        alpha = float(params["alpha"])

        # If the student named the event category, use it (it must exist).
        requested_event = str(params.get("event_level") or "").strip()
        if requested_event:
            if requested_event not in outcome_cats:
                raise AssumptionError(
                    f"The event category '{requested_event}' is not one of the "
                    f"two outcome categories ({', '.join(str(v) for v in outcome_cats)}).",
                    hint="Set event_level to one of the outcome column's categories.",
                )
            event_label = requested_event
            no_event_label = outcome_cats[0] if outcome_cats[1] == requested_event else outcome_cats[1]
            ctx.log_decision(
                f"Using '{requested_event}' as the event category (from event_level)."
            )
        else:
            ctx.log_decision(
                f"No event_level given; treating '{event_label}' (first outcome "
                f"category alphabetically) as the event. Set event_level if the "
                f"other category is the real event."
            )
            result.add_warning(
                f"Automatic choice: '{event_label}' was treated as the 'event'. "
                f"If the event is actually '{no_event_label}', re-run with "
                f"event_level={no_event_label}."
            )
            result.add_verdict(
                "WARN",
                "event-level",
                f"The event category was chosen automatically as "
                f"'{event_label}' (the first outcome category alphabetically). "
                f"Confirm this is your real event, or set event_level explicitly.",
            )

        observed = pd.crosstab(both[exposure_col], both[outcome_col]).loc[
            exposed_cats, outcome_cats
        ]
        a = float(observed.loc[exposed_label, event_label])
        b = float(observed.loc[exposed_label, no_event_label])
        c = float(observed.loc[unexposed_label, event_label])
        d = float(observed.loc[unexposed_label, no_event_label])
        n = int(observed.to_numpy().sum())
        ctx.log_decision(
            f"Built the 2x2 table a={a:.0f}, b={b:.0f}, c={c:.0f}, d={d:.0f} "
            f"(n = {n}) with '{exposed_label}' as the exposed group and "
            f"'{event_label}' as the event category."
        )

        # --- zero-cell handling: Haldane 0.5 correction
        hal = False
        a_c, b_c, c_c, d_c = a, b, c, d
        if min(a, b, c, d) == 0:
            hal = True
            a_c, b_c, c_c, d_c = (v + 0.5 for v in (a, b, c, d))
            result.add_verdict(
                "WARN",
                "zero-cells",
                "At least one of the four cells is zero, so a Haldane 0.5 "
                "continuity correction was applied before computing the odds "
                "ratio and its confidence interval.",
            )
            result.add_warning(
                "At least one cell in the 2x2 table is zero. A Haldane 0.5 "
                "correction was added to every cell for the odds ratio and its "
                "interval; the relative risk and tests are reported on the "
                "original counts. Interpret the result cautiously."
            )
            ctx.log_decision(
                "Zero cell detected: applied Haldane 0.5 correction to the odds "
                f"ratio computation (a->{a_c:.2f}, b->{b_c:.2f}, c->{c_c:.2f}, d->{d_c:.2f})."
            )

        # --- point estimates + Woolf-log 95% CIs
        rr, ori, se_rr, se_or = _finish_2x2(a_c, b_c, c_c, d_c)
        rr_lo, rr_hi = _wald_log_ci(rr, se_rr, alpha)
        or_lo, or_hi = _wald_log_ci(ori, se_or, alpha)

        # --- significance: chi-square (Yates 2x2) + Fisher's exact
        chi2, chi2_p, dof, expected = stats.chi2_contingency(
            observed.to_numpy(), correction=True
        )
        fisher_or, fisher_p = stats.fisher_exact(observed.to_numpy())
        significant = bool(
            (chi2_p < alpha) or (fisher_p < alpha)
        )  # either test reaching significance is informative

        # --- expected-count verdict
        min_expected = float(expected.min())
        if min_expected < 5:
            result.add_verdict(
                "WARN",
                "expected-counts",
                f"The smallest expected cell count is {min_expected:.1f}, below "
                "the rule-of-thumb of 5, so the chi-square p-value is only "
                "approximate; the Fisher exact p-value remains valid.",
            )
            ctx.log_decision(
                f"Smallest expected cell count = {min_expected:.2f} (< 5): "
                "chi-square flagged as approximate; Fisher exact used."
            )
        else:
            result.add_verdict(
                "PASS",
                "expected-counts",
                f"Every expected cell count is at least 5 (smallest = "
                f"{min_expected:.1f}), so the chi-square p-value is reliable.",
            )
            ctx.log_decision(
                f"Smallest expected cell count = {min_expected:.2f} (>= 5): "
                "expected-count assumption holds."
            )

        ctx.log_decision(
            f"RR = {rr:.4f} (95% CI {rr_lo:.4f}-{rr_hi:.4f}), "
            f"OR = {ori:.4f} (95% CI {or_lo:.4f}-{or_hi:.4f}); "
            f"chi2 = {chi2:.4f} (p = {chi2_p:.4g}), "
            f"Fisher p = {fisher_p:.4g}."
        )

        # --- tables
        table = observed.copy().astype(int)
        table["Row total"] = table.sum(axis=1)
        result.tables["Contingency table"] = table

        row_pct = observed.div(observed.sum(axis=1), axis=0) * 100.0
        row_pct = row_pct.round(1)
        row_pct["Row total"] = 100.0
        result.tables["Row percentages"] = row_pct

        measures = pd.DataFrame(
            {
                "Measure": [
                    "relative risk (RR)",
                    "RR 95% CI (lower)",
                    "RR 95% CI (upper)",
                    "odds ratio (OR)",
                    "OR 95% CI (lower)",
                    "OR 95% CI (upper)",
                    "chi-square (Yates) statistic",
                    "chi-square p-value",
                    "Fisher exact p-value",
                    "sample size (n)",
                    "significance level (alpha)",
                    "significant at alpha?",
                ],
                "Value": [
                    round(rr, 6),
                    round(rr_lo, 6),
                    round(rr_hi, 6),
                    round(ori, 6),
                    round(or_lo, 6),
                    round(or_hi, 6),
                    round(float(chi2), 6),
                    round(float(chi2_p), 6),
                    round(float(fisher_p), 6),
                    n,
                    f"{alpha:.3f}",
                    "Yes" if significant else "No",
                ],
            }
        )
        result.tables["Effect measures"] = measures

        # --- figure: event proportion by exposure group
        fig = _event_proportion_figure(
            exposed_label,
            unexposed_label,
            a,
            b,
            c,
            d,
            rr,
            ori,
            chi2_p,
            event_label,
        )
        result.figures.append(
            FigureItem(
                name="odds_risk_event_rates",
                figure=fig,
                caption=(
                    f"Proportion of '{event_label}' in the '{exposed_label}' "
                    f"(RR = {rr:.2f}) vs '{unexposed_label}' (OR = {ori:.2f}) "
                    f"groups; p = {self.fmt_p(chi2_p)} (chi-square)"
                ),
            )
        )

        # --- summaries (plain-English highlights)
        result.summaries = {
            "relative risk": f"RR = {rr:.2f} (95% CI {rr_lo:.2f}-{rr_hi:.2f})",
            "odds ratio": f"OR = {ori:.2f} (95% CI {or_lo:.2f}-{or_hi:.2f})",
            "chi-square p-value": self.fmt_p(chi2_p),
            "Fisher exact p-value": self.fmt_p(fisher_p),
            "exposed group event rate": f"{a / (a + b) * 100:.1f}%",
            "unexposed group event rate": f"{c / (c + d) * 100:.1f}%",
            "sample size": str(n),
            "significant at alpha": f"{alpha:.3f} → {'Yes' if significant else 'No'}",
            "zero-cell correction": "Haldane 0.5 applied" if hal else "none needed",
        }

        # --- methods.txt sentences
        methods = [
            f"A 2x2 table cross-tabulated the '{event_label}' outcome (in "
            f"'{outcome_col}') against the '{exposure_col}' exposure column "
            f"(exposed = '{exposed_label}', n = {n} complete rows).",
            f"The relative risk (RR) of '{event_label}' was {rr:.2f} (95% "
            f"confidence interval {rr_lo:.2f} to {rr_hi:.2f}), meaning the "
            f"event was {rr:.2f} times as likely in the '{exposed_label}' group "
            f"as in the '{unexposed_label}' group.",
            f"The odds ratio (OR) was {ori:.2f} (95% confidence interval "
            f"{or_lo:.2f} to {or_hi:.2f}).",
            f"A chi-square test with Yates' continuity correction gave chi2 = "
            f"{chi2:.2f}, p = {self.fmt_p(chi2_p)}, and Fisher's exact test gave "
            f"p = {self.fmt_p(fisher_p)} at alpha = {alpha:.3f}.",
        ]
        if hal:
            methods.append(
                "Because one cell was zero, Haldane's 0.5 correction was applied "
                "to the odds ratio and its interval; treat this estimate as "
                "tentative."
            )
        if dropped:
            methods.append(
                f"{dropped} row(s) with missing values in these columns were "
                "excluded; nothing was imputed."
            )
        else:
            methods.append(
                "No rows were missing values in these columns; nothing was "
                "imputed."
            )
        result.methods = methods

        # --- honest interpretation limits
        result.what_does_not_tell = (
            "RR and OR describe an association between exposure and outcome; they "
            "do NOT prove that the exposure caused the outcome. The odds ratio is "
            "not the same as the relative risk when the outcome is common, so do "
            "not read an OR as 'x times more likely'. For a cross-sectional or "
            "case-control study, only the OR is meaningful — the RR from such "
            "data would be misleading because the outcome prevalence is set by "
            "the sampling design, not the real population."
        )
        return result


def _event_proportion_figure(
    exposed_label,
    unexposed_label,
    a,
    b,
    c,
    d,
    rr,
    ori,
    chi2_p,
    event_label,
):
    """Bar chart of event proportion in exposed vs unexposed groups."""
    import matplotlib.pyplot as plt

    rate_exposed = a / (a + b)
    rate_unexposed = c / (c + d)
    labels = [str(exposed_label), str(unexposed_label)]
    rates = [rate_exposed, rate_unexposed]
    colors = ["#2a6fb0", "#d55e00"]

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    bars = ax.bar(range(2), rates, color=colors, width=0.6)
    ax.bar_label(bars, fmt=lambda v: f"{v * 100:.0f}%", padding=2)
    ax.set_xticks(range(2), labels)
    ax.set_ylabel(f"proportion with {event_label}")
    ax.set_ylim(0, max(max(rates) * 1.2, 0.15))
    ax.set_title(
        f"Event rate by exposure\\nRR = {rr:.2f}, OR = {ori:.2f}, "
        f"p = {('p < 0.001' if chi2_p < 0.001 else f'p = {chi2_p:.3f}')}",
        fontsize=10,
    )
    ax.grid(axis="y", ls=":", alpha=0.5)
    fig.tight_layout()
    return fig


# Module-level instance the registry looks for.
ANALYSIS = OddsAndRiskAnalysis()

