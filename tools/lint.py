#!/usr/bin/env python3
"""tradecraft repository lint.

Checks:

 1. zone wall: shipped files cannot cite repo-only paths, and shipped prose
    cannot use a decision marker or repo-only path as a behaviour's reason.
 2. harness tokens: live calling contracts use no runtime-only root token.
 3. charter cell: the charter exists, has a body and has no depth files.
 4. cell frontmatter: every cell has parseable bounded name and description.
 5. pointer graph: named cell dependencies exist, stay lawful and are acyclic.
 6. cell references: cell names and relative reference paths resolve.
 7. depth index: every cell depth file is named and every named file exists.
 8. retired.
 9. doctrine citations: decision markers in repository doctrine resolve.
10. doctrine references: repository paths in repository doctrine resolve.
11. doctrine: AGENTS.md and CLAUDE.md keep their required pointer shape.
12. retired.
13. retired.
14. decision index: each entry and index row has the other.
15. entry references: frozen and editable decision references resolve, are
    pinned to their landing commit or have a recorded retirement reason.
16. emitted ASCII: Python output literals are safe on Windows text streams.
17. docstring not piped: argparse does not emit an unchecked docstring.
18. stdio wired: executable Python mains configure UTF-8 before other work.
19. retired.
20. marketplace source: the installable plugin source remains exactly `./`.
21. subprocess streams: launches redirect no standard streams or all three.
22. docstring control characters: compiled docstrings contain no unsafe control.
23. hollow code span: inline code spans contain visible content.
24. committed carriage return: committed text has no lone carriage returns.
25. body strip: modules reuse the authoring engine's frontmatter parser.
26. retired.
27. retired.
28. retired.
29. retired.

Slots stay numbered because frozen decisions cite them. Checks 2, 16, 17, 18
and 21 are implemented in tools/substrate_lint.py and imported here so the
repository has one predicate for each substrate rule.

All shipped files are scanned regardless of extension; binary content is
skipped. Run `python tools/lint.py` from any directory. A raised check becomes
a finding and the remaining checks still run.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import subprocess
import sys
import traceback
import unicodedata
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent

# Shared with the shipped zone, which is the lawful direction: repo-only
# code may import shipped code. Resolved from this file rather than the
# working directory, so the script runs from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from winio import utf8_stdio  # noqa: E402

# The substrate predicates live beside this repository's wrapper. The wrapper
# adds the one repository-specific input: its live calling-contract population.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from substrate_lint import (  # noqa: E402
    HARNESS_TOKENS,
    _git_ignored,
    _iter_files,
    _python_files,
    _read_text,
    check_docstring_not_piped,
    check_emitted_ascii,
    check_stdio_wired,
    check_subprocess_streams,
    check_harness_tokens as _check_harness_tokens,
    reset_ignored_memo,
)

SHIPPED_DIRS = (
    "skills", "lib", "commands", "agents", "hooks", ".claude-plugin",
)
REPO_ONLY_NAMES = {"docs", "tools", ".github"}

SHIPPED_CELLS = "skills"
REPO_CELLS = "docs/cells"
CELL_SOURCES = (SHIPPED_CELLS, REPO_CELLS)
CELL_FILE = "SKILL.md"


def names_under(root: Path, source: str) -> list[str]:
    """Every cell under one source directory, sorted."""
    directory = root / source
    if not directory.is_dir():
        return []
    return sorted(
        path.name for path in directory.iterdir()
        if (path / CELL_FILE).is_file()
    )


def cell_sources(root: Path) -> dict[str, str]:
    """Every cell mapped to the first source that owns its name."""
    found: dict[str, str] = {}
    for source in CELL_SOURCES:
        for name in names_under(root, source):
            found.setdefault(name, source)
    return dict(sorted(found.items()))


def check_harness_tokens(root: Path) -> list[str]:
    """Apply the shipped token predicate to this repository's live contracts."""
    roots = [root / dirname for dirname in SHIPPED_DIRS]
    roots.append(root / REPO_CELLS)
    return _check_harness_tokens(root, roots)

CHARTER = "skills/charter/SKILL.md"
# Cell metadata is loaded before its body, so malformed or unbounded fields
# can make a cell undiscoverable or spend every session's context.
CELL_FIELD_MAX_CHARS = {"name": 64, "description": 700}
CHARTER_IMPORT = f"@{CHARTER}"
POINTER_BUDGET_CHARS = 500

# The one cell a pointer to which costs nothing, and so the one cell that is
# not a node in the graph below. Self-containment existed to stop loading cost
# and multi-site drift; neither applies here. The charter is always-on in every
# session by construction -- imported by this repository's AGENTS.md and loaded
# by an adopter's repository instruction -- so a cell citing it points at prose
# the reader has already loaded, and a citation cannot fall out of agreement
# the way a second copy can.
#
# **What this constant now means, and what it stopped meaning.** It was the
# single exemption from a ban on cells naming each other, and the ban is gone:
# a cell may name the one cell owning a rule it needs, and what is refused is a
# circle. So the charter is no longer an exception to a rule other cells obey.
# It is the one target whose edge is dropped before the graph is built, for
# the two reasons `cell_pointer_graph`'s docstring gives and this does not
# repeat -- one argument at four sites was a review finding against the change
# that wrote them. [#404] [PR #437 review, M16]
CHARTER_CELL = "charter"

ROOTED_ZONE = re.compile(r"(docs|tools|\.github)[\\/]", re.IGNORECASE)
DECISION_MARKER = re.compile(r"\[D-[0-9]+\]")
ROOTED_SKILL = re.compile(r"skills[\\/]([\w-]+)[\\/]", re.IGNORECASE)
# The same reference in the repo-only tree, by path. The name form is now a
# lawful pointer and the path form is not, for the reason check 5's docstring
# gives: a path does not survive installation where a name does. This regex is
# what makes that hold in the repo-only tree as well as the shipped one.
# Written from the generator's constant so a moved source directory moves this
# with it. [#260]
ROOTED_REPO_CELL = re.compile(
    re.escape(REPO_CELLS).replace("/", r"[\\/]") + r"[\\/]([\w-]+)[\\/]",
    re.IGNORECASE,
)
# The name form of a cell reference: `engagement` cell. A skill is reached by
# invoking it by name, not by opening a file, so this -- not a path -- is the
# form the prose uses; defining it is also what makes name-form coupling
# checkable, which it was not while any phrasing counted.
CELL_REF = re.compile(r"`([a-z][a-z0-9-]*)`\s+[Cc]ells?\b")
# The same reference with a line break where its space was. A reflow is a
# formatting edit nobody inspects, and without this it silently removes a
# reference from both the coupling check and the existence check -- observed
# under review, by reflowing one charter reference and watching the rename
# probe drop from three findings to two. Catching it enlarges nothing: it is
# the prescribed spelling, wrapped.
CELL_REF_TAIL = re.compile(r"`([a-z][a-z0-9-]*)`\Z")
CELL_REF_HEAD = re.compile(r"\A[Cc]ells?\b")
# A pointer from a cell into its own depth. Resolved against the directory of
# the file naming it, the same rule a script's calling contract follows.
# **Both separators, because a backslash is what a Windows session writing the
# path from its own shell produces**, and matching only the forward form made
# `references\x.md` name a file that need not exist while the guard stayed
# green -- the one polarity nothing here tested. RELATIVE_MD_REF beside it
# already accepts both, so the narrow form was a divergence rather than a
# choice. The separator is normalised at the point of resolution below, since
# `Path` on a POSIX runtime does not read a backslash as one. [#337]
REFERENCES_REF = re.compile(r"(references[\\/][\w.-]+\.md)")
# The same pointer written relatively, which is the only form a cell's depth
# can use to reach its sibling depth: the bare form above would resolve to
# references/references/x.md from inside references/. Anchored at `.md` rather
# than filtered afterwards, because RELATIVE_REF's trailing class swallows the
# full stop that ends a sentence -- `../references/x.md.` -- and a suffix test
# on that text answers "not markdown" for a pointer that plainly is. Its head
# is RELATIVE_REF's, so the two agree on where a relative reference starts.
RELATIVE_MD_REF = re.compile(
    r"(?<![\w.\\/-])(?:\.\.?[\\/])+[\w.][\w.\\/-]*\.md", re.IGNORECASE
)
# The first segment may itself be dot-leading (`.github`), so the class after
# the prefix admits a dot. Requiring a word character there let every relative
# form of `.github/` through while catching `docs/` and `tools/` -- the one
# repo-only name starting with a dot was the one the docstring above lied about.
# Anchored at a token boundary: a `../` run preceded by a path character is
# the tail of a longer token (`assets/../../docs/x.md`), whose WHOLE path is
# what resolves -- matching the suffix alone resolved it from the wrong base
# and reported a repo-only hit for a path that lands inside the skill. Shared
# with check_sideways_deps, so the same false positive reached both guards.
RELATIVE_REF = re.compile(r"(?<![\w.\\/-])(?:\.\.?[\\/])+[\w.][\w.\\/\\-]*")
REL_PREFIX_TAIL = re.compile(r"(?:\.\.?[\\/])+$")

# A decision entry's references. Markdown links claim to resolve outright;
# backticked paths are the form entries actually use most, and are what PR #104
# and PR #132 stranded. An optional title is admitted in the link form, and
# either separator in the path form -- every other pattern in this file accepts
# `[\/]`, and the one that did not was the newest.
ENTRY_LINK = re.compile(r"""\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+["'(][^)]*)?\)""")
ENTRY_PATH = re.compile(r"`([\w.-]+(?:[\\/][\w.-]+)+(?::\d+)?)`")

# What makes a slash-joined token a path claim rather than ordinary prose. A
# content filter cannot tell `A/B` -- this repo's own word for its spike
# pattern -- from `docs/x.md`, so the test is shape: a known extension, or a
# first segment that is a root this repo declares. Without it the guard fails
# lawful work, which is as bad as passing unlawful work, and the only escape is
# to write the reference less precisely.
#
# Declared, not merely present: `lib`, `commands` and `agents` are shipped-zone
# roots even when empty. Runtime-managed `.claude` and `.agents` directories
# are excluded because their local contents are not repository reference roots.
REPO_ROOTS = frozenset(SHIPPED_DIRS) | {
    "tools", "docs", ".github", ".", "..",
}
REF_EXTENSIONS = frozenset({
    ".md", ".py", ".yml", ".yaml", ".json", ".jsonl", ".txt", ".toml", ".cfg",
    ".ini", ".sh", ".ps1",
})

# A pin names the commit a reference shipped at, so no later move can falsify
# it. The backticks carry the whole discrimination: this repo cites GitHub
# comment ids constantly and `at 5380976787` is the live example, which is
# unbackticked. Requiring a hex letter as well would additionally refuse an
# all-decimal short sha -- about one prefix in twenty-seven -- and the author
# who wrote it would get a silently inert pin.
PINNED_REF = re.compile(r"\bat\s+`[0-9a-fA-F]{7,40}`")

# References dead when this guard landed, keyed by the line that carries them
# because one entry can hold both a repairable and an unrepairable occurrence
# of the same path -- D-119 did, at :19 and :66, and a key without the line
# could not say so. Each row states why it is here.
#
# THIS SET MAY ONLY SHRINK, and the guard enforces that rather than asserting
# it: a row whose reference has come back to life is reported as stale and must
# be removed. It is a baseline, not an exemption list -- a reference added here
# is a dead reference nobody had to repair, which is the failure this guard
# exists to make impossible.
BASELINE_UNRESOLVABLE = {
    # Each states where the file WAS when its entry was written, so repointing
    # falsifies the sentence rather than repairing it.
    ("D-80-2026-08-19-spikes.md", 15, "skills/authoring/references/spikes.md"):
        "states where D-80 itself placed the file",
    ("D-102-2026-08-21-merged-list-is-an-index.md", 50,
     "skills/authoring/references/spikes.md"):
        "cites the path as evidence a references/ directory existed",
    ("D-104-2026-08-22-engagement-cell.md", 36, "engagement/references/spikes.md"):
        "states where PR #104 moved the file",
    ("D-132-2026-08-23-spikes-graduate.md", 19, "engagement/references/spikes.md"):
        "states where the file was before PR #132 moved it",
    # D-119:19 quotes "a mechanism nobody has executed", a phrase PR #132
    # deleted while moving the file, so repointing would leave the sentence
    # quoting words its target does not contain. Line 66 of the same entry was
    # a see-also whose characterization survives the move, and was repointed.
    ("D-119-2026-08-23-cost-estimate-outside-the-artifact.md", 19,
     "skills/engagement/references/spikes.md"):
        "quotes a phrase PR #132 deleted while moving the target",
    # Renamed by PR #74's reset, not deleted -- but D-53:15 calls the target
    # the "always-current statute", which repointing to an -archived path
    # would falsify.
    ("D-53-2026-08-18-log-and-statute.md", 15, "docs/architecture/constitution.md"):
        "calls the target the always-current statute; renamed to -archived",
    ("D-53-2026-08-18-log-and-statute.md", 75, "docs/architecture/evidence.md"):
        "a locator whose target PR #74 renamed; nothing sends a reader into the pre-reset archive to act",
    # Deleted outright by the same reset. D-53 correctly records what it built.
    ("D-53-2026-08-18-log-and-statute.md", 64, "tools/check_constitution.py"):
        "target deleted by PR #74; the entry records what it built",
    ("D-53-2026-08-18-log-and-statute.md", 64,
     "tools/tests/test_check_constitution.py"):
        "target deleted by PR #74; the entry records what it built",
    # D-53 through D-69 are the pre-reset frozen archive, and nothing directs a
    # reader into it to act -- the reason this pair was dropped from the carve
    # the owner had approved.
    ("D-69-2026-08-18-trial-instrument-and-exception.md", 19, "../evidence.md"):
        "nothing sends a reader into the pre-reset archive to act; PR #74 renamed the target",
    ("D-69-2026-08-18-trial-instrument-and-exception.md", 94, "../evidence.md"):
        "nothing sends a reader into the pre-reset archive to act; PR #74 renamed the target",
    # Never in this repository: a path on the owner's own machine. D-99:37's
    # `.claude/agents` was a row here too and is deliberately gone: `.claude`
    # left REPO_ROOTS, so the token no longer reads as a path claim at all --
    # a recorded shrink, not a silent loss of coverage.
    ("D-90-2026-08-20-dispatch-contract.md", 25,
     "Documents/Design/review-dispatch-overhead-measurement.md"):
        "never in this repository; the predecessor's local path",
}

