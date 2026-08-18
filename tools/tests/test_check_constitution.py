"""Red-first pins for the constitutional guards.

This repository's practice — not a rule the statute states — is that each guard
is demonstrated to fail *and* to block, with the pins committed rather than shown
in a transcript, because a guard merged untested is the predecessor's
never-wired-live class. Every test here mutates a real temporary git repository;
the last group invokes the guard as a subprocess and asserts its **exit status**,
which is the only channel CI reads — the in-process pins cannot see it, and
sabotaging `main()` once left all of them green.
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
           "# D-53: x\n\n**Status:** Accepted 2026-08-18 (PR #53)\n\n## Context\n\nc.\n\n"
           "## Decision\n\n**Statute delta:** none.\n\n## Rejected\n\nnone.\n\n"
           "## Evidence\n\nnone.\n")
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
           "# D-54: later\n\n**Status:** Accepted 2026-08-19 (PR #54)\n\n## Context\n\nc.\n\n"
           "## Decision\n\n**Statute delta:** none.\n**Displaces:** [ADR-001:9]\n\n"
           "## Rejected\n\nnone.\n\n## Evidence\n\nnone.\n")
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
    assert any("dropped its citation" in f for f in out), out


# --- the guard must never go quiet -----------------------------------------

def test_undeterminable_base_exits_two(repo):
    """ADR-003's constraint: undeterminable is a failure, not a pass."""
    with pytest.raises(cc.Undetermined):
        cc.run("no-such-ref-anywhere", None)


def test_clean_tree_reports_nothing(repo):
    assert _findings(repo) == []


# --- the exit code is the only channel CI reads (statute §3) -----------------

def _install_guard(repo: Path) -> Path:
    """ROOT is derived from the guard's own path, so a subprocess must run a copy
    that lives inside the temp repo."""
    src = Path(__file__).resolve().parent.parent / "check_constitution.py"
    dst = repo / "tools" / "check_constitution.py"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


def _exit_code(repo: Path, *extra: str) -> int:
    """Invoke the guard as CI does. The pins above call run() in-process, which
    cannot see main()'s return value — sabotaging it left all of them green."""
    guard = _install_guard(repo)
    return subprocess.run(
        [sys.executable, str(guard), "--base", "base-ref", *extra],
        cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).returncode


def test_exit_code_is_one_when_findings_exist(repo):
    """RED-FIRST: findings must exit non-zero, or CI reads success."""
    p = repo / "docs/architecture/constitution.md"
    _write(p, p.read_text(encoding="utf-8") + "- **An uncited rule.** No token.\n")
    _run("git", "commit", "-aqm", "uncited", cwd=repo)
    assert _exit_code(repo) == 1


