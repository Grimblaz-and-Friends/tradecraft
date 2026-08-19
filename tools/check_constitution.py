#!/usr/bin/env python3
"""Constitutional format guards — the statute and the decision log (D-53).

Form, position and existence only. Correspondence — whether an entry's content
describes the change, whether a "Changes no operative rule" declaration is true,
whether meaning was preserved — is review's, and nothing here reaches it
(statute §12).

  1. append-only. Evaluated against the MERGE BASE, which is what makes the
     lifecycle work with no extra state: an entry is *accepted* when present at
     the merge base, and an ADR is *frozen* when it carried its freeze marker
     there. Before that both are drafts and freely revisable — which is why this
     guard lands in the same change as the files it guards and still passes.

  2. citation. Rules are identified by their bold lead-in, at any indent, and
     compared per rule against the merge base: a rule added must cite this pull
     request's entry, a rule that drops an `[ADR-NNN:L]` or `[D-N]` citation must
     have that displacement declared, and a rule that vanishes must be displaced
     by an entry. Quoted fragments must appear on the line they cite.

  3. entry shape. A decision entry's required-field skeleton, checked while it is
     still a draft — because an entry that lands malformed can never be repaired:
     the repair is itself a diff to an accepted entry.

Exit 0 clean, 1 with findings, **2 when the answer cannot be determined** — a
guard that goes quiet when its base has moved prints the same line as a clean
pass, and every failure mode it meets becomes invisible (statute §3).

Usage: python tools/check_constitution.py [--base origin/main] [--pr N]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUTE = "docs/architecture/constitution.md"
ADR_DIR = "docs/architecture/adr"
LOG_DIR = "docs/architecture/decisions"
LOG_INDEX = f"{LOG_DIR}/README.md"

FREEZE_MARKER = re.compile(r"^\*\*Frozen \d{4}-\d{2}-\d{2} by \[D-\d+\]")
STATUS_LINE = re.compile(r"^\*\*Status:\*\*")
# The one lawful post-freeze diff, and the one lawful edit to an accepted entry.
# The target admits a frozen ADR's lines or another entry — an entry has no line
# numbers, so a form naming only ADRs left entry-to-entry supersession unwritable.
POINTER = re.compile(
    r" · Superseded in part by \[D-(\d+)\] \((\d{4}-\d{2}-\d{2})\): "
    r"(ADR-\d{3}:\d+(?:, \d+)*|D-\d+) — .+?(?= · Superseded in part by |\Z)"
)
ENTRY_NAME = re.compile(r"\AD-(\d+)-\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.md\Z")
# A rule unit is a bold-led list item at ANY indent. The statute states 35 of its
# rules as nested bullets and contains no continuation lines at all, so anchoring
# at column 0 put those 35 outside every check.
RULE_UNIT = re.compile(r"\A\s*- \*\*")
LEAD_IN = re.compile(r"\A\s*- (\*\*.+?\*\*)")
CITATION = re.compile(r"\[(?:ADR-\d{3}:\d+(?: \"[^\"]*\")?|D-\d+)\]\s*\Z")
ADR_TOKEN = re.compile(r"\[ADR-(\d{3}):(\d+)(?: \"([^\"]*)\")?\]")
D_TOKEN = re.compile(r"\[D-(\d+)\]")
DISPLACES = re.compile(r"^\*\*Displaces:\*\*(.*)$", re.MULTILINE)
# The forms that lawfully declare nothing. §12 requires the line only where any
# are displaced, so an absent line and these are the same statement.
_DISPLACES_NONE = {"", "—", "-", "none", "n/a"}

ENTRY_SKELETON = (
    (re.compile(r"^# D-\d+: \S", re.MULTILINE), "a `# D-<N>: <title>` heading"),
    (re.compile(r"^\*\*Status:\*\* Accepted \d{4}-\d{2}-\d{2} \(PR #\d+\)", re.MULTILINE),
     "a `**Status:** Accepted YYYY-MM-DD (PR #<N>)` line"),
    (re.compile(r"^## Context\s*$", re.MULTILINE), "a `## Context` section"),
    (re.compile(r"^## Decision\s*$", re.MULTILINE), "a `## Decision` section"),
    (re.compile(r"^\*\*Statute delta:\*\*|^\*\*Changes no operative rule\.\*\*", re.MULTILINE),
     "a `**Statute delta:**` or `**Changes no operative rule.**` opener in `## Decision`"),
    (re.compile(r"^## Rejected\s*$", re.MULTILINE), "a `## Rejected` section"),
    (re.compile(r"^## Evidence\s*$", re.MULTILINE), "an `## Evidence` section"),
)


class Undetermined(Exception):
    """The guard cannot answer. Never a pass."""


def _git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=False,
        )
    except OSError as exc:  # noqa: BLE001
        raise Undetermined(f"git is not runnable: {exc}") from exc
    if out.returncode != 0:
        raise Undetermined(f"git {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout


def _merge_base(base: str) -> str:
    sha = _git("merge-base", "HEAD", base).strip()
    if not sha:
        raise Undetermined(f"no merge base between HEAD and {base}")
    return sha


def _at(sha: str, path: str) -> str | None:
    out = subprocess.run(
        ["git", "show", f"{sha}:{path}"], cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return out.stdout if out.returncode == 0 else None


def _changed(sha: str) -> list[str]:
    return [n for n in _git("diff", "--name-only", f"{sha}...HEAD").splitlines() if n.strip()]


def _status_line(text: str) -> str | None:
    return next((l for l in text.split("\n") if STATUS_LINE.match(l)), None)


def _rules(text: str) -> dict[str, str]:
    """Rule identity is the bold lead-in. Keyed so a rule can be followed across
    a diff — line-set comparison could not tell an edited rule from a new one."""
    out: dict[str, str] = {}
    for line in text.split("\n"):
        m = LEAD_IN.match(line)
        if m and RULE_UNIT.match(line):
            out[m.group(1)] = line
    return out


def _duplicate_lead_ins(text: str) -> list[str]:
    """Identity must be unique or it is not identity: a second rule sharing a
    lead-in reads as an edit of the first, so the added-rule check never runs and
    the original becomes invisible to every later comparison."""
    seen: set[str] = set()
    dupes: list[str] = []
    for line in text.split("\n"):
        m = LEAD_IN.match(line)
        if m and RULE_UNIT.match(line):
            if m.group(1) in seen:
                dupes.append(m.group(1))
            seen.add(m.group(1))
    return dupes


def check_append_only(base_sha: str) -> list[str]:
    findings: list[str] = []
    for path in _changed(base_sha):
        is_adr = path.startswith(f"{ADR_DIR}/")  # the index froze with the preamble it indexes
        is_entry = path.startswith(f"{LOG_DIR}/") and path != LOG_INDEX
        if not (is_adr or is_entry):
            continue  # the log's index grows with every entry and is never frozen
        base_text = _at(base_sha, path)
        head_path = ROOT / path
        head = head_path.read_text(encoding="utf-8") if head_path.is_file() else None

        if is_entry:
            name = Path(path).name
            if not ENTRY_NAME.match(name):
                findings.append(
                    f"append-only (§12): {path} is not a lawful entry filename — "
                    f"expected D-<pr>-YYYY-MM-DD-<slug>.md"
                )
            accepted = base_text is not None
        else:
            accepted = base_text is not None and any(
                FREEZE_MARKER.match(l) for l in base_text.split("\n")
            )
        if not accepted:
            continue
        if head is None:
            findings.append(
                f"append-only (§12): {path} was accepted at the merge base and is deleted "
                f"at head — reversal is by superseding entry, never by removal"
            )
            continue

        b_all = [x for x in base_text.split(chr(10)) if STATUS_LINE.match(x)]
        h_all = [x for x in head.split(chr(10)) if STATUS_LINE.match(x)]
        if len(h_all) > 1 and len(h_all) > len(b_all):
            # The canonical status line is exempt from the body comparison below,
            # so a SECOND one rides that exemption and carries arbitrary content
            # through untouched. Found independently by both external reviewers.
            findings.append(
                f"append-only (§12): {path} has {len(h_all)} `**Status:**` lines — exactly "
                f"one is lawful; any other rides the status-line exemption"
            )
            continue
        b_status, h_status = _status_line(base_text), _status_line(head)
        if b_status is None or h_status is None:
            # Never an append-only finding: a missing status line is a SHAPE defect,
            # and reporting it here made the repair its own trigger — an entry that
            # landed malformed could never be fixed and stayed CI-red forever.
            findings.append(
                f"entry-shape (§12): {path} has no `**Status:**` line — repair it before "
                f"it lands; an accepted entry cannot be edited afterwards"
            )
            continue
        strip = lambda t: [l for l in t.split("\n") if not STATUS_LINE.match(l)]  # noqa: E731
        if strip(base_text) != strip(head):
            findings.append(
                f"append-only (§12): {path} is accepted/frozen and changed outside its "
                f"status line — the only lawful diff is a status-line append"
            )
        if h_status != b_status:
            if not h_status.startswith(b_status):
                findings.append(
                    f"append-only (§12): {path} status line was rewritten rather than appended to"
                )
            elif not POINTER.fullmatch(h_status[len(b_status):]):
                findings.append(
                    f"append-only (§12): {path} status-line append is malformed — expected "
                    f"' · Superseded in part by [D-N] (YYYY-MM-DD): <ADR-NNN:L[, L…] | D-N> "
                    f"— <one clause>', got {h_status[len(b_status):]!r}"
                )
    return findings


def _entry_files() -> list[Path]:
    d = ROOT / LOG_DIR
    return sorted(f for f in d.rglob("D-*.md") if ENTRY_NAME.match(f.name)) if d.is_dir() else []


def _entry_numbers() -> set[int]:
    return {int(ENTRY_NAME.match(f.name).group(1)) for f in _entry_files()}


def _duplicate_entry_numbers() -> dict[int, list[str]]:
    """One number must resolve to one file. Zero-padding is lawful in a filename
    and invisible to every consumer, all of which key on the int — so a second
    file claiming a taken number silently overwrites the first's `Displaces`."""
    by_num: dict[int, list[str]] = {}
    for f in _entry_files():
        by_num.setdefault(int(ENTRY_NAME.match(f.name).group(1)), []).append(f.name)
    return {n: sorted(names) for n, names in by_num.items() if len(names) > 1}


