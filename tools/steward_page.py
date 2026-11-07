# Design: tools/DESIGN.md#the-standing-page
"""Edit the Steward's standing page one entry at a time, and archive what leaves it."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import secrets
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import steward_watch as sw  # noqa: E402
from winio import utf8_stdio  # noqa: E402  (steward_watch puts lib/ on the path)

LIMIT = 20_000
# GitHub's comment cap counts UTF-8 bytes, whatever its refusal message says.
ARCHIVE_CAP = 262_144
# Aliases per GraphQL query: few calls for a whole page, each well inside GitHub's per-query cost.
GRAPHQL_BATCH = 50
GH_NO_SUCH_NUMBER = "Could not resolve to"

PART_ORDER = ("body", "steward", "read", "ready", "flight", "traps", "residues")
COMMENT_PARTS = PART_ORDER[1:]
TITLES = {
    "body": "Rulings a holder applies",
    "steward": "The Steward's part",
    "read": "The latest read",
    "ready": "Ready for a holder session",
    "flight": "In flight",
    "traps": "Traps",
    "residues": "Residues",
}
# Rulings retire only when their carrying change lands; every other kind leaves on any close.
RULING_KINDS = ("ruling", "steward-ruling")
KIND_PART = {
    "ruling": "body",
    "steward-ruling": "steward",
    "owner-wait": "steward",
    "owed": "steward",
    "read": "read",
    "ready": "ready",
    "flight": "flight",
    "trap": "traps",
    "residue": "residues",
}

PART_MARKER = re.compile(
    r"<!-- lab:steward-part:v1 part=(?P<part>[a-z]+)(?P<attrs>(?: [a-z]+=\S+)*) -->")
ENTRY_MARKER = re.compile(
    r"<!-- lab:steward-entry:v1 id=(?P<id>[0-9a-f]{8}) kind=(?P<kind>[a-z-]+) "
    r"issue=(?P<issue>[^\s>]+?)(?P<kept> kept=yes)? -->")
# A list number runs to nine digits at most, as in CommonMark; a longer one is plain text.
ITEM = re.compile(r"(?:[-*+]|\d{1,9}[.)])(?:[ \t]+|$)")
ENTRY_LINE = re.compile(
    r"(?P<prefix>(?:[-*+]|\d{1,9}[.)])[ \t]+)(?P<content>.*?)[ \t]*"
    + ENTRY_MARKER.pattern + r"[ \t]*")
OVER_MARKER = "<!-- lab:steward-over:v1 -->"
OVER_LINE = re.compile(re.escape(f"> **Over its {LIMIT:,}-byte limit at ") + r"[\d,]+"
                       + re.escape(" bytes:** ") + r"(?P<reason>.+)")
INDEX_BEGIN = "<!-- lab:steward-index:v1 begin -->"
INDEX_END = "<!-- lab:steward-index:v1 end -->"
ARCHIVE_ISSUE_MARKER = "<!-- lab:steward-archive-issue:v1 -->"
# The archive's second line names its page, so a probe page's archive is never taken for #683's.
ARCHIVE_PAGE_LINE = "<!-- lab:steward-archive-page:v1 page={page} -->"
MOVE_MARKER = "<!-- lab:steward-archive:v1 event=move -->"
ARCHIVE_MARKER = re.compile(r"<!-- lab:steward-archive:v1 (?:read=(?P<read>\d+)|event=move) -->")
KEPT_WORDS = "Kept after its issue closed: "
REF = re.compile(r"(?P<repo>[A-Za-z0-9._-]+)#(?P<number>[1-9]\d*)")

ARCHIVE_ISSUE_PROSE = (
    "The Steward's archive for the standing page: what has left it, posted word for word, "
    "one comment per cross-change read. It stays closed.")


class PageError(Exception):
    """A refusal the Steward must see, with whatever lets it act on it."""

    def __init__(self, message: str, **detail):
        super().__init__(message)
        self.detail = detail


# ---------------------------------------------------------------- text


def normalise(text: str | None) -> str:
    # GitHub may keep a leading byte-order mark or CRLF endings; neither is text the Steward sees,
    # so every read of the page goes through here and neither ever counts as a change.
    return (text or "").lstrip(sw.BOM).replace("\r\n", "\n")


def size(text: str) -> int:
    return len(text.encode("utf-8"))


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Marker kinds this tool reads as structure; a mention of the wake's own marker is harmless.
STRUCTURE = ("lab:steward-part", "lab:steward-entry", "lab:steward-over", "lab:steward-index",
             "lab:steward-archive")


def clean(text: str, what: str, markers_ok: bool = False) -> str:
    """Refuse what would put a control character, or a stray structure marker, on the page."""
    # A control character renders invisibly or garbles the page, and hand-written edits have put
    # them there before; newline and tab are the only ones Markdown means.
    if sw.BOM in text:
        raise PageError(f"{what} carries a byte-order mark; save it as UTF-8 without one")
    text = normalise(text)
    for number, line in enumerate(text.split("\n"), 1):
        for char in line:
            if (ord(char) < 0x20 and char != "\t") or 0x7F <= ord(char) <= 0x9F:
                raise PageError(f"{what} line {number} carries the control character "
                                f"U+{ord(char):04X}; nothing written")
    for marker in STRUCTURE:
        if marker in text and not markers_ok:
            raise PageError(f"{what} carries {marker}; the tool writes every such marker itself")
    return text


def read_file(path: str, what: str, markers_ok: bool = False) -> str:
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise PageError(f"{what} {path} could not be read: {exc}") from exc
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PageError(f"{what} {path} is not UTF-8: {exc}") from exc
    return clean(text, f"{what} {path}", markers_ok)


def one_line(text: str, what: str) -> str:
    text = clean(text, what).strip()
    if not text or "\n" in text:
        raise PageError(f"{what} must be one non-empty line")
    return text


def lab_short_names() -> list[str]:
    return [repo.split("/", 1)[1] for repo in sw.lab_repos()]


def check_ref(ref: str, names: list[str]) -> str:
    if ref == "none":
        return ref
    match = REF.fullmatch(ref)
    if not match or match.group("repo") not in names:
        raise PageError(f"issue {ref!r} is neither none nor REPO#N in one of the lab's "
                        "repositories (" + ", ".join(names) + ")")
    return ref


# ---------------------------------------------------------------- entries


def entry_marker(eid: str, kind: str, issue: str, kept: bool) -> str:
    return (f"<!-- lab:steward-entry:v1 id={eid} kind={kind} issue={issue}"
            + (" kept=yes" if kept else "") + " -->")


class Entry:
    """One top-level list item: its marked first line and the lines that follow it."""

    def __init__(self, eid: str, kind: str, issue: str, kept: bool, lines: list[str]):
        self.id, self.kind, self.issue, self.kept, self.lines = eid, kind, issue, kept, lines

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def parts_of_first(self) -> tuple[str, str]:
        match = ENTRY_LINE.fullmatch(self.lines[0])
        return match.group("prefix"), match.group("content")

    def first_words(self, width: int = 120) -> str:
        return self.parts_of_first()[1][:width]

    def kept_reason(self) -> str | None:
        if not self.kept:
            return None
        if len(self.lines) == 1:
            content = self.parts_of_first()[1]
            index = content.rfind(" " + KEPT_WORDS)
            return content[index + 1 + len(KEPT_WORDS):] if index >= 0 else None
        last = self.lines[-1].strip()
        return last[len(KEPT_WORDS):] if last.startswith(KEPT_WORDS) else None

    def with_mark(self, issue: str | None = None, kept: bool | None = None,
                  reason: str | None = None) -> "Entry":
        """The same entry with its marker changed, and its shown kept reason set or cleared."""
        issue = self.issue if issue is None else issue
        kept = self.kept if kept is None else kept
        prefix, content = self.parts_of_first()
        lines = list(self.lines)
        old = self.kept_reason() if self.kept else None
        if old is not None:
            if len(lines) == 1:
                content = content[:content.rfind(" " + KEPT_WORDS)]
            else:
                lines.pop()
        if kept and reason is not None and len(lines) == 1 and self.kind == "ready":
            content = f"{content} {KEPT_WORDS}{reason}"
        lines[0] = f"{prefix}{content} {entry_marker(self.id, self.kind, issue, kept)}"
        if kept and reason is not None and not (len(lines) == 1 and self.kind == "ready"):
            lines.append(" " * len(prefix) + KEPT_WORDS + reason)
        return Entry(self.id, self.kind, issue, kept, lines)


def build_entry(eid: str, kind: str, issue: str, text: str,
                reason: str | None = None) -> Entry:
    """An entry from the Steward's text: the tool adds the list prefix and the marker."""
    text = text.strip("\n").rstrip()
    if not text.strip():
        raise PageError("the entry's text is empty")
    lines = text.split("\n")
    lines[0] = lines[0].strip()
    if ITEM.match(lines[0]):
        raise PageError("write the entry's text without its list prefix; the tool adds it")
    if kind == "ready" and len(lines) > 1:
        raise PageError("a ready entry is one line: the issue, its defect in plain words, "
                        "and its place")
    prefix = "1. " if kind == "ready" else "- "
    first = f"{prefix}{lines[0]} {entry_marker(eid, kind, issue, False)}"
    rest = [(" " * len(prefix) + line) if line.strip() else "" for line in lines[1:]]
    entry = Entry(eid, kind, issue, False, [first] + rest)
    return entry.with_mark(kept=True, reason=reason) if reason is not None else entry


