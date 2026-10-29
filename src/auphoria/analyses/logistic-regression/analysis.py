"""Binary logistic regression for AUPHORIA.

Fits a multiple binary logistic-regression model with ``statsmodels``:
- one column is the *outcome* (the yes/no thing being predicted);
- every OTHER numeric column is used automatically as a predictor
  (at least one is required);
- the fit yields a coefficient table with odds ratios (OR), standard
  errors, z, p and the 95% CI for each odds ratio, plus a model-fit
  table (McFadden pseudo-R2, log-likelihood, LR chi2 + p, class counts);
- a threshold confusion matrix and the in-sample accuracy are shown but
  are clearly labelled as *in-sample* — they refer back to the
  ``ml-classification-eval`` analysis for an honest held-out evaluation;
- a ROC curve (via scikit-learn) summarises how well the scores separate
  the two classes.

Guardrails are enforced here, not in the front end:
- the outcome must be exactly two classes (a single class, or three or
  more, is refused);
- it accepts a numeric binary 0/1 outcome column gracefully (treated as
  class membership, not as a continuous predictor);
- at least one numeric predictor is required;
- missing values are counted and the affected rows are DROPPED with a
  warning; values are never imputed;
- a singular design matrix or perfect separation cannot be fitted and is
  refused with a plain ``AssumptionError``;
- a small event count (<10 per class) or strong class imbalance flags the
  result for expert review.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import roc_auc_score, roc_curve

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError

#: Majority/minority class-count ratio at or above which the outcome is
#: called imbalanced and the result is flagged for expert review.
_IMBALANCE_RATIO = 5.0

#: Smallest event count (rows in either class) still considered comfortable;
#: below this an expert review banner is added (10 events-per-variable rule).
_MIN_EVENTS = 10


class LogisticRegressionAnalysis(Analysis):
    id = "logistic-regression"
    name = "Binary Logistic Regression"

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
            col = profile.by_name(outcome_col)
            # The outcome may be categorical (diagnosis = yes/no) OR a numeric
            # binary 0/1 column; run() validates it is genuinely two-class.
            # Refuse only kinds that cannot be a class outcome.
            if col is not None and col.kind not in ("categorical", "text", "numeric"):
                refusals.append(
                    f"'{outcome_col}' looks like a {col.kind} column, not an "
                    "outcome. Logistic regression needs a two-class outcome "
                    "(e.g. survived = yes/no or 0/1)."
                )
        return refusals

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        del params
        result = AnalysisResult()
        outcome_col = inputs["outcome"]

        if outcome_col not in data.columns:
            raise AssumptionError(
                f"The data has no column named '{outcome_col}'.",
                hint="Pick an outcome column from your file.",
            )

        # All OTHER numeric columns become the predictors automatically
        # (this includes a numeric binary 0/1 predictor; the outcome itself
        # is removed from the predictor set).
        predictors = [
            c
            for c in data.columns
            if c != outcome_col and pd.api.types.is_numeric_dtype(data[c])
        ]
        if len(predictors) < 1:
            raise AssumptionError(
                "Logistic regression needs at least one numeric predictor "
                f"column, but the data has none besides the outcome "
                f"'{outcome_col}'.",
                hint="Add at least one numeric measurement column.",
            )

        # --- outcome must be a readable two-class column
        outcome_values = data[outcome_col].dropna()
        classes = sorted(outcome_values.unique().tolist(), key=str)
        if len(classes) != 2:
            raise AssumptionError(
                f"The outcome column '{outcome_col}' has {len(classes)} "
                f"class{'' if len(classes) == 1 else 'es'} "
                f"({', '.join(map(str, classes))}); binary logistic "
                "regression needs exactly two classes.",
                hint="Use a yes/no (or 0/1) outcome column for this analysis.",
            )

        # --- missing values: counted, rows dropped, NEVER imputed
        all_cols = [outcome_col] + predictors
        for c in all_cols:
            self.describe_missing(data[c], c, ctx)

        work = data[all_cols].copy()
        dropped = int(work.isna().any(axis=1).sum())
        work = work.dropna()
        if dropped:
            result.add_warning(
                f"{dropped} row(s) had a missing value in the outcome or a "
                "predictor column and were dropped. Missing values were "
                "counted and removed by dropping those rows; none were "
                "imputed or replaced."
            )
            ctx.log_decision(
                f"Dropped {dropped} row(s) with missing values (listwise); "
                f"{len(work)} complete row(s) remain."
            )

        if len(work) < 2:
            raise AssumptionError(
                "At least two complete rows are needed to fit a logistic "
                "regression, but none remain after dropping missing values.",
                hint="Add more rows, or pick columns with fewer missing values.",
            )

        # --- build the (0/1) numeric target from the two-class outcome
        # A numeric binary column (0/1, or 1/2) is accepted gracefully; a
        # text two-class column is mapped onto 0/1 for the fit while the
        # original labels are kept for display.
        y_orig = work[outcome_col]
        y_num = pd.to_numeric(y_orig, errors="coerce")
        if y_num.notna().all():
            vals = sorted(y_num.unique().tolist())
            y = y_num.map({vals[0]: 0, vals[1]: 1}).astype(float)
        else:
            y = y_orig.map({classes[0]: 0, classes[1]: 1}).astype(float)

        X_raw = work[predictors].copy()
        X = sm.add_constant(X_raw)
        n_events = int(y.sum())
        n_controls = int((1 - y).sum())

        ctx.log_decision(
            f"Fitting binary logistic regression of '{outcome_col}' "
            f"({classes[0]} = {n_controls} vs {classes[1]} = {n_events}) on "
            f"{len(predictors)} numeric predictor(s) (all numeric columns "
            f"except the outcome) with {len(work)} complete rows."
        )

        # --- fit; singular/perfect-separation errors become a plain refusal
        try:
            fit = sm.Logit(y, X).fit(disp=False)
        except Exception as exc:  # noqa: BLE001 - wraps LinAlgError & PerfectSeparationError
            raise AssumptionError(
                "The logistic-regression model could not be fitted. This "
                "usually means the predictor values are perfectly separated "
                "(a linear combination of them predicts the outcome with no "
                "overlap) or a predictor is constant/singular.",
                hint=(
                    "Check for a constant predictor column, or a predictor "
                    "that perfectly determines the outcome; Firth/penalised "
                    "regression is needed for genuine perfect separation."
                ),
            ) from exc

        # --- coefficient table (odds ratios from the log-odds)
        ci = fit.conf_int()
        coef_rows = []
        for name in list(X.columns):
            beta = float(fit.params[name])
            se = float(fit.bse[name])
            z = float(fit.tvalues[name])
            p = float(fit.pvalues[name])
            or_ci_low = float(np.exp(ci.loc[name, 0]))
            or_ci_high = float(np.exp(ci.loc[name, 1]))
            label = "Intercept" if name == "const" else str(name)
            coef_rows.append(
                {
                    "predictor": label,
                    "beta": round(beta, 6),
                    "odds_ratio": round(float(np.exp(beta)), 6),
                    "std_err": round(se, 6),
                    "z": round(z, 6),
                    "p": round(p, 6),
                    "odds_ratio_ci_low": round(or_ci_low, 6),
                    "odds_ratio_ci_high": round(or_ci_high, 6),
                }
            )
        result.tables["Coefficients (odds ratios)"] = pd.DataFrame(coef_rows)

        # --- model-fit table
        model_fit = pd.DataFrame(
            {
                "metric": [
                    "McFadden Pseudo R-squared",
                    "Log-likelihood (full model)",
                    "Log-likelihood (intercept-only)",
                    "Likelihood-ratio chi2",
                    "Likelihood-ratio p-value",
                    "N (complete rows used)",
                    f"Outcome class '{classes[1]}' count",
                    f"Outcome class '{classes[0]}' count",
                ],
                "value": [
                    round(float(fit.prsquared), 6),
                    round(float(fit.llf), 6),
                    round(float(fit.llnull), 6),
                    round(float(fit.llr), 6),
                    round(float(fit.llr_pvalue), 6),
                    int(len(work)),
                    n_events,
                    n_controls,
                ],
            }
        )
        result.tables["Model fit"] = model_fit

        # --- in-sample threshold classification (clearly labelled)
        prob = fit.predict(X)
        y_pred_bin = (prob >= 0.5).astype(int)
        y_bin = y.astype(int)
        thresh = {0: classes[0], 1: classes[1]}
        y_true_disp = y_bin.map(thresh)
        y_pred_disp = y_pred_bin.map(thresh)
        labels = [classes[0], classes[1]]
        cm = pd.crosstab(
            y_true_disp, y_pred_disp, rownames=["Actual"], colnames=["Predicted"],
            dropna=False,
        )
        # ensure both axes always carry both classes
        cm = cm.reindex(index=labels, columns=labels, fill_value=0)
        result.tables["Confusion matrix (in-sample)"] = cm
        accuracy = float((y_bin == y_pred_bin).mean())
        result.summaries["in-sample accuracy"] = f"{accuracy:.3f}"
        result.summaries["McFadden pseudo-R2"] = f"{fit.prsquared:.3f}"
        result.summaries["events / non-events"] = f"{n_events} / {n_controls}"
        result.summaries["n predictors"] = f"{len(predictors)}"

        # --- ROC curve (scikit-learn reference implementation)
        auc = float(roc_auc_score(y_bin, prob))
        fpr, tpr, _ = roc_curve(y_bin, prob, pos_label=1)
        roc_fig, roc_caption = _roc_figure(fpr, tpr, auc, outcome_col)
        result.figures.append(
            FigureItem(name="roc_curve", figure=roc_fig, caption=roc_caption)
        )

        # --- expert review flags: small event count or class imbalance
        if n_events < _MIN_EVENTS or n_controls < _MIN_EVENTS:
            result.add_expert_review(
                f"One outcome class has fewer than {_MIN_EVENTS} cases "
                f"({classes[0]} = {n_controls}, {classes[1]} = {n_events}), "
                "so the standard errors and odds ratios are unreliable "
                "(the 10-events-per-variable rule is a rough guide)."
            )
        imbalance_ratio = max(n_events, n_controls) / max(1, min(n_events, n_controls))
        if imbalance_ratio >= _IMBALANCE_RATIO:
            result.add_expert_review(
                f"The outcome is strongly imbalanced ({classes[0]} = "
                f"{n_controls}, {classes[1]} = {n_events}); odds ratios are "
                "still estimable but the model may fit poorly and a "
                "statistician should review the handling of the rare class."
            )
        if n_events < _MIN_EVENTS or n_controls < _MIN_EVENTS:
            result.add_verdict(
                "WARN",
                "events-per-variable",
                f"Few cases in one class ({n_events} vs {n_controls}); "
                "results deserve expert review.",
            )
        else:
            result.add_verdict(
                "PASS",
                "events-per-variable",
                f"Both classes have at least {_MIN_EVENTS} cases "
                f"({n_events} vs {n_controls}).",
            )

        # --- methods.txt sentences (>= 3)
        result.methods = [
            f"A multiple binary logistic-regression model was fitted to "
            f"predict '{outcome_col}' from {len(predictors)} numeric "
            f"predictor(s) on {len(work)} complete rows using "
            "statsmodels.api.Logit (maximum-likelihood estimation).",
            f"Model fit: McFadden pseudo-R2 = {fit.prsquared:.3f}, "
            f"log-likelihood = {fit.llf:.3f}, likelihood-ratio chi2 = "
            f"{fit.llr:.3f} (p = {self.fmt_p(float(fit.llr_pvalue))}).",
            f"At the in-sample 0.5 threshold the model reached accuracy = "
            f"{accuracy:.3f}; the ROC-AUC on the fitted (in-sample) data is "
            f"{auc:.3f}. These describe the training data and are optimistic "
            f"— use ml-classification-eval for an honest held-out evaluation.",
        ]
        if dropped:
            result.methods.append(
                f"{dropped} row(s) with a missing outcome or predictor value "
                "were dropped (listwise); no value was imputed."
            )

        result.what_does_not_tell = (
            "Odds ratios describe association, not causation: an OR greater "
            "than 1 means the outcome is more likely as the predictor rises, "
            "but unmeasured confounders can change the effect. The in-sample "
            "accuracy and ROC-AUC are optimistic because they use the same "
            "rows the model was fitted on — they do not tell you how the "
            "model performs on new data. And this is one fixed set of "
            "predictors, not proof they are the best (or only) predictors: "
            "adding or removing predictors can change every coefficient."
        )
        return result


def _roc_figure(
    fpr: np.ndarray, tpr: np.ndarray, auc: float, outcome_col: str
) -> tuple[Any, str]:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.4, 5.0))
    ax.plot(fpr, tpr, color="#b48cd9", lw=2.2, label=f"ROC (AUC = {auc:.3f})")
    ax.plot([0, 1], [0, 1], ls="--", color="#888", lw=1.0, label="Chance")
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title(f"ROC curve: {outcome_col}", fontsize=11)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.grid(ls=":", alpha=0.5)
    ax.legend(loc="lower right", fontsize=9)
    fig.tight_layout()
    caption = f"ROC curve for the fitted model predicting '{outcome_col}' (in-sample AUC = {auc:.3f})."
    return fig, caption


# Module-level instance the registry looks for.
ANALYSIS = LogisticRegressionAnalysis()
