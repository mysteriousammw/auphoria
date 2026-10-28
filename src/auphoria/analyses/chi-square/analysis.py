"""Chi-square test of independence analysis for AUPHORIA.

Tests whether two categorical variables are associated by comparing the
observed counts in a contingency table with the counts expected under
independence (SciPy's `chi2_contingency`). Cramer's V is reported as the
effect size so students can gauge the strength of the association beyond
the p-value.

Guardrails are enforced here, not in the front end:
- both columns must exist;
- rows missing either value are counted and excluded with a warning, never
  imputed;
- each column must have at least two distinct non-null categories;
- when any expected cell count is 5 or fewer the result is flagged as
  approximate and Fisher's exact test is recommended (2x2 tables).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError


def _cramers_v(chi2: float, n: int, table_shape: tuple[int, int]) -> float:
    """Cramer's V: association strength in [0, 1] for an r x c table."""
    rows, cols = table_shape
    denom = n * min(rows - 1, cols - 1)
    if denom <= 0:
        return 0.0
    return float(np.sqrt(chi2 / denom))


def _v_label(v: float) -> str:
    av = abs(v)
    if av < 0.1:
        return "negligible"
    if av < 0.3:
        return "small"
    if av < 0.5:
        return "medium"
    return "large"


def _p_expr(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


class ChiSquareAnalysis(Analysis):
    id = "chi-square"
    name = "Chi-Square Test of Independence"

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        result = AnalysisResult()
        var1_col = inputs["var1"]
        var2_col = inputs["var2"]

        if var1_col not in data.columns:
            raise AssumptionError(
                f"The data has no column named '{var1_col}'.",
                hint="Pick a column from your file.",
            )
        if var2_col not in data.columns:
            raise AssumptionError(
                f"The data has no column named '{var2_col}'.",
                hint="Pick a column from your file.",
            )

        # Categorical columns are used raw (no numeric coercion).
        var1_raw = data[var1_col]
        var2_raw = data[var2_col]
        self.describe_missing(var1_raw, var1_col, ctx)
        self.describe_missing(var2_raw, var2_col, ctx)

        # Combine and drop rows missing EITHER value, with a warning.
        both = pd.DataFrame({var1_col: var1_raw, var2_col: var2_raw})
        dropped = int(both.isna().any(axis=1).sum())
        both = both.dropna()
        if dropped:
            result.add_warning(
                f"{dropped} row(s) had a missing value in '{var1_col}' or "
                f"'{var2_col}' and were left out of this test. They were "
                "counted, not changed or replaced."
            )
            ctx.log_decision(
                f"Excluded {dropped} row(s) with missing values (listwise); "
                f"{len(both)} row(s) remain for the test."
            )

        if both.empty:
            raise AssumptionError(
                "After removing rows with missing values there were no "
                "complete rows left to test.",
                hint="Check that both columns have actual values.",
            )

        for col in (var1_col, var2_col):
            cats = both[col].dropna().unique()
            if len(cats) < 2:
                raise AssumptionError(
                    f"The column '{col}' has only 1 distinct category "
                    f"('{cats[0] if len(cats) else ''}'), so an association "
                    "between two variables is impossible.",
                    hint="Choose columns that each contain at least two "
                    "different categories.",
                )
            ctx.log_decision(
                f"Column '{col}' has {len(cats)} distinct categories."
            )

        alpha = float(params["alpha"])
        observed = pd.crosstab(both[var1_col], both[var2_col])
        n = int(observed.to_numpy().sum())
        rows, cols = observed.shape

        correction = bool(rows == 2 and cols == 2)
        ctx.log_decision(
            f"Built a {rows}x{cols} contingency table from n = {n} "
            f"observations; Yates' continuity correction "
            f"{'applied' if correction else 'not applied'} (2x2 only)."
        )
        chi2, p_val, dof, expected = stats.chi2_contingency(
            observed.to_numpy(), correction=correction
        )

        # Effect size (never NaN for a real table, but guard anyway).
        v = _cramers_v(float(chi2), n, (rows, cols))
        significant = bool(p_val < alpha)

        # --- expected-count guardrail
        min_expected = float(expected.min())
        if min_expected <= 5:
            result.add_verdict(
                "WARN",
                "expected-counts",
                f"The smallest expected cell count is {min_expected:.1f}, at "
                "or below the rule of thumb of at least 5 per cell, so the "
                "chi-square approximation may be unreliable.",
            )
            result.add_warning(
                f"At least one expected cell count is 5 or fewer (smallest = "
                f"{min_expected:.1f}). The chi-square result is approximate. "
                "For a 2x2 table, Fisher's exact test is the recommended "
                "alternative (AUPHORIA does not yet offer it as a separate "
                "analysis)."
            )
            ctx.log_decision(
                f"Smallest expected cell count = {min_expected:.2f} (<= 5): "
                "chi-square flagged as approximate; Fisher's exact test "
                "recommended for 2x2 tables."
            )
        else:
            result.add_verdict(
                "PASS",
                "expected-counts",
                f"Every expected cell count is above 5 (smallest = "
                f"{min_expected:.1f}), so the chi-square approximation is "
                "reasonable here.",
            )
            ctx.log_decision(
                f"Smallest expected cell count = {min_expected:.2f} (> 5): "
                "expected-count assumption holds."
            )

        # --- tables
        table = observed.copy()
        table["Row total"] = table.sum(axis=1)
        result.tables["Contingency table"] = table

        row_pct = observed.div(observed.sum(axis=1), axis=0) * 100.0
        row_pct = row_pct.round(1)
        row_pct["Row total"] = 100.0
        result.tables["Row percentages"] = row_pct

        result_table = pd.DataFrame(
            {
                "Item": [
                    "chi-square statistic",
                    "degrees of freedom",
                    "p-value",
                    "sample size (n)",
                    "Cramer's V (effect size)",
                    "effect size label",
                    "significance level (alpha)",
                    "significant at alpha?",
                ],
                "Value": [
                    round(float(chi2), 6),
                    int(dof),
                    round(float(p_val), 6),
                    n,
                    round(v, 4),
                    _v_label(v),
                    f"{alpha:.3f}",
                    "Yes" if significant else "No",
                ],
            }
        )
        result.tables["Chi-square test"] = result_table

        # --- figure (stacked bars: proportions within each var1 category)
        fig = _stacked_bars(observed, var1_col, var2_col, float(chi2), float(p_val))
        result.figures.append(
            FigureItem(
                name="chi_square_stacked_bars",
                figure=fig,
                caption=(
                    f"Proportion of each '{var2_col}' category within each "
                    f"'{var1_col}' category "
                    f"(chi2 = {chi2:.2f}, p = {self.fmt_p(p_val)})"
                ),
            )
        )

        # --- summaries (plain-English highlights)
        result.summaries = {
            "chi-square statistic": f"chi2 = {chi2:.2f}",
            "degrees of freedom": f"df = {dof:.0f}",
            "p-value": self.fmt_p(p_val),
            "sample size": str(n),
            "effect size (Cramer's V)": f"{v:.2f} ({_v_label(v)})",
            "significant at alpha": (
                f"{alpha:.3f} → {'Yes' if significant else 'No'}"
            ),
            "expected-count check": (
                "PASS (all > 5)"
                if min_expected > 5
                else f"WARN (smallest = {min_expected:.1f})"
            ),
        }

        # --- methods.txt sentences
        methods = [
            f"A chi-square test of independence compared the counts of "
            f"'{var2_col}' across the {rows} categories of '{var1_col}' in a "
            f"{rows}x{cols} table (n = {n}).",
            f"The test gave chi2({dof:.0f}) = {chi2:.2f}, {_p_expr(p_val)} at "
            f"alpha = {alpha:.3f}, with Cramer's V = {v:.2f} "
            f"({_v_label(v)}).",
        ]
        if min_expected <= 5:
            methods.append(
                "Because some expected cell counts were 5 or fewer, the "
                "result is approximate; for a 2x2 table Fisher's exact test "
                "is recommended."
            )
        if dropped:
            methods.append(
                f"{dropped} row(s) with missing values in these columns were "
                "excluded; nothing was imputed."
            )
        result.methods = methods

        # --- notes (reproducibility / interpretation)
        ctx.log_decision(
            f"chi2 = {chi2:.4f}, df = {dof}, p = {p_val:.4g}, "
            f"Cramer's V = {v:.4f}."
        )
        result.what_does_not_tell = (
            "A significant chi-square means the pattern of counts differs "
            "across the groups — it does NOT mean one variable caused the "
            "other: association is not causation. The test also does not say "
            "which category drives the association, and Cramer's V only "
            "measures strength relative to the strongest possible "
            "association, not its size in absolute terms."
        )
        return result


def _stacked_bars(
    observed: pd.DataFrame,
    var1_col: str,
    var2_col: str,
    chi2: float,
    p_val: float,
):
    """Stacked bar figure: proportion of each var2 category per var1 row."""
    import matplotlib.pyplot as plt

    prop = observed.div(observed.sum(axis=1), axis=0)
    cats2 = list(observed.columns)
    colors = plt.cm.tab10(np.linspace(0, 1, max(len(cats2), 1)))

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    x = np.arange(len(observed))
    bottom = np.zeros(len(observed))
    for i, cat in enumerate(cats2):
        vals = prop[cat].to_numpy(dtype=float)
        ax.bar(x, vals, bottom=bottom, width=0.6, label=str(cat),
               color=colors[i])
        bottom = bottom + vals

    p_str = "p < 0.001" if p_val < 0.001 else f"p = {p_val:.3f}"
    # Positional labels form keeps compat across matplotlib 3.7-3.12.
    ax.set_xticks(range(len(observed)), [str(v) for v in observed.index])
    ax.set_title(
        f"{var1_col} x {var2_col}\nchi2 = {chi2:.2f}, {p_str}",
        fontsize=10,
    )
    ax.set_ylabel(f"proportion within {var1_col}")
    ax.set_xlabel(var1_col)
    ax.legend(title=var2_col, fontsize=8)
    ax.grid(axis="y", ls=":", alpha=0.5)
    fig.tight_layout()
    return fig


# Module-level instance the registry looks for.
ANALYSIS = ChiSquareAnalysis()