# The fourth lawful disposition, and the one the rule was missing. A reference
# can become unrepairable AFTER this guard landed: its target is retired rather
# than moved, or a change moves the target and rewrites the text the entry
# quotes. Neither has a repoint, and the entry is frozen, so without this a
# required check reds with no compliant answer -- a guard blocking lawful work.
#
# Unlike the baseline above this may grow, because that is what makes the
# deadlock lawful. It is not an open exemption list: every row states its own
# reason, the reason is enforced non-empty, and a row is one visible line of
# diff on the pull request that created the situation.
UNREPAIRABLE_AFTER_LANDING: dict[tuple[str, int, str], str] = {
    ("D-156-2026-08-24-installable-plugin-and-shipped-charter.md", 43,
     "hooks/README.md"):
        "target retired by PR #222 with the lifecycle-hook fallback it documented",
    ("D-186-2026-08-25-windows-text-mode-defaults.md", 9,
     "hooks/emit_charter.py"):
        "target retired by PR #222 with the lifecycle-hook fallback it implemented",
    # Five references to one target, retired together by #543, which replaced
    # the merge-time filing job with a line in the board's refresh note. Each
    # sentence characterises the script -- what it ran on, what a guard caught
    # in it, what it would have been unable to obey -- so none is a bare
    # locator, and there is no new home to repoint to.
    ("D-480-2026-09-07-the-split-is-the-shape.md", 25,
     "tools/ceiling_filing.py"):
        "target retired by PR #544, which moved the reading to the refresh note",
    ("D-480-2026-09-07-the-split-is-the-shape.md", 43,
     "tools/ceiling_filing.py"):
        "target retired by PR #544; the sentence records a guard finding against it",
    ("D-491-2026-09-07-one-owner-for-cold-one-route-to-the-tree.md", 25,
     "tools/ceiling_filing.py"):
        "target retired by PR #544, which is also what makes the sentence's "
        "'raises a pool item' false of any later tree",
    ("D-496-2026-09-07-a-handoff-that-reaches-nobody.md", 26,
     "tools/ceiling_filing.py"):
        "target retired by PR #544; the sentence names it as an origin exhibit",
    ("D-496-2026-09-07-a-handoff-that-reaches-nobody.md", 44,
     "tools/ceiling_filing.py"):
        "target retired by PR #544; the sentence names it as a rejected shape's exhibit",
    # Issue #652 retires the pool, the review row, and the external-pass
    # mechanism by deletion. These entries are frozen accounts of those
    # mechanisms while they existed, so none has a truthful new target.
    ("D-438-2026-09-06-a-filing-lands-in-a-pool.md", 25,
     "skills/filing/scripts/pool-policy.json"):
        "target retired by issue #652 with the pool whose policy it carried",
    ("D-441-2026-09-06-the-pool-moves-on-its-own.md", 9,
     "skills/filing/scripts/pool.py"):
        "target retired by issue #652 with the pool transport it implemented",
    ("D-481-2026-09-07-the-push-line.md", 53,
     "skills/filing/scripts/pool-policy.json"):
        "target retired by issue #652 with the pool whose push rule it carried",
    ("D-522-2026-09-08-the-refresh-owns-the-cycle.md", 11,
     "skills/filing/scripts/pool-policy.json"):
        "target retired by issue #652 with the pool cycle it configured",
    ("D-523-2026-09-08-a-tie-break-that-states-itself.md", 22,
     "skills/filing/scripts/pool.py"):
        "target retired by issue #652 with the pool command the entry records",
    ("D-524-2026-09-08-a-load-condition-has-one-home.md", 29,
     "skills/filing/scripts/pool.py"):
        "target retired by issue #652 with the pool loader the entry records",
    ("D-524-2026-09-08-a-load-condition-has-one-home.md", 29,
     "skills/filing/scripts/pool-policy.json"):
        "target retired by issue #652 with the policy that loader read",
    ("D-524-2026-09-08-a-load-condition-has-one-home.md", 31,
     "skills/filing/scripts/pool.py"):
        "target retired by issue #652 with the pool loader the entry quotes",
    ("D-561-2026-09-10-records-sheds-three-sections.md", 9,
     "docs/cells/records/references/what-a-review-records.md"):
        "target retired by issue #652 when the review record became closed history",
    ("D-561-2026-09-10-records-sheds-three-sections.md", 21,
     "docs/cells/records/references/what-a-review-records.md"):
        "target retired by issue #652 with the review-record procedure it describes",
    ("D-561-2026-09-10-records-sheds-three-sections.md", 31,
     "docs/cells/records/references/what-a-review-records.md"):
        "target retired by issue #652 with the review-record procedure it locates",
    ("D-643-2026-09-16-the-charter-cell-swept.md", 51,
     "docs/cells/records/references/what-a-review-records.md"):
        "target retired by issue #652 when the review record became closed history",
    ("D-644-2026-09-16-the-filing-cell-swept.md", 15,
     "skills/filing/references/pitch-template.md"):
        "target retired by issue #652 when the filing template was replaced",
    ("D-644-2026-09-16-the-filing-cell-swept.md", 17,
     "skills/filing/references/the-pool.md"):
        "target retired by issue #652 with the pool procedure it contained",
    ("D-644-2026-09-16-the-filing-cell-swept.md", 31,
     "skills/filing/scripts/pool.py"):
        "target retired by issue #652 with the pool command the entry records",
    ("D-644-2026-09-16-the-filing-cell-swept.md", 35,
     "skills/filing/references/pitch-template.md"):
        "target retired by issue #652 when the filing template was replaced",
    ("D-644-2026-09-16-the-filing-cell-swept.md", 72,
     "skills/filing/tests/test_fade.py"):
        "target retired by issue #652 with the pool fade behavior it proved",
    ("D-646-2026-09-16-adversarial-review-cell-swept.md", 11,
     "skills/adversarial-review/scripts/external_pass.py"):
        "target retired by issue #652 with the external-pass mechanism it implemented",
    ("D-646-2026-09-16-adversarial-review-cell-swept.md", 177,
     "docs/cells/records/references/what-a-review-records.md"):
        "target retired by issue #652 when the review record became closed history",
}

_ISSUE_665_RETIRED_MECHANISMS = {
    ".claude/skills/adversarial-review/SKILL.md": "the roster mirror tree",
    "docs/admissions.jsonl": "the admission record and always-on budgets",
    "docs/cells/board/SKILL.md": "the board",
    "docs/cells/board/references/refreshing-it.md": "the board refresh procedure",
    "docs/cells/records/references/the-settling-row.md": "the settling-row procedure",
    "docs/settling.jsonl": "the settling record",
    "skills/substrate/scripts/lint.py": "the shipped substrate guard implementation",
    "skills/substrate/tests/test_substrate_lint.py": "the shipped substrate guard tests",
    "tools/board.py": "the board command",
    "tools/check_version_bump.py": "the per-PR version-bump guard",
    "tools/tests/test_check_version_bump.py": "the per-PR version-bump guard tests",
    "tools/doctrine_callout.py": "the doctrine-callout job",
    "tools/roster.py": "the roster mirror generator",
    "tools/tests/test_roster.py": "the roster mirror generator tests",
}

_ISSUE_665_RETIRED_REFS = {
    ("D-156-2026-08-24-installable-plugin-and-shipped-charter.md", 13, "tools/check_version_bump.py"),
    ("D-186-2026-08-25-windows-text-mode-defaults.md", 27, "tools/check_version_bump.py"),
    ("D-186-2026-08-25-windows-text-mode-defaults.md", 33, "tools/check_version_bump.py"),
    ("D-186-2026-08-25-windows-text-mode-defaults.md", 33, "tools/doctrine_callout.py"),
    ("D-186-2026-08-25-windows-text-mode-defaults.md", 62, "tools/tests/test_check_version_bump.py"),
    ("D-186-2026-08-25-windows-text-mode-defaults.md", 71, "tools/doctrine_callout.py"),
    ("D-210-2026-08-26-project-roster-and-the-loaded-total.md", 17, "tools/roster.py"),
    ("D-232-2026-08-29-subprocess-stdin-and-the-roster-comparison.md", 98, "tools/roster.py"),
    ("D-252-2026-08-30-the-standard-stops-picking-a-language.md", 19, "tools/roster.py"),
    ("D-253-2026-08-30-guidance-on-its-readers-surface.md", 58, "tools/roster.py"),
    ("D-262-2026-08-30-batch-at-birth-and-the-failing-run.md", 17, "tools/roster.py"),
    ("D-270-2026-08-30-version-guard-two-bounds.md", 7, "tools/check_version_bump.py"),
    ("D-270-2026-08-30-version-guard-two-bounds.md", 64, "tools/check_version_bump.py"),
    ("D-270-2026-08-30-version-guard-two-bounds.md", 64, "tools/tests/test_check_version_bump.py"),
    ("D-270-2026-08-30-version-guard-two-bounds.md", 90, "tools/check_version_bump.py"),
    ("D-270-2026-08-30-version-guard-two-bounds.md", 90, "tools/tests/test_check_version_bump.py"),
    ("D-278-2026-08-30-a-roster-surface-per-runtime.md", 26, "tools/roster.py"),
    ("D-291-2026-09-01-repo-only-cells-and-a-budget-on-the-rows.md", 11, "tools/roster.py"),
    ("D-291-2026-09-01-repo-only-cells-and-a-budget-on-the-rows.md", 27, "tools/doctrine_callout.py"),
    ("D-295-2026-09-01-the-trigger-and-its-fix-batch-reach-the-product-consumer.md", 49, "tools/doctrine_callout.py"),
    ("D-317-2026-09-01-the-installed-version-check-is-declined.md", 7, "tools/check_version_bump.py"),
    ("D-317-2026-09-01-the-installed-version-check-is-declined.md", 21, ".claude/skills/adversarial-review/SKILL.md"),
    ("D-317-2026-09-01-the-installed-version-check-is-declined.md", 21, "tools/roster.py"),
    ("D-327-2026-09-02-board-transport.md", 11, "tools/board.py"),
    ("D-346-2026-09-03-a-ceiling-admits-on-an-itemised-record.md", 21, "docs/admissions.jsonl"),
    ("D-346-2026-09-03-a-ceiling-admits-on-an-itemised-record.md", 44, "docs/admissions.jsonl"),
    ("D-346-2026-09-03-a-ceiling-admits-on-an-itemised-record.md", 46, "tools/doctrine_callout.py"),
    ("D-365-2026-09-04-review-cost-and-target.md", 71, "docs/admissions.jsonl"),
    ("D-371-2026-09-04-the-review-runs-once.md", 53, "docs/admissions.jsonl"),
    ("D-376-2026-09-04-the-charter-holds-what-loads-first.md", 25, "docs/admissions.jsonl"),
    ("D-393-2026-09-05-the-affirmation-happens-in-conversation-and-one-document-states-it.md", 55, "tools/doctrine_callout.py"),
    ("D-394-2026-09-05-the-callout-watches-descriptions-not-bodies.md", 7, "tools/doctrine_callout.py"),
    ("D-394-2026-09-05-the-callout-watches-descriptions-not-bodies.md", 33, "tools/doctrine_callout.py"),
    ("D-415-2026-09-05-the-cause-tie-and-what-consumes-it.md", 9, "docs/cells/board/SKILL.md"),
    ("D-415-2026-09-05-the-cause-tie-and-what-consumes-it.md", 13, "docs/cells/board/SKILL.md"),
    ("D-415-2026-09-05-the-cause-tie-and-what-consumes-it.md", 33, "docs/cells/board/SKILL.md"),
    ("D-415-2026-09-05-the-cause-tie-and-what-consumes-it.md", 39, "tools/board.py"),
    ("D-415-2026-09-05-the-cause-tie-and-what-consumes-it.md", 49, "tools/board.py"),
    ("D-429-2026-09-05-the-cause-relationship-becomes-a-link.md", 11, "docs/cells/board/SKILL.md"),
    ("D-429-2026-09-05-the-cause-relationship-becomes-a-link.md", 11, "tools/board.py"),
    ("D-429-2026-09-05-the-cause-relationship-becomes-a-link.md", 17, "tools/board.py"),
    ("D-429-2026-09-05-the-cause-relationship-becomes-a-link.md", 19, "tools/doctrine_callout.py"),
    ("D-429-2026-09-05-the-cause-relationship-becomes-a-link.md", 27, "docs/cells/board/SKILL.md"),
    ("D-429-2026-09-05-the-cause-relationship-becomes-a-link.md", 47, "tools/board.py"),
    ("D-430-2026-09-06-intake-enters-the-board-by-cause.md", 62, "tools/board.py"),
    ("D-430-2026-09-06-intake-enters-the-board-by-cause.md", 62, "tools/doctrine_callout.py"),
    ("D-430-2026-09-06-intake-enters-the-board-by-cause.md", 70, "docs/admissions.jsonl"),
    ("D-431-2026-09-05-handoff-at-the-affirmation.md", 47, "docs/admissions.jsonl"),
    ("D-436-2026-09-06-successor-stop-ordering.md", 58, "docs/admissions.jsonl"),
    ("D-437-2026-09-06-a-cell-may-point-and-a-circle-fails.md", 35, "docs/admissions.jsonl"),
    ("D-437-2026-09-06-a-cell-may-point-and-a-circle-fails.md", 51, "tools/roster.py"),
    ("D-437-2026-09-06-a-cell-may-point-and-a-circle-fails.md", 51, "tools/tests/test_roster.py"),
    ("D-438-2026-09-06-a-filing-lands-in-a-pool.md", 11, "docs/cells/board/SKILL.md"),
    ("D-438-2026-09-06-a-filing-lands-in-a-pool.md", 11, "tools/board.py"),
    ("D-438-2026-09-06-a-filing-lands-in-a-pool.md", 31, "tools/board.py"),
    ("D-438-2026-09-06-a-filing-lands-in-a-pool.md", 33, "docs/cells/board/SKILL.md"),
    ("D-438-2026-09-06-a-filing-lands-in-a-pool.md", 68, "docs/cells/board/SKILL.md"),
    ("D-438-2026-09-06-a-filing-lands-in-a-pool.md", 74, "docs/cells/board/SKILL.md"),
    ("D-441-2026-09-06-the-pool-moves-on-its-own.md", 9, "tools/board.py"),
    ("D-441-2026-09-06-the-pool-moves-on-its-own.md", 25, "tools/board.py"),
    ("D-441-2026-09-06-the-pool-moves-on-its-own.md", 66, "docs/cells/board/SKILL.md"),
    ("D-441-2026-09-06-the-pool-moves-on-its-own.md", 67, "tools/board.py"),
    ("D-454-2026-09-07-an-ask-announces-itself.md", 11, "tools/doctrine_callout.py"),
    ("D-454-2026-09-07-an-ask-announces-itself.md", 35, "docs/settling.jsonl"),
    ("D-481-2026-09-07-the-push-line.md", 52, "docs/cells/board/SKILL.md"),
    ("D-481-2026-09-07-the-push-line.md", 72, "docs/settling.jsonl"),
    ("D-522-2026-09-08-the-refresh-owns-the-cycle.md", 7, "docs/cells/board/SKILL.md"),
    ("D-522-2026-09-08-the-refresh-owns-the-cycle.md", 23, "docs/cells/board/SKILL.md"),
    ("D-522-2026-09-08-the-refresh-owns-the-cycle.md", 23, "tools/board.py"),
    ("D-524-2026-09-08-a-load-condition-has-one-home.md", 9, "tools/roster.py"),
    ("D-524-2026-09-08-a-load-condition-has-one-home.md", 25, "docs/admissions.jsonl"),
    ("D-524-2026-09-08-a-load-condition-has-one-home.md", 33, "docs/admissions.jsonl"),
    ("D-544-2026-09-09-the-ceiling-reading-goes-to-the-refresh-note.md", 22, "docs/cells/board/SKILL.md"),
    ("D-544-2026-09-09-the-ceiling-reading-goes-to-the-refresh-note.md", 32, "tools/roster.py"),
    ("D-545-2026-09-09-a-review-disposes-its-own-findings.md", 23, "docs/cells/board/SKILL.md"),
    ("D-556-2026-09-09-an-amendment-seats-revision-diff.md", 46, "docs/settling.jsonl"),
    ("D-561-2026-09-10-records-sheds-three-sections.md", 9, "docs/cells/records/references/the-settling-row.md"),
    ("D-561-2026-09-10-records-sheds-three-sections.md", 21, "docs/cells/records/references/the-settling-row.md"),
    ("D-561-2026-09-10-records-sheds-three-sections.md", 49, "docs/cells/records/references/the-settling-row.md"),
    ("D-561-2026-09-10-records-sheds-three-sections.md", 59, "tools/roster.py"),
    ("D-568-2026-09-10-adversarial-review-sheds-three-blocks.md", 92, "docs/admissions.jsonl"),
    ("D-575-2026-09-11-a-rule-is-a-guard-a-script-an-exhibit-or-unwritten.md", 33, "docs/admissions.jsonl"),
    ("D-602-2026-09-13-the-implementation-brief.md", 31, "docs/settling.jsonl"),
    ("D-611-2026-09-14-the-substrate-cell-swept.md", 64, "docs/settling.jsonl"),
    ("D-618-2026-09-14-the-guards-ship.md", 7, "skills/substrate/scripts/lint.py"),
    ("D-618-2026-09-14-the-guards-ship.md", 7, "skills/substrate/tests/test_substrate_lint.py"),
    ("D-618-2026-09-14-the-guards-ship.md", 29, "skills/substrate/tests/test_substrate_lint.py"),
    ("D-618-2026-09-14-the-guards-ship.md", 39, "skills/substrate/tests/test_substrate_lint.py"),
    ("D-627-2026-09-14-persist-changes-cell-swept.md", 107, "docs/settling.jsonl"),
    ("D-628-2026-09-14-the-spikes-cell-swept.md", 108, "docs/settling.jsonl"),
    ("D-643-2026-09-16-the-charter-cell-swept.md", 65, "docs/admissions.jsonl"),
    ("D-644-2026-09-16-the-filing-cell-swept.md", 97, "docs/cells/board/SKILL.md"),
    ("D-644-2026-09-16-the-filing-cell-swept.md", 97, "docs/cells/board/references/refreshing-it.md"),
    ("D-646-2026-09-16-adversarial-review-cell-swept.md", 223, "docs/settling.jsonl"),
    ("D-654-2026-09-18-every-change-proven-by-running-it.md", 13, "tools/doctrine_callout.py"),
    ("D-654-2026-09-18-every-change-proven-by-running-it.md", 40, "tools/roster.py"),
    ("D-81-2026-08-19-doctrine-callout.md", 15, "tools/doctrine_callout.py"),
}

