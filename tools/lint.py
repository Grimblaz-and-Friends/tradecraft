#!/usr/bin/env python3
"""tradecraft packaging lint — enforcement for the doctrine's checkable subset.

Checks:

  1. zone wall: no file in the shipped zone may reference the repo-only zone
     (docs/, tools/, .github/) by any path form — rooted, relative (../ or ./),
     backslashed, or case-shifted. Full web URLs are lawful: they resolve for
     consumers; repo paths do not.
  2. harness tokens: no shipped file, and no repo-only cell, names a
     harness-specific
     path token (${CLAUDE_PLUGIN_ROOT} and kin). Not because they fail --
     Claude Code substitutes them into a skill's body -- but because Codex does
     not, so any such contract binds in one runtime and is dead in the other.
  3. charter cell: the shipped charter exists, has a body, and carries no depth
     files whose binding prose an adopting repository would fail to load.
  4. cell frontmatter: every cell under either source declares a name and a description the
     runtime can parse, each within its field budget. A cell whose description
     is absent or malformed silently never fires.
  5. sideways deps: no cell may reference another cell -- except the
     charter, and except a repo-only cell naming a shipped one, which is
     the wall's lawful direction — by path (rooted or
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
  shown, as check 9 already reasons about an import. Every *path* form is
  read everywhere, fences included -- check 5's rooted and relative skill
  paths and check 6's references/ pointers alike -- because a path that does
  not resolve is broken whatever encloses it, this repository's fenced blocks
  are calling contracts rather than examples, and checks 1 and 2 already fire
  inside them. Both checks also read one wrap — a line ending in `<name>` whose successor
  begins "cell" — because a reflow is a formatting edit no reviewer inspects
  and it would otherwise silently remove a reference from both checks.
  7. doctrine citations: every [D-N] the doctrine writes names an entry that
     exists. The log's own references are check 13's; a marker in the always-on
     surface was checked by nothing, which the outflow rule makes load-bearing
     by instructing a session to compress prose into one.
  8. doctrine references: every repo path the doctrine writes resolves.
     Check 13 covers the decision log, which is frozen exhaust, so the
     surface carrying the live rules was the one nothing checked --
     repointing the doctrine's own docs/values.md mention left lint
     green while the identical break inside an entry fired. Scoped to
     the doctrine files: docs/*.md needs resolver work, not a path-list
     edit, because references there resolve relative to their file.
  9. doctrine: AGENTS.md exists, imports the charter and imports nothing
     else, and CLAUDE.md stays a bare pointer; CLAUDE.md exists and
     is a live @AGENTS.md import — checked by position (first non-empty line,
     unquoted), because Claude Code skips imports inside code spans and loads
     nothing from an absent file.
  10. doctrine callout: tools/doctrine_callout.py exists and ci.yml still
     declares the job that runs it. The callout cannot catch its own removal,
     because a PR deleting the job touches no doctrine file [D-81].
  11. review index: docs/reviews.jsonl, when present, parses and carries one
     valid row per review. Past the cutover: date, artifact, lane, the
     sustained highs named — each with the surface it hit, past a later
     boundary — the model and runtime that staffed it, the external pass's
     outcome, what the review cost to run, report URL, and no arithmetic over
     the findings, the key set being closed. Before the cutover: per-seat
     counts, what came of the findings, and the split by consequence shape,
     which reconciles against the disposition counts and is the only
     cross-total on the row that is sound. Which of those a row owes is a fact
     about *this* record: the file is identified by the sha256 of its first
     non-blank row's bytes, trailing whitespace stripped,
     and any other file is held to the current shape throughout.
 12. decision index: every decision entry has a row in the log's index, and
     every row a file.
 13. entry references: every path reference and relative link a decision entry
     or the log's index writes resolves, is pinned to the commit it shipped at,
     or is recorded with a reason. Unlike check 1, this one reads shape rather
     than any path form: `A/B` is prose, not a reference.
14. emitted ASCII: no Python file states a non-ASCII character in a
    non-docstring string constant. Windows encodes stdout and stderr to the
    locale codepage, pipes included, so a captured em dash garbles in the one
    message a guard exists to deliver. It reads literals, not reachability:
    a filename and a regex source are flagged too, and a character built at
    runtime is out of reach. Docstrings and comments are exempt.
15. docstring not piped: no script passes __doc__ as an argparse
    description. --help writes it to stdout before any stream setup runs,
    which turns the docstring check 14 exempts into locale-encoded output.
16. stdio wired: every script with a main() imports utf8_stdio by that name
    and calls it as the first statement, so runtime data this repository did
    not write reaches the stream protected. Both halves are checked: without
    the import binding, a local no-op with the right name would satisfy the
    call site while setting nothing up. The first statement is a position, and a position is
    exact -- a call after parse_args is one that --help has outrun.
17. project roster: every cell has an entry under .claude/skills/ AND under
    .agents/skills/ carrying its frontmatter byte for byte, and no entry THIS
    GENERATOR WROTE names a cell that is gone. A file it did not write is not
    its business: at a name that is no cell it draws no finding at all,
    because that is a project skill in the runtime's documented place for one;
    at a cell's name it is reported and never overwritten. The qualifier is
    load-bearing and was missing -- an experience session read this line,
    concluded a hand-written entry was a finding, and had to open roster.py to
    find it was not. Those two directories are the whole of what a session
    working in THIS repository loads a **description** from -- one per
    runtime, nothing here installing the plugin. They are not the whole of
    its always-on surface, which the doctrine files and the charter body
    dominate. A locally installed copy of the published plugin
    adds its own descriptions on top, which no figure derived from this tree
    can see and none claims to; that gap is conceded rather than closed, and
    it is how a session here can be offered one cell twice, once from this
    tree and once from a release -- so without them every trigger
    routed to a description reaches every adopter and misses us (#199, #258).
    A finding about a surface names both the directory it found and the
    runtime that reads it, because neither directory reaches the other's
    runtime and a session repairing one has not repaired the other; a finding
    about a cell rather than a surface names neither and is reported once. The expectation is tools/roster.py's own, never recomputed
    here: a guard holding a second definition drifts from the writer it
    judges.
18. marketplace source: the tradecraft entry's source stays the exact string
    `./`, because Codex cannot discover the plugin from Claude's object form.
19. subprocess streams: a launch redirects nothing, or names all three of
    stdin, stdout and stderr, because on Windows an unnamed stream resolves
    through a std-handle table that can still name a closed handle.

20. docstring control characters: no docstring's compiled value holds a
    control character other than a line feed or a tab. A docstring is not raw,
    so a backslash followed by r, written in one, is a carriage return at
    runtime. Named in words rather than shown, because every attempt to write
    that escape into this repository's prose produced the character instead --
    including one in this sentence -- so the form that cannot be lost is the
    one that spells it out. Named rather than counted, for the reason the
    check's own docstring gives: the count was wrong the moment the next
    instance landed. Read from the compiled value rather than the source bytes,
    because the instance that motivated this had clean bytes on disk and four
    carriage returns in `__doc__` [D-231].

21. hollow code span: no inline code span holds nothing but whitespace. Prose
    here names control characters constantly, and a span written to show one
    that no longer holds it reads as finished while saying nothing -- three
    instances in one change, one of which reached a commit and broke a row in
    the decision index. The predicate is *non-empty* whitespace: the
    doubled-backtick idiom's inner span is exactly empty, so the non-empty
    clause separates lawful prose about fences from the defect on a property
    rather than on a list of call sites that would go stale. Fenced blocks are
    skipped, as checks 5 and 6 skip the name form inside one, and by the same
    closing rule -- a fence ends only on its own marker.
22. committed carriage return: no file reaches a commit holding a lone
    carriage return. The LF pin has one hole and git states it plainly --
    text=auto refuses to normalize such a file, and commits every line ending
    in it verbatim. Three populations are read, because the flow runs this
    command before staging and reading the index alone answered a question
    about the previous commit: the index copy of a tracked file, the working
    copy where git classifies it differently, and untracked files git is not
    told to ignore. What the classification flags has its bytes read before
    anything is said, because a genuine binary reports the same way. Disjoint
    from check 20 by the tokenizer, which folds a lone carriage return in
    source to a line feed before a docstring compiles -- a NUL is invisible
    there too, for its own reason, and check 14 is what reports that file.

23. body strip: no module outside the authoring engine hand-rolls the strip
    that takes a cell's body off its frontmatter. Three implementations were
    plausible and the cheapest was wrong; the rule lived in a sibling
    docstring, so a session going straight from the doctrine to code wrote
    its own and everything stayed green (#190). Recorded exemptions are
    (path, function) pairs and the suite pins that the set only shrinks.

24. always-on budget: every per-runtime always-on row, and the adopter
    total separately, inside its ceiling. Replaces the two per-file ceilings
    on AGENTS.md and the charter body, which could not see a move between
    two members of one row -- it read as a saving in whichever file shrank
    while the surface a session loads had not moved (#260).

25. admissions: docs/admissions.jsonl parses, every row carries all six
    fields, and no key has banked more than was ever admitted against it.
    The record is what lets a needed item land over a ceiling without the
    constant moving; a row this cannot read grants nothing. The re-arming
    finding, which fires when a surface comes back to or below its constant
    with characters still charged, belongs to checks 9, 4 and 24 -- the
    three that know each surface's size -- and not to this one (#334).

The frozen archive (docs/ledger.jsonl, docs/seat-record.jsonl, the pre-reset
constitution and the ADRs beneath it) is not validated: it is history, not a
live format (D-74). The prose guards skip the live append-only records too --
docs/reviews.jsonl, docs/recorded-findings.jsonl and docs/admissions.jsonl --
because a finding inside one is a red no lawful edit can clear.

All shipped files are scanned regardless of extension; binary content (NUL
byte in the first 1KB) is skipped. Invoke as `python <repo>/tools/lint.py`
from any cwd — paths resolve from this file's own location.
Exit 0 when clean, 1 with findings listed one per line.

A check that raises is reported as a finding naming it, and every other
check still reports: the chain isolates them one at a time, so the one
command the flow mandates before a commit never answers with a traceback
and never discards what the checks before it found (#239).
"""
from __future__ import annotations

import ast
import datetime
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import traceback
import unicodedata
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent

# Shared with the shipped zone, which is the lawful direction: repo-only
# code may import shipped code. Resolved from this file rather than the
# working directory, so the script runs from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from winio import utf8_stdio  # noqa: E402

# Repo-only importing repo-only, resolved from this file rather than the
# working directory. The roster's expected content is the generator's to
# define; check 17 asks it rather than reproducing it.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import roster  # noqa: E402

SHIPPED_DIRS = (
    "skills", "lib", "commands", "agents", "hooks", ".claude-plugin",
)
REPO_ONLY_NAMES = {"docs", "tools", ".github"}

# The two directories a cell may live under, taken from the generator rather
# than restated here. `tools/roster.py` is what actually decides where a cell
# can be, since it is what makes a description load; a second copy in this file
# would be a second definition of one fact, and they drift the moment a source
# is added to one of them. [#260]
SHIPPED_CELLS = roster.CELLS
REPO_CELLS = roster.REPO_CELLS

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