def check_entry_shape(base_sha: str) -> list[str]:
    """Drafts only. An accepted entry cannot be repaired — the repair is itself a
    diff to an accepted entry — so re-checking one would make it permanently red
    for a defect nobody can fix. That is the trap this check was added to close."""
    findings: list[str] = []
    for num, names in sorted(_duplicate_entry_numbers().items()):
        # Reported only when this change introduces one of the colliding files,
        # for the same reason the rest of this function is draft-scoped.
        if any(_at(base_sha, f"{LOG_DIR}/{n}") is None for n in names):
            findings.append(
                f"entry-shape (§12): {len(names)} entries claim the number D-{num} "
                f"({', '.join(names)}) — one number, one file"
            )
    for f in _entry_files():
        rel = f.relative_to(ROOT).as_posix()
        if _at(base_sha, rel) is not None:
            continue  # accepted at the merge base: immutable, and past repair
        text = f.read_text(encoding="utf-8")
        # Three sites name one entry. Left free to disagree, [D-N] resolves to
        # whichever the reader happened to consult.
        extra = [x for x in text.split(chr(10)) if STATUS_LINE.match(x)]
        if len(extra) > 1:
            findings.append(
                f"entry-shape (§12): {rel} has {len(extra)} `**Status:**` lines — repair it "
                f"before it lands; afterwards the record can be neither superseded nor fixed"
            )
        own = ENTRY_NAME.match(f.name).group(1)
        for pat, site in ((r"^# D-(\d+):", "heading"),
                          (r"^\*\*Status:\*\* Accepted \d{4}-\d{2}-\d{2} \(PR #(\d+)\)", "status line")):
            m = re.search(pat, text, re.MULTILINE)
            if m and int(m.group(1)) != int(own):
                findings.append(
                    f"entry-shape (§12): {rel} is named D-{int(own)} but its {site} says "
                    f"D-{int(m.group(1))} — one entry, one number"
                )
        # Same collapse as the `**Status:**` twin above, one field over: `_declared`
        # reads the first match, so a second line rides behind an innocent one and
        # its targets never reach the supersession cross-check §12 makes obligatory.
        decl = [x for x in text.split(chr(10)) if DISPLACES.match(x)]
        if len(decl) > 1:
            findings.append(
                f"entry-shape (§12): {rel} has {len(decl)} `**Displaces:**` lines — only the "
                f"first is read, so the rest declare nothing and demand no supersession pointer"
            )
        # A target written without brackets reads to a person as a declaration and to
        # `_targets` as the empty set, so the cross-check silently does not run.
        for line in decl:
            payload = DISPLACES.match(line).group(1).strip()
            if payload.lower() in _DISPLACES_NONE:
                continue
            residue = ADR_TOKEN.sub("", D_TOKEN.sub("", payload)).strip(" ,;.")
            if residue:
                findings.append(
                    f"entry-shape (§12): {rel} declares Displaces `{payload}`, which carries "
                    f"unbracketed text ({residue!r}) — a target is only read as [ADR-NNN:L] or [D-N]"
                )
        for pattern, described in ENTRY_SKELETON:
            if not pattern.search(text):
                findings.append(f"entry-shape (§12): {rel} is missing {described}")
    return findings