UNREPAIRABLE_AFTER_LANDING.update({
    key: (
        "target retired by issue #665 with "
        + _ISSUE_665_RETIRED_MECHANISMS[key[2]]
    )
    for key in _ISSUE_665_RETIRED_REFS
})

def cell_of(rel_posix: str) -> str | None:
    """The cell a repo-relative path belongs to, or None if it is in no cell.

    `skills/<cell>` itself counts, so a pointer's target and the file naming
    it are compared on the same footing whichever depth either sits at.
    """
    parts = rel_posix.split("/")
    return parts[1] if len(parts) >= 2 and parts[0] == "skills" else None


def _token_before(line: str, start: int) -> str:
    i = start
    while i > 0 and not line[i - 1].isspace():
        i -= 1
    return line[i:start]


def _rooted_zone_hits(line: str):
    """Rooted-form repo-only references: docs/, tools/, .github/ (any case,
    either slash), not preceded by more path (repo/docs/) or a URL host."""
    for match in ROOTED_ZONE.finditer(line):
        before = _token_before(line, match.start())
        if "://" in before:
            continue  # full web URL — lawful, it resolves for consumers
        if REL_PREFIX_TAIL.search(before):
            continue  # relative form — the resolution check owns it
        if before and re.search(r"[\w@\-/\\]$", before):
            continue  # part of a longer path or hyphenated word (foo-docs/)
        yield match.group(0)


def _resolved_relative_targets(root: Path, file_path: Path, line: str):
    """Resolve ../ and ./ references against the file's directory; yield
    (raw_text, parts-relative-to-root) for targets inside the repo."""
    for match in RELATIVE_REF.finditer(line):
        raw = match.group(0)
        candidate = (file_path.parent / raw.replace("\\", "/")).resolve()
        try:
            rel = candidate.relative_to(root.resolve())
        except ValueError:
            continue  # escapes the repo — not this lint's concern
        yield raw, rel.parts


def check_zone_wall(root: Path) -> list[str]:
    findings = []
    for dirname in SHIPPED_DIRS:
        base = root / dirname
        if not base.is_dir():
            continue
        for path in _iter_files(base):
            text = _read_text(path)
            if text is None:
                continue
            rel_file = path.relative_to(root).as_posix()
            for lineno, line in enumerate(text.splitlines(), 1):
                if path.suffix.lower() == ".md":
                    for marker in DECISION_MARKER.findall(line):
                        findings.append(
                            f"zone-wall: {rel_file}:{lineno} cites repo-only "
                            f"decision marker '{marker}' as shipped rationale; "
                            "state the behavior's reason in the shipped prose"
                        )
                for hit in _rooted_zone_hits(line):
                    findings.append(
                        f"zone-wall: {rel_file}:{lineno} references "
                        f"repo-only path '{hit}'"
                    )
                for raw, parts in _resolved_relative_targets(root, path, line):
                    if parts and parts[0].lower() in REPO_ONLY_NAMES:
                        findings.append(
                            f"zone-wall: {rel_file}:{lineno} relative "
                            f"reference '{raw}' resolves into repo-only '{parts[0]}/'"
                        )
    return findings


def _origin(own: str | None, base: Path) -> str:
    """Name where the reference came from, computed rather than hardcoded.

    The scan list has changed twice already -- `lib/` alone, then three
    directories, then two when the charter became a cell and got a skill's own
    label. A hardcoded label survives none of those, and a label naming the
    wrong zone misdirects the one reader who is already lost."""
    return f" from skill '{own}'" if own else f" from {base.name}/"


class PointerEdge(NamedTuple):
    """One cell naming another, and the line that names it.

    The line travels with the edge because a cycle finding that named only
    the cells would leave the reader to find which sentence of which file
    made each hop -- the archaeology a guard exists to spare them.
    """

    source: str
    target: str
    file: str
    line: int


def _cell_name_refs(text: str) -> list[tuple[int, str, bool]]:
    """Every reserved-form cell reference in `text`, as (line, name, wrapped).

    The one reader for every consumer of the name form -- the pointer graph,
    the lib/hooks arm below, and `check_cell_references` -- so none of them
    can disagree about what counts as a reference: a name one read as an edge
    and another did not would be a pointer lawful in one guard and invisible
    to the next, and the wall's refused direction rests on exactly that
    agreement. [PR #437 review, M12] The name form is read outside fenced blocks only,
    which is the split check 6's docstring states, and the wrapped form is
    read because a reflow is a formatting edit nobody inspects.
    """
    lines = _unfenced_numbered(text)
    refs = [(lineno, match.group(1), False)
            for lineno, line in lines for match in CELL_REF.finditer(line)]
    refs += [(lineno, name, True) for lineno, name in _wrapped_cell_refs(lines)]
    return sorted(refs)


def cell_pointer_graph(root: Path) -> dict[str, list[PointerEdge]]:
    """Every pointer from one cell to another, keyed by the naming cell.

    Only Markdown is read because code a cell carries is executed rather than
    loaded as prose. Missing targets, self-references, charter targets and the
    wall's refused shipped-to-local direction are excluded here because their
    owning checks decide those cases. A directory becomes a cell only when it
    contains SKILL.md, matching the runtime-visible definition used everywhere.
    """
    sources = cell_sources(root)
    repo_names = set(names_under(root, REPO_CELLS))
    graph: dict[str, list[PointerEdge]] = {name: [] for name in sources}
    for name, source in sorted(sources.items()):
        base = root / source / name
        if not base.is_dir():
            continue
        own_is_repo = name in repo_names
        for path in _iter_files(base):
            if path.suffix.lower() != ".md":
                continue
            text = _read_text(path)
            if text is None:
                continue
            rel_file = path.relative_to(root).as_posix()
            for lineno, target, _wrapped in _cell_name_refs(text):
                if target not in graph:
                    continue
                if target.lower() == name.lower():
                    continue
                if target.lower() == CHARTER_CELL:
                    continue
                if not own_is_repo and target in repo_names:
                    continue
                graph[name].append(PointerEdge(name, target, rel_file, lineno))
    return graph


def _strongly_connected(graph: dict[str, list[PointerEdge]]) -> list[list[str]]:
    """Tarjan's components, iteratively.

    Iterative rather than recursive not because this graph is large -- it is
    a dozen cells -- but because a guard that raises on a deep input answers
    the one command the landing procedure mandates with a traceback, and the
    depth here is whatever an adopting repository's cell count happens to be.
    """
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    components: list[list[str]] = []
    counter = 0
    for start in sorted(graph):
        if start in index:
            continue
        index[start] = low[start] = counter
        counter += 1
        stack.append(start)
        on_stack.add(start)
        work = [(start, iter(sorted({e.target for e in graph[start]})))]
        while work:
            node, successors = work[-1]
            descended = False
            for nxt in successors:
                if nxt not in graph:
                    continue
                if nxt not in index:
                    index[nxt] = low[nxt] = counter
                    counter += 1
                    stack.append(nxt)
                    on_stack.add(nxt)
                    work.append(
                        (nxt, iter(sorted({e.target for e in graph[nxt]})))
                    )
                    descended = True
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            if descended:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[node])
            if low[node] == index[node]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                components.append(component)
    return components


def _shortest_cycle(graph: dict[str, list[PointerEdge]],
                    component: set[str]) -> list[PointerEdge]:
    """One representative circle through the component's first member.

    A component can hold exponentially many simple cycles, and printing them
    all would answer a defect with a wall of text. One concrete circle names
    every hop a reader has to break to clear the finding. Breadth-first from
    the alphabetically first member, so the same tree reports the same circle
    every run.

    **A hop is a pair of cells, not a line, and the finding says so.** This
    returns one edge per hop, and a cell may name another from several lines
    or several files -- seven of fourteen pairs did on the tree this landed
    on. A reader who deleted exactly the line named, re-ran, and met the same
    route would read the guard as not registering the fix. The remedy names
    the pair; the line is where to start looking. [PR #437 review, M7]
    """
    start = min(component)
    reached: dict[str, PointerEdge] = {}
    queue = [start]
    while queue:
        node = queue.pop(0)
        for edge in sorted(graph.get(node, []),
                           key=lambda e: (e.target, e.file, e.line)):
            if edge.target not in component:
                continue
            if edge.target == start:
                chain = [edge]
                cursor = node
                while cursor != start:
                    hop = reached[cursor]
                    chain.append(hop)
                    cursor = hop.source
                chain.reverse()
                return chain
            if edge.target not in reached:
                reached[edge.target] = edge
                queue.append(edge.target)
    return []


def pointer_cycle_findings(graph: dict[str, list[PointerEdge]]) -> list[str]:
    """A circle of cell pointers, named member by member.

    **The finding is the cycle and nothing else.** A pointer is lawful, and a
    long chain of them is lawful; what a circle costs is what a circular
    dependency costs a build -- neither end can be read, revised or removed
    without the other, which is the coupling the old ban prevented by
    forbidding the first pointer. [#404]
    """
    findings = []
    for component in _strongly_connected(graph):
        if len(component) < 2:
            continue
        chain = _shortest_cycle(graph, set(component))
        if not chain:
            continue
        route = " -> ".join([chain[0].source] + [edge.target for edge in chain])
        hops = "; ".join(
            f"{edge.file}:{edge.line} names '{edge.target}'" for edge in chain
        )
        findings.append(
            f"pointer-cycle: {route} -- cell pointers may not run in a "
            f"circle: each of these names the next until the chain returns "
            f"to where it began, so none of them can be read or revised "
            f"without the rest. Break any one hop, which means every "
            f"reference from that cell to the next and not only the line "
            f"named here -- {hops}"
        )
    return sorted(findings)


def check_sideways_deps(root: Path) -> list[str]:
    findings = []
    skills = root / SHIPPED_CELLS
    # **No zone flag on the row.** The name form is judged here for `lib/` and
    # `hooks/` alone and every path form is judged the same from either zone,
    # so nothing below reads which zone a directory sits in; carrying the flag
    # left a dead discriminator a later reader would take for a live one.
    # [PR #437 review, M14]
    scan: list[tuple[Path, str | None]] = []
    if skills.is_dir():
        for skill_dir in sorted(p for p in skills.iterdir() if p.is_dir()):
            scan.append((skill_dir, skill_dir.name))
    repo_cells_dir = root / REPO_CELLS
    if repo_cells_dir.is_dir():
        for cell_dir in sorted(p for p in repo_cells_dir.iterdir() if p.is_dir()):
            scan.append((cell_dir, cell_dir.name))
    for name in ("lib", "hooks"):
        base = root / name
        if base.is_dir():
            # None: none of these is a skill, so any skill path is sideways.
            scan.append((base, None))

    # The generator's predicate, not a bare directory test: a directory is
    # not a cell until it holds the file that loads. `check_cell_references`
    # already agrees with the generator; this was the second definition of
    # one fact, and the two disagreed on a half-created cell. [#291]
    # **Both zones read it the same way now.** The shipped half was a
    # directory test while the repo-only half was the generator's, so a
    # half-created shipped cell -- a directory with no SKILL.md -- was a cell
    # to this check and not to the generator or to check 6. [#404]
    cell_names = set(cell_sources(root))
    repo_cell_names = set(names_under(root, REPO_CELLS))

    def _is_cell(name: str) -> bool:
        return name in cell_names

    # **The rooted-repo-cell branch asks a narrower question and keeps its own
    # predicate.** `docs/cells/<name>/` names a repo-only cell or it names
    # nothing: a shipped cell's name there is a path that resolves to no cell
    # at all, so answering it from the union reported prose about a
    # nonexistent path as a reference to a repo-only cell that does not exist.
    # Found by an external reviewer on PR #437, which is where the union
    # arrived. [#404]
    def _is_repo_cell(name: str) -> bool:
        return name in repo_cell_names

    for base, own in scan:
        for path in _iter_files(base):
            text = _read_text(path)
            if text is None:
                continue
            rel_file = path.relative_to(root).as_posix()
            # **Every path form below is read fenced or not**, which is the
            # split `_cell_name_refs` states from the other side. A path
            # inside a fence is not display: this repo's fenced blocks are
            # calling contracts and command lines, check_zone_wall and
            # check_harness_tokens both fire inside them, and
            # test_portability.py reads a cell's script contract through one
            # and requires it to resolve. A path is dead once installed
            # whatever encloses it, where an unlawful *name* inside a fence is
            # a spelling being shown.
            if own is None:
                # **The name form is judged here for lib/ and hooks/ alone.**
                # A cell naming a cell is a pointer, and pointers are ruled on
                # as a graph -- `pointer_cycle_findings` below -- rather than
                # one reference at a time. Neither of these directories is a
                # cell, so a skill dependency from either points sideways
                # however it is spelled, and no graph rule reaches it. [#404]
                for lineno, target, wrapped in _cell_name_refs(text):
                    # Only a name that is actually a cell couples anything; a
                    # backticked word before "cell" that names no skill is
                    # ordinary prose here, and check_cell_references is what
                    # rules on whether it should have resolved.
                    if not _is_cell(target):
                        continue
                    across = " across a line break" if wrapped else ""
                    findings.append(
                        f"sideways-dep: {rel_file}:{lineno} names "
                        f"skill '{target}'" + across + _origin(own, base)
                    )
            for lineno, line in enumerate(text.splitlines(), 1):
                for match in ROOTED_REPO_CELL.finditer(line):
                    target = match.group(1)
                    if not _is_repo_cell(target):
                        continue
                    if own is not None and target.lower() == own.lower():
                        continue
                    findings.append(
                        f"sideways-dep: {rel_file}:{lineno} names the "
                        f"repo-only cell '{target}' by path" + _origin(own, base)
                        + " -- a cell is reached by its name, never by a "
                        f"path into its files, which does not resolve once "
                        f"installed"
                    )
                for match in ROOTED_SKILL.finditer(line):
                    # Same lawful-case guards as the zone wall's rooted branch:
                    # web URLs resolve for consumers, relative forms belong to
                    # the resolution check, and a longer path or hyphenated
                    # token (their-skills/) is not this repo's skills/.
                    before = _token_before(line, match.start())
                    if "://" in before:
                        continue
                    if REL_PREFIX_TAIL.search(before):
                        continue
                    if before and re.search(r"[\w@\-/\\]$", before):
                        continue
                    target = match.group(1)
                    if own is None or target.lower() != own.lower():
                        findings.append(
                            f"sideways-dep: {rel_file}:{lineno} references "
                            f"skill '{target}'" + _origin(own, base)
                        )
                for raw, parts in _resolved_relative_targets(root, path, line):
                    if len(parts) >= 2 and parts[0] == "skills":
                        target = parts[1]
                        if own is None or target.lower() != own.lower():
                            findings.append(
                                f"sideways-dep: {rel_file}:{lineno} relative "
                                f"reference '{raw}' resolves into skill '{target}'"
                                + _origin(own, base)
                            )
    # **The graph is rebuilt rather than accumulated in the loop above.** That
    # loop walks lib/ and hooks/ as well as the cells and carries a zone flag
    # per directory; the graph is a statement about cells alone and is wanted
    # by `tools/figures.py` too, so it has one definition, in one function,
    # with one set of exclusions. The cost is a second read of the cell
    # prose, on a tree of a dozen cells. [#404]
    findings += pointer_cycle_findings(cell_pointer_graph(root))
    return findings