# **The always-on budget is on what a session loads, not on the files it is
# spread across.** The predecessor's root file passed 30k chars in eight months
# because every incident defaulted to a paragraph, and a per-file ceiling was
# the first counterweight -- but two of them, on AGENTS.md and on the charter
# body, priced a move between those files as a reduction in the one that shrank
# while the surface a session actually reads was unchanged. That is the failure
# D-184 diagnosed in its own predecessor, reproduced one level up. So the
# ceiling is now on each per-runtime row `tools/figures.py` derives, and on the
# adopter total separately.
#
# **Not on `repo_total`**, which is the smallest row: a budget on the minimum
# lets the larger runtime grow unbudgeted, and figures.py's own `_always_on`
# records that nothing renders that scalar alone.
#
# **The value is the larger row this change measured plus one unit, and the
# unit is what a rule costs in the shape this repository makes rules take.**
# Not the headroom `AGENTS_BUDGET_CHARS` happened to carry at `81fb1d9`: that
# measured a paragraph in a file which, after this change, no longer receives
# paragraphs. A rule now joins an existing cell's body -- costing nothing
# always-on -- or, where no cell fits, arrives as a new cell, whose whole
# always-on cost is its name plus its description. Derive it with `python
# tools/figures.py`, which reports every cell's name and description; the unit
# is the median of those, taken to the next hundred. At 253 the previous value
# was smaller than **every** cell in this repository, so the home the routing
# map names for a repo-specific rule could not be used a second time without an
# eviction -- which inverts the charter's *the burden sits on cramming, never
# on creating*. Found by a five-seat review and ruled by the owner. [#291]
#
# **The trade this number makes, stated because it is not obvious.** Headroom
# and the largest tolerated relocation are the same quantity: the budget
# refuses a move-then-refill of block S exactly when S exceeds the headroom,
# and admits an addition A exactly when A fits it. So raising the unit to admit
# a cell widens, by the same amount, the relocation the budget exists to
# refuse. There is no value that separates them; a mechanism that did would
# have to price the two moves apart, which is the shape
# `CELL_BODY_BUDGET_CHARS`' comment argues for and this constant does not have.
#
# This replaces the two per-file ceilings raised under the owner approval on
# issue #260; that approval's condition is discharged here. Find every change
# with `git log -G "ALWAYS_ON_ROW_BUDGET_CHARS = " -- tools/lint.py` -- `-S`
# reports a changed occurrence count and is blind to a changed value.
ALWAYS_ON_ROW_BUDGET_CHARS = 16_345
# The adopter surface is the charter body plus the roster this practice ships.
# This change touches neither, so this is the total measured plus the same
# unit rather than a reduction being banked. Lowering it is the roster
# redesign's, not this change's.
#
# **The charter body has no ceiling of its own any more; it is a member of
# every row and of this total.** So a session growing the charter and a session
# growing a description draw on one pool and neither can read the headroom as
# solely theirs -- which is the point, and is why the figure reports the
# members beside each total. [#291]
ALWAYS_ON_ADOPTER_BUDGET_CHARS = 11_508
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
# --cell-budget <the ceiling in force>` prices that cell on whatever tree you
# are on. The value to pass is this constant plus what `docs/admissions.jsonl`
# charges to that body -- which is what `check_doctrine` enforces and what
# that command reconciles against, so passing the bare constant on a tree
# carrying a body admission is refused rather than answered.
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

# **The fourth answer at a ceiling, and the record that carries it.** None of
# the ceilings above offered a way to admit a needed item. The always-on row
# finding offered three answers -- retire a cell, merge two, or raise the
# ceiling as a recorded decision; `doctrine-budget` offered two relocations
# and no raise; the description and adopter-total findings named no answer at
# all. So "three" was one finding's list rather than the file's, and the
# condition was worse than a first draft of this comment claimed. The owner ruled that a size limit exists to trigger better design
# and must never keep out a needed item, and none of the three admits one --
# so a needed clause was priced as a deletion somewhere else four times on
# #303 alone, once as the examples D-141 had placed (D-184), and once as a
# temporary owner approval that had to be granted, recorded, expired and
# discharged as work in itself (#260).
#
# **An admission is not a raise, and that difference is the whole mechanism.**
# A raise moves the constant and creates round headroom nobody argued for,
# which nothing then has to argue for spending. An admission moves nothing.
#
# **What that rests on, and what it does not.** The structural half is enough
# on its own: a raise hands the next addition room it never argued for, and
# an admission does not. An earlier draft of this comment also claimed
# "ceilings ratchet to just under their limit and stay there", and that claim
# is withdrawn -- `ratchet` is D-184's word for the opposite move, lowering a
# constant to what the tree measures, and the empirical claim is falsified by
# what `python tools/lint.py` prints on any run: `authoring`'s body sits a
# fifth below its ceiling, and most cell descriptions carry room. What is
# true of this tree is that the surfaces which actually bind sit tight, and
# that same command says which those are. The history of what
# happened to headroom after a raise here is on #260 and is not checkable
# from inside this repository. An admission adds exactly the characters
# its row names, spent by the
# item that row names, and leaves the next addition with nothing. So the item
# lands and the pressure survives, which is the pair the comment on
# `ALWAYS_ON_ROW_BUDGET_CHARS` says no single value can hold: headroom and the
# largest tolerated relocation are one quantity, and no *number* separates
# them. An itemisation separates them because it is not a number. [#334]
ADMISSIONS = "docs/admissions.jsonl"
# Every field a row carries, all six required. `issue` is what makes the row
# an admission rather than a waiver -- a needed item is needed *by* some piece
# of work, and a row that cannot name it is one nobody can hold to anything.
# `outflow` is the design obligation the exceedance triggers, written down:
# what moved, what was deleted, or why nothing had a cheaper home.
ADMISSION_FIELDS = ("date", "issue", "ceilings", "chars", "item", "outflow")
# The keys a row may charge itself against: one per ceiling here that prices a
# **share of a surface**. `POINTER_BUDGET_CHARS` and the 64-character `name`
# cap are deliberately absent -- each bounds a file's or a field's shape
# rather than its share of what a session loads, and neither has priced a
# needed item out. Widening this set is a decision, not an edit.
ADMISSION_BARE_KEYS = ("always-on-row", "always-on-adopter")
ADMISSION_KEY_PREFIXES = ("description:", "body:")
_ADMISSION_DATE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")


def _admission_blank(value: object) -> bool:
    """Whether a row's field carries nothing a reader can act on.

    **`str(value).strip()` alone is the defeated idiom.** `str(None)` is
    `"None"` and `str([])` is `"[]"`, both non-blank, so JSON `null`, `[]`,
    `{}` and `false` all passed a truthiness check and admitted their
    characters. That was found for `issue` and fixed for `issue` alone, and
    the two fields beside it kept the hole -- while `issue` itself kept it for
    `[]` and `{}`, which is the field acceptance criterion 6 is written about,
    so that criterion held on its literal falsifier and failed on the natural
    reading of *empty*. One predicate now, all three fields.
    [PR #346 review, M6, M25]
    """
    return (value is None or isinstance(value, bool)
            or isinstance(value, (list, dict, tuple))
            or not str(value).strip())


def _admission_key_ok(key: object) -> bool:
    """Whether a row's ceiling key names something this file enforces.

    Shape, never existence. A cell renamed after a row was written strands
    that row's key, and the record is append-only -- so a guard demanding the
    path resolve would red a tree over history no lawful edit can clear, which
    is the shape #224 was about.

    **What that costs, stated because only the benefit was.** A key that
    matched nothing on the run that wrote it -- a typo, a cell name where a
    path belongs -- validates, charges nothing, and leaves the ceiling finding
    repeating verbatim with nothing connecting the two; the row is then
    permanent and unbankable, since a body ceiling skips an absent cell and
    `check_admissions` reports only over-banking. Separating that case from a
    genuinely stranded key without reinstating the #224 red is a design call
    with no observed instance behind it, and it is recorded rather than taken
    here. [PR #346 review, M20]
    """
    if not isinstance(key, str):
        return False
    if key in ADMISSION_BARE_KEYS:
        return True
    return any(key.startswith(prefix) and key[len(prefix):].strip()
               for prefix in ADMISSION_KEY_PREFIXES)


def read_admissions(root: Path) -> tuple[list[dict], list[str]]:
    """The well-formed rows of the admissions record, and a finding for each that is not.

    **Fail closed.** A row this cannot read grants nothing: it is dropped from
    every sum and reported instead, so a malformed record leaves the constants
    in force rather than admitting whatever the parse happened to salvage.
    That is `check_always_on_budget`'s own rule -- no budget passes by being
    unmeasurable -- applied to the thing that relaxes a budget.

    **An absent record is an empty one, not a failure.** A tree that has never
    admitted anything has no rows, which is the state of the commit that adds
    this mechanism and of every fixture tree the suite builds.
    """
    rows: list[dict] = []
    findings: list[str] = []
    target = root / ADMISSIONS
    if not target.is_file():
        return rows, findings
    text = target.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        where = f"admissions: {ADMISSIONS}:{lineno}"
        try:
            row = json.loads(line)
        except ValueError as exc:
            findings.append(
                f"{where} is not valid JSON ({exc}), so it admits nothing and "
                f"the constant stays in force on whatever it was meant to "
                f"cover. One object per line")
            continue
        if not isinstance(row, dict):
            findings.append(
                f"{where} is not a JSON object, so it admits nothing")
            continue
        missing = [field for field in ADMISSION_FIELDS if field not in row]
        if missing:
            findings.append(
                f"{where} is missing {', '.join(missing)} -- every row carries "
                f"all of {', '.join(ADMISSION_FIELDS)}, and it admits nothing "
                f"until it does")
            continue
        if _admission_blank(row["issue"]):
            findings.append(
                f"{where} names no issue. An admission says which work "
                f"required the item; a row that cannot name it is a waiver, "
                f"and it admits nothing")
            continue
        if not isinstance(row["chars"], int) or isinstance(row["chars"], bool):
            findings.append(
                f"{where}'s chars is {row['chars']!r}, not a whole number of "
                f"characters, so it admits nothing")
            continue
        keys = row["ceilings"]
        if not isinstance(keys, list) or not keys:
            findings.append(
                f"{where}'s ceilings is {keys!r} -- it is a non-empty list of "
                f"the ceilings this row is charged against, so it admits "
                f"nothing")
            continue
        bad = [key for key in keys if not _admission_key_ok(key)]
        if bad:
            forms = " or ".join(prefix + "<path to SKILL.md>"
                                for prefix in ADMISSION_KEY_PREFIXES)
            findings.append(
                f"{where} charges itself against {bad!r}, which names no "
                f"ceiling here. Use {', '.join(ADMISSION_BARE_KEYS)}, or "
                f"{forms} -- it admits nothing meanwhile")
            continue
        empty = [field for field in ("item", "outflow")
                 if _admission_blank(row[field])]
        if empty:
            findings.append(
                f"{where} leaves {', '.join(empty)} empty. The item is what "
                f"was admitted and the outflow is what was tried first; a row "
                f"stating neither records nothing, and it admits nothing")
            continue
        if not _ADMISSION_DATE.match(str(row["date"])):
            findings.append(
                f"{where}'s date is {row['date']!r}, not YYYY-MM-DD, so it "
                f"admits nothing")
            continue
        rows.append(row)
    return rows, findings


def admitted(rows: list[dict], key: str) -> tuple[int, int]:
    """The characters admitted against one ceiling, and how many rows say so.

    Floored at zero for enforcement. `check_admissions` reports a set of rows
    that has banked more than it admitted rather than letting the record
    tighten a ceiling below its constant: a record that could tighten one
    would be a second place constants are set, and this file is the first.
    """
    charged = [row for row in rows if key in row["ceilings"]]
    return max(0, sum(row["chars"] for row in charged)), len(charged)


def ceiling(constant: int, rows: list[dict], key: str) -> tuple[int, str]:
    """The ceiling actually in force for one key, and how to say it.

    One composition for all three enforcement sites, because three renderings
    of "the constant plus what has been admitted against it" is three places
    for the reported ceiling to stop being the enforced one.
    """
    extra, count = admitted(rows, key)
    if not extra:
        return constant, f"budget is {constant}"
    return constant + extra, (
        f"budget is {constant + extra} ({constant} plus {extra} admitted "
        f"across {count} row{'' if count == 1 else 's'} of {ADMISSIONS})")