def check_citations(base_sha: str, pr: int | None) -> list[str]:
    findings: list[str] = []
    statute = ROOT / STATUTE
    if not statute.is_file():
        return [f"citation (§12): {STATUTE} is missing"]
    text = statute.read_text(encoding="utf-8")
    lines = text.split("\n")

    for n, line in enumerate(lines, 1):
        if not line.strip() or line.startswith(("# ", "## ")) or RULE_UNIT.match(line):
            continue
        findings.append(
            f"citation (§12): {STATUTE}:{n} is neither a section heading nor a rule unit "
            f"— {line.strip()[:60]!r}"
        )
    for lead in _duplicate_lead_ins(text):
        findings.append(
            f"citation (§12): {STATUTE} states more than one rule with the lead-in {lead[:60]} "
            f"— a rule is identified by its lead-in, so it must be unique"
        )
    for n, line in enumerate(lines, 1):
        if RULE_UNIT.match(line) and not CITATION.search(line):
            findings.append(
                f"citation (§12): {STATUTE}:{n} rule unit does not end in a citation token"
            )

    known = _entry_numbers()
    for f in [statute, *sorted((ROOT / ADR_DIR).glob("*.md")), *_entry_files()]:
        rel = f.relative_to(ROOT).as_posix()
        for n, line in enumerate(f.read_text(encoding="utf-8").split("\n"), 1):
            for num, ln, frag in ADR_TOKEN.findall(line):
                target = list((ROOT / ADR_DIR).glob(f"ADR-{num}-*.md"))
                if not target:
                    findings.append(f"citation (§12): {rel}:{n} [ADR-{num}:{ln}] — no such ADR")
                    continue
                body = target[0].read_text(encoding="utf-8").split("\n")
                if not (1 <= int(ln) <= len(body)):
                    findings.append(
                        f"citation (§12): {rel}:{n} [ADR-{num}:{ln}] is out of bounds "
                        f"({target[0].name} has {len(body)} lines)"
                    )
                elif frag and frag not in body[int(ln) - 1]:
                    # The fragment is the reader's only check on a frozen line, so an
                    # unverified one is worse than none — it looks like corroboration.
                    findings.append(
                        f"citation (§12): {rel}:{n} [ADR-{num}:{ln}] quotes {frag!r}, which "
                        f"does not appear on that line"
                    )
            for num in D_TOKEN.findall(line):
                if int(num) not in known:
                    findings.append(f"citation (§12): {rel}:{n} [D-{num}] — no entry file for it")

    findings += _check_rule_changes(base_sha, text, pr)
    findings += _check_displacements()
    return findings