# ---------------------------------------------------------------- parts


class Part:
    """One part: its marker lines, any over-limit reason, its preamble and its entries."""

    def __init__(self, name: str, comment_id: int | None = None, live: str | None = None):
        self.name = name
        self.comment_id = comment_id
        self.live = live
        self.marked = True
        self.archive: int | None = None
        self.over_reason: str | None = None
        self.index: list[str] = []
        self.preamble: list[str] = []
        self.entries: list[Entry] = []
        self.faults: list[str] = []

    def header(self) -> list[str]:
        if self.name == "body":
            attrs = f" archive={self.archive}" if self.archive else ""
            return [f"<!-- lab:steward-part:v1 part=body{attrs} -->"]
        return [sw.marker_line("post"), f"<!-- lab:steward-part:v1 part={self.name} -->"]


def strip_blank(lines: list[str]) -> list[str]:
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def parse_part(name: str, text: str, names: list[str], comment_id: int | None = None) -> Part:
    """Split a part's text into its pieces; anything the tool cannot place is a fault."""
    part = Part(name, comment_id, text)
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    top = 1 if name == "body" else 2
    if name == "body":
        attrs = dict(sw.ATTR.findall(PART_MARKER.fullmatch(lines[0].rstrip()).group("attrs")))
        archive = attrs.get("archive", "")
        if set(attrs) - {"archive"}:
            part.faults.append("body: the page marker carries an attribute other than archive=N")
        if not archive.isdigit() or int(archive) == 0:
            part.faults.append("body: the page marker names no archive issue as archive=N")
        part.archive = int(archive) if archive.isdigit() and int(archive) > 0 else None
    rest = lines[top:]
    first = next((i for i, line in enumerate(rest) if ENTRY_LINE.fullmatch(line)), len(rest))
    pre = list(rest[:first])

    def where(offset: int) -> str:
        return f"{name} line {top + offset + 1}"

    for offset, line in enumerate(rest):
        if "lab:steward-entry:v1" in line and not ENTRY_LINE.fullmatch(line):
            part.faults.append(f"{where(offset)}: an entry marker that does not end a "
                               "top-level list item's first line")
    if OVER_MARKER in pre:
        at = pre.index(OVER_MARKER)
        reason = OVER_LINE.fullmatch(pre[at + 1]) if at + 1 < len(pre) else None
        if reason:
            part.over_reason = reason.group("reason")
            del pre[at:at + 2]
        else:
            part.faults.append(f"{where(at)}: an over-limit marker with no reason line under it")
            del pre[at]
    for offset, line in enumerate(rest[first:], first):
        if line == OVER_MARKER:
            part.faults.append(f"{where(offset)}: an over-limit marker below the first entry")
    if INDEX_BEGIN in pre or INDEX_END in pre:
        if (name != "body" or INDEX_BEGIN not in pre or INDEX_END not in pre
                or pre.index(INDEX_END) < pre.index(INDEX_BEGIN)):
            part.faults.append(f"{name}: an index block out of place, out of order, or missing "
                               "its other end")
        else:
            begin, end = pre.index(INDEX_BEGIN), pre.index(INDEX_END)
            part.index = pre[begin:end + 1]
            del pre[begin:end + 1]
    part.preamble = strip_blank(pre)
    current: Entry | None = None
    for offset, line in enumerate(rest[first:], first):
        match = ENTRY_LINE.fullmatch(line)
        if match:
            kind, issue = match.group("kind"), match.group("issue")
            current = Entry(match.group("id"), kind, issue, bool(match.group("kept")), [line])
            part.entries.append(current)
            if kind not in KIND_PART:
                part.faults.append(f"{where(offset)}: unknown kind {kind}")
            elif KIND_PART[kind] != name:
                part.faults.append(f"{where(offset)}: a {kind} entry ({current.id}) belongs in "
                                   f"the {KIND_PART[kind]} part, not {name}")
            try:
                check_ref(issue, names)
            except PageError as exc:
                part.faults.append(f"{where(offset)}: {exc}")
        elif ITEM.match(line):
            part.faults.append(f"{where(offset)}: a top-level list item with no entry marker")
        else:
            current.lines.append(line)
    for entry in part.entries:
        entry.lines = strip_blank(entry.lines)
        if entry.kept and entry.kept_reason() is None:
            # A rewrite would carry no reason forward, so a kept entry whose reason is unreadable
            # must be repaired before anything writes over it.
            part.faults.append(f"{name}: kept entry {entry.id} shows no readable "
                               f"'{KEPT_WORDS.strip()}' reason")
        if entry.kind == "ready" and len(entry.lines) > 1:
            part.faults.append(f"{name}: ready entry {entry.id} spans {len(entry.lines)} lines")
    return part