def admit_route(key: str) -> str:
    """The fourth answer, in the words of the ceiling being hit.

    On the finding rather than behind a pointer: the `authoring` cell prefers
    the rule whose compliance is visible on the artifact its reader is
    producing, and the lint output is what a session at a ceiling already has
    open. All three sites say it the same way because they share this.
    """
    return (
        f"Where the outflow frees nothing and the item is needed, admit it "
        f"rather than cutting, merging or raising: append ONE row to "
        f"{ADMISSIONS} carrying date, issue (the work that required it), "
        f'ceilings ["{key}"], chars, item, and outflow (what moved, what was '
        f"deleted, or why nothing had a cheaper home). **One row per "
        f"ceiling, and one row however many findings name that same "
        f"ceiling** -- both runtime rows cross the row ceiling together, so a "
        f"row apiece there charges the item twice and leaves the surplus as "
        f"headroom for the next addition; but an item exceeding two different "
        f"ceilings takes a row for each, because a row carries one chars for "
        f"every key it names and two ceilings are seldom over by the same "
        f"amount. **Size each row's chars to that ceiling's own overage**, "
        f"the largest where several findings name it, and charge only the "
        f"ceilings the item actually exceeds -- a ceiling still under its "
        f"constant reds as a stale admission. The constant does not move: an "
        f"admission buys its own item and no room for the next one")