def _targets(text: str) -> set[tuple[str, str]]:
    """Both citation forms in one vocabulary. Reading only the ADR form made the
    displacement rule decay to nothing on exactly the forward path, since every
    rule minted after this migration cites [D-N]."""
    return ({(f"ADR-{a}", ln) for a, ln, _ in ADR_TOKEN.findall(text)}
            | {("D", n) for n in D_TOKEN.findall(text)})


def _show(tgt: tuple[str, str]) -> str:
    return f"[D-{tgt[1]}]" if tgt[0] == "D" else f"[{tgt[0]}:{tgt[1]}]"


def _declared() -> dict[int, set[tuple[str, str]]]:
    out: dict[int, set[tuple[str, str]]] = {}
    for f in _entry_files():
        num = int(ENTRY_NAME.match(f.name).group(1))
        m = DISPLACES.search(f.read_text(encoding="utf-8"))
        out[num] = _targets(m.group(1)) if m else set()
    return out


def _check_rule_changes(base_sha: str, head_text: str, pr: int | None) -> list[str]:
    """Per-rule, keyed on the bold lead-in. A whole-file token-set comparison let a
    rule drop its citation whenever any other rule still cited the same target —
    179 of 271 citation instances, on the corpus that motivated this."""
    findings: list[str] = []
    base_text = _at(base_sha, STATUTE)
    if base_text is None:
        return findings  # the statute is new in this change; nothing to compare
    was, now = _rules(base_text), _rules(head_text)
    # Scoped to THIS change's entry. A union over all history only grows, so a
    # target displaced once would license dropping it from any rule, forever.
    declared = _declared()
    declared_now = declared.get(pr, set()) if pr else set()

    for lead, line in now.items():
        if lead in was:
            for tgt in sorted(_targets(was[lead]) - _targets(line)):
                if tgt not in declared_now:
                    findings.append(
                        f"citation (§12): the rule {lead[:50]}… dropped its citation "
                        f"{_show(tgt)} and no entry declares it displaced"
                    )
        elif pr and f"[D-{pr}]" not in line:
            findings.append(
                f"citation (§12): the rule {lead[:50]}… is added in this change and does "
                f"not cite [D-{pr}]"
            )
    for lead in sorted(set(was) - set(now)):
        if not (_targets(was[lead]) & declared_now):
            findings.append(
                f"citation (§12): the rule {lead[:50]}… was removed from the statute and no "
                f"entry declares its displacement"
            )
    return findings


