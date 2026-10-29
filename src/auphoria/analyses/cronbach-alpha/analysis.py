"""Cronbach's alpha (internal-consistency reliability) for AUPHORIA.

Cronbach's alpha quantifies how consistently a set of numeric item columns
(usually questionnaire / survey items) score the same underlying construct.
This analysis:

- uses every numeric column in the data as an item;
- computes the raw alpha with the textbook formula
  ``alpha = (k / (k - 1)) * (1 - sum(item_var) / total_var)``
  where ``item_var`` is each item's variance and ``total_var`` is the
  variance of the row sums across all items;
- also reports the standardised alpha (computed after standardising every
  item to unit variance), which is useful when items have very different
  variances;
- reports a per-item table with n, mean, SD, the corrected item-total
  correlation (correlation with the sum of the OTHER items) and the
  alpha-if-deleted value;
- gives a plain-English interpretation of the overall alpha.

Guardrails are enforced here, not in the front end:
- fewer than two numeric item columns is refused (nothing to combine);
- missing values are counted, reported and excluded row-wise (listwise),
  never imputed;
- a small sample (n < 30) or a large gap between the raw and the
  standardised alpha (difference > 0.1) flags an expert-review banner and a
  WARN verdict;
- AUPHORIA does NOT auto-reverse-code items: the user must reverse the
  scoring of any negatively-worded item before running, otherwise alpha is
  artificially low (this is stated in the methods and the honest
  what-does-not-tell note).

Cronbach's alpha is computed by hand here, so no extra dependency is
introduced (pingouin is GPL and avoided per the dependency policy).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from auphoria.core.analysis import Analysis, AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError

#: Below this many complete observations the alpha estimate is noisy.
_MIN_ROWS = 30
#: The standardised/raw alpha gap (absolute) that flags scale heterogeneity.
_MAX_STD_RAW_DIFF = 0.1


def _interpretation(alpha: float) -> str:
    """Map a Cronbach's alpha onto the conventional descriptive band."""
    if alpha < 0.6:
        return "unacceptable"
    if alpha < 0.7:
        return "questionable"
    if alpha < 0.8:
        return "acceptable"
    if alpha < 0.9:
        return "good"
    return "excellent"


