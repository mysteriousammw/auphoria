"""Phase 12 tests: release-preparation assets (not the publish action).

Covers: version pinned to 0.1.0, the release workflow file, PR + bug issue
templates, the pilot checklist, CONTRIBUTING maintainer/succession sections,
CITATION.cff completeness (placeholders not real personal data), and the
CHANGELOG [0.1.0] entry. Publishing/tagging itself is NOT exercised.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def test_version_is_0_1_0():
    from auphoria.core.version import __version__

    assert __version__ == "0.1.0"


def test_release_workflow_exists_and_is_tag_triggered():
    wf = _read(".github/workflows/release.yml")
    assert "push:" in wf and "tags:" in wf and '"v*"' in wf
    # It should never publish without an explicit step; a draft release is the
    # prepared artifact.
    assert "draft: true" in wf
    assert "python -m build" in wf or "pip install build" in wf


def test_pr_and_bug_templates_exist():
    assert "PULL_REQUEST_TEMPLATE.md" in {
        p.name for p in (REPO_ROOT / ".github").rglob("*") if p.is_file()
    }
    bug = _read(".github/ISSUE_TEMPLATE/bug_report.md")
    assert "[bug]" in bug and "auphoria doctor" in bug


def test_pilot_checklist_has_form_and_gate():
    pilot = _read("docs/pilot/pilot-checklist.md")
    assert "what went wrong" in pilot
    assert "3–5" in pilot or "3-5" in pilot
    assert "blocking" in pilot.lower()


def test_contributing_has_maintainer_and_succession():
    c = _read("CONTRIBUTING.md")
    assert "## Maintainers" in c and "## Succession" in c
    assert "Handover checklist" in c or "handover checklist" in c.lower()


def test_citation_has_people_only_authors_with_confirm_placeholders():
    cff = _read("CITATION.cff")
    # Personal detail fields exist but are NOT filled with a real name/ORCID;
    # the sole active author is the project lead and the other four people stay
    # in a commented block under [CONFIRM ROLE] (AI tools are never authors).
    assert "Abdul Momin Muhammad Wisal" in cff or "Wisal" in cff
    assert "ammw@aup.edu.pk" in cff
    assert "CONFIRM ROLE" in cff
    assert "https://github.com/mysteriousammw/auphoria" in cff
    assert 'version: "0.1.0"' in cff


def test_changelog_has_0_1_0_entry():
    cl = _read("CHANGELOG.md")
    assert "## [0.1.0] - 2026-" in cl
    assert "[0.1.0]: https://github.com/mysteriousammw/auphoria" in cl


def test_publish_checklist_tracks_shipped_release_stack():
    pc = _read("docs/PUBLISH_CHECKLIST.md")
    for token in ("set_repo_url.py", "build_docs.sh", "pilot-checklist.md",
                  "release.yml", "mkdocs.yml", "CITATION.cff"):
        assert token in pc, f"PUBLISH_CHECKLIST no longer mentions {token}"