DOCTRINE_CITATION = re.compile(r"\[D-(\d+)\]")


def _doctrine_scan_paths(root: Path) -> list[Path]:
    """The doctrine files, plus every repo-only cell.

    **The cells are here because the material is.** The flow, this
    repository's records rules and its content-routing map carried `[D-N]`
    citations and repo paths while they lived in AGENTS.md, and both were
    checked there. Moving them under `docs/cells/` without moving the scan
    would have retired those guarantees silently. A dangling citation reads
    as authority that resolves and does not, wherever it is written.
    """
    paths = [root / name for name in ("AGENTS.md", "CLAUDE.md")]
    cells = root / REPO_CELLS
    if cells.is_dir():
        # **Depth included, because this change sanctions it.** A repo-only
        # cell sheds into `references/` exactly as a shipped one does, and a
        # dangling `[D-N]` or dead repo path there reads as authority that
        # resolves and does not -- the harm this scan exists to prevent, in
        # the one place the material tells authors to put depth. Probed [#291]:
        # identical prose redded in `SKILL.md` and was silent one directory
        # down. Shipped prose stays out because check 1 rejects its decision
        # markers outright. Repo-only depth may cite the local log, so this
        # resolution check reaches it just as it reaches each cell body.
        paths += sorted(cells.glob("**/*.md"))
    return paths


def check_doctrine_citations(root: Path) -> list[str]:
    r"""Every [D-N] marker in repo-only doctrine names an existing entry.

    check_entry_references resolves references made by the decision log and
    stops there. A dangling doctrine marker still presents historical rationale
    as available evidence, so it must resolve where the local log is present.

    Shipped prose is deliberately outside this scan: check 1 rejects decision
    markers there because an adopter receives the prose without the log. This
    check owns the repository doctrine where a decision citation can resolve.
    """
    findings = []
    directory = root / "docs" / "architecture" / "decisions"
    for path in _doctrine_scan_paths(root):
        name = path.relative_to(root).as_posix()
        if not path.is_file():
            continue  # its absence is check 11's finding, not this one's
        text = _read_text(path)
        if text is None:
            continue
        for lineno, line in _unfenced_numbered(text):
            for match in DOCTRINE_CITATION.finditer(line):
                number = match.group(1)
                if not any(directory.glob(f"D-{number}-*.md")):
                    findings.append(
                        f"doctrine-citation: {name}:{lineno} cites "
                        f"[D-{number}], which is not an entry in the log"
                    )
    return findings


def check_doctrine_references(root: Path) -> list[str]:
    """Every repo path the doctrine writes resolves.

    check_entry_references covers the decision log, which is frozen exhaust,
    and stops there -- so the surface carrying the live rules was the one
    nothing checked. The gap is not theoretical: repointing the doctrine's
    `docs/values.md` mention at a path that does not exist left lint green and
    the whole suite passing, while the identical break inside an entry fired.
    A future change that moves a target repoints every entry, because
    mover-pays and this module force it to, and has nothing telling it the
    doctrine named the target too -- so the guarded surfaces are the record and
    the unguarded one is the rule a session actually follows.

    Scoped to the doctrine files and no wider. `docs/*.md` was measured and
    left out: `_entry_ref_resolves` does not resolve a reference relative to
    its containing file, so `north-star/flow.md` and `../values.md` report as
    unresolved from documents that read them fine. That is resolver work, not
    a path-list edit, and doing it badly here would red the tree with no
    compliant answer -- as bad as passing unlawful work.

    No pin form and no recorded set, deliberately: both exist because an entry
    freezes on landing and cannot be repaired. The doctrine is editable, so its
    only lawful answer is to repoint, and offering an exemption would invite
    the doctrine to carry a dead path with a note instead.
    """
    findings: list[str] = []
    for path in _doctrine_scan_paths(root):
        name = path.relative_to(root).as_posix()
        if not path.is_file():
            continue  # its absence is check 11's finding, not this one's
        text = _read_text(path)
        if text is None:
            continue
        # Fences included, per this module's own rule: a path that does not
        # resolve is broken whatever encloses it, and this repository's fenced
        # blocks are calling contracts rather than examples.
        for lineno, line in enumerate(text.splitlines(), 1):
            for ref, form, _pinned in _entry_refs(line):
                if _doctrine_ref_resolves(root, ref):
                    continue
                # **A cell's own depth resolves against the cell, not the
                # root.** `references/x.md` inside a repo-only cell is the
                # ordinary cell-local form every shipped cell uses, and
                # resolving it from the repository root reports the one lawful
                # way a repo-only cell sheds depth as a broken link -- which
                # would leave a cell unable to have a `references/` directory
                # at all. The doctrine files keep root resolution, having no
                # directory of their own to resolve against. [#260]
                if (path.parent / ref).is_file():
                    continue
                findings.append(
                    f"doctrine-reference: {name}:{lineno} {form} '{ref}' "
                    f"resolves to nothing. The doctrine is editable, so "
                    f"repoint it at the target's current location -- a pin "
                    f"and the decision log's recorded sets are for entries "
                    f"that froze on landing, and neither applies here"
                )
    return findings


def _doctrine_ref_resolves(root: Path, ref: str) -> bool:
    """From the repository root and nowhere else.

    `_entry_ref_resolves` also tries the entry's own directory and `skills/`,
    because decision entries write the skills-relative shorthand routinely. The
    doctrine does not, and inheriting that leniency makes it blind to a broken
    root-relative shorthand such as `charter/SKILL.md`. Doctrine paths are
    written from the repository root, so that is their only resolution base.
    """
    ref = ref.replace("\\", "/")
    if not ref or ref.startswith("/"):
        return False
    candidate = root / ref
    try:
        resolved = candidate.resolve()
    except OSError:
        return False
    return _within(resolved, root) and resolved.exists()


def check_cell_references(root: Path) -> list[str]:
    """Every `<name>` cell reference names a real skill, and every pointer resolves.

    The charter's whole value is that a session reading it can reach the cell
    owning the depth behind each rule it states. That value is what a rename
    silently destroys: the sentence still reads correctly and points nowhere,
    and prose cannot be resolved by the runtime the way a path can be. So the
    reference form is machine-checked at the only moment anyone will look.

    A backticked word before "cell" that names no skill is the finding, not an
    exemption -- there is no way to tell a typo'd cell name from a word that
    was never meant as one, and the reference form exists precisely so the
    question does not have to be judged case by case.
    """
    findings = []

    def _names(source: str) -> set:
        # **A directory is not a cell until it holds the file that loads.** An
        # abandoned or half-renamed `docs/cells/ghost/` would otherwise satisfy
        # a `` `ghost` cell `` reference although no runtime can load it.
        return set(names_under(root, source))

    # **Two known sets, because the wall runs one way.** A repo-only cell may
    # name a shipped cell -- that is the lawful direction, the same one that
    # lets every tool here import `lib/` -- and a shipped cell may never name a
    # repo-only one, because a consumer installing the plugin receives the
    # shipped cell and not the repo-only cell it would be pointing at. The name
    # form is the one shape `check_zone_wall` cannot see: it matches paths, and
    # `` `siting` cell `` is not a path. So a single widened set would open the
    # wall in the one place nothing else is watching. [#260]
    shipped_cells = _names(SHIPPED_CELLS)
    repo_cells = _names(REPO_CELLS)
    known = shipped_cells | repo_cells
    # The doctrine files and the README are not cells and the sideways rule
    # does not reach them -- they may name any cell. But a name they write
    # strands exactly as a cell's does, and all three now point at the cell
    # owning a standard they apply, so the existence half has to see them.
    # The README is here because it is the front door: a rename leaving it
    # reading correctly and pointing nowhere is the failure this check is for,
    # and widening the scan is not the widening D-169 priced out -- that was
    # the matcher, whose cost was more prose over-firing, which this adds none of.
    scan = [root / name for name in SHIPPED_DIRS] + [
        root / "AGENTS.md", root / "CLAUDE.md", root / "README.md",
        root / REPO_CELLS,
    ]
    for base in scan:
        if base.is_file():
            paths = [base]
        elif base.is_dir():
            paths = _iter_files(base)
        else:
            continue
        for path in paths:
            text = _read_text(path)
            if text is None:
                continue
            rel_file = path.relative_to(root).as_posix()
            # **The one reader, not a third copy of it.** These three steps
            # were repeated inline here while `_cell_name_refs` was extracted
            # to own them, and this copy is the sole guard for the wall's
            # refused direction in the name form -- check 5 drops that edge on
            # the ground that this check holds it. A divergence here would
            # open the wall with nothing reporting it. [PR #437 review, M12]
            named = [(lineno, name)
                     for lineno, name, _wrapped in _cell_name_refs(text)]
            in_shipped = any(
                rel_file == d or rel_file.startswith(d + "/")
                for d in SHIPPED_DIRS
            )
            for lineno, target in sorted(named):
                if target not in known:
                    findings.append(
                        f"cell-reference: {rel_file}:{lineno} names cell "
                        f"'{target}', which is not a cell under "
                        f"{SHIPPED_CELLS}/ or {REPO_CELLS}/"
                    )
                elif in_shipped and target in repo_cells:
                    findings.append(
                        f"cell-reference: {rel_file}:{lineno} names the "
                        f"repo-only cell '{target}' from the shipped zone -- "
                        f"a consumer installs {SHIPPED_CELLS}/ and never "
                        f"loads {REPO_CELLS}/, so this points them at nothing. "
                        f"The wall runs one way: {REPO_CELLS}/ may name "
                        f"{SHIPPED_CELLS}/, never the reverse"
                    )
            # A pointer is a path form, so it reads every line, fenced or
            # not -- the same rule check 5's paths follow, and for the same
            # reason: a path that does not resolve is broken wherever it is
            # written. Only the name form above is exempt inside a fence.
            for lineno, line in enumerate(text.splitlines(), 1):
                for match in REFERENCES_REF.finditer(line):
                    # The same lawful cases the rooted-skill branch names: a
                    # web URL resolves for a consumer, and a longer path that
                    # merely ends in `references/x.md` is somebody else's
                    # tree, not this cell's depth. Copied rather than shared
                    # because the two matchers differ; the reasoning does not.
                    before = _token_before(line, match.start())
                    if "://" in before:
                        continue
                    if before and re.search(r"[\w@\-/\\]$", before):
                        continue
                    pointer = match.group(1)
                    # Normalised because a POSIX runtime does not read a
                    # backslash as a separator, so the unnormalised form
                    # resolves to a single strangely-named file and misses.
                    if not (path.parent / pointer.replace("\\", "/")).is_file():
                        findings.append(
                            f"reference-pointer: {rel_file}:{lineno} points at "
                            f"'{pointer}', which does not resolve against this "
                            f"file's own directory"
                        )
                # The relative form of the same pointer, which the branch
                # above cannot see: from inside references/ the bare form
                # would resolve to references/references/x.md, so depth that
                # points at its sibling depth writes `../references/x.md` --
                # and _token_before reads the `../` prefix as more path and
                # skips it as somebody else's tree. It was skipped in silence
                # until this cell shed five files' worth of depth and wrote
                # the tree's first sibling pointers; a probe renaming one
                # target left the suite green.
                #
                # Two bounds, and both are about who owns the finding. Only
                # .md targets, because a script mention is check 6's, resolved
                # the same way. And only targets landing inside the naming
                # file's OWN cell, because a relative reference out of a cell
                # is the zone wall's or the sideways rule's -- unlawful
                # whether or not it resolves, and reporting it twice prices
                # one defect as two.
                for match in RELATIVE_MD_REF.finditer(line):
                    raw = match.group(0)
                    target = (path.parent / raw.replace("\\", "/")).resolve()
                    try:
                        rel = target.relative_to(root.resolve()).as_posix()
                    except ValueError:
                        # Knowingly silent, and not for the reason the arm
                        # below is: check_sideways_deps does catch an
                        # out-of-cell target, and nothing in lint.run
                        # reports one outside the repository at all.
                        # Left so because the bound is the naming file's
                        # own cell; no cell has ever written such a path.
                        continue
                    if cell_of(rel_file) is None or cell_of(rel) != cell_of(rel_file):
                        continue
                    if not target.is_file():
                        findings.append(
                            f"reference-pointer: {rel_file}:{lineno} points at "
                            f"'{raw}', which does not resolve against this "
                            f"file's own directory"
                        )
    return findings


def _frontmatterless(text: str) -> str:
    """Text with a leading YAML frontmatter block removed, if there is one."""
    if not text.startswith("---"):
        return text
    end = text.find(chr(10) + "---", 3)
    return text if end == -1 else text[end + 4:].lstrip(chr(10))


# The marker run and whatever follows it on the line. CommonMark closes a
# fence only on the same character at least as long as the opener, and adds
# two clauses a marker-only match misses: a backtick opener's info string may
# not contain a backtick -- so a line-initial code span showing a literal
# ``` is a paragraph, not a fence -- and a closing fence carries no info
# string at all. Both are what a cell documenting markdown writes, and
# without them one such line silently swallows every reference check to the
# end of the file, or ends a fence early and reads displayed prose as live.
FENCE_MARKER = re.compile(r"\A(`{3,}|~{3,})(.*)\Z")


