#!/usr/bin/env python3
"""Generate the per-analysis docs pages (docs_site/analyses/<id>.md).

Reads each analysis's manifest.yaml (via the registry) and writes one plain
MkDocs page per analysis: what it does, what you need, options, assumptions,
limitations, known issues, the example command, and which discipline pack (if
any) it belongs to.

Usage:
    python scripts/gen_analysis_docs.py            # write docs_site/analyses/
    python scripts/gen_analysis_docs.py --check    # verify only, no write
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from auphoria.core import registry

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "docs_site" / "analyses"


def _page_for(info) -> str:
    m = info.manifest
    idv = info.id
    out: list[str] = []
    out.append(f"# {info.name}\n")
    out.append(f"`{idv}` · maturity: **{m.get('maturity', 'experimental')}**\n")
    packs = m.get("pack") or []
    if packs:
        out.append(f"Discipline packs: {', '.join(f'`{p}`' for p in packs)}  \n")
    if m.get("reference"):
        out.append(f"Validation reference: {m['reference']}  \n")
    out.append("\n## What it does\n")
    out.append((m.get("description") or info.description or "No description.").strip() + "\n")

    inputs = m.get("inputs") or []
    if inputs:
        out.append("## What you need\n")
        for raw in inputs:
            req = "required" if raw.get("required") else "optional"
            out.append(f"- **{raw.get('name')}** ({raw.get('kind')}, {req}): "
                       f"{raw.get('description', '')}")
        out.append("")

    params = m.get("parameters") or []
    if params:
        out.append("## Options\n")
        for raw in params:
            out.append(f"- `{raw.get('name')}` (default {raw.get('default')}): "
                       f"{raw.get('description', '')}")
        out.append("")

    outputs = m.get("outputs") or []
    if outputs:
        out.append("## What you get out\n")
        for o in outputs:
            out.append(f"- {o}")
        out.append("")

    assumptions = m.get("assumptions") or []
    if assumptions:
        out.append("## Assumptions\n")
        for a in assumptions:
            out.append(f"- {a}")
        out.append("")

    limitations = m.get("limitations") or []
    if limitations:
        out.append("## Limitations\n")
        for l_ in limitations:
            out.append(f"- {l_}")
        out.append("")

    known = m.get("known_issues") or []
    if known:
        out.append("## Known issues\n")
        for k in known:
            out.append(f"- {k}")
        out.append("")

    out.append("## Run it\n")
    example = _example(m)
    out.append("```bash\n" + example + "\n```\n")
    return "\n".join(out)


def _example(m: dict) -> str:
    cmd = ["auphoria", "run", "--data", "YOURFILE.csv", "--analysis", str(m["id"])]
    added = set()
    for raw in m.get("inputs") or []:
        name = raw.get("name")
        if not raw.get("required") or name in added:
            continue
        added.add(name)
        if name in ("outcome", "group"):
            cmd.append(f"--{name} <{name}>")
        else:
            cmd.append(f"--extra {name}=<{name}>")
    return " ".join(cmd)


def _write_all() -> list[Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for info in sorted(registry.discover().values(), key=lambda i: i.id):
        p = OUT_DIR / f"{info.id}.md"
        p.write_text(_page_for(info), encoding="utf-8")
        written.append(p)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify only, no write")
    args = parser.parse_args(argv)

    if args.check:
        missing = []
        for info in sorted(registry.discover().values(), key=lambda i: i.id):
            p = OUT_DIR / f"{info.id}.md"
            if not p.exists() or p.read_text(encoding="utf-8") != _page_for(info):
                missing.append(info.id)
        if missing:
            print(f"STALE analysis docs for: {', '.join(missing)}. Re-run the generator.",
                  file=sys.stderr)
            return 1
        print(f"OK: {len(registry.discover())} analysis pages are current.")
        return 0

    written = _write_all()
    print(f"Wrote {len(written)} analysis pages to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
