"""Data card: a rich, honest profile of a loaded data frame.

The plain "advisor" (src/auphoria/advisor/) answers 'what kind is this column
and what analyses fit'. The **data card** answers the supervisor-style
question: 'what is actually in this data, and what should I look at before
trusting any analysis?'

Every column is classified into one of:

    numeric, ordinal, binary, categorical, date, id, free_text

and for each column we report missingness and uniqueness. The data card then
flags dataset-level concerns:

- duplicate rows (count only - never removed);
- constant columns (useless as a predictor);
- suspected outliers on numeric columns (IQR rule - FLAGGED ONLY, never
  removed, never silently changed);
- suspicious values such as negative ages (heuristic - flagged, not removed).

It also suggests a column *role* (outcome / group / covariate / id / time /
weight) so the interactive flow can ask the user to confirm or correct it.
Nothing here edits the data; every flag is advisory and goes into the decision
log with plain-English text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

# Column type labels (machine + human readable).
NUMERIC = "numeric"
ORDINAL = "ordinal"
BINARY = "binary"
CATEGORICAL = "categorical"
DATE = "date"
ID = "id"
FREE_TEXT = "free_text"

# Column roles (what a column is FOR in a study).
ROLE_OUTCOME = "outcome"
ROLE_GROUP = "group"
ROLE_COVARIATE = "covariate"
ROLE_ID = "id"
ROLE_TIME = "time"
ROLE_WEIGHT = "weight"
ROLE_UNKNOWN = "unknown"

# An integer column with at most this many distinct values is *candidate*
# ordinal (e.g. a Likert 1-5). Heuristic only.
_ORDINAL_MAX_UNIQUE = 12
# A column is "candidate id" if it is almost all-unique and not obviously a
# measurement (long text, or high-cardinality object).
_ID_UNIQUE_RATIO = 0.95
# For ordinal/binary detection we look at the *non-null* distinct count.
# Suspicious-value heuristics: column names strongly suggesting a non-negative
# quantity.
_NON_NEGATIVE_HINT = ("age", "height", "weight", "mass", "concentration",
                      "price", "cost", "income", "days", "score", "count",
                      "n_", "length", "width", "depth", "dose", "amount",
                      "temperature", "hours", "yield", "value")


@dataclass
class ColumnCard:
    name: str
    dtype: str
    kind: str                 # one of the type labels above
    n_values: int             # total non-null
    n_unique: int             # distinct non-null
    n_missing: int
    missing_pct: float
    sample: list[str]
    # Role suggestion (user confirms/corrects in the interactive flow).
    suggested_role: str = ROLE_UNKNOWN
    role: str | None = None   # set once the user confirms

    @property
    def has_missing(self) -> bool:
        return self.n_missing > 0


@dataclass
class DataFlag:
    level: str                # "WARN" or "NOTE"
    column: str | None
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {"level": self.level, "column": self.column, "message": self.message}


@dataclass
class DataCard:
    n_rows: int
    n_cols: int
    columns: list[ColumnCard] = field(default_factory=list)
    n_duplicate_rows: int = 0
    flags: list[DataFlag] = field(default_factory=list)

    def by_name(self, name: str) -> ColumnCard | None:
        for c in self.columns:
            if c.name == name:
                return c
        return None

    def of_kind(self, kind: str) -> list[ColumnCard]:
        return [c for c in self.columns if c.kind == kind]

    def flag_messages(self) -> list[str]:
        return [f.message for f in self.flags]


def _detect_kind(series: pd.Series) -> str:
    """Classify a single column into one of the data-card kinds."""
    if pd.api.types.is_bool_dtype(series.dtype):
        return BINARY

    non_null = series.dropna()
    if non_null.empty:
        return CATEGORICAL  # all missing: can't say much; treat as categorical

    # ---- a true datetime dtype is a date (checked BEFORE numeric coercion,
    # because pandas can coerce datetime64 values to integer nanoseconds).
    if pd.api.types.is_datetime64_any_dtype(series.dtype):
        return DATE

    # ---- Numeric is checked BEFORE string-date guessing, because pandas parses
    # plain integers (e.g. 0-8) as nanosecond timestamps if you ask for dates.
    coerced = _safe_numeric(non_null)
    is_numeric = np.count_nonzero(~np.isnan(coerced)) / len(non_null) >= 0.9
    if is_numeric:
        distinct = int(non_null.astype(str).nunique())
        # integer-like with few distinct values -> candidate ordinal
        clean = coerced[~np.isnan(coerced)]
        ints_only = bool(np.all(np.equal(np.mod(clean, 1), 0)))
        if ints_only and 2 < distinct <= _ORDINAL_MAX_UNIQUE:
            return ORDINAL
        return NUMERIC

    # ---- only numeric-unparseable columns are checked for string dates
    if _is_date_like(non_null):
        return DATE

    # Object/text: categorical, id, or free text.
    distinct = int(non_null.nunique())
    unique_ratio = distinct / len(non_null)
    mean_len = float(np.mean([len(str(v)) for v in non_null.iloc[:200]])) if len(non_null) else 0
    if unique_ratio >= _ID_UNIQUE_RATIO and mean_len > 4 and distinct > 20:
        return ID
    if mean_len > 80:  # long prose cell
        return FREE_TEXT
    if distinct == 2:
        return BINARY
    return CATEGORICAL


def _is_date_like(series: pd.Series) -> bool:
    import warnings

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            coerced = pd.to_datetime(series, errors="coerce")
        return coerced.notna().mean() >= 0.9
    except Exception:  # noqa: BLE001 - any parse failure means "not a date"
        return False


def _safe_numeric(series: pd.Series) -> np.ndarray:
    try:
        return pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    except Exception:  # noqa: BLE001
        return np.full(len(series), np.nan)


def _suggest_role(kind: str, name: str, n_unique: int, n_values: int) -> str:
    """A first guess at a column's role; user confirms/corrects."""
    low = name.strip().lower()
    if kind == DATE:
        return ROLE_TIME
    if kind == ID:
        return ROLE_ID
    if kind == BINARY or (kind == CATEGORICAL and n_unique <= 6 and n_values > 0):
        # two/few categories: often the group we compare, sometimes the outcome.
        if n_unique <= 2:
            return ROLE_GROUP
        return ROLE_GROUP
    if kind == ORDINAL:
        return ROLE_GROUP   # ordered factor often a group; user can switch to covariate
    if any(h in low for h in ("weight", "wt")):
        return ROLE_WEIGHT
    if kind in (NUMERIC, ORDINAL):
        return ROLE_OUTCOME
    return ROLE_UNKNOWN