def _unfenced_numbered(text: str) -> list[tuple[int, str]]:
    """Non-fenced lines as (line number, stripped text), numbering preserved.

    A fence closes only on the same character at least as long as the one
    that opened it -- CommonMark's rule, and the renderer every reader of
    these files is looking at. A naive toggle gets this wrong in both
    directions: a ``` line quoted inside a ```` block ends the fence early,
    so displayed prose is read as live; and a ~~~ line inside a ``` block
    fails to end it, so live prose goes unread to the end of the file. Both
    are what a cell teaching markdown writes, not an adversary's input.

    This is the one implementation. `_unfenced` below delegates rather than
    repeating it, because two copies of a rule kept in agreement by hand is
    the defect this repository's own authoring standard forbids -- and the
    duplicate was found under review, having already drifted in behaviour
    from nothing but being written twice.
    """
    out, opener = [], None
    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        marker = FENCE_MARKER.match(stripped)
        if marker:
            run, info = marker.group(1), marker.group(2)
            if opener is None:
                if not (run[0] == "`" and "`" in info):
                    opener = run
                    continue
            elif run[0] == opener[0] and len(run) >= len(opener) and not info.strip():
                opener = None
                continue
        if opener is None:
            out.append((lineno, stripped))
    return out


def _wrapped_cell_refs(lines: list[tuple[int, str]]):
    """Cell references split across a line break, reported at the first line.

    Adjacency in the original file is required: a blank line or a dropped
    fence between the halves is a paragraph break, not a wrap.
    """
    for (lineno, line), (next_lineno, next_line) in zip(lines, lines[1:]):
        if next_lineno != lineno + 1 or not next_line:
            continue
        tail = CELL_REF_TAIL.search(line)
        if tail and CELL_REF_HEAD.match(next_line):
            yield lineno, tail.group(1)


def _unfenced(text: str) -> list[str]:
    """The document's lines with fenced blocks dropped, each stripped.

    An import inside a fence is displayed, not performed, exactly as a
    backticked one is. This file's own docstring reasons from that premise;
    the guard below has to apply it to both spellings or to neither.
    """
    return [line for _lineno, line in _unfenced_numbered(text)]


def check_doctrine(root: Path) -> list[str]:
    findings = []
    agents = root / "AGENTS.md"
    if not agents.is_file():
        findings.append("doctrine: AGENTS.md is missing (it is the canonical root file)")
    charter = root / CHARTER
    # This repository receives its local charter through a bare import in
    # AGENTS.md. Backticked and fenced mentions display text but import nothing.
    if agents.is_file():
        lines = _unfenced(agents.read_text(encoding="utf-8", errors="replace"))
        if CHARTER_IMPORT not in lines:
            findings.append(
                "doctrine-import: AGENTS.md carries no bare "
                f"'{CHARTER_IMPORT}' line -- without it the binding half "
                "reaches no session in this repository, which installs no plugin"
            )
        elif not charter.is_file():
            findings.append(
                f"doctrine-import: AGENTS.md imports '{CHARTER_IMPORT}', "
                "which does not exist"
            )

    # Only the two sanctioned imports are lawful; any other one silently adds
    # an entire file to the root instructions.
    for name, allowed in (("AGENTS.md", {CHARTER_IMPORT}),
                          ("CLAUDE.md", {"@AGENTS.md"})):
        doc = root / name
        if not doc.is_file():
            continue
        for lineno, line in enumerate(_unfenced(doc.read_text(
                encoding="utf-8", errors="replace")), 1):
            stripped = line.strip()
            if stripped.startswith("@") and stripped not in allowed:
                findings.append(
                    f"doctrine-import: {name} imports '{stripped}', which the "
                    f"runtime inlines whole without making that content visible "
                    f"at this root. The lawful imports here are "
                    f"{', '.join(sorted(allowed))}"
                )

    pointer = root / "CLAUDE.md"
    if not pointer.is_file():
        findings.append(
            "doctrine-pointer: CLAUDE.md is missing -- Claude Code loads "
            "no root doctrine without it; it must be a live @AGENTS.md import"
        )
        return findings
    text = pointer.read_text(encoding="utf-8", errors="replace")
    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    if first_line != "@AGENTS.md" or len(text) > POINTER_BUDGET_CHARS:
        findings.append(
            "doctrine-pointer: CLAUDE.md must begin with a bare "
            "'@AGENTS.md' import line and stay a short pointer -- a backticked or "
            "buried mention does not import, and any fork diverges the runtimes"
        )
    return findings


def check_decision_index(root: Path) -> list[str]:
    """Every decision entry has a row in the log's index, and every row a file.

    The row is part of landing, written once in the PR that lands the entry.
    It is not maintained after, except for the narrow repairs the index itself
    permits. Without the row a later session cannot find the decision by number.
    """
    findings: list[str] = []
    directory = root / "docs" / "architecture" / "decisions"
    index = directory / "README.md"
    if not index.is_file():
        return findings
    entries = {path.name for path in directory.glob("D-*.md")}
    listed = set(re.findall(r"^\| \[D-[^\]]+\]\(([^)]+)\)", index.read_text(
        encoding="utf-8", errors="replace"
    ), re.MULTILINE))
    for name in sorted(entries - listed):
        findings.append(
            f"decision-index: {name} has no row in "
            f"docs/architecture/decisions/README.md -- the entry is unreachable "
            f"from its number"
        )
    for name in sorted(listed - entries):
        findings.append(
            f"decision-index: docs/architecture/decisions/README.md links {name}, "
            f"which does not exist"
        )
    return findings


def check_entry_references(root: Path) -> list[str]:
    """Every reference a decision entry makes resolves, is pinned, or is recorded.

    An entry is frozen on landing but for two narrow repairs, of which this
    guard reaches one: the change that moves a target repoints every entry
    reference to it, and that repair is only lawful inside the moving change. This guard is what makes the
    permission fire at that moment -- without it the mover has no signal, and
    by the time anyone notices, no change is the mover any more. PR #104
    stranded three references that way and PR #132 stranded three more the next
    day, the second time reproducing a spike's rehearsal exactly.

    A reference is lawful four ways. It resolves. It is pinned -- written with
    the commit it shipped at, which no later move can break. It is in
    BASELINE_UNRESOLVABLE, dead before this guard existed. Or it is in
    UNREPAIRABLE_AFTER_LANDING, the disposition for a reference a later change
    made unrepairable: a retired target, or a move that also rewrote the text
    the entry quotes. Without that fourth form the guard reds with no compliant
    answer, which blocks lawful work -- as bad as passing unlawful work.

    Both recorded sets are checked for staleness: a row whose reference has
    come back to life is reported, so the baseline can only shrink and the
    record cannot rot into an exemption list nobody rereads.
    """
    findings: list[str] = []
    directory = root / "docs" / "architecture" / "decisions"
    if not directory.is_dir():
        return findings
    seen: set[tuple[str, int, str]] = set()
    # The index is scanned with the entries: it carries references of its own,
    # and unlike an entry it is editable, so its repair has an obvious home.
    paths = sorted(directory.glob("D-*.md")) + [directory / "README.md"]
    for path in paths:
        # A directory named like an entry would raise here and take down every
        # other check in the run; a traceback is a worse signal than a finding.
        if not path.is_file():
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            for ref, form, pinned in _entry_refs(line):
                key = (path.name, lineno, ref)
                seen.add(key)
                if key in BASELINE_UNRESOLVABLE or key in UNREPAIRABLE_AFTER_LANDING:
                    continue
                if pinned or _entry_ref_resolves(root, directory, ref):
                    continue
                findings.append(
                    f"entry-reference: docs/architecture/decisions/{path.name}:"
                    f"{lineno} {form} '{ref}' resolves to nothing. If you moved "
                    f"its target, repoint it here in the same change -- unless "
                    f"repointing would leave this sentence untrue of the "
                    f"target at its new home, in which case record it in "
                    f"UNREPAIRABLE_AFTER_LANDING with a reason. Do not add a "
                    f"pin to a landed entry. The bound is in "
                    f"docs/architecture/decisions/README.md"
                )
    findings.extend(_check_recorded_rows(root, directory, seen))
    return findings


def _check_recorded_rows(root: Path, directory: Path, seen) -> list[str]:
    """A recorded row must still name a real, still-dead reference, and a row
    in the growable set must say why. Otherwise the record rots: a stale row
    silently exempts nothing, and an unexplained one is the exemption list the
    baseline exists not to be."""
    findings: list[str] = []
    for label, rows in (
        ("BASELINE_UNRESOLVABLE", BASELINE_UNRESOLVABLE),
        ("UNREPAIRABLE_AFTER_LANDING", UNREPAIRABLE_AFTER_LANDING),
    ):
        for key, reason in sorted(rows.items()):
            name, lineno, ref = key
            if not str(reason).strip():
                findings.append(
                    f"entry-reference: {label} row {name}:{lineno} '{ref}' has "
                    f"no reason -- every recorded reference states why it stands"
                )
            # A row naming an entry this tree does not contain is not stale, it
            # is inapplicable: the same module lints partial trees and fixtures.
            if not (directory / name).is_file():
                continue
            if key not in seen:
                findings.append(
                    f"entry-reference: {label} row {name}:{lineno} '{ref}' "
                    f"matches no reference in the tree -- remove the stale row"
                )
            elif _entry_ref_resolves(root, directory, ref):
                findings.append(
                    f"entry-reference: {label} row {name}:{lineno} '{ref}' "
                    f"resolves again -- remove the row; this record only shrinks"
                )
    return findings


def _entry_refs(line: str):
    """Repo references a decision entry makes, each with whether it is pinned.

    A bare filename is not a reference -- it names a thing in prose and claims
    nothing about where it lives, so it has nothing to repoint. A slash-joined
    token is a reference only if its shape says so (REPO_ROOTS / REF_EXTENSIONS):
    `A/B` is this repo's own name for its spike pattern, and a guard that reds
    it blocks lawful work while teaching authors to write references less
    precisely.

    The pin is scoped to the reference it follows, never to the line. Entries
    are written one paragraph per line, so a line-wide pin exempted every
    reference in a paragraph -- and one pin in the tree already sat on a line
    carrying three.
    """
    found = []
    for match in ENTRY_LINK.finditer(line):
        target = match.group(1).split("#")[0].strip()
        if target and not target.startswith(("http://", "https://", "mailto:")):
            found.append((match.start(), match.end(), target, "link"))
    for match in ENTRY_PATH.finditer(line):
        # A `:N` line anchor is not part of the path it anchors into.
        ref = match.group(1).split(":")[0]
        if _is_reference_shaped(ref):
            found.append((match.start(), match.end(), ref, "path"))
    found.sort()
    for index, (_, end, ref, form) in enumerate(found):
        # A pin covers the reference it follows and stops where the next one
        # begins, so ``a` at <sha>; also `b`` pins a and leaves b exposed. The
        # next match's own start is what bounds it: reconstructing that start
        # by subtracting the reference's length is exact only when the match
        # text is the reference, and for `[display](target)` it is not -- the
        # window then swallowed the following link's anchor text, so a sha
        # quoted in that anchor pinned the reference before it.
        limit = found[index + 1][0] if index + 1 < len(found) else len(line)
        window = line[end:max(end, limit)]
        yield ref, form, PINNED_REF.search(window) is not None


def _is_reference_shaped(ref: str) -> bool:
    """Shape, not content: a known extension, or a first segment that is a real
    root of this repository."""
    first = ref.replace("\\", "/").split("/")[0]
    if first in REPO_ROOTS:
        return True
    return any(ref.endswith(ext) for ext in REF_EXTENSIONS)


def _entry_ref_resolves(root: Path, directory: Path, ref: str) -> bool:
    """Resolved from the repo root, from the entry's own directory, or under
    `skills/` -- entries write the skills-relative shorthand routinely, and a
    guard that failed it would be reporting a reference a reader follows fine.

    A reference that escapes the repository never resolves, whatever sits
    beside the checkout: a sibling worktree exists locally and not in CI, and a
    guard whose answer depends on that is a guard with two answers.
    """
    ref = ref.replace("\\", "/")
    if not ref or ref.startswith("/"):
        return False
    for base in (root, directory, root / "skills"):
        candidate = base / ref
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if not _within(resolved, root):
            continue
        if candidate.exists():
            return True
    return False


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return False
    return True


def check_cell_frontmatter(root: Path) -> list[str]:
    """Every skill declares a name and a description the runtime can parse.

    A cell's frontmatter is the whole of its always-on surface: the runtime
    indexes the name and description and nothing else until the cell fires. One
    unquoted `: ` inside a description made the charter's frontmatter
    unparseable, and the runtime's answer to unparseable is to load the cell
    with empty metadata -- no name, no description, no trigger, silently. The
    lint, the suite and `claude plugin validate .` were all green over it,
    because the first two never looked and the third validates the marketplace
    manifest and stops.

    Hand-rolled rather than PyYAML, and not only for the stdlib rule: the
    runtime parses YAML 1.2 in JavaScript, PyYAML is 1.1, and the two can
    disagree on exactly the plain scalars at issue. A dependency that buys an
    approximation of the real oracle is worse than a narrow check that states
    what it covers. This covers the shapes that actually break a plain scalar;
    a wholly quoted value is accepted without inspection, which is the escape
    hatch for a description that genuinely needs a colon.
    """
    findings = []
    skills = root / SHIPPED_CELLS
    if not skills.is_dir():
        return findings
    # Both sources, because both load. A repo-only cell's description sits in
    # every session here exactly as a shipped one does -- the generator copies
    # it onto both runtime surfaces -- so an unparseable or oversized one fails
    # in the same way, silently, and a guard that looked at only one source
    # would be green over half the always-on surface. [#260]
    cell_dirs = [p for p in skills.iterdir() if p.is_dir()]
    repo_cells_dir = root / REPO_CELLS
    if repo_cells_dir.is_dir():
        cell_dirs += [p for p in repo_cells_dir.iterdir() if p.is_dir()]
    for skill_dir in sorted(cell_dirs, key=lambda p: p.as_posix()):
        cell = skill_dir / "SKILL.md"
        if not cell.is_file():
            continue
        rel = cell.relative_to(root).as_posix()
        text = _read_text(cell) or ""
        for key in continued_keys(text):
            findings.append(
                f"cell-frontmatter: {rel}'s {key} continues onto an indented "
                f"line, so a parser reads one value and this repository reads "
                f"the first line -- the description is charged to the always-on "
                f"surface at a fraction of what it costs, and a hazard below "
                f"the first line is invisible to the parse check. Write the "
                f"value on one line"
            )
        fields = _frontmatter_fields(text)
        if fields is None:
            findings.append(
                f"cell-frontmatter: {rel} has no frontmatter block -- the "
                f"runtime indexes it with no name and no description"
            )
            continue
        for key in ("name", "description"):
            value = fields.get(key, "")
            if not value.strip():
                findings.append(
                    f"cell-frontmatter: {rel} declares no {key}"
                    + (" -- a cell with no description has no trigger"
                       if key == "description" else "")
                )
                continue
            hazard = _plain_scalar_hazard(value)
            if hazard:
                findings.append(
                    f"cell-frontmatter: {rel}'s {key} will not parse -- {hazard}. "
                    f"Reword to avoid the construct, which is what every other "
                    f"cell does. Quoting also works but is the harder path: a "
                    f"single-quoted value must double every interior ', and "
                    f"most descriptions here carry one. Unparseable "
                    f"frontmatter loads as empty metadata -- no name, no "
                    f"description, no trigger, silently"
                )
            elif key in CELL_FIELD_MAX_CHARS:
                allowed = CELL_FIELD_MAX_CHARS[key]
                if len(value) > allowed:
                    findings.append(
                        f"cell-frontmatter: {rel}'s {key} is {len(value)} "
                        f"chars, maximum is {allowed} -- "
                        + ("every session here pays for it, invoked or not"
                           if rel.startswith(REPO_CELLS + "/") else
                           "every adopter pays for it in every session, "
                           "invoked or not")
                    )
        name = fields.get("name", "").strip().strip("'\"")
        if name and name != skill_dir.name:
            findings.append(
                f"cell-frontmatter: {rel} declares name '{name}' but sits in "
                f"'{skill_dir.name}/' -- the runtime addresses it by one of them"
            )
    return findings