class CronbachAlphaAnalysis(Analysis):
    id = "cronbach-alpha"
    name = "Cronbach's Alpha (Internal Consistency)"

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, Any],
        ctx: RunContext,
    ) -> AnalysisResult:
        del inputs  # Cronbach's alpha uses every numeric column automatically
        result = AnalysisResult()

        acceptable_threshold = float(params.get("acceptable_threshold", 0.7))

        # --- collect all numeric columns -------------------------------------
        numeric_cols = [
            c for c in data.columns if pd.api.types.is_numeric_dtype(data[c])
        ]
        if len(numeric_cols) < 2:
            raise AssumptionError(
                "Cronbach's alpha needs at least two numeric item columns, "
                f"but the data only has {len(numeric_cols)} numeric column(s). "
                "Non-numeric columns are not used.",
                hint="Choose a file with several numeric items that are meant "
                     "to measure one scale (e.g. questionnaire items).",
            )
        ctx.log_decision(
            f"Using all {len(numeric_cols)} numeric columns as items: "
            f"{', '.join(numeric_cols)}."
        )

        # --- missing values: count, then drop rows listwise with a warning ----
        working = data[numeric_cols].copy()
        total_missing = int(working.isna().sum().sum())
        dropped = int(working.isna().any(axis=1).sum())
        if total_missing:
            result.add_warning(
                f"{dropped} row(s) had at least one missing numeric value and "
                "were left out of the reliability computation. Missing values "
                "were counted and excluded, never changed or imputed."
            )
            ctx.log_decision(
                f"Counted {total_missing} missing value(s) across the item "
                f"columns; dropped {dropped} row(s) listwise so "
                f"{len(working) - dropped} complete row(s) remain. No imputation."
            )
        working = working.dropna()
        if working.shape[1] < 2:
            raise AssumptionError(
                "After removing rows with missing values fewer than two item "
                "columns remain; Cronbach's alpha needs at least two.",
                hint="Provide at least two numeric item columns with values.",
            )
        items = list(working.columns)
        k = working.shape[1]
        n = working.shape[0]
        X = working.to_numpy(dtype=float)
        ctx.log_decision(
            f"Computing Cronbach's alpha on {k} item(s) with n = {n} complete "
            f"observations (row-wise/listwise deletion; no imputation)."
        )

        # --- raw alpha: population variance of each item and of the row sums --
        item_var = X.var(axis=0, ddof=0)  # per-column variance (population)
        row_sums = X.sum(axis=1)
        total_var = row_sums.var(ddof=0)  # variance of the row sums
        if total_var <= 0.0:
            raise AssumptionError(
                "Every row sum is identical, so total variance is zero and "
                "Cronbach's alpha is undefined. Check that the items vary.",
                hint="Alphabetically identical row sums suggest the columns "
                     "are all constant or perfectly cancel out.",
            )
        sum_item_var = float(item_var.sum())
        alpha = (k / (k - 1)) * (1.0 - sum_item_var / total_var)

        # --- standardised alpha: standardise each item, then the same formula --
        sd = X.std(axis=0, ddof=0)
        sd[sd < np.finfo(float).eps] = 1.0
        Xz = (X - X.mean(axis=0)) / sd
        z_item_var = Xz.var(axis=0, ddof=0)
        z_row_var = Xz.sum(axis=1).var(ddof=0)
        std_alpha = (k / (k - 1)) * (1.0 - float(z_item_var.sum()) / z_row_var)
        ctx.log_decision(
            f"Raw alpha = {alpha:.4f}; standardised alpha = {std_alpha:.4f}."
        )

        # --- per-item table: corrected item-total corr (sum of OTHER items) ---
        rows: list[dict[str, Any]] = []
        for i, col in enumerate(items):
            # Corrected item-total correlation: item vs sum of the OTHER items.
            other_mask = np.ones(k, dtype=bool)
            other_mask[i] = False
            other_sum = X[:, other_mask].sum(axis=1)
            if other_sum.std(ddof=0) > 1e-12 and X[:, i].std(ddof=0) > 1e-12:
                corr = float(np.corrcoef(X[:, i], other_sum)[0, 1])
            else:
                corr = np.nan
            # alpha if this item is removed.
            rem = sum_item_var - float(item_var[i])
            rem_rows = row_sums - X[:, i]
            rem_total = float(rem_rows.var(ddof=0))
            if rem_total <= 0.0:
                alpha_deleted = np.nan
            else:
                alpha_deleted = ((k - 1) / (k - 2)) * (1.0 - rem / rem_total)
            rows.append(
                {
                    "Item": col,
                    "n": int(np.isfinite(X[:, i]).sum()),
                    "mean": round(float(X[:, i].mean()), 4),
                    "SD": round(float(X[:, i].std(ddof=0)), 4),
                    "item-total corr (rest)": round(corr, 4)
                    if np.isfinite(corr)
                    else None,
                    "alpha if deleted": round(float(alpha_deleted), 4)
                    if np.isfinite(alpha_deleted)
                    else None,
                }
            )
        item_table = pd.DataFrame(rows)
        result.tables["Item statistics"] = item_table

        # --- verdicts ---------------------------------------------------------
        interpretation = _interpretation(alpha)
        verdict = "PASS" if alpha >= acceptable_threshold else "WARN"
        result.add_verdict(
            verdict,
            "cronbach-alpha",
            f"Overall Cronbach's alpha = {alpha:.3f}, which is interpreted as "
            f"'{interpretation}'; reliability is {'acceptable (>= ' + str(acceptable_threshold) + ')' if alpha >= acceptable_threshold else 'below the chosen acceptable threshold of ' + str(acceptable_threshold)}.",
        )
        if n < _MIN_ROWS:
            result.add_warning(
                f"The sample is small (n = {n}, below the recommended minimum "
                f"of {_MIN_ROWS}); the alpha estimate carries substantial "
                "sampling error."
            )
            result.add_expert_review(
                f"Sample size n = {n} is below the recommended minimum of "
                f"{_MIN_ROWS} observations; the reliability estimate is noisy. "
                "This estimate needs a statistician's (or supervisor's) "
                "judgement before use."
            )
        if std_alpha - alpha > _MAX_STD_RAW_DIFF:
            result.add_warning(
                f"The standardised alpha ({std_alpha:.3f}) differs from the "
                f"raw ({alpha:.3f}) by more than {_MAX_STD_RAW_DIFF}. The "
                "items have very different variances; the standardised value "
                "is often more appropriate for unequal item scales."
            )
            result.add_expert_review(
                "The raw and standardised alpha differ by more than "
                f"{_MAX_STD_RAW_DIFF}; the items have heterogeneous variances, "
                "so interpreting a single alpha may mislead. This needs a "
                "statistician's (or supervisor's) judgement."
            )

        # --- summaries --------------------------------------------------------
        result.summaries = {
            "items": str(k),
            "observations (complete rows)": str(n),
            "Cronbach's alpha": f"{alpha:.3f} ({interpretation})",
            "standardised alpha": f"{std_alpha:.3f}",
            "acceptable threshold": str(acceptable_threshold),
        }

        # --- methods sentences (include the named test + no reverse-coding) ---
        missing_note = ""
        if dropped:
            missing_note = (
                f" {dropped} row(s) with missing item values were excluded;"
                " missing values were never imputed."
            )
        methods = [
            "Cronbach's alpha (the named reliability test of internal "
            f"consistency) was computed by hand on {k} numeric item column(s) "
            f"({', '.join(items)}) with n = {n} complete observations, using "
            "the formula alpha = (k/(k-1)) * (1 - sum(item variance) / "
            f"total(row-sum variance)). The overall alpha was {alpha:.3f}, "
            f"interpreted as '{interpretation}'.{missing_note}",
            "A standardised alpha was also computed on standardised items; "
            f"it was {std_alpha:.3f}.",
            "Per-item corrected item-total correlations (each item with the "
            "sum of the remaining items) and alpha-if-deleted values are "
            "reported to show which items are most consistent with the rest.",
            "AUPHORIA does NOT automatically reverse-code any item. If any "
            "item is scored in the opposite direction to the rest, reverse "
            "it before running; otherwise alpha underestimates reliability.",
        ]
        if n < _MIN_ROWS:
            methods.append(
                f"The sample ({n}) was below the recommended minimum of "
                f"{_MIN_ROWS}; the estimate should be treated as preliminary."
            )
        result.methods = methods

        # --- honest interpretation -------------------------------------------
        result.what_does_not_tell = (
            "A high Cronbach's alpha does NOT mean the items are "
            "unidimensional (they could be several correlated facets), and it "
            "does NOT establish validity: alpha only reflects the average "
            "inter-item correlation and the number of items, not whether the "
            "scale measures what it claims to. A long or redundant scale can "
            "look highly consistent without being homogeneous. AUPHORIA does "
            "not reverse-code any item automatically, so a low alpha may just "
            "reflect items worded in the opposite direction rather than poor "
            "reliability."
        )

        return result

    def check_fit(
        self,
        profile: Any,
        params: dict[str, Any],
        inputs: dict[str, Any],
    ) -> list[str]:
        del params, inputs
        refusals: list[str] = []
        try:
            cols = list(profile.all_columns())  # type: ignore[attr-defined]
        except AttributeError:
            try:
                cols = list(profile)  # type: ignore[call-overload]
            except Exception:  # noqa: BLE001
                return refusals
        numeric = sum(1 for c in cols if getattr(c, "kind", None) == "numeric")
        if numeric < 2:
            refusals.append(
                "Cronbach's alpha needs at least two numeric item columns; "
                f"this file appears to have only {numeric}."
            )
        return refusals


# Module-level instance the registry looks for.
ANALYSIS = CronbachAlphaAnalysis()
