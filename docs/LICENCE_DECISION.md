# Licence decision — for the maintainer

**DECIDED: MIT** (chosen by the maintainer on 2026-10-29). The `LICENSE` file,
the `pyproject.toml` `license` metadata + `License :: OSI Approved :: MIT
License` classifier, and `CITATION.cff`'s `license: "MIT"` field are all set.

Why MIT: AUPHORIA is a teaching/research tool whose entire dependency stack is
permissive (NumPy/pandas/SciPy/Matplotlib/scikit-learn/statsmodels are BSD;
PyYAML/Typer are MIT). MIT is the simplest, most popular permissive licence,
fully compatible with those dependencies, and maximally reusable by students
and downstream users. It carries no patent grant, which is a reasonable
trade-off for a non-commercial academic tool.

The original options compared below are kept for reference.

---

## Permissive (no copyleft: anyone can reuse, including in proprietary work)

| Licence | One-line trade-off |
|---|---|
| **MIT** | Simplest and most popular; permissive; one caveat — no patent grant. |
| **BSD-3-Clause** | Permissive like MIT plus a "no endorsement" clause protecting your name; the Flask/Django-adjacent default. |
| **BSD-2-Clause** | Like BSD-3 but drops the endorsement clause — shorter, a touch less protective. |
| **Apache-2.0** | Permissive **with an explicit patent grant** — the strongest permissive option for a project with code; recommended if you care about contributors' patents. |

## Copyleft (derivatives must stay open)

| Licence | One-line trade-off |
|---|---|
| **GPL-3.0** | Derivatives (including "contacted works" over a network) must stay GPL — the strongest "stay open" guarantee, but scares off commercial embedding. |
| **LGPL-3.0** | Middle ground: libraries can be linked from proprietary code but modifications to the library itself stay open. |
| **AGPL-3.0** | GPL-3.0 plus a network-use clause — appropriate only if hosted as a service (AUPHORIA is not; it runs locally/offline, so AGPL adds little). |

## A note relevant to AUPHORIA specifically

AUPHORIA realistically **depends on** permissively-licensed scientific Python
libraries (NumPy, pandas, SciPy, scikit-learn, statsmodels, matplotlib — BSD;
PyYAML, typer — MIT). Picking a permissive licence for AUPHORIA itself keeps
everything compatible with a permissive downstream audience with none of the
friction of copyleft. A copyleft licence would still be fine legally (the
dependencies are BSD/MIT and do not impose copyleft on us), but it would send
a different message about reuse.

## What to do when you choose

1. Add the full licence text as `LICENSE` (and optionally `LICENSES.md`).
2. Set `license` metadata in `pyproject.toml` and add the matching
   `License ::` classifier.
3. Set the `license` field in `CITATION.cff`.

_Recommendation:_ **MIT** for simplicity and reach, or **BSD-3-Clause** if you
also want the endorsement clause. Both are one file and fully compatible with
the AUPHORIA ecosystem.