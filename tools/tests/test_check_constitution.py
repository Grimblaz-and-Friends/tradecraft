"""Red-first pins for the constitutional guards.

Statute §12 requires each guard to be demonstrated to fail *and* to block, with
the pins committed rather than shown in a transcript — a guard merged untested
is the predecessor's never-wired-live class. Every test here mutates a real
temporary git repository and asserts the guard's exit status, so a check that
stops reading its input, or that goes quiet, fails the suite.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import check_constitution as cc  # noqa: E402

MARKER = "**Frozen 2026-08-18 by [D-53].** Historical record; operative rules live in the statute. Only status-line supersession pointers may be appended."
POINTER = (
    " · Superseded in part by [D-53] (2026-08-18): ADR-001:9 — the rule moves to the statute."
)


def _run(*args: str, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """A git repo whose merge base already has a frozen ADR and an accepted entry."""
    r = tmp_path / "r"
    r.mkdir()
    _run("git", "init", "-q", "-b", "main", cwd=r)
    _run("git", "config", "user.email", "t@t", cwd=r)
    _run("git", "config", "user.name", "t", cwd=r)

    _write(r / "docs/architecture/adr/ADR-001-identity.md",
           f"# ADR-001\n\n**Status:** Accepted 2026-08-15\n\n{MARKER}\n\n## Decision\n\n"
           "Some frozen rule.\n")
    _write(r / "docs/architecture/decisions/D-53-2026-08-18-log-and-statute.md",
           "# D-53: x\n\n**Status:** Accepted 2026-08-18 (PR #53)\n\n## Decision\n\n"
           "**Statute delta:** none.\n")
    _write(r / "docs/architecture/constitution.md",
           "# The constitution\n\n## 1. Identity\n\n- **A rule.** Its reason. [ADR-001:7]\n")
    _run("git", "add", "-A", cwd=r)
    _run("git", "commit", "-qm", "base", cwd=r)
    _run("git", "branch", "base-ref", cwd=r)

    monkeypatch.setattr(cc, "ROOT", r)
    return r


def _findings(repo: Path, pr: int | None = None) -> list[str]:
    return cc.run("base-ref", pr)


# --- append-only ------------------------------------------------------------

def test_frozen_adr_body_edit_is_caught(repo):
    """RED-FIRST: editing a frozen ADR outside its status line must fail."""
    p = repo / "docs/architecture/adr/ADR-001-identity.md"
    _write(p, p.read_text(encoding="utf-8").replace("Some frozen rule.", "Rewritten rule."))
    _run("git", "commit", "-aqm", "edit", cwd=repo)
    out = _findings(repo)
    assert any("changed outside" in f for f in out), out


def test_frozen_adr_marker_drop_is_caught(repo):
    """A change that also removes the freeze marker is still judged against the base."""
    p = repo / "docs/architecture/adr/ADR-001-identity.md"
    _write(p, p.read_text(encoding="utf-8").replace(MARKER, "").replace("Some frozen rule.", "X."))
    _run("git", "commit", "-aqm", "unfreeze", cwd=repo)
    out = _findings(repo)
    assert any("changed outside" in f for f in out), out


def test_lawful_amendment_passes(repo):
    """The shape a real amendment takes: a NEW draft entry plus a lawful pointer.

    The accepted entry is untouched. Editing it to add its own Displaces field
    would trip append-only — correctly, and that is pinned separately below.
    """
    p = repo / "docs/architecture/adr/ADR-001-identity.md"
    _write(p, p.read_text(encoding="utf-8").replace(
        "**Status:** Accepted 2026-08-15",
        "**Status:** Accepted 2026-08-15"
        " · Superseded in part by [D-54] (2026-08-19): ADR-001:9 — moved to the statute."))
    _write(repo / "docs/architecture/decisions/D-54-2026-08-19-later.md",
           "# D-54: later\n\n**Status:** Accepted 2026-08-19 (PR #54)\n\n## Decision\n\n"
           "**Statute delta:** none.\n**Displaces:** [ADR-001:9]\n")
    _run("git", "add", "-A", cwd=repo)
    _run("git", "commit", "-qm", "lawful amendment", cwd=repo)
    out = _findings(repo)
    assert out == [], out


def test_malformed_status_append_is_caught(repo):
    """A free-prose append is not the fixed pointer form."""
    p = repo / "docs/architecture/adr/ADR-001-identity.md"
    _write(p, p.read_text(encoding="utf-8").replace(
        "**Status:** Accepted 2026-08-15",
        "**Status:** Accepted 2026-08-15 · Withdrawn, ignore this ADR"))
    _run("git", "commit", "-aqm", "bad append", cwd=repo)
    out = _findings(repo)
    assert any("malformed" in f for f in out), out


def test_accepted_entry_edit_is_caught(repo):
    """An accepted entry is immutable except status-line appends."""
    p = repo / "docs/architecture/decisions/D-53-2026-08-18-log-and-statute.md"
    _write(p, p.read_text(encoding="utf-8").replace("**Statute delta:** none.", "Rewritten."))
    _run("git", "commit", "-aqm", "edit entry", cwd=repo)
    out = _findings(repo)
    assert any("changed outside" in f for f in out), out


def test_accepted_entry_deletion_is_caught(repo):
    """Reversal is by superseding entry, never by removal."""
    p = repo / "docs/architecture/decisions/D-53-2026-08-18-log-and-statute.md"
    p.unlink()
    _run("git", "commit", "-aqm", "delete entry", cwd=repo)
    out = _findings(repo)
    assert any("deleted at head" in f for f in out), out


def test_misnamed_entry_is_caught(repo):
    """DF2's class: a filename convention assigned to no guard is a permanent typo."""
    _write(repo / "docs/architecture/decisions/D53-bad-name.md", "# D-53\n")
    _run("git", "add", "-A", cwd=repo)
    _run("git", "commit", "-qm", "misnamed", cwd=repo)
    out = _findings(repo)
    assert any("not a lawful entry filename" in f for f in out), out