def continued_keys(text: str) -> list[str]:
    """Keys whose value continues onto a following, more-indented line.

    This reader takes one line per key while YAML may continue a plain scalar
    on indented lines. Reject the construct because otherwise length and scalar
    safety checks inspect only the first line and the runtime may see another
    value or empty metadata.
    """
    block = _frontmatter_block(text)
    if block is None:
        return []
    continued, last_key = [], None
    for line in block.splitlines():
        if not line.strip():
            last_key = None
            continue
        if line[:1].isspace():
            if last_key is not None and last_key not in continued:
                continued.append(last_key)
            continue
        key, sep, _ = line.partition(":")
        last_key = key.strip() if sep and key.strip() else None
    return continued


def _frontmatter_block(text: str) -> str | None:
    """The frontmatter's own lines, opener and terminator excluded."""
    if not text.startswith("---"):
        return None
    end = text.find(chr(10) + "---", 3)
    return None if end == -1 else text[3:end]


def _frontmatter_fields(text: str) -> dict[str, str] | None:
    """Top-level `key: value` pairs of a leading frontmatter block, unparsed."""
    if not text.startswith("---"):
        return None
    end = text.find(chr(10) + "---", 3)
    if end == -1:
        return None
    fields: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if not line.strip() or line[:1].isspace():
            continue
        key, sep, value = line.partition(":")
        if sep and key.strip():
            fields[key.strip()] = value.strip()
    return fields


# Closure, not endpoints. `value[0] == value[-1]` admitted every wrapper that
# was not actually closed: `'it's'` opens and closes with a quote and is three
# scalars to a parser. That hole was reachable by following this guard's own
# advice, on any description carrying an apostrophe -- which is most of them.
# YAML 1.2 ns-plain-first: `-`, `?` and `:` may open a plain scalar when a
# non-space follows -- `-portable` is lawful, `- portable` is a sequence
# entry. The other fourteen may not open one in any position. The split is
# justified by what the value LOADS as, never by the vendor validator,
# which returns 0 for all fourteen under LF: `#x` and `&x` load as null
# there, silently, which is the metadata loss this guard exists to catch.
_PLAIN_FIRST_ALWAYS = ",[]{}#&*!|>%@`"
_PLAIN_FIRST_IF_SPACED = "-?:"

_SQ_CLOSED = re.compile(r"'(?:[^']|'')*'")
_DQ_CLOSED = re.compile(r'"[^"\\]*"')


def _plain_scalar_hazard(value: str) -> str | None:
    """Why this value would not survive as an unquoted YAML plain scalar."""
    if value[:1] == "'":
        if _SQ_CLOSED.fullmatch(value):
            return None  # closed, interior quotes doubled: not read as plain
        return ("it opens with a quote but is not a closed single-quoted "
                "scalar -- an interior ' must be doubled ('')")
    if value[:1] == '"':
        # A backslash is refused rather than parsed: YAML 1.2 admits a fixed
        # escape set, so `\x` is invalid where a permissive `\\.` would accept
        # it. No shipped description opens with a quote, so the strictness is
        # free today and errs toward the side that fails loudly.
        if "\\" in value:
            return ("escape sequences in a double-quoted value are not checked "
                    "here -- reword, or single-quote it with interior ' doubled")
        if _DQ_CLOSED.fullmatch(value):
            return None
        return "it opens with a quote but is not a closed double-quoted scalar"
    first = value[:1]
    if first in _PLAIN_FIRST_ALWAYS:
        return f"it opens with the YAML indicator '{first}'"
    if first in _PLAIN_FIRST_IF_SPACED and (len(value) == 1
                                            or value[1] in " \t"):
        return (f"it opens with the YAML indicator '{first}' with nothing "
                f"non-space after it")
    if ": " in value:
        return "it contains an unquoted ': ', which ends a plain scalar"
    if value.endswith(":"):
        return "it ends with ':', which reads as a mapping key"
    if " #" in value:
        return "it contains ' #', which starts a YAML comment"
    return None


def check_charter_cell(root: Path) -> list[str]:
    """The single shipped charter source exists and keeps all binding prose.

    Repository adoption tells a session to load this cell completely before
    substantive work. Depth under the charter would therefore be available but
    not binding, so this check keeps the source both singular and complete.

    Deliberately not checked: that the charter carries a fixed item count. That
    couples a machine check to editable governing prose and would go stale on
    the first lawful edit -- priced out in review, and the price holds.
    """
    findings = []
    charter = root / CHARTER
    if not charter.is_file():
        findings.append(
            f"charter-cell: {CHARTER} is missing -- an adopting repository "
            "cannot load the practice's binding rules"
        )
    elif not _frontmatterless(_read_text(charter) or "").strip():
        findings.append(
            f"charter-cell: {CHARTER} has no body below its frontmatter"
        )

    # Compared by path, not basename: `references/SKILL.md` shares the name
    # and is exactly what an author following `skills/authoring`'s depth
    # instruction would create.
    charter_file = root / CHARTER
    stray = sorted(
        q.relative_to(root).as_posix()
        for q in charter_file.parent.rglob("*")
        if q.is_file() and q != charter_file
    ) if charter_file.parent.is_dir() else []
    if stray:
        # A binding rule routed into the charter's own references/ would escape
        # the complete load the adoption instruction requires. The charter
        # routes content out, never down.
        findings.append(
            f"charter-cell: the charter cell carries {stray} -- only SKILL.md "
            f"is adopted, budgeted, and read completely, so anything else "
            f"there is binding prose the adoption instruction does not reach"
        )
    return findings


def check_docstring_control_chars(root: Path) -> list[str]:
    """No docstring's compiled value holds a control character but LF or TAB.

    A docstring is not raw, so `\\r` written in one **is** a carriage return at
    runtime -- reaching `pydoc`, `help()`, `inspect.getdoc` and any tooltip,
    where a bare CR makes a terminal overwrite the line it sat on. The prose
    here names control characters constantly, because the practice's own rules
    are about them, so the escape and the character are one keystroke apart and
    the source looks identical either way.

    It has caught control bytes in a decision row and in compiled docstrings.
    Instances are named rather than counted because the count changes whenever
    another instance lands.

    It reads the **compiled** value, not the source, which is the whole point:
    the bytes on disk were clean in the second instance and the runtime value
    was not. A scan for carriage-return bytes catches the first instance and
    neither of the others.

    LF and TAB are exempt because prose is written in lines and indented. Every
    other `Cc` character is banned outright, and **there is no sanctioned escape
    hatch here, unlike `check_emitted_ascii`'s.** That check's live tension is
    `chr()` in *code*, which code can call; a docstring is a literal and calls
    nothing, so `chr(13)` written in one is four characters of prose. An earlier
    version of the finding message offered it anyway -- a remedy that cannot be
    applied where the message names it, which is a fix that does not fix.
    Where the character itself is genuinely meant, it belongs in code.
    """
    findings = []
    candidates = [
        path for path in _python_files(root)
        if ".git" not in path.parts
    ]
    ignored = _git_ignored(root, candidates)
    # Line feed and tab are how prose is written; every other Cc character
    # is one. `Cc` rather than `point < 32` because DEL and the C1 block
    # (U+007F-U+009F) are control characters too -- U+0085 is a line break
    # to `str.splitlines()`, so it mis-renders anything paginating a
    # docstring -- and the stated rule said "control character", not
    # "below U+0020".
    allowed = {10, 9}
    for path in candidates:
        if path in ignored:
            continue
        rel_file = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_bytes().decode("utf-8-sig"))
        except (UnicodeDecodeError, SyntaxError):
            # check_emitted_ascii walks the same files and reports both, so a
            # second message here would be one defect stated twice.
            continue
        except OSError:
            # Reported by check 16 for the same reason and on the same walk,
            # so this one stays silent rather than stating it twice -- but it
            # must not raise, which it did. [PR #247 review, post-fix 5]
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                     ast.AsyncFunctionDef)):
                continue
            doc = ast.get_docstring(node, clean=False)
            if not doc:
                continue
            # `ast.Module` carries no `lineno`, and this used to format it
            # unguarded: a control character in a *module* docstring -- which is
            # exactly the shape this check teaches about -- raised out of
            # `run()`, so the mandated first step of the flow answered with a
            # traceback and none of the other checks' findings.
            line = node.body[0].lineno
            owner = getattr(node, "name", "module")
            for point in sorted({ord(c) for c in doc} - allowed):
                if unicodedata.category(chr(point)) != "Cc":
                    continue
                findings.append(
                    f"docstring-control-char: {rel_file}:{line} "
                    f"({owner}) holds U+{point:04X} in its docstring -- a "
                    f"docstring is not raw, so an escape written there is the "
                    f"character at runtime; double the backslash. A docstring "
                    f"cannot build one, being a literal: where the character "
                    f"itself is meant, it belongs in code and not in prose"
                )
    return findings

# What the guards do not read. **Two populations, because the two guards skip
# for two different reasons, and one list conflated them.**
#
# **The frozen archive** is history rather than a live format (D-74), and
# nothing in it can newly appear. Both guards skip it: a finding inside a file
# that may not change is a red no lawful edit can clear, which is the shape
# #224 was about, reinstated by a guard rather than by a comparison.
# `docs/architecture/adr/` is a prefix rather than a file -- `AGENTS.md` names
# the ADRs as part of the archive and there are ten of them.
#
# **The append-only records** -- including the closed `docs/reviews.jsonl` and
# `docs/recorded-findings.jsonl` -- are skipped by the prose guard only, and the
# asymmetry is the point. A
# finding must quote the line it names, so a review row about a hollow code
# span holds one: that is intended content, and reporting it would red the
# lint over a file doctrine forbids repairing. **A lone carriage return in
# those files is not content at all.** It is corruption of the row's own
# format -- `{"a": "x<CR>y"}` and a record split across a stray one are both
# invalid JSON -- and #233's motivating instance was exactly a row appended by
# a script whose escapes had become control bytes. Skipping them from the byte
# guard withdrew, for `docs/recorded-findings.jsonl`, the pre-commit catch this
# change's own M2 remedy had just bought. The byte guard still covers each
# record, including the two closed files.
# [PR #247 review, post-fix 1]
FROZEN_ARCHIVE = frozenset({
    "docs/ledger.jsonl",
    "docs/seat-record.jsonl",
    "docs/architecture/constitution-archived.md",
    "docs/architecture/evidence-archived.md",
    "docs/architecture/open-questions-archived.md",
})
FROZEN_PREFIXES = ("docs/architecture/adr/",)
LIVE_RECORDS = frozenset({
    "docs/reviews.jsonl",
    "docs/recorded-findings.jsonl",
})


def _frozen(rel_file: str) -> bool:
    """Whether this path is in the frozen archive, by name or by prefix.

    What **both** guards skip. A new frozen path goes here; a new append-only
    record that is still written to goes in `LIVE_RECORDS` instead.
    """
    return rel_file in FROZEN_ARCHIVE or rel_file.startswith(FROZEN_PREFIXES)


def _unread_as_prose(rel_file: str) -> bool:
    """Whether the prose guard skips this path: frozen, or a live record."""
    return _frozen(rel_file) or rel_file in LIVE_RECORDS


# Git's own binary-detection window, matched deliberately. This module skips
# binary content on a NUL in the first kilobyte everywhere else; check 24 uses
# git's number instead, so lint's answer to "is this text" and git's cannot
# disagree inside the window. A binary whose first NUL falls past 8000 bytes
# still classifies as `-text` and still draws a finding -- unclosable, because
# git's own classification cannot separate it from a lone-carriage-return text
# file, which is the thing the check exists for. Recorded, not fixed.
# [PR #247 review, post-fix 4]
BINARY_WINDOW = 8000

CODE_SPAN = re.compile(r"(?<!`)`([^`]*?)`(?!`)", re.S)


def _prose_files(root: Path):
    """Every file under the repository, `.git` aside, for the caller to filter.

    Walked rather than listed, for the reason `_git_ignored` states on itself:
    a hardcoded skip list makes every future top-level directory silently
    escape. `git ls-files` is wrong here for its reason too -- it lists
    *tracked* files, and a decision entry a session has just written is
    exactly the untracked file these guards exist to catch before it commits.

    A third repository-wide walk, which is one more than there should be.
    `_iter_files` is the same walk without the `.git` clause and is live at
    four call sites, none of which passes the repository root. Recorded rather
    than unified here [PR #247 review, M16].
    """
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        yield path


def _unfenced_text(text: str) -> str:
    """The text with fenced blocks blanked, line numbering preserved.

    A code span inside a fence is being *shown*, not written -- the premise
    checks 5 and 6 already reason from for the name form, and the one this
    guard needs, since a fixture demonstrating the defect has to be able to
    quote it. Blanked rather than dropped so the caller can count lines here
    and have them mean lines in the original.

    **A fence closes only on the same character, at least as long as the one
    that opened it**, and a backtick opener whose info string holds a backtick
    is not a fence at all -- CommonMark's rules, and the ones
    `_unfenced_numbered` already implements for checks 5, 6 and 9. This began
    as an unconditional toggle, which got all three wrong: a ``` line shown
    inside a ```` block ended the fence early and drew a finding against
    lawful displayed prose -- the very construct
    `test_a_fence_closes_only_on_its_own_marker` pins as lawful for the
    sibling checks -- while a `~~~` line inside a backtick block, or a single
    opener whose info string holds a backtick, blanked the rest of the file
    in silence. A genuinely unclosed fence is *not* among them: both
    implementations blank to the end of the document there, and so does
    CommonMark. An earlier version of this sentence named that construct, and
    a reader took it literally and concluded a defect was still open.
    [PR #247 review, post-fix 6]

    **This is a second implementation of one rule, and that is a defect held
    open on purpose.** It shares `FENCE_MARKER` and nothing else; it cannot
    share `_unfenced_numbered` itself, which strips its lines and drops rather
    than blanks them, and unifying the two reaches four other checks. Filed
    [PR #247 review, M4]. **One deliberate divergence to carry into that
    work:** the opener here must begin within three spaces of the margin,
    which is CommonMark's limit and which the sibling does not enforce -- and
    the gate is read before the opener/closer branch, so it governs closing
    fences too, which is also what CommonMark says. Every fence line in this
    repository sits at the margin, so the two agree on every file that exists
    today. **This is a correctness fix the sibling still owes, not a stylistic
    carve-out**: on an indented fence marker `_unfenced_numbered` drops the
    rest of the file where a reference parser reads an indented code block and
    a paragraph, so unifying the two by adopting the sibling's machine would
    regress this check. [PR #247 review, post-fix E3]
    """
    out, opener = [], None
    for raw in text.split("\n"):
        stripped = raw.strip()
        marker = None
        # CommonMark allows an opening fence up to three spaces of indent;
        # a fourth makes the line an indented code block, not a fence.
        if len(raw) - len(raw.lstrip(" ")) <= 3:
            marker = FENCE_MARKER.match(stripped)
        if marker:
            run, info = marker.group(1), marker.group(2)
            if opener is None:
                if not (run[0] == "`" and "`" in info):
                    opener = run
                    out.append("")
                    continue
            elif run[0] == opener[0] and len(run) >= len(opener) and not info.strip():
                opener = None
                out.append("")
                continue
        out.append("" if opener is not None else raw)
    return "\n".join(out)


