"""Multiple linear regression analysis for AUPHORIA.

Tests how two or more numeric predictors jointly relate to a numeric outcome,
fitted with ordinary least squares (statsmodels.api.OLS):

    outcome ~ 1 + predictor1 + predictor2 + ...

Every numeric column besides the outcome is used automatically as a predictor
(text and categorical columns are ignored). The analysis reports:

- a coefficients table (predictor, beta, standard error, t, p and 95%
  confidence interval), so you can see each predictor's partial effect after
  adjusting for all the others;
- a model table (R2, adjusted R2, the overall model F test and its p, sample
  size and residual degrees of freedom), so you can see how much of the outcome
  the predictors jointly explain;
- a VIF (variance inflation factor) table, computed by hand as
  VIF_j = 1 / (1 - R2_j), where R2_j is from regressing predictor j on all the
  other predictors. VIF flags multicollinearity: values above about 10 mean
  that predictor j is largely explained by the others and its coefficient is
  unstable;
- a predicted-vs-actual figure on the fitted (full-sample) values.

Guardrails are enforced here, not in the front end:
- at least two numeric predictors are required (a single predictor or zero
  numeric predictors is refused);
- there must be more complete rows than predictors (n > k); otherwise the fit
  is over-determined and refused;
- a singular design matrix is refused with a plain-English error;
- missing values are counted and excluded listwise with a warning, never
  imputed.

Because this is an advanced analysis it flags a prominent *needs expert review*
notice whenever it is run outside its intended conditions: fewer than about 30
complete rows, or a VIF above 10 for any predictor (severe multicollinearity).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError

# Recommended minimum number of complete rows for a stable multi-predictor fit.
_MIN_N = 30
# Above this VIF a predictor is considered badly collinear and the fit is
# flagged for expert review.
_VIF_THRESHOLD = 10

_PALETTE = ["#7fb4d8", "#e8a87c", "#8fc98d", "#d98c8c", "#b48cd9", "#8cd9c9"]


def _p_str(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


class RegressionMultipleAnalysis(Analysis):
    id = "regression-multiple"
    name = "Multiple Linear Regression"

    def check_fit(
        self,
        profile: Any,
        params: dict[str, Any],
        inputs: dict[str, str],
    ) -> list[str]:
        del params
        refusals: list[str] = []
        outcome_col = inputs.get("outcome")
        if outcome_col is not None:
            col = profile.by_name(outcome_col) if hasattr(profile, "by_name") else None
            if col is not None and col.kind != "numeric":
                refusals.append(
                    f"'{outcome_col}' looks like a {col.kind} column, not a "
                    "numeric outcome. Multiple regression needs a continuous "
                    "outcome to explain."
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

        if outcome_col not in data.columns:
            raise AssumptionError(
                f"The data has no column named '{outcome_col}'.",
                hint="Pick an outcome column from your file.",
            )

        outcome = self.ensure_numeric(data[outcome_col], outcome_col)
        ctx.log_decision(
            f"'{outcome_col}' treated as numeric; "
            f"{self.count_missing(outcome, outcome_col)} missing value(s)."
        )

        # Predictors = every OTHER numeric column (text/categorical ignored).
        predictors = [
            c
            for c in data.columns
            if c != outcome_col and pd.api.types.is_numeric_dtype(data[c])
        ]
        # The outcome column may contain text that coerces to numeric; drop it
        # from the predictors by name in case it reappears as a numeric dtype.
        predictors = [c for c in predictors if c != outcome_col]
        if len(predictors) < 2:
            raise AssumptionError(
                "Multiple linear regression needs at least two numeric "
                f"predictor columns, but only {len(predictors)} numeric "
                "column(s) besides the outcome was/were found.",
                hint="Add at least two numeric predictor columns, or use "
                     "simple linear regression for a single predictor.",
            )
        ctx.log_decision(
            f"Using '{outcome_col}' as the outcome and {len(predictors)} "
            f"numeric predictor(s): {', '.join(predictors)}."
        )

        # Missing-value handling: count and report, drop used rows listwise.
        used = pd.DataFrame({outcome_col: outcome})
        for c in predictors:
            used[c] = data[c]
        missing_counts = {c: int(used[c].isna().sum()) for c in used.columns}
        dropped = int(used.isna().any(axis=1).sum())
        if dropped:
            result.add_warning(
                f"{dropped} row(s) had a missing value in the outcome or in a "
                "predictor column and were left out of this analysis. They "
                "were counted, not changed or replaced — nothing was imputed."
            )
            for c, n in missing_counts.items():
                if n:
                    ctx.log_decision(
                        f"Column '{c}' has {n} missing value(s); those rows "
                        "are excluded for this analysis, never imputed."
                    )
            used = used.dropna()
            ctx.log_decision(
                f"Excluded {dropped} row(s) missing in used columns (listwise); "
                f"{len(used)} complete row(s) remain."
            )
        else:
            ctx.log_decision(
                "No missing values in the outcome or predictor columns; all "
                "rows are used in full."
            )

        n = len(used)
        k = len(predictors)
        if n == 0:
            raise AssumptionError(
                "After removing rows with missing values there were no "
                "complete rows left to analyse.",
                hint="Check that the outcome and predictor columns have values.",
            )
        # Need more rows than predictors AND at least one residual degree of
        # freedom (n - k - 1 >= 1), else the fit is saturated or impossible.
        if n <= k or (n - k - 1) < 1:
            raise AssumptionError(
                f"There are {n} complete row(s) but {k} predictor(s); a "
                "multiple regression needs more rows than predictors (n > k), "
                "with at least one leftover degree of freedom, to estimate all "
                "the coefficients. Please add rows or remove predictors.",
                hint="Collect more data or reduce the number of predictor "
                     "columns.",
            )
        ctx.log_decision(
            f"Fitting OLS with {n} complete rows and {k} predictor(s) "
            f"(degrees of freedom: model = {k}, residual = {n - k - 1})."
        )

        alpha = float(params["alpha"])

        # --- fit the model with a constant term
        X = sm.add_constant(used[predictors].to_numpy(dtype=float))
        y = used[outcome_col].to_numpy(dtype=float)
        # A singular (rank-deficient) design means perfect collinearity:
        # statsmodels only warns and returns garbage — refuse instead.
        if np.linalg.matrix_rank(X) < X.shape[1]:
            raise AssumptionError(
                "The predictor columns are perfectly collinear, so the "
                "regression could not be fit: one predictor is exactly a "
                "combination of the others.",
                hint="Remove or replace the redundant predictor column(s).",
            )
        model = sm.OLS(y, X).fit()

        ctx.log_decision(
            f"Model fit: R2 = {model.rsquared:.4f}, adj R2 = "
            f"{model.rsquared_adj:.4f}, F = {model.fvalue:.4f}, "
            f"p = {model.f_pvalue:.4g} (alpha = {alpha:.3f})."
        )

        # --- coefficients table (drop the intercept)
        ci = model.conf_int()
        coef_rows = []
        for j, name in enumerate(predictors):
            col_index = j + 1  # X[:, 0] is the constant
            coef_rows.append(
                {
                    "predictor": name,
                    "beta": float(model.params[col_index]),
                    "std err": float(model.bse[col_index]),
                    "t": float(model.tvalues[col_index]),
                    "p": float(model.pvalues[col_index]),
                    "CI95 lower": float(ci[col_index, 0]),
                    "CI95 upper": float(ci[col_index, 1]),
                }
            )
        coef_table = pd.DataFrame(coef_rows)
        result.tables["Coefficients"] = coef_table

        # --- model table
        model_table = pd.DataFrame(
            {
                "Statistic": ["R2", "Adjusted R2", "F", "p (model)", "n", "df residual"],
                "Value": [
                    float(model.rsquared),
                    float(model.rsquared_adj),
                    float(model.fvalue),
                    float(model.f_pvalue),
                    int(model.nobs),
                    int(model.df_resid),
                ],
            }
        )
        result.tables["Model"] = model_table
        ctx.log_decision(
            f"Residual degrees of freedom = {int(model.df_resid)} "
            f"(n = {int(model.nobs)}, predictors = {k})."
        )

        # --- VIF table (hand-computed 1/(1 - R2_j)); constant excluded
        vif_rows = []
        for name in predictors:
            others = [c for c in predictors if c != name]
            try:
                Xo = sm.add_constant(used[others].to_numpy(dtype=float))
                r2_j = float(sm.OLS(used[name].to_numpy(dtype=float), Xo).fit().rsquared)
                vif = 1.0 / (1.0 - r2_j) if r2_j < 1.0 else float("inf")
            except np.linalg.LinAlgError:
                r2_j, vif = float("nan"), float("inf")
            vif_rows.append({"predictor": name, "R2_j (vs others)": r2_j, "VIF": vif})
        vif_table = pd.DataFrame(vif_rows)
        result.tables["VIF"] = vif_table

        high_vif = [str(r["predictor"]) for r in vif_rows
                    if isinstance(r["VIF"], float) and np.isfinite(r["VIF"])
                    and r["VIF"] > _VIF_THRESHOLD]
        infinite_vif = [str(r["predictor"]) for r in vif_rows if np.isinf(r["VIF"])]
        for name in high_vif:
            result.add_warning(
                f"Predictor '{name}' has a VIF above {_VIF_THRESHOLD}, which "
                "signals strong multicollinearity: it is largely explained by "
                "the other predictors, so its individual coefficient is "
                "unstable and may flip sign."
            )
            result.add_expert_review(
                f"Predictor '{name}' has severe multicollinearity (VIF above "
                f"{_VIF_THRESHOLD}). Its individual coefficient is unstable; "
                "please have a statistician review whether it can be "
                "interpreted at all."
            )
        for name in infinite_vif:
            result.add_warning(
                f"Predictor '{name}' is perfectly explained by the other "
                "predictors (infinite VIF). The data are collinear and this "
                "coefficient cannot be separated from the others."
            )
            result.add_expert_review(
                f"Perfect multicollinearity involving '{name}' (infinite VIF) "
                "means that predictor cannot be separated from the others; "
                "the coefficient is not identifiable and needs expert review."
            )
        if high_vif or infinite_vif:
            ctx.log_decision(
                "Multicollinearity flagged: predictors with VIF above "
                f"{_VIF_THRESHOLD}: {', '.join(high_vif + infinite_vif) or 'none'}."
            )

        # --- sample size verdict + expert review
        if n >= _MIN_N:
            result.add_verdict(
                "PASS", "sample-size",
                f"The analysis used {n} complete rows for {k} predictor(s), a "
                "reasonable sample for an exploratory multiple regression.",
            )
        else:
            result.add_verdict(
                "WARN", "sample-size",
                f"Only {n} complete rows were available for {k} predictor(s). "
                "Below about 30 rows the coefficients and R2 are unstable and "
                "the result should be treated as very preliminary.",
            )
            result.add_expert_review(
                f"Only {n} complete rows were available (recommended minimum "
                f"about {_MIN_N}). Results on a small sample with {k} "
                "predictor(s) are unstable; please have a statistician review "
                "them before drawing conclusions."
            )
        if high_vif or infinite_vif:
            result.add_verdict(
                "WARN", "multicollinearity",
                "At least one predictor has a VIF above 10, so some "
                "coefficients are unstable. R2 of the whole model is still "
                "meaningful, but individual betas are not.",
            )
        else:
            result.add_verdict(
                "PASS", "multicollinearity",
                "No predictor has a VIF above 10, so multicollinearity is not "
                "severe and the individual coefficients can be read.",
            )

        # --- predicted-vs-actual figure
        fig, caption = _pred_vs_actual(y, np.asarray(model.fittedvalues), outcome_col,
                                       model.rsquared)
        result.figures.append(
            FigureItem(name="predicted_vs_actual", figure=fig, caption=caption)
        )

        # --- plain-English summaries
        significant = bool(model.f_pvalue < alpha)
        result.summaries = {
            "rows used": str(n),
            "predictors": str(k),
            "R2": f"{float(model.rsquared):.3f}",
            "adjusted R2": f"{float(model.rsquared_adj):.3f}",
            "model F": f"F({k}, {int(model.df_resid)}) = {float(model.fvalue):.2f}",
            "model p": self.fmt_p(float(model.f_pvalue)),
            "significant at alpha": f"{alpha:.3f} \u2192 {'Yes' if significant else 'No'}",
        }

        # --- methods.txt sentences
        methods = [
            f"A multiple linear regression of the numeric outcome "
            f"'{outcome_col}' on {k} numeric predictor(s) "
            f"({', '.join(predictors)}) was fitted by ordinary least squares "
            f"at alpha = {alpha:.3f}.",
            f"The model explained R2 = {float(model.rsquared):.3f} "
            f"(adjusted R2 = {float(model.rsquared_adj):.3f}) of the outcome "
            f"variance, with an overall F({k}, {int(model.df_resid)}) = "
            f"{float(model.fvalue):.2f}, p = {_p_str(float(model.f_pvalue))}.",
        ]
        if len(high_vif) or len(infinite_vif):
            methods.append(
                f"Multicollinearity was checked with the variance inflation "
                f"factor; predictors with VIF above {_VIF_THRESHOLD} "
                f"({', '.join(high_vif + infinite_vif) or 'none'}) have "
                "unstable individual coefficients."
            )
        if dropped:
            methods.append(
                f"{dropped} row(s) with missing values in the used columns "
                "were excluded; no missing values were imputed."
            )
        result.methods = methods

        if not significant:
            result.notes.append(
                "The overall model was not significant, so the predictors, "
                "taken together, cannot be shown to explain the outcome beyond "
                "chance at this alpha. Individual coefficients should not be "
                "over-read."
            )

        # --- honest interpretation
        result.what_does_not_tell = (
            "A significant overall model or a significant coefficient does not "
            "prove causation: multiple regression only adjusts for the "
            "predictors that are actually in the data, so unmeasured or poorly "
            "measured confounders can still explain the outcome. It does not "
            "test which predictor is the 'true' cause of an effect. Results "
            "should not be extrapolated beyond the range of the observed "
            "predictors, and where multicollinearity is present the individual "
            "coefficients cannot be cleanly separated even when the model as a "
            "whole fits well."
        )
        return result


def _pred_vs_actual(y: np.ndarray, y_pred: np.ndarray, outcome_col: str, r2: float):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.0, 5.5))
    ax.scatter(y, y_pred, alpha=0.6, s=24, color="#7fb4d8",
               edgecolor="white", linewidth=0.4)
    lo = min(float(np.min(y)), float(np.min(y_pred)))
    hi = max(float(np.max(y)), float(np.max(y_pred)))
    ax.plot([lo, hi], [lo, hi], ls="--", color="#c44", lw=1.2,
            label="perfect prediction")
    ax.set_xlabel(f"actual {outcome_col}")
    ax.set_ylabel(f"predicted {outcome_col}")
    ax.set_title(f"Predicted vs actual (fitted values)\nR2 = {r2:.3f}",
                 fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(ls=":", alpha=0.4)
    fig.tight_layout()
    caption = (
        f"Fitted values against actual '{outcome_col}' (R2 = {r2:.3f}); points "
        "on the dashed line are predicted perfectly."
    )
    return fig, caption


# Module-level instance the registry looks for.
ANALYSIS = RegressionMultipleAnalysis()