def unified(before: str, after: str, label_before: str, label_after: str) -> str:
    return "".join(difflib.unified_diff(before.splitlines(keepends=True),
                                        after.splitlines(keepends=True),
                                        fromfile=label_before, tofile=label_after))


def archived_entries(text: str) -> list[str]:
    """Each whole entry an archive comment holds, from its marked line to the entry's end."""
    found: list[list[str]] = []
    current: list[str] | None = None
    for line in normalise(text).split("\n"):
        if ENTRY_LINE.fullmatch(line):
            current = [line]
            found.append(current)
        elif line.startswith("#"):
            # Entries sit under part headings and every continuation line is indented, so a
            # column-0 heading ends the entry before it.
            current = None
        elif current is not None:
            current.append(line)
    return ["\n".join(strip_blank(lines)) for lines in found]


def render(part: Part, index: list[str], over_line: str | None = None) -> str:
    blocks = ["\n".join(part.header())]
    if over_line:
        blocks.append(OVER_MARKER + "\n" + over_line)
    if part.name == "body":
        blocks.append("\n".join(index))
    if part.preamble:
        blocks.append("\n".join(part.preamble))
    if part.entries:
        lines = []
        for number, entry in enumerate(part.entries, 1):
            first = entry.lines[0]
            if part.name == "ready":
                # Holders take ready work in this order, so an item's number is its place in line.
                first = f"{number}. " + first[ITEM.match(first).end():]
            lines.extend([first] + entry.lines[1:])
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def over_line(bytes_: int, reason: str) -> str:
    return f"> **Over its {LIMIT:,}-byte limit at {bytes_:,} bytes:** {reason}"


# ---------------------------------------------------------------- the page


class Page:
    """The body and every counted part comment, read once."""

    def __init__(self, number: int, body: str, comments: list[dict], names: list[str]):
        self.number = number
        self.names = names
        self.faults: list[str] = []
        self.not_counted: list[int] = []
        self.misplaced: set[str] = set()
        self.parts: dict[str, Part] = {}
        first = body.split("\n", 1)[0].rstrip()
        mark = PART_MARKER.fullmatch(first)
        if mark and mark.group("part") == "body":
            self.body = parse_part("body", body, names)
        else:
            self.body = Part("body", None, body)
            self.body.marked = False
        seen: dict[str, int] = {}
        for comment in sorted(comments, key=lambda c: int(c["id"])):
            text = normalise(comment.get("body"))
            lines = text.split("\n")
            match = PART_MARKER.fullmatch(lines[1].rstrip()) if len(lines) > 1 else None
            cid = int(comment["id"])
            if not match:
                stray = [PART_MARKER.fullmatch(line.rstrip()) for line in lines]
                stray = [m for m in stray if m]
                if stray and (sw.classify_comment(comment) or {}).get("kind") == "post":
                    self.misplaced.update(m.group("part") for m in stray)
                    self.faults.append(f"comment {cid} carries a part marker off its second line; "
                                       "move it to line two by hand, then accept the part")
                continue
            if (sw.classify_comment(comment) or {}).get("kind") != "post":
                self.not_counted.append(cid)
                continue
            name = match.group("part")
            if name not in COMMENT_PARTS or match.group("attrs"):
                self.faults.append(f"comment {cid} carries an unknown part marker")
                continue
            if name in seen:
                self.faults.append(f"part {name} is carried by two comments, {seen[name]} and "
                                   f"{cid}; delete one or remove its part marker")
                continue
            seen[name] = cid
            self.parts[name] = parse_part(name, text, names, cid)
        ids: dict[str, str] = {}
        for part in self.all_parts():
            for entry in part.entries:
                if entry.id in ids:
                    self.faults.append(f"entry id {entry.id} appears in {ids[entry.id]} and "
                                       f"{part.name}")
                ids[entry.id] = part.name

    def all_parts(self) -> list[Part]:
        found = [self.body] if self.body.marked else []
        return found + [self.parts[n] for n in COMMENT_PARTS if n in self.parts]

    def all_faults(self) -> list[str]:
        return self.faults + [f for part in self.all_parts() for f in part.faults]

    def link(self, comment_id: int | None = None) -> str:
        base = f"https://github.com/{sw.LAB_REPO}/issues/{self.number}"
        return base if comment_id is None else f"{base}#issuecomment-{comment_id}"

    def index(self) -> list[str]:
        lines = [INDEX_BEGIN, "**The page's other parts:**", ""]
        for name in COMMENT_PARTS:
            part = self.parts.get(name)
            if part is None:
                lines.append(f"- {TITLES[name]} (not yet created)")
            else:
                lines.append(f"- [{TITLES[name]}]({self.link(part.comment_id)})")
        return lines + ["", INDEX_END]

    def part(self, name: str) -> Part:
        if name == "body":
            if not self.body.marked:
                raise PageError("the body carries no page marker yet; the move's body "
                                "command writes it")
            return self.body
        if name not in COMMENT_PARTS:
            raise PageError(f"unknown part {name}; the parts are " + ", ".join(PART_ORDER))
        if name not in self.parts:
            raise PageError(f"part {name} is not yet created; run create-part {name}")
        return self.parts[name]

    def find(self, eid: str) -> tuple[Part, int, Entry]:
        for part in self.all_parts():
            for at, entry in enumerate(part.entries):
                if entry.id == eid:
                    return part, at, entry
        raise PageError(f"no entry {eid} on the page")

    def ids(self) -> set[str]:
        return {e.id for part in self.all_parts() for e in part.entries}

    def new_id(self, taken: set[str] = frozenset()) -> str:
        used = self.ids() | set(taken)
        while True:
            eid = secrets.token_hex(4)
            if eid not in used:
                return eid


