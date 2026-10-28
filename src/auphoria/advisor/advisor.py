"""Data profiling: understand what each column is before any analysis.

The advisor looks at a loaded DataFrame and labels each column as one of:

- ``numeric``      numbers (int/float, or text that parses entirely as numbers)
- ``categorical``  discrete labels / groups (object/bool/category/text)
- ``datetime``     parseable dates
- ``text``         free-form text that isn't a useful group

It also records missingness, so the engine can warn before an analysis loses
rows to missing values. Nothing here is statistical logic; it just classifies
columns so the menu can offer sensible analyses.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from auphoria.core.errors import InputValidationError

# Column-kind string constants shared with params.py.
KIND_NUMERIC = "numeric"
KIND_CATEGORICAL = "categorical"
KIND_DATETIME = "datetime"
KIND_TEXT = "text"

# Threshold: at most this many distinct values before we stop treating a
# text/Object column as a clean category for menu purposes.
_MAX_GROUP_VALUES = 50


@dataclass
class ColumnProfile:
    name: str
    kind: str
    n_missing: int
    n_unique: int
    dtype: str
    sample_values: list[str] = field(default_factory=list)

    @property
    def has_missing(self) -> bool:
        return self.n_missing > 0


@dataclass
class DataProfile:
    n_rows: int
    n_cols: int
    columns: list[ColumnProfile] = field(default_factory=list)

    def by_name(self, name: str) -> ColumnProfile | None:
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def of_kind(self, kind: str) -> list[ColumnProfile]:
        return [col for col in self.columns if col.kind == kind]

    def numeric(self) -> list[ColumnProfile]:
        return self.of_kind(KIND_NUMERIC)

    def categorical(self) -> list[ColumnProfile]:
        return self.of_kind(KIND_CATEGORICAL)

    def kind_of(self, name: str) -> str | None:
        col = self.by_name(name)
        return col.kind if col else None


def _detect_kind(series: pd.Series) -> str:
    """Classify a single series without changing it."""
    dtype = series.dtype

    # Timestamps are easy.
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return KIND_DATETIME

    # Already-typed numeric (int/float/bool that are actually numeric).
    if pd.api.types.is_numeric_dtype(dtype):
        return KIND_NUMERIC

    if pd.api.types.is_bool_dtype(dtype):
        return KIND_CATEGORICAL

    if isinstance(dtype, pd.CategoricalDtype):
        return KIND_CATEGORICAL

    # Object / string: try to see if it is numeric or date-like.
    non_null = series.dropna()
    if non_null.empty:
        return KIND_TEXT

    # Numeric?
    coerced = pd.to_numeric(non_null, errors="coerce")
    numeric_ratio = float(np.count_nonzero(~pd.isna(coerced)) / len(non_null))
    if numeric_ratio >= 0.9:
        return KIND_NUMERIC

    # Date-like?
    if kind := _try_datetime(non_null):
        return kind

    # Otherwise: categorical if it has a bounded number of values, else text.
    u = int(non_null.nunique())
    if u <= _MAX_GROUP_VALUES:
        return KIND_CATEGORICAL
    return KIND_TEXT


def _try_datetime(series: pd.Series) -> str | None:
    # Detecting dates is best-effort; suppress pandas' "could not infer format"
    # chatter because we only probe (we never convert the user's data).
    import warnings

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            coerced = pd.to_datetime(series, errors="coerce")
    except Exception:  # noqa: BLE001 - any parse failure means "not datetime"
        return None
    if coerced.isna().sum() / len(series) > 0.5:
        return None
    return KIND_DATETIME


def profile_column(series: pd.Series, name: str) -> ColumnProfile:
    kind = _detect_kind(series)
    non_null = series.dropna()
    sample = [str(v) for v in non_null.unique().tolist()[:5]]
    return ColumnProfile(
        name=name,
        kind=kind,
        n_missing=int(series.isna().sum()),
        n_unique=int(non_null.nunique()),
        dtype=str(series.dtype),
        sample_values=sample,
    )


def profile_data_frame(
    df: pd.DataFrame,
    kind_overrides: dict[str, str] | None = None,
) -> DataProfile:
    """Build a DataProfile, applying any user-forced column kinds.

    ``kind_overrides`` maps column name -> one of the KIND_* constants and is
    the *only* way a user can force a column's type. Invalid values raise.
    """
    profile = DataProfile(n_rows=int(df.shape[0]), n_cols=len(df.columns))
    for col_name in df.columns:
        base = profile_column(df[col_name], col_name)
        kind = base.kind
        if kind_overrides and col_name in kind_overrides:
            forced = str(kind_overrides[col_name]).lower()
            aliases = {
                "number": KIND_NUMERIC,
                "numeric": KIND_NUMERIC,
                "category": KIND_CATEGORICAL,
                "categorical": KIND_CATEGORICAL,
                "date": KIND_DATETIME,
                "datetime": KIND_DATETIME,
                "text": KIND_TEXT,
                KIND_NUMERIC: KIND_NUMERIC,
                KIND_CATEGORICAL: KIND_CATEGORICAL,
                KIND_DATETIME: KIND_DATETIME,
                KIND_TEXT: KIND_TEXT,
            }
            if forced not in aliases:
                raise InputValidationError(
                    f"Kind '{kind_overrides[col_name]}' for column '{col_name}' is not "
                    f"recognised.",
                    hint="Use one of: numeric, categorical, datetime, text.",
                )
            kind = aliases[forced]
        profile.columns.append(
            ColumnProfile(
                name=col_name,
                kind=kind,
                n_missing=base.n_missing,
                n_unique=base.n_unique,
                dtype=base.dtype,
                sample_values=base.sample_values,
            )
        )
    return profile


def render_column_summary(profile: DataProfile) -> str:
    """One-line-per-column description for preview/confirmation screens."""
    lines = []
    for col in profile.columns:
        miss = f", {col.n_missing} missing" if col.has_missing else ""
        lines.append(f"  - {col.name}: {col.kind}{miss}")
    return "\n".join(lines)
