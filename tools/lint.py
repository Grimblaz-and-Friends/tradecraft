#!/usr/bin/env python3
"""tradecraft packaging lint — enforcement for the doctrine's checkable subset.

Checks:

  1. zone wall: no file in the shipped zone may reference the repo-only zone
     (docs/, tools/, .github/) by any path form — rooted, relative (../ or ./),
     backslashed, or case-shifted. Full web URLs are lawful: they resolve for
     consumers; repo paths do not.
  2. harness tokens: no shipped file names a harness-specific
     path token (${CLAUDE_PLUGIN_ROOT} and kin). Not because they fail --
     Claude Code substitutes them into a skill's body -- but because Codex does
     not, so any such contract binds in one runtime and is dead in the other.
  3. charter cell: the shipped charter exists, has a body, and carries no depth
     files whose binding prose an adopting repository would fail to load.
  4. cell frontmatter: every skill declares a name and a description the
     runtime can parse, each within its field budget. A cell whose description
     is absent or malformed silently never fires.
  5. sideways deps: no skill may reference another skill — by path (rooted or
     relative) or by the name form `<name>` cell — and lib/ and hooks/ may
     reference no skill (deps point down otherwise). The
     charter is exempt in the name form only and as a target from anywhere,
     because an adopting repository loads it before substantive work, so the
     citation costs no second loading and cannot drift like a copied rule.
     Paths between cells stay findings even from the charter, for a reason
     self-containment never covered — a rooted skills/ path does not resolve
     once installed, while the name survives relocation.
  6. cell references: every `<name>` cell reference names a skill that
     exists, and every references/ pointer resolves against the directory of
     the file naming it, so renaming or deleting either cannot silently
     strand the prose that points at it. Scanned over the shipped zone and
     over the doctrine files, which are not cells and may name any -- but a
     name they write strands exactly as a cell's does.

  Checks 5 and 6 split on form, not on check. The *name* form is read
  outside fenced blocks only: a name inside a fence is a spelling being
  shown, as check 8 already reasons about an import. Every *path* form is
  read everywhere, fences included -- check 5's rooted and relative skill
  paths and check 6's references/ pointers alike -- because a path that does
  not resolve is broken whatever encloses it, this repository's fenced blocks
  are calling contracts rather than examples, and checks 1 and 2 already fire
  inside them. Both checks also read one wrap — a line ending in `<name>` whose successor
  begins "cell" — because a reflow is a formatting edit no reviewer inspects
  and it would otherwise silently remove a reference from both checks.
  7. doctrine citations: every [D-N] the doctrine writes names an entry that
     exists. The log's own references are check 12's; a marker in the always-on
     surface was checked by nothing, which the outflow rule makes load-bearing
     by instructing a session to compress prose into one.
  8. doctrine: AGENTS.md exists and stays within budget; CLAUDE.md exists and
     is a live @AGENTS.md import — checked by position (first non-empty line,
     unquoted), because Claude Code skips imports inside code spans and loads
     nothing from an absent file.
  9. doctrine callout: tools/doctrine_callout.py exists and ci.yml still
     declares the job that runs it. The callout cannot catch its own removal,
     because a PR deleting the job touches no doctrine file [D-81].
  10. review index: docs/reviews.jsonl, when present, parses and carries one
     valid row per review. Past the cutover: date, artifact, lane, the
     sustained highs named, the model and runtime that staffed it, report URL,
     and no arithmetic — the key set is closed. Before it: per-seat counts,
     what came of the findings, and the split by consequence shape, which
     reconciles against the disposition counts and is the only cross-total on
     the row that is sound.
 11. decision index: every decision entry has a row in the log's index, and
     every row a file.
 12. entry references: every path reference and relative link a decision entry
     or the log's index writes resolves, is pinned to the commit it shipped at,
     or is recorded with a reason. Unlike check 1, this one reads shape rather
     than any path form: `A/B` is prose, not a reference.
13. emitted ASCII: no Python file states a non-ASCII character in a
    non-docstring string constant. Windows encodes stdout and stderr to the
    locale codepage, pipes included, so a captured em dash garbles in the one
    message a guard exists to deliver. It reads literals, not reachability:
    a filename and a regex source are flagged too, and a character built at
    runtime is out of reach. Docstrings and comments are exempt.
14. docstring not piped: no script passes __doc__ as an argparse
    description. --help writes it to stdout before any stream setup runs,
    which turns the docstring check 12 exempts into locale-encoded output.
15. stdio wired: every script with a main() imports utf8_stdio by that name
    and calls it as the first statement, so runtime data this repository did
    not write reaches the stream protected. Both halves are checked: without
    the import binding, a local no-op with the right name would satisfy the
    call site while setting nothing up. The first statement is a position, and a position is
    exact -- a call after parse_args is one that --help has outrun.
16. project roster: every cell has an entry under .claude/skills/ carrying its
    frontmatter byte for byte, and no entry THIS GENERATOR WROTE names a cell
    that is gone. A file it did not write is not its business: at a name that
    is no cell it draws no finding at all, because that is a project skill in
    the runtime's documented place for one; at a cell's name it is reported
    and never overwritten. The qualifier is load-bearing and was missing --
    an experience session read this line, concluded a hand-written entry was
    a finding, and had to open roster.py to find it was not. That
    directory is the only surface a Claude Code session working in THIS
    repository loads a description from -- the plugin is never installed here
    -- so without it every trigger routed to a description reaches every
    adopter and misses us (#199). Codex is not reached by it and reads cells by
    opening files, which is why the scope is named rather than left universal.
    The expectation is tools/roster.py's own, never recomputed here: a guard
    holding a second definition drifts from the writer it judges.
17. marketplace source: the tradecraft entry's source stays the exact string
    `./`, because Codex cannot discover the plugin from Claude's object form.

The frozen archive (docs/ledger.jsonl, docs/seat-record.jsonl, the pre-reset
constitution) is not validated: it is history, not a live format (D-74).

All shipped files are scanned regardless of extension; binary content (NUL
byte in the first 1KB) is skipped. Invoke as `python <repo>/tools/lint.py`
from any cwd — paths resolve from this file's own location.
Exit 0 when clean, 1 with findings listed one per line.
"""
from __future__ import annotations

import ast
import datetime
import importlib.util
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent

# Shared with the shipped zone, which is the lawful direction: repo-only
# code may import shipped code. Resolved from this file rather than the
# working directory, so the script runs from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from winio import utf8_stdio  # noqa: E402

# Repo-only importing repo-only, resolved from this file rather than the
# working directory. The roster's expected content is the generator's to
# define; check 16 asks it rather than reproducing it.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import roster  # noqa: E402

SHIPPED_DIRS = (
    "skills", "lib", "commands", "agents", "hooks", ".claude-plugin",
)
REPO_ONLY_NAMES = {"docs", "tools", ".github"}

# A shipped calling contract naming a harness token binds in one runtime only.
# Claude Code substitutes `${CLAUDE_PLUGIN_ROOT}` -- and `${CLAUDE_SKILL_DIR}` --
# into a skill's body before the model reads it; Codex substitutes neither,
# and exposes harness-owned roots through runtime-specific mechanisms. Shipped
# contracts carried these tokens before this guard, making them runtime-bound.
# `CLAUDE_SKILL_DIR` is the vendor's own skill-relative placeholder and it
# does expand -- in Claude Code only. It is banned here on the same ground
# the forced output style was rejected: a form that binds in one runtime and
# not the other forks the practice. The `$env:` and `%...%` spellings are the
# ones a Windows author reaches for, on the platform half of CI runs on.
_HARNESS_NAMES = (
    "CLAUDE_PLUGIN_ROOT|CLAUDE_PLUGIN_DATA|CLAUDE_PROJECT_DIR"
    "|CLAUDE_SKILL_DIR|CLAUDE_CONFIG_DIR|CLAUDE_WORKING_DIR"
    "|PLUGIN_ROOT|PLUGIN_DATA|CODEX_HOME"
)
HARNESS_TOKENS = re.compile(
    rf"\$\{{?(?:{_HARNESS_NAMES})\}}?"
    rf"|(?i:\$env:(?:{_HARNESS_NAMES}))"
    rf"|(?i:%(?:{_HARNESS_NAMES})%)"
)
CHARTER = "skills/charter/SKILL.md"
# The always-on surface of a cell, budgeted because every adopter pays for
# it in every session whether or not the cell ever fires. Not #130's
# description standard -- a ceiling is not a standard -- but the ceiling has
# to exist, because moving the charter's budget to its body left the part
# that is genuinely always-on bounded by nothing.
CELL_FIELD_MAX_CHARS = {"name": 64, "description": 700}
CHARTER_IMPORT = f"@{CHARTER}"

