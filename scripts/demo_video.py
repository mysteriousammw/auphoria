#!/usr/bin/env python3
"""Run the exact steps of the AUPHORIA 3-minute demo, in order.

This drives the real tool through the same steps shown in the demo video
(see scripts/demo_video_script.md for the narration), so you can record the
screen while it runs, or just verify the demo works end to end.

The steps are non-interactive: it uses `auphoria run` one-liners plus opens
the newest report.html in the browser at the end. It creates a fresh results
folder per step and prints a short "what to say" cue line under each one.

Usage:
    python scripts/demo_video.py            # run all steps (safe, offline data)
    python scripts/demo_video.py --no-open  # don't open the browser at the end
    python scripts/demo_video.py --fresh    # remove ~/AUPHORIA_results first

Requires AUPHORIA installed and the sample datasets (they ship with the package).
"""

from __future__ import annotations

import subprocess
import sys
import webbrowser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SAMPLE = REPO / "src" / "auphoria" / "sample_data" / "data"
RESULTS = Path(
    __import__("os").environ.get("AUPHORIA_RESULTS_ROOT", "")
    or (Path.home() / "AUPHORIA_results")
)

PY = sys.executable

STEPS: list[tuple[str, str, list[str]]] = [
    # (cue line, analysis label, `auphoria run` args after "run")
    (
        "Step 1 — the tool: show doctor + list.",
        "doctor/list",
        [],
    ),
    (
        "Step 2 — a guided one-liner t-test on survey.csv (score by group).",
        "ttest",
        ["run", "--data", str(SAMPLE / "survey.csv"), "--analysis", "ttest",
         "--outcome", "score", "--group", "group"],
    ),
    (
        "Step 3 — survival: Kaplan-Meier on survival.csv (group = treatment).",
        "kaplan-meier",
        ["run", "--data", str(SAMPLE / "survival.csv"), "--analysis", "kaplan-meier",
         "--outcome", "time_months", "--group", "group", "--extra", "event=event"],
    ),
    (
        "Step 4 — an advanced analysis: ML classification on features.csv.",
        "ml-classification-eval",
        ["run", "--data", str(SAMPLE / "features.csv"), "--analysis",
         "ml-classification-eval", "--group", "label"],
    ),
]


def _newest_report() -> Path | None:
    if not RESULTS.is_dir():
        return None
    runs = [p for p in RESULTS.iterdir() if p.is_dir()]
    return max(runs, key=lambda p: p.stat().st_mtime) if runs else None


def main() -> int:
    no_open = "--no-open" in sys.argv
    fresh = "--fresh" in sys.argv
    if fresh and RESULTS.is_dir():
        import shutil

        shutil.rmtree(RESULTS)

    print("=" * 68)
    print("AUPHORIA 3-minute demo")
    print(f"results root: {RESULTS}")
    print("=" * 68)

    for cue, label, args in STEPS:
        print("\n- " + cue)
        if label == "doctor/list":
            for cmd in (["doctor"], ["list"]):
                r = subprocess.run([PY, "-m", "auphoria", *cmd])
                if r.returncode != 0:
                    print(f"  !! {cmd[0]} failed", file=sys.stderr)
                    return 1
            continue
        # run --data <path> --analysis <id> ...
        r = subprocess.run([PY, "-m", "auphoria", *args])
        if r.returncode != 0:
            print(f"  !! analysis '{label}' failed", file=sys.stderr)
            return 1

    newest = _newest_report()
    if newest:
        report = newest / "report.html"
        print(f"\nNewest results folder: {newest}")
        if report.exists():
            print(f"Open {report} to show the report as in the video.")
            if not no_open:
                webbrowser.open(str(report))
    else:
        print("\nNo results folder was created (unexpected).")

    print("\nDone. See scripts/demo_video_script.md for the narration.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
