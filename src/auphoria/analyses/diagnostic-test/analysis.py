"""Diagnostic test performance analysis for AUPHORIA.

Evaluates how well a numeric *test score* separates two groups defined by a
binary *reference standard* (the gold-standard true status, e.g. diseased vs
healthy). It reports:

- sensitivity, specificity, positive/negative predictive value (PPV/NPV),
- prevalence in the sample,
- a confusion matrix at a chosen threshold,
- a full ROC curve with the area under the curve (AUC).

The cutoff is chosen by Youden's J (the threshold maximising
sensitivity + specificity - 1 over the observed score range) unless the user
passes a fixed ``threshold`` parameter.

Guardrails are enforced here, not in the front end:
- the test score is confirmed numeric (refusing if it contains text);
- the reference must have exactly two categories (refuse otherwise),
  and both classes must be present;
- a higher score is assumed to mean a higher probability of disease;
- missing values are counted and excluded with a warning, never imputed;
- small or imbalanced samples warn, and outside the intended conditions
  (very small total, a very small class, or a very uncertain AUC) the
  result is flagged for expert review.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, roc_curve

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError

#: Minimum rows the intended, unstressed use assumes (matches the manifest).
_MIN_N = 20
#: Minimum rows in the smaller class before the result is could-be-unstable.
_MIN_CLASS = 5

#: Labels that mark a category as the *positive / diseased* class.
_POSITIVE_TOKENS = {
    "1",
    "true",
    "yes",
    "pos",
    "positive",
    "abnormal",
    "affected",
    "case",
    "disease",
    "diseased",
    "present",
    "+",
}


def _is_positive_label(cat: Any) -> bool:
    return str(cat).strip().lower() in _POSITIVE_TOKENS


def _pick_positive_class(cats: Sequence[Any], counts: Sequence[int]) -> Any:
    """Choose which reference category is the diseased (positive) class.

    Prefer an explicit label such as 'positive' / 'disease' / '1'; otherwise
    the rarer class (disease is usually the less common state); ties resolve
    by the lexicographically later label for determinism.
    """
    explicit = [c for c in cats if _is_positive_label(c)]
    if explicit:
        return explicit[0]
    zipped = sorted(zip(cats, counts, strict=False), key=lambda pair: str(pair[0]))
    return min(zipped, key=lambda pair: pair[1])[0]


def _youden_threshold(
    scores: np.ndarray, y: np.ndarray
) -> tuple[float, float, float, float, float]:
    """Pick the cutoff by Youden's J over the observed score range.

    Returns (threshold, sensitivity, specificity, J). ``pred = score >= t``.
    """
    best_t: float | None = None
    best_j = -np.inf
    best_sens = best_spec = float("nan")
    for t in np.unique(scores):
        pred = scores >= t
        tp = float(((pred) & (y == 1)).sum())
        tn = float(((~pred) & (y == 0)).sum())
        fn = float(((~pred) & (y == 1)).sum())
        fp = float(((pred) & (y == 0)).sum())
        sens = tp / (tp + fn) if (tp + fn) > 0 else float("nan")
        spec = tn / (tn + fp) if (tn + fp) > 0 else float("nan")
        j = sens + spec - 1.0
        if not np.isnan(j) and j > best_j:
            best_j = j
            best_t = float(t)
            best_sens, best_spec = sens, spec
    if best_t is None:
        raise AssumptionError(
            "No usable threshold could be found over the test-score range.",
            hint="Check that the test-score column has some variation.",
        )
    return best_t, best_sens, best_spec, best_j


def _confusion(pred: np.ndarray, y: np.ndarray) -> dict[str, int]:
    return {
        "tp": int(((pred) & (y == 1)).sum()),
        "tn": int(((~pred) & (y == 0)).sum()),
        "fn": int(((~pred) & (y == 1)).sum()),
        "fp": int(((pred) & (y == 0)).sum()),
    }


def _auc_ci(scores: np.ndarray, y: np.ndarray, seed: int, n_boot: int = 2000) -> tuple[float, float]:
    """Bootstrap 95 % confidence interval for the AUC (seeded, reproducible)."""
    rng = np.random.default_rng(seed)
    a = scores[y == 1]
    b = scores[y == 0]
    n_a, n_b = len(a), len(b)
    vals = []
    for _ in range(n_boot):
        a_ = a[rng.integers(0, n_a, n_a)]
        b_ = b[rng.integers(0, n_b, n_b)]
        joined = np.concatenate([a_, b_])
        lab = np.concatenate([np.ones(n_a, dtype=int), np.zeros(n_b, dtype=int)])
        if np.unique(lab).size < 2 or np.ptp(joined) == 0:
            continue
        vals.append(roc_auc_score(lab, joined))
    if not vals:
        return float("nan"), float("nan")
    arr = np.sort(np.asarray(vals))
    lo = float(np.percentile(arr, 2.5))
    hi = float(np.percentile(arr, 97.5))
    return lo, hi


class DiagnosticTestAnalysis(Analysis):
    id = "diagnostic-test"
    name = "Diagnostic Test Performance"

    def check_fit(
        self,
        profile: Any,
        params: dict[str, Any],
        inputs: dict[str, str],
    ) -> list[str]:
        del params
        refusals: list[str] = []
        ref = inputs.get("reference")
        if ref is not None:
            col = profile.by_name(ref)
            # The reference standard may be a text/categorical (disease ↔ no
            # disease) OR a numeric binary 0/1 column (0=no, 1=yes); run()
            # validates it is genuinely two-valued. Refuse other kinds.
            if col is not None and col.kind not in ("categorical", "text", "numeric"):
                refusals.append(
                    f"'{ref}' looks like a {col.kind} column, not a reference "
                    "standard. The reference must be a binary (two-category) "
                    "column, e.g. disease yes/no."
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
        test_col = inputs["test"]
        ref_col = inputs["reference"]

        if test_col not in data.columns:
            raise AssumptionError(
                f"The data has no column named '{test_col}'.",
                hint="Pick a test-score column from your file.",
            )
        if ref_col not in data.columns:
            raise AssumptionError(
                f"The data has no column named '{ref_col}'.",
                hint="Pick a reference-standard column from your file.",
            )

        threshold_param = params.get("threshold")

        # Numeric guarantee on the test score (refuses non-numeric text).
        test = self.ensure_numeric(data[test_col], test_col)
        ctx.log_decision(
            f"Test score '{test_col}' treated as numeric; "
            f"{self.count_missing(test, test_col)} missing value(s)."
        )

        ref_raw = data[ref_col]
        self.describe_missing(ref_raw, ref_col, ctx)

        # Combine and drop rows missing EITHER value, with a warning.
        both = pd.DataFrame({test_col: test, ref_col: ref_raw})
        dropped = int(both.isna().any(axis=1).sum())
        both = both.dropna()
        if dropped:
            result.add_warning(
                f"{dropped} row(s) had a missing value in '{test_col}' or "
                f"'{ref_col}' and were left out of this analysis. They were "
                "counted, not changed or replaced (no imputation)."
            )
            ctx.log_decision(
                f"Excluded {dropped} row(s) with missing test/reference "
                f"(listwise); {len(both)} row(s) remain for the analysis."
            )

        if both.empty:
            raise AssumptionError(
                "After removing rows with missing values there were no complete "
                "rows left to analyse.",
                hint="Check that your test and reference columns have actual values.",
            )

        # The reference must be binary.
        cats = sorted(
            {c for c in both[ref_col].dropna().unique().tolist() if pd.notna(c)},
            key=str,
        )
        if len(cats) != 2:
            raise AssumptionError(
                f"The reference standard '{ref_col}' has {len(cats)} distinct "
                f"categor{'y' if len(cats) == 1 else 'ies'} ({', '.join(map(str, cats))}), "
                "but a diagnostic test needs exactly two (true/false, "
                "diseased/healthy).",
                hint="Pick a binary reference-standard column with two categories.",
            )

        counts = {c: int((both[ref_col] == c).sum()) for c in cats}
        positive = _pick_positive_class(cats, [counts[c] for c in cats])
        negative = next(c for c in cats if c != positive)
        pos_n = counts[positive]
        neg_n = counts[negative]
        ctx.log_decision(
            f"Reference '{ref_col}' mapped to 0/1 with disease (positive) = "
            f"'{positive}' and healthy (negative) = '{negative}'; "
            f"{pos_n} positive / {neg_n} negative rows."
        )

        y = (both[ref_col] == positive).astype(int).to_numpy()
        scores = both[test_col].to_numpy(dtype=float)
        n = len(scores)

        if np.ptp(scores) == 0:
            raise AssumptionError(
                "The test score is constant across all rows, so no discrimination "
                "between the two groups is possible.",
                hint="Choose a test-score column that varies across subjects.",
            )

        # --- verdicts: sample size and class balance
        if n < _MIN_N:
            result.add_verdict(
                "WARN", "sample-size",
                f"Total sample is small (n = {n}, recommended at least {_MIN_N}). "
                "Sensitivity/specificity here are unstable and need a "
                "statistician's review.",
            )
            result.add_expert_review(
                f"The total sample is small (n = {n}); the sensitivity, "
                "specificity and AUC should be interpreted cautiously and "
                "reviewed by a statistician."
            )
        else:
            result.add_verdict(
                "PASS", "sample-size",
                f"Total sample has n = {n} complete rows (>= {_MIN_N}).",
            )

        small_class = pos_n < _MIN_CLASS or neg_n < _MIN_CLASS
        if small_class:
            result.add_verdict(
                "WARN", "class-balance",
                f"The sample is imbalanced: {pos_n} positive vs {neg_n} negative "
                f"rows. One class has fewer than {_MIN_CLASS} members, so the "
                "performance estimates are unstable and need a statistician's "
                "review.",
            )
            result.add_expert_review(
                f"The reference classes are imbalanced ({pos_n} positive, "
                f"{neg_n} negative); estimates for the smaller class are "
                "unreliable and should be reviewed by a statistician."
            )
        else:
            result.add_verdict(
                "PASS", "class-balance",
                f"Both classes have at least {_MIN_CLASS} rows "
                f"(positive {pos_n}, negative {neg_n}).",
            )

        # --- chosen threshold: user-supplied or Youden's J
        if threshold_param is not None:
            t = float(threshold_param)
            sens, spec, j = float("nan"), float("nan"), None
            pred = scores >= t
            cm = _confusion(pred, y)
            sens = cm["tp"] / (cm["tp"] + cm["fn"]) if (cm["tp"] + cm["fn"]) > 0 else float("nan")
            spec = cm["tn"] / (cm["tn"] + cm["fp"]) if (cm["tn"] + cm["fp"]) > 0 else float("nan")
            j = sens + spec - 1.0
            ctx.log_decision(
                f"Using the user-supplied threshold t = {t:.6g} "
                f"(predicted positive when score >= {t:.6g})."
            )
        else:
            t, sens, spec, j = _youden_threshold(scores, y)
            ctx.log_decision(
                f"Chosen threshold by Youden's J = {t:.6g} "
                f"(sensitivity + specificity - 1 = {j:.4f})."
            )
            pred = scores >= t
            cm = _confusion(pred, y)

        tp, tn, fn, fp = cm["tp"], cm["tn"], cm["fn"], cm["fp"]
        prevalence = (tp + fn) / n
        ppv = tp / (tp + fp) if (tp + fp) > 0 else float("nan")
        npv = tn / (tn + fn) if (tn + fn) > 0 else float("nan")

        if np.isnan(sens) or np.isnan(spec):
            raise AssumptionError(
                "No genuine sensitivity/specificity could be computed at the "
                "chosen threshold (one of the cells is empty).",
                hint="Check that the threshold separates the two classes.",
            )

        # --- AUC
        auc = float(roc_auc_score(y, scores))
        auc_lo, auc_hi = _auc_ci(scores, y, seed=ctx.safe_seed())
        ctx.log_decision(
            f"AUC = {auc:.4f} (bootstrap 95% CI {auc_lo:.3f}-{auc_hi:.3f}, "
            f"n_boot = 2000, seed = {ctx.safe_seed()})."
        )
        if _MIN_CLASS <= min(pos_n, neg_n) and not np.isnan(auc_lo) and (
            auc_hi - auc_lo > 0.5
        ):
            result.add_expert_review(
                "The AUC bootstrap confidence interval is very wide, so the "
                "reported discrimination is highly uncertain; a statistician "
                "should review this result."
            )

        # --- tables
        confusion = pd.DataFrame(
            {
                "Reference positive": {"Predicted positive": tp, "Predicted negative": fn},
                "Reference negative": {"Predicted positive": fp, "Predicted negative": tn},
            }
        )
        result.tables["Confusion matrix"] = confusion
        performance = pd.DataFrame(
            {
                "Metric": [
                    "Total valid rows",
                    "Disease prevalence",
                    "Chosen threshold (score >= t)",
                    "Threshold selection",
                    "Sensitivity (TP/(TP+FN))",
                    "Specificity (TN/(TN+FP))",
                    "PPV (TP/(TP+FP))",
                    "NPV (TN/(TN+FN))",
                    "AUC",
                    "AUC 95% CI (bootstrap)",
                ],
                "Value": [
                    n,
                    f"{prevalence:.3f}",
                    f"{t:.6g}",
                    "Youden's J" if threshold_param is None else "user-supplied",
                    f"{sens:.3f}",
                    f"{spec:.3f}",
                    f"{ppv:.3f}" if not np.isnan(ppv) else "NA",
                    f"{npv:.3f}" if not np.isnan(npv) else "NA",
                    f"{auc:.3f}",
                    f"{auc_lo:.3f} - {auc_hi:.3f}" if not np.isnan(auc_lo) else "NA",
                ],
            }
        )
        result.tables["Performance"] = performance

        # --- summaries
        result.summaries = {
            "sensitivity": self.fmt_float(sens, 3),
            "specificity": self.fmt_float(spec, 3),
            "PPV": self.fmt_float(ppv, 3),
            "NPV": self.fmt_float(npv, 3),
            "disease prevalence": f"{prevalence:.3f}",
            "AUC": f"{auc:.3f}",
            "chosen threshold": f"{t:.6g}",
            "reference positive mapping": f"{positive}",
        }

        # --- figure (ROC curve)
        fig, caption = _roc_figure(y, scores, auc, positive, negative)
        result.figures.append(
            FigureItem(name="roc_curve", figure=fig, caption=caption)
        )

        # --- methods sentences
        methods = [
            f"The diagnostic accuracy of the numeric test score "
            f"'{test_col}' was assessed against the binary reference "
            f"'{ref_col}' ('{positive}' coded as the disease/positive class), "
            f"with n = {n} complete observations and a disease prevalence "
            f"of {prevalence:.3f}.",
            f"Using a cutoff chosen to maximise Youden's J "
            f"(score >= {t:.6g} called positive), sensitivity = {sens:.3f} "
            f"and specificity = {spec:.3f}; positive predictive value = "
            f"{ppv:.3f} and negative predictive value = {npv:.3f} at the "
            f"observed prevalence.",
            f"Discrimination was summarised by the area under the ROC curve, "
            f"AUC = {auc:.3f} (bootstrap 95% CI "
            f"{auc_lo:.3f}-{auc_hi:.3f}).",
        ]
        if dropped:
            methods.append(
                f"{dropped} row(s) with missing values in these columns were "
                "excluded; no missing values were imputed."
            )
        result.methods = methods

        # --- honest interpretation
        result.what_does_not_tell = (
            "Sensitivity and specificity are tied to the chosen threshold and "
            "to the disease prevalence in this sample — they are not fixed "
            "properties of the test and do not transfer to a different "
            "population. The AUC is a single overall summary of the whole ROC "
            "curve, not a per-patient probability, and a high AUC does not "
            "mean every patient near the threshold is correctly classified. "
            "Everything here is only as good as the reference standard: if "
            "the gold standard is faulty, these accuracy figures are "
            "misleading, and PPV/NPV will change if the prevalence changes."
        )
        return result


def _roc_figure(
    y: np.ndarray, scores: np.ndarray, auc: float, positive: Any, negative: Any
):
    import matplotlib.pyplot as plt

    fpr, tpr, _ = roc_curve(y, scores)
    fig, ax = plt.subplots(figsize=(6.2, 5.2))
    ax.plot(fpr, tpr, color="#2a6fb0", lw=2, label=f"ROC (AUC = {auc:.3f})")
    ax.plot([0, 1], [0, 1], ls="--", color="#999", lw=1, label="Chance")
    ax.set_xlabel("False positive rate (1 - specificity)")
    ax.set_ylabel("True positive rate (sensitivity)")
    ax.set_title(f"ROC curve (positive = {positive}, negative = {negative})", fontsize=10)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.grid(ls=":", alpha=0.5)
    ax.legend(loc="lower right", fontsize=9)
    fig.tight_layout()
    caption = (
        f"ROC curve for '{positive}' vs '{negative}' with AUC = {auc:.3f}. "
        f"A point at the top-left corner is a perfect test."
    )
    return fig, caption


# Module-level instance the registry looks for.
ANALYSIS = DiagnosticTestAnalysis()