# The predecessor's root file passed 30k chars in eight months because every
# incident defaulted to a paragraph. The budget is the structural counterweight;
# the outflow every edit owes is the rule, and this ceiling is only what makes
# an unpaid one visible. [D-184]
# Ratcheted from 8,000 against the size measured at the tree that set it. This
# file shrank through both of its rewrites; what grew through both is the
# always-on surface it belongs to, because prose moved between artifacts and
# each change reported the file it emptied. That is why the figure to watch is
# the total rather than this one -- and why neither is written here: `python
# tools/figures.py` prices this file and that surface against these constants
# on whatever tree you are on, and the headroom this comment used to state was
# false one commit after the change that wrote it landed. Set so roughly one substantial rule
# fits before something has to leave, not so the margin stays comfortable,
# which is the failure mode. It is expected to be tight. The answer to a change
# that wants more is an outflow.
AGENTS_BUDGET_CHARS = 6_000
# The charter is the half that ships, and an adopting repository directs every
# session to load it before substantive work, so it needs the displacement
# pressure more than this repo's own file does, not less.
# Ratcheted from 6,000 against the size measured when it was set, which
# `python tools/figures.py` prices against this constant on whatever tree you
# are on. The margin is smaller than
# the doctrine's because the charter is not audited here -- its prose was
# left untouched deliberately, so the ceiling is the only pressure it gets.
CHARTER_BUDGET_CHARS = 5_600
POINTER_BUDGET_CHARS = 500
# A cell body whose budget is enforced rather than remembered. `authoring`'s
# cap was stated in #169 as that change's own evidence that depth-shedding is
# applicable rather than aspirational -- and enforced by nothing: it lived in a
# command string inside a decision entry that has since frozen. A budget a
# guard does not hold is a budget the next edit does not have. The value is
# the bound #169 declared and held itself under, not a fresh judgement: that
# entry's own derivation command reads `--budget 7359`. The comparison below is
# `>`, so 7,359 itself passes -- the cap admits one character more than the body
# measured before that change, and is not the tighter "no larger than you
# started" it reads like. Nothing has turned on that character yet; it is
# stated because a session raising this constant reads here first. Raising
# it is a decision to be made and recorded, which is what a constant makes visible and a sentence
# in a frozen entry does not. Cells absent from this map are unbudgeted on
# purpose: a number chosen for a cell nobody has argued about would be a
# ruling on its size arriving as a constant.
# `adversarial-review` is the second entry, and the first chosen rather than
# inherited. #184 left it out on the ground that a number for a cell nobody
# has argued about is a ruling arriving as a constant; #177 is that argument,
# and the owner ruled a budget follows the split. The basis is the size the
# split landed at plus about one bullet, which
# `python tools/figures.py --cell skills/adversarial-review/SKILL.md
# --cell-budget 9000` prices against this constant on whatever tree you are on.
# That margin is deliberate in both directions: at zero headroom every
# reword of the body is a constant change, which turns the cap into noise
# nobody reads, while a section-sized regrowth cannot fit under it. The number
# is a ceiling above a measured body, not the measured body, so nothing here
# should be read as "no larger than you started". What it holds is the split's
# own claim: #54's rewrite took the body to 13,721 at the reset (401669f,
# #74) and it regrew 76.0% to 24,155 because nothing failed when it did.
# Re-derive that pair before citing it -- an earlier draft here said 63%,
# which no reset-anchored measurement returns, and the understatement sat
# in the one comment a session reads while about to raise this constant. A body cap is dodgeable by moving prose one directory down,
# which is why tools/figures.py reports the cell's total beside it, unbudgeted
# -- a ceiling on the total would cap depth-shedding itself.
CELL_BODY_BUDGET_CHARS = {
    "skills/adversarial-review/SKILL.md": 9_000,
    "skills/authoring/SKILL.md": 7_359,
}

# The one cell any other cell may reference, and the one cell that may
# reference the others. Self-containment exists to stop loading cost and
# multi-site drift; neither applies here. The charter is always-on in every
# session by construction -- imported by this repository's AGENTS.md and loaded
# by an adopter's repository instruction -- so a cell citing it points at prose
# the reader has already loaded, and a citation cannot fall out of agreement
# the way a second copy can. The exemption is one target at depth one: cells may cite the
# charter and it may cite them, no cell may cite any other, so the shape
# cannot grow into the mesh of mutual references the predecessor accumulated.
CHARTER_CELL = "charter"

ROOTED_ZONE = re.compile(r"(docs|tools|\.github)[\\/]", re.IGNORECASE)
ROOTED_SKILL = re.compile(r"skills[\\/]([\w-]+)[\\/]", re.IGNORECASE)
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
REFERENCES_REF = re.compile(r"(references/[\w.-]+\.md)")
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

DATE_SHAPE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")
# One form rule for every name-shaped field: a lowercase token with no
# whitespace, so one name occupies exactly one bucket and a query over seat
# names enumerates what is actually in use.
TOKEN = re.compile(r"\A[a-z0-9][a-z0-9-]*\Z")

# The doctrine callout's wiring, matched by position rather than by substring:
# a commented-out job still contains every substring it had when it was live.
JOB_HEADER = "  doctrine-callout:"
# All three lawful spellings of the trigger, and none of `pull_request_target`
# (the `\b` cannot end before an underscore). A guard that fails a required
# check on a lawful reformat blocks lawful work, which fails as hard as
# passing unlawful work.
PR_TRIGGER = re.compile(
    r"^\s*pull_request:\s*$|^\s*-\s*pull_request\s*$|^on:.*\bpull_request\b"
)
RUNS_SCRIPT = re.compile(r"^\s+(?:-\s+)?run:\s*python tools[\\/]doctrine_callout\.py\b")
# The event is named; the gate's exact wording is not, so a lawful rewrite
# (adding `&& !draft`, or moving to ${{ }} form) does not fail a required check.
GATED_ON_PR = re.compile(r"^\s+if:.*pull_request")
# The delta's base side reads blobs at another revision, which a shallow clone
# does not have: the read fails, the delta drops out, and the callout states a
# total with no direction while every check stays green. The job cannot go red
# for its own missing figure, so the pin is here. `0` and not a positive depth
# -- a bounded depth is still a shallow clone, and the base sits any distance
# back.
FULL_HISTORY = re.compile(
    r"^\s+fetch-depth:\s*['\"]?0['\"]?\s*(?:#.*)?$"
)
# The delta's *request*, where the pin above is only its precondition. Both
# seams, because neither regex can see the other's: deleting `--base` leaves
# the env line standing, and deleting the env line leaves the run line
# standing while `--base "$BASE_SHA"` expands to `--base ""` -- falsy, so the
# delta drops out with the command still reading correctly. Four one-token
# deletions across these two lines each rendered the callout the review had
# already ruled an unmet criterion, with the whole suite green.
BASE_FLAG = re.compile(
    r"^\s+(?:-\s+)?run:\s*python tools[\\/]doctrine_callout\.py\b.*--base\b"
)
BASE_ENV = re.compile(r"^\s+BASE_SHA:\s*\S")

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
# Declared, not merely present: `lib`, `commands` and `agents` are named in the
# doctrine's shipped zone and hold no file yet. `.claude` is deliberately
# absent though a directory of that name exists locally -- most of it is
# untracked and ungitignored, so resolving against it gave
# `python tools/lint.py` two answers for the same commit depending on whether a
# session had created `.claude/agents`, and the local answer instructed a
# repair that reds CI.
#
# #199 tracked one subtree of it -- `.claude/skills`, the generated roster --
# and that did not change this. The reason is about the rest: a session can
# still drop `.claude/agents` or `.claude/commands` into a working tree, so
# admitting `.claude` as a root would reinstate the two-answers defect for
# every path under it that is not the roster. Admitting the roster alone would
# be a root that is one directory deep, which nothing else here is. Left out,
# with the narrowed reason recorded rather than the old one left standing.
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
}

