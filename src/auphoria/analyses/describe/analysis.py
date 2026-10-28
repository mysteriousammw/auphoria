"""Describe-my-data analysis (data card) for AUPHORIA.

This is the "look first" analysis that exercises the whole engine pipeline: it
loads the (already profiled) data, runs the rich data-card profiler
(``auphoria.core.data_card``), and reports the table-level and value-level
concerns as results, with PASS/WARN verdicts.

Nothing is changed or removed: duplicate rows and outliers are only counted and
described. This honours the rule that no code path alters the user's data
without saying so.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from auphoria.core.analysis import Analysis, AnalysisResult, RunContext
from auphoria.core.data_card import profile_data_card, render_data_card_text


class DescribeAnalysis(Analysis):
    id = "describe"
    name = "Describe My Data"

    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        del params, inputs
        result = AnalysisResult()

        card = profile_data_card(data)

        # --- log every flag through the decision log (nothing is silent).
        ctx.log_decision(
            f"Data card built: {card.n_rows} rows x {card.n_cols} columns, "
            f"{card.n_duplicate_rows} duplicate row(s)."
        )
        for flag in card.flags:
            ctx.log_decision(flag.message, level="warn" if flag.level == "WARN" else "info")

        # --- table 1: per-column card
        card_rows = []
        for cc in card.columns:
            card_rows.append({
                "Column": cc.name,
                "Type": cc.kind,
                "Values": cc.n_values,
                "Unique": cc.n_unique,
                "Missing": cc.n_missing,
                "Missing %": cc.missing_pct,
                "Suggested role": cc.suggested_role,
            })
        result.tables["Data card"] = pd.DataFrame(card_rows, columns=[
            "Column", "Type", "Values", "Unique", "Missing", "Missing %",
            "Suggested role",
        ])

        # --- table 2: dataset overview
        overview = pd.DataFrame({
            "Metric": ["Rows", "Columns", "Duplicate rows"],
            "Value": [card.n_rows, card.n_cols, card.n_duplicate_rows],
        })
        result.tables["Dataset overview"] = overview

        n_missing_cells = sum(cc.n_missing for cc in card.columns)
        result.summaries = {
            "rows": str(card.n_rows),
            "columns": str(card.n_cols),
            "missing cells": str(n_missing_cells),
            "flags to review": str(len([f for f in card.flags if f.level == "WARN"])),
            "constant columns": str(len([c for c in card.columns if c.n_unique <= 1 and card.n_rows > 1])),
        }

        # --- verdicts: honest PASS / WARN
        result.add_verdict(
            "PASS" if card.n_rows > 0 else "FAIL",
            "rows-present",
            f"The file has {card.n_rows} data row(s).",
        )
        if card.n_duplicate_rows:
            result.add_verdict(
                "WARN", "duplicate-rows",
                f"{card.n_duplicate_rows} row(s) are exact duplicates; they were "
                f"kept and should be reviewed (do not let them double-weight results).",
            )
        else:
            result.add_verdict("PASS", "duplicate-rows", "No exact duplicate rows found.")
        if n_missing_cells:
            result.add_verdict(
                "WARN", "missing-values",
                f"{n_missing_cells} cell(s) across your columns are blank; they "
                f"are counted, never imputed.",
            )
        else:
            result.add_verdict("PASS", "missing-values", "No missing values found.")
        for cc in card.columns:
            if cc.n_unique <= 1 and card.n_rows > 1:
                result.add_verdict(
                    "WARN", "constant-column",
                    f"Column '{cc.name}' never changes across rows, so it cannot "
                    f"help separate anything. Review whether it is useful.",
                )
        warn_flags = [f for f in card.flags if f.level == "WARN"]
        if warn_flags:
            result.add_verdict(
                "WARN", "flagged-values",
                f"{len(warn_flags)} value-level concern(s) are flagged for review "
                f"(e.g. outliers, suspicious values); none were changed.",
            )
        else:
            result.add_verdict(
                "PASS", "flagged-values",
                "No outliers or suspicious values were flagged by the heuristics.",
            )

        # --- methods + what this does not tell you
        result.methods = [
            "Descriptive data quality was assessed for each column: type "
            "(numeric/ordinal/binary/categorical/date/id/free text), number of "
            "values and unique values, missing counts, and a suggested role. "
            "Duplicate rows, constant columns, suspected outliers (IQR rule) "
            "and suspicious values were flagged for review but not removed or "
            "imputed.",
        ]
        result.what_does_not_tell = (
            "This description does NOT test any hypothesis, prove any "
            "relationship, or confirm the data are correct. A flag (e.g. an "
            "outlier or a negative age) means 'please look at it', not 'this "
            "is wrong'. Type labels and role suggestions are guesses for you "
            "to confirm. Check with your supervisor before drawing conclusions."
        )

        # keep the human-readable card available as a note for the terminal
        result.notes.append(render_data_card_text(card))
        return result


# Module-level instance the registry looks for.
ANALYSIS = DescribeAnalysis()
