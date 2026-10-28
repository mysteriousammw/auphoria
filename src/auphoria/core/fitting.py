"""Which analyses can run on a given set of columns.

Shared by the CLI menu and the Colab notebook so that "does this analysis fit
my data" is decided in exactly one place. Front ends only pass in what columns
of each kind are available; no analysis logic lives in the front end.
"""

from __future__ import annotations

from auphoria.core import registry
from auphoria.core.params import (
    KIND_ANY,
    KIND_CATEGORICAL,
    KIND_DATETIME,
    KIND_NUMERIC,
    build_inputs,
)

# Manifest kind constants -> plain front-end labels (used by CLIs and the
# notebook dropdown). Keep in sync with params.ALL_COLUMN_KINDS.
KIND_LABEL = {
    KIND_NUMERIC: "numeric",
    KIND_CATEGORICAL: "categorical",
    KIND_DATETIME: "datetime",
    KIND_ANY: "any",
}


def analyses_that_fit(column_kinds: list[str]) -> list[str]:
    """Return analysis ids whose required inputs can all be satisfied.

    ``column_kinds`` is the set of distinct column kinds available in the
    data, using the front-end labels ("numeric", "categorical", "datetime",
    "any" — see :data:`KIND_LABEL`). An analysis fits when every required
    input has at least one available column of an accepted kind.
    """
    kinds = set(column_kinds)
    fitting: list[str] = []
    for a_id in sorted(registry.discover()):
        if _fits(registry.get(a_id).manifest, kinds):
            fitting.append(a_id)
    return fitting


def _fits(manifest: dict, kinds: set[str]) -> bool:
    for raw in build_inputs(manifest):
        if not raw.required:
            continue
        # `accepts` holds manifest-kind constants (e.g. numeric-column).
        accepted_labels = {KIND_LABEL.get(k, "any") for k in raw.accepts}
        # An input that accepts "any" is always satisfiable by a real column.
        if not accepted_labels or accepted_labels == {"any"}:
            continue
        if not accepted_labels & kinds:
            return False
    return True