REVIEW_FIELDS = {"date", "artifact", "lane", "report"}
REVIEW_LANES = {"panel", "routine"}
SEAT_COUNTS = ("raw", "merged", "sustained", "high")

# The row stops carrying arithmetic here. Every count on it was hand-totalled
# and reconciled by hand into a file nobody may edit, and that is this index's
# whole defect record: two
# open issues about values no stage produces, plus reconciliation prose inside
# rows nobody may edit. What a review was worth is read from the report it
# links; how many highs it sustained is the length of `highs`, derived at read
# time from the row rather than transcribed into it.
#
# Grandfathered by POSITION, like the two boundaries above and for the reason
# stated there: a date cutoff is one an experience session reached past in
# eight tool calls. Rows before this index keep the counting shape and its
# validators untouched; from it the counting fields are FORBIDDEN rather than
# optional -- an optional field lets the shape drift back one row at a time,
# and obliges this guard to validate two live shapes for ever. The value is
# the file's row count when this landed, and it moved once before landing:
# reviews closed on `main` while this change was open, and their rows are
# exempt for the same reason every earlier row is -- records are appended,
# never rewritten to suit a schema that arrived after them.
REVIEW_ROWS_QUALITATIVE = 39
# The first qualitative row predates the rule that the index itself carries a
# qualitative external-pass outcome. Preserve it by position; every later row
# names what actually posted without turning the pass into a seat or a count.
REVIEW_ROWS_EXTERNAL_QUALITATIVE = 40
COUNTING_FIELDS = ("seats", "dispositions", "facing")
QUALITATIVE_FIELDS = frozenset(
    {
        "date", "artifact", "lane", "report", "highs", "staffing", "external",
        "notes",
    }
)

# What became of the findings, in the terminal stage's own vocabulary: clause
# (a) dismisses, clause (b) sustains and fixes, routes, or prices out. The row
# copies counts the ruling already produced; it does not derive them.
#
# `dismissed` earns its place as the only field that measures noise. Measuring
# value while never measuring noise is how the predecessor's pipeline could
# only ratchet heavier, and it is near-derivable from merged minus sustained
# but not reliably -- the terminal docket also carries uncarried seat entries,
# which is why the seat counts deliberately do not enforce merged >= sustained.
DISPOSITIONS = ("fixed", "routed", "priced_out", "dismissed")

# Per review rather than per seat: per-seat fields multiply the write cost by
# the panel width, and a mixed panel can record its split in the value -- which
# two of the twenty grandfathered rows would have needed. The keys are closed
# so a per-seat shape cannot enter through `staffing` itself -- not the whole
# key space: a top-level row key and a seat's own counts mapping are
# unvalidated, and closing them was priced out.
STAFFING_FIELDS = ("model", "runtime")

# Where a review's findings landed: on the artifact a consumer will use, or on
# the record of having reviewed it. The population is the one `dispositions`
# counts -- one entry per terminal ruling -- so the two reconcile, which is the
# whole reason the field can be checked at all. The three reports that stated a
# split before this landed each counted a different population -- 26 panel-merged
# findings, 45 rulings, and a 14-to-6 labelled as round one's 20 sustained where
# that report's own table gives round one 17 -- so the trend the record exists to
# show could not be read even by opening all of them.
FACING_FIELDS = ("artifact", "apparatus")

# Forward-only, enforced rather than stated: an optional field can never catch
# its own omission, and a record that silently fails to carry what it promises
# is the defect this closes.
#
# Grandfathered by POSITION, not by date. A date cutoff was written first and an
# experience session found the hole in it within eight tool calls: the session's
# hand reached for "today" before re-reading its brief, and a row dated one day
# early takes both new fields as optional, passes lint in silence, and lands
# pre-schema in a file nobody may edit. It got it right by copying its brief,
# not by understanding. Position cannot be missed by a typo -- the rows that
# existed when this landed are exempt, everything appended after is not.
REVIEW_ROWS_GRANDFATHERED = 20

# `facing` arrives later than `dispositions` and grandfathers at its own
# position, for the same reason and by the same mechanism: the rows extant when
# it landed are exempt, everything appended after is not. Two constants rather
# than one moving constant -- raising a single one would silently un-oblige
# every row between the two boundaries, in a file nobody may edit.
REVIEW_ROWS_FACING_GRANDFATHERED = 31

def _read_text(path: Path) -> str | None:
    """Return decoded text, or None for binary content (NUL in first 1KB)."""
    data = path.read_bytes()
    if b"\0" in data[:1024]:
        return None
    return data.decode("utf-8", errors="replace")


def _iter_files(base: Path):
    for path in sorted(base.rglob("*")):
        if path.is_file():
            yield path


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


def _name_form_is_sideways(own: str | None, target: str) -> bool:
    """Whether naming skill `target` from `own` couples two cells unlawfully.

    The charter's exemption lives here and only here -- in naming a cell, not
    in reaching into one. A path form stays a finding from the charter too,
    for a reason self-containment never covered: a rooted `skills/...` path
    does not resolve once installed, because the cells sit in a plugin cache
    rather than beside the reader. The name survives relocation, which the
    path does not -- note that a runtime may qualify it (Claude Code addresses
    an installed plugin's skills as `<plugin>:<skill>`), so the name is the
    part a reader can still follow, not a string that resolves bare.

    The charter is exempt as a target from another cell because an adopting
    repository has already loaded it. `own is None` is lib/ or hooks/, neither
    of which is a cell, so any skill dependency from either points sideways.
    """
    if own is None:
        return True
    if target.lower() == CHARTER_CELL:
        return False
    if target.lower() == own.lower():
        return False
    return own.lower() != CHARTER_CELL


def check_sideways_deps(root: Path) -> list[str]:
    findings = []
    skills = root / "skills"
    scan: list[tuple[Path, str | None]] = []
    if skills.is_dir():
        for skill_dir in sorted(p for p in skills.iterdir() if p.is_dir()):
            scan.append((skill_dir, skill_dir.name))
    for name in ("lib", "hooks"):
        base = root / name
        if base.is_dir():
            # None: none of these is a skill, so any skill path is sideways.
            scan.append((base, None))

    for base, own in scan:
        for path in _iter_files(base):
            text = _read_text(path)
            if text is None:
                continue
            rel_file = path.relative_to(root).as_posix()
            # The fence exemption is the *name form's* alone. A path inside a
            # fence is not display: this repo's fenced blocks are calling
            # contracts and command lines, check_zone_wall and
            # check_harness_tokens both fire inside them, and
            # test_portability.py reads a cell's script contract through one
            # and requires it to resolve. Exempting paths here would put two
            # guards in one tree disagreeing about what a fence means. What
            # licenses the name form's exemption is different in kind -- an
            # unlawful *name* inside a fence is a spelling being shown, while
            # a path is dead once installed whatever encloses it.
            unfenced = _unfenced_numbered(text)
            for lineno, target in _wrapped_cell_refs(unfenced):
                if not (root / "skills" / target).is_dir():
                    continue
                if _name_form_is_sideways(own, target):
                    findings.append(
                        f"sideways-dep: {rel_file}:{lineno} names skill "
                        f"'{target}' across a line break" + _origin(own, base)
                    )
            for lineno, line in unfenced:
                for match in CELL_REF.finditer(line):
                    target = match.group(1)
                    # Only a name that is actually a cell couples anything; a
                    # backticked word before "cell" that names no skill is
                    # ordinary prose here, and check_cell_references is what
                    # rules on whether it should have resolved.
                    if not (root / "skills" / target).is_dir():
                        continue
                    if _name_form_is_sideways(own, target):
                        findings.append(
                            f"sideways-dep: {rel_file}:{lineno} names "
                            f"skill '{target}'" + _origin(own, base)
                        )
            for lineno, line in enumerate(text.splitlines(), 1):
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
    return findings


DOCTRINE_CITATION = re.compile(r"\[D-(\d+)\]")


