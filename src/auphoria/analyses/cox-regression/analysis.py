"""Cox proportional-hazards regression analysis for AUPHORIA.

Models the *time until an event* (survival / time-to-event) with one or more
numeric covariates, estimating a hazard ratio (HR) for each predictor: how
the instantaneous risk of the event changes per unit change in that predictor,
holding the others fixed. Uses statsmodels' ``PHReg`` (``statsmodels.duration.
hazard_regression.PHReg``), a permissive-licensed implementation — lifelines
(which drags in autograd) is deliberately avoided.

Guardrails are enforced here, not in the front end:
- ``time``, ``event`` and every covariate are confirmed numeric.
- the event indicator must be exactly 0/1 (1 = the event happened);
- the event time must be non-negative;
- we refuse if there are no events (nothing to model);
- we refuse if a covariate is constant (its hazard ratio is undefined);
- missing values are counted and *listwise* excluded *with a warning*, never
  imputed;
- few events (<10) and small samples (<30) are warned about, and both trigger
  a request for expert review (advanced-analysis requirement);
- the proportional-hazards assumption is *checked* (Schoenfeld residuals vs
  event time) and reported as a verdict, never silently ignored.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError

#: How large |r| a pair of covariates must reach before we call it "strong
#: collinearity" and ask for expert review.
_COLLINEARITY_CUTOFF = 0.95
#: Below this many events the point estimates are unstable -> expert review.
_MIN_EVENTS = 10
#: Below this total sample size the fit is fragile -> expert review.
_MIN_TOTAL_N = 30


def _split_covariates(cov_col: str) -> list[str]:
    """Turn the covariate input into a list of column names.

    ``covariate`` may be a single column (``age``) or a comma-separated list
    of predictors (``age, bmi, stage``) so a multivariable model can be fit.
    """
    return [c.strip() for c in cov_col.split(",") if c.strip()]


def _p_rel(p: float) -> str:
    return "<" if p < 0.001 else "="


def _hr_summary(hr: float, lo: float, hi: float, p: float) -> str:
    if lo is None or hi is None:
        return f"HR = {hr:.2f}"
    return f"HR = {hr:.2f} (95% CI {lo:.2f}, {hi:.2f})"


def _forest_plot(rows: list[dict[str, Any]], alpha: float, n_events: int):
    """Horizontal forest plot of the hazard ratios with 95% CIs."""
    import matplotlib.pyplot as plt

    labels = [r["covariate"] for r in rows]
    med = [r["hr"] for r in rows]
    lo = [r["ci_low"] for r in rows]
    hi = [r["ci_high"] for r in rows]
    p_vals = [r["p"] for r in rows]

    fig, ax = plt.subplots(figsize=(7.0, max(3.2, 0.55 * len(rows) + 1.2)))
    ypos = np.arange(len(rows))[::-1]  # top row first
    ax.errorbar(
        med, ypos, xerr=[np.array(med) - np.array(lo), np.array(hi) - np.array(med)],
        fmt="o", color="#1f4e79", ecolor="#1f4e79", elinewidth=1.6,
        capsize=4, ms=6, zorder=3,
    )
    ax.axvline(1.0, color="#9d9d9d", ls="--", lw=1.0, zorder=1)
    ax.set_yticks(ypos)
    ax.set_yticklabels(labels, fontsize=9)
    for yp, pv in zip(ypos, p_vals, strict=False):
        tag = "p < 0.001" if pv < 0.001 else f"p = {pv:.3f}"
        ax.text(1.02, yp + 0.02, tag, va="center", fontsize=8, color="#333")
    ax.set_xlabel("Hazard ratio (95% CI), log scale")
    ax.set_title(
        f"Cox proportional-hazards: hazard ratios\n"
        f"({n_events} events, alpha = {alpha:.3f})",
        fontsize=10,
    )
    ax.grid(axis="y", ls=":", alpha=0.4)
    xlim = ax.get_xlim()
    if xlim[0] <= 0:
        lo_nz = min(v for v in lo if v > 0)
        ax.set_xlim(min(lo_nz * 0.6, 0.5), None)
    fig.tight_layout()
    return fig


class CoxRegressionAnalysis(Analysis):
    id = "cox-regression"
    name = "Cox Proportional-Hazards Regression"

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        result = AnalysisResult()
        time_col = inputs["time"]
        event_col = inputs["event"]
        cov_input = inputs["covariate"]
        cov_cols = _split_covariates(cov_input)

        for col in [time_col, event_col, *cov_cols]:
            if col not in data.columns:
                raise AssumptionError(
                    f"The data has no column named '{col}'.",
                    hint="Pick a time, event and one or more covariate columns "
                         "that actually exist in your file.",
                )

        # Numeric guarantee on time, event and every covariate (refuses text).
        time = self.ensure_numeric(data[time_col], time_col)
        event = self.ensure_numeric(data[event_col], event_col)
        ctx.log_decision(
            f"Time '{time_col}' and event '{event_col}' treated as numeric; "
            f"{self.count_missing(time, time_col)} time / "
            f"{self.count_missing(event, event_col)} event missing value(s)."
        )

        covs: dict[str, pd.Series] = {}
        for c in cov_cols:
            covs[c] = self.ensure_numeric(data[c], c)
            self.describe_missing(covs[c], c, ctx)

        # Listwise exclusion of any row missing time, event or a covariate.
        frame_cols = {time_col: time, event_col: event, **covs}
        work = pd.DataFrame(frame_cols)
        dropped = int(work.isna().any(axis=1).sum())
        work = work.dropna()
        if dropped:
            result.add_warning(
                f"{dropped} row(s) had a missing value in '{time_col}', "
                f"'{event_col}' or a covariate and were left out of this "
                "analysis. They were counted and excluded — never imputed, "
                "never changed."
            )
            ctx.log_decision(
                f"Excluded {dropped} row(s) with missing time/event/covariate "
                f"(listwise); {len(work)} complete row(s) remain."
            )
        if work.empty:
            raise AssumptionError(
                "After removing rows with missing values there were no "
                "complete rows left to analyse.",
                hint="Check that the time, event and covariate columns have "
                     "actual values.",
            )

        # Event indicator must be exactly 0/1.
        ev_vals = sorted(work[event_col].unique().tolist())
        allowed = {0, 1}
        bad = [v for v in ev_vals if float(v) not in allowed]
        if bad:
            raise AssumptionError(
                "The event indicator must be 0 (censored) or 1 (event). "
                f"It contains {len(bad)} other value(s): {bad[:8]}.",
                hint="Recode the event column so 1 = the event happened and "
                     "0 = censored (no event by the end of follow-up).",
            )

        # Non-negative event times.
        if float(work[time_col].min()) < 0:
            raise AssumptionError(
                f"The event time column '{time_col}' contains negative values; "
                "time-to-event cannot be negative.",
                hint="Check the time column for coding errors or negative "
                     "follow-up durations.",
            )

        # We cannot model a dataset with no events.
        n_events = int(work[event_col].sum())
        if n_events == 0:
            raise AssumptionError(
                "There are no events in the data (everyone is censored). A "
                "Cox model needs at least one observed event to estimate "
                "hazard ratios.",
                hint="Check that the event column marks actual events (1).",
            )
        n_total = len(work)

        # Refuse a constant covariate (its hazard ratio is undefined / infinite).
        for c in cov_cols:
            if work[c].nunique(dropna=True) <= 1:
                raise AssumptionError(
                    f"The covariate '{c}' is constant (all values identical), "
                    "so no hazard ratio can be estimated for it.",
                    hint="Drop it from the model or choose a predictor that "
                         "actually varies across subjects.",
                )

        alpha = float(params["alpha"])
        ctx.log_decision(
            f"Running Cox proportional-hazards regression (alpha = {alpha:.3f}) "
            f"on '{time_col}' ~ {' + '.join(cov_cols)}, event '{event_col}', "
            f"{n_total} rows, {n_events} events."
        )

        # --- small-sample / low-event flags (advanced-analysis requirement)
        if n_total < _MIN_TOTAL_N:
            result.add_warning(
                f"The sample is small (n = {n_total} complete rows). Cox "
                "estimates are fragile and the result should be treated as "
                "preliminary."
            )
            result.add_expert_review(
                f"Total complete cases n = {n_total} is below the recommended "
                f"minimum of {_MIN_TOTAL_N}. The hazard ratios should be "
                "reviewed by a statistician before any decision is made."
            )
            ctx.log_decision(
                f"n = {n_total} < {_MIN_TOTAL_N}: added a small-sample warning "
                "and requested expert review."
            )
        if n_events < _MIN_EVENTS:
            result.add_warning(
                f"Only {n_events} event(s) observed. Hazard ratios from fewer "
                f"than {_MIN_EVENTS} events are unstable; treat the results as "
                "very preliminary."
            )
            result.add_expert_review(
                f"Only {n_events} event(s) observed (recommended minimum "
                f"{_MIN_EVENTS}). The Cox model can run but the hazard-ratio "
                "estimates are unreliable and need a statistician's review."
            )
            ctx.log_decision(
                f"{n_events} events < {_MIN_EVENTS}: requested expert review."
            )
        result.add_verdict(
            "PASS" if n_events >= _MIN_EVENTS else "WARN",
            "events-count",
            f"{n_events} event(s) observed "
            f"({'≥' if n_events >= _MIN_EVENTS else '<'} recommended minimum "
            f"{_MIN_EVENTS}).",
        )

        # --- strong collinearity between covariates
        if len(cov_cols) >= 2:
            corr = work[cov_cols].corr()
            strong: list[str] = []
            for i in range(len(cov_cols)):
                for j in range(i + 1, len(cov_cols)):
                    r = float(corr.iloc[i, j])
                    if abs(r) > _COLLINEARITY_CUTOFF:
                        strong.append(f"'{cov_cols[i]}' & '{cov_cols[j]}' (|r| = {abs(r):.2f})")
            if strong:
                msg = "Strong collinearity detected between " + "; ".join(strong) + ". This inflates the standard errors and makes individual hazard ratios unstable."
                result.add_warning(msg)
                result.add_expert_review(
                    "Strong collinearity between covariates " + "; ".join(strong)
                    + " — interpret individual hazard ratios cautiously; "
                      "consider dropping one of the correlated predictors."
                )
                ctx.log_decision("Strong collinearity detected; requested expert review.")
            else:
                ctx.log_decision(
                    f"Collinearity check: no pair of covariates exceeds "
                    f"|r| = {_COLLINEARITY_CUTOFF}; individual hazard ratios OK."
                )

        # --- fit the model (sorted internally by time; censoring handled)
        from statsmodels.duration.hazard_regression import PHReg

        exog = work[cov_cols].to_numpy(dtype=float)
        t_arr = work[time_col].to_numpy(dtype=float)
        e_arr = work[event_col].to_numpy(dtype=float)
        model = PHReg(endog=t_arr, exog=exog, status=e_arr)
        res = model.fit(disp=0)

        zcrit = stats.norm.ppf(1.0 - alpha / 2.0)
        rows: list[dict[str, Any]] = []
        methods_cov = []
        for i, c in enumerate(cov_cols):
            coef = float(res.params[i])
            se = float(res.bse[i])
            p = float(res.pvalues[i])
            hr = float(np.exp(coef))
            lo = float(np.exp(coef - zcrit * se))
            hi = float(np.exp(coef + zcrit * se))
            rows.append(
                {
                    "covariate": c,
                    "coef": coef,
                    "se": se,
                    "hr": hr,
                    "ci_low": lo,
                    "ci_high": hi,
                    "p": p,
                    "significant": bool(p < alpha),
                }
            )
            methods_cov.append(
                f"'{c}': HR = {hr:.2f} (95% CI {lo:.2f}, {hi:.2f}), "
                f"p {_p_rel(p)} {self.fmt_p(p)}"
            )
            ctx.log_decision(
                f"Covariate '{c}': log HR = {coef:.4f} (SE {se:.4f}), "
                f"HR = {hr:.4f}, 95% CI ({lo:.4f}, {hi:.4f}), "
                f"p = {p:.4g}."
            )

        llf = float(res.llf)
        ctx.log_decision(
            f"Cox model fitted: log-likelihood = {llf:.4f}; "
            f"{n_events} events across {len(cov_cols)} covariate(s)."
        )

        # --- proportional-hazards check (Schoenfeld residuals vs event time)
        try:
            sr = np.asarray(res.schoenfeld_residuals, dtype=float)
            event_mask = e_arr == 1
            ph_all_pass = True
            for i, c in enumerate(cov_cols):
                r_i = sr[event_mask, i]
                t_i = t_arr[event_mask]
                keep = ~(np.isnan(r_i) | np.isnan(t_i))
                r_i, t_i = r_i[keep], t_i[keep]
                if len(t_i) < 5 or np.ptp(t_i) == 0:
                    ctx.log_decision(
                        f"Proportional-hazards test skipped for '{c}': too few "
                        f"event times ({len(t_i)})."
                    )
                    continue
                rho = stats.spearmanr(r_i, t_i)
                ph_stat = float(rho.statistic)
                ph_p = float(rho.pvalue)
                ctx.log_decision(
                    f"Proportional-hazards check for '{c}': Schoenfeld residual "
                    f"correlation with event time rho = {ph_stat:.4f}, "
                    f"p = {ph_p:.4g} (alpha = {alpha:.3f})."
                )
                if np.isnan(ph_p):
                    continue
                if ph_p < alpha:
                    ph_all_pass = False
                    result.add_verdict(
                        "WARN", "proportional-hazards",
                        f"The proportional-hazards assumption may be violated "
                        f"for '{c}' (Schoenfeld residuals correlate with event "
                        f"time, p = {self.fmt_p(ph_p)} < alpha = {alpha:.3f}). "
                        "The hazard ratio is an *average* that may not fit "
                        "early vs late time points.",
                    )
                else:
                    result.add_verdict(
                        "PASS", "proportional-hazards",
                        f"No strong violation of proportional hazards for "
                        f"'{c}' (Schoenfeld residual-time correlation, "
                        f"p = {self.fmt_p(ph_p)} vs alpha = {alpha:.3f}).",
                    )
            if ph_all_pass and any(v.check == "proportional-hazards" for v in result.verdicts):
                ctx.log_decision("Proportional-hazards check passed for all covariates.")
        except Exception as exc:  # noqa: BLE001 - residual extraction may vary by statsmodels version
            result.add_verdict(
                "WARN", "proportional-hazards",
                "The proportional-hazards diagnostic could not be computed in "
                "this statsmodels version; please verify the assumption holds "
                "(e.g. with scaled Schoenfeld residuals or a log-log plot).",
            )
            result.add_warning(
                "The proportional-hazards assumption could not be checked "
                "automatically in this environment. Before interpreting the "
                "hazard ratios, confirm that the hazard ratio is roughly "
                "constant over time."
            )
            ctx.log_decision(
                "Proportional-hazards diagnostic unavailable; noted as a "
                f"limitation ({exc})."
            )

        # --- tables and summaries
        hr_table = pd.DataFrame(
            {
                "Covariate": [r["covariate"] for r in rows],
                "Hazard ratio (exp coef)": [round(r["hr"], 4) for r in rows],
                "95% CI lower": [round(r["ci_low"], 4) for r in rows],
                "95% CI upper": [round(r["ci_high"], 4) for r in rows],
                "log HR": [round(r["coef"], 4) for r in rows],
                "log HR SE": [round(r["se"], 4) for r in rows],
                "p": [r["p"] for r in rows],
                "significant at alpha?": [
                    "Yes" if r["significant"] else "No" for r in rows
                ],
            }
        )
        result.tables["Hazard ratios"] = hr_table

        fit_table = pd.DataFrame(
            {
                "Quantity": ["log-likelihood", "total complete rows (n)", "events"],
                "Value": [f"{llf:.4f}", int(n_total), int(n_events)],
            }
        )
        result.tables["Model fit"] = fit_table

        result.summaries = {
            "analysis": f"Cox proportional-hazards ({', '.join(cov_cols)})",
            "events": str(int(n_events)),
            "total rows (n)": str(int(n_total)),
            "log-likelihood": f"{llf:.2f}",
            "notable hazard ratio": _hr_summary(
                rows[0]["hr"], rows[0]["ci_low"], rows[0]["ci_high"], rows[0]["p"]
            ),
        }

        # --- figure: forest plot of hazard ratios
        fig = _forest_plot(rows, alpha, n_events)
        result.figures.append(
            FigureItem(
                name="cox_forest_plot",
                figure=fig,
                caption=(
                    "Forest plot of hazard ratios (95% CI) from the Cox "
                    f"model ({n_events} events). A ratio of 1 (dashed line) "
                    "means no association."
                ),
            )
        )

        # --- methods.txt sentences
        methods = [
            f"A Cox proportional-hazards regression (statsmodels PHReg) modelled "
            f"the time to '{time_col}' using the 0/1 event indicator "
            f"'{event_col}' and the covariate(s) "
            f"{', '.join(cov_cols)}, at alpha = {alpha:.3f}.",
            "Hazard ratios (exponentiated coefficients, with 95% confidence "
            "intervals and p-values) were: " + "; ".join(methods_cov) + ".",
            f"The model fit gave a log-likelihood of {llf:.2f} across "
            f"{n_events} event(s); "
            f"{dropped} row(s) with missing values were excluded (listwise) "
            "and none were imputed.",
        ]
        result.methods = methods

        # --- honest interpretation
        result.what_does_not_tell = (
            "A hazard ratio is a *relative* effect: how the instantaneous risk "
            "of the event scales per unit of the predictor — it does NOT "
            "estimate absolute risk or the probability of the event by a given "
            "time (that needs a survival curve). The result is only meaningful "
            "if the proportional-hazards assumption holds (the hazard ratio is "
            "roughly constant over time) and under non-informative censoring "
            "and linearity of continuous predictors. Cox regression measures "
            "association, not causation — the covariates could correlate with "
            "the event for unmeasured reasons."
        )
        return result


# Module-level instance the registry looks for.
ANALYSIS = CoxRegressionAnalysis()