def _check_displacements() -> list[str]:
    findings: list[str] = []
    declared = _declared()
    pointers: dict[int, set[tuple[str, str]]] = {}
    # Entry status lines carry pointers too — globbing only the ADRs made an entry's
    # status line a lawful place to write a supersession claim nothing could see.
    for f in [*sorted((ROOT / ADR_DIR).glob("*.md")), *_entry_files()]:
        status = _status_line(f.read_text(encoding="utf-8")) or ""
        for pm in POINTER.finditer(status):
            tgt = pm.group(3)
            if tgt.startswith("ADR-"):
                adr, rest = tgt.split(":", 1)
                for ln in re.findall(r"\d+", rest):
                    pointers.setdefault(int(pm.group(1)), set()).add((adr, ln))
            else:
                pointers.setdefault(int(pm.group(1)), set()).add(("D", tgt.replace("D-", "")))

    for num, targets in declared.items():
        for tgt in sorted(targets):
            if tgt not in pointers.get(num, set()):
                findings.append(
                    f"citation (§12): D-{num} declares Displaces {_show(tgt)} but that record's "
                    f"status line carries no matching supersession pointer"
                )
    for num, targets in pointers.items():
        if num not in declared:
            findings.append(
                f"citation (§12): a supersession pointer names [D-{num}] but no such entry exists"
            )
            continue
        for tgt in sorted(targets):
            if tgt not in declared[num]:
                where = f"for line {tgt[1]} " if tgt[0] != "D" else ""
                findings.append(
                    f"citation (§12): a status line points at [D-{num}] {where}"
                    f"superseding {_show(tgt)}, which D-{num} does not list in Displaces"
                )
    return findings


def run(base: str, pr: int | None) -> list[str]:
    base_sha = _merge_base(base)
    return (
        check_append_only(base_sha)
        + check_entry_shape(base_sha)
        + check_citations(base_sha, pr)
    )


def main() -> int:
    # stdout is not UTF-8 by default on Windows, and findings echo document content
    # that contains characters cp1252 cannot encode — the guard died mid-report.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):  # pragma: no cover - non-reconfigurable stream
        pass
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--pr", type=int, default=None)
    args = ap.parse_args()
    if args.pr is None:
        print(
            "constitution: NOTE — no --pr given, so the added-rule check is skipped. "
            "CI passes it; a clean run here is weaker than a clean run there."
        )
    try:
        findings = run(args.base, args.pr)
    except Undetermined as exc:
        print(f"constitution: UNDETERMINED — {exc}")
        return 2
    for f in findings:
        print(f)
    print(f"constitution: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