# --- citation ---------------------------------------------------------------

def test_rule_unit_without_citation_is_caught(repo):
    p = repo / "docs/architecture/constitution.md"
    _write(p, p.read_text(encoding="utf-8") + "- **An uncited rule.** No token here.\n")
    _run("git", "commit", "-aqm", "uncited", cwd=repo)
    out = _findings(repo)
    assert any("does not end in a citation token" in f for f in out), out


def test_non_rule_content_in_statute_is_caught(repo):
    """PF16's class: content outside the shape exits the citation regime silently."""
    p = repo / "docs/architecture/constitution.md"
    _write(p, p.read_text(encoding="utf-8") + "\nA loose paragraph of prose.\n")
    _run("git", "commit", "-aqm", "loose prose", cwd=repo)
    out = _findings(repo)
    assert any("neither a section heading nor a rule unit" in f for f in out), out


def test_out_of_bounds_adr_citation_is_caught(repo):
    p = repo / "docs/architecture/constitution.md"
    _write(p, p.read_text(encoding="utf-8") + "- **A rule.** Reason. [ADR-001:9999]\n")
    _run("git", "commit", "-aqm", "oob", cwd=repo)
    out = _findings(repo)
    assert any("out of bounds" in f for f in out), out


def test_dangling_d_token_is_caught(repo):
    """PF1/MF12's class: a dangling [D-N] anywhere in a constitutional file."""
    p = repo / "docs/architecture/constitution.md"
    _write(p, p.read_text(encoding="utf-8") + "- **A rule.** Reason. [D-99]\n")
    _run("git", "commit", "-aqm", "dangling", cwd=repo)
    out = _findings(repo)
    assert any("no entry file for it" in f for f in out), out


def test_added_rule_must_cite_this_pr(repo):
    """QF1's class: a rule added in the diff arrives with its own decision."""
    p = repo / "docs/architecture/constitution.md"
    _write(p, p.read_text(encoding="utf-8") + "- **A new rule.** Reason. [ADR-001:7]\n")
    _run("git", "commit", "-aqm", "added rule", cwd=repo)
    out = _findings(repo, pr=53)
    assert any("does not cite [D-53]" in f for f in out), out


def test_declared_displacement_without_pointer_is_caught(repo):
    """Cross-check (i): a Displaces target with no matching pointer."""
    p = repo / "docs/architecture/decisions/D-53-2026-08-18-log-and-statute.md"
    _write(p, p.read_text(encoding="utf-8") + "**Displaces:** [ADR-001:9]\n")
    _run("git", "commit", "-aqm", "undeclared", cwd=repo)
    out = _findings(repo)
    assert any("carries no matching supersession pointer" in f for f in out), out


def test_pointer_without_declaration_is_caught(repo):
    """Cross-check (ii): DPF3's class — the reverse direction."""
    p = repo / "docs/architecture/adr/ADR-001-identity.md"
    _write(p, p.read_text(encoding="utf-8").replace(
        "**Status:** Accepted 2026-08-15", "**Status:** Accepted 2026-08-15" + POINTER))
    _run("git", "commit", "-aqm", "pointer only", cwd=repo)
    out = _findings(repo)
    assert any("does not list in Displaces" in f for f in out), out


def test_silently_dropped_adr_citation_is_caught(repo):
    """Cross-check (iii)/QF2: a citation present at base and gone at head."""
    p = repo / "docs/architecture/constitution.md"
    _write(p, "# The constitution\n\n## 1. Identity\n\n- **A rule.** Its reason. [D-53]\n")
    _run("git", "commit", "-aqm", "dropped cite", cwd=repo)
    out = _findings(repo)
    assert any("no entry declaring it displaced" in f for f in out), out


# --- the guard must never go quiet -----------------------------------------

def test_undeterminable_base_exits_two(repo):
    """ADR-003's constraint: undeterminable is a failure, not a pass."""
    with pytest.raises(cc.Undetermined):
        cc.run("no-such-ref-anywhere", None)


def test_clean_tree_reports_nothing(repo):
    assert _findings(repo) == []
