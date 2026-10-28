"""ML classification model evaluation for AUPHORIA.

Trains a plain logistic-regression baseline and evaluates it honestly:
- one categorical column is the *label* (target class), all other numeric
  columns are used automatically as features;
- the data is split into a stratified train/test pair so scores describe
  held-out rows, not the training rows;
- the test set yields accuracy, precision, recall, F1 (classification
  report), and ROC-AUC, plus a ROC curve;
- a figure and a table show per-fold accuracy from stratified cross-
  validation, with the mean and spread.

Guardrails are enforced here, not in the front end:
- the label must be binary (two classes): a single class cannot be learned
  and ROC-AUC needs two classes, so anything except two classes is refused;
- at least two numeric feature columns are needed, and at least 20 complete
  rows, otherwise the analysis refuses;
- missing values in the label or any feature are COUNTED, the affected rows
  are DROPPED with a warning, and values are NEVER imputed (imputation would
  leak information computed from the whole dataset);
- class imbalance and a small test set produce warnings; less than 30 rows,
  a class with fewer than five rows, or a strongly imbalanced label flag the
  result for expert review.

This is a baseline build, not a tuned model, and the honest caveats about
generalisation and leakage are spelled out in ``what_does_not_tell``.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError

#: Majority/minority class-count ratio at or above which the label is called
#: imbalanced (built with accuracy still readable below this, warning above).
_IMBALANCE_RATIO = 4.0


class MlClassificationEvalAnalysis(Analysis):
    id = "ml-classification-eval"
    name = "ML Classification Model Evaluation"

    def check_fit(
        self,
        profile: Any,
        params: dict[str, Any],
        inputs: dict[str, str],
    ) -> list[str]:
        del params
        refusals: list[str] = []
        label_col = inputs.get("label")
        if label_col is not None:
            col = profile.by_name(label_col)
            # The label may be categorical (diagnosis = yes/no) OR a numeric
            # binary 0/1 column; run() validates it is genuinely two-class.
            # Refuse only kinds that cannot be a class label.
            if col is not None and col.kind not in ("categorical", "text", "numeric"):
                refusals.append(
                    f"'{label_col}' looks like a {col.kind} column, not a class "
                    "label. Classification needs a categorical target (e.g. "
                    "diagnosis = yes/no)."
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
        label_col = inputs["label"]

        if label_col not in data.columns:
            raise AssumptionError(
                f"The data has no column named '{label_col}'.",
                hint="Pick a categorical label column from your file.",
            )

        # All OTHER numeric columns become the features automatically.
        numeric_features = [
            c
            for c in data.columns
            if c != label_col and pd.api.types.is_numeric_dtype(data[c])
        ]
        if len(numeric_features) < 2:
            raise AssumptionError(
                "Classification needs at least two numeric feature columns, but "
                f"the data only has {len(numeric_features)} numeric column(s) "
                f"besides the label '{label_col}'.",
                hint="The model learns from every other numeric column; add "
                     "more numeric measurements (or check that your label "
                     "column is not numeric).",
            )

        # --- missing values: counted, rows dropped, NEVER imputed
        for c in [label_col] + numeric_features:
            self.describe_missing(data[c], c, ctx)

        work = data[[label_col] + numeric_features].copy()
        dropped = int(work.isna().any(axis=1).sum())
        work = work.dropna()
        if dropped:
            result.add_warning(
                f"{dropped} row(s) had a missing value in the label or a feature "
                "column and were dropped. Missing values were counted and "
                "removed by dropping those rows; none were imputed or replaced."
            )
            ctx.log_decision(
                f"Dropped {dropped} row(s) with missing values (listwise); "
                f"{len(work)} complete row(s) remain."
            )

        if len(work) < 20:
            raise AssumptionError(
                f"At least 20 complete rows are needed to train and evaluate a "
                f"classification model, but only {len(work)} row(s) remain "
                "after dropping rows with missing values.",
                hint="Add more rows, or pick feature columns with fewer missing "
                     "values.",
            )

        y = work[label_col]
        X = work[numeric_features]

        labels = sorted(np.unique(y).tolist(), key=str)
        if len(labels) != 2:
            raise AssumptionError(
                f"The label column '{label_col}' has {len(labels)} class"
                f"{'' if len(labels) == 1 else 'es'} "
                f"({', '.join(map(str, labels))}); this baseline is binary and "
                "reports ROC-AUC, which needs exactly two classes.",
                hint="Use a two-class label (e.g. yes/no) or a multiclass "
                     "analysis if you have more than two classes.",
            )

        ctx.log_decision(
            f"Binary classification of '{label_col}' with {len(numeric_features)} "
            f"numeric features and {len(work)} rows across classes "
            f"{', '.join(map(str, labels))}."
        )

        test_size = float(params["test_size"])
        cv_folds = int(params["cv_folds"])
        random_state = int(params["random_state"])
        ctx.log_decision(
            f"train_test_split(test_size={test_size}, stratify=True, "
            f"random_state={random_state}); label is binary, so stratification "
            "keeps both classes in the train and test sets."
        )

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )

        clf = LogisticRegression(max_iter=1000)
        clf.fit(X_train, y_train)

        y_pred = clf.predict(X_test)
        # Positive-class probability for ROC-AUC (index 1 = the second class).
        y_proba = clf.predict_proba(X_test)[:, 1]
        accuracy = float(accuracy_score(y_test, y_pred))
        auc = float(roc_auc_score(y_test, y_proba))
        cm = confusion_matrix(y_test, y_pred, labels=labels)

        ctx.log_decision(
            f"Test set: n = {len(X_test)}; accuracy = {accuracy:.4f}, "
            f"ROC-AUC = {auc:.4f}."
        )

        # --- honest guardrails: imbalance, small test set, tiny sample
        counts = pd.Series(y).value_counts()
        majority, minority = int(counts.max()), int(counts.min())
        imbalance_ratio = float(counts.max()) / float(counts.min())
        for lab, n in zip(labels, [int(counts.loc[x]) for x in labels if x in counts], strict=False):
            if n < 5:
                result.add_expert_review(
                    f"Class '{lab}' has only {n} row(s), so the model has very "
                    "little to learn from for that class; any metric should be "
                    "treated as unreliable."
                )
        if len(work) < 30:
            result.add_expert_review(
                f"The dataset is small ({len(work)} rows < 30), so cross-"
                "validation scores and the test metrics have wide uncertainty "
                "and should be read as preliminary only."
            )
        if imbalance_ratio > 10:
            result.add_expert_review(
                f"The label is strongly imbalanced (majority/minority = "
                f"{imbalance_ratio:.1f}); accuracy alone is misleading and a "
                "statistician should review how the classes are handled."
            )

        if imbalance_ratio >= _IMBALANCE_RATIO:
            result.add_verdict(
                "WARN", "class-balance",
                f"The label is imbalanced: {majority} of the most common class "
                f"vs {minority} of the rarest (ratio {imbalance_ratio:.1f}). "
                "Accuracy is hard to interpret; read precision, recall and "
                "ROC-AUC together.",
            )
            result.add_warning(
                f"The label classes are imbalanced (ratio {imbalance_ratio:.1f}). "
                "Accuracy overstates the model on imbalanced data — prefer "
                "precision, recall and ROC-AUC."
            )
        else:
            result.add_verdict(
                "PASS", "class-balance",
                f"Class balance is acceptable on this label "
                f"({majority} vs {minority}, ratio {imbalance_ratio:.2f}).",
            )
        ctx.log_decision(
            f"Class balance: majority = {majority}, minority = {minority}, "
            f"ratio = {imbalance_ratio:.2f}."
        )

        if len(X_test) < 20:
            result.add_warning(
                f"The held-out test set is small (n = {len(X_test)}), so the "
                "reported metrics are noisy. Prefer a larger test_size or more "
                "data for firmer estimates."
            )
            ctx.log_decision(
                f"Test set has {len(X_test)} rows (< 20); added a small-test-"
                "set warning."
            )
        result.add_verdict(
            "PASS" if len(work) >= 30 else "WARN",
            "sample-size",
            f"{len(work)} complete rows were used. "
            + (
                "This is enough for a rough baseline."
                if len(work) >= 30
                else "Below 30 rows the results deserve expert review."
            ),
        )

        # --- cross-validation with mean and spread
        cv_splitter = StratifiedKFold(
            n_splits=cv_folds, shuffle=True, random_state=random_state
        )
        cv_scores = cross_val_score(
            LogisticRegression(max_iter=1000), X, y, cv=cv_splitter, scoring="accuracy"
        )
        cv_mean = float(np.mean(cv_scores))
        cv_sd = float(np.std(cv_scores))
        ctx.log_decision(
            f"Stratified {cv_folds}-fold CV accuracy: "
            f"{', '.join(f'{s:.4f}' for s in cv_scores)}; "
            f"mean = {cv_mean:.4f}, SD = {cv_sd:.4f}."
        )

        # --- tables
        cm_df = pd.DataFrame(
            cm,
            index=[f"Actual {x}" for x in labels],
            columns=[f"Predicted {x}" for x in labels],
        )
        result.tables["Confusion matrix"] = cm_df

        report = classification_report(
            y_test, y_pred, labels=labels, output_dict=True, zero_division=0
        )
        metric_rows = [
            {
                "Class": str(lab),
                "precision": round(float(report[str(lab)]["precision"]), 4),
                "recall": round(float(report[str(lab)]["recall"]), 4),
                "F1": round(float(report[str(lab)]["f1-score"]), 4),
                "support": report[str(lab)]["support"],
            }
            for lab in labels
        ]
        metric_rows.append(
            {
                "Class": "weighted avg",
                "precision": round(float(report["weighted avg"]["precision"]), 4),
                "recall": round(float(report["weighted avg"]["recall"]), 4),
                "F1": round(float(report["weighted avg"]["f1-score"]), 4),
                "support": report["weighted avg"]["support"],
            }
        )
        metric_rows.append(
            {
                "Class": "accuracy",
                "precision": "",
                "recall": "",
                "F1": round(accuracy, 4),
                "support": len(X_test),
            }
        )
        result.tables["Classification metrics"] = pd.DataFrame(metric_rows)

        cv_df = pd.DataFrame(
            {
                "Fold": [f"Fold {i + 1}" for i in range(len(cv_scores))],
                "accuracy": [round(float(s), 4) for s in cv_scores],
            }
        )
        cv_df.loc[len(cv_df)] = ["mean", round(cv_mean, 4)]
        cv_df.loc[len(cv_df)] = ["SD", round(cv_sd, 4)]
        result.tables["Cross-validation scores"] = cv_df

        # --- figures
        fpr, tpr, _ = roc_curve(y_test, y_proba, pos_label=labels[1])
        roc_fig, roc_caption = _roc_figure(fpr, tpr, auc, label_col)
        cv_fig, cv_caption = _cv_figure(cv_scores, cv_mean, cv_sd, cv_folds)
        result.figures.append(FigureItem(name="roc_curve", figure=roc_fig, caption=roc_caption))
        result.figures.append(
            FigureItem(name="cross_validation_scores", figure=cv_fig, caption=cv_caption)
        )

        # --- summaries (plain-English highlights)
        result.summaries = {
            "accuracy (test)": f"{accuracy:.3f}",
            "ROC-AUC (test)": f"{auc:.3f}",
            "precision / recall / F1 (weighted)": (
                f"{metric_rows[1]['precision']:.2f} / "
                f"{metric_rows[1]['recall']:.2f} / "
                f"{metric_rows[1]['F1']:.2f}"
            ),
            "cross-validation accuracy": (
                f"{cv_mean:.3f} ± {cv_sd:.3f} (mean ± SD over {cv_folds} folds)"
            ),
            "classes": f"{', '.join(map(str, labels))} ({majority} vs {minority})",
            "train / test rows": f"{len(X_train)} / {len(X_test)}",
        }

        # --- methods.txt sentences (>= 3)
        methods = [
            f"A logistic-regression baseline (max_iter = 1000) was trained on "
            f"{len(X_train)} rows to predict '{label_col}' from "
            f"{len(numeric_features)} numeric features, with a stratified "
            f"train/test split (test_size = {test_size:.1f}, random_state = "
            f"{random_state}).",
            f"On the held-out test set (n = {len(X_test)}) the model reached "
            f"accuracy = {accuracy:.3f}, ROC-AUC = {auc:.3f}, and weighted "
            f"precision / recall / F1 = {metric_rows[1]['precision']:.3f} / "
            f"{metric_rows[1]['recall']:.3f} / {metric_rows[1]['F1']:.3f}.",
            f"{cv_folds}-fold stratified cross-validation gave a mean accuracy "
            f"of {cv_mean:.3f} (SD = {cv_sd:.3f}).",
        ]
        if dropped:
            methods.append(
                f"{dropped} row(s) with missing values in the label or features "
                "were dropped; no value was imputed."
            )
        result.methods = methods

        # --- honest interpretation
        result.what_does_not_tell = (
            "A good test-set accuracy or ROC-AUC does not prove the model will "
            "generalise to new data in a different setting — it only describes "
            "this single held-out sample, and cross-validation only gives a "
            "rough idea of stability. Data leakage (using test information "
            "while training) would invalidate every number here; this run keeps "
            "train and test strictly separate. Accuracy is misleading on "
            "imbalanced classes, and this is deliberately an untuned logistic-"
            "regression baseline, not a tuned model: it is a lower bound for "
            "comparison, not a production-ready classifier."
        )
        return result


def _roc_figure(
    fpr: np.ndarray, tpr: np.ndarray, auc: float, label_col: str
) -> tuple[Any, str]:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.4, 5.0))
    ax.plot(fpr, tpr, color="#b48cd9", lw=2.2, label=f"ROC (AUC = {auc:.3f})")
    ax.plot([0, 1], [0, 1], ls="--", color="#888", lw=1.0, label="Chance")
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title(f"ROC curve: {label_col}", fontsize=11)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.grid(ls=":", alpha=0.5)
    ax.legend(loc="lower right", fontsize=9)
    fig.tight_layout()
    caption = f"ROC curve for '{label_col}' with test-set ROC-AUC = {auc:.3f}."
    return fig, caption


def _cv_figure(
    scores: np.ndarray, mean: float, sd: float, folds: int
) -> tuple[Any, str]:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    x = np.arange(1, len(scores) + 1, dtype=float)
    ax.bar(x, scores, color="#8fc98d", edgecolor="white", width=0.6)
    ax.axhline(mean, color="#333", ls="--", lw=1.6, label=f"mean = {mean:.3f} ± {sd:.3f}")
    ax.set_xticks(x)
    ax.set_xlabel("Fold")
    ax.set_ylabel("Accuracy")
    ax.set_title(f"Cross-validation accuracy ({folds} folds)", fontsize=11)
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", ls=":", alpha=0.5)
    ax.legend(fontsize=9)
    fig.tight_layout()
    caption = (
        f"Per-fold cross-validation accuracy (mean = {mean:.3f}, "
        f"SD = {sd:.3f})."
    )
    return fig, caption


# Module-level instance the registry looks for.
ANALYSIS = MlClassificationEvalAnalysis()