def _suspicious_values(series: pd.Series, name: str) -> list[str]:
    """Return plain-English notes about value-level concerns (never remove)."""
    notes: list[str] = []
    low = name.strip().lower()
    if any(h in low for h in _NON_NEGATIVE_HINT) or low.startswith("n"):
        nums = _safe_numeric(series)
        neg = int(np.sum(nums < 0))
        if neg:
            notes.append(
                f"'{name}' has {neg} negative value(s), but its name suggests a "
                f"non-negative quantity (e.g. age/length/score). Double-check "
                f"whether these are real (a coding scheme like -999 for missing) "
                f"or an error."
            )
    # Percentages sanity (0-100).
    if "pct" in low or "percent" in low:
        nums = _safe_numeric(series)
        bad = int(np.sum((nums < 0) | (nums > 100)))
        if bad:
            notes.append(
                f"'{name}' has {bad} value(s) outside 0-100, but its name "
                f"suggests a percentage. Verify them."
            )
    return notes


def profile_data_card(df: pd.DataFrame) -> DataCard:
    """Build the data card for a data frame. Never modifies ``df``."""
    card = DataCard(n_rows=int(df.shape[0]), n_cols=len(df.columns))

    for name in df.columns:
        series = df[name]
        kind = _detect_kind(series)
        non_null = series.dropna()
        n_unique = int(non_null.nunique())
        n_missing = int(series.isna().sum())
        # Name-hint: a mostly-unique column whose name suggests an identifier
        # (id, subject, code, sample, patient) is almost always an id column,
        # even if short (e.g. "P1", "AB12").
        low_name = str(name).strip().lower()
        unique_ratio = n_unique / len(non_null) if len(non_null) else 0
        if unique_ratio >= 0.85 and any(
            tok in low_name for tok in ("id", "subject", "code", "sample", "key", "patient")
        ) and n_unique > 2:
            kind = ID
        sample = [str(v) for v in non_null.unique().tolist()[:5]]
        cc = ColumnCard(
            name=str(name),
            dtype=str(series.dtype),
            kind=kind,
            n_values=int(len(non_null)),
            n_unique=n_unique,
            n_missing=n_missing,
            missing_pct=round(100.0 * n_missing / len(series), 1) if len(series) else 0.0,
            sample=sample,
            suggested_role=_suggest_role(kind, str(name), n_unique, int(len(non_null))),
        )
        card.columns.append(cc)

        for note in _suspicious_values(series, str(name)):
            card.flags.append(DataFlag("WARN", str(name), note))

    # Duplicate rows (flagged; never removed).
    if df.shape[0] > 1:
        dup = int(df.duplicated().sum())
        card.n_duplicate_rows = dup
        if dup:
            card.flags.append(DataFlag(
                "NOTE", None,
                f"{dup} row(s) are exact duplicates of another row. They were "
                f"kept, but if they are accidental copies you should remove "
                f"them in your spreadsheet before analysis."
            ))

    # Constant columns (no analytic value as a predictor).
    for cc in card.columns:
        if cc.n_unique <= 1 and df.shape[0] > 1:
            card.flags.append(DataFlag(
                "WARN", cc.name,
                f"Column '{cc.name}' has only {cc.n_unique} distinct value(s) - "
                f"it never changes and cannot help separate anything. Keep it "
                f"(it may be an id or intercept) but do not use it as a predictor."
            ))

    # Suspected outliers on numeric columns (IQR rule - FLAG ONLY).
    for cc in card.columns:
        if cc.kind not in (NUMERIC, ORDINAL):
            continue
        arr = _safe_numeric(df[cc.name])
        arr = arr[~np.isnan(arr)]
        if len(arr) < 4:
            continue
        q1, q3 = np.percentile(arr, [25, 75])
        iqr = q3 - q1
        if iqr == 0:
            continue
        low_bound, high_bound = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        n_out = int(np.sum((arr < low_bound) | (arr > high_bound)))
        if n_out:
            card.flags.append(DataFlag(
                "WARN", cc.name,
                f"Column '{cc.name}' has {n_out} value(s) far from the rest "
                f"(more than 1.5 x the inter-quartile range below/above). These "
                f"are FLAGGED for you to inspect - AUPHORIA will not remove or "
                f"change them. An outlier can be a real extreme or a typo."
            ))
    return card


def render_data_card_text(card: DataCard) -> str:
    """Human-readable data card for the terminal."""
    lines = [
        f"Data card: {card.n_rows} rows x {card.n_cols} columns",
        f"Duplicate rows: {card.n_duplicate_rows}",
        "",
        f"{'Column':<24}{'type':<14}{'values':<8}{'unique':<8}{'missing':<8}role",
        "-" * 70,
    ]
    for cc in card.columns:
        lines.append(
            f"{cc.name:<24}{cc.kind:<14}{cc.n_values:<8}{cc.n_unique:<8}"
            f"{cc.n_missing:<8}{cc.suggested_role}"
        )
    if card.flags:
        lines.append("")
        lines.append("Flags (for your review - nothing was changed):")
        for f in card.flags:
            lines.append(f"  [{f.level}] {f.message}")
    return "\n".join(lines)