def place(entries: list[Entry], entry: Entry, position: int | None, after: str | None) -> None:
    if after is not None:
        at = next((i for i, e in enumerate(entries) if e.id == after), None)
        if at is None:
            raise PageError(f"--after {after}: no such entry in that part")
        entries.insert(at + 1, entry)
    elif position is not None:
        if not 1 <= position <= len(entries) + 1:
            raise PageError(f"--position {position} is outside 1..{len(entries) + 1}")
        entries.insert(position - 1, entry)
    else:
        entries.append(entry)


# ---------------------------------------------------------------- issue state


def resolve_states(github: sw.GitHub, refs: list[str]) -> tuple[dict, dict]:
    """Each reference's state: open, landed, or closed (without landing); else an error."""
    states: dict[str, str] = {}
    errors: dict[str, str] = {}
    refs = sorted(set(r for r in refs if r != "none" and REF.fullmatch(r)))

    def query(chunk: list[str]) -> None:
        fields = []
        for at, ref in enumerate(chunk):
            repo, number = ref.split("#")
            fields.append(
                f'r{at}: repository(owner: "{sw.OWNER}", name: "{repo}") '
                f"{{ issueOrPullRequest(number: {number}) {{ __typename "
                "... on Issue { state stateReason } ... on PullRequest { state merged } } }")
        try:
            answer = github.send("POST", "graphql", {"query": "query { " + " ".join(fields) + " }"})
        except sw.WatchError as exc:
            if GH_NO_SUCH_NUMBER not in str(exc):
                raise PageError(f"issue states could not be read: {exc}") from exc
            # One unresolvable reference fails its whole query, so the batch is retried singly to
            # name it and still resolve the rest.
            if len(chunk) > 1:
                for ref in chunk:
                    query([ref])
                return
            errors[chunk[0]] = str(exc)
            return
        data = (answer or {}).get("data") or {}
        for at, ref in enumerate(chunk):
            node = (data.get(f"r{at}") or {}).get("issueOrPullRequest")
            if not node:
                errors[ref] = "could not be resolved"
            elif node.get("state") == "OPEN":
                states[ref] = "open"
            elif node.get("__typename") == "PullRequest":
                states[ref] = "landed" if node.get("merged") else "closed"
            else:
                states[ref] = "landed" if node.get("stateReason") == "COMPLETED" else "closed"

    for start in range(0, len(refs), GRAPHQL_BATCH):
        query(refs[start:start + GRAPHQL_BATCH])
    return states, errors


def closed_lists(page: Page, states: dict) -> dict:
    lists = {"closed": [], "closed_without_landing": [], "kept": []}
    for part in page.all_parts():
        for entry in part.entries:
            row = {"id": entry.id, "kind": entry.kind, "issue": entry.issue, "part": part.name,
                   "state": states.get(entry.issue, "none" if entry.issue == "none" else "unknown"),
                   "first": entry.first_words()}
            if entry.kept:
                lists["kept"].append({**row, "reason": entry.kept_reason()})
            elif states.get(entry.issue) in ("landed", "closed"):
                if entry.kind in RULING_KINDS and states[entry.issue] != "landed":
                    lists["closed_without_landing"].append(row)
                else:
                    lists["closed"].append(row)
    return lists


# ---------------------------------------------------------------- the tool


