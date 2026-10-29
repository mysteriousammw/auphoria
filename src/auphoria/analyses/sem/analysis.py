"""Structural Equation Model (one-factor CFA) for AUPHORIA.

Fits a CONFIRMATORY one-factor (latent variable) model to every numeric column
in the data using ``semopy``:

- every numeric column (the items) is assumed to load onto one latent factor,
  and AUPHORIA builds the ``F =~ item1 + item2 + ... + itemN`` model string;
- fits the model with ``semopy.Model(...).fit(data)`` (maximum likelihood);
- reports the standardised factor loadings for each item, the model-fit
  indices (CFI, TLI, RMSEA, SRMR, chi-square, degrees of freedom, chi-square
  p-value), and the fitted equation string;
- draws a bar chart of the standardised loadings.

Why one factor? A generic SEM needs the user to specify the model (which
factors load on which items, and any paths), and AUPHORIA runs non-interactively.
So it fits the simplest universally-applicable confirmatory model: a one-factor
CFA that directly tests whether the items measure one underlying construct.
Students with more complex hypothesised models (multiple factors, paths,
mediators) should see a statistician; the tool notes this as a limitation.

Guardrails are enforced here, not in the front end:
- fewer than three numeric items is refused (not enough to define a factor);
- fewer than 30 complete rows is refused (CFA needs a reasonable sample);
- missing values are counted, reported and excluded (listwise), never imputed;
- an effective sample below 100, or a poor fit (CFI < 0.9), flags an
  expert-review banner and a WARN verdict (the analysis still runs).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import semopy
import semopy.stats as semopy_stats

from auphoria.core.analysis import Analysis, AnalysisResult, FigureItem, RunContext
from auphoria.core.errors import AssumptionError

#: A latent factor needs at least three measured indicators.
_MIN_ITEMS = 3
#: Hard floor for a single complete sample (CFA below this is meaningless).
_MIN_ROWS = 30
#: Recommended minimum sample for a stable CFA.
_SAMPLE_RECOMMENDED = 100

# Interpretation thresholds (Hu & Bentler 1999, common practice):
_CFI_GOOD = 0.95
_TLI_GOOD = 0.95
_RMSEA_GOOD = 0.06
_SRMR_GOOD = 0.08
#: When CFI falls below this we tell the student the fit is poor and to
#: consider respecification / expert review.
_CFI_POOR = 0.90


def _model_string(items: list[str]) -> str:
    """Build the semopy model string for a one-factor confirmatory model.

    ``F =~ item1 + item2 + ... + itemN`` declares that the latent factor ``F``
    is measured by (loads onto) every item.
    """
    return "F =~ " + " + ".join(items)


def _srmr(data: pd.DataFrame, implied_cov: np.ndarray) -> float:
    """Standardised root mean square residual (Hu & Bentler, correlation metric).

    semopy 2.3.11's ``calc_stats`` reports CFI/TLI/RMSEA but not SRMR, so we
    compute it directly from the implied covariance matrix returned by
    ``Model.calc_sigma()``. SRMR is the square root of the mean of the squared
    standardised residuals (observed minus implied correlation), where each
    residual is standardised by the corresponding observed variances.
    """
    obs = data.cov().values
    p = obs.shape[0]
    so = np.diag(obs)
    sq = 0.0
    for i in range(p):
        for j in range(p):
            base = so[i] * so[j]
            if base <= 0.0:
                continue
            sq += (obs[i, j] - implied_cov[i, j]) ** 2 / base
    n_el = p * (p + 1) // 2
    return float(np.sqrt(sq / n_el))


def _loading_chart(loadings: pd.DataFrame, caption: str):
    import matplotlib.pyplot as plt

    items = loadings["Item"].tolist()
    est = loadings["Std. loading"].astype(float).tolist()
    fig, ax = plt.subplots(figsize=(max(5.0, 0.9 * len(items) + 2.0), 4.5))
    colours = ["#4c72b0" if abs(v) >= 0.4 else "#d9534f" for v in est]
    ax.bar(range(len(items)), est, color=colours)
    ax.axhline(0.4, color="#888", ls="--", linewidth=1.0, label="|loading| = 0.4")
    ax.axhline(0.0, color="#333", linewidth=0.8)
    ax.set_xticks(range(len(items)))
    ax.set_xticklabels(items, rotation=30, ha="right")
    ax.set_ylabel("Standardised loading on factor F")
    ax.set_ylim(-1.05, 1.05)
    ax.set_title("Standardised factor loadings", fontsize=11)
    ax.grid(axis="y", ls=":", alpha=0.5)
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig, caption


class SEMAnalysis(Analysis):
    id = "sem"
    name = "Structural Equation Model (one-factor CFA)"

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        del inputs  # SEM uses every numeric column automatically
        result = AnalysisResult()

        if len(data) < _MIN_ROWS:
            raise AssumptionError(
                f"Structural equation modelling needs at least {_MIN_ROWS} rows of "
                f"data; this file has only {len(data)}.",
                hint="Confirmatory factor analysis needs a reasonable sample "
                     "size; add more observations or use a different analysis.",
            )

        numeric_cols = [
            c for c in data.columns if pd.api.types.is_numeric_dtype(data[c])
        ]
        n_missing_total = 0
        for c in numeric_cols:
            n_missing_value = int(data[c].isna().sum())
            n_missing_total += n_missing_value
            self.describe_missing(data[c], c, ctx)
        if n_missing_total:
            ctx.log_decision(
                f"{n_missing_total} missing value(s) across the numeric item "
                "columns; they are counted and excluded, never imputed."
            )

        # Narrow to the numeric columns that actually vary (a constant column
        # has no variance and cannot carry a factor loading).
        used = [c for c in numeric_cols if data[c].dropna().std() > 1e-12]
        dropped_const = set(numeric_cols) - set(used)
        if dropped_const:
            result.add_warning(
                f"Constant column(s) {', '.join(sorted(dropped_const))} were "
                "ignored (zero variance makes them uninformative for a factor "
                "model)."
            )
            ctx.log_decision(
                f"Excluded constant column(s): {', '.join(sorted(dropped_const))}."
            )

        if len(used) < _MIN_ITEMS:
            raise AssumptionError(
                f"Structural equation modelling needs at least {_MIN_ITEMS} numeric "
                f"item columns loading onto the latent factor; found {len(used)}.",
                hint="Pick a file with several correlated numeric item columns "
                     "that might all measure one underlying construct.",
            )

        matrix = data[used].astype(float)
        n_before = len(matrix)
        complete = matrix.dropna()
        dropped_rows = n_before - len(complete)
        if dropped_rows:
            result.add_warning(
                f"{dropped_rows} row(s) had a missing value in one of the item "
                "columns and were left out of this analysis. Missing values were "
                "counted and excluded, never imputed."
            )
            ctx.log_decision(
                f"Excluded {dropped_rows} row(s) with missing item values "
                f"(listwise); {len(complete)} row(s) remain."
            )

        if len(complete) < _MIN_ROWS:
            raise AssumptionError(
                "After removing rows with missing values there were fewer than "
                f"{_MIN_ROWS} complete rows left to model.",
                hint="Provide more complete observations, or reduce missingness.",
            )
        n = len(complete)
        items = list(complete.columns)

        alpha = float(params.get("alpha", 0.05))
        ctx.log_decision(
            f"Fitting a one-factor confirmatory model on {len(items)} item "
            f"column(s) ({', '.join(items)}) with n = {n} complete rows; "
            f"alpha = {alpha}."
        )

        # --- build and fit the semopy model
        model_string = _model_string(items)
        model = semopy.Model(model_string)
        try:
            model.fit(complete)
        except Exception as exc:  # noqa: BLE001 - surface a plain refusal
            raise AssumptionError(
                "The one-factor confirmatory model could not be fitted (the "
                f"optimiser failed; message: {exc}).",
                hint="This often means a singular or non-positive-definite "
                     "covariance matrix, or items that are linear combinations "
                     "of each other. Check for perfectly-aligned items.",
            ) from exc

        # --- model-fit indices
        fit = semopy_stats.calc_stats(model)
        row = fit.loc["Value"] if "Value" in fit.index else fit.iloc[0]

        def _get(key: str, default: float | None = None) -> float | None:
            try:
                val = row[key]
                if val is None or (isinstance(val, float) and np.isnan(val)):
                    return default
                return float(val)
            except KeyError:
                return default

        cfi = _get("CFI")
        tli = _get("TLI")
        rmsea = _get("RMSEA")
        chi2 = _get("chi2")
        dof = _get("DoF")
        chi2_p = _get("chi2 p-value")

        observed_vars = list(complete.columns)
        implied_cov = np.asarray(model.calc_sigma()[0], dtype=float)
        # calc_sigma returns the implied covariance for ALL model variables in
        # the order semopy classified them, which may not match column order.
        # Reorder to the observed item order only when counts match so SRMR is
        # computed on the observed block only.
        srmr = None
        if implied_cov.ndim == 2 and implied_cov.shape[0] == len(observed_vars):
            srmr = _srmr(complete.loc[:, observed_vars], implied_cov)

        ctx.log_decision(
            f"Fit indices: CFI = {cfi}, TLI = {tli}, RMSEA = {rmsea}, "
            f"SRMR = {srmr}, chi2 = {chi2} (df = {dof}), p = {chi2_p}."
        )

        # --- factor loadings from the standardised parameter table
        insp = model.inspect(std_est=True)
        est_std_col = "Est. Std" if "Est. Std" in insp.columns else None
        load_rows = insp[insp["op"] == "=~"].copy() if "op" in insp.columns else None
        if load_rows is None or len(load_rows) == 0:
            # Older/newer semopy may label the measurement operator differently.
            load_rows = insp[insp["op"] == "~"].copy()
        load_rows = load_rows[load_rows["rval"] == "F"].copy()

        loading_table = pd.DataFrame(columns=["Item", "Std. loading", "SE", "p-value"])
        raw_col = next(c for c in ("Estimate", "Est. Std") if c in insp.columns)

        # Build one row per item using the operator rows that bind item ~ F.
        use_op = "=~" if "=~" in set(load_rows["op"]) else "~"
        sel = load_rows[load_rows["op"] == use_op]
        se_col = next(c for c in ("Std. Err", "Std. Err.") if c in insp.columns)
        p_col = next(c for c in ("p-value", "p") if c in insp.columns)
        records = []
        for _idx, r in sel.iterrows():
            lv = r["lval"]
            est_std = float(r[est_std_col]) if est_std_col else float(r[raw_col])
            se = self._coerce_float(r[se_col])
            pv = self._coerce_float(r[p_col])
            records.append({
                "Item": str(lv),
                "Std. loading": round(est_std, 4),
                "SE": round(se, 4) if se is not None else np.nan,
                "p-value": pv,
            })
        # Keep only rows whose lval is an observed item in our used columns.
        records = [rec for rec in records if rec["Item"] in items]
        loading_table = pd.DataFrame(records, columns=["Item", "Std. loading", "SE", "p-value"])
        loading_table["p-value"] = loading_table["p-value"].map(self._fmt_p_series)
        # Reorder to the item order used in the model string.
        order = {name: i for i, name in enumerate(items)}
        loading_table = loading_table.copy()
        loading_table = loading_table.sort_values(
            by="Item", key=lambda s: s.map(order)
        ).reset_index(drop=True)
        result.tables["Factor loadings"] = loading_table

        # --- model-fit table
        def _cell(value: float | None, ndigits: int = 4) -> str | float:
            if value is None or (isinstance(value, float) and np.isnan(value)):
                return "NA"
            if ndigits == 0:
                return int(value)
            return round(value, ndigits)

        fit_table = pd.DataFrame({
            "Statistic": ["CFI", "TLI", "RMSEA", "SRMR", "chi2", "Df", "chi2 p"],
            "Value": [
                _cell(cfi),
                _cell(tli),
                _cell(rmsea),
                _cell(srmr),
                _cell(chi2, 3),
                _cell(dof, 0),
                self.fmt_p(chi2_p) if chi2_p is not None else "NA",
            ],
        })
        result.tables["Model fit"] = fit_table

        # --- verdicts on fit interpretation
        n_finite = sum(1 for v in (cfi, tli, rmsea, srmr) if v is not None)
        if n_finite >= 2 and cfi is not None:
            cfi_good = cfi >= _CFI_GOOD
            rmsea_good = rmsea is not None and rmsea <= _RMSEA_GOOD
            good = cfi_good and rmsea_good
            result.add_verdict(
                "PASS" if good else "WARN",
                "model-fit",
                f"The one-factor model fit is {'acceptable' if good else 'marginal or poor'} "
                f"(CFI = {cfi:.3f}, RMSEA = {rmsea:.3f} if computed, "
                f"TLI = {tli:.3f} if computed, SRMR = {srmr:.3f} if computed); "
                "common rules of thumb are CFI ≥ 0.95, TLI ≥ 0.95, "
                "RMSEA ≤ 0.06 and SRMR < 0.08.",
            )
            if chi2_p is not None and chi2 is not None and dof is not None:
                sig = chi2_p < alpha
                result.add_verdict(
                    "WARN" if sig else "PASS",
                    "chi-square",
                    f"Chi-square goodness-of-fit chi2({int(dof)}) = {chi2:.2f}, "
                    f"p = {self.fmt_p(chi2_p)}; {'the model is rejected at ' + str(alpha) + ' (often due to large n)' if sig else 'the model is not rejected'} — a non-significant p supports the model.",
                )
        else:
            result.add_verdict(
                "WARN", "model-fit",
                "Fit indices could not be fully computed; check the fit table.",
            )

        # --- expert review and warnings
        if n < _SAMPLE_RECOMMENDED:
            result.add_warning(
                f"The sample is small for a confirmatory factor analysis (n = {n}; "
                f"recommended about {_SAMPLE_RECOMMENDED} complete observations)."
            )
            result.add_expert_review(
                f"Sample size {n} is below the recommended minimum of about "
                f"{_SAMPLE_RECOMMENDED} observations for confirmatory factor "
                "analysis; loadings and fit indices carry substantial sampling "
                "error at this size."
            )
        if cfi is not None and cfi < _CFI_POOR:
            result.add_expert_review(
                f"CFI = {cfi:.3f} is below {_CFI_POOR:.2f}; the one-factor model "
                "does not fit the data well. A respecified model (different "
                "structure, cross-loadings, or dropping poor items) and a "
                "statistician's review is recommended."
            )

        # --- fitted equation string
        equation = model_string + "  (one-factor confirmatory model)"

        # --- figures
        if len(loading_table) > 0:
            fig, cap = _loading_chart(
                loading_table,
                "Standardised loadings of each item on the one latent factor F",
            )
            result.figures.append(FigureItem(name="sem_loadings", figure=fig, caption=cap))

        # --- summaries
        srmr_s = f"{srmr:.3f}" if srmr is not None else "NA"
        cfi_s = f"{cfi:.3f}" if cfi is not None else "NA"
        rmsea_s = f"{rmsea:.3f}" if rmsea is not None else "NA"
        result.summaries = {
            "items": f"{len(items)} numeric item column(s)",
            "sample": f"n = {n} complete rows",
            "model": "single latent factor F (one-factor CFA)",
            "CFI": cfi_s,
            "RMSEA": rmsea_s + " (≤ 0.06 good)",
            "SRMR": srmr_s + " (< 0.08 good)",
        }

        # --- methods sentences
        srmr_text = f", SRMR = {srmr:.3f}" if srmr is not None else ""
        chi2_text = ""
        if chi2 is not None and dof is not None and chi2_p is not None:
            chi2_text = (f"; chi-square({int(dof)}) = {chi2:.2f}, "
                         f"p = {self.fmt_p(chi2_p)}")
        methods = [
            f"A one-factor confirmatory factor analysis was run with semopy "
            f"{semopy.__version__} on {len(items)} standardised numeric item "
            f"column(s) ({', '.join(items)}) with listwise deletion, leaving "
            f"n = {n} complete observations.",
            f"The hypothesised model declared that all items load on a single "
            f"latent factor (equation: {equation}).",
            f"Model fit was: CFI = {cfi_s}, TLI = "
            f"{f'{tli:.3f}' if tli is not None else 'NA'}, RMSEA = {rmsea_s}"
            f"{srmr_text}{chi2_text}.",
        ]
        if dropped_rows:
            methods.append(
                f"{dropped_rows} row(s) with missing item values were excluded; "
                "no missing values were imputed."
            )
        result.methods = methods

        # --- honest interpretation
        result.what_does_not_tell = (
            "A good fit does NOT prove the model is correct: many different "
            "(equivalent) models can fit the same data equally well, and fit "
            "indices only tell you that one hypothesised structure is not "
            "inconsistent with the data. The one-factor model assumes the items "
            "are unidimensional and does not test cross-loadings or the causal "
            "direction of any paths. This is not a full path/SEM analysis with "
            "mediators or multiple factors; AUPHORIA fits a single latent "
            "factor by default because a generic SEM needs a user-specified "
            "model that this tool cannot collect interactively."
        )

        return result

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        """Convert a semopy cell to float, or None when it is a placeholder.

        semopy renders unavailable estimates as '-', 'nan' or a None; we
        convert those to None so callers can format them as 'NA' instead of
        crashing on a non-numeric string.
        """
        if value is None:
            return None
        if isinstance(value, str):
            s = value.strip().lower()
            if s in ("", "-", "nan", "none", "n/a", "na"):
                return None
        try:
            v = float(value)
        except (TypeError, ValueError):
            return None
        if np.isnan(v):
            return None
        return v

    @staticmethod
    def _fmt_p_series(value: Any) -> str:
        v = SEMAnalysis._coerce_float(value)
        if v is None:
            return "NA"
        if v < 0.001:
            return "< 0.001"
        return f"{v:.3f}"

    def check_fit(
        self,
        profile: Any,
        params: dict[str, Any],
        inputs: dict[str, str],
    ) -> list[str]:
        del params, inputs
        refusals: list[str] = []
        # SEM needs several numeric item columns; refuse up front when the
        # profile can already see too few (run() still re-checks the frame).
        try:
            cols = list(profile.all_columns())  # type: ignore[attr-defined]
        except AttributeError:
            try:
                cols = list(profile)  # type: ignore[call-overload]
            except Exception:  # noqa: BLE001
                return refusals
        numeric = sum(1 for c in cols if getattr(c, "kind", None) == "numeric")
        if numeric < _MIN_ITEMS:
            refusals.append(
                f"Structural equation modelling needs at least {_MIN_ITEMS} numeric "
                f"item columns loading on the latent factor; this file appears "
                f"to have only {numeric}."
            )
        return refusals


# Module-level instance the registry looks for.
ANALYSIS = SEMAnalysis()