def stale_admission(label: str, size: int, constant: int,
                    rows: list[dict], key: str) -> list[str]:
    """A ceiling still carrying admitted characters after its surface came back under.

    **This is what stops an admission becoming a waiver.** Space an outflow
    frees under an admitted ceiling would otherwise sit as room nobody argued
    for -- the refill `routing.md` names, arriving through the very mechanism
    built to admit needed items. Banking it is an append naming what came
    back, never an edit of the row it banks: the record stays append-only and
    both rows stay readable.

    **It fires at the constant, not at the effective ceiling.** Zero slack
    would make every reword of an admitted surface a record append, which is
    the noise the comment on `CELL_BODY_BUDGET_CHARS` warns a zero-headroom
    cap becomes. At or under the constant the surface is unambiguously back,
    and one row settles it.
    """
    extra, count = admitted(rows, key)
    if not extra or size > constant:
        return []
    return [
        f"admission-stale: {label} is {size} chars, back at or under its "
        f"{constant} ceiling, while {extra} chars stay admitted against "
        f'"{key}" across {count} row{"" if count == 1 else "s"} -- that is '
        f"room nobody argued for, which is the refill a ceiling exists to "
        f"refuse. Bank it: append a row to {ADMISSIONS} with chars {-extra} "
        f"and the same five other fields an admission carries -- date, issue, "
        f'ceilings ["{key}"], item and outflow, where item names what came '
        f"back and outflow names what freed it. Appending, never editing what "
        f"it banks"]

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
# The same reference in the repo-only tree. The name form was fenced when the
# second source landed and the path form was not, so one repo-only cell could
# name another as a path and build exactly the mesh the name-form fence bans.
# Written from the generator's constant so a moved source directory moves this
# with it. [#260]
ROOTED_REPO_CELL = re.compile(
    re.escape(roster.REPO_CELLS).replace("/", r"[\\/]") + r"[\\/]([\w-]+)[\\/]",
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
# and that did not change this.
#
# `.agents` is out too, and for a different reason, because the one above does
# not reach it: that tree is **fully tracked**, so it gives one answer per
# commit and the two-answers defect is not in play. It stays out because
# admitting it would be a root one directory deep -- `.agents` holds nothing
# but `skills/` -- which is the shape rejected just above for the roster
# alone, and because no reference here resolves through it.
# [PR #278 review, M25] The reason is about the rest: a session can
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

# The row stops carrying arithmetic over the findings here. Every count on it was hand-totalled
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
# Moved a second time for the same reason it moved the first: PR #225's review
# closed on `main` while this change was open, and its row cannot be rewritten
# to carry a field the schema gained after it was appended.
REVIEW_ROWS_EXTERNAL_QUALITATIVE = 42
COUNTING_FIELDS = ("seats", "dispositions", "facing")
QUALITATIVE_FIELDS = frozenset(
    {
        "date", "artifact", "lane", "report", "highs", "staffing", "external",
        "notes", "cost",
    }
)

# What became of the findings, in the vocabulary these rows were written in.
# All four are dead as *fields*: D-194's cutover forbids `dispositions` on any
# row past REVIEW_ROWS_QUALITATIVE, so they validate grandfathered rows and
# nothing else. Two are also dead as *rulings* -- [D-230] retired `routed` and
# `priced_out` -- while a terminal stage still fixes, and still drops where it
# once dismissed. What it may rule today is the review cell's, never this
# comment's. The row copies counts the ruling already produced; it does not
# derive them.
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

# What the review cost to run, and where each sustained high landed. Both
# arrive at the same boundary because one close writes both, and the value is
# the file's row count when this landed.
#
# **`cost` is not the arithmetic the cutover retired.** That arithmetic was
# over the *findings* -- raw/merged/sustained/high, hand-totalled, reconcilable
# by nothing. These two integers are facts about the run, which is the same
# ground `staffing` survived the cutover on: they are read off the figures each
# dispatch returns, never estimated and never re-derived from a transcript. The
# lane heuristic's own rule promises an audit ("an unrecorded shape choice can
# never be audited later") that, with nothing recorded, could only ever be
# answered qualitatively -- the reason a lane was chosen is in the report every
# row already links; what it cost is nowhere.
# [#357]
REVIEW_ROWS_COST_AND_TARGET = 74
# `subagent_tokens` may be null and `dispatches` may not: a runtime that does
# not report per-dispatch tokens must be able to abstain, while the count of
# dispatches is available to every runtime that made one. Null is an
# abstention claiming nothing; zero is the claim that no subagent ran.
COST_FIELDS = ("dispatches", "subagent_tokens")
COST_NULLABLE = frozenset({"subagent_tokens"})
# **`dispatches` is positive, not merely non-negative.** Every lane this
# practice defines is staffed by fresh dispatches -- the routine lane by a cold
# pass and a defense, the panel lane by four or five seats, a defense and a
# judge -- so a completed review that made none of them is not a review that
# ran. Zero was lawful until an external pass found it, and it was the shape
# that made `{"dispatches": 0, "subagent_tokens": 500000}` -- no subagent ran,
# and here is half a million tokens from the subagents that did not -- pass
# clean into a record nobody may correct. [PR #365 review, M16 + external]
COST_POSITIVE = frozenset({"dispatches"})

# A sustained high stops being a bare string and carries the surface it hit.
# Booked per high rather than as counts, because counts over findings are
# exactly what could never be reconciled -- `facing` is that failure on this
# record -- re-derive with
#   python -c "import json;print([(i, r['date']) for i, r in enumerate(map(json.loads, open('docs/reviews.jsonl', encoding='utf-8'))) if 'facing' in r])"
# whose denominator grows with every append. A label riding with
# the text it describes cannot fail to reconcile, and the list's length is
# still what answers "how many highs" [D-185].
HIGH_FIELDS = ("high", "target")
# Decided in this order, the first match governing, which is what makes the
# three a partition rather than three overlapping enumerations: `record` is
# this change's own paperwork and is tested first because the two of those
# sites that are in the tree live in the repo-only zone; `shipped` is what an adopter installs; `repo` is the
# residual, so every site in the tree has a lawful label.
HIGH_TARGETS = ("record", "shipped", "repo")

# Every boundary above is a fact about ONE record -- this repository's -- and
# a guard that applied them to any file named `docs/reviews.jsonl` demanded the
# retired counting shape from the first row of a tree whose index has not
# started. Two experience-session consumers hit that independently and both
# refused to clear the red the way the message asked, because clearing it meant
# inventing counts into a record nobody may correct. [#268]
#
# The file is identified by the exact bytes of its first non-blank row -- the
# sha256 of that line, trailing whitespace stripped, encoded UTF-8. Row 0's
# `artifact` was rejected as the sentinel: it is `pr-74`, which no other
# repository is prevented from writing, and `artifact` values are not even
# unique within this file (`pr-156` appears twice). Records here are
# append-only, so row 0's bytes are as stable as its name and far harder to
# collide with.
REVIEW_INDEX_ORIGIN_SHA256 = (
    "ca5ef3bfdf26935a852b059c880aa8e2f7211b6e07d272e4fab6aa24394c3eef"
)


class ReviewBounds(NamedTuple):
    """Which rows each schema boundary exempts, for the file in hand.

    Every field is a row count: rows before it are grandfathered against that
    schema. `FOREIGN` zeroes all five, which holds every row of a file that is
    not this record to the current shape -- the one the shipped material
    describes -- rather than to a shape it abolished.
    """

    qualitative: int
    external: int
    grandfathered: int
    facing: int
    cost: int


REVIEW_BOUNDS_FOREIGN = ReviewBounds(0, 0, 0, 0, 0)


def _this_record_bounds() -> ReviewBounds:
    """Composed on each call rather than frozen at import.

    The five constants above stay the single statement of where each schema
    begins; a snapshot taken at import would be a sixth place the numbers live,
    and the first edit to one of them would leave the other five disagreeing
    silently.
    """
    return ReviewBounds(
        qualitative=REVIEW_ROWS_QUALITATIVE,
        external=REVIEW_ROWS_EXTERNAL_QUALITATIVE,
        grandfathered=REVIEW_ROWS_GRANDFATHERED,
        facing=REVIEW_ROWS_FACING_GRANDFATHERED,
        cost=REVIEW_ROWS_COST_AND_TARGET,
    )


def _rows_past(boundary: int) -> str:
    """How a message names the rows a schema obliges.

    A boundary of zero is every row -- the ordinary state of any tree that is
    not this record -- and "rows past the first 0" is a sentence a consumer has
    to decode before it can act. **Both branches read as a plural noun phrase**,
    so every call site takes a plural verb: a first draft returned "every row"
    and forced the singular, which fixed the zero branch's grammar by breaking
    the branch this repository's own record always takes. The one message #268 records a consumer
    refusing to act on was this guard's, so its wording is load-bearing.
    """
    return "all rows" if boundary == 0 else f"rows past the first {boundary}"


def _review_index_is_this_record(first_row_line: str | None) -> bool:
    """Whether the file in hand is this repository's own review index.

    Answered separately from the boundaries rather than read back off them: the
    two are not the same question, and a value comparison against an all-zero
    `ReviewBounds` conflates a foreign file with this record under boundaries a
    test has patched to zero. That conflation fired the unrecognised-record
    diagnostic on two passing tests when this was written the short way.
    """
    if first_row_line is None:
        return False
    digest = hashlib.sha256(first_row_line.rstrip().encode("utf-8")).hexdigest()
    return digest == REVIEW_INDEX_ORIGIN_SHA256


def _review_index_bounds(first_row_line: str | None) -> ReviewBounds:
    """This record's boundaries, or none at all.

    `None` for a file with no non-blank row -- there is nothing to grandfather
    and nothing to check either. Any other first row that is not this record's
    own gets the foreign bounds, deliberately including a truncated copy of
    this file: a record that lost its first row was mutated, which this
    repository forbids, and holding what remains to the current shape is the
    safer of the two wrong answers.
    """
    if _review_index_is_this_record(first_row_line):
        return _this_record_bounds()
    return REVIEW_BOUNDS_FOREIGN


def _read_text(path: Path) -> str | None:
    """Decoded text, or None for binary content or a file that will not open.

    **Unreadable is None, not an exception**, matching `roster.is_generated`
    and `_git_ignored`, which both answer rather than raise. A caller walking
    the whole tree meets files that vanish between the walk and the read, and
    on Windows files an editor or a scanner holds an exclusive lock on; with
    the read unguarded, one of those cost the calling check its entire
    territory and named a frame inside the standard library. Reproduced with a
    real exclusive lock, not a patched walk. [PR #247 review, D1]
    """
    try:
        data = path.read_bytes()
    except OSError:
        return None
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


def _name_form_is_sideways(own: str | None, target: str,
                           own_is_repo: bool = False,
                           target_is_repo: bool = False) -> bool:
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
    if own.lower() == CHARTER_CELL:
        return False
    # **A repo-only cell naming a shipped cell is the wall's lawful
    # direction**, and is the whole reason a repo-only cell can apply a
    # standard the practice ships without copying it. No cycle can form
    # through it, because the reverse is refused outright by
    # check_cell_references: shipped never names repo-only. What stays
    # unlawful is repo-only naming repo-only, which is the mesh of mutual
    # references this rule exists to prevent, and which two cells in one
    # repository can build as easily as two in a plugin. [#260]
    if own_is_repo and not target_is_repo:
        return False
    return True


def check_sideways_deps(root: Path) -> list[str]:
    findings = []
    skills = root / SHIPPED_CELLS
    scan: list[tuple[Path, str | None, bool]] = []
    if skills.is_dir():
        for skill_dir in sorted(p for p in skills.iterdir() if p.is_dir()):
            scan.append((skill_dir, skill_dir.name, False))
    repo_cells_dir = root / REPO_CELLS
    if repo_cells_dir.is_dir():
        for cell_dir in sorted(p for p in repo_cells_dir.iterdir() if p.is_dir()):
            scan.append((cell_dir, cell_dir.name, True))
    for name in ("lib", "hooks"):
        base = root / name
        if base.is_dir():
            # None: none of these is a skill, so any skill path is sideways.
            scan.append((base, None, False))

    repo_cell_names = set(roster.names_under(root, REPO_CELLS))

    def _is_repo_cell(name: str) -> bool:
        # The generator's predicate, not a bare directory test: a directory is
        # not a cell until it holds the file that loads. `check_cell_references`
        # already agrees with the generator; this was the second definition of
        # one fact, and the two disagreed on a half-created cell. [#291]
        return name in repo_cell_names

    for base, own, own_is_repo in scan:
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
                target_is_repo = _is_repo_cell(target)
                if not (root / SHIPPED_CELLS / target).is_dir() and not target_is_repo:
                    continue
                if _name_form_is_sideways(own, target, own_is_repo, target_is_repo):
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
                    target_is_repo = _is_repo_cell(target)
                    if not (root / SHIPPED_CELLS / target).is_dir() and not target_is_repo:
                        continue
                    if _name_form_is_sideways(own, target, own_is_repo,
                                              target_is_repo):
                        findings.append(
                            f"sideways-dep: {rel_file}:{lineno} names "
                            f"skill '{target}'" + _origin(own, base)
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
                        + " -- a cell is reached by name, and only the charter "
                        f"may be named across cells"
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
    return findings


DOCTRINE_CITATION = re.compile(r"\[D-(\d+)\]")


def _doctrine_scan_paths(root: Path) -> list[Path]:
    """The doctrine files, plus every repo-only cell.

    **The cells are here because the material is.** The flow, this
    repository's records rules and its content-routing map carried `[D-N]`
    citations and repo paths while they lived in AGENTS.md, and both were
    checked there. Moving them under `docs/cells/` without moving the scan
    would have retired those guarantees silently -- the same shape as the
    merge gate in tools/doctrine_callout.py, which this change also had to
    follow. A dangling citation reads as authority that resolves and does
    not, wherever it is written. [#260]
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
        # down. The shipped cells stay out for the adopter-resolution reason
        # `check_doctrine_citations` gives, which does not reach repo-only
        # depth: nothing under `docs/` is resolved by a consumer at all.
        paths += sorted(cells.glob("**/*.md"))
    return paths


def check_doctrine_citations(root: Path) -> list[str]:
    r"""Every [D-N] the doctrine writes names a decision entry that exists.

    check_entry_references resolves what the decision log itself writes, and
    stops there -- so a marker in the always-on surface resolved to nothing and
    lint stayed green, verified for all four of them. That mattered little
    while the doctrine merely cited; it matters now that the outflow rule
    instructs a session to replace prose with a citation and requires one that
    resolves. A reason compressed into a marker nobody checks is a reason
    deleted on the next renumbering, on the surface every session reads first.

    Scoped to the doctrine files by decision, not by the shipped cells being
    clean: they carry the `[D-N]` markers
    `git grep -oE "\[D-[0-9]+\]" -- 'skills/**/*.md'` counts on whatever tree
    you are on, and D-173 priced exactly that
    cost rather than arguing it away, on the ground that the party who would
    unknowingly undo the ruling is looking at the cell and not at the log. An
    adopter cannot resolve any of them -- they receive the cells and not the
    decision log -- so widening this guard would either mean stripping reasons
    the practice deliberately kept, or a permanent exemption list. That is the
    owner's call to reopen, not a repair a guard should make on its own; until
    he does, those markers are lawful and out of reach here.

    (The zone wall is not what puts them out of reach, whatever the shape of
    the argument suggests: a `[D-N]` marker is not a path and violates no
    zone rule. The reason is the resolution cost above.)
    """
    findings = []
    directory = root / "docs" / "architecture" / "decisions"
    for path in _doctrine_scan_paths(root):
        name = path.relative_to(root).as_posix()
        if not path.is_file():
            continue  # its absence is check 9's finding, not this one's
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
            continue  # its absence is check 9's finding, not this one's
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
    doctrine does not, and inheriting that leniency made the guard blind on the
    one path it most needs to see: `charter/SKILL.md` -- broken from the root,
    and the shortened form a session under budget pressure would reach for --
    resolved under `skills/` and drew no finding, while a nonexistent cell name
    in the same position did. The doctrine's paths are written from the root,
    so that is the only base that answers the question it is asked.
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
        # a `` `ghost` cell `` reference here while the roster skips it and no
        # runtime can load it -- a reference that resolves for the guard and
        # for nobody else. The generator's own predicate is the one this must
        # agree with, so it is the one used.
        return set(roster.names_under(root, source))

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
            lines = _unfenced_numbered(text)
            named = [(n, m.group(1)) for n, line in lines
                     for m in CELL_REF.finditer(line)]
            named += list(_wrapped_cell_refs(lines))
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
    else:
        # **No per-file ceiling here any more.** AGENTS.md and the charter
        # body are both members of the always-on rows, and a ceiling on each
        # member priced a relocation between them as a saving in the file that
        # shrank while the surface a session loads did not move. The budget is
        # on the rows themselves -- check_always_on_budget. [#260]
        pass
    charter = root / CHARTER
    # An absent cell is not a budget violation -- a tree without it simply has
    # no such cell, and every minimal fixture is one. What an absent cell WOULD
    # do is silently drop the budget on a rename, so that the map still names a
    # real cell is pinned against this repository's own tree in the suite,
    # where the question has an answer, rather than guessed at here.
    # The record relaxes the constants below, never tightens them, and a row
    # it cannot read grants nothing -- `read_admissions` fails closed and
    # `check_admissions` reports what it dropped, so the malformed-record
    # finding is not repeated at every site the record touches.
    admissions, _ = read_admissions(root)
    for rel, budget in sorted(CELL_BODY_BUDGET_CHARS.items()):
        cell = root / rel
        if not cell.is_file():
            continue
        size = len(_frontmatterless(cell.read_text(encoding="utf-8", errors="replace")))
        key = f"body:{rel}"
        allowed, against = ceiling(budget, admissions, key)
        if size > allowed:
            findings.append(
                f"doctrine-budget: {rel}'s body is {size} chars, {against} -- "
                f"shed depth to references/ or route content out; "
                f"`python tools/figures.py --cell {rel} --cell-budget {allowed}` "
                f"reports the cell total, which shedding does not reduce. "
                f"{admit_route(key)}"
            )
        findings += stale_admission(f"{rel}'s body", size, budget,
                                    admissions, key)
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

    # **An import is not a line, it is the file it names.** The row budget
    # measures the doctrine files themselves; the runtime inlines whatever they
    # `@`-import. Probed [#291]: `@docs/values.md` in AGENTS.md moved the row 17
    # characters while the session loaded 5,482 more, with the lint clean -- so
    # the one move the ceiling exists to refuse was available as a one-liner,
    # and the guard's own message told the author it was not. Refusing the
    # construct is the cheapest material that holds it: resolving imports into
    # the figure would oblige `always_on_at` to resolve them at an arbitrary
    # ref too, or the two halves of every delta measure different surfaces.
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
                    f"runtime inlines whole while the always-on figure charges "
                    f"the line -- so it spends the row budget at a fraction of "
                    f"what a session loads. The lawful imports here are "
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
    external pass's qualitative outcome from its later boundary and, past
    REVIEW_ROWS_COST_AND_TARGET, what the review cost to run and the surface
    each high hit, all in place of the arithmetic the rows before it carry.

    **Every boundary below is a fact about one record**, identified by the
    sha256 of its first row's bytes. In any other file all five are zero, so
    every row is held to the current shape rather than to one the material
    abolished. [#268]

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
    lines = index.read_text(encoding="utf-8", errors="replace").splitlines()
    # Which boundaries apply is a fact about the file, settled once before any
    # row is read: this record's own, or none at all for any other file.
    first_row_line = next((line for line in lines if line.strip()), None)
    recognised = _review_index_is_this_record(first_row_line)
    bounds = _review_index_bounds(first_row_line)
    # Rows are counted, not lines: a blank line would otherwise shift every
    # row's position and with it which rows the schema obliges.
    row_index = -1
    # Whether a file this guard does not recognise is nonetheless carrying this
    # record's retired shape -- which is what a mangled copy of it looks like,
    # and what a genuinely fresh index never does.
    foreign_with_counting_rows = False
    for lineno, line in enumerate(lines, 1):
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
        if not recognised and isinstance(row, dict) and "seats" in row:
            foreign_with_counting_rows = True
        try:
            _check_review_row(row, where, findings, row_index, bounds)
        except Exception as exc:  # noqa: BLE001 - report, never crash the lint
            findings.append(
                f"{where} could not be fully validated ({type(exc).__name__}: {exc})"
            )
    if foreign_with_counting_rows:
        # Said once, first, and only where the evidence points at a mangled
        # copy of this record rather than at a record that has not started.
        #
        # **The failure this closes is #268's own, reproduced by its fix.** The
        # identity gate reads the first row's bytes, so a BOM prepended by a
        # text-mode write, a leading space, or a re-serialisation of that row
        # makes this record foreign -- and every one of its landed rows is then
        # held to the current shape, which on the real file is several hundred
        # findings, each one ordering a session to edit a row it may not edit.
        # Without this line nothing in that output says why. Scoped to files
        # carrying `seats` because a genuinely fresh index has no such row and
        # must stay clean: an unscoped diagnostic would red every adopter's
        # tree, which is the defect, not the remedy.
        # [PR #365 review, M9]
        findings.insert(
            0,
            "review-index: docs/reviews.jsonl is not recognised as this "
            "repository's own record, so every row in it is held to the "
            "current shape -- yet it carries rows in the retired counting "
            "shape, which is what a mangled copy of this record looks like. "
            "The identity is the sha256 of the first non-blank row's bytes, "
            "trailing whitespace stripped: check that row for a byte-order "
            "mark, leading whitespace, or a re-serialisation. Every finding "
            "below may be an artefact of that, and rows already landed are "
            "never edited to clear one",
        )
    return findings


def _check_review_row(
    row, where: str, findings: list, row_index: int, bounds: ReviewBounds
) -> None:
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
    _check_row_shape(row, row_index, where, findings, bounds)
    if "seats" in row:
        _check_seats(row["seats"], where, findings)
    if "highs" in row:
        _check_highs(row["highs"], where, findings, row_index, bounds.cost)
    _check_external(row, row_index, where, findings, bounds)
    _check_cost(row, row_index, where, findings, bounds)
    _check_dispositions_and_staffing(row, row_index, where, findings, bounds)
    _check_facing(row, row_index, where, findings, bounds)


def _check_row_shape(
    row, row_index: int, where: str, findings: list, bounds: ReviewBounds
) -> None:
    """Which of the two shapes this row's position obliges.

    Before the cutover a row carries per-seat counts; from it a row carries
    `highs` and no arithmetic at all. Both directions are checked, because a
    guard that only catches the missing field lets the retired shape back in.

    In a file that is not this record `bounds.qualitative` is zero, so no row
    is ever obliged to the retired shape and every row is forbidden it -- which
    is the whole of the fresh-index fix. [#268]
    """
    if row_index < bounds.qualitative:
        if "seats" not in row:
            findings.append(
                f"{where} missing field 'seats' -- rows before the first "
                f"{bounds.qualitative} carry per-seat counts"
            )
        return
    if "highs" not in row:
        findings.append(
            f"{where} missing field 'highs' -- {_rows_past(bounds.qualitative)} "
            f"name each sustained high instead of counting anything: for "
            f"{_rows_past(bounds.cost)} a list of {{'high': ..., 'target': ...}} "
            f"mappings, before that a list of strings, and empty where none was "
            f"sustained"
        )
    present = [f for f in COUNTING_FIELDS if f in row]
    if present:
        findings.append(
            f"{where} carries retired counting field(s) {', '.join(present)} -- "
            f"{_rows_past(bounds.qualitative)} carry no arithmetic over "
            f"the findings: every count this row used to carry was totalled and "
            f"reconciled by hand into a file nobody may edit. What the review "
            f"was worth is in the report it links"
        )
    # Naming the three retired fields is not the rule -- the same totals under a
    # fresh key are the same frozen arithmetic, and passed clean until this
    # closed. The key set is what makes "no arithmetic" enforceable rather than
    # merely stated; a new field is a decision somebody makes here.
    unknown = sorted(set(row) - QUALITATIVE_FIELDS - set(COUNTING_FIELDS))
    if unknown:
        findings.append(
            f"{where} carries unknown key(s) {', '.join(unknown)} -- for "
            f"{_rows_past(bounds.qualitative)} the key set is closed "
            f"({', '.join(sorted(QUALITATIVE_FIELDS))}); arithmetic under a "
            f"fresh name is the arithmetic this cutover retired"
        )


def _check_highs(
    highs, where: str, findings: list, row_index: int, cost_boundary: int
) -> None:
    """Each sustained high, named. The list is the record and its length is the
    count, so nothing here is transcribed and nothing can fail to reconcile.

    An empty list is lawful and means what it says -- a review that sustained
    no high is a valid outcome, and the field cannot express it otherwise.

    Past the cost-and-target boundary — which is zero in any file that is not
    this record, so there every element — an element also carries where the high
    landed, so it is a mapping rather than a bare string. Both element shapes
    are checked in both directions: a bare string past the boundary is the
    field silently failing to carry what it promises, and a mapping before it
    is a schema arriving in a row that predates it.
    """
    if not isinstance(highs, list):
        findings.append(
            f"{where} highs must be a list naming each sustained high "
            f"(got {type(highs).__name__})"
        )
        return
    # One fact, derived once, and one already-rendered phrase: passing the
    # boundary and the verdict about it as two parameters let a later edit
    # desynchronise them, and a first repair fixed that here while reproducing
    # it one call deeper. [PR #365 review, M38 + cycle 2, L10]
    carries_target = row_index >= cost_boundary
    boundary_phrase = _rows_past(cost_boundary)
    seen: dict[str, int] = {}
    for position, element in enumerate(highs):
        high = _high_text(
            element, position, where, findings, carries_target, boundary_phrase
        )
        if high is None:
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


def _high_text(
    element,
    position: int,
    where: str,
    findings: list,
    carries_target: bool,
    boundary_phrase: str,
):
    """The high's own text, or None where the element is not a lawful high.

    Returning the text rather than a bool is what lets the caller's duplicate
    check key on the high itself under either element shape -- the length of
    the list is what this record answers "how many highs" with [D-185], so a
    high named twice under a different label would inflate the only count the
    row still makes.
    """
    if not carries_target:
        if isinstance(element, str) and element.strip():
            return element
        findings.append(
            f"{where} highs[{position}] must be a non-empty string naming "
            f"one sustained high"
        )
        return None
    if not isinstance(element, dict):
        findings.append(
            f"{where} highs[{position}] must be a mapping of "
            f"{', '.join(HIGH_FIELDS)} -- {boundary_phrase} name "
            f"the surface a high hit as well as the high "
            f"(got {type(element).__name__})"
        )
        return None
    unknown = sorted(set(element) - set(HIGH_FIELDS))
    if unknown:
        findings.append(
            f"{where} highs[{position}] carries unknown key(s) "
            f"{', '.join(unknown)} -- a high names itself and where it landed, "
            f"and nothing else: {', '.join(HIGH_FIELDS)}"
        )
    text = element.get("high")
    if not isinstance(text, str) or not text.strip():
        findings.append(
            f"{where} highs[{position}] high must be a non-empty string naming "
            f"one sustained high"
        )
        text = None
    target = element.get("target")
    if target not in HIGH_TARGETS:
        findings.append(
            f"{where} highs[{position}] target '{target}' not in "
            f"{list(HIGH_TARGETS)} -- read from the site the finding cites, "
            f"first match governing: this change's own paperwork is 'record', "
            f"what an adopter installs is 'shipped', everything else here is "
            f"'repo'"
        )
    return text


def _check_cost(
    row, row_index: int, where: str, findings: list, bounds: ReviewBounds
) -> None:
    """What the review cost to run -- evidence for the next lane choice.

    Not a target and not a ceiling: the lane heuristic leans expensive by
    design and its own rule promises an audit that, with nothing recorded,
    could only ever be qualitative. The figures are read off what each dispatch
    returned, so nothing here is estimated. Scoped to the REVIEW's own staffed
    stages: convergence rounds, the convergence cold seat, spikes, experience
    sessions and a commissioned pass are all outside it.
    `docs/cells/records/SKILL.md` is where that list binds and where each
    exclusion's reason is stated.

    **A zero `subagent_tokens` under a nonzero `dispatches` is left lawful**,
    deliberately: `null` is the field's way of saying a runtime does not report
    the figure, and a runtime reporting an honest zero must not be forced to
    lie. The combination is odd rather than impossible, and no guard can tell
    those two apart. [#357] [PR #365 review, cycle 2, L12]
    """
    if "cost" not in row:
        if row_index >= bounds.cost:
            findings.append(
                f"{where} missing field 'cost' -- {_rows_past(bounds.cost)} "
                f"carry what the review cost to run "
                f"({', '.join(COST_FIELDS)})"
            )
        return
    cost = row["cost"]
    if not isinstance(cost, dict):
        findings.append(
            f"{where} cost must be a mapping of {', '.join(COST_FIELDS)} "
            f"(got {type(cost).__name__})"
        )
        return
    missing = set(COST_FIELDS) - set(cost)
    if missing:
        findings.append(f"{where} cost missing {', '.join(sorted(missing))}")
    for field in COST_FIELDS:
        if field not in cost:
            continue
        value = cost[field]
        if value is None and field in COST_NULLABLE:
            continue
        if not _is_count(value) or (field in COST_POSITIVE and value == 0):
            findings.append(
                f"{where} cost {field} '{value}' must be a "
                + ("positive" if field in COST_POSITIVE else "non-negative")
                + f" integer read off what the dispatches returned"
                + (
                    ", or null where the runtime does not report it"
                    if field in COST_NULLABLE
                    else ""
                )
            )
    unknown = set(cost) - set(COST_FIELDS)
    if unknown:
        findings.append(
            f"{where} cost carries unknown key(s) {', '.join(sorted(unknown))} "
            f"-- the row records what the run took, not what it was worth: "
            f"{', '.join(COST_FIELDS)}"
        )


def _check_external(
    row, row_index: int, where: str, findings: list, bounds: ReviewBounds
) -> None:
    """The external pass's qualitative outcome, never its arithmetic."""
    if "external" not in row:
        if row_index >= bounds.external:
            findings.append(
                f"{where} missing field 'external' -- "
                f"{_rows_past(bounds.external)} name the external pass's "
                "qualitative outcome without counts or a panel seat"
            )
        return
    value = row["external"]
    if (
        not isinstance(value, str)
        or not value.strip()
        or value.strip().isdigit()
    ):
        findings.append(
            f"{where} external must be a non-empty qualitative string naming "
            "what actually posted -- never a count or a panel seat"
        )


def _check_dispositions_and_staffing(
    row, row_index: int, where: str, findings: list, bounds: ReviewBounds
) -> None:
    """What came of the findings, and who produced them.

    Counts alone answer how many findings a review raised and nothing about
    whether they mattered -- the question three decision entries circle. And
    the skill requires every report to record model and runtime so per-runtime
    evidence can accumulate, which it cannot do anywhere queryable while the
    index drops both.

    Required of every row past the first REVIEW_ROWS_GRANDFATHERED — which is
    zero in any file that is not this record, so there of every row — and
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
            bounds.grandfathered <= row_index < bounds.qualitative
        ),
        "staffing": row_index >= bounds.grandfathered,
    }
    for field, checker in (
        ("dispositions", _check_disposition_counts),
        ("staffing", _check_staffing),
    ):
        if field not in row:
            if required[field]:
                findings.append(
                    f"{where} missing field '{field}' -- "
                    f"{_rows_past(bounds.grandfathered)} carry it"
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


def _check_facing(
    row, row_index: int, where: str, findings: list, bounds: ReviewBounds
) -> None:
    """The split by consequence shape -- what the review's rulings were about.

    #122 says to watch whether apparatus-facing findings trend down relative to
    findings about the work. The watch item fired on the first full run and
    nothing could measure it, because the split lived only in report prose --
    and two of the five reports that owed it under D-153 did not carry it.

    Required of every row past REVIEW_ROWS_FACING_GRANDFATHERED and validated
    whenever present, so rows already written stay valid untouched. In a file
    that is not this record both boundaries are zero, so the required-window is
    empty and `facing` is forbidden on every row rather than required on any.
    """
    if "facing" not in row:
        if bounds.facing <= row_index < bounds.qualitative:
            findings.append(
                f"{where} missing field 'facing' -- "
                f"{_rows_past(bounds.facing)} carry it "
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

    The row is part of landing, written once in the PR that lands the entry.
    It is not maintained after, but for the same two narrow repairs the entry
    itself admits -- see the log's README. Without it the entry is unreachable:
    the shipped rule carries at most a bare `[D-N]` marker, so the index is the
    only route a later session has from a decision's number to its reasoning.
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
    # The record relaxes the description ceiling below, never tightens it, and
    # a row it cannot read grants nothing -- `read_admissions` fails closed
    # and `check_admissions` reports what it dropped, so the malformed-record
    # finding is not repeated at every site the record touches.
    admissions, _ = read_admissions(root)
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
                # **Only `description` is admissible.** The 64-character
                # `name` cap bounds an identifier the runtime addresses the
                # cell by, not a share of what a session loads, so no
                # admission key names it and `ceiling` is handed the constant
                # with nothing charged against it.
                admission = f"description:{rel}" if key == "description" else ""
                allowed, against = ceiling(
                    CELL_FIELD_MAX_CHARS[key], admissions, admission)
                if len(value) > allowed:
                    findings.append(
                        f"cell-frontmatter: {rel}'s {key} is {len(value)} "
                        f"chars, {against} -- "
                        + ("every session here pays for it, invoked or not"
                           if rel.startswith(REPO_CELLS + "/") else
                           "every adopter pays for it in every session, "
                           "invoked or not")
                        + (f". {admit_route(admission)}" if admission else "")
                    )
                if admission:
                    findings += stale_admission(
                        f"{rel}'s description", len(value),
                        CELL_FIELD_MAX_CHARS[key], admissions, admission)
        name = fields.get("name", "").strip().strip("'\"")
        if name and name != skill_dir.name:
            findings.append(
                f"cell-frontmatter: {rel} declares name '{name}' but sits in "
                f"'{skill_dir.name}/' -- the runtime addresses it by one of them"
            )
    return findings


def continued_keys(text: str) -> list[str]:
    """Keys whose value continues onto a following, more-indented line.

    **This reader takes one line per key, and YAML does not.** A plain scalar
    continued on indented lines is one value to a parser and one line to the
    loop below, which skips any line starting with whitespace. That gap costs
    two guarantees at once, so it is detected once here and both callers ask.

    **What it costs the budget** [#291]: the runtime loads the whole value and
    `_roster` charges the first line. Probed on this repository -- a 4,007
    character description measured as 58, and the always-on row *fell* 533
    while ~3,950 always-on characters were added, with the lint and the roster
    both clean. **What it costs the cell**: `_plain_scalar_hazard` inspects
    what this returns, so a hazard on a continuation line is invisible -- a
    frontmatter block PyYAML raises `ScannerError` on shipped through the whole
    gate green, and the runtime's answer to unparseable is to load the cell
    with empty metadata, silently, which is the failure check 4 exists to
    catch.

    Rejecting the construct rather than parsing it, on the ground check 4
    already gives for not taking a YAML dependency to buy an approximation of
    the real oracle -- and because a value nobody here can measure is one
    nobody can budget, which is true of every spelling and not only the block
    markers `>` and `|`.
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

    **It fired repeatedly inside the one change that added it, and nothing
    caught any of them** -- a committed decision-log row split by two control
    bytes, a docstring carrying carriage returns after a repair turned its bytes
    into escapes it never doubled, a code span that lost the character it named,
    and this check's own registration sentence. Named rather than counted: the
    stated count was wrong the moment the next instance landed, which is the
    arithmetic `roster.verify` deleted rather than corrected a fourth time
    [PR #210 cycle one, C1-F5]. [#233]

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
            # Reported by check 14 for the same reason and on the same walk,
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
            # traceback and none of the other checks' findings. The same defect
            # `roster.write` records at [PR #210 review, M4], reinstated by the
            # guard written to end a different one.
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
# **The live records** -- `docs/reviews.jsonl`, `docs/recorded-findings.jsonl`
# and `docs/admissions.jsonl` -- are skipped by the prose guard only, and the
# asymmetry is the point. A
# finding must quote the line it names, so a review row about a hollow code
# span holds one: that is intended content, and reporting it would red the
# lint over a file doctrine forbids repairing. **A lone carriage return in
# those files is not content at all.** It is corruption of the row's own
# format -- `{"a": "x<CR>y"}` and a record split across a stray one are both
# invalid JSON -- and #233's motivating instance was exactly a row appended by
# a script whose escapes had become control bytes. Skipping them from the byte
# guard withdrew, for `docs/recorded-findings.jsonl`, the pre-commit catch this
# change's own M2 remedy had just bought; `docs/reviews.jsonl` is covered
# either way, because check 11 parses it and reds on the same run, and so is
# `docs/admissions.jsonl` via check 25.
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
    # An admission's `item` and `outflow` are prose about the rule that was
    # admitted, so a row naming a path or quoting a clause holds exactly the
    # constructs the prose guard reports. Append-only means such a finding is
    # a red no lawful edit clears, which is the shape #224 was about -- the
    # byte guard still covers it, where a lone carriage return is corruption
    # of the row's own format rather than content. [#334]
    "docs/admissions.jsonl",
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
# binary content on a NUL in the first kilobyte everywhere else; check 22 uses
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
    `_unfenced_numbered` already implements for checks 5, 6 and 7. This began
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


def _is_generated_entry(root: Path, rel_file: str) -> bool:
    """Whether this path is a roster entry `tools/roster.py` wrote.

    A generated entry's frontmatter is its cell's, byte for byte, so a defect
    in one prose guard's territory would be reported twice for a single edit
    -- once against the cell, once against the copy. The copy's finding is the
    useless half: the file it names says *do not edit this one*, so a reader
    acting on it edits a generated file and the next `--write` brings the
    defect back.

    **The location is tested first, and that is the whole of what was wrong
    here.** `roster.is_generated` answers whether a file holds the generator's
    marker, and its five other callers all hand it a path under the roster
    directory. Handed every path in the repository, it also answers True for
    `tools/roster.py`, which contains that marker's own byte literal -- so
    both prose guards went blind on the one file both of their motivating
    instances came out of, and the falsification this guard's own tests name
    returned nothing. Every seat of this change's review found it
    independently [PR #247 review, M1].

    The marker is still read, and is what decides it inside those
    directories: each is its own runtime's documented home for a project's own
    skills, so a hand-written one there is nobody's copy and is still read.

    **Every surface the generator writes**, asked of `roster.ROSTER_DIRS`
    rather than listed here. A second directory that this predicate did not
    know about would report each description defect once more per copy, which
    is the doubling the whole exemption exists to stop. [#258]

    Nothing hides behind this. Check 17 holds every entry in step with its
    cell, and a lone carriage return is not among what its comparison
    forgives, so a copy that diverged from its cell is already a finding
    there.
    """
    if not any(rel_file.startswith(directory + "/")
               for directory in roster.ROSTER_DIRS):
        return False
    return roster.is_generated(root / rel_file)


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

    **This is disjoint from check 20, which reads compiled docstrings.** That
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
        if _unread_as_prose(rel_file) or _is_generated_entry(root, rel_file):
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

    **Disjoint from check 20 by the tokenizer, not by scope.** Python folds a
    lone carriage return in *source* to a line feed before a docstring
    compiles, so a raw one on disk is invisible to a check reading the
    compiled value. It is not the only such character -- a NUL is invisible
    there too, for its own reason, and check 14 is what reports that file --
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
        if _frozen(rel_file) or _is_generated_entry(root, rel_file):
            continue
        if index_eol not in ("i/lf", "i/none"):
            candidates.setdefault(rel_file, []).append("index")
        if worktree_eol not in ("w/lf", "w/none"):
            candidates.setdefault(rel_file, []).append("working tree")
    for rel_file in untracked:
        if not _frozen(rel_file) and not _is_generated_entry(root, rel_file):
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


def check_harness_tokens(root: Path) -> list[str]:
    """No shipped file, and no repo-only cell, names a harness-specific path token.

    **The repo-only cells are here because they are read in both runtimes.**
    A cell under `docs/cells/` never ships, so the adopter argument does not
    reach it -- but the generator mirrors its description onto both runtime
    surfaces and a session in either one reads its body, so a token that
    expands in Claude Code and not in Codex forks this repository's own
    procedure exactly as it would fork a consumer's. The token is banned for
    what it does to the reader, and this repository has two. [#260]
    """
    findings = []
    for dirname in tuple(SHIPPED_DIRS) + (REPO_CELLS,):
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
                        f"'{match.group(0)}' -- a calling contract read in "
                        f"both runtimes resolves against the directory of the "
                        f"file naming it"
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
            # `text=True` alone encodes stdin with the locale codepage, so one
            # non-ASCII path anywhere collapses this filter for every check
            # that uses it -- and not silently cheaply: the write raises in
            # subprocess's writer thread, stdin never closes, and the call
            # runs the full timeout before returning empty. Measured at 60s.
            capture_output=True, text=True, encoding="utf-8",
            cwd=root, timeout=60,
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
    half. The two are complementary, not alternatives, and check 15 is what
    keeps the second one wired.

    Docstrings are exempt because the house prose style is free where it is
    read as prose. Note the exemption is about docstrings, not about reaching a
    stream: `argparse(description=__doc__)` pipes a module docstring to stdout,
    which is why check 15 bans that construction outright.
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
        try:
            raw = path.read_bytes()
        except OSError as exc:
            # Reported, never raised -- `_read_text`'s rule, which this read
            # predates and did not have. A file an editor or a scanner holds
            # a lock on, or one that vanishes between the walk and the read,
            # used to take this check's whole territory with it.
            # [PR #247 review, post-fix 5]
            findings.append(
                f"emitted-ascii: {rel_file} could not be read ({exc.strerror}) "
                f"-- it is unchecked, and a check that skips in silence cannot "
                f"be told apart from a clean tree"
            )
            continue
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
            at = f":{exc.lineno}" if exc.lineno is not None else ""
            findings.append(
                f"emitted-ascii: {rel_file}{at} does not parse ({exc.msg}) "
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

    **The warrant is check 14's exemption, not the encoding.** Check 14 lets a
    docstring carry any character the house prose style likes, and the reason it
    can is that a docstring is read as prose and never written to a stream.
    `ArgumentParser(description=__doc__)` falsifies that premise: it makes the
    docstring output. The ban is what keeps check 14's exemption true.

    An earlier version of this docstring gave the reason as "--help exits inside
    parse_args before any stream setup runs" -- which was accurate when it was
    written and was falsified by check 16 in the same change, since the stream
    is now set up before parse_args is reached. Left standing, a session that
    checked the stated reason would find it false and reason correctly to
    deleting the check. The reason above is the one that survives check 16.

    Two narrower warrants also survive: a module that parses arguments at import
    with no `main()` at all, which check 16 does not reach, and a run where
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
    reason check 13 is: a zone list silently exempts the next directory someone
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


_LAUNCHERS = ("run", "Popen", "call", "check_call", "check_output")

# Wrappers that redirect a stream by construction and expose no way to name the
# others: `getoutput` and `getstatusoutput` are `check_output(..., shell=True)`
# with no `stdin` parameter at all, and `os.popen` is `Popen(..., stdout=PIPE)`.
# The rule below therefore has no compliant form for them -- measured at 10/10
# failures each under a stale std-handle table -- so they are named rather than
# stream-checked. **`check_output` is deliberately not here**: it also redirects
# by construction, but it does have a compliant form, so flagging it
# unconditionally would redden lawful work. It is handled in `_redirected`
# instead, which is the distinction PR #232's own post-fix look and its defense
# established between them. [D-232]
_NO_STDIN = {
    ("subprocess", "getoutput"),
    ("subprocess", "getstatusoutput"),
    ("os", "popen"),
}
_STREAMS = ("stdin", "stdout", "stderr")

# What each launcher redirects before any argument is read, and which keyword
# rewritings it performs. Read out of each one's own source rather than off
# `run`'s -- three proposed remedies in this change's review diagnosed correctly
# and prescribed a fix that reddened a lawful call, every one of them by
# assuming a wrapper behaves as `run` does. [D-232]
_IMPLICIT = {"check_output": frozenset({"stdout"})}   # run(*a, stdout=PIPE, ...)
_TAKES_CAPTURE_OUTPUT = frozenset({"run"})
_TAKES_INPUT = frozenset({"run", "check_output"})


def _module_aliases(tree: ast.AST, module: str) -> set[str]:
    """Every name this file binds to `module` through `import`.

    `import subprocess as sp` binds a name no literal match reaches, and
    `import os.path` binds `os` while naming something else. The first version
    of this check closed the `from subprocess import run` route and neither of
    these, so it read as complete while ordinary idioms walked through it.
    [D-232]
    """
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Import):
            continue
        for alias in node.names:
            if alias.asname:
                if alias.name == module:
                    names.add(alias.asname)
            elif alias.name == module or alias.name.startswith(module + "."):
                names.add(module)
    return names


def _is_none(node: ast.AST) -> bool:
    """Whether this argument is the literal `None`.

    `stdin=None` is the default spelled out on every launcher, so it redirects
    nothing. `input=None` is **`run`'s** case only: it never reaches `run`'s
    `if input is not None: kwargs['stdin'] = PIPE`, so stdin stays inherited --
    where `check_output` rewrites `input=None` to `b''` before calling `run`,
    and so does pipe it. That split is why `_redirected` asks which launcher it
    is looking at rather than applying one reading to all five. An external
    reviewer contested the `run` half with a cited answer saying `input=None`
    behaves as `input=b''`; the source contradicts them for `run` and agrees
    with them for `check_output`. [D-232]
    """
    return isinstance(node, ast.Constant) and node.value is None


def _redirected(call: ast.Call, launcher: str) -> set[str] | None:
    """Which of the three streams this call redirects, or None if unreadable.

    **What is read is the callee and its keyword arguments.** A second
    positional argument, a splat of either kind, and a non-literal
    `capture_output` are unread, and unread is silence -- whether a stream is
    redirected is genuinely unknown there, and reddening on it blocks lawful
    work, which the `substrate` cell holds fails as hard as passing unlawful
    work.

    **A stream keyword whose value is not the literal `None` is read as a
    redirect, including a name that happens to be `None` at run time.** That is
    a permanent bound of a call-site check rather than a gap to close: nothing
    at the syntax tree knows what a name evaluates to. It is stated because the
    sentence this replaces said the opposite -- it claimed non-literals were
    unread, which is false of all 17 launches in this repository, every one of
    them `stdin=subprocess.DEVNULL`. [D-232]
    """
    if len(call.args) > 1 or any(isinstance(a, ast.Starred) for a in call.args):
        return None
    covered = set(_IMPLICIT.get(launcher, ()))
    for keyword in call.keywords:
        if keyword.arg is None:                      # **kwargs
            return None
        if keyword.arg in _STREAMS and not _is_none(keyword.value):
            covered.add(keyword.arg)
        elif keyword.arg == "input" and launcher in _TAKES_INPUT:
            # `check_output` rewrites None to b'' and pipes either way.
            if launcher == "check_output" or not _is_none(keyword.value):
                covered.add("stdin")
        elif keyword.arg == "capture_output" and launcher in _TAKES_CAPTURE_OUTPUT:
            if not isinstance(keyword.value, ast.Constant):
                return None
            if keyword.value.value:
                covered.update(("stdout", "stderr"))
    return covered


def check_subprocess_streams(root: Path) -> list[str]:
    """A launch redirects nothing, or names all three streams.

    **The rule is about the whole call, not about stdin.** On Windows
    `_get_handles` opens with `if stdin is None and stdout is None and stderr is
    None: return (-1, ...)`, so a launch that redirects **nothing** never asks
    `GetStdHandle` anything and cannot fail. Redirect one stream and leave
    another unnamed, and the unnamed one resolves through the process's
    std-handle table -- which can still name a handle something has since
    closed. `DuplicateHandle` on that raises `OSError: [WinError 6] The handle
    is invalid`, from a call that has nothing to do with the command.

    Requiring `stdin=` alone therefore **manufactured the defect on a launch
    that did not have it**: measured under real pytest capture, 20 launches per
    case in a fresh process each, `run(cmd)` failed 0/20 while
    `run(cmd, stdin=DEVNULL)` failed 20/20. [D-232]

    **A launcher is read against its own source.** `check_output` redirects
    `stdout` by construction and forbids naming it, so *redirects nothing* is
    false of `check_output(cmd)` however few keywords it carries -- measured at
    20/20 while the first version of this check certified it. Its compliant form
    is `stdin=` and `stderr=`, measured 0/20. `getoutput`, `getstatusoutput` and
    `os.popen` have no compliant form at all and are named in `_NO_STDIN`.

    **It fails intermittently, which is the part that costs.** Windows recycles
    handle values: when some unrelated object in the process happens to hold the
    recycled value the duplicate succeeds and the child silently receives an
    unrelated handle; when the value is free, the launch raises. On this
    repository's own suite that produced a different set of red tests every run,
    all of them this one error, while CI stayed green -- a step's Python is born
    with its streams already redirected, and that is itself the immunity, so a
    green Windows leg cannot speak to this either way. [#229]

    `stdin=subprocess.DEVNULL, capture_output=True` is the compliant form for a
    program not meant to read input, which is nearly all of them here -- not
    all: `check_ignored` in this module feeds `git check-ignore --stdin` through
    `input=`, which implies `stdin=PIPE` and covers that stream.

    **A call-site check, not a reachability analysis** -- the same bound
    `check_docstring_not_piped` states, and for the same reason: the pattern is
    readable off one call, and matching it needs no guess about what reaches
    where. What it reads is stated as a criterion in `_redirected`, and the walk
    covers `SHIPPED_DIRS` and `REPO_ONLY_NAMES` -- so not a repository-root
    script, and not an ignored file. Both of those are recorded in
    `docs/recorded-findings.jsonl` rather than fixed. [D-232]
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
            modules = {n: "subprocess" for n in _module_aliases(tree, "subprocess")}
            modules.update({n: "os" for n in _module_aliases(tree, "os")})
            bare = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module in ("subprocess", "os"):
                    for alias in node.names:
                        bare[alias.asname or alias.name] = (node.module, alias.name)
            rel_file = path.relative_to(root).as_posix()
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id in modules
                ):
                    module, attr = modules[func.value.id], func.attr
                    shown = f"{func.value.id}.{attr}"
                elif isinstance(func, ast.Name) and func.id in bare:
                    module, attr = bare[func.id]
                    shown = func.id
                else:
                    continue
                if (module, attr) in _NO_STDIN:
                    findings.append(
                        f"subprocess-streams: {rel_file}:{node.lineno} calls "
                        f"{shown}, which redirects a stream and takes no stdin "
                        f"argument, so it can never name all three -- on "
                        f"Windows it fails with WinError 6 wherever the "
                        f"std-handle table has gone stale. Use subprocess.run("
                        f"..., stdin=DEVNULL, capture_output=True) instead"
                    )
                    continue
                if module != "subprocess" or attr not in _LAUNCHERS:
                    continue
                covered = _redirected(node, attr)
                if covered is None or not covered or len(covered) == 3:
                    continue
                missing = [s for s in _STREAMS if s not in covered]
                devnull = (
                    f"{func.value.id}.DEVNULL"
                    if isinstance(func, ast.Attribute)
                    else "DEVNULL, which this file must import from subprocess"
                )
                # `redirect none of them` is not on offer where the launcher
                # redirects by construction, and neither is naming the stream it
                # owns: `check_output(..., stdout=...)` raises ValueError.
                escape = (
                    "" if attr in _IMPLICIT
                    else ", or redirect none of them"
                )
                findings.append(
                    f"subprocess-streams: {rel_file}:{node.lineno} calls {shown} "
                    f"redirecting some streams and leaving "
                    f"{', '.join(missing)} unnamed -- on Windows an unnamed "
                    f"stream resolves through a std-handle table that can still "
                    f"name a closed handle, so the launch fails with WinError 6 "
                    f"intermittently and for a reason that is not the command's. "
                    f"Name {' and '.join(missing)} "
                    f"({devnull} for a program given nothing to read){escape}"
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
    has none, and took nineteen other checks' findings with it. Fixing that one
    trigger left the chain as it was. The same defect `roster.write` records at
    [PR #210 review, M4], with the same remedy and the same reason: reporting
    keeps the remaining work going and leaves the reader what the other checks
    would have given them. [#239]

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

    Hoisting the marker to a constant is what a reader would call an
    improvement, and it defeated an earlier form of this check outright --
    tools/roster.py already writes its markers that way, so the house style
    was the blind spot.
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


def check_project_roster(root: Path) -> list[str]:
    """Every cell has an entry on every surface, carrying its frontmatter.

    There is one surface per runtime, and between them they are the whole of
    what a session working in this repository loads a description from:
    `.claude/skills/` for Claude Code, `.agents/skills/` for Codex. An adopter
    installs the plugin and receives the roster from it; this repository never
    installs itself, so before #199 no session here held any cell's name or
    description, and every trigger routed to a description over several
    changes reached every consumer and missed us. `tools/roster.py` carries
    the mechanism and the evidence.

    **Codex was outside that scope and is now inside it.** [PR #210 review,
    M10] required the runtime be named rather than left to a universal,
    because a sentence claiming every session would have asserted a fix Codex
    never received -- and while it stood, that named exclusion was the whole
    of what this repository contributed to the runtime its doctrine calls
    canonical. **How long it stood is left to its derivation** --
    `git log -S "Codex is outside
    that scope" -- tools/lint.py` -- rather than stated here, where a comment
    beside code freezes and the figure rule gives it the command and the tree
    and never the output. A draft stated a duration and the duration was
    wrong. **The quoted string is wrapped on purpose**: unwrapped, this file
    holds its own search term, and the command then reports the commit that
    unwrapped it as though the sentence had moved there.
    [PR #278 review, M5, F7, P4, P5] The rule survives the fix, narrowed to
    what the messages do: a finding **about a surface** names its runtime as
    well as its directory, because the two directories reach one runtime each
    and a session that repaired one has not repaired the other. A finding
    about a **cell** -- frontmatter that will not parse, no cell at all --
    names no surface and is reported once, the cell being one file however
    many copies of it are owed. An earlier draft claimed the runtime
    universally while three of the shapes named only a directory.
    [#258] [PR #278 review, M2]

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


# Every check, in report order. A tuple rather than an expression because
# `run()` calls them one at a time to isolate them; see its docstring.
def _unmeasurable_descriptions(root: Path) -> list[str]:
    """Every counted description is one this repository can actually measure.

    **The ceiling is only as good as the number it is applied to.** The
    frontmatter reader here takes `key: value` on one line, which is what every
    cell in this practice writes -- but a *hand-written* project skill on a
    roster surface is somebody else's file, and YAML lets it write
    `description: >-` with the value indented beneath. The runtime loads the
    whole block; this reader sees the two-character token. Probed: a description of thousands of characters measured as the marker
    alone and left the row budget green; the shipped pin reproduces it.

    Rejecting the construct rather than parsing it, for the reason
    `check_cell_frontmatter` already gives about not taking a YAML dependency
    to buy an approximation of the real oracle -- and because a description
    nobody can measure is one nobody can budget, whichever way it is spelled.
    [#260] [#291]
    """
    findings = []
    for surface in roster.SURFACES:
        base = root / surface.directory
        if not base.is_dir():
            continue
        for cell in sorted(base.glob("*/SKILL.md")):
            text = _read_text(cell)
            if text is None or not text.startswith("---"):
                continue
            rel = cell.relative_to(root).as_posix()
            if "description" in continued_keys(text):
                findings.append(
                    f"always-on-budget: {rel}'s description continues onto an "
                    f"indented line, which the runtime loads whole and this "
                    f"repository measures as the first line -- so it is "
                    f"charged to the {surface.runtime} row at a fraction of "
                    f"what it costs. Write the description on one line"
                )
            for line in (_frontmatter_block(text) or "").splitlines():
                key, sep, value = line.partition(":")
                if sep and key.strip() == "description":
                    if value.strip().startswith((">", "|")):
                        findings.append(
                            f"always-on-budget: {rel}'s description is a YAML "
                            f"block scalar, which the runtime loads whole and "
                            f"this repository measures as the marker alone -- "
                            f"so it is charged to the {surface.runtime} row at "
                            f"a fraction of what it costs. Write the "
                            f"description on one line"
                        )
    return findings


def check_always_on_budget(root: Path) -> list[str]:
    """Every per-runtime always-on row, and the adopter total, inside budget.

    **This is the ceiling the two per-file ones became.** A budget on AGENTS.md
    and another on the charter body could not see a move between them: the file
    that shrank reported headroom, the file that grew reported a violation only
    if it happened to be near its own line, and the surface a session actually
    loads had not changed. Budgeting the rows prices what is read. [#260]

    **It fails loudly when the figure cannot be derived.** `always_on_note`
    swallows every exception and returns a string, which is right for a note
    printed beside the findings and wrong for an enforced ceiling: a ceiling
    that silently stops applying when its input breaks is not a ceiling. So the
    import and the arithmetic are inside this check and a failure is a finding.

    **Both rows are checked against one constant, not one row against it.** The
    rows differ -- only Claude Code reads CLAUDE.md -- and a check that took the
    smallest, or the first, would leave the larger unbudgeted, which is the
    defect `_always_on` records for `repo_total` and the reason this does not
    use that scalar.
    """
    findings = []
    # **This guard runs where this guard lives.** The quantity is composed
    # from this repository's own doctrine files and its two generated roster
    # surfaces and measured by its own instrument, so the tree it means
    # anything about is the one carrying this file. A fixture tree writes some
    # of `tools/` without writing `tools/lint.py`, and reporting there would
    # red every synthetic tree the suite builds.
    #
    # **The deletion bypass stays closed**, which is what #134 records going
    # wrong when a guard reads its own input's absence as clean: the gate is
    # this file, not the figure, so removing `tools/figures.py` from this
    # repository reaches the branch below and reds. Probed both ways. [#260]
    if not (root / "tools" / "lint.py").is_file():
        return findings
    # **Before the figure, not after it.** A description this repository cannot
    # measure is a finding whether or not the figure derives -- it is a fact
    # about the file, not about the arithmetic -- and putting it behind the
    # derivation meant a tree with no `tools/figures.py` reported the
    # derivation failure and nothing about the descriptions it also could not
    # have measured. [#291]
    findings += _unmeasurable_descriptions(root)
    # Before the figure, for the same reason: a malformed row is a fact about
    # the record, not about whether `tools/figures.py` imported. The rows are
    # what relax the two constants below; `read_admissions` fails closed, so a
    # row it could not read leaves the constant in force and is reported by
    # `check_admissions` rather than a second time here.
    admissions, _ = read_admissions(root)
    try:
        spec = importlib.util.spec_from_file_location(
            "repo_figures_budget", root / "tools" / "figures.py"
        )
        figures = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(figures)
        data = figures.figure_always_on(root)["data"]
        rows = data["here"]
        adopter = data["adopter_total"]
    except Exception as exc:  # noqa: BLE001 -- a ceiling with no input is a finding
        return findings + [
            f"always-on-budget: not derived ({type(exc).__name__}: {exc}), so "
            f"the always-on ceiling applied to nothing on this run -- fix "
            f"tools/figures.py; no budget passes by being unmeasurable"
        ]
    # **An incomplete figure is not a passing one.** An empty or short `here`
    # list would walk the loop below zero times and apply no ceiling at all,
    # which is the same silent pass the note above was rejected for. The
    # expected set is the generator's surfaces, so a runtime added there and
    # missed here reports rather than going unbudgeted.
    want = {surface.runtime for surface in roster.SURFACES}
    got = {row.get("runtime") for row in rows if isinstance(row, dict)}
    if want - got:
        return findings + [
            f"always-on-budget: the figure reported no row for "
            f"{', '.join(sorted(want - got))}, so that runtime's surface was "
            f"not measured and no ceiling applied to it -- fix "
            f"tools/figures.py; no budget passes by being unmeasurable"
        ]
    if not isinstance(adopter, int):
        return findings + [
            f"always-on-budget: the figure's adopter total is not a number "
            f"({adopter!r}), so no ceiling applied to it -- fix "
            f"tools/figures.py; no budget passes by being unmeasurable"
        ]
    row_key, adopter_key = "always-on-row", "always-on-adopter"
    row_allowed, row_against = ceiling(
        ALWAYS_ON_ROW_BUDGET_CHARS, admissions, row_key)
    for row in rows:
        if row["total"] > row_allowed:
            findings.append(
                f"always-on-budget: the {row['runtime']} row is "
                f"{row['total']} chars, {row_against} -- this is the whole "
                f"surface that runtime loads before acting, so moving prose "
                f"to another always-on file will not clear it. A body over "
                f"budget sheds to a cell body or to references/; a "
                f"*description* over budget can do neither without ceasing "
                f"to be a trigger, so it is answered by retiring a cell or "
                f"merging two. {admit_route(row_key)}. What to do at a "
                f"ceiling is skills/authoring/SKILL.md's -- whose own fourth "
                f"answer is deleting the rule, "
                f"which is a different move from admitting and is "
                f"reached only against evidence that the rule does "
                f"not bind"
            )
    # **The largest row, because one constant governs both.** Re-arming asks
    # whether the surface has come back under, and it has not while either
    # runtime is still over -- taking the smaller would bank space the larger
    # is still spending.
    findings += stale_admission(
        "the largest always-on row", max(row["total"] for row in rows),
        ALWAYS_ON_ROW_BUDGET_CHARS, admissions, row_key)
    adopter_allowed, adopter_against = ceiling(
        ALWAYS_ON_ADOPTER_BUDGET_CHARS, admissions, adopter_key)
    if adopter > adopter_allowed:
        findings.append(
            f"always-on-budget: the adopter total is {adopter} chars, "
            f"{adopter_against} -- this is what this practice puts in every "
            f"session of every repository that adopts it, and it counts the "
            f"charter body and the shipped roster's descriptions only. "
            f"{admit_route(adopter_key)}"
        )
    findings += stale_admission(
        "the adopter total", adopter, ALWAYS_ON_ADOPTER_BUDGET_CHARS,
        admissions, adopter_key)
    return findings


def check_admissions(root: Path) -> list[str]:
    """The admissions record parses, and no ceiling carries what it no longer spends.

    **This is the guard on the thing that relaxes the other guards**, so it
    reports what `read_admissions` refused rather than leaving a malformed row
    to fail silently closed. Silent fail-closed would be safe and unreadable:
    the session would meet a ceiling finding it had just written a row to
    clear, with nothing saying the row was the problem.

    **A record cannot tighten a ceiling.** Rows banking more than was ever
    admitted against a key would drive the effective ceiling below the
    constant, which would make this file's constants stop being where the
    ceilings are set. `admitted` floors the sum at zero and this reports the
    set that got there, in both polarities: over-banking is a finding, and
    banking exactly what was admitted is the lawful end state.
    """
    rows, findings = read_admissions(root)
    for key in sorted({key for row in rows for key in row["ceilings"]}):
        charged = [row for row in rows if key in row["ceilings"]]
        total = sum(row["chars"] for row in charged)
        if total < 0:
            findings.append(
                f"admissions: the rows charged against \"{key}\" sum to "
                f"{total}, which would put its ceiling below the constant "
                f"that {ADMISSIONS} exists to relax -- a record does not tighten a "
                f"ceiling, and tools/lint.py is where they are set. Bank no "
                f"more than was admitted"
            )
    return findings



CHECKS = (
    check_zone_wall,
    check_harness_tokens,
    check_charter_cell,
    check_cell_frontmatter,
    check_project_roster,
    check_sideways_deps,
    check_cell_references,
    check_doctrine_citations,
    check_doctrine_references,
    check_doctrine,
    check_doctrine_callout,
    check_review_index,
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
    check_always_on_budget,
    check_admissions,
)


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

    **It prints every runtime's total, not one scalar**, and the renderer is
    the figure's own rather than a fourth wording of it. This was the third
    place `repo_total` was rendered and the only one that did not learn the
    term had been redefined to the smallest row: on a tree the roster guard
    passes -- a lawful hand-written project skill under one surface is enough
    -- it handed the session that ran the flow's first mandated step a number
    that was some other runtime's, understated, with nothing saying so. Found
    by every seat of PR #278's panel and by the external pass, at the one
    surface the criterion's own audience reads. **No runtime detection is owed
    or wanted**: this cannot ask which runtime it is under, `check_harness_tokens`
    exists because a form binding in one runtime and not the other forks the
    practice, and this runs in CI where neither is present. It names every row
    and lets the reader take its own. [PR #278 review, M1]

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
        # Inside the guard, not after it. The read was inside and the
        # formatting was not, so a `data` missing either key escaped as a
        # KeyError -- and `main()` answered the flow's mandated command
        # with a traceback, which is the guarantee `run()`'s isolation
        # exists to make. Two seats disagreed about whether this function
        # was guarded; the probe settled it. [PR #247 review, M19]
        # The adopter total is stated with what is admitted against it, for
        # the reason `figures.priced` carries: a session reading the constant
        # alone reads headroom a different number governs. Silent on a tree
        # that has admitted nothing.
        extra = data.get("admitted", {}).get("always-on-adopter", 0)
        return (
            f"always-on surface here, per runtime: "
            f"{figures.by_runtime(data)}; "
            f"{data['adopter_total']:,} of "
            f"{figures.priced(ALWAYS_ON_ADOPTER_BUDGET_CHARS, extra)} "
            f"from this practice for an adopter"
        )
    except Exception as exc:  # noqa: BLE001 -- reported, never fatal
        return f"always-on surface: not derived ({type(exc).__name__}: {exc})"


def cell_body_note(root: Path) -> str:
    """Every cell body, where a session sees it before it writes.

    **The map is not the cells.** `check_doctrine` iterates
    `CELL_BODY_BUDGET_CHARS`, so a cell absent from it was sized by nothing at
    either command the landing procedure mandates -- save the charter, whose
    body is a term in every always-on row and was already printed there -- and the cells absent from
    it had become the large ones, with the governed bodies neither the
    largest nor near it. Reporting a size asserts no number, which is why this
    is a note and not a ceiling: the map is sparse on purpose, because a number
    chosen for a cell nobody has argued about would be a ruling arriving as a
    constant, and this change was affirmed not to make one. [#302]

    **Never fatal, and never silent.** It reports rather than reds, copying
    `always_on_note` above -- which states a figure it cannot derive and moves
    on. The two states a reader must be able to tell apart are *nothing to
    report*, which a tree with no cells is, and *could not derive*, which a
    broken input is; silence would say neither, so each produces text.
    """
    try:
        spec = importlib.util.spec_from_file_location(
            "repo_figures_bodies", root / "tools" / "figures.py"
        )
        figures = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(figures)
        rows = figures.cell_body_rows(root)
        # Inside the guard, for the reason always_on_note records: a `data`
        # missing its key escaping as a KeyError answers the flow's mandated
        # command with a traceback.
        if not rows:
            return "cell bodies here: no cells on either roster source"
        return (
            "cell bodies here, largest first:"
            + chr(10) + figures.cell_body_block(rows)
        )
    except Exception as exc:  # noqa: BLE001 -- reported, never fatal
        return f"cell bodies: not derived ({type(exc).__name__}: {exc})"


def admission_note() -> str:
    """The fourth answer, beside the figures rather than only in the finding.

    **A route reachable only after you exceed cannot reach a session whose
    method is not exceeding.** An experience session on this change closed a
    real charter gap against 108 characters of headroom: it drafted six
    candidate sentences, measured each before touching the file, found its
    first three came in at +98 to +109 against 108 characters of room, and
    shipped one at +95 -- dropping a clause it wanted to keep. (An earlier
    wording here said all three were at or over the line; the note it cites
    says +98, which fits with ten to spare.) That is the move `skills/authoring/SKILL.md`
    forbids in the same sentence that names it, and it happened with
    `tools/lint.py`'s budget and admission constants among what the session
    reports having read. The run never went red, so it never met the finding
    that carries the route, and the surface it did meet -- the block below,
    which it preferred to `tools/figures.py` throughout -- named the ceiling
    and no answer to it. [PR #346 session note]

    **Unconditional, and evaluating nothing.** No threshold, no marker, no
    word about how full a surface is: `cell_body_block` records why a figure
    surface here invents no such number, and a route printed only when
    headroom looks tight would be exactly that number wearing prose. This
    states what to do at a ceiling and lets the reader see where it stands
    from the figures above it.
    """
    forms = list(ADMISSION_BARE_KEYS) + [
        prefix + "<path to SKILL.md>" for prefix in ADMISSION_KEY_PREFIXES]
    keys = ", ".join(forms[:-1]) + ", or " + forms[-1]
    return (
        f"at a ceiling on a share of what a session loads -- an always-on "
        f"row, the adopter total, a cell description, a budgeted cell body "
        f"-- a needed item that will not fit is admitted on {ADMISSIONS} "
        f"rather than trimmed until it fits: a row carrying "
        f"{', '.join(ADMISSION_FIELDS)}, where ceilings names one or more of "
        f"{keys}. The constant does not move, so an admission buys its own "
        f"item and no room for the next one"
    )


def main() -> int:
    utf8_stdio()
    findings = run(ROOT)
    for finding in findings:
        print(finding)
    print(always_on_note(ROOT))
    print(cell_body_note(ROOT))
    print(admission_note())
    print(f"lint: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