class PageTool:
    def __init__(self, github: sw.GitHub, page: int, state_dir: Path, now: datetime):
        self.github = github
        self.number = page
        self.state_dir = state_dir
        self.now = now
        self.names = lab_short_names()
        self.writes: list[dict] = []

    # -- reading

    def load(self) -> Page:
        issue = self.github.get(f"repos/{sw.LAB_REPO}/issues/{self.number}")
        comments = self.github.comments(sw.LAB_REPO, self.number)
        return Page(self.number, normalise(issue.get("body")), comments, self.names)

    def load_for_write(self) -> Page:
        page = self.load()
        faults = page.all_faults()
        if faults:
            raise PageError("the page has faults; nothing written. Repair each by hand, then "
                            "accept the part", faults=faults)
        return page

    def fetch(self, name: str, comment_id: int | None) -> str:
        if name == "body":
            return normalise(self.github.get(f"repos/{sw.LAB_REPO}/issues/{self.number}").get("body"))
        comment = self.github.get(f"repos/{sw.LAB_REPO}/issues/comments/{comment_id}")
        return normalise(comment.get("body"))

    # -- the saved copy

    def copy_path(self, name: str) -> Path:
        return self.state_dir / f"page-{self.number}" / f"{name}.json"

    def copy_state(self, name: str, live: str, comment_id: int | None) -> str:
        saved = sw.read_json(self.copy_path(name), None)
        if saved is None:
            return "no-copy"
        if saved.get("text") != live or saved.get("comment_id") != comment_id:
            return "differs"
        return "in-step"

    def check_copy(self, name: str, live: str, comment_id: int | None) -> None:
        saved = sw.read_json(self.copy_path(name), None)
        if saved is None:
            raise PageError(f"no saved copy of the {name} part, so nothing was written to it. "
                            f"Read the live part below, then run accept {name} --sha SHA",
                            part=name, live=live, live_sha256=sha256(live))
        if saved.get("text") != live or saved.get("comment_id") != comment_id:
            diff = unified(saved.get("text") or "", live, f"{name} (saved copy)", f"{name} (live)")
            if saved.get("comment_id") != comment_id:
                diff = (f"comment id: saved {saved.get('comment_id')}, live {comment_id}\n") + diff
            raise PageError(f"the live {name} part differs from the saved copy, so nothing was "
                            f"written to it. Review the difference, then run accept {name} "
                            "--sha SHA and redo the edit", part=name, diff=diff,
                            live_sha256=sha256(live))

    def save_copy(self, name: str, text: str, comment_id: int | None) -> None:
        sw.write_json_atomic(self.copy_path(name), {
            "schema_version": 1, "part": name, "page": self.number, "comment_id": comment_id,
            "text": text, "sha256": sha256(text)})

    # -- writing

    def finalize(self, page: Page, part: Part, over: str | None) -> str:
        """The part's text to write, refused over the limit unless a reason is given."""
        plain = render(part, page.index())
        if size(plain) <= LIMIT:
            part.over_reason = None
            return plain
        if over is None:
            raise PageError(f"the {part.name} part would be {size(plain):,} bytes, over its "
                            f"{LIMIT:,}-byte limit; nothing written. Shorten it, or give "
                            "--over-reason", part=part.name, bytes=size(plain))
        if over == "same":
            if not part.over_reason:
                raise PageError(f"--over-reason same, but the {part.name} part shows no reason; "
                                "nothing written", part=part.name, bytes=size(plain))
            reason = part.over_reason
        else:
            reason = one_line(over, "--over-reason")
        # The shown size counts its own digits, so render until it equals the text's own size.
        guess = size(plain)
        while True:
            text = render(part, page.index(), over_line(guess, reason))
            if size(text) == guess:
                part.over_reason = reason
                return text
            guess = size(text)

    def write(self, page: Page, name: str, comment_id: int | None, text: str, loaded: str) -> None:
        live = self.fetch(name, comment_id)
        self.check_copy(name, live, comment_id)
        if live != loaded:
            # Another run may have written the part and its saved copy since this one read it.
            raise PageError(f"the live {name} part changed after this command read it, so nothing "
                            "was written to it; run the command again", part=name,
                            diff=unified(loaded, live, f"{name} (as read)", f"{name} (live)"),
                            live_sha256=sha256(live))
        endpoint = (f"repos/{sw.LAB_REPO}/issues/{self.number}" if name == "body"
                    else f"repos/{sw.LAB_REPO}/issues/comments/{comment_id}")
        self.github.send("PATCH", endpoint, {"body": text})
        self.writes.append({"part": name, "url": page.link(comment_id)})
        back = self.fetch(name, comment_id)
        if back != text:
            raise PageError(f"the {name} part read back differently from what was written; the "
                            "saved copy is unchanged, so the next edit will show the difference",
                            part=name, written=self.writes)
        self.save_copy(name, text, comment_id)

    def commit(self, page: Page, names: list[str], over: str | None) -> None:
        prepared = []
        for name in names:
            part = page.part(name)
            text = self.finalize(page, part, over)
            self.check_copy(name, part.live, part.comment_id)
            prepared.append((name, part.comment_id, text, part.live))
        for name, comment_id, text, loaded in prepared:
            self.write(page, name, comment_id, text, loaded)

    def result(self, **fields) -> dict:
        return {"schema_version": 1, **fields, "writes": self.writes}

    # -- commands

    def status(self) -> dict:
        page = self.load()
        refs = [e.issue for part in page.all_parts() for e in part.entries]
        states, errors = resolve_states(self.github, refs)
        parts = {}
        for name in PART_ORDER:
            part = page.body if name == "body" else page.parts.get(name)
            if part is None:
                parts[name] = {"missing": True}
                continue
            row = {"link": page.link(part.comment_id), "bytes": size(part.live), "limit": LIMIT,
                   "over": size(part.live) > LIMIT, "over_reason": part.over_reason,
                   "copy": self.copy_state(name, part.live, part.comment_id),
                   "faults": part.faults, "entries": len(part.entries)}
            if name == "body":
                row.update({"page_marker": part.marked, "archive": part.archive,
                            "rulings": [e.id for e in part.entries if e.kind == "ruling"],
                            "ruling_count": sum(e.kind == "ruling" for e in part.entries),
                            "index_current": part.marked and part.index == page.index()})
            parts[name] = row
        return {"schema_version": 1, "page": page.link(), "parts": parts,
                "missing": [n for n in COMMENT_PARTS
                            if n not in page.parts and n not in page.misplaced],
                "faults": page.all_faults(), "not_counted": page.not_counted,
                **closed_lists(page, states),
                "unresolved": [{"issue": k, "error": v} for k, v in sorted(errors.items())]}

    def show(self, name: str) -> dict:
        page = self.load()
        part = page.body if name == "body" else page.part(name)
        return {"schema_version": 1, "part": name, "link": page.link(part.comment_id),
                "sha256": sha256(part.live), "bytes": size(part.live), "text": part.live,
                "faults": part.faults,
                "entries": [{"id": e.id, "kind": e.kind, "issue": e.issue, "kept": e.kept,
                             "first": e.first_words()} for e in part.entries]}

    def accept(self, name: str, sha: str) -> dict:
        page = self.load()
        part = page.body if name == "body" else page.part(name)
        live = self.fetch(name, part.comment_id)
        if sha256(live) != sha:
            raise PageError(f"the live {name} part's SHA-256 is no longer {sha}; nothing "
                            "accepted. Read it again", part=name, live=live, live_sha256=sha256(live))
        self.save_copy(name, live, part.comment_id)
        return self.result(accepted=name, sha256=sha)

    def add(self, kind: str, issue: str, text: str, position: int | None, after: str | None,
            over: str | None) -> dict:
        page = self.load_for_write()
        name = KIND_PART[kind]
        part = page.part(name)
        entry = build_entry(page.new_id(), kind, check_ref(issue, self.names), text)
        place(part.entries, entry, position, after)
        self.commit(page, [name], over)
        return self.result(added=entry.id, part=name)

    def replace(self, eid: str, text: str | None, issue: str | None, clear_kept: bool,
                over: str | None) -> dict:
        if text is None and issue is None and not clear_kept:
            raise PageError("replace needs --text-file, --issue or --clear-kept")
        page = self.load_for_write()
        part, at, entry = page.find(eid)
        issue = entry.issue if issue is None else check_ref(issue, self.names)
        reason = entry.kept_reason() if entry.kept and not clear_kept else None
        if text is not None:
            new = build_entry(entry.id, entry.kind, issue, text, reason)
        else:
            new = entry.with_mark(issue=issue, kept=entry.kept and not clear_kept, reason=reason)
        part.entries[at] = new
        self.commit(page, [part.name], over)
        return self.result(replaced=eid, part=part.name)

    def move(self, eid: str, position: int | None, after: str | None, kind: str | None,
             text: str | None, over: str | None) -> dict:
        page = self.load_for_write()
        source, at, entry = page.find(eid)
        if kind is None:
            if text is not None:
                raise PageError("--text-file applies to a move to another kind")
            if position is None and after is None:
                raise PageError("move needs --position, --after or --kind")
            if after == eid:
                raise PageError("an entry cannot move after itself")
            source.entries.pop(at)
            place(source.entries, entry, position, after)
            self.commit(page, [source.name], over)
            return self.result(moved=eid, part=source.name)
        if entry.kind == "ruling" or kind == "ruling":
            raise PageError("a ruling a holder applies stays in the body until it retires, and "
                            "only rulings belong there; nothing written")
        if text is None:
            raise PageError("a move to another kind takes its new text from --text-file")
        new = build_entry(entry.id, kind, entry.issue, text, entry.kept_reason())
        target = page.part(KIND_PART[kind])
        if target is source:
            source.entries.pop(at)
            if position is None and after is None:
                source.entries.insert(at, new)
            else:
                place(source.entries, new, position, after)
            self.commit(page, [source.name], over)
        else:
            place(target.entries, new, position, after)
            source.entries.pop(at)
            # The destination is written first: a failure between leaves a duplicate, not a loss.
            self.commit(page, [target.name, source.name], over)
        return self.result(moved=eid, part=target.name)

    def keep(self, eid: str, reason: str, over: str | None) -> dict:
        reason = one_line(reason, "--reason")
        page = self.load_for_write()
        part, at, entry = page.find(eid)
        part.entries[at] = entry.with_mark(kept=True, reason=reason)
        self.commit(page, [part.name], over)
        return self.result(kept=eid, part=part.name)

    def preamble(self, name: str, text: str, over: str | None) -> dict:
        page = self.load_for_write()
        part = page.part(name)
        part.preamble = strip_blank(text.split("\n"))
        self.commit(page, [name], over)
        return self.result(preamble=name)

    def create_part(self, name: str, text: str, over: str | None) -> dict:
        if name not in COMMENT_PARTS:
            raise PageError(f"create-part takes one of {', '.join(COMMENT_PARTS)}; the body is "
                            "the issue itself")
        page = self.load_for_write()
        if name in page.parts:
            raise PageError(f"part {name} already exists", link=page.link(page.parts[name].comment_id))
        part = Part(name)
        part.preamble = strip_blank(text.split("\n"))
        body_text = None
        if page.body.marked:
            # Checked before posting, with a long stand-in id, so the index rarely refuses after.
            page.parts[name] = part
            part.comment_id = 10 ** 12
            self.finalize(page, page.body, over)
            self.check_copy("body", page.body.live, None)
            part.comment_id = None
        text = self.finalize(page, part, over)
        # sw.post prepends this same post marker line; the read-back matches only while the two agree.
        posted = sw.post(self.github, self.number, "post", None, text.split("\n", 1)[1])
        cid = int(posted["id"])
        part.comment_id = cid
        page.parts[name] = part
        self.writes.append({"part": name, "url": page.link(cid)})
        back = self.fetch(name, cid)
        if back != text:
            raise PageError(f"the new {name} part read back differently from what was posted; "
                            "no copy saved", part=name, written=self.writes)
        self.save_copy(name, text, cid)
        if page.body.marked:
            body_text = self.finalize(page, page.body, over)
            self.write(page, "body", None, body_text, page.body.live)
        return self.result(created=name, comment_id=cid, link=page.link(cid))

    def load_entries(self, name: str, items: list, over: str | None) -> dict:
        page = self.load_for_write()
        part = page.part(name)
        if part.entries:
            raise PageError(f"part {name} already holds entries; load fills only an empty part")
        part.entries = self.entries_from(page, name, items)
        self.commit(page, [name], over)
        return self.result(loaded=name, ids=[e.id for e in part.entries])

    def entries_from(self, page: Page, name: str, items) -> list[Entry]:
        """Every entry of a JSON list, checked whole before anything is written."""
        if not isinstance(items, list):
            raise PageError("the entries file holds a JSON list of {kind, issue, text}")
        taken: set[str] = set()
        entries = []
        for number, item in enumerate(items, 1):
            if not isinstance(item, dict) or set(item) != {"kind", "issue", "text"}:
                raise PageError(f"entry {number} is not exactly {{kind, issue, text}}")
            wrong = [key for key in ("kind", "issue", "text") if not isinstance(item[key], str)]
            if wrong:
                raise PageError(f"entry {number}: {', '.join(wrong)} must be text")
            kind = item["kind"]
            if KIND_PART.get(kind) != name:
                raise PageError(f"entry {number}: kind {kind!r} does not belong in the {name} part")
            text = clean(item["text"], f"entry {number}")
            entry = build_entry(page.new_id(taken), kind, check_ref(item["issue"], self.names), text)
            taken.add(entry.id)
            entries.append(entry)
        return entries

    def write_body(self, text: str, archive: int, rulings, over: str | None) -> dict:
        page = self.load_for_write()
        if page.body.marked:
            raise PageError("the body already carries the page marker; change its preamble "
                            "with preamble body")
        entries = self.entries_from(page, "body", rulings)
        if not any(sw.first_line(c.get("body")) == MOVE_MARKER for c in self.archive_comments(archive)):
            raise PageError(f"archive issue {archive} holds no move comment yet; run archive --move "
                            "first, so the old page is archived before the body is overwritten")
        live = page.body.live
        part = Part("body", None, live)
        part.archive = archive
        part.preamble = strip_blank(text.split("\n"))
        # One write carries the rulings with the marker, so the old page is never half replaced.
        part.entries = entries
        page.body = part
        self.commit(page, ["body"], over)
        return self.result(body=page.link(), archive=archive, ids=[e.id for e in entries])

    def init_archive(self, title: str) -> dict:
        page = self.load()
        if page.body.marked and page.body.archive:
            raise PageError(f"the page already names archive issue {page.body.archive}")
        recorded = sw.read_json(self.archive_record(), {}).get("archive")
        found = sorted(set(self.archives_for_page()) | ({int(recorded)} if recorded else set()))
        if found:
            raise PageError(f"archive issue {found[0]} already exists for page {self.number}; "
                            f"name it with body --archive {found[0]}", archives=found)
        made = self.github.send("POST", f"repos/{sw.LAB_REPO}/issues", {
            "title": one_line(title, "--title"),
            "body": "\n".join([ARCHIVE_ISSUE_MARKER, ARCHIVE_PAGE_LINE.format(page=self.number),
                               ARCHIVE_ISSUE_PROSE]) + "\n"})
        number = int(made["number"])
        # GitHub's issue listing lags a new issue, so a quick re-run relies on this record instead.
        sw.write_json_atomic(self.archive_record(), {"schema_version": 1, "page": self.number,
                                                     "archive": number})
        self.writes.append({"part": "archive", "url": made.get("html_url")})
        # Closed at once so it never sits among open work; completed, as a record and not a declined plan.
        self.github.send("PATCH", f"repos/{sw.LAB_REPO}/issues/{number}",
                         {"state": "closed", "state_reason": "completed"})
        return self.result(archive=number)

    def archive_record(self) -> Path:
        return self.state_dir / f"page-{self.number}" / "archive.json"

    def archives_for_page(self) -> list[int]:
        issues = self.github.get_all(f"repos/{sw.LAB_REPO}/issues?state=all&creator={sw.OWNER_LOGIN}"
                                     "&per_page=100")
        return sorted(int(i["number"]) for i in issues if self.is_archive_body(i.get("body")))

    def is_archive_body(self, body: str | None) -> bool:
        lines = normalise(body).split("\n")
        return (len(lines) > 1 and lines[0].rstrip() == ARCHIVE_ISSUE_MARKER
                and lines[1].rstrip() == ARCHIVE_PAGE_LINE.format(page=self.number))

    # -- the archive

    def check_archive_issue(self, number: int) -> None:
        issue = self.github.get(f"repos/{sw.LAB_REPO}/issues/{number}")
        if not self.is_archive_body(issue.get("body")):
            raise PageError(f"issue {number} is not page {self.number}'s archive: it does not open "
                            f"with {ARCHIVE_ISSUE_MARKER} and its page line")

    def archive_comments(self, number: int) -> list[dict]:
        self.check_archive_issue(number)
        # The repository is public, so anyone else could post a comment forging a read's archive.
        return [c for c in self.github.comments(sw.LAB_REPO, number)
                if (c.get("user") or {}).get("login") == sw.OWNER_LOGIN]

    def post_archive(self, number: int, existing: dict | None, body: str) -> dict:
        if size(body) > ARCHIVE_CAP:
            raise PageError(f"the archive comment would be {size(body):,} bytes, over GitHub's "
                            f"{ARCHIVE_CAP:,} cap; nothing written")
        if existing is None:
            made = self.github.send("POST", f"repos/{sw.LAB_REPO}/issues/{number}/comments",
                                    {"body": body})
            cid = int(made["id"])
        else:
            cid = int(existing["id"])
            self.github.send("PATCH", f"repos/{sw.LAB_REPO}/issues/comments/{cid}", {"body": body})
        url = f"https://github.com/{sw.LAB_REPO}/issues/{number}#issuecomment-{cid}"
        self.writes.append({"part": "archive", "url": url})
        back = normalise(self.github.get(f"repos/{sw.LAB_REPO}/issues/comments/{cid}").get("body"))
        return {"id": cid, "url": url, "body": back}

    def recheck_read_comment(self, number: int, read: int, mark: str, existing: list[dict],
                             current: str | None) -> None:
        # Another run may have rewritten read N's comment since this one read it, and appending to
        # the text this run read would drop that run's entries from the archive.
        if existing:
            live = normalise(self.github.get(
                f"repos/{sw.LAB_REPO}/issues/comments/{existing[0]['id']}").get("body"))
        else:
            now = [c for c in self.archive_comments(number) if sw.first_line(c.get("body")) == mark]
            live = normalise(now[0]["body"]) if now else None
        if live != current:
            raise PageError(f"read {read}'s archive comment changed after this command read it, so "
                            "nothing was written; run the command again",
                            diff=unified(current or "", live or "", f"read {read} (as read)",
                                         f"read {read} (live)"))

    def archive_move(self, number: int, text: str) -> dict:
        comments = self.archive_comments(number)
        found = [c for c in comments if ARCHIVE_MARKER.fullmatch(sw.first_line(c.get("body")))
                 and "event=move" in sw.first_line(c.get("body"))]
        if found:
            raise PageError(f"the archive already holds the move's comment {found[0]['id']}")
        body = (f"<!-- lab:steward-archive:v1 event=move -->\n## The move, "
                f"{self.now.strftime('%Y-%m-%d')}\n\n{text.strip(chr(10))}\n")
        posted = self.post_archive(number, None, body)
        if text.strip("\n") not in posted["body"]:
            raise PageError("the move's archive comment read back without the whole file",
                            written=self.writes)
        return self.result(archived="move", comment=posted["url"])

    def archive_read(self, read: int, closed: bool, ids: list[str], over: str | None) -> dict:
        if not closed and not ids:
            raise PageError("archive --read takes --closed, --ids or both")
        page = self.load_for_write()
        number = page.part("body").archive
        if not number:
            raise PageError("the body names no archive issue")
        comments = self.archive_comments(number)
        refs = [e.issue for part in page.all_parts() for e in part.entries]
        states, errors = resolve_states(self.github, refs)
        if errors:
            raise PageError("some issues could not be resolved; nothing written",
                            unresolved=[{"issue": k, "error": v} for k, v in sorted(errors.items())])
        lists = closed_lists(page, states)
        if lists["closed_without_landing"]:
            raise PageError("a ruling's carrying change closed without landing; re-point each "
                            "with replace --issue, or keep it with its reason, then re-run. "
                            "Nothing written", closed_without_landing=lists["closed_without_landing"])
        mark = f"<!-- lab:steward-archive:v1 read={read} -->"
        existing = [c for c in comments if sw.first_line(c.get("body")) == mark]
        if len(existing) > 1:
            raise PageError(f"the archive holds {len(existing)} comments for read {read}")
        current = normalise(existing[0]["body"]) if existing else None
        held = archived_entries(current) if current is not None else []
        held_ids = {ENTRY_MARKER.search(text).group("id") for text in held}
        on_page = page.ids()
        chosen: list[str] = []
        if closed:
            chosen += [row["id"] for row in lists["closed"]]
        for eid in ids:
            if eid not in on_page:
                # A re-run after a stopped archive names entries already gone from the page.
                if eid in held_ids:
                    continue
                raise PageError(f"no entry {eid} on the page or in read {read}'s archive comment")
            if eid not in chosen:
                chosen.append(eid)
        if not chosen:
            return self.result(archived=[], read=read)
        removed: list[tuple[str, Entry]] = []
        for part in page.all_parts():
            keep = [e for e in part.entries if e.id not in chosen]
            removed += [(part.name, e) for e in part.entries if e.id in chosen]
            part.entries = keep
        affected = [n for n in PART_ORDER if any(name == n for name, _ in removed)]
        prepared = []
        for name in affected:
            part = page.part(name)
            text = self.finalize(page, part, over)
            self.check_copy(name, part.live, part.comment_id)
            prepared.append((name, part.comment_id, text, part.live))
        fresh = [(n, e) for n, e in removed if e.text not in held]
        groups = []
        for name in PART_ORDER:
            group = [e.text for n, e in fresh if n == name]
            if group:
                groups.append(f"### {TITLES[name]}\n\n" + "\n".join(group))
        if current is None:
            body = (f"{mark}\n## Read {read}, archived {self.now.strftime('%Y-%m-%d')}\n\n"
                    + "\n\n".join(groups) + "\n")
        else:
            body = current.rstrip("\n") + ("\n\n" + "\n\n".join(groups) if groups else "") + "\n"
        if current is None or groups:
            self.recheck_read_comment(number, read, mark, existing, current)
            posted = self.post_archive(number, existing[0] if existing else None, body)
            back, url = posted["body"], posted["url"]
        else:
            cid = existing[0]["id"]
            back = normalise(self.github.get(f"repos/{sw.LAB_REPO}/issues/comments/{cid}")
                             .get("body"))
            url = f"https://github.com/{sw.LAB_REPO}/issues/{number}#issuecomment-{cid}"
        back_entries = archived_entries(back)
        missing = [e.id for _, e in removed if e.text not in back_entries]
        if missing:
            raise PageError("the archive comment read back without some entries, so nothing was "
                            "removed from the page", missing=missing, written=self.writes)
        for name, comment_id, text, loaded in prepared:
            try:
                self.write(page, name, comment_id, text, loaded)
            except PageError as exc:
                exc.detail.setdefault("written", self.writes)
                exc.detail["stopped_at"] = name
                raise
        return self.result(archived=[e.id for _, e in removed], read=read, comment=url)