def test_exit_code_is_two_when_undeterminable(repo):
    """ADR-003's constraint, on the channel that carries it: undeterminable is
    never a pass. A guard that goes quiet prints the same line as a clean run."""
    guard = _install_guard(repo)
    r = subprocess.run(
        [sys.executable, str(guard), "--base", "no-such-ref-anywhere"],
        cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert r.returncode == 2, r.stdout


def test_exit_code_is_zero_on_a_clean_tree(repo):
    assert _exit_code(repo) == 0


# --- what the review's twelve highs bought -----------------------------------

def test_nested_rule_is_not_exempt(repo):
    """H6: 35 real rules sat behind an exemption written for continuation lines
    the statute does not contain. A nested rule is a rule."""
    p = repo / "docs/architecture/constitution.md"
    _write(p, p.read_text(encoding="utf-8") + "  - **A nested rule.** No citation at all.\n")
    _run("git", "commit", "-aqm", "nested", cwd=repo)
    out = _findings(repo, pr=54)
    assert any("does not end in a citation token" in f for f in out), out


def test_quoted_fragment_must_appear_on_its_line(repo):
    """H12: the fragment is the reader's only check on a frozen line, so an
    unverified one looks like corroboration and is worse than none."""
    p = repo / "docs/architecture/constitution.md"
    _write(p, p.read_text(encoding="utf-8")
           + '- **A rule.** Reason. [ADR-001:7 "words that are not on line 7"]\n')
    _run("git", "commit", "-aqm", "bad fragment", cwd=repo)
    out = _findings(repo)
    assert any("does not appear on that line" in f for f in out), out


def test_malformed_entry_is_caught_while_still_a_draft(repo):
    """N1: a malformed entry that lands can never be repaired — the repair is a
    diff to an accepted entry. So the skeleton is checked while it is a draft."""
    _write(repo / "docs/architecture/decisions/D-54-2026-08-19-shapeless.md",
           "garbage, no title, no status line, no sections at all\n")
    _run("git", "add", "-A", cwd=repo)
    _run("git", "commit", "-qm", "shapeless", cwd=repo)
    out = _findings(repo)
    assert any("is missing" in f and "entry-shape" in f for f in out), out


def test_deleting_a_d_cited_rule_is_caught(repo):
    """H5: deletion protection scanned ADR tokens only, so it decayed to zero on
    the forward path — every rule minted after the split cites [D-N]."""
    p = repo / "docs/architecture/constitution.md"
    _write(p, p.read_text(encoding="utf-8") + "- **A minted rule.** Reason. [D-53]\n")
    _run("git", "commit", "-aqm", "add minted", cwd=repo)
    _run("git", "branch", "-f", "base-ref", "HEAD", cwd=repo)
    _write(p, "# The constitution\n\n## 1. Identity\n\n- **A rule.** Its reason. [ADR-001:7]\n")
    _run("git", "commit", "-aqm", "delete minted", cwd=repo)
    out = _findings(repo)
    assert any("no entry declares its displacement" in f for f in out), out


def test_log_index_is_editable(repo):
    """H1: the log's index grows with every entry. Freezing it made the log's
    normal operation fail required CI with a message naming a false cause."""
    _write(repo / "docs/architecture/decisions/README.md", "# The decision log\n\n| D-53 |\n")
    _run("git", "add", "-A", cwd=repo)
    _run("git", "commit", "-qm", "index", cwd=repo)
    _write(repo / "docs/architecture/decisions/README.md",
           "# The decision log\n\n| D-53 |\n| D-54 |\n")
    _run("git", "commit", "-aqm", "index grows", cwd=repo)
    out = _findings(repo)
    assert not any("README" in f for f in out), out


def test_entry_hosted_supersession_pointer_is_seen(repo):
    """H2: entry status lines were globbed by nothing, so an entry's status line
    was a lawful place to write a supersession claim no cross-check could see."""
    p = repo / "docs/architecture/decisions/D-53-2026-08-18-log-and-statute.md"
    _write(p, p.read_text(encoding="utf-8").replace(
        "(PR #53)",
        "(PR #53) · Superseded in part by [D-99] (2026-08-20): D-53 — reversed."))
    _run("git", "commit", "-aqm", "false pointer", cwd=repo)
    out = _findings(repo)
    assert any("no such entry exists" in f for f in out), out


# --- pins for branches a sabotage sweep found unread (post-fix cycle) --------


def test_accepted_file_losing_its_status_line_is_caught(repo):
    """Reported as a SHAPE defect, never append-only: the two carry different
    remedies, and this one's remedy is 'repair before it lands'."""
    p = repo / "docs/architecture/decisions/D-53-2026-08-18-log-and-statute.md"
    _write(p, p.read_text(encoding="utf-8").replace(
        "**Status:** Accepted 2026-08-18 (PR #53)\n", ""))
    _run("git", "commit", "-aqm", "drop status", cwd=repo)
    out = _findings(repo)
    assert any("has no `**Status:**` line" in f for f in out), out


def test_status_line_rewritten_rather_than_appended_is_caught(repo):
    """Distinct from the malformed-append branch: here the accepted prefix is
    gone, so the file's own history has been rewritten, not extended."""
    p = repo / "docs/architecture/adr/ADR-001-identity.md"
    _write(p, p.read_text(encoding="utf-8").replace(
        "**Status:** Accepted 2026-08-15", "**Status:** Accepted 2026-08-16"))
    _run("git", "commit", "-aqm", "rewrite status", cwd=repo)
    out = _findings(repo)
    assert any("rewritten rather than appended" in f for f in out), out


def test_citation_to_a_nonexistent_adr_is_caught(repo):
    """Out-of-bounds and no-such-ADR are separate branches; only the first was pinned."""
    p = repo / "docs/architecture/constitution.md"
    _write(p, p.read_text(encoding="utf-8").replace("[ADR-001:7]", "[ADR-404:7]"))
    _run("git", "commit", "-aqm", "dangling adr", cwd=repo)
    out = _findings(repo)
    assert any("no such ADR" in f for f in out), out


def test_duplicate_rule_lead_in_is_caught(repo):
    """Identity must be unique or it is not identity — a second rule sharing a
    lead-in reads as an edit of the first, so the added-rule check never runs."""
    p = repo / "docs/architecture/constitution.md"
    _write(p, p.read_text(encoding="utf-8")
           + "\n## 2. Other\n\n- **A rule.** A different reason. [ADR-001:7]\n")
    _run("git", "commit", "-aqm", "duplicate lead-in", cwd=repo)
    out = _findings(repo)
    assert any("more than one rule with the lead-in" in f for f in out), out


def test_accepted_entry_is_not_re_checked_for_shape(repo):
    """The trap N1 closed, reproduced by N1's own remedy: an entry that landed
    malformed cannot be repaired, so re-checking it makes it permanently red."""
    p = repo / "docs/architecture/decisions/D-53-2026-08-18-log-and-statute.md"
    _write(p, p.read_text(encoding="utf-8").replace("## Evidence\n\nnone.\n", ""))
    _run("git", "commit", "-aqm", "base has a malformed entry", cwd=repo)
    _run("git", "branch", "-f", "base-ref", cwd=repo)
    _run("git", "commit", "-q", "--allow-empty", "-m", "later work", cwd=repo)
    out = _findings(repo)
    assert not any("Evidence" in f for f in out), out


def test_draft_entry_missing_a_section_is_caught(repo):
    """The other half of the same rule: while still a draft, shape is checked."""
    _write(repo / "docs/architecture/decisions/D-61-2026-08-19-later.md",
           "# D-61: y\n\n**Status:** Accepted 2026-08-19 (PR #61)\n\n## Context\n\nc.\n\n"
           "## Decision\n\n**Changes no operative rule.**\n\n## Rejected\n\nnone.\n")
    _run("git", "add", "-A", cwd=repo)
    _run("git", "commit", "-qm", "draft entry", cwd=repo)
    out = _findings(repo)
    assert any("Evidence" in f for f in out), out


def test_the_adr_index_is_frozen_too(repo):
    """It carries the freeze marker, so the guard must reach it — a file that
    asserts a freeze nothing enforces is worse than one that says nothing."""
    _write(repo / "docs/architecture/adr/README.md",
           f"# ADR index\n\n**Status:** Frozen 2026-08-18\n\n{MARKER}\n\nHistorical.\n")
    _run("git", "add", "-A", cwd=repo)
    _run("git", "commit", "-qm", "add index", cwd=repo)
    _run("git", "branch", "-f", "base-ref", cwd=repo)
    _write(repo / "docs/architecture/adr/README.md",
           f"# ADR index\n\n**Status:** Frozen 2026-08-18\n\n{MARKER}\n\nRewritten.\n")
    _run("git", "commit", "-aqm", "rewrite the index", cwd=repo)
    out = _findings(repo)
    assert any("changed outside" in f for f in out), out


def test_a_displacement_declared_by_another_entry_does_not_license_this_one(repo):
    """Scoped to THIS change's entry. A union over all history only grows, so a
    target displaced once would license dropping it from any rule, forever."""
    _write(repo / "docs/architecture/decisions/D-60-2026-08-19-earlier.md",
           "# D-60: y\n\n**Status:** Accepted 2026-08-19 (PR #60)\n\n## Context\n\nc.\n\n"
           "## Decision\n\n**Statute delta:** none.\n**Displaces:** [ADR-001:7]\n\n"
           "## Rejected\n\nnone.\n\n## Evidence\n\nnone.\n")
    _run("git", "add", "-A", cwd=repo)
    _run("git", "commit", "-qm", "an entry that displaces ADR-001:7", cwd=repo)
    _run("git", "branch", "-f", "base-ref", cwd=repo)

    p = repo / "docs/architecture/constitution.md"
    _write(p, p.read_text(encoding="utf-8").replace(
        "- **A rule.** Its reason. [ADR-001:7]", "- **A rule.** Its opposite. [D-60]"))
    _write(repo / "docs/architecture/decisions/D-61-2026-08-19-later.md",
           "# D-61: z\n\n**Status:** Accepted 2026-08-19 (PR #61)\n\n## Context\n\nc.\n\n"
           "## Decision\n\n**Changes no operative rule.**\n\n## Rejected\n\nnone.\n\n"
           "## Evidence\n\nnone.\n")
    _run("git", "add", "-A", cwd=repo)
    _run("git", "commit", "-qm", "migrate the citation, declaring nothing", cwd=repo)
    out = _findings(repo, 61)
    assert any("ADR-001:7" in f and "displace" in f.lower() for f in out), out