def check_hollow_code_span(root: Path) -> list[str]:
    """No inline code span holds nothing but whitespace.

    A code span that is all whitespace is prose that lost the character it was
    naming. This repository's prose names control characters constantly --
    whole changes here are about the difference between a carriage-return pair
    and a bare one -- so a sentence explaining a byte, with the byte gone from
    the span that was supposed to show it, reads as finished and says nothing.
    Three instances landed in one pull request, two of them inside the repair
    of the first; one reached a commit and broke a row in the decision index
    [#233].

    **The predicate is non-empty whitespace, and the non-empty half is what
    removes the design call.** The obvious form -- content that strips to
    nothing -- was measured over every tracked file and reported the
    doubled-backtick idiom every time it appears, which is prose about fences
    and entirely lawful. Every one of those has content that is *exactly*
    empty, because the idiom's inner span is the gap between the doubled
    backticks; the real instance's content was a line break. So requiring the
    content to be non-empty separates them on a property rather than on a list
    of call sites, and a list would have gone stale the next time anybody
    wrote about fences.

    **The line number is counted in the blanked text, not the original.**
    `match.start()` is an offset into what `_unfenced_text` returned, and
    blanking shortens every line it touches; counting that offset in the
    original reported a line too early for every file carrying a fence above
    the span -- eight of the eight such files in this repository, measured, at
    the moment the guard shipped. The two texts have the same number of lines
    by construction, which is what makes counting in the blanked one correct.
    [PR #247 review, M3]

    **This is disjoint from check 22, which reads compiled docstrings.** That
    one catches the escape that became the character; this one catches the
    character that went missing. Neither sees the other's instance, which is
    the whole reason the class needed more than one guard.

    A span holding more than one line break is skipped. CommonMark ends a code
    span at a **blank line**, not at a second line break -- and in content that
    is all whitespace, two line breaks put a blank line between them, which is
    why the count is the cheap test for the rule rather than the rule itself.
    """
    findings = []
    candidates = list(_prose_files(root))
    ignored = _git_ignored(root, candidates)
    for path in candidates:
        if path in ignored:
            continue
        rel_file = path.relative_to(root).as_posix()
        if _unread_as_prose(rel_file):
            continue
        text = _read_text(path)
        if text is None:
            continue
        unfenced = _unfenced_text(text)
        for match in CODE_SPAN.finditer(unfenced):
            content = match.group(1)
            if content.count("\n") > 1 or not content or content.strip():
                continue
            lineno = unfenced.count("\n", 0, match.start()) + 1
            shown = "".join(f"U+{ord(c):04X} " for c in content).strip()
            findings.append(
                f"hollow-code-span: {rel_file}:{lineno} has a code span "
                f"holding only whitespace ({shown}) -- a span written to show "
                f"a character it no longer holds. If the character itself is "
                f"meant, name it in words: every attempt to write one into "
                f"this repository's prose so far has produced the character "
                f"instead of the escape"
            )
    return findings


def _lone_cr(data: bytes) -> int | None:
    """Offset of the first carriage return not followed by a line feed.

    **A lone one, not any one.** Git's `text=auto` declines to normalize a
    file for exactly this reason and no other, so `\\r\\n` in a working copy is
    lawful here under [D-186] and must not be read as the defect. Testing for
    any carriage return reported a binary whose only ones were part of pairs
    -- a PDF's own header is a carriage return and a line feed -- with a
    message asserting a lone one it had never looked for. [PR #247 review, M5]
    """
    start = 0
    while True:
        at = data.find(b"\r", start)
        if at == -1:
            return None
        if data[at + 1:at + 2] != b"\n":
            return at
        start = at + 1


