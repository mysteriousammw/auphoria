"""ML regression model evaluation for AUPHORIA.

Evaluates a cross-validated linear-regression baseline on a continuous
target with honest train/test separation. The target column is chosen by the
user; every OTHER numeric column is treated automatically as a feature (text
and categorical columns are ignored). The data is split into a training set
(used to fit the model) and a held-out test set (never seen during fitting),
and the model is scored on that test set with RMSE, MAE and R2. The same
baseline is then re-run in K-fold cross-validation on the whole set, so you
also get a cross-validated RMSE with its mean and spread.

Guardrails are enforced here, not in the front end:
- the target is confirmed to exist and be numeric;
- at least one numeric feature (a numeric column other than the target) is
  required, and at least 20 complete rows;
- missing values are counted and excluded with a warning, never imputed;
- a very small overall sample or a very small test set is flagged for
  statistician review (advanced-analysis requirement), and the sample size is
  reported as a verdict.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    from sklearn.metrics import mean_squared_error

    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


class MLRegressionEvalAnalysis(Analysis):
    id = "ml-regression-eval"
    name = "ML Regression Model Evaluation"

    def check_fit(
        self,
        profile: Any,
        params: dict[str, Any],
        inputs: dict[str, str],
    ) -> list[str]:
        del params
        refusals: list[str] = []
        target = inputs.get("target")
        if target is not None:
            col = profile.by_name(target) if hasattr(profile, "by_name") else None
            if col is not None and col.kind != "numeric":
                refusals.append(
                    f"'{target}' looks like a {col.kind} column, not a numeric "
                    "target. ML regression evaluation needs a continuous "
                    "outcome to predict."
                )
        return refusals

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        from sklearn.linear_model import LinearRegression
        from sklearn.model_selection import cross_val_score, train_test_split

        result = AnalysisResult()
        target_col = inputs["target"]

        if target_col not in data.columns:
            raise AssumptionError(
                f"The data has no column named '{target_col}'.",
                hint="Pick a target column from your file.",
            )

        # The target must be numeric (refuses text that cannot become a number).
        target = self.ensure_numeric(data[target_col], target_col)

        if len(data) < 20:
            raise AssumptionError(
                f"This analysis needs at least 20 complete rows, but the data "
                f"has only {len(data)}.",
                hint="Add more rows or evaluate a larger sample.",
            )

        # Features = every OTHER numeric column (text/categorical are ignored).
        numeric_cols = [
            c
            for c in data.columns
            if c != target_col and pd.api.types.is_numeric_dtype(data[c])
        ]
        if not numeric_cols:
            raise AssumptionError(
                "There are no numeric feature columns to predict from: every "
                "column besides the target is text or categorical, or the data "
                "is empty.",
                hint="Add numeric feature columns, or pick a continuous target "
                     "and at least one numeric predictor.",
            )
        ctx.log_decision(
            f"Using '{target_col}' as the target and {len(numeric_cols)} "
            f"numeric feature(s): {', '.join(numeric_cols)}."
        )

        # Missing-value handling: count and report, drop used rows listwise.
        used = pd.DataFrame({target_col: target})
        for c in numeric_cols:
            used[c] = data[c]
        missing_counts = {c: int(used[c].isna().sum()) for c in used.columns}
        dropped = int(used.isna().any(axis=1).sum())
        if dropped:
            result.add_warning(
                f"{dropped} row(s) had a missing value in the target or in a "
                "feature column and were left out of this analysis. They were "
                "counted, not changed or replaced — nothing was imputed."
            )
            for c, n in missing_counts.items():
                if n:
                    ctx.log_decision(
                        f"Column '{c}' has {n} missing value(s); those rows are "
                        "excluded for this analysis, never imputed."
                    )
            used = used.dropna()
            ctx.log_decision(
                f"Excluded {dropped} row(s) missing in used columns (listwise); "
                f"{len(used)} complete row(s) remain."
            )
        else:
            ctx.log_decision(
                "No missing values in the target or feature columns; all rows "
                "are used in full."
            )
        if used.empty:
            raise AssumptionError(
                "After removing rows with missing values there were no "
                "complete rows left to analyse.",
                hint="Check that the target and feature columns have values.",
            )

        n_total = len(used)
        # Verdict on sample size (advanced-analysis requirement).
        if n_total >= 30:
            result.add_verdict(
                "PASS", "sample-size",
                f"The analysis used {n_total} complete rows, which is a "
                "reasonable sample for an exploratory linear baseline.",
            )
        else:
            result.add_verdict(
                "WARN", "sample-size",
                f"The analysis used only {n_total} complete rows. A linear "
                "baseline fit on fewer than 30 rows is unstable and the test "
                "metrics should be treated as very preliminary.",
            )
            result.add_expert_review(
                f"Only {n_total} complete rows were available. Results on fewer "
                "than about 30 rows are unstable; please have a statistician "
                "review the model before drawing conclusions."
            )

        X = used[numeric_cols].to_numpy(dtype=float)
        y = used[target_col].to_numpy(dtype=float)

        test_size = float(params["test_size"])
        cv_folds = int(params["cv_folds"])
        random_state = int(params["random_state"])

        # --- honest train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )
        n_test = len(y_test)
        ctx.log_decision(
            f"Split {n_total} rows into {len(y_train)} training / {n_test} test "
            f"(test_size = {test_size:.2f}, random_state = {random_state}). "
            "Test rows were never used to fit the model."
        )
        if n_test < 10:
            result.add_warning(
                f"The held-out test set has only {n_test} row(s); the "
                "test-set metrics are based on very little data and are noisy."
            )
            ctx.log_decision(
                f"Test set is small ({n_test} row(s)); added a small-test-set "
                "warning."
            )
            result.add_expert_review(
                f"The held-out test set has only {n_test} row(s). Test metrics "
                "on such a small test set are noisy; please have a statistician "
                "review them."
            )

        model = LinearRegression()
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

        rmse_test = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        mae_test = float(mean_absolute_error(y_test, y_pred))
        r2_test = float(r2_score(y_test, y_pred))

        # --- 5-fold (or cv_folds) cross-validation of the same baseline
        cv_scores = cross_val_score(
            LinearRegression(), X, y, cv=cv_folds,
            scoring="neg_mean_squared_error",
        )
        cv_rmse = np.sqrt(-cv_scores)
        cv_mean = float(np.mean(cv_rmse))
        cv_sd = float(np.std(cv_rmse, ddof=1)) if cv_folds > 1 else float("nan")
        ctx.log_decision(
            f"Model fitted on {len(y_train)} training rows and scored on "
            f"{n_test} test rows: RMSE = {rmse_test:.4f}, MAE = {mae_test:.4f}, "
            f"R2 = {r2_test:.4f}. {cv_folds}-fold CV RMSE: "
            f"mean = {cv_mean:.4f} +/- {cv_sd:.4f} "
            f"(folds: {' + '.join(f'{v:.4f}' for v in cv_rmse)})."
        )

        # --- tables
        test_metrics = pd.DataFrame(
            {
                "Metric": ["RMSE", "MAE", "R2"],
                "Value": [round(rmse_test, 4), round(mae_test, 4), round(r2_test, 4)],
                "Meaning": [
                    "Root mean squared error on the held-out test set",
                    "Mean absolute error on the held-out test set",
                    "Fraction of test-set variance captured by the model",
                ],
            }
        )
        cv_table = pd.DataFrame(
            {
                "Fold": [f"Fold {i + 1}" for i in range(cv_folds)],
                "RMSE": [round(float(v), 4) for v in cv_rmse],
            }
        )
        cv_summary = pd.DataFrame(
            {
                "Measure": ["Mean CV RMSE", "SD of CV RMSE"],
                "Value": [round(cv_mean, 4), round(cv_sd, 4)],
            }
        )
        result.tables["Test-set metrics"] = test_metrics
        result.tables["Cross-validation RMSE"] = cv_table
        result.tables["Cross-validation summary"] = cv_summary

        # --- figures
        pred_fig, pred_caption = _pred_vs_actual(y_test, y_pred, target_col, r2_test)
        result.figures.append(
            FigureItem(name="predicted_vs_actual", figure=pred_fig, caption=pred_caption)
        )
        cv_fig, cv_caption = _cv_plot(cv_rmse, cv_mean, cv_sd)
        result.figures.append(
            FigureItem(name="cv_rmse", figure=cv_fig, caption=cv_caption)
        )

        # --- summaries (plain-English highlights)
        result.summaries = {
            "rows used": str(n_total),
            "features": str(len(numeric_cols)),
            "test set": str(n_test),
            "RMSE (test)": self.fmt_float(rmse_test, 4),
            "MAE (test)": self.fmt_float(mae_test, 4),
            "R2 (test)": self.fmt_float(r2_test, 4),
            "CV RMSE (mean +/- SD)": (
                f"{cv_mean:.4f} +/- {cv_sd:.4f}"
                if not np.isnan(cv_sd) else f"{cv_mean:.4f} (single fold)"
            ),
        }

        # --- methods.txt sentences
        methods = [
            f"A linear regression baseline was fitted on {len(y_train)} "
            f"training rows to predict the continuous target '{target_col}' "
            f"from {len(numeric_cols)} numeric feature(s) "
            f"({', '.join(numeric_cols)}), and scored on a held-out test set "
            f"of {n_test} rows (test_size = {test_size:.2f}, "
            f"random_state = {random_state}).",
            f"On the held-out test set the model gave RMSE = {rmse_test:.3f}, "
            f"MAE = {mae_test:.3f} and R2 = {r2_test:.3f}.",
            f"The same baseline was re-evaluated with {cv_folds}-fold "
            f"cross-validation, giving a mean cross-validated RMSE of "
            f"{cv_mean:.3f} (SD = {cv_sd:.3f}).",
        ]
        if dropped:
            methods.append(
                f"{dropped} row(s) with missing values in the used columns "
                "were excluded; no missing values were imputed."
            )
        result.methods = methods

        # --- honest interpretation
        result.what_does_not_tell = (
            "R2 is not a general 'goodness of fit' measure without checking "
            "the residuals: a high R2 can hide systematic bias or outliers. A "
            "good test-set R2 does not prove the model generalises to new "
            "data, other populations, or future time periods. These numbers "
            "only hold if no leakage occurred (features must be known before "
            "the target) and because this is a linear baseline, not a tuned "
            "model, more flexible methods could do better — or worse, if the "
            "baseline is already overfitting."
        )
        return result


def _pred_vs_actual(
    y_test: np.ndarray, y_pred: np.ndarray, target_col: str, r2_test: float
):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.0, 5.5))
    ax.scatter(y_test, y_pred, alpha=0.6, s=24, color="#7fb4d8",
               edgecolor="white", linewidth=0.4)
    lo = min(float(np.min(y_test)), float(np.min(y_pred)))
    hi = max(float(np.max(y_test)), float(np.max(y_pred)))
    ax.plot([lo, hi], [lo, hi], ls="--", color="#c44", lw=1.2,
            label="perfect prediction")
    ax.set_xlabel(f"actual {target_col}")
    ax.set_ylabel(f"predicted {target_col}")
    ax.set_title(f"Predicted vs actual (test set)\nR2 = {r2_test:.3f}",
                 fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(ls=":", alpha=0.4)
    fig.tight_layout()
    caption = (
        f"Held-out test set: predicted against actual '{target_col}' "
        f"(R2 = {r2_test:.3f}); points on the dashed line are perfect."
    )
    return fig, caption


def _cv_plot(cv_rmse: np.ndarray, cv_mean: float, cv_sd: float):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.0, 4.0))
    x = np.arange(1, len(cv_rmse) + 1)
    ax.bar(x, cv_rmse, color="#8fc98d", edgecolor="#333", linewidth=0.6)
    ax.axhline(cv_mean, ls="--", color="#c44", lw=1.2,
               label=f"mean = {cv_mean:.3f}")
    if not np.isnan(cv_sd):
        ax.axhspan(cv_mean - cv_sd, cv_mean + cv_sd, color="#c44", alpha=0.12,
                   label=f"+/- {cv_sd:.3f}")
    ax.set_xticks(x)
    ax.set_xlabel("fold")
    ax.set_ylabel("RMSE")
    ax.set_title(f"{len(cv_rmse)}-fold cross-validation RMSE", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(axis="y", ls=":", alpha=0.4)
    fig.tight_layout()
    caption = (
        f"Per-fold cross-validation RMSE (mean = {cv_mean:.3f}, "
        f"SD = {cv_sd:.3f}); spread shows how stable the baseline is."
    )
    return fig, caption


# Module-level instance the registry looks for.
ANALYSIS = MLRegressionEvalAnalysis()