def check_doctrine_citations(root: Path) -> list[str]:
    """Every [D-N] the doctrine writes names a decision entry that exists.

    check_entry_references resolves what the decision log itself writes, and
    stops there -- so a marker in the always-on surface resolved to nothing and
    lint stayed green, verified for all four of them. That mattered little
    while the doctrine merely cited; it matters now that the outflow rule
    instructs a session to replace prose with a citation and requires one that
    resolves. A reason compressed into a marker nobody checks is a reason
    deleted on the next renumbering, on the surface every session reads first.

    Scoped to the doctrine files by decision, not by the shipped cells being
    clean: they carry eighteen `[D-N]` markers, and D-173 priced exactly that
    cost rather than arguing it away, on the ground that the party who would
    unknowingly undo the ruling is looking at the cell and not at the log. An
    adopter cannot resolve any of them -- they receive the cells and not the
    decision log -- so widening this guard would either mean stripping reasons
    the practice deliberately kept, or a permanent exemption list. That is the
    owner's call to reopen, not a repair a guard should make on its own; until
    he does, the eighteen are lawful and out of reach here.

    (The zone wall is not what puts them out of reach, whatever the shape of
    the argument suggests: a `[D-N]` marker is not a path and violates no
    zone rule. The reason is the resolution cost above.)
    """
    findings = []
    directory = root / "docs" / "architecture" / "decisions"
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = root / name
        if not path.is_file():
            continue  # its absence is check 8's finding, not this one's
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
    known = {p.name for p in (root / "skills").iterdir() if p.is_dir()} \
        if (root / "skills").is_dir() else set()
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
            lines = _unfenced_numbered(text)
            named = [(n, m.group(1)) for n, line in lines
                     for m in CELL_REF.finditer(line)]
            named += list(_wrapped_cell_refs(lines))
            for lineno, target in sorted(named):
                if target not in known:
                    findings.append(
                        f"cell-reference: {rel_file}:{lineno} names cell "
                        f"'{target}', which is not a skill in skills/"
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
                    if not (path.parent / pointer).is_file():
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
    else:
        size = len(agents.read_text(encoding="utf-8", errors="replace"))
        if size > AGENTS_BUDGET_CHARS:
            findings.append(
                f"doctrine-budget: AGENTS.md is {size} chars, "
                f"budget is {AGENTS_BUDGET_CHARS} -- route content out (skill, decision entry, mechanism)"
            )
    charter = root / CHARTER
    if charter.is_file():
        # The body, not the file: the charter is a cell now, so it carries
        # frontmatter addressed to the runtime's skill index rather than to a
        # session reading the rules. Budgeting the whole file would let a
        # description edit eat the rules' headroom, which is the wrong coupling
        # -- the description has its own always-on cost and its own ceiling
        # above. A standard for what it should say is #130's, and unwritten.
        size = len(_frontmatterless(charter.read_text(encoding="utf-8", errors="replace")))
        if size > CHARTER_BUDGET_CHARS:
            findings.append(
                f"doctrine-budget: {CHARTER}'s body is {size} chars, budget "
                f"is {CHARTER_BUDGET_CHARS} -- route content out"
            )
    # An absent cell is not a budget violation -- a tree without it simply has
    # no such cell, and every minimal fixture is one. What an absent cell WOULD
    # do is silently drop the budget on a rename, so that the map still names a
    # real cell is pinned against this repository's own tree in the suite,
    # where the question has an answer, rather than guessed at here.
    for rel, budget in sorted(CELL_BODY_BUDGET_CHARS.items()):
        cell = root / rel
        if not cell.is_file():
            continue
        size = len(_frontmatterless(cell.read_text(encoding="utf-8", errors="replace")))
        if size > budget:
            findings.append(
                f"doctrine-budget: {rel}'s body is {size} chars, budget is "
                f"{budget} -- shed depth to references/ or route content out; "
                f"`python tools/figures.py --cell {rel} --cell-budget {budget}` "
                f"reports the cell total, which shedding does not reduce"
            )
    # An adopter loads the installed charter because its repository instructions
    # say so. In THIS source repository the local charter reaches the session
    # through an import in a file that is itself imported. Checked by shape
    # rather than by position: unlike CLAUDE.md the
    # import does not lead the file, and a backticked mention imports nothing.
    # Nor does a fenced one -- the same premise, and the guard rejected one
    # spelling of not-bare while accepting the other.
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


def _is_calendar_day(value: str) -> bool:
    """DATE_SHAPE pins the shape; this rejects 2026-13-45 and 2026-02-30."""
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_https_url(value) -> bool:
    """An https URL with a real host.

    `netloc` alone is not that test: it is non-empty for `https://@/x` and
    `https://:443/x`, neither of which names a host a reader can reach.
    `hostname` is None for both. A malformed authority raises from urlsplit,
    which is a failed check rather than a crashed lint.
    """
    if not isinstance(value, str) or not value.startswith("https://"):
        return False
    try:
        return bool(urlsplit(value).hostname)
    except ValueError:
        return False


def _not_a_mapping(row, where: str, findings: list) -> bool:
    """A JSON array or scalar row must be rejected before any field is read."""
    if not isinstance(row, dict):
        findings.append(
            f"{where} is not a JSON object (got {type(row).__name__}) -- a row "
            f"must be a mapping of fields"
        )
        return True
    return False


def check_review_index(root: Path) -> list[str]:
    """One row per review: date, artifact, lane, the staffing, the report URL,
    and — past REVIEW_ROWS_QUALITATIVE — each sustained high named, plus the
    external pass's qualitative outcome from its later boundary, in place of
    the arithmetic the rows before it carry.

    The row is written once when the review ends and never maintained after —
    it exists so process-weight questions are answerable when asked, from the
    reports it links. It answers none of them by itself, which is why it no
    longer totals anything: the counts it used to carry were re-derived by
    nothing and had to be reconciled by hand into a file nobody may edit.
    """
    findings: list[str] = []
    index = root / "docs" / "reviews.jsonl"
    if not index.is_file():
        return findings
    # Rows are counted, not lines: a blank line would otherwise shift every
    # row's position and with it which rows the schema obliges.
    row_index = -1
    for lineno, line in enumerate(
        index.read_text(encoding="utf-8", errors="replace").splitlines(), 1
    ):
        if not line.strip():
            continue
        # Position is the non-blank line's ordinal, counted before the parse: a
        # row that fails to decode would otherwise shift every later row toward
        # exemption, so the finding disappears while it is still actionable and
        # returns later against a row that has landed and cannot be edited.
        row_index += 1
        where = f"review-index: docs/reviews.jsonl:{lineno}"
        # One malformed row must never silence the rest, so both the decode and
        # the per-field checks report rather than raise.
        try:
            row = json.loads(line)
        except Exception as exc:  # noqa: BLE001 - report, never crash the lint
            findings.append(f"{where} is not valid JSON ({type(exc).__name__}: {exc})")
            continue
        try:
            _check_review_row(row, where, findings, row_index)
        except Exception as exc:  # noqa: BLE001 - report, never crash the lint
            findings.append(
                f"{where} could not be fully validated ({type(exc).__name__}: {exc})"
            )
    return findings


def _check_review_row(row, where: str, findings: list, row_index: int) -> None:
    if _not_a_mapping(row, where, findings):
        return
    missing = REVIEW_FIELDS - set(row)
    if missing:
        findings.append(f"{where} missing field(s) {', '.join(sorted(missing))}")
    if "date" in row and (
        not isinstance(row["date"], str)
        or not DATE_SHAPE.match(row["date"])
        or not _is_calendar_day(row["date"])
    ):
        findings.append(f"{where} date '{row.get('date')}' is not an ISO YYYY-MM-DD date")
    if "artifact" in row and (
        not isinstance(row["artifact"], str) or not row["artifact"].strip()
    ):
        findings.append(f"{where} artifact must be a non-empty string naming what was reviewed")
    if "lane" in row and (
        not isinstance(row["lane"], str) or row["lane"] not in REVIEW_LANES
    ):
        findings.append(f"{where} lane '{row.get('lane')}' not in {sorted(REVIEW_LANES)}")
    if "report" in row and not _is_https_url(row["report"]):
        findings.append(
            f"{where} report '{row.get('report')}' must be an https URL to the "
            f"review's report -- the row points at the findings, it does not hold them"
        )
    _check_row_shape(row, row_index, where, findings)
    if "seats" in row:
        _check_seats(row["seats"], where, findings)
    if "highs" in row:
        _check_highs(row["highs"], where, findings)
    _check_external(row, row_index, where, findings)
    _check_dispositions_and_staffing(row, row_index, where, findings)
    _check_facing(row, row_index, where, findings)


def _check_row_shape(row, row_index: int, where: str, findings: list) -> None:
    """Which of the two shapes this row's position obliges.

    Before the cutover a row carries per-seat counts; from it a row carries
    `highs` and no arithmetic at all. Both directions are checked, because a
    guard that only catches the missing field lets the retired shape back in.
    """
    if row_index < REVIEW_ROWS_QUALITATIVE:
        if "seats" not in row:
            findings.append(
                f"{where} missing field 'seats' -- rows before the first "
                f"{REVIEW_ROWS_QUALITATIVE} carry per-seat counts"
            )
        return
    if "highs" not in row:
        findings.append(
            f"{where} missing field 'highs' -- rows past the first "
            f"{REVIEW_ROWS_QUALITATIVE} name each sustained high instead of "
            f"counting anything (a list of strings; empty where none was "
            f"sustained)"
        )
    present = [f for f in COUNTING_FIELDS if f in row]
    if present:
        findings.append(
            f"{where} carries retired counting field(s) {', '.join(present)} -- "
            f"rows past the first {REVIEW_ROWS_QUALITATIVE} carry no arithmetic: "
            f"every count this row used to carry was totalled and reconciled by "
            f"hand into a file nobody may edit. What the review was worth is in "
            f"the report it links"
        )
    # Naming the three retired fields is not the rule -- the same totals under a
    # fresh key are the same frozen arithmetic, and passed clean until this
    # closed. The key set is what makes "no arithmetic" enforceable rather than
    # merely stated; a new field is a decision somebody makes here.
    unknown = sorted(set(row) - QUALITATIVE_FIELDS - set(COUNTING_FIELDS))
    if unknown:
        findings.append(
            f"{where} carries unknown key(s) {', '.join(unknown)} -- past the "
            f"first {REVIEW_ROWS_QUALITATIVE} the row's key set is closed "
            f"({', '.join(sorted(QUALITATIVE_FIELDS))}); arithmetic under a "
            f"fresh name is the arithmetic this cutover retired"
        )


def _check_highs(highs, where: str, findings: list) -> None:
    """Each sustained high, named. The list is the record and its length is the
    count, so nothing here is transcribed and nothing can fail to reconcile.

    An empty list is lawful and means what it says -- a review that sustained
    no high is a valid outcome, and the field cannot express it otherwise.
    """
    if not isinstance(highs, list):
        findings.append(
            f"{where} highs must be a list naming each sustained high "
            f"(got {type(highs).__name__})"
        )
        return
    seen: dict[str, int] = {}
    for position, high in enumerate(highs):
        if not isinstance(high, str) or not high.strip():
            findings.append(
                f"{where} highs[{position}] must be a non-empty string naming "
                f"one sustained high"
            )
            continue
        key = " ".join(high.split()).casefold()
        if key in seen:
            findings.append(
                f"{where} highs[{position}] repeats highs[{seen[key]}] -- the "
                f"list's length is what the record now answers 'how many highs' "
                f"with, so a high credited to several seats is named once, not "
                f"once per credit. A row is appended and never corrected"
            )
        else:
            seen[key] = position


def _check_external(row, row_index: int, where: str, findings: list) -> None:
    """The external pass's qualitative outcome, never its arithmetic."""
    if "external" not in row:
        if row_index >= REVIEW_ROWS_EXTERNAL_QUALITATIVE:
            findings.append(
                f"{where} missing field 'external' -- rows past the first "
                f"{REVIEW_ROWS_EXTERNAL_QUALITATIVE} name the external pass's "
                "qualitative outcome without counts or a panel seat"
            )
        return
    value = row["external"]
    if not isinstance(value, str) or not value.strip():
        findings.append(
            f"{where} external must be a non-empty qualitative string naming "
            "what actually posted -- never a count or a panel seat"
        )


def _check_dispositions_and_staffing(row, row_index: int, where: str, findings: list) -> None:
    """What came of the findings, and who produced them.

    Counts alone answer how many findings a review raised and nothing about
    whether they mattered -- the question three decision entries circle. And
    the skill requires every report to record model and runtime so per-runtime
    evidence can accumulate, which it cannot do anywhere queryable while the
    index drops both.

    Required of every row past the first REVIEW_ROWS_GRANDFATHERED, and
    validated whenever present, so rows already written stay valid untouched. This closes two of
    the four questions #126 raised: it does not verify that a routed finding
    reached its vehicle, which needs the vehicle named, and it detects no
    recurring defect class.
    """
    # `staffing` survives the cutover -- a model and a runtime are facts about
    # who ran the review, not arithmetic about it, and this row is the only
    # queryable home the per-runtime evidence has. `dispositions` does not, so
    # its window closes where the counting shape does; without that it would be
    # required to carry a field it is forbidden to carry.
    required = {
        "dispositions": (
            REVIEW_ROWS_GRANDFATHERED <= row_index < REVIEW_ROWS_QUALITATIVE
        ),
        "staffing": row_index >= REVIEW_ROWS_GRANDFATHERED,
    }
    for field, checker in (
        ("dispositions", _check_disposition_counts),
        ("staffing", _check_staffing),
    ):
        if field not in row:
            if required[field]:
                findings.append(
                    f"{where} missing field '{field}' -- rows past the first "
                    f"{REVIEW_ROWS_GRANDFATHERED} carry it"
                    + (
                        f" ({', '.join(DISPOSITIONS)} counts)"
                        if field == "dispositions"
                        else f" ({', '.join(STAFFING_FIELDS)})"
                    )
                )
            continue
        checker(row[field], where, findings)


def _check_disposition_counts(dispositions, where: str, findings: list) -> None:
    if not isinstance(dispositions, dict):
        findings.append(
            f"{where} dispositions must be a mapping of "
            f"{', '.join(DISPOSITIONS)} to counts"
        )
        return
    missing = set(DISPOSITIONS) - set(dispositions)
    if missing:
        findings.append(
            f"{where} dispositions missing {', '.join(sorted(missing))}"
        )
    for field in DISPOSITIONS:
        if field not in dispositions:
            continue
        value = dispositions[field]
        if not _is_count(value):
            findings.append(
                f"{where} dispositions {field} '{value}' must be a "
                f"non-negative integer"
            )
    unknown = set(dispositions) - set(DISPOSITIONS)
    if unknown:
        findings.append(
            f"{where} dispositions carries unknown key(s) "
            f"{', '.join(sorted(unknown))} -- the vocabulary is the terminal "
            f"stage's own: {', '.join(DISPOSITIONS)}"
        )


def _is_count(value) -> bool:
    """A count, at the bar the seat counts already meet: bool subclasses int,
    so True would otherwise pass as a count of one."""
    return not isinstance(value, bool) and isinstance(value, int) and value >= 0


def _check_facing(row, row_index: int, where: str, findings: list) -> None:
    """The split by consequence shape -- what the review's rulings were about.

    #122 says to watch whether apparatus-facing findings trend down relative to
    findings about the work. The watch item fired on the first full run and
    nothing could measure it, because the split lived only in report prose --
    and two of the five reports that owed it under D-153 did not carry it.

    Required of every row past REVIEW_ROWS_FACING_GRANDFATHERED and validated
    whenever present, so rows already written stay valid untouched.
    """
    if "facing" not in row:
        if (
            REVIEW_ROWS_FACING_GRANDFATHERED
            <= row_index
            < REVIEW_ROWS_QUALITATIVE
        ):
            findings.append(
                f"{where} missing field 'facing' -- rows past the first "
                f"{REVIEW_ROWS_FACING_GRANDFATHERED} carry it "
                f"({', '.join(FACING_FIELDS)} counts, summing to the "
                f"dispositions total)"
            )
        return
    facing = row["facing"]
    if not isinstance(facing, dict):
        findings.append(
            f"{where} facing must be a mapping of "
            f"{', '.join(FACING_FIELDS)} to counts"
        )
        return
    missing = set(FACING_FIELDS) - set(facing)
    if missing:
        findings.append(f"{where} facing missing {', '.join(sorted(missing))}")
    for field in FACING_FIELDS:
        if field in facing and not _is_count(facing[field]):
            findings.append(
                f"{where} facing {field} '{facing[field]}' must be a "
                f"non-negative integer"
            )
    unknown = set(facing) - set(FACING_FIELDS)
    if unknown:
        findings.append(
            f"{where} facing carries unknown key(s) "
            f"{', '.join(sorted(unknown))} -- a consequence lands on the "
            f"artifact or on the record of having reviewed it, and a finding "
            f"citing both is artifact-facing"
        )
    _check_facing_reconciles(row, facing, where, findings)


def _check_facing_reconciles(row, facing, where: str, findings: list) -> None:
    """The one cross-total on this row that is sound.

    The seat counts deliberately carry no invariants against `dispositions`,
    because the two count different populations -- the terminal docket also
    carries uncarried seat entries, and a dismissal was never sustained. This
    one is different by construction: `facing` splits the same rulings
    `dispositions` counts, so a disagreement is an arithmetic error in a row
    about to become permanent, not two populations talking past each other.
    """
    dispositions = row.get("dispositions")
    if not isinstance(dispositions, dict):
        return
    if not all(_is_count(dispositions.get(f)) for f in DISPOSITIONS):
        return
    if not all(_is_count(facing.get(f)) for f in FACING_FIELDS):
        return
    # An unknown key in either mapping carries part of the population into a
    # bucket neither total counts, so the sum is not the writer's arithmetic --
    # and the obvious repair, absorbing the difference, lands a permanently
    # double-counted row. The vocabulary finding already fired; this one would
    # name a total nobody wrote.
    if set(facing) - set(FACING_FIELDS) or set(dispositions) - set(DISPOSITIONS):
        return
    split = sum(facing[f] for f in FACING_FIELDS)
    total = sum(dispositions[f] for f in DISPOSITIONS)
    if split != total:
        findings.append(
            f"{where} facing sums to {split} and dispositions to {total} -- "
            f"both count one entry per terminal ruling, so they reconcile; "
            f"the per-seat columns do not and are not meant to"
        )


def _check_staffing(staffing, where: str, findings: list) -> None:
    if not isinstance(staffing, dict):
        findings.append(
            f"{where} staffing must be a mapping of "
            f"{', '.join(STAFFING_FIELDS)} to names"
        )
        return
    for field in STAFFING_FIELDS:
        value = staffing.get(field)
        if not isinstance(value, str) or not value.strip():
            findings.append(
                f"{where} staffing {field} must be a non-empty string"
            )
    # Deliberately no vocabulary for the *values*: a fixed list would have to be
    # amended before the first review staffed by a new runtime could be recorded
    # at all, and a mixed panel records its split in the value itself. The
    # *keys* are closed, which is what keeps a per-seat shape -- the design this
    # change excluded -- from entering silently through a field nobody validates.
    unknown = set(staffing) - set(STAFFING_FIELDS)
    if unknown:
        findings.append(
            f"{where} staffing carries unknown key(s) "
            f"{', '.join(sorted(unknown))} -- the row names one model and one "
            f"runtime; an uneven panel says so in the value"
        )


def _check_seats(seats, where: str, findings: list) -> None:
    if not isinstance(seats, dict) or not seats:
        findings.append(
            f"{where} seats must be a non-empty mapping of seat name to counts"
        )
        return
    for name, counts in seats.items():
        if not isinstance(name, str) or not TOKEN.match(name):
            findings.append(
                f"{where} seat name '{name}' must be a lowercase token of "
                f"letters, digits and hyphens -- one seat, one bucket"
            )
        if not isinstance(counts, dict):
            findings.append(f"{where} seat '{name}' counts must be a mapping")
            continue
        missing = set(SEAT_COUNTS) - set(counts)
        if missing:
            findings.append(
                f"{where} seat '{name}' missing count(s) {', '.join(sorted(missing))}"
            )
        bad_type = False
        for field in SEAT_COUNTS:
            value = counts.get(field)
            if field in counts and not _is_count(value):
                findings.append(
                    f"{where} seat '{name}' {field} '{value}' must be a "
                    f"non-negative integer"
                )
                bad_type = True
        if bad_type or set(SEAT_COUNTS) - set(counts):
            continue
        raw, merged, sustained, high = (counts[f] for f in SEAT_COUNTS)
        # Both `merged >= sustained` and `raw >= sustained` are deliberately
        # absent [D-102]: the terminal stage's docket carries anything in a
        # seat's report that no merged finding carries, and a declined
        # examination is not a finding, so it is in neither count. A
        # zero-finding seat with one sustained decline is raw 0, sustained 1.
        # `sustained` therefore has no upper bound expressible in these four
        # fields. Re-adding either conjunct looks right and is wrong.
        if not (raw >= merged and sustained >= high):
            findings.append(
                f"{where} seat '{name}' counts are not nested: raw {raw} >= "
                f"merged {merged} and sustained {sustained} >= high {high} "
                f"must hold"
            )


def check_doctrine_callout(root: Path) -> list[str]:
    """The callout must still be wired into CI.

    Its own mechanism cannot catch its own removal: a PR that deletes the job
    touches no doctrine file, so no callout fires, nothing goes red, and
    the mechanism disappears exactly as silently as the CODEOWNERS callout it
    replaced. Loud-on-failure and pinned-when-present are different guarantees
    and the script only carries the first. This is the second, and it lives in
    the lint because the lint is a required status check.
    """
    findings = []
    script = root / "tools" / "doctrine_callout.py"
    workflow = root / ".github" / "workflows" / "ci.yml"
    if not script.is_file():
        findings.append(
            "doctrine-callout: tools/doctrine_callout.py is missing -- nothing "
            "would flag a doctrine change for the owner's merge-time read [D-81]"
        )
    if not workflow.is_file():
        findings.append("doctrine-callout: .github/workflows/ci.yml is missing")
        return findings
    lines = workflow.read_text(encoding="utf-8", errors="replace").splitlines()

    # Scoped to the job's own block, not searched over the whole file. A
    # whole-file search for the gate matches the version-bump step's identical
    # `if:` line and passes a workflow whose callout job is disabled; and a
    # plain substring passes a job that has merely been commented out, which is
    # the most ordinary CI edit in the set. Both were measured.
    block = []
    for i, line in enumerate(lines):
        if line == JOB_HEADER:
            for tail in lines[i + 1:]:
                if tail.strip() and not tail.startswith("    "):
                    break
                block.append(tail)
            break
    else:
        findings.append(
            "doctrine-callout: no live `doctrine-callout:` job in "
            ".github/workflows/ci.yml -- the callout would stop firing with "
            "nothing going red [D-81]"
        )
        return findings

    for pattern, why in (
        (RUNS_SCRIPT, "does not run tools/doctrine_callout.py"),
        (GATED_ON_PR, "is not gated on a pull_request event"),
        (FULL_HISTORY, "does not check out full history (`fetch-depth: 0`), "
                       "so the base revision is unreadable and the callout "
                       "loses this PR's own movement"),
        (BASE_FLAG, "does not pass `--base` to tools/doctrine_callout.py, so "
                    "the callout states a total and says nothing about "
                    "direction"),
        (BASE_ENV, "does not put the base revision in the environment as "
                   "`BASE_SHA`, so `--base` expands to nothing and the delta "
                   "is dropped with the command still reading correctly"),
    ):
        if not any(pattern.match(line) for line in block):
            findings.append(
                f"doctrine-callout: the doctrine-callout job {why} [D-81]"
            )
    # The trigger is file-level, and switching it (to pull_request_target, say)
    # would skip the job silently while both required checks still report.
    if not any(PR_TRIGGER.match(line) for line in lines):
        findings.append(
            "doctrine-callout: .github/workflows/ci.yml has no `pull_request:` "
            "trigger -- the callout job would never run [D-81]"
        )
    return findings


def check_decision_index(root: Path) -> list[str]:
    """Every decision entry has a row in the log's index, and every row a file.

    The row is part of landing, written once in the PR that lands the entry and
    never maintained after. Without it the entry is unreachable: the shipped
    rule carries at most a bare `[D-N]` marker, so the index is the only route
    a later session has from a decision's number to its reasoning.
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

    An entry is frozen on landing but for a moved reference: the change that
    moves a target repoints every entry reference to it, and that repair is
    only lawful inside the moving change. This guard is what makes the
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
    skills = root / "skills"
    if not skills.is_dir():
        return findings
    for skill_dir in sorted(p for p in skills.iterdir() if p.is_dir()):
        cell = skill_dir / "SKILL.md"
        if not cell.is_file():
            continue
        rel = cell.relative_to(root).as_posix()
        fields = _frontmatter_fields(_read_text(cell) or "")
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
            elif len(value) > CELL_FIELD_MAX_CHARS.get(key, 10**9):
                findings.append(
                    f"cell-frontmatter: {rel}'s {key} is {len(value)} chars, "
                    f"budget is {CELL_FIELD_MAX_CHARS[key]} -- every adopter "
                    f"pays for it in every session, invoked or not"
                )
        name = fields.get("name", "").strip().strip("'\"")
        if name and name != skill_dir.name:
            findings.append(
                f"cell-frontmatter: {rel} declares name '{name}' but sits in "
                f"'{skill_dir.name}/' -- the runtime addresses it by one of them"
            )
    return findings


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
        parsed = json.loads(manifest.read_text(encoding="utf-8", errors="replace"))
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


def check_harness_tokens(root: Path) -> list[str]:
    """No shipped file names a harness-specific path token."""
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
                for match in HARNESS_TOKENS.finditer(line):
                    findings.append(
                        f"harness-token: {rel_file}:{lineno} names "
                        f"'{match.group(0)}' -- a shipped calling contract "
                        f"resolves against the directory of the file naming it"
                    )
    return findings


def _python_files(base: Path):
    """Every `.py` *file* under `base`, sorted, directories excluded.

    `rglob("*.py")` matches a directory named like a module, and reading one
    raises. A delivery test creates exactly that shape deliberately, so this is
    not hypothetical: it took a check down mid-run twice while this change was
    being written. The third walk got this helper rather than the same patch a
    third time.
    """
    for path in sorted(base.rglob("*.py")):
        if path.is_file():
            yield path


def _docstring_constants(tree: ast.AST) -> set[int]:
    """Identities of the string constants that are docstrings, not output.

    A docstring is the first statement of a module, class or function and is
    never written to a stream, so the house style's punctuation is free there.
    Identity rather than position because two docstrings can share a line
    number after a reflow, and `is` is what distinguishes the node.
    """
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if isinstance(first.value.value, str):
                found.add(id(first.value))
    return found


def _git_ignored(root: Path, paths: list[Path]) -> set[Path]:
    """Which of `paths` git is told to ignore, or an empty set if it cannot say.

    The alternative -- a hardcoded skip list -- makes every future top-level
    directory silently escape this check until someone remembers to add it.
    Asking git costs one subprocess and stays correct as the repository grows.

    `git ls-files` was the other candidate and is wrong here: it lists *tracked*
    files, so a script a session has written but not yet added would go
    unchecked, and catching a new script before it merges is the whole point.

    An empty set on any failure is deliberate. A tree with no git (this check's
    own tests build one) is scanned whole, which is the safe direction: the
    filter may only ever remove noise, never hide a finding.
    """
    if not paths:
        return set()
    try:
        proc = subprocess.run(
            ["git", "check-ignore", "--stdin", "-z"],
            input="\0".join(str(path) for path in paths),
            capture_output=True, text=True, cwd=root, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    if proc.returncode not in (0, 1):  # 1 is "nothing ignored", not an error
        return set()
    return {Path(name) for name in proc.stdout.split("\0") if name}


def _true_lineno(text: str, node: ast.Constant, char: str) -> int:
    """The physical line carrying `char`, not the line the constant opens on.

    `node.lineno` is where the literal starts, and CPython folds implicit
    concatenation into one node -- the shape of nearly every message in this
    repository. Reporting the opening line sent a reader to a line with nothing
    wrong on it, measured at 12 of the 44 findings on the tree that motivated
    this check.

    A character written as an escape (`\u2014`) appears nowhere in the source,
    so there is no true line to find and the opening line is the best available
    answer. Returning it is not a defeat: the escape form is caught, which is
    the property that matters, and no line would have been searchable anyway.
    """
    lines = text.splitlines()
    first = node.lineno - 1
    last = min(node.end_lineno or node.lineno, len(lines))
    for offset in range(first, last):
        if char in lines[offset]:
            return offset + 1
    return node.lineno


def check_emitted_ascii(root: Path) -> list[str]:
    """No Python file states a non-ASCII character outside a docstring.

    Python's text mode encodes stdout and stderr to the platform's locale
    codepage -- cp1252 on Windows, including when the destination is a pipe,
    which is what a CI log, an agent harness and a captured command all are.
    An em dash leaves as one byte that a UTF-8 reader renders as a replacement
    character, and a guard speaks exactly when something is already wrong, so
    the one moment its message matters is the moment it is least readable.

    **What this checks is a proxy, and the proxy is stated rather than implied.**
    It reads string *literals*; it does not compute whether one reaches a
    stream, which is not decidable from an AST. So it flags a filename, a regex
    source and a dict key alongside a message, and it cannot see a character
    that is constructed at runtime -- `chr()`, `str.format`, `%`, a `__str__`.
    Saying "reaches a stream" cost this repository a disarmed regression test:
    a session met a lawful fixture, was told a false thing about it, and
    reasoned correctly from the falsehood. The message now says what is true.

    Runtime data is out of reach by construction -- a path this repository did
    not write can carry anything -- and `lib/winio.py` is what protects that
    half. The two are complementary, not alternatives, and check 14 is what
    keeps the second one wired.

    Docstrings are exempt because the house prose style is free where it is
    read as prose. Note the exemption is about docstrings, not about reaching a
    stream: `argparse(description=__doc__)` pipes a module docstring to stdout,
    which is why check 13 bans that construction outright.
    """
    findings = []
    candidates = [
        path for path in _python_files(root)
        if ".git" not in path.parts
    ]
    ignored = _git_ignored(root, candidates)
    for path in candidates:
        if path in ignored:
            continue
        rel_file = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            findings.append(
                f"emitted-ascii: {rel_file} is not valid UTF-8 ({exc.reason} at "
                f"byte {exc.start}) -- the substrate reads UTF-8, and a file it "
                f"cannot decode cannot be checked for what it states"
            )
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            findings.append(
                f"emitted-ascii: {rel_file}:{exc.lineno} does not parse ({exc.msg}) "
                f"-- an unparseable file is not checked, and a check that skips in "
                f"silence cannot be told apart from a clean tree"
            )
            continue
        docstrings = _docstring_constants(tree)
        seen = set()
        per_file = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if id(node) in docstrings:
                continue
            for char in node.value:
                if ord(char) < 128:
                    continue
                lineno = _true_lineno(text, node, char)
                if (lineno, ord(char)) in seen:
                    continue
                seen.add((lineno, ord(char)))
                per_file.append((lineno, ord(char), char))
        for lineno, _codepoint, char in sorted(per_file):
            findings.append(
                f"emitted-ascii: {rel_file}:{lineno} states "
                f"U+{ord(char):04X} ({unicodedata.name(char, 'unnamed')}) "
                f"in a non-docstring string constant -- machine-read output "
                f"stays ASCII, because Windows encodes it to the locale "
                f"codepage and a captured non-ASCII byte garbles. If this "
                f"string is data rather than output, it still stays ASCII "
                f"here: build the character with chr() as the fixtures do"
            )
    return findings


def check_docstring_not_piped(root: Path) -> list[str]:
    """No script hands its module docstring to argparse as help text.

    **The warrant is check 12's exemption, not the encoding.** Check 12 lets a
    docstring carry any character the house prose style likes, and the reason it
    can is that a docstring is read as prose and never written to a stream.
    `ArgumentParser(description=__doc__)` falsifies that premise: it makes the
    docstring output. The ban is what keeps check 12's exemption true.

    An earlier version of this docstring gave the reason as "--help exits inside
    parse_args before any stream setup runs" -- which was accurate when it was
    written and was falsified by check 14 in the same change, since the stream
    is now set up before parse_args is reached. Left standing, a session that
    checked the stated reason would find it false and reason correctly to
    deleting the check. The reason above is the one that survives check 14.

    Two narrower warrants also survive: a module that parses arguments at import
    with no `main()` at all, which check 14 does not reach, and a run where
    `utf8_stdio` hit its swallowed except and set nothing up.

    `epilog` is banned on the same terms. argparse writes it to stdout on --help
    exactly as it writes the description, and it is the conventional home for
    the long-form prose a module docstring holds -- so it is the compliant-
    looking route to the same defect, which is the worst kind to leave open.

    This is a call-site ban rather than a reachability analysis, which is what
    makes it exact: the pattern is one keyword argument whose value is the name
    `__doc__`, and matching it needs no guess about what reaches where.
    """
    findings = []
    for dirname in SHIPPED_DIRS + tuple(sorted(REPO_ONLY_NAMES)):
        base = root / dirname
        if not base.is_dir():
            continue
        for path in _python_files(base):
            text = _read_text(path)
            if text is None:
                continue
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            rel_file = path.relative_to(root).as_posix()
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                for keyword in node.keywords:
                    if keyword.arg not in ("description", "epilog"):
                        continue
                    if isinstance(keyword.value, ast.Name) and keyword.value.id == "__doc__":
                        findings.append(
                            f"docstring-piped: {rel_file}:{node.lineno} passes "
                            f"__doc__ as an argparse {keyword.arg} -- --help writes "
                            f"it to stdout, so a docstring becomes output and the "
                            f"exemption that lets it carry any character stops being "
                            f"true. Write the help text as its own ASCII string"
                        )
    return findings


def check_stdio_wired(root: Path) -> list[str]:
    """Every script with a `main()` imports `utf8_stdio` and calls it first.

    The emitted-ASCII check protects what this repository writes; it reads
    literals and cannot reach what the repository is handed -- a path from git,
    a filename a consumer chose. On Windows that garbles, and for anything
    outside cp1252 it raises mid-report so the offending path never prints.
    `lib/winio.py` closes that half, and this closes the gap between having a
    helper and having called it.

    The objection this answers was the reason a helper was once rejected
    outright: "the helper was called on this entry path" sounds like a
    reachability question, and reachability is not decidable from an AST. It is
    not that question. **The first statement of `main()` is a position, and a
    position is exact.** Ordering is the whole point -- a call after
    `parse_args` is a call that `--help` has already outrun.

    Position alone proved insufficient, though, and the claim of exactness is
    what made that worth closing: a module defining its own no-op `utf8_stdio`
    satisfied the call site while setting nothing up, so the guard reported
    green on precisely the tree it exists to catch. The import binding is
    checked too, which is what makes "it was called" mean "the helper was
    called".

    Scoped to the whole tree, minus what git is told to ignore, for the same
    reason check 12 is: a zone list silently exempts the next directory someone
    adds, and `scripts/` or `.claude/` is exactly where a session drops a
    helper. A module without a `main()` is not a script and is not asked.
    """
    findings = []
    candidates = [path for path in _python_files(root)
                  if ".git" not in path.parts and "tests" not in path.parts]
    ignored = _git_ignored(root, candidates)
    for path in candidates:
        if path in ignored:
            continue
        text = _read_text(path)
        if text is None:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        main = next((n for n in tree.body
                     if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
        if main is None:
            continue
        rel_file = path.relative_to(root).as_posix()
        body = list(main.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            body = body[1:]  # its docstring
        first = body[0] if body else None
        called = (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Call)
            and isinstance(first.value.func, ast.Name)
            and first.value.func.id == "utf8_stdio"
        )
        imported = any(
            isinstance(node, ast.ImportFrom)
            and any(alias.asname == "utf8_stdio"
                    or (alias.asname is None and alias.name == "utf8_stdio")
                    for alias in node.names)
            for node in ast.walk(tree)
        )
        if not called or not imported:
            missing = "does not call it first" if imported else (
                "calls it first but never imports it" if called else
                "neither imports nor calls it first")
            findings.append(
                f"stdio-unwired: {rel_file}:{main.lineno} defines main() and "
                f"{missing} -- runtime data this repository did not write "
                f"reaches the stream unprotected, and a call placed later is "
                f"one that --help has outrun. Import utf8_stdio from lib/winio.py, "
                f"resolving lib/ against this file's own directory rather than "
                f"the working directory, and call it as the first statement"
            )
    return findings


def run(root: Path) -> list[str]:
    return (
        check_zone_wall(root)
        + check_harness_tokens(root)
        + check_charter_cell(root)
        + check_cell_frontmatter(root)
        + check_project_roster(root)
        + check_sideways_deps(root)
        + check_cell_references(root)
        + check_doctrine_citations(root)
        + check_doctrine(root)
        + check_doctrine_callout(root)
        + check_review_index(root)
        + check_decision_index(root)
        + check_entry_references(root)
        + check_emitted_ascii(root)
        + check_docstring_not_piped(root)
        + check_stdio_wired(root)
        + check_marketplace_source(root)
    )


def check_project_roster(root: Path) -> list[str]:
    """Every cell has a `.claude/skills/` entry carrying its frontmatter.

    That directory is the whole of what a **Claude Code** session working in
    this repository loads a description from. An adopter installs the plugin
    and receives the roster from it; this repository never installs itself, so
    before #199 no session here held any cell's name or description, and every
    trigger routed to a description over several changes reached every consumer
    and missed us. `tools/roster.py` carries the mechanism and the evidence.

    **Codex is outside that scope and stays outside it.** It is not documented
    to load this directory, so a Codex session here reaches a cell by opening
    the file, exactly as it did before. The runtime is named rather than left
    to a universal because this repository's doctrine states its audience as
    every runtime, and a sentence claiming every session would have asserted a
    fix Codex never received. [PR #210 review, M10]

    The expectation is the generator's, asked for rather than recomputed. A
    guard that computes its own copy of what a writer produces is a second
    definition of the same thing, and the two agree exactly until either is
    edited -- the failure `_always_on` in `tools/figures.py` already records,
    where two hand-written copies of one sum let a mutation through green.

    An empty `skills/` is a finding rather than a pass, for the reason #198
    states about a sibling guard: no cell found is indistinguishable from
    every cell lawful, and the cheapest route to green must never be deleting
    what the check reads.
    """
    return roster.verify(root)


def always_on_note(root: Path) -> str:
    """The always-on total, where a session sees it before it writes.

    A cold consumer adding a binding rule found this number only because it
    thought to go looking: `tools/figures.py` is named in no always-on surface
    and in no skill prose. It said the
    number changed what it did -- it measured its rule and its outflow before
    writing either, against whatever headroom the tree had -- which is the whole
    argument for putting it where the flow already goes.

    The callout is a merge-surface instrument by design and gated to
    `pull_request`, so it cannot reach the session doing the editing. This is
    that session's answer, and it costs no always-on characters, owes no
    outflow, and adds no sentence anybody has to read.

    Never fatal. A figure that will not derive is stated and moves on; a clean
    tree does not go red because a number was unavailable.
    """
    try:
        spec = importlib.util.spec_from_file_location(
            "repo_figures", root / "tools" / "figures.py"
        )
        figures = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(figures)
        data = figures.figure_always_on(root)["data"]
    except Exception as exc:  # noqa: BLE001 -- reported, never fatal
        return f"always-on surface: not derived ({type(exc).__name__}: {exc})"
    return (
        f"always-on surface: {data['repo_total']:,} chars here, "
        f"{data['adopter_total']:,} from this practice for an adopter"
    )


def main() -> int:
    utf8_stdio()
    findings = run(ROOT)
    for finding in findings:
        print(finding)
    print(always_on_note(ROOT))
    print(f"lint: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
