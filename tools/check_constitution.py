#!/usr/bin/env python3
"""Constitutional format guards — the statute and the decision log (D-53).

Two guards, both form/position/existence only. Correspondence — whether an
entry's content describes the change, whether a "Changes no operative rule"
declaration is true, whether meaning was preserved — is review's, and nothing
here is claimed to reach it (statute §12).

  1. append-only. Evaluated against the MERGE BASE, which is what makes the
     lifecycle work with no extra state: an entry is *accepted* when it is
     present at the merge base, and a frozen ADR is *frozen* when it carried
     its freeze marker there. Before that, both are drafts and freely
     revisable — including on the pull request that introduces them, which is
     why this guard can land in the same change as the files it guards.
     A diff touching an accepted entry or a frozen ADR beyond a status-line
     append of the fixed pointer form fails. Malformed appends fail. Entry
     filenames must match `D-<digits>-YYYY-MM-DD-<slug>.md`.

  2. citation. Every statute rule unit ends in a citation token; the statute
     holds nothing but section headings and rule units; `[ADR-NNN:L]` targets
     must exist and be line-bound; `[D-N]` targets must exist wherever the
     token appears in a constitutional file; a rule unit added in the diff
     must cite this pull request's own entry; and displacement is cross-checked
     in three directions so a pointer and a Displaces field cannot disagree.

Exit 0 clean, 1 with findings, **2 when the answer cannot be determined** —
a guard that goes quiet when its base has moved prints the same line as a
clean pass, and every failure mode it meets becomes invisible (statute §3).

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

FREEZE_MARKER = re.compile(r"^\*\*Frozen \d{4}-\d{2}-\d{2} by \[D-\d+\]\.\*\*")
STATUS_LINE = re.compile(r"^\*\*Status:\*\*")
# The one lawful post-freeze diff, and the one lawful edit to an accepted
# entry: a status-line append of exactly this shape (statute §12).
POINTER = re.compile(
    r" · Superseded in part by \[D-(\d+)\] \((\d{4}-\d{2}-\d{2})\): "
    r"(ADR-\d{3}:\d+(?:, \d+)*) — [^·]+"
)
ENTRY_NAME = re.compile(r"\AD-(\d+)-\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.md\Z")
RULE_UNIT = re.compile(r"\A- \*\*")
CITATION = re.compile(r"\[(?:ADR-\d{3}:\d+(?: \"[^\"]*\")?|D-\d+)\]\s*\Z")
ADR_TOKEN = re.compile(r"\[ADR-(\d{3}):(\d+)(?: \"[^\"]*\")?\]")
D_TOKEN = re.compile(r"\[D-(\d+)\]")
DISPLACES = re.compile(r"^\*\*Displaces:\*\*(.*)$", re.MULTILINE)


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
    """File content at a revision, or None when it did not exist there."""
    out = subprocess.run(
        ["git", "show", f"{sha}:{path}"], cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return out.stdout if out.returncode == 0 else None


def _changed(sha: str) -> list[str]:
    names = _git("diff", "--name-only", f"{sha}...HEAD").splitlines()
    return [n for n in names if n.strip()]


def _status_line(text: str) -> str | None:
    for line in text.split("\n"):
        if STATUS_LINE.match(line):
            return line
    return None


def _was_frozen(base_text: str | None) -> bool:
    if base_text is None:
        return False
    return any(FREEZE_MARKER.match(l) for l in base_text.split("\n"))


def check_append_only(base_sha: str) -> list[str]:
    findings: list[str] = []
    for path in _changed(base_sha):
        if not (path.startswith(f"{ADR_DIR}/ADR-") or path.startswith(f"{LOG_DIR}/")):
            continue
        base_text = _at(base_sha, path)
        head = (ROOT / path).read_text(encoding="utf-8") if (ROOT / path).is_file() else None

        if path.startswith(f"{LOG_DIR}/"):
            name = Path(path).name
            if name != "README.md" and not ENTRY_NAME.match(name):
                findings.append(
                    f"append-only (§12): {path} is not a lawful entry filename — "
                    f"expected D-<pr>-YYYY-MM-DD-<slug>.md"
                )
            accepted = base_text is not None
        else:
            accepted = _was_frozen(base_text)

        if not accepted:
            continue  # a draft, or not yet frozen at the base: freely revisable
        if head is None:
            findings.append(
                f"append-only (§12): {path} was accepted at the merge base and is "
                f"deleted at head — reversal is by superseding entry, never by removal"
            )
            continue

        b_lines, h_lines = base_text.split("\n"), head.split("\n")
        b_status, h_status = _status_line(base_text), _status_line(head)
        if b_status is None or h_status is None:
            findings.append(f"append-only (§12): {path} has no **Status:** line")
            continue
        # Everything except the status line must be byte-identical.
        if [l for l in b_lines if not STATUS_LINE.match(l)] != [
            l for l in h_lines if not STATUS_LINE.match(l)
        ]:
            findings.append(
                f"append-only (§12): {path} is accepted/frozen and changed outside "
                f"its status line — the only lawful diff is a status-line append"
            )
        if h_status != b_status:
            if not h_status.startswith(b_status):
                findings.append(
                    f"append-only (§12): {path} status line was rewritten rather than "
                    f"appended to"
                )
            else:
                appended = h_status[len(b_status):]
                if not POINTER.fullmatch(appended):
                    findings.append(
                        f"append-only (§12): {path} status-line append is malformed — "
                        f"expected ' · Superseded in part by [D-N] (YYYY-MM-DD): "
                        f"ADR-NNN:L[, L…] — <one clause>', got {appended!r}"
                    )
    return findings


def _entry_numbers() -> set[int]:
    d = ROOT / LOG_DIR
    if not d.is_dir():
        return set()
    out = set()
    for f in d.glob("D-*.md"):
        m = ENTRY_NAME.match(f.name)
        if m:
            out.add(int(m.group(1)))
    return out


def _constitutional_files() -> list[Path]:
    files = [ROOT / STATUTE]
    files += sorted((ROOT / ADR_DIR).glob("ADR-*.md"))
    files += sorted((ROOT / LOG_DIR).glob("D-*.md"))
    return [f for f in files if f.is_file()]


def check_citations(base_sha: str, pr: int | None) -> list[str]:
    findings: list[str] = []
    statute = ROOT / STATUTE
    if not statute.is_file():
        return [f"citation (§12): {STATUTE} is missing"]
    lines = statute.read_text(encoding="utf-8").split("\n")

    # The statute holds nothing but section headings and rule units. Content
    # outside that shape exits the citation regime silently, which is why the
    # shape is checked and not merely recommended.
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        if line.startswith(("# ", "## ")) or line.startswith("  ") or RULE_UNIT.match(line):
            continue
        findings.append(
            f"citation (§12): {STATUTE}:{n} is neither a section heading nor a rule "
            f"unit — {line[:60]!r}"
        )
    for n, line in enumerate(lines, 1):
        if RULE_UNIT.match(line) and not CITATION.search(line):
            findings.append(
                f"citation (§12): {STATUTE}:{n} rule unit does not end in a citation token"
            )

    known = _entry_numbers()
    for f in _constitutional_files():
        rel = f.relative_to(ROOT).as_posix()
        for n, line in enumerate(f.read_text(encoding="utf-8").split("\n"), 1):
            for num, ln in ADR_TOKEN.findall(line):
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
            for num in D_TOKEN.findall(line):
                if int(num) not in known:
                    findings.append(
                        f"citation (§12): {rel}:{n} [D-{num}] — no entry file for it"
                    )

    # A rule unit added in this diff must cite this pull request's own entry:
    # a new rule arrives with the decision that made it, or the entry is missing.
    base_statute = _at(base_sha, STATUTE)
    if base_statute is not None and pr:
        was = {l for l in base_statute.split("\n") if RULE_UNIT.match(l)}
        for n, line in enumerate(lines, 1):
            if RULE_UNIT.match(line) and line not in was:
                if f"[D-{pr}]" not in line:
                    findings.append(
                        f"citation (§12): {STATUTE}:{n} is a rule unit added in this "
                        f"change and does not cite [D-{pr}]"
                    )

    findings += _check_displacements(base_sha, known)
    return findings


def _check_displacements(base_sha: str, known: set[int]) -> list[str]:
    """Three directions, so a pointer and a Displaces field cannot disagree."""
    findings: list[str] = []
    declared: dict[int, set[tuple[str, str]]] = {}
    for f in sorted((ROOT / LOG_DIR).glob("D-*.md")):
        m = ENTRY_NAME.match(f.name)
        if not m:
            continue
        num = int(m.group(1))
        text = f.read_text(encoding="utf-8")
        d = DISPLACES.search(text)
        declared[num] = set(ADR_TOKEN.findall(d.group(1))) if d else set()

    pointers: dict[int, set[tuple[str, str]]] = {}
    for f in sorted((ROOT / ADR_DIR).glob("ADR-*.md")):
        status = _status_line(f.read_text(encoding="utf-8")) or ""
        for pm in POINTER.finditer(status):
            n = int(pm.group(1))
            adr = pm.group(3).split(":")[0].replace("ADR-", "")
            for ln in re.findall(r"\d+", pm.group(3).split(":", 1)[1]):
                pointers.setdefault(n, set()).add((adr, ln))

    # (i) every Displaces target has its pointer appended
    for num, targets in declared.items():
        for adr, ln in targets:
            if (adr, ln) not in pointers.get(num, set()):
                findings.append(
                    f"citation (§12): D-{num} declares Displaces ADR-{adr}:{ln} but that "
                    f"ADR's status line carries no matching supersession pointer"
                )
    # (ii) every pointer naming [D-N] is matched by that entry's Displaces
    for num, targets in pointers.items():
        if num not in declared:
            findings.append(
                f"citation (§12): a supersession pointer names [D-{num}] but no such entry exists"
            )
            continue
        for adr, ln in targets:
            if (adr, ln) not in declared[num]:
                findings.append(
                    f"citation (§12): ADR-{adr}'s status line points at [D-{num}] for line "
                    f"{ln}, which D-{num} does not list in Displaces"
                )
    # (iii) a statute citation that migrated [ADR-NNN:L] -> [D-N] must be declared
    base_statute = _at(base_sha, STATUTE)
    if base_statute is not None:
        was = set(ADR_TOKEN.findall(base_statute))
        now = set(ADR_TOKEN.findall((ROOT / STATUTE).read_text(encoding="utf-8")))
        for adr, ln in sorted(was - now):
            if not any((adr, ln) in t for t in declared.values()):
                findings.append(
                    f"citation (§12): [ADR-{adr}:{ln}] was cited in the statute at the "
                    f"merge base and is gone at head, with no entry declaring it displaced"
                )
    return findings


def run(base: str, pr: int | None) -> list[str]:
    base_sha = _merge_base(base)
    return check_append_only(base_sha) + check_citations(base_sha, pr)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--pr", type=int, default=None)
    args = ap.parse_args()
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