def _git_lines(root: Path, args: list[str]) -> list[str] | None:
    """NUL-separated output of one `git ls-files` call, or None if git cannot answer.

    None rather than an empty list, so the caller can tell "git said nothing"
    from "git could not be asked" -- `_git_ignored`'s reason, and the same
    direction of safety: these guards may only ever remove noise.
    """
    try:
        proc = subprocess.run(
            ["git", "ls-files"] + args,
            stdin=subprocess.DEVNULL,
            capture_output=True, text=True, encoding="utf-8",
            cwd=root, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return [row for row in proc.stdout.split(chr(0)) if row.strip()]


def check_committed_carriage_return(root: Path) -> list[str]:
    """No file reaches a commit carrying a lone carriage return.

    `.gitattributes` pins this repository's index to LF, and a text-mode write
    producing CRLF on disk is expected rather than a defect [D-186] precisely
    because that pin normalizes it away. **The pin has one hole and git states
    it plainly: `text=auto` refuses to normalize any file holding a lone
    carriage return.** Such a file is classified as binary and every line
    ending in it commits verbatim -- which is how a decision-index row
    appended by a script whose escapes had become control bytes reached a
    commit, splitting one table row into a truncated row and a
    2,181-character orphan. The lint was green over it, and a repository-wide
    byte scan found it the only such file [#233].

    **It reads the working tree as well as the index, and that is the whole
    point of the guard.** `AGENTS.md` orders the flow build, then this command,
    then commit -- and `persist.py` refuses to run against a pre-loaded index,
    so at the moment the lint runs the index provably does not hold the
    session's work. Reading only the index therefore answered a question about
    the previous commit: the guard could not fire until the run *after* the
    bad bytes had landed, on a file that by then is often a frozen decision
    entry or an append-only record. Every stage of this change's review
    reached it independently, and an earlier commit had already half-closed it
    without noticing the other half. [PR #247 review, M2]

    So three populations are read, in one `ls-files` call each: the index
    copy of a tracked file, the working copy where git classifies it
    differently from the index, and untracked files git is not told to ignore
    -- the last being where a decision entry a session has just written lives,
    which is `_prose_files`' reason for rejecting a tracked-only listing.

    **What the classification cannot do is tell a text file from a binary**,
    so what it flags is confirmed against bytes rather than trusted. Binary
    content is skipped by the NUL rule this module applies everywhere, without
    which the first image committed here goes red for its own file signature.
    `i/none` -- an empty file, or one with no trailing terminator -- is
    lawful and is skipped before any read; the predicate used to flag both and
    pay a subprocess for each, against a docstring claiming nothing was read
    on a lawful tree. [PR #247 review, M5, and `claims-vs-evidence` #3]

    **The finding names the copy and the position.** Naming neither is what
    made an earlier version of this message unusable: it told the reader to
    rewrite a file whose working copy was already clean, so following the
    remedy left the finding standing word for word, which is a fix that does
    not fix. [PR #247 review, M6]

    **Disjoint from check 22 by the tokenizer, not by scope.** Python folds a
    lone carriage return in *source* to a line feed before a docstring
    compiles, so a raw one on disk is invisible to a check reading the
    compiled value. It is not the only such character -- a NUL is invisible
    there too, for its own reason, and check 16 is what reports that file --
    but it is the one this closes.

    Silent when git cannot answer, for `_git_ignored`'s reason: a tree with no
    git is not a tree with a finding, and these guards may only remove noise.
    """
    tracked = _git_lines(root, ["--eol", "-z"])
    untracked = _git_lines(root, ["--others", "--exclude-standard", "-z"])
    if tracked is None or untracked is None:
        return []

    # path -> the copies to read, in report order. The index copy is read
    # through git, because that is the blob a commit would take; a working
    # copy is read off disk.
    candidates: dict[str, list[str]] = {}
    for row in tracked:
        # `i/<eol> w/<eol> attr/<attrs><TAB><path>`. Split on the tab, because
        # the attrs field may be empty and a path may hold spaces.
        fields, _, rel_file = row.partition(chr(9))
        parts = fields.split()
        index_eol, worktree_eol = parts[0], parts[1]
        if _frozen(rel_file):
            continue
        if index_eol not in ("i/lf", "i/none"):
            candidates.setdefault(rel_file, []).append("index")
        if worktree_eol not in ("w/lf", "w/none"):
            candidates.setdefault(rel_file, []).append("working tree")
    for rel_file in untracked:
        if not _frozen(rel_file):
            candidates.setdefault(rel_file, []).append("working tree")

    findings = []
    for rel_file, copies in candidates.items():
        held = []
        for copy in copies:
            if copy == "index":
                try:
                    blob = subprocess.run(
                        ["git", "cat-file", "-p", f":{rel_file}"],
                        stdin=subprocess.DEVNULL,
                        capture_output=True, cwd=root, timeout=60,
                    )
                except (OSError, subprocess.SubprocessError):
                    continue
                if blob.returncode != 0:
                    continue
                data = blob.stdout
            else:
                try:
                    data = (root / rel_file).read_bytes()
                except OSError:
                    continue
            if bytes([0]) in data[:BINARY_WINDOW]:
                continue
            at = _lone_cr(data)
            if at is not None:
                held.append((copy, at, data.count(bytes([10]), 0, at) + 1))
        if not held:
            continue
        # One finding per path. A file whose index and working copies both
        # hold the byte is one defect, and reporting it twice is the shape
        # the sibling guard's own skip exists to stop. Anchored on the
        # working copy where both hold it, because that is the one a reader
        # can edit.
        copy, at, lineno = min(held, key=lambda h: h[0] != "working tree")
        both = " (its index copy holds one too)" if len(held) > 1 else ""
        remedy = (
            "if it is text, rewrite it with line feeds and stage it"
            if copy == "working tree"
            else "the working copy is already clean -- stage it"
        )
        findings.append(
            f"committed-carriage-return: {rel_file}:{lineno} holds a lone "
            f"carriage return at byte {at} of its {copy} copy{both} -- git "
            f"refuses to normalize a file holding one, so "
            f"every line ending in it is committed verbatim and renders "
            f"wherever it lands. To clear this, {remedy}; if a control "
            f"character is genuinely meant, it belongs in code and not in prose"
        )
    return findings


def check_marketplace_source(root: Path) -> list[str]:
    """Keep the tradecraft source in the form both plugin runtimes accept."""
    manifest = root / ".claude-plugin" / "marketplace.json"
    if not manifest.is_file():
        return [
            "marketplace-source: .claude-plugin/marketplace.json is missing -- "
            "Codex and Claude must discover the shared tradecraft plugin from "
            "one marketplace manifest"
        ]
    try:
        content = manifest.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [
            "marketplace-source: .claude-plugin/marketplace.json cannot be read "
            f"({exc}) -- the shared tradecraft source cannot be verified"
        ]
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        return [
            "marketplace-source: .claude-plugin/marketplace.json is not valid "
            f"JSON ({exc}) -- the shared tradecraft source cannot be verified"
        ]
    if not isinstance(parsed, dict):
        return [
            "marketplace-source: .claude-plugin/marketplace.json must be an "
            "object containing the shared tradecraft plugin"
        ]
    plugins = parsed.get("plugins")
    if not isinstance(plugins, list):
        return [
            "marketplace-source: .claude-plugin/marketplace.json field "
            "'plugins' must be a list containing tradecraft"
        ]
    findings = []
    found = False
    for plugin in plugins:
        if not isinstance(plugin, dict) or plugin.get("name") != "tradecraft":
            continue
        found = True
        if plugin.get("source") != "./":
            findings.append(
                "marketplace-source: .claude-plugin/marketplace.json tradecraft "
                "source must be the string `./` -- Codex cannot discover the "
                "plugin from Claude's object form"
            )
    if not found:
        findings.append(
            "marketplace-source: .claude-plugin/marketplace.json has no "
            "tradecraft plugin entry -- the shared plugin cannot be discovered"
        )
    return findings


def _where(exc: BaseException) -> str:
    """The innermost frame of a raised check **inside this repository**, as `file:line`.

    Computed from the traceback rather than guessed. Without it the finding
    names an exception and no site -- `AttributeError: 'Module' object has no
    attribute 'lineno'` is the real one this happened with, and it appears
    nowhere a reader could search for. The exception's own message is not
    enough to find the line that raised it, and the traceback that carried it
    is exactly what isolating the check throws away.

    **Innermost under `ROOT`, not innermost.** The last frame is usually
    inside the standard library, and `json/decoder.py:361` is unsearchable
    from here and reads like a repository path. A later session simplifying
    this back to `frames[-1]` would be undoing that, so the scoping is stated
    here rather than left to the loop. [PR #247 review, M8]

    The fallback string is not reachable from the one production caller:
    `run()` calls this from its own `except`, so `lint.py`'s frame is always
    on the traceback and always under `ROOT`. It exists for a caller that has
    neither, and says so rather than naming a frame it never found.
    """
    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
        try:
            where = Path(frame.filename).resolve().relative_to(ROOT).as_posix()
        except (ValueError, OSError):
            continue
        return f"{where}:{frame.lineno}"
    return "no frame inside this repository"


def run(root: Path) -> list[str]:
    """Every check, each isolated, findings in report order.

    **A check that raises is reported, never raised.** This used to be one `+`
    chain over every check, so an exception in any one of them propagated out
    of `main()` to the console -- after the checks before it had already
    computed their findings, which were discarded unprinted. The one command
    the flow mandates between an edit and a commit then answered with a
    traceback naming an internal helper instead of a list naming the tree, and
    a session had no way to tell a clean tree from a filthy one.

    Observed live: a check formatted `node.lineno` on an `ast.Module`, which
    has none, and took the other checks' findings with it. Reporting keeps the
    remaining work going and leaves the reader what those checks found.

    **The finding claims only what was computed.** It names the check, the
    exception and the frame that raised -- and says the check's territory went
    unchecked, which is the honest statement. It does not say the rest of the
    tree is clean, and it does not guess what the check would have found: that
    is the trap `check_emitted_ascii`'s docstring records, a guard's message
    asserting something it never computed. A session met a lawful fixture
    there, was told a false thing about it, and reasoned correctly from the
    falsehood.

    The finding is a finding like any other, so the exit code is non-zero even
    when nothing else reported. A raising check that exited 0 would be read as
    a clean tree, which is the failure this exists to end rather than relocate.
    """
    # This wrapper is an invocation too: the memo the shipped helper keeps is
    # per-run, and the caller that drives this in-process over mutated trees
    # reaches it through here. [#649]
    reset_ignored_memo()
    findings: list[str] = []
    for check in CHECKS:
        try:
            findings.extend(check(root))
        except Exception as exc:  # noqa: BLE001 -- reported, never raised
            findings.append(
                f"check-raised: {check.__name__} raised "
                f"{type(exc).__name__} at {_where(exc)} ({exc}) -- that check "
                f"reported nothing, so what it covers is unchecked and this "
                f"run does not say the tree is clean. Every other check's "
                f"findings stand and are listed with this one"
            )
    return findings


# The one lawful owner of the cell-body strip, and the body strips recorded as
# lawful beside it. The owner is exempt as a whole file -- the engine may hold
# helpers, and deciding which of its names are lawful is a design call this
# check does not make; a second strip landing there is guarded by nothing,
# which is said here rather than left to be discovered. Recorded entries are
# (path, qualified name), so an exempt name reused on a class or in a nested
# scope is not thereby exempt. What the suite pins is this set's exact
# membership, which stops an exemption being added quietly to clear a red; it
# is not a ratchet, and nothing reports an entry that has gone stale.
BODY_STRIP_OWNER = "skills/authoring/scripts/figures.py"
BODY_STRIP_RECORDED = {
    # A guard that imported from the tree it audits could not report on a tree
    # whose authoring cell is broken or absent, which is the tree this check is
    # most needed on. tools/tests/test_repo_figures.py pins it against the
    # engine's over the real cells, so the two cannot drift unnoticed.
    ("tools/lint.py", "_frontmatterless"),
}


def _is_marker(value: object) -> bool:
    """Whether a literal carries a frontmatter marker, in str or bytes form."""
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    return isinstance(value, str) and "---" in value


def _marker_names(tree: ast.Module) -> set[str]:
    """Module-level names bound to a marker literal.

    A body-strip detector must follow a marker hoisted to a constant or a
    mechanical refactor would silently defeat the check.
    """
    names: set[str] = set()
    for node in tree.body:
        # An annotated binding and a tuple binding are the same hoist wearing
        # different syntax, and both are written in this repository.
        if isinstance(node, ast.AnnAssign):
            if (isinstance(node.value, ast.Constant) and _is_marker(node.value.value)
                    and isinstance(node.target, ast.Name)):
                names.add(node.target.id)
            continue
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                if _is_marker(node.value.value):
                    names.add(target.id)
            elif isinstance(target, ast.Tuple) and isinstance(node.value, ast.Tuple):
                for name, value in zip(target.elts, node.value.elts):
                    if (isinstance(name, ast.Name) and isinstance(value, ast.Constant)
                            and _is_marker(value.value)):
                        names.add(name.id)
    return names


def _marker_arg(call: ast.Call, marker_names: set[str]) -> bool:
    """Whether any argument of a call carries a frontmatter marker.

    Keywords are read as well as positionals: a split naming its separator by
    keyword is the same call, and a guard reading only positionals is defeated
    by valid syntax.
    """
    for arg in list(call.args) + [kw.value for kw in call.keywords]:
        for child in ast.walk(arg):
            if isinstance(child, ast.Constant) and _is_marker(child.value):
                return True
            if isinstance(child, ast.Name) and child.id in marker_names:
                return True
    return False


def _is_tail_slice(node: ast.Subscript) -> bool:
    """Whether a subscript takes everything after a point.

    This is the whole discriminator between the two things that look alike. A
    body strip takes the unbounded tail below the frontmatter; a *field* read
    takes the bounded head between the markers, and an ordinary index is
    neither. A check that cannot tell them apart reddens lawful frontmatter
    readers and sends them to a strip that discards the fields they want.
    """
    return isinstance(node.slice, ast.Slice) and node.slice.upper is None


def _own_nodes(scope: ast.AST) -> list[ast.AST]:
    """Every node belonging to this scope, excluding any nested scope's own.

    Without this an enclosing function inherits its nested function's hit, and
    one defect is reported twice -- the first naming a function that holds none
    and cannot be lawfully exempted without exempting everything under it.
    """
    nested: list[ast.AST] = [
        child
        for child in ast.walk(scope)
        if child is not scope
        and isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
    ]
    disowned = {id(node) for parent in nested for node in ast.walk(parent)}
    return [child for child in ast.walk(scope) if id(child) not in disowned]


def _hand_rolled_frontmatter_split(
    nodes: list[ast.AST], marker_names: set[str]
) -> bool:
    """Whether these nodes test for a marker and take the body below it.

    Two properties are required of every hit and a third of one branch. The
    marker and the slice must be *connected*, or every long function that
    merely mentions a marker reads as a strip; and the receiver is matched
    structurally rather than by name, so an attribute or a chained call is not
    a free pass. On a slice of the *tested* text the third applies: it must be
    an unbounded tail, which is what separates taking the body below the
    frontmatter from reading the fields between the markers. **On a piece of a
    marker split it does not** -- `split(m, 2)[2]` is an index rather than a
    slice, so requiring a tail there would lose the cheapest wrong expression
    there is. The cost of that asymmetry is stated plainly: a field read
    spelled as `split(m, 2)[1]` is reported, and the finding message names the
    lawful spelling so the reader has somewhere to go.

    What this reaches is a marker -- literal, or a module-level name bound to
    one -- tested or split, and a subscript, **within a single scope**. The
    bound is that class, not a list of tricks. Outside it, and out of reach at
    any price this check is worth: a marker test in one scope with the slice in
    another; an algorithm that compares rather than splits, such as iterating
    lines to the closing marker; a marker held on a class attribute; a regex
    strip; `pop()` on a split result; a partition tail bound to a throwaway
    name, which is the deliberate trade at the partition branch below; and
    `list.index`, which no AST pass can tell from `str.index`. A bound nobody
    writes down is a bound the next reader assumes away.
    """
    tested: set[str] = set()
    split_names: set[str] = set()
    sliced_calls: list[ast.Call] = []

    for child in nodes:
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
            if not _marker_arg(child, marker_names):
                continue
            if child.func.attr in ("startswith", "find", "index", "rfind"):
                tested.add(ast.dump(child.func.value))
            elif child.func.attr in ("split", "rsplit", "partition", "rpartition"):
                sliced_calls.append(child)
        if isinstance(child, ast.Assign) and isinstance(child.value, ast.Call):
            call = child.value
            if (
                isinstance(call.func, ast.Attribute)
                and call.func.attr in ("split", "rsplit", "partition", "rpartition")
                and _marker_arg(call, marker_names)
            ):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        split_names.add(target.id)
                    # `head, sep, tail = text.partition(marker)` produces no
                    # subscript at all, so the shape below never sees it. The
                    # tail element is the body; a field read binds it to a
                    # throwaway and uses the head, which is why the name being
                    # a real one is what separates the two.
                    elif (
                        isinstance(target, ast.Tuple)
                        and call.func.attr in ("partition", "rpartition")
                        and len(target.elts) == 3
                        and isinstance(target.elts[2], ast.Name)
                        and not target.elts[2].id.startswith("_")
                    ):
                        return True

    for child in nodes:
        if not isinstance(child, ast.Subscript):
            continue
        base = child.value
        # A piece of a marker split is the body by construction; which piece
        # is not something this check second-guesses.
        if isinstance(base, ast.Name) and base.id in split_names:
            return True
        if isinstance(base, ast.Call) and any(base is call for call in sliced_calls):
            return True
        # A slice of the tested text is the body only when it is the tail.
        if ast.dump(base) in tested and _is_tail_slice(child):
            return True
    return False


def _qualified_scopes(tree: ast.Module):
    """Every function and lambda in a module, paired with its qualified name."""
    def walk(node: ast.AST, prefix: str):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + child.name
                yield name, child
                yield from walk(child, name + ".")
            elif isinstance(child, ast.ClassDef):
                yield from walk(child, prefix + child.name + ".")
            elif isinstance(child, ast.Lambda):
                yield prefix + "<lambda>", child
            else:
                yield from walk(child, prefix)
    yield from walk(tree, "")


def hand_rolled_strips(tree: ast.Module) -> list[tuple[str, int]]:
    """Every scope in a module that hand-rolls a frontmatter body strip.

    The single owner of the per-file sweep. `check_body_strip_owner` reports
    what this returns, and `tools/figures.py --body-strip-scan` sizes the
    corpus that check skips with it. Two copies of this loop drifted the
    moment a module-scope pass was added to one of them, and the figure that
    sized the blind spot then read low -- which is the defect this check is
    itself about, one layer down.

    A `<module>` entry carries line 0: module scope has no line of its own.
    """
    markers = _marker_names(tree)
    hits = [
        (name, node.lineno)
        for name, node in _qualified_scopes(tree)
        if _hand_rolled_frontmatter_split(_own_nodes(node), markers)
    ]
    if _hand_rolled_frontmatter_split(_own_nodes(tree), markers):
        hits.append(("<module>", 0))
    return hits


def check_body_strip_owner(root: Path) -> list[str]:
    """No module hand-rolls the cell-body strip the authoring engine ships.

    "The character count of the body below the frontmatter" has three
    plausible implementations here, and the cheapest is the wrong one: a strip
    of your own passes the lint and the suite while measuring something other
    than what the guards judge. A cold consumer on PR #186 reached the right
    one only by opening a sibling tool's docstring, and said that a session
    going straight from AGENTS.md to code would have written its own (#190).
    The rule was enforced against the two implementations that already existed
    and against a third by nothing -- and a third was in the tree:
    tools/check_codex_compat.py kept the two newlines the engine strips.

    Module scope and lambdas are read as well as functions, because moving a
    strip out of a `def` is the cheapest way to silence a check that visits
    only functions.

    Test files are out of scope: they build frontmatter fixtures rather than
    measure with them. `python tools/figures.py --body-strip-scan` reports what
    this predicate finds in that excluded corpus on whatever tree you are on --
    that command, and not a number written here, is what a session revisiting
    the exclusion runs. Read its output with the predicate's asymmetry above in
    mind: a hit is not by itself a hand-rolled strip, and the one this tree
    reports is a field rewrite over a list of lines.
    """
    findings: list[str] = []
    for dirname in SHIPPED_DIRS + tuple(sorted(REPO_ONLY_NAMES)):
        base = root / dirname
        if not base.is_dir():
            continue
        for path in _iter_files(base):
            if path.suffix != ".py" or "__pycache__" in path.parts:
                continue
            if path.name.startswith("test_") or "tests" in path.parts:
                continue
            rel = path.relative_to(root).as_posix()
            if rel == BODY_STRIP_OWNER:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                # check_emitted_ascii reports the unparseable file, as it does
                # for the three sibling AST checks. A second report of one
                # broken file under a second name locates nothing new.
                continue
            for name, lineno in hand_rolled_strips(tree):
                if (rel, name) in BODY_STRIP_RECORDED:
                    continue
                where = f"{rel}:{lineno} {name}()" if name != "<module>" else (
                    f"{rel} at module scope")
                findings.append(
                    f"body-strip: {where} splits a frontmatter marker by hand "
                    f"-- the body strip is {BODY_STRIP_OWNER}'s "
                    f"`frontmatterless`, so a figure cannot drift from the "
                    f"guard judging it. Reading the frontmatter *fields* is a "
                    f"different job this check cannot always tell apart: take "
                    f"the bounded head off the tested text, as "
                    f"tools/lint.py's `_frontmatter_fields` does, and this "
                    f"check leaves it alone"
                )
    return findings


def check_depth_index(root: Path) -> list[str]:
    """Every depth file a cell holds is named in that cell's body, and back.

    `cell-structure.md` makes the index the authority on what depth a cell has,
    and an authority nothing checks is a list that goes stale the first time a
    file is added under a deadline. Two directions, and they fail differently.

    An **orphan** -- a `references/` file no body names -- is the silent half,
    and it is this guard's own. It loads for nobody, costs nothing anyone
    measures, and is found only by enumerating the directory, which is what no
    reader does. `check_cell_references` cannot see it: that guard resolves
    pointers that exist, and an orphan is the absence of one.

    A **dangling** entry is reported only in the form the sibling guard skips.
    `check_cell_references` already reds on a relative `references/x.md` that
    does not resolve, and reporting it here too would price one defect as two
    -- which that guard's own comment refuses. What it skips is the repo-root
    form, `skills/<cell>/references/x.md`, which it reads as somebody else's
    tree. That form is this half's, and only that form.

    **A path naming another cell's depth is that cell's business, not this
    one's.** Attributing it here invents a dangling entry against the naming
    cell and masks a real orphan of the same basename in it.

    The check is naming, not shape: whether the entries are collected into one
    table is the standard's business and a reader's judgment, while whether
    every depth file is reachable at all is a fact, and a fact is what a guard
    is for. This is the floor beneath that standard, not the standard.
    """
    findings = []
    for parent in ("skills", "docs/cells"):
        base = root / parent
        if not base.is_dir():
            continue
        for cell in sorted(d for d in base.iterdir() if d.is_dir()):
            skill = cell / "SKILL.md"
            depth_dir = cell / "references"
            if not skill.is_file() or not depth_dir.is_dir():
                continue
            body = _frontmatterless(skill.read_text(encoding="utf-8", errors="replace"))
            rel = f"{parent}/{cell.name}"

            # **Both separators, like REFERENCES_REF.** A pointer written
            # `references\\detail.md` is lawful here and a forward-slash-only
            # match misses it -- which does not merely fail to check that
            # pointer, it reports the file it names as an orphan. Captures are
            # normalised so the comparison against the directory is one shape.
            def _named(pattern):
                return {m.replace("\\", "/")
                        for m in re.findall(pattern, body)}

            # Relative mentions belong to this cell by construction.
            bare = _named(r"(?<![\w/.\\-])references[\\/]([A-Za-z0-9._/\\-]+\.md)")
            # Rooted mentions belong to whichever cell they name; only this
            # cell's count here, and only they can be reported dangling.
            rooted = _named(
                rf"(?<![\w/.\\-]){re.escape(rel)}[\\/]references[\\/]"
                rf"([A-Za-z0-9._/\\-]+\.md)")

            named = bare | rooted
            present = {f.relative_to(depth_dir).as_posix()
                       for f in depth_dir.rglob("*.md")}

            for orphan in sorted(present - named):
                findings.append(
                    f"depth-index: {rel}/references/{orphan} is named nowhere in "
                    f"{rel}/SKILL.md, so nothing routes a reader to it -- add its "
                    f"entry to the cell's index, or delete the file")
            for dangling in sorted(rooted - present):
                findings.append(
                    f"depth-index: {rel}/SKILL.md names "
                    f"{rel}/references/{dangling}, which does not exist -- fix "
                    f"the entry or restore the file")
    return findings


CHECKS = (
    check_zone_wall,
    check_harness_tokens,
    check_charter_cell,
    check_cell_frontmatter,
    check_sideways_deps,
    check_cell_references,
    check_depth_index,
    check_doctrine_citations,
    check_doctrine_references,
    check_doctrine,
    check_decision_index,
    check_entry_references,
    check_emitted_ascii,
    check_docstring_not_piped,
    check_stdio_wired,
    check_subprocess_streams,
    check_docstring_control_chars,
    check_hollow_code_span,
    check_committed_carriage_return,
    check_marketplace_source,
    check_body_strip_owner,
)


def pointer_reach_note(root: Path) -> str:
    """Report each cell's transitive pointer reach with its measurement basis."""
    try:
        spec = importlib.util.spec_from_file_location(
            "repo_figures_reach", root / "tools" / "figures.py"
        )
        figures = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(figures)
        rows = figures.pointer_reach_rows(root)
        if not rows:
            return "pointer reach here: no cells in either cell source"
        return (
            "pointer reach here, largest first -- " + figures.REACH_BASIS + ":"
            + chr(10) + figures.pointer_reach_block(rows)
        )
    except Exception as exc:  # noqa: BLE001 -- reported, never fatal
        return f"pointer reach: not derived ({type(exc).__name__}: {exc})"


def main() -> int:
    utf8_stdio()
    findings = run(ROOT)
    for finding in findings:
        print(finding)
    print(pointer_reach_note(ROOT))
    print(f"lint: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
