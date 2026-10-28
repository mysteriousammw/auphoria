"""{{ MODULE_NAME }} analysis for AUPHORIA.

REPLACE THIS DOCSTRING: describe what the analysis does, when it is
appropriate, and give a tiny worked example. Keep it plain-English — students
who do not code read this page.

The structure mirrors every other analysis in src/auphoria/analyses/. Fill in
the `run()` method (and a `check_fit()` if you need to refuse bad fits), then
write the tests and this README's sibling. See docs CONTRIBUTING.md for the
full conventions and run `auphoria new-module` to regenerate this skeleton.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from auphoria.core.analysis import Analysis, AnalysisResult, RunContext
from auphoria.core.errors import AssumptionError


class {{ MODULE_CLASS }}(Analysis):
    id = "{{ MODULE_ID }}"
    name = "{{ MODULE_NAME }}"

    def check_fit(
        self,
        profile: Any,
        params: dict[str, Any],
        inputs: dict[str, str],
    ) -> list[str]:
        """Return refusal reasons if the data clearly cannot be used.

        Most analyses check nothing here (the engine validates column kinds);
        add a refusal when a design prerequisite is missing, e.g. fewer than
        two groups, or a group with a single observation. Refusals are surfaced
        as a plain AssumptionError with these reasons.
        """
        del profile, params  # placeholder: use what you need
        refusals: list[str] = []
        return refusals

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        result = AnalysisResult()

        # ---- REPLACE with your analysis. Example: confirm a required input
        # column exists, then guarantee it is numeric (refuses text that cannot
        # become a number rather than silently dropping it).
        outcome_col = inputs.get("outcome")
        if outcome_col is None:
            raise AssumptionError(
                "This analysis needs an 'outcome' column.",
                hint="Pick the numeric outcome column.",
            )
        if outcome_col not in data.columns:
            raise AssumptionError(
                f"The data has no column named '{outcome_col}'.",
                hint="Available columns: " + ", ".join(str(c) for c in data.columns) + ".",
            )
        outcome = self.ensure_numeric(data[outcome_col], outcome_col)
        self.describe_missing(outcome, outcome_col, ctx)

        ctx.log_decision(f"Analysing column '{outcome_col}' with {len(outcome)} rows.")

        # ---- Example output: a single summary table + a highlight card.
        # Replace with the analysis's real tables/figures/summaries/methods.
        summary = pd.DataFrame(
            {
                "Statistic": ["name", "n", "mean"],
                "Value": [
                    "Example analysis — implement run() to produce real output.",
                    int(outcome.notna().sum()),
                    round(float(outcome.mean()), 4),
                ],
            }
        )
        result.tables["Summary"] = summary
        result.summaries = {"progress": "Scaffold — implement run()."}
        result.methods = [
            "This is a scaffold. Replace these methods sentences with what "
            "your analysis actually computed.",
        ]

        result.what_does_not_tell = (
            "REPLACE: state plainly what this result does NOT imply, so a "
            "student does not over-read it (e.g. 'a significant p-value does "
            "not prove causation')."
        )
        return result


# Module-level instance the registry looks for.
ANALYSIS = {{ MODULE_CLASS }}()
