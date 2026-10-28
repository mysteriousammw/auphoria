"""Base classes and shared helpers for analyses.

Every analysis inherits from :class:`Analysis`, declares an ``id``, and
implements :meth:`Analysis.run`. The engine calls its ``check_fit`` first so
poor fits are refused (or warned about) before any computation runs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

# Headless rendering is mandatory (servers, CI, Colab headless sessions).
try:
    matplotlib.use("Agg")
except Exception:  # noqa: BLE001 - backend may already be locked; not fatal
    pass

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from auphoria.core.errors import AssumptionError  # noqa: E402
from auphoria.core.logging_core import log_traceback  # noqa: E402

# Numeric contants shared by analyses.
ZERO = 1e-12


@dataclass
class FigureItem:
    """A matplotlib figure destined for PNG + base64 embedding in the report."""

    name: str                 # filename stem, e.g. "ttest_boxplot"
    figure: Figure
    caption: str = ""


@dataclass(frozen=True)
class Verdict:
    """A plain-English PASS / WARN / FAIL about a check performed."""

    level: str          # "PASS", "WARN", "FAIL"
    check: str          # short machine-ish name, e.g. "sample-size"
    message: str        # human sentence

    def as_dict(self) -> dict[str, Any]:
        return {"level": self.level, "check": self.check, "message": self.message}


@dataclass
class AnalysisResult:
    """What an analysis returns to the engine.

    - ``tables``: ordered {table_name: DataFrame} written as <name>.csv AND
      shown in report.html.
    - ``figures``: list of FigureItem written as <name>.png and embedded.
    - ``summaries``: ordered {label: str} shown as a highlights card.
    - ``methods``: one or more paste-ready sentences for methods.txt.
    - ``warnings``: plain-English warnings shown to the user and in the report.
    - ``notes``: additional plain-English context (never alarming).
    - ``verdicts``: list of PASS/WARN/FAIL checks (assumptions, sample size...).
    - ``what_does_not_tell``: plain text on what this result does NOT imply,
      written honestly so the student does not over-read the output.
    """

    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    figures: list[FigureItem] = field(default_factory=list)
    summaries: dict[str, str] = field(default_factory=dict)
    methods: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    verdicts: list[Verdict] = field(default_factory=list)
    what_does_not_tell: str = ""
    #: Plain-English reasons this result needs a statistician's review (set by
    #: ADVANCED analyses when used outside their intended conditions, e.g. a
    #: small sample or a violated assumption). Rendered as a prominent banner.
    expert_review: list[str] = field(default_factory=list)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def add_verdict(self, level: str, check: str, message: str) -> None:
        self.verdicts.append(Verdict(level, check, message))

    def add_expert_review(self, message: str) -> None:
        """Flag that this result needs a statistician's review and why.

        Used by advanced analyses (ANCOVA, mixed-effects, survival, PCA, ML,
        ...) when they are run outside their intended conditions. The reason
        is shown as a prominent banner in the report and recorded in run.json.
        """
        self.expert_review.append(message)


@dataclass
class DecisionEvent:
    """One recorded decision: what we checked/did, and the plain reason."""

    at: str                 # ISO timestamp
    message: str            # what happened
    level: str = "info"     # info / warn / error

    def as_dict(self) -> dict[str, Any]:
        return {"at": self.at, "level": self.level, "message": self.message}


@dataclass
class RunContext:
    """Handed to :meth:`Analysis.run`; carries everything an analysis may need.

    Splits the invasive responsibilities (logging, output path, seed,
    reproducibility metadata, decision log) away from the analysis's own math
    so analyses stay simple and testable. ``decision_log`` records every
    assumption check, data decision, and whether a test was (not) run, with a
    plain-English reason — the audit trail promised to the user.
    """

    seed: int
    out_dir: Path
    data_name: str
    expert: bool
    _log: Any
    _log_decision: Callable[[str], None] = field(default_factory=lambda: lambda m: None)
    decision_log: list[DecisionEvent] = field(default_factory=list)
    input_sha256: str = ""
    package_versions: dict[str, str] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)

    def log_decision(self, message: str, level: str = "info") -> None:
        event = DecisionEvent(
            at=datetime.now().isoformat(timespec="seconds"),
            message=message,
            level=level,
        )
        self.decision_log.append(event)
        self._log_decision(message)

    def log_error(self, exc: BaseException) -> None:
        log_traceback(self._log, exc)

    def safe_seed(self) -> int:
        """Return a derived seed analyses can pass to np.random.default_rng."""
        return int(self.seed)

    def decision_log_dicts(self) -> list[dict[str, Any]]:
        return [e.as_dict() for e in self.decision_log]


class Analysis(ABC):
    """Base class for every AUPHORIA analysis."""

    #: stable id, must equal the manifest id and the folder name.
    id: str = ""
    #: human name, shown in menus/reports (from manifest at runtime).
    name: str = ""

    def __init__(self) -> None:
        if not self.id:
            raise AssumptionError(
                "An analysis class must set a non-empty 'id'.",
                hint="Set id = 'my_analysis' on the class.",
            )

    # ------------------------------------------------------------------ API
    @abstractmethod
    def run(
        self,
        data: pd.DataFrame,
        params: dict[str, Any],
        inputs: dict[str, str],
        ctx: RunContext,
    ) -> AnalysisResult:
        """Execute the analysis and return results.

        ``inputs`` maps the manifest's declared input role names to the actual
        column names chosen by the user (e.g. ``{"outcome": "height_cm"}``).
        Must not silently drop/change data; the engine converts unexpected
        exceptions into a user-friendly EngineError (traceback logged).
        """

    def check_fit(
        self,
        profile: Any,
        params: dict[str, Any],
        inputs: dict[str, str],
    ) -> list[str]:
        """Return a list of *refusal* reasons if the data clearly cannot be used.

        Called by the engine before ``run``. Return an empty list when the
        analysis can at least attempt the fit; raise :class:`AssumptionError`
        inside ``run`` for anything discovered once the actual columns are
        inspected. Overrides may special-case, e.g. t-test refusing 1 group.
        """
        del profile, params, inputs  # most analyses check nothing here (engine handles kinds)
        return []

    # ------------------------------------------------------ shared helpers
    @staticmethod
    def ensure_numeric(series: pd.Series, column: str) -> pd.Series:
        """Return a numeric copy of ``series`` or raise a plain-English refusal.

        Coercion is explicit: if turning the column numeric would *change*
        any non-null value (i.e. text that cannot become a number), we refuse
        rather than silently drop those cells.
        """
        original = series
        try:
            converted = pd.to_numeric(original, errors="coerce")
        except Exception as exc:  # noqa: BLE001
            raise AssumptionError(
                f"Column '{column}' could not be read as numbers.",
                hint="Check the column values; remove any stray text or symbols.",
            ) from exc
        # Any value that was non-null and became null was TEXT we cannot use.
        mask = original.notna() & converted.isna()
        bad = sorted({str(v) for v in original[mask].unique().tolist()})
        if mask.any():
            sample = ", ".join(bad[:5]) + (" ..." if len(bad) > 5 else "")
            raise AssumptionError(
                f"Column '{column}' contains text that cannot become a number "
                f"({len(bad)} problem value(s): {sample}).",
                hint=(
                    "Fix those cells in your data (or choose a different column). "
                    "AUPHORIA never drops or changes data for you."
                ),
            )
        return converted

    @staticmethod
    def count_missing(series: pd.Series, column: str) -> int:
        return int(series.isna().sum())

    @staticmethod
    def describe_missing(series: pd.Series, column: str, ctx: RunContext) -> None:
        n = series.isna().sum()
        if n:
            ctx.log_decision(
                f"Column '{column}' has {n} missing value(s); they are counted "
                f"and excluded for this analysis, never imputed."
            )

    @staticmethod
    def fmt_float(value: float | None, ndigits: int = 3) -> str:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return "NA"
        return f"{value:.{ndigits}f}"

    @staticmethod
    def fmt_p(p: float, alpha: float | None = None) -> str:
        """Format a p-value like 0.002, or '< 0.001' when very small."""
        if p < 0.001:
            return "< 0.001"
        return f"{p:.3f}"

    @staticmethod
    def bool_to_yesno(value: bool) -> str:
        return "Yes" if value else "No"
