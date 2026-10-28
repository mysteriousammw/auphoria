#!/usr/bin/env bash
# Build the MkDocs Material docs site and fail if there are any warnings
# (the Phase 11 acceptance criterion: "docs build without warnings").
#
# The Material theme prints a harmless upstream "end of life" banner to stderr;
# NO_MKDOCS_2_WARNING=1 silences it so it never counts as a build warning.
#
# Usage:
#   scripts/build_docs.sh            # build into site/
#   scripts/build_docs.sh --strict   # also treat stray nav as a warning
set -euo pipefail
cd "$(dirname "$0")/.."

export NO_MKDOCS_2_WARNING=1

strict=""
if [[ "${1:-}" == "--strict" ]]; then
  strict="--strict"
fi

log="$(mktemp)"
if python -m mkdocs build $strict >"$log" 2>&1; then
  if grep -qiE "WARNING|ERROR" "$log"; then
    echo "Docs built but reported warnings:" >&2
    grep -iE "WARNING|ERROR" "$log" >&2
    rm -f "$log"
    exit 1
  fi
  echo "Docs built cleanly (no warnings)."
  rm -f "$log"
  exit 0
else
  echo "Docs build FAILED:" >&2
  cat "$log" >&2
  rm -f "$log"
  exit 1
fi