# ---------------------------------------------------------------- command line


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Edit the Steward's standing page entry by entry.")
    sub = parser.add_subparsers(dest="command", required=True)

    def command(name: str, help_text: str, writes: bool = True) -> argparse.ArgumentParser:
        one = sub.add_parser(name, help=help_text, description=help_text)
        one.add_argument("--state-dir", help="local state directory (default: the "
                         f"{sw.STATE_ENV} variable, else ~/.tradecraft-lab/steward)")
        one.add_argument("--page", type=int, default=sw.STANDING_PAGE,
                         help=f"standing page issue number; anything but {sw.STANDING_PAGE} is "
                         "probe-only")
        if writes:
            one.add_argument("--over-reason", help="write the part over its limit, showing this "
                             "reason; `same` restates the reason it already shows")
        return one

    command("status", "report every part, its size, copy and faults, and the closed lists",
            writes=False)
    one = command("show", "print one live part, its SHA-256 and its entries", writes=False)
    one.add_argument("part", choices=PART_ORDER)
    one = command("accept", "record the live part as the saved copy", writes=False)
    one.add_argument("part", choices=PART_ORDER)
    one.add_argument("--sha", required=True)
    one = command("add", "add one entry to its kind's part")
    one.add_argument("--kind", choices=tuple(KIND_PART), required=True)
    one.add_argument("--issue", required=True, help="REPO#N in a lab repository, or none")
    one.add_argument("--text-file", required=True)
    where = one.add_mutually_exclusive_group()
    where.add_argument("--position", type=int)
    where.add_argument("--after")
    one = command("replace", "replace an entry's text or issue")
    one.add_argument("id")
    one.add_argument("--text-file")
    one.add_argument("--issue")
    one.add_argument("--clear-kept", action="store_true")
    one = command("move", "reorder an entry, or move it to another kind's part")
    one.add_argument("id")
    where = one.add_mutually_exclusive_group()
    where.add_argument("--position", type=int)
    where.add_argument("--after")
    one.add_argument("--kind", choices=tuple(KIND_PART))
    one.add_argument("--text-file")
    one = command("keep", "keep an entry after its issue closed, showing why")
    one.add_argument("id")
    one.add_argument("--reason", required=True)
    one = command("preamble", "replace a part's preamble")
    one.add_argument("part", choices=PART_ORDER)
    one.add_argument("--text-file", required=True)
    one = command("create-part", "post a new part comment")
    one.add_argument("part", choices=COMMENT_PARTS)
    one.add_argument("--text-file", required=True)
    one = command("load", "fill an empty part from a JSON list of {kind, issue, text}")
    one.add_argument("part", choices=PART_ORDER)
    one.add_argument("--file", required=True)
    one = command("body", "write the body's preamble, page marker, index and rulings (the move only)")
    one.add_argument("--text-file", required=True)
    one.add_argument("--archive", type=int, required=True)
    one.add_argument("--rulings", required=True, help="JSON list of {kind, issue, text} rulings")
    one = command("init-archive", "create and close the archive issue", writes=False)
    one.add_argument("--title", required=True)
    one = command("archive", "post entries to the archive, then remove them from the page")
    mode = one.add_mutually_exclusive_group(required=True)
    mode.add_argument("--read", type=int)
    mode.add_argument("--move", action="store_true")
    one.add_argument("--closed", action="store_true")
    one.add_argument("--ids", nargs="+", default=[])
    one.add_argument("--file")
    one.add_argument("--archive", type=int)
    return parser


