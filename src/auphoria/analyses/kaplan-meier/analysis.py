"""Kaplan-Meier survival analysis for AUPHORIA.

Estimates survival curves over time for censored time-to-event data using
statsmodels' ``SurvfuncRight`` (the permissive-deps pick; lifelines and its
autograd dependency are not used). Survival probabilities use the product-
limit (Kaplan-Meier) formula S(t) = prod_{t_j <= t} (1 - d_j / n_j), computed
once per group, so the report can show each group's own curve. Groups are
compared with a log-rank test whose chi-squared statistic is computed by hand
(observed minus expected events accumulated across the joint event times),
so students can see exactly where the difference comes from.

Guardrails are enforced here, not in the front end:
- the time column is confirmed numeric and non-negative;
- the event column must be a 0/1 indicator (anything else is refused);
- the group must have two or more categories with at least one event each;
- a group with no events is refused (its survival curve is undefined);
- missing values are counted and excluded with a warning, never imputed;
- heavy censoring or very few events produce warnings and, when the design
  strays outside the intended conditions, an expert-review banner.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError

#: Warn on this overall censoring rate or higher.
_CENSOR_WARN = 0.70
#: Warn when a group has fewer than this many observed events.
_MIN_EVENTS_WARN = 5
#: Total sample below which the analysis is clearly underpowered.
_MIN_TOTAL_N = 20


def _logrank_stat(
    times: np.ndarray, events: np.ndarray, group_idx: np.ndarray, k: int
) -> tuple[float, float]:
    """Hand-computed k-sample log-rank test.

    At each distinct event time we accumulate, per group (the first k-1 of
    them), the observed minus expected events S_i and the hypergeometric
    covariance matrix V (sizes (k-1)x(k-1)), then chi2 = S^T V^-1 S with
    df = k-1. For k=2 this reduces to the familiar (O-E)^2 / V.

    Returns (chi_squared, p_value).
    """
    from scipy import stats

    all_obs = sorted(
        float(t) for t in np.unique(times[events == 1])
    )
    S = np.zeros(k - 1)
    V = np.zeros((k - 1, k - 1))
    for tj in all_obs:
        atrisk = times >= tj
        n_total = int(atrisk.sum())
        if n_total < 2:
            continue
        d_total = int(((times == tj) & (events == 1)).sum())
        if d_total < 1:
            continue
        for a in range(k - 1):
            mask_a = atrisk & (group_idx == a)
            n_a = int(mask_a.sum())
            d_a = int(((times == tj) & (events == 1) & (group_idx == a)).sum())
            # Contribution to the score (observed - expected).
            S[a] += d_a - n_a * d_total / n_total
            # Variance diagonal (hypergeometric).
            V[a, a] += (
                n_a * (n_total - n_a) * d_total * (n_total - d_total)
                / (n_total * n_total * (n_total - 1))
            )
            for b in range(a + 1, k - 1):
                n_b = int(((atrisk & (group_idx == b))).sum())
                cov = (
                    n_a * n_b * d_total * (n_total - d_total)
                    / (n_total * n_total * (n_total - 1))
                )
                V[a, b] -= cov
                V[b, a] -= cov
    if k - 1 == 1:
        v = V[0, 0]
        if v <= 0:
            return float("nan"), float("nan")
        chi2 = float(S[0] ** 2 / v)
    else:
        try:
            inv = np.linalg.pinv(V)
            chi2 = float(S @ inv @ S)
        except np.linalg.LinAlgError:
            return float("nan"), float("nan")
    if np.isnan(chi2) or chi2 < 0:
        return float("nan"), float("nan")
    return chi2, float(stats.chi2.sf(chi2, k - 1))


def _survival_figure(
    group_records: list[dict[str, Any]],
    result: AnalysisResult,
    alpha: float,
    time_col: str,
):
    """Step survival curves per group with a number-at-risk table below."""
    import matplotlib.pyplot as plt

    palette = ["#2c7fb8", "#d95f0e", "#31a354", "#756bb1", "#e6a817", "#b33797"]
    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(7.2, 5.6), gridspec_kw={"height_ratios": [3.2, 1.0]},
    )
    fig.suptitle(
        f"Kaplan-Meier survival curves for '{time_col}' by group "
        f"(alpha = {alpha:.3f})",
        fontsize=10,
    )
    for i, rec in enumerate(group_records):
        color = palette[i % len(palette)]
        st = rec["surv_times"]
        sp = rec["surv_prob"]
        med = rec["median"]
        med_str = "not reached" if (med is None or np.isinf(med)) else f"{med:.1f}"
        label = f"{rec['name']} — median {med_str}"
        ax_top.step(st, sp, where="post", color=color, linewidth=2, label=label)
        # Marker on the final plotted estimate.
        if len(st):
            ax_top.plot(st[-1], sp[-1], marker="o", ms=5,
                        color=color, ls="none")
    ax_top.set_ylabel("Survival probability")
    ax_top.set_ylim(0.0, 1.05)
    ax_top.grid(axis="y", ls=":", alpha=0.5)
    ax_top.legend(loc="best", fontsize=8)

    # Number-at-risk ribbon per group.
    ax_bot.axis("off")
    times = sorted({float(t) for rec in group_records for t in rec["surv_times"]})
    row_labels = [str(rec["name"]) for rec in group_records]
    ax_bot.table(
        cellText=[
            [str(rec["at_risk"][list(rec["surv_times"]).index(t)])
             if t in rec["surv_times"]
             else "" for t in times]
            for rec in group_records
        ],
        rowLabels=[f"at risk: {lab}" for lab in row_labels],
        colLabels=[str(int(t)) for t in times],
        loc="center",
        cellLoc="center",
    )

    fig.tight_layout()
    caption = (
        f"Kaplan-Meier survival curves by '{time_col}' for each group, with "
        "median survival and a number-at-risk table (figures are the number "
        "still event-free just before each time)."
    )
    return fig, caption


class KaplanMeierAnalysis(Analysis):
    id = "kaplan-meier"
    name = "Kaplan-Meier survival analysis"

    def check_fit(self, profile, params, inputs) -> list[str]:
        del params
        refusals: list[str] = []
        col = profile.by_name(inputs.get("group")) if profile else None
        if col is not None and col.kind not in ("categorical", "text"):
            refusals.append(
                f"'{inputs.get('group')}' looks like a {col.kind} column, not a "
                "grouping. Kaplan-Meier needs a group column with two or more "
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
        time_col = inputs["time"]
        event_col = inputs["event"]
        group_col = inputs["group"]

        for col in (time_col, event_col, group_col):
            if col not in data.columns:
                raise AssumptionError(
                    f"The data has no column named '{col}'.",
                    hint="Pick the time, event and group columns from your file.",
                )

        # Numeric guarantee on time and event (refuses non-numeric text cells).
        time = self.ensure_numeric(data[time_col], time_col)
        event = self.ensure_numeric(data[event_col], event_col)
        ctx.log_decision(
            f"'{time_col}' and '{event_col}' treated as numeric; "
            f"{self.count_missing(time, time_col)} / "
            f"{self.count_missing(event, event_col)} missing value(s)."
        )

        # Time must be non-negative.
        if (time.dropna() < 0).any():
            raise AssumptionError(
                f"The time column '{time_col}' contains negative values, which "
                "cannot be event times.",
                hint="Times must be 0 or larger (time since study entry).",
            )
        ctx.log_decision(f"'{time_col}' confirmed non-negative.")

        # The event column must be a 0/1 indicator.
        ev_vals = event.dropna().unique()
        if not set(ev_vals.tolist()).issubset({0.0, 1.0}):
            bad = sorted({str(v) for v in ev_vals if v not in (0.0, 1.0)})
            raise AssumptionError(
                f"The event column '{event_col}' may only contain 0 (censored) "
                f"and 1 (event), but has: {', '.join(bad[:8])}.",
                hint="Recode the column so 0 = censored, 1 = event occurred.",
            )
        ctx.log_decision(
            f"'{event_col}' confirmed a 0/1 event indicator "
            f"({int(event.eq(1).sum())} events)."
        )

        group_raw = data[group_col]
        self.describe_missing(group_raw, group_col, ctx)

        # Listwise exclusion of rows missing ANY needed column, with a warning.
        frame = pd.DataFrame(
            {time_col: time, event_col: event, group_col: group_raw}
        )
        dropped = int(frame.isna().any(axis=1).sum())
        frame = frame.dropna()
        if dropped:
            result.add_warning(
                f"{dropped} row(s) had a missing value in '{time_col}', "
                f"'{event_col}' or '{group_col}' and were left out. They were "
                "counted, not changed or replaced."
            )
            ctx.log_decision(
                f"Excluded {dropped} row(s) with a missing value (listwise); "
                f"{len(frame)} row(s) remain. Nothing was imputed."
            )
        if frame.empty:
            raise AssumptionError(
                "After removing rows with missing values there were no complete "
                "rows left to analyse.",
                hint="Check that your time, event and group columns have values.",
            )

        groups = sorted(frame[group_col].unique().tolist())
        if len(groups) < 2:
            raise AssumptionError(
                f"The group column '{group_col}' has only {len(groups)} distinct "
                "value(s), so a between-group survival comparison is impossible.",
                hint="You need a group column with two or more categories to "
                     "compare survival curves.",
            )

        alpha = float(params["alpha"])
        ctx.log_decision(
            f"Running Kaplan-Meier survival analysis (alpha = {alpha:.3f}) on "
            f"'{time_col}' with event indicator '{event_col}' across "
            f"{len(groups)} groups: {', '.join(map(str, groups))}."
        )

        from statsmodels.duration.survfunc import SurvfuncRight

        # group_idx aligned to all rows, plus per-group records.
        data_t = frame[time_col].to_numpy(dtype=float)
        data_e = frame[event_col].to_numpy(dtype=float)
        data_g = frame[group_col].to_numpy()
        gpos = {g: i for i, g in enumerate(groups)}
        group_idx = np.array([gpos[g] for g in data_g], dtype=int)

        group_records: list[dict[str, Any]] = []
        total_events = 0
        total_obs = len(data_t)
        overall_cens = 0
        for g in groups:
            m = data_g == g
            t_g = data_t[m]
            e_g = data_e[m]
            sf = SurvfuncRight(t_g, e_g)
            if not np.any(e_g == 1):
                raise AssumptionError(
                    f"Group '{g}' has no observed events at all (every subject "
                    "is censored), so no survival curve can be estimated for it.",
                    hint="Survival analysis needs at least one event per group.",
                )
            med = sf.quantile(0.5)
            if np.isnan(med) or np.isinf(med):
                med = None
            group_records.append(
                {
                    "name": g,
                    "n": int(m.sum()),
                    "events": int((e_g == 1).sum()),
                    "censored": int((e_g == 0).sum()),
                    "surv_times": list(sf.surv_times),
                    "surv_prob": [float(p) for p in sf.surv_prob],
                    "at_risk": list(sf.n_risk),
                    "n_events": list(sf.n_events),
                    "median": float(med) if med is not None else None,
                }
            )
            total_events += int((e_g == 1).sum())
            overall_cens += int((e_g == 0).sum())
        cens_fraction = overall_cens / total_obs if total_obs else 0.0
        ctx.log_decision(
            f"Total n = {total_obs} with {total_events} events and "
            f"{overall_cens} censored ({cens_fraction:.1%} censored overall)."
        )

        # --- verdicts: events per group and censoring
        min_events = min(r["events"] for r in group_records)
        if min_events < _MIN_EVENTS_WARN:
            result.add_verdict(
                "WARN", "events-per-group",
                f"The group with fewest events has only {min_events} observed "
                f"event(s) (fewer than {_MIN_EVENTS_WARN}). Survival curves and "
                "the log-rank test are very imprecise with so few events.",
            )
        else:
            result.add_verdict(
                "PASS", "events-per-group",
                f"Every group has at least {_MIN_EVENTS_WARN} observed events "
                f"(fewest group: {min_events}); enough to estimate a curve.",
            )
        if cens_fraction > _CENSOR_WARN:
            result.add_verdict(
                "WARN", "censoring",
                f"{cens_fraction:.1%} of rows are censored (over {_CENSOR_WARN:.0%}): "
                "the right-hand tail of every curve is poorly informed and the "
                "median may be unreliable.",
            )
        else:
            result.add_verdict(
                "PASS", "censoring",
                f"Censoring is {cens_fraction:.1%} overall, within the "
                f"{_CENSOR_WARN:.0%} threshold.",
            )

        # --- advanced-analysis guardrails: outside intended conditions
        if total_obs < _MIN_TOTAL_N:
            result.add_expert_review(
                f"Total sample is only {total_obs} (below {_MIN_TOTAL_N}). "
                "Kaplan-Meier estimates and the log-rank test will be imprecise "
                "and should be reviewed by a statistician."
            )
            ctx.log_decision("Added expert-review banner: total n < 20.")
        if min_events < _MIN_EVENTS_WARN:
            result.add_expert_review(
                f"A group has only {min_events} observed event(s). The survival "
                "curve for that group is dominated by a few events; a "
                "statistician should check the log-rank comparison."
            )
            ctx.log_decision("Added expert-review banner: few events in a group.")
        if cens_fraction > _CENSOR_WARN:
            result.add_expert_review(
                f"Censoring is {cens_fraction:.1%} (> {_CENSOR_WARN:.0%}). The "
                "reported curves rely heavily on the assumption that censoring "
                "is non-informative; a statistician should review the tail."
            )
            ctx.log_decision("Added expert-review banner: heavy censoring.")

        # Also warn (verbally) about heavy censoring / few events.
        if cens_fraction > _CENSOR_WARN:
            result.add_warning(
                f"{cens_fraction:.1%} of rows are censored. Beyond "
                f"{_CENSOR_WARN:.0%} censoring the right tail of the curves and "
                "the median survival are unreliable."
            )
        if min_events < _MIN_EVENTS_WARN:
            result.add_warning(
                f"The group with fewest events has only {min_events}; treat the "
                "comparison as preliminary."
            )

        # --- log-rank test across groups
        chi2, p_lr = _logrank_stat(data_t, data_e, group_idx, len(groups))
        ctx.log_decision(
            f"Log-rank test: chi2 = {chi2:.4f}, df = {len(groups) - 1}, "
            f"p = {p_lr:.4g} (alpha = {alpha:.3f})."
        )
        significant = bool(np.isfinite(p_lr) and p_lr < alpha)

        # --- survival tables per group
        for rec in group_records:
            name = str(rec["name"])
            base_p = rec["surv_prob"]
            at_risk0 = rec["at_risk"]
            # survival probability carried forward to the next event (start):
            eff = list(base_p)
            table = pd.DataFrame(
                {
                    "time": [float(t) for t in rec["surv_times"]],
                    "at-risk n": at_risk0,
                    "events": rec["n_events"],
                    "survival probability": [round(p, 6) for p in eff],
                }
            )
            result.tables[f"Survival table: {name}"] = table

        # --- log-rank test reference table (full precision, machine-readable)
        result.tables["Log-rank test"] = pd.DataFrame(
            {
                "Measure": [
                    "log-rank chi-squared",
                    "degrees of freedom",
                    "log-rank p-value",
                ],
                "Value": [
                    float(chi2) if np.isfinite(chi2) else float("nan"),
                    float(len(groups) - 1),
                    float(p_lr) if np.isfinite(p_lr) else float("nan"),
                ],
            }
        )

        # --- summaries
        med_parts = [
            f"{r['name']}: "
            + ("not reached" if r["median"] is None else f"{r['median']:.2f}")
            for r in group_records
        ]
        result.summaries = {
            "log-rank chi-squared": (
                "NA" if not np.isfinite(chi2) else f"{chi2:.3f}"
            ),
            "degrees of freedom": str(len(groups) - 1),
            "log-rank p-value": "NA" if not np.isfinite(p_lr) else self.fmt_p(p_lr),
            "median survival": ", ".join(med_parts),
            "censoring": f"{cens_fraction:.1%} ({overall_cens}/{total_obs})",
            "significant at alpha": (
                f"{alpha:.3f} → {'Yes' if significant else 'No'}"
            ),
        }

        # --- methods.txt sentences (>=3 for survival)
        methods = [
            f"Kaplan-Meier product-limit estimates of survival were computed for "
            f"'{time_col}' using statsmodels SurvfuncRight for each of "
            f"{len(groups)} groups ({', '.join(map(str, groups))}), at alpha = "
            f"{alpha:.3f}.",
            f"A two-sided log-rank test compared the survival curves: "
            f"chi2 = {chi2:.2f} (df = {len(groups) - 1}), p = "
            f"{self.fmt_p(p_lr)}.",
            "Median survival was "
            + ", ".join(
                f"{r['name']} "
                + ("not reached" if r["median"] is None else f"{r['median']:.1f}")
                for r in group_records
            )
            + "; overall censoring was "
            f"{cens_fraction:.1%}.",
        ]
        if dropped:
            methods.append(
                f"{dropped} row(s) with missing values in the requested columns "
                "were excluded; no missing values were imputed."
            )
        result.methods = methods

        if not significant and np.isfinite(p_lr):
            result.notes.append(
                "The log-rank test was not significant, so the survival curves "
                "cannot be shown to differ beyond chance at this alpha."
            )

        # --- figure
        fig, caption = _survival_figure(group_records, result, alpha, time_col)
        result.figures.append(
            FigureItem(name="kaplan_meier_curves", figure=fig, caption=caption)
        )

        # --- honest interpretation
        result.what_does_not_tell = (
            "The survival curves describe this sample only; they estimate "
            "event-free probability over time, not a cure rate or a true "
            "population risk. They are only valid if censoring is "
            "non-informative — i.e. subjects who drop out are event-free for "
            "reasons unrelated to the outcome (informative censoring biases "
            "everything). The log-rank test compares whole curves, so a "
            "significant result does not quantify how much groups differ or "
            "give a hazard ratio, and it does not prove the group caused the "
            "difference — confounding or an unmeasured risk factor could."
        )
        return result


# Module-level instance the registry looks for.
ANALYSIS = KaplanMeierAnalysis()
