"""Fixed-effects (within) panel regression analysis for AUPHORIA.

Estimates how a numeric outcome changes WITHIN repeated observations of the
same units over time (a panel / longitudinal dataset):

    y_it = alpha_i + beta * x_it + u_it

The unobserved unit-specific intercept ``alpha_i`` (the *fixed effect*) absorbs
every time-constant difference between units -- stable ability, location,
management quality -- so ``beta`` is identified only from the variation that
happens *inside* each unit over time. This is the within estimator, computed
here directly by group-demeaning (the "within transformation"): subtract each
unit's own mean from the outcome and from every covariate, then fit ordinary
least squares on the demeaned data with no intercept.

The analysis reports:

- a coefficients table (covariate, beta, standard error, t, p and 95%
  confidence interval), so you can read each covariate's within-unit effect;
- a model table (R-squared within, the model F test and its p, sample size,
  number of entities and number of time periods);
- a fitted-versus-actual scatter figure.

Guardrails are enforced here, not in the front end:

- the outcome, an entity (unit) id column and a time column are required, and
  at least one numeric covariate is required (otherwise the analysis refuses);
- the panel needs at least 8 entities and at least 30 complete rows in total;
- a perfectly collinear (rank-deficient) covariate set is refused with a
  plain-English error;
- missing values are counted and excluded listwise with a warning, never
  imputed.

Because this is an advanced analysis it flags a prominent *needs expert review*
notice whenever it is run outside its intended conditions: fewer than 15
entities or fewer than 60 complete rows.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError

# Recommended minimum number of complete rows for a stable panel fit.
_MIN_N = 30
# Recommended minimum number of entities for a usable fixed-effects panel.
_MIN_ENTITIES = 8
# Below these the analysis asks for expert review.
_EXPERT_ENTITIES = 15
_EXPERT_N = 60


def _p_str(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


class PanelRegressionAnalysis(Analysis):
    id = "panel-regression"
    name = "Panel Regression (Fixed Effects)"

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
                    "numeric outcome. Panel regression needs a continuous "
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
        entity_col = inputs["entity"]
        time_col = inputs["time"]

        for col in (outcome_col, entity_col, time_col):
            if col not in data.columns:
                raise AssumptionError(
                    f"The data has no column named '{col}'.",
                    hint=f"Pick a '{col}' column from your file.",
                )

        outcome = self.ensure_numeric(data[outcome_col], outcome_col)
        ctx.log_decision(
            f"'{outcome_col}' treated as numeric; "
            f"{self.count_missing(outcome, outcome_col)} missing value(s)."
        )

        # Covariates = every OTHER numeric column. The outcome, entity and time
        # columns are excluded by name (entity/time may be stored as numbers).
        reserved = {outcome_col, entity_col, time_col}
        covariates = [
            c
            for c in data.columns
            if c not in reserved and pd.api.types.is_numeric_dtype(data[c])
        ]
        if len(covariates) < 1:
            raise AssumptionError(
                "Panel regression needs at least one numeric covariate column, "
                f"but {len(covariates)} numeric column(s) besides the outcome "
                "was/were found.",
                hint="Add a numeric covariate column, or use a different "
                     "analysis for a single outcome with no controls.",
            )
        ctx.log_decision(
            f"Using '{outcome_col}' as the outcome, '{entity_col}' as the "
            f"entity and '{time_col}' as the time column, with {len(covariates)} "
            f"numeric covariate(s): {', '.join(covariates)}."
        )

        # Missing-value handling: count and report, drop used rows listwise.
        used = pd.DataFrame({outcome_col: outcome})
        for c in covariates:
            used[c] = data[c]
        used[entity_col] = data[entity_col].astype(str)
        used[time_col] = data[time_col].astype(str)

        missing_counts = {c: int(used[c].isna().sum()) for c in used.columns}
        dropped = int(used.isna().any(axis=1).sum())
        if dropped:
            result.add_warning(
                f"{dropped} row(s) had a missing value in the outcome, in a "
                "covariate, or in the entity/time columns and were left out of "
                "this analysis. They were counted, not changed or replaced — "
                "nothing was imputed."
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
                "No missing values in the used columns; all rows are used in "
                "full."
            )

        n = len(used)
        n_entities = int(used[entity_col].nunique())
        n_time = int(used[time_col].nunique())
        if n == 0:
            raise AssumptionError(
                "After removing rows with missing values there were no "
                "complete rows left to analyse.",
                hint="Check that the outcome, entity and covariate columns "
                     "have values.",
            )
        if n_entities < _MIN_ENTITIES:
            raise AssumptionError(
                f"There are {n_entities} entities in this panel, but fixed-"
                f"effects regression needs at least {_MIN_ENTITIES} units to "
                "estimate a reliable within effect.",
                hint="Collect data on more units, or use a simpler regression.",
            )
        if n < _MIN_N:
            raise AssumptionError(
                f"There are {n} complete rows, but panel regression needs at "
                f"least {_MIN_N} rows to estimate a stable fixed-effects model.",
                hint="Collect more observations or reduce the number of "
                     "covariates.",
            )
        ctx.log_decision(
            f"Fitting the within model on {n} complete rows across "
            f"{n_entities} entity(ies) and {n_time} time period(s)."
        )

        alpha = float(params["alpha"])

        # --- group-demean (within transformation) by entity
        demeaned = used.groupby(entity_col)[[outcome_col] + covariates].transform(
            lambda s: s - s.mean()
        )
        y_dm = demeaned[outcome_col].to_numpy(dtype=float)
        X_dm = demeaned[covariates].to_numpy(dtype=float)

        if np.linalg.matrix_rank(X_dm) < X_dm.shape[1]:
            raise AssumptionError(
                "The covariate columns are perfectly collinear (one is exactly "
                "a combination of the others), so the fixed-effects regression "
                "could not be estimated.",
                hint="Remove or replace the redundant covariate column(s).",
            )

        # --- within-estimator coefficients by OLS on the demeaned data
        beta, *_ = np.linalg.lstsq(X_dm, y_dm, rcond=None)
        residuals = y_dm - X_dm @ beta
        ssr = float(np.sum(residuals ** 2))
        tss_within = float(np.sum(y_dm ** 2))  # demeaned y sums to zero overall
        r2_within = 1.0 - ssr / tss_within if tss_within > 0 else float("nan")

        # Degrees of freedom account for the entity fixed effects.
        k = len(covariates)
        df_resid = n - n_entities - k
        sigma2 = ssr / df_resid if df_resid > 0 else float("nan")
        var_beta = sigma2 * np.linalg.inv(X_dm.T @ X_dm)
        se_beta = np.sqrt(np.diag(var_beta))
        t_values = beta / se_beta
        p_values = 2.0 * stats.t.sf(np.abs(t_values), df=df_resid)
        t_crit = stats.t.ppf(1.0 - alpha / 2.0, df=df_resid)

        f_value = (r2_within / k) / ((1.0 - r2_within) / df_resid)
        f_pvalue = 1.0 - stats.f.cdf(f_value, k, df_resid)

        ctx.log_decision(
            f"Within model fit: R2 within = {r2_within:.4f}, F = "
            f"{f_value:.4f}, p = {f_pvalue:.4g} (alpha = {alpha:.3f})."
        )

        # --- coefficients table
        coef_rows = []
        for j, name in enumerate(covariates):
            coef_rows.append(
                {
                    "covariate": name,
                    "beta": float(beta[j]),
                    "std err": float(se_beta[j]),
                    "t": float(t_values[j]),
                    "p": float(p_values[j]),
                    "CI95 lower": float(beta[j] - t_crit * se_beta[j]),
                    "CI95 upper": float(beta[j] + t_crit * se_beta[j]),
                }
            )
        result.tables["Coefficients"] = pd.DataFrame(coef_rows)

        # --- model table
        result.tables["Model"] = pd.DataFrame(
            {
                "Statistic": ["R2 within", "F", "p (model)", "n", "entities", "time periods"],
                "Value": [
                    float(r2_within),
                    float(f_value),
                    float(f_pvalue),
                    int(n),
                    int(n_entities),
                    int(n_time),
                ],
            }
        )

        # --- fitted vs actual figure
        fig, caption = _fitted_vs_actual(
            y_dm, residuals, outcome_col, r2_within, n_entities
        )
        result.figures.append(
            FigureItem(name="fitted_vs_actual", figure=fig, caption=caption)
        )

        # --- expert review for a small panel (small units or small row count)
        if n_entities < _EXPERT_ENTITIES or n < _EXPERT_N:
            small = []
            if n_entities < _EXPERT_ENTITIES:
                small.append(f"{n_entities} entities (fewer than {_EXPERT_ENTITIES})")
            if n < _EXPERT_N:
                small.append(f"{n} complete rows (fewer than {_EXPERT_N})")
            result.add_verdict(
                "WARN", "sample-size",
                f"The panel has {n_entities} entities and {n} complete rows, "
                "which is small for a fixed-effects model; the estimates are "
                "less stable and should be treated as preliminary.",
            )
            result.add_expert_review(
                f"This panel is small ({', '.join(small)}). Fixed-effects "
                "estimates on a small panel are unstable; please have a "
                "statistician review them before drawing conclusions."
            )
        else:
            result.add_verdict(
                "PASS", "sample-size",
                f"The panel has {n_entities} entities and {n} complete rows, "
                "a reasonable size for an exploratory fixed-effects model.",
            )

        # --- plain-English summaries
        significant = bool(f_pvalue < alpha)
        result.summaries = {
            "rows used": str(n),
            "entities": str(n_entities),
            "time periods": str(n_time),
            "covariates": str(k),
            "R2 within": f"{float(r2_within):.3f}",
            "model F": f"F({k}, {int(df_resid)}) = {float(f_value):.2f}",
            "model p": self.fmt_p(float(f_pvalue)),
            "significant at alpha": f"{alpha:.3f} \u2192 {'Yes' if significant else 'No'}",
        }

        # --- methods.txt sentences
        methods = [
            f"A fixed-effects (within) panel regression of the numeric outcome "
            f"'{outcome_col}' on {k} covariate(s) ({', '.join(covariates)}) "
            f"was estimated across {n_entities} entities observed over "
            f"{n_time} time periods at alpha = {alpha:.3f}. The within "
            "estimator was computed by demeaning every variable by its "
            "entity mean and fitting ordinary least squares on the demeaned "
            "data.",
            f"The model explained R2(within) = {float(r2_within):.3f} of the "
            f"within-entity outcome variance, with F({k}, {int(df_resid)}) = "
            f"{float(f_value):.2f}, p = {_p_str(float(f_pvalue))}.",
        ]
        if dropped:
            methods.append(
                f"{dropped} row(s) with missing values in the used columns "
                "were excluded; no missing values were imputed."
            )
        result.methods = methods

        if not significant:
            result.notes.append(
                "The overall model was not significant, so the covariates, "
                "taken together, cannot be shown to explain within-unit "
                "changes in the outcome beyond chance at this alpha. "
                "Individual coefficients should not be over-read."
            )

        # --- honest interpretation
        result.what_does_not_tell = (
            "Fixed effects remove time-invariant unobserved differences "
            "between units, but NOT time-varying confounders (variables that "
            "change over time and also affect the outcome) still bias the "
            "results. A significant coefficient does not establish causality, "
            "and each coefficient is a within-entity effect: it describes how "
            "a change in a covariate relates to a change in the outcome for "
            "the same unit over time, not how units compare with each other. "
            "Standard errors are not adjusted for within-unit serial "
            "correlation or clustering, so they may be optimistic."
        )
        return result


def _fitted_vs_actual(
    y_dm: np.ndarray,
    residuals: np.ndarray,
    outcome_col: str,
    r2_within: float,
    n_entities: int,
):
    import matplotlib.pyplot as plt

    y_pred = y_dm - residuals  # modelled component of the demeaned outcome
    fig, ax = plt.subplots(figsize=(6.0, 5.5))
    ax.scatter(y_dm, y_pred, alpha=0.6, s=24, color="#7fb4d8",
               edgecolor="white", linewidth=0.4)
    lo = min(float(np.min(y_dm)), float(np.min(y_pred)))
    hi = max(float(np.max(y_dm)), float(np.max(y_pred)))
    ax.plot([lo, hi], [lo, hi], ls="--", color="#c44", lw=1.2,
            label="perfect prediction")
    ax.set_xlabel(f"actual (within-de-meaned {outcome_col})")
    ax.set_ylabel(f"predicted (within-de-meaned {outcome_col})")
    ax.set_title(f"Fitted vs actual, within estimator (R2 within = {r2_within:.3f})",
                 fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(ls=":", alpha=0.4)
    fig.tight_layout()
    caption = (
        f"Within-de-meaned fitted values against actual values "
        f"(R2 within = {r2_within:.3f}; {n_entities} entities); points on the "
        "dashed line are predicted perfectly."
    )
    return fig, caption


# Module-level instance the registry looks for.
ANALYSIS = PanelRegressionAnalysis()