def run(args: argparse.Namespace, github: sw.GitHub | None = None,
        now: datetime | None = None) -> dict:
    state_dir = sw.resolve_state_dir(args.state_dir)
    sw.refuse_probe_against_default(state_dir, ["--page"] if args.page != sw.STANDING_PAGE else [])
    tool = PageTool(github or sw.GitHub(), args.page, state_dir, now or sw.now_utc())
    try:
        return dispatch(tool, args)
    except PageError as exc:
        # A refusal after a write must say what already reached GitHub, or the Steward can't tell.
        if tool.writes:
            exc.detail.setdefault("written", list(tool.writes))
        raise
    except sw.WatchError as exc:
        if tool.writes:
            raise PageError(str(exc), written=list(tool.writes)) from exc
        raise


def read_json_file(path: str):
    text = read_file(path, "entries file")
    try:
        return json.loads(text)
    except ValueError as exc:
        raise PageError(f"entries file {path} is not JSON: {exc}") from exc


def dispatch(tool: PageTool, args: argparse.Namespace) -> dict:
    over = getattr(args, "over_reason", None)
    command = args.command
    if command == "status":
        return tool.status()
    if command == "show":
        return tool.show(args.part)
    if command == "accept":
        return tool.accept(args.part, args.sha)
    if command == "add":
        return tool.add(args.kind, args.issue, read_file(args.text_file, "text file"),
                        args.position, args.after, over)
    if command == "replace":
        text = read_file(args.text_file, "text file") if args.text_file else None
        return tool.replace(args.id, text, args.issue, args.clear_kept, over)
    if command == "move":
        text = read_file(args.text_file, "text file") if args.text_file else None
        return tool.move(args.id, args.position, args.after, args.kind, text, over)
    if command == "keep":
        return tool.keep(args.id, args.reason, over)
    if command == "preamble":
        return tool.preamble(args.part, read_file(args.text_file, "text file"), over)
    if command == "create-part":
        return tool.create_part(args.part, read_file(args.text_file, "text file"), over)
    if command == "load":
        return tool.load_entries(args.part, read_json_file(args.file), over)
    if command == "body":
        return tool.write_body(read_file(args.text_file, "text file"), args.archive,
                               read_json_file(args.rulings), over)
    if command == "init-archive":
        return tool.init_archive(args.title)
    if command == "archive":
        if args.move:
            if args.closed or args.ids or not args.file or not args.archive:
                raise PageError("archive --move takes --archive N and --file F, and no "
                                "--closed or --ids")
            # The move's file holds the old page word for word, so it may quote this tool's markers.
            return tool.archive_move(args.archive, read_file(args.file, "move file", markers_ok=True))
        if args.file:
            raise PageError("--file applies to archive --move")
        if args.archive:
            raise PageError("--archive applies to archive --move; archive --read uses the archive "
                            "issue the body names")
        return tool.archive_read(args.read, args.closed, args.ids, over)
    raise PageError(f"unknown command {command}")


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        value = run(args)
    except PageError as exc:
        sw.emit({"schema_version": 1, "error": str(exc), **exc.detail})
        return 2
    except sw.WatchError as exc:
        sw.emit({"schema_version": 1, "error": str(exc)})
        return 2
    sw.emit(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
