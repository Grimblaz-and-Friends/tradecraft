"""Build the cold reader's isolated reading of a change, check its account, and judge currency.

Design: lib/DESIGN.md#the-cold-reader
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import tempfile

import recipient_tree

# Version 2 records a reading's mode and the lines it judged, so an entrance older than that refuses one
# rather than misreading it as a whole-file reading. A version 1 record still loads and is read as written.
SCHEMA_VERSION = 2
SCHEMA_VERSIONS = (1, 2)
FLAG_KINDS = (
    "cannot-tell", "missing-reason", "what-comment", "changeable-number", "history",
    "dead-end-pointer", "in-force-missing",
)
# The standard's two gaps in a document a change's code points to: the only flags a first reading may
# place on a document the change never touched.
DOCUMENT_GAPS = ("in-force-missing", "dead-end-pointer")
MODES = ("first", "fix-check", "why-check")
HEADINGS = ("## Sections", "## Flags", "## Why this change was made", "## Worth a look")
EARLIER_HEADING = "## Earlier flags"
# A reread judges only the fixes, so it describes and nominates nothing.
MODE_HEADINGS = {
    "first": HEADINGS,
    "fix-check": (EARLIER_HEADING, "## Flags"),
    "why-check": (EARLIER_HEADING, "## Flags", "## Why this change was made"),
}
MAX_NOMINATIONS = 5
# Above this the diff travels as a file, so the prompt stays readable.
INLINE_DIFF_CHARACTERS = 60_000
DIFF_FILE = "CHANGE.diff"
EXCERPTS_FILE = "CHANGE.excerpts"
GENERATED = (DIFF_FILE, EXCERPTS_FILE)
# Unmarked lines shown either side of each run of a reread's marked lines.
EXCERPT_CONTEXT = 3
# A deleted or binary file has no lines to number, so the whole of it is the change's.
WHOLE = "whole"
# Any token naming a Markdown section counts, since a pointer may open a comment, docstring or document.
POINTER = re.compile(r"(?<![\w./-])((?:[\w.-]+/)*[\w.-]+\.md)#([A-Za-z0-9_-]+)")
LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
# A full `[text][id]` or collapsed `[text][]` reference, then a shortcut `[id]` that opens no other form.
FULL_REFERENCE = re.compile(r"\[([^\]]*)\]\[([^\]]*)\]")
SHORTCUT_REFERENCE = re.compile(r"(?<!\])\[([^\]]+)\](?![\[(:])")
DEFINITION = re.compile(r"^ {0,3}\[([^\]]+)\]:[ \t]*<?([^\s>]+)>?")
HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
FENCE = re.compile(r"^\s*(```|~~~)")
# Built at run time: string constants stay ASCII, since a platform encoding can garble captured output.
EM_DASH, EN_DASH = chr(0x2014), chr(0x2013)
# A reader names one finding at several places as a comma list; the gate holds a flag by its file, so a
# list owes nothing more.
LINE_ITEM = r"[0-9]+(?:[-" + EN_DASH + r"][0-9]+)?"
LINES = LINE_ITEM + r"(?:,[ \t]*" + LINE_ITEM + r")*"
# Lenient on dashes, bullets and backticks, so a reader's stray formatting doesn't refuse a whole account.
FLAG_LINE = re.compile(
    r"^(?:[-*][ \t]+)?`?(?P<path>[^\s:`]+)(?::(?P<lines>" + LINES + r"))?`?"
    r"[ \t]+[" + EM_DASH + r"-][ \t]+(?P<kind>" + "|".join(FLAG_KINDS) + r")[ \t]+["
    + EM_DASH + r"-][ \t]+(?P<text>\S.*)$"
)
NO_FLAGS = re.compile(r"^(?:[-*][ \t]+)?`?none\.?`?\.?$", re.IGNORECASE)
CAN_TELL = re.compile(r"^Can tell: (yes|no)$")
REVIEW_HEADING = "Holder's review against the brief"
# A mistyped acceptance must fail the `open`, so it never silently accepts nothing.
ACCEPTANCE = re.compile(
    r"^(?:[-*][ \t]+)?Accepted:[ \t]+`?(?P<path>[^\s:`]+)(?::(?P<lines>" + LINES + r"))?`?[ \t]+[" + EM_DASH + r"-][ \t]+(?P<kind>" + "|".join(FLAG_KINDS) + r")[ \t]+["
    + EM_DASH + r"-][ \t]+(?P<rest>\S.*)$"
)
ACCEPTANCE_START = re.compile(r"^(?:[-*][ \t]+)?Accepted:")
SEPARATOR = re.compile(r"^[ \t]+[" + EM_DASH + r"-][ \t]+(?=\S)")
# A reread's verdict on one earlier flag, lenient on dashes and formatting as a flag line is.
VERDICT_LINE = re.compile(
    r"^(?:[-*][ \t]+)?`?(?P<id>F[0-9]+)`?[.:]?[ \t]+[" + EM_DASH + r"-][ \t]+`?(?P<verdict>not-answered|answered)`?"
    r"(?:[ \t]+[" + EM_DASH + r"-][ \t]+(?P<why>\S.*))?$"
)
HUNK = re.compile(rb"^@@ -([0-9]+)(?:,([0-9]+))? \+([0-9]+)(?:,([0-9]+))? @@")
# A file diff's two sides, `--- a/old` and `+++ b/new`, printed before its first hunk.
SIDE_LINE = re.compile(rb"^(-|\+)(?:--|\+\+) (.*)$")


class ColdReaderError(RuntimeError):
    """The reading cannot be built or judged from committed bytes."""


def _git(root: Path, *arguments: str, input_bytes: bytes | None = None) -> bytes:
    try:
        return recipient_tree._git(root, *arguments, input_bytes=input_bytes)
    except recipient_tree.RecipientTreeError as exc:
        raise ColdReaderError(str(exc)) from exc


def _tree_map(root: Path, revision: str) -> dict[str, str]:
    found = {}
    for entry in _git(root, "ls-tree", "-r", "-z", revision).split(b"\0"):
        header, separator, name = entry.partition(b"\t")
        fields = header.split()
        if separator and len(fields) == 3 and fields[1] == b"blob":
            found[name.decode("utf-8")] = fields[2].decode("ascii")
    return found


def _blob_text(root: Path, oid: str) -> str | None:
    try:
        return _git(root, "cat-file", "blob", oid).decode("utf-8")
    except UnicodeDecodeError:
        return None  # A binary file carries no pointer.


def _name_status(root: Path, base: str, head: str) -> list[tuple[str, str, str | None]]:
    """Each changed entry's status, its path at head, and its old path when renamed or copied."""
    raw = _git(root, "diff", "--name-status", "-z", "-M", base, head).split(b"\0")
    entries = []
    index = 0
    while index < len(raw) and raw[index]:
        status = raw[index].decode("ascii")
        # A rename or copy names its old path first; the change is read at its new one.
        count = 2 if status[:1] in {"R", "C"} else 1
        old = raw[index + 1].decode("utf-8") if count == 2 else None
        entries.append((status, raw[index + count].decode("utf-8"), old))
        index += count + 1
    return entries


def change_set(root: Path, base_tip: str, head: str) -> tuple[str, dict[str, str]]:
    """Return the merge base and each changed path's blob at head, or `deleted`."""
    base = _git(root, "merge-base", base_tip, head).decode("ascii").strip()
    tree = _tree_map(root, head)
    paths = {path: "deleted" if status.startswith("D") else tree.get(path, "deleted")
             for status, path, _ in _name_status(root, base, head)}
    return base, dict(sorted(paths.items()))


def renames(root: Path, base: str, head: str) -> dict[str, str]:
    """Map each path renamed by the change to its path at the base."""
    return {path: old for status, path, old in _name_status(root, base, head)
            if status.startswith("R") and old is not None}


# Design: lib/DESIGN.md#the-cold-reader (the change's lines through `gained`)

def _unquote(raw: bytes) -> str:
    """A path as Git prints it, C-quoted when it holds a character Git won't print bare."""
    if not (len(raw) >= 2 and raw.startswith(b'"') and raw.endswith(b'"')):
        return raw.decode("utf-8", errors="replace")
    escapes = {b"n": 10, b"t": 9, b'"': 34, b"\\": 92, b"a": 7, b"b": 8, b"f": 12, b"r": 13, b"v": 11}
    body, out, index = raw[1:-1], bytearray(), 0
    while index < len(body):
        if body[index:index + 1] == b"\\" and index + 1 < len(body):
            following = body[index + 1:index + 2]
            if following in escapes:
                out.append(escapes[following])
                index += 2
                continue
            if following.isdigit():
                out.append(int(body[index + 1:index + 4], 8))
                index += 4
                continue
        out += body[index:index + 1]
        index += 1
    return out.decode("utf-8", errors="replace")


def _side(raw: bytes, prefix: bytes) -> str | None:
    # Git adds a tab after a name holding a space, for patch tools.
    raw = raw.rstrip(b"\n").rstrip(b"\r").removesuffix(b"\t")
    if raw == b"/dev/null":
        return None
    name = _unquote(raw)
    return name[len(prefix):] if name.startswith(prefix.decode("ascii")) else name


def file_diffs(root: Path, old: str, new: str) -> dict[str, dict]:
    """Each file the line-level diff from `old` to `new` touches, by its path at `new` (or at `old` when deleted).

    Each holds its path at `old` (None when added), its hunks as (old start, old count, new start, new
    count), and whether Git shows it as binary. Taken with no context, renames followed, and the machine's
    diff settings named off as `reading_diff` names them, so the same lines count wherever it runs.
    """
    raw = _git(root, "-c", "core.quotePath=false", "diff", "--no-color", "--no-ext-diff", "--unified=0",
               "--inter-hunk-context=0", "--src-prefix=a/", "--dst-prefix=b/", "-M", old, new)
    found: dict[str, dict] = {}
    current: dict | None = None

    def close() -> None:
        if current is not None:
            key = current["path"] if current["path"] is not None else current["old"]
            if key is not None:
                found[key] = current

    in_hunks = False
    for line in raw.split(b"\n"):
        if line.startswith(b"diff --git "):
            close()
            current, in_hunks = {"path": None, "old": None, "hunks": [], "binary": False, "named": False}, False
            continue
        if current is None:
            continue
        hunk = HUNK.match(line)
        if hunk:
            in_hunks = True
            old_start, old_count, new_start, new_count = hunk.groups()
            current["hunks"].append((int(old_start), 1 if old_count is None else int(old_count),
                                     int(new_start), 1 if new_count is None else int(new_count)))
        elif in_hunks:
            continue
        elif (side := SIDE_LINE.match(line)) is not None:
            sign, name = side.groups()
            if sign == b"-":
                current["old"], current["named"] = _side(name, b"a/"), True
            else:
                current["path"] = _side(name, b"b/")
        elif line.startswith(b"rename from ") and not current["named"]:
            current["old"] = _side(line[len(b"rename from "):], b"")
        elif line.startswith(b"rename to ") and not current["named"]:
            current["path"] = _side(line[len(b"rename to "):], b"")
        elif line.startswith(b"Binary files "):
            current["binary"] = True
            # Binary files name no `---` or `+++` side, so their paths come from Git's one summary line.
            names = line[len(b"Binary files "):].removesuffix(b" differ").split(b" and ", 1)
            if len(names) == 2:
                current["old"] = current["old"] or _side(names[0], b"a/")
                current["path"] = current["path"] or _side(names[1], b"b/")
    close()
    return found


def _count(text: str) -> int:
    return text.count("\n") + (1 if text and not text.endswith("\n") else 0)


def _ranges(numbers) -> list[list[int]]:
    found: list[list[int]] = []
    for number in sorted(set(numbers)):
        if found and number == found[-1][1] + 1:
            found[-1][1] = number
        else:
            found.append([number, number])
    return found


def numbers_of(ranges) -> set[int]:
    """The line numbers a sealed set names; `WHOLE` names no number, so callers test it first."""
    if ranges == WHOLE:
        return set()
    return {number for start, end in ranges for number in range(start, end + 1)}


def flag_numbers(lines: str | None) -> set[int]:
    """The line numbers a flag's location names, from its one line, range or comma list."""
    found: set[int] = set()
    for item in re.split(r",", (lines or "").replace(EN_DASH, "-")):
        item = item.strip()
        if not item:
            continue
        start, _dash, end = item.partition("-")
        first, last = int(start), int(end or start)
        found.update(range(min(first, last), max(first, last) + 1))
    return found


def change_lines(root: Path, base: str, head: str) -> dict[str, object]:
    """The change's lines in each changed file at head: sorted ranges, or `WHOLE` for a deleted or binary file.

    A line counts when the diff from the merge base adds it; where a hunk removes lines and adds none,
    the line just before the removal and the line just after it count, or whichever of them exists.
    A line the diff would show only as context never counts.
    """
    found: dict[str, object] = {}
    for path, entry in file_diffs(root, base, head).items():
        if entry["path"] is None or entry["binary"]:
            found[path] = WHOLE
            continue
        numbers: set[int] = set()
        removals = []
        for _old_start, _old_count, new_start, new_count in entry["hunks"]:
            if new_count:
                numbers.update(range(new_start, new_start + new_count))
            else:
                removals.append(new_start)
        if removals:
            # The line after a removal at the file's end doesn't exist, so the file's length is read.
            length = _count(_git(root, "cat-file", "blob", f"{head}:{path}").decode("utf-8", errors="replace"))
            for before in removals:
                numbers.update(number for number in (before, before + 1) if 1 <= number <= length)
        found[path] = _ranges(numbers)
    return found


def _mapped(hunks: list[tuple[int, int, int, int]], number: int) -> int | None:
    """The line at the earlier head that a line at the later head stands unchanged from, or None."""
    shift = 0
    for old_start, old_count, new_start, new_count in hunks:
        if new_count and new_start <= number < new_start + new_count:
            return None
        # A hunk wholly before the line shifts it; a removal at `+n,0` sits after line n.
        if (new_start + new_count if new_count else new_start + 1) <= number:
            shift += old_count - new_count
    return number + shift


def gained(present: object, earlier: object, entry: dict | None, *, same_blob: bool) -> object:
    """The change's lines at the present head that a reading of the file at an earlier head didn't read.

    `present` and `earlier` are the change's lines at the two heads; `entry` is the file's diff
    between them, or None where it didn't change. A present line was read when it stands unchanged
    from the earlier head and was one of the change's lines there, so a line edited since is gained,
    and so is one that has become the change's without being edited.
    """
    if present == WHOLE:
        return [] if earlier == WHOLE and same_blob else WHOLE
    if entry is not None and entry["binary"]:
        return present
    earlier_numbers = numbers_of(earlier) if earlier != WHOLE else set()
    hunks = entry["hunks"] if entry is not None else []
    read = set()
    for number in numbers_of(present):
        before = _mapped(hunks, number)
        if before is not None and before in earlier_numbers:
            read.add(number)
    return _ranges(numbers_of(present) - read)


def github_anchor(heading: str) -> str:
    # Pointers are written against the anchors the document's renderer gives its headings.
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def section(text: str, anchor: str) -> str | None:
    """Return the anchored section, from its heading to the next heading as high or higher."""
    lines = text.splitlines()
    start = level = None
    fenced = False
    used: dict[str, int] = {}
    for number, line in enumerate(lines):
        if FENCE.match(line):
            fenced = not fenced
            continue
        match = None if fenced else HEADING.match(line)
        if match is None:
            continue
        depth = len(match.group(1))
        # The renderer numbers a repeated heading's anchor, so the second `Notes` is `notes-1`.
        slug = github_anchor(match.group(2))
        repeat = used.get(slug, 0)
        used[slug] = repeat + 1
        if start is None and (slug if not repeat else f"{slug}-{repeat}") == anchor:
            start, level = number, depth
        elif start is not None and depth <= level:
            return "\n".join(lines[start:number])
    return None if start is None else "\n".join(lines[start:])


def _resolve(document: str, target: str) -> str:
    """A link target's repository path, read relative to the document unless it opens with `/`."""
    relative = target.split("#", 1)[0]
    if relative.startswith("/"):
        return posixpath.normpath(relative.lstrip("/"))
    return posixpath.normpath(posixpath.join(posixpath.dirname(document), relative))


def _definitions(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    fenced = False
    for line in text.splitlines():
        if FENCE.match(line):
            fenced = not fenced
            continue
        match = None if fenced else DEFINITION.match(line)
        if match:
            # The first definition of a label wins, as it does when the document renders.
            found.setdefault(_label(match.group(1)), match.group(2))
    return found


def _label(text: str) -> str:
    return " ".join(text.split()).lower()


def _section_records(document: str, text: str, anchor: str, tree: dict[str, str]) -> list[dict]:
    body = section(text, anchor)
    if body is None:
        return []
    definitions = _definitions(text)
    targets = LINK.findall(body)
    for match in FULL_REFERENCE.finditer(body):
        targets.append(definitions.get(_label(match.group(2) or match.group(1)), ""))
    targets.extend(definitions.get(_label(label), "") for label in SHORTCUT_REFERENCE.findall(body))
    records, seen = [], set()
    for target in targets:
        if not target or "://" in target or target.startswith(("mailto:", "#")):
            continue
        resolved = _resolve(document, target)
        if resolved in tree and resolved not in seen:
            seen.add(resolved)
            records.append({"path": resolved, "blob": tree[resolved]})
    return records


def _pointer_target(path: str, target: str, tree: dict[str, str]) -> str:
    # A pointer is usually written from the repository root, but one opening with `./` or `../`, or
    # found only beside its file, is read relative to the file the way a section's links are.
    rooted, beside = posixpath.normpath(target), _resolve(path, target)
    first, second = (beside, rooted) if target.startswith(("./", "../")) else (rooted, beside)
    return first if first in tree or second not in tree else second


def dependencies(root: Path, tree: dict[str, str], path: str) -> list[dict]:
    """Follow a changed file's pointers, and every relative link inside each pointed section, only."""
    oid = tree.get(path)
    text = _blob_text(root, oid) if oid else None
    if text is None:
        return []
    found, seen = [], set()
    for target, anchor in POINTER.findall(text):
        token = f"{target}#{anchor}"
        if token in seen:
            continue
        seen.add(token)
        target = _pointer_target(path, target, tree)
        if target not in tree:
            found.append({"pointer": token, "path": target, "blob": "absent", "records": []})
            continue
        document = _blob_text(root, tree[target]) or ""
        found.append({"pointer": token, "path": target, "blob": tree[target],
                      "records": _section_records(target, document, anchor, tree)})
    return found


def coverage_entry(root: Path, tree: dict[str, str], path: str, blob: str) -> dict:
    return {"blob": blob,
            "dependencies": [] if blob == "deleted" else dependencies(root, tree, path)}


def dependency_paths(entry: dict) -> set[str]:
    paths = set()
    for dependency in entry.get("dependencies", []):
        paths.add(dependency["path"])
        paths.update(record["path"] for record in dependency.get("records", []))
    return paths


def current(root: Path, base_tip: str, head: str) -> dict:
    """The change set at head with every path's dependencies re-resolved there."""
    base, changed = change_set(root, base_tip, head)
    tree = _tree_map(root, head)
    return {"base": base, "head": head, "change_set": changed,
            "coverage": {path: coverage_entry(root, tree, path, blob) for path, blob in changed.items()}}


def _digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode("ascii")).hexdigest()


def reading_diff(source: Path, base: str, head: str, selected: list[str]) -> bytes:
    """The diff a reading carries for its covered paths, regenerated the same way wherever it is needed."""
    # A rename's old path joins the pathspec so the diff shows the edit as a rename, removed lines and all.
    moved = renames(source, base, head)
    pathspec = sorted(set(selected) | {moved[path] for path in selected if path in moved})
    # Git's default context, named so a machine's diff settings can't change what the reader is given.
    return _git(source, "diff", "--no-color", "--no-ext-diff", "--unified=3", "--inter-hunk-context=0",
                "-M", base, head, "--", *pathspec)


def _blob_texts(root: Path, oids: list[str]) -> dict[str, str]:
    """Each blob's text, read in one Git call.

    Bytes that aren't UTF-8 are replaced rather than refused, so a text file in another encoding still
    numbers its lines; Git's own diff decides which files are binary and judged whole.
    """
    wanted = sorted(set(oids))
    if not wanted:
        return {}
    raw = _git(root, "cat-file", "--batch", input_bytes=("\n".join(wanted) + "\n").encode("ascii"))
    found: dict[str, str] = {}
    index = 0
    while index < len(raw):
        header_end = raw.index(b"\n", index)
        fields = raw[index:header_end].split()
        if len(fields) != 3:
            raise ColdReaderError("git cat-file returned an unreadable header: "
                                  + raw[index:header_end].decode("ascii", errors="replace"))
        size = int(fields[2])
        found[fields[0].decode("ascii")] = raw[header_end + 1:header_end + 1 + size].decode("utf-8", errors="replace")
        index = header_end + 1 + size + 1
    return found


def _clip(ranges: object, count: int) -> object:
    if ranges == WHOLE:
        return WHOLE
    return _ranges(number for number in numbers_of(ranges) if 1 <= number <= count)


def _fence(text: str) -> str:
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def excerpts(texts: dict[str, str | None], lines: dict[str, dict], change_set: dict[str, str]) -> str:
    """A reread's lines to judge: each covered file's judged lines marked and numbered, with a little context.

    Composed from the sealed record and the files at the reading's head alone, so the marked lines are
    exactly the judged ones and the same text is composed wherever the reading is rebuilt.
    """
    parts = []
    for path in sorted(lines):
        judged = lines[path]["judged"]
        if judged == WHOLE:
            why = ("The change deletes this file, so the deletion is judged whole."
                   if change_set.get(path) == "deleted" else "This file isn't text, so it is judged whole.")
            parts.append(f"### `{path}`\n\n{why}")
            continue
        marked = numbers_of(judged)
        if not marked:
            continue
        rows = (texts.get(path) or "").split("\n")
        if rows and rows[-1] == "":
            rows.pop()
        rows = [row.removesuffix("\r") for row in rows]
        width = len(str(len(rows)))
        windows: list[list[int]] = []
        for start, end in judged:
            low, high = max(1, start - EXCERPT_CONTEXT), min(len(rows), end + EXCERPT_CONTEXT)
            if windows and low <= windows[-1][1] + 1:
                windows[-1][1] = max(windows[-1][1], high)
            else:
                windows.append([low, high])
        blocks = []
        for low, high in windows:
            body = "\n".join(f"{'>' if number in marked else ' '} {number:>{width}} | {rows[number - 1]}"
                             for number in range(low, high + 1))
            fence = _fence(body)
            blocks.append(f"{fence}text\n{body}\n{fence}")
        parts.append(f"### `{path}`\n\n" + "\n\n".join(blocks))
    if not parts:
        return ("No line has been gained since the last reading, so no line is marked: judge only the "
                "earlier flags.\n")
    return "\n\n".join(parts) + "\n"


def reading_excerpts(source: Path, metadata: dict) -> str:
    """A reread's excerpts, composed from its sealed record and the files at its head in `source`."""
    lines = metadata.get("lines") or {}
    change_set = metadata["change_set"]
    texts = _blob_texts(source, [change_set[path] for path in lines if change_set.get(path) != "deleted"])
    return excerpts({path: texts.get(change_set[path]) for path in lines if change_set.get(path) != "deleted"},
                    lines, change_set)


def build_tree(*, source: Path, output: Path, work: str, producer_version: str,
               base_tip: str, head: str, covered: list[str] | None, branch: str,
               numbers: list[int], records_home: Path, order: dict | None = None) -> Path:
    """Write the reading tree, its record and diff kept in the entrance's records; refuse one naming the branch.

    `order` is what the gate ordered: its mode, its covered paths and, for a reread, the lines to judge,
    the head each covered path was last read at, and the earlier flags. Without one this is a first
    reading of `covered`, or of the whole change.
    """
    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    record = recipient_tree.record_path(output, records_home)
    # A reading's record is evidence the gate reads, so it is never replaced.
    if output.exists() or record.exists():
        raise ColdReaderError(f"refusing existing reading output: {output}")
    if recipient_tree._inside(output, source):
        raise ColdReaderError("reading output must be outside the source repository")
    try:
        recipient_tree.refuse_records_placement(output, records_home)
    except recipient_tree.RecipientTreeError as exc:
        raise ColdReaderError(str(exc)) from exc
    state = current(source, base_tip, head)
    changed = state["change_set"]
    if not changed:
        raise ColdReaderError("the change set is empty; there is nothing to read")
    order = order or {"mode": "first", "covered": sorted(changed if covered is None else covered)}
    mode = order["mode"]
    if mode not in MODES:
        raise ColdReaderError(f"unknown reading mode: {mode}")
    selected = sorted(order["covered"])
    unknown = [path for path in selected if path not in changed]
    if unknown:
        raise ColdReaderError("covered paths are not in the change set: " + ", ".join(unknown))
    coverage = {path: state["coverage"][path] for path in selected}
    # Every reading carries every changed file, so the reader can follow code across files.
    carried = {path for path, blob in changed.items() if blob != "deleted"}
    for entry in coverage.values():
        for dependency in entry["dependencies"]:
            if dependency["blob"] != "absent":
                carried.add(dependency["path"])
            carried.update(record["path"] for record in dependency["records"])
    # An empty selection would list, and archive, the whole tree.
    try:
        files = recipient_tree._tree_files(source, head, sorted(carried)) if carried else {}
    except recipient_tree.RecipientTreeError as exc:
        # A file the tree can't hold, such as a symlink, refuses the reading rather than escaping the stage.
        raise ColdReaderError(str(exc)) from exc
    # The lines are sealed so the reading's flags are placed from its record alone, whatever is pruned later.
    now = change_lines(source, state["base"], head)
    texts = _blob_texts(source, [changed[path] for path in selected if changed[path] != "deleted"])
    lines = {}
    for path in selected:
        count = 0 if changed[path] == "deleted" else _count(texts.get(changed[path]) or "")
        change = now.get(path, [])
        judged = change if mode == "first" else (order.get("judged") or {}).get(path, change)
        lines[path] = {"change": change, "judged": _clip(judged, count), "count": count}
    # A first reading and a why-check show the whole change's diff; a fix-check shows only its marked lines.
    diff = reading_diff(source, state["base"], head, selected) if mode != "fix-check" else None
    composed = None if mode == "first" else excerpts(
        {path: texts.get(changed[path]) for path in selected if changed[path] != "deleted"}, lines, changed)
    pieces = {DIFF_FILE: diff, EXCERPTS_FILE: None if composed is None else composed.encode("utf-8")}
    inline = {name: piece is not None and len(piece.decode("utf-8", errors="replace")) <= INLINE_DIFF_CHARACTERS
              for name, piece in pieces.items()}
    # With nothing else to carry, the material travels as files, since the neutral commit can't be empty.
    if not files:
        inline = {name: False for name in pieces}
    as_file = [name for name, piece in pieces.items() if piece is not None and not inline[name]]
    clash = [name for name in as_file if name in files]
    if clash:
        raise ColdReaderError(f"the change carries a root {clash[0]}, which the generated one would overwrite")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".tradecraft-reading-", dir=output.parent) as temporary:
        staged = Path(temporary) / "reading"
        staged.mkdir()
        try:
            claims = recipient_tree._extract_archive(source, head, files, staged, []) if files else {}
            for name in as_file:
                (staged / name).write_bytes(pieces[name])
                claims[name] = {"mode": "100644", "oid": recipient_tree._blob_oid(source, pieces[name])}
            # The entrance's branch names carry a unique token, so a match is the change naming itself.
            needle = branch.encode("utf-8")
            for name in sorted(claims):
                if needle and needle in (staged / Path(*PurePosixPath(name).parts)).read_bytes():
                    raise ColdReaderError(f"carried file names the change's branch: {name}")
            if needle and needle in (diff or b"") + (pieces[EXCERPTS_FILE] or b""):
                raise ColdReaderError("the change's diff names its branch")
            recipient_tree._initialize_neutral_repository(staged, dict(sorted(claims.items())))
            recipient_tree._prove_neutral_repository(staged, source)
        except recipient_tree.RecipientTreeError as exc:
            raise ColdReaderError(str(exc)) from exc
        # Counted in every carried file, not refused: a decision record the change adds lawfully names
        # them, and their links are dead to a reader with no network.
        residue = {}
        for name in sorted(claims):
            content = (staged / Path(*PurePosixPath(name).parts)).read_text("utf-8", errors="replace")
            counts = {f"#{number}": len(re.findall(rf"#{number}(?![0-9])", content)) for number in numbers}
            counts = {key: value for key, value in counts.items() if value}
            if counts:
                residue[name] = counts
        staged.replace(output)
    placed = {name: "none" if pieces[name] is None else "inline" if inline[name] else name for name in pieces}
    value = {
        "schema_version": SCHEMA_VERSION, "work": work, "producer_version": producer_version,
        "tree_root": str(output), "source_root": str(source), "base": state["base"], "head": head,
        "change_set": changed, "coverage": coverage, "whole": set(selected) == set(changed),
        "files": claims, "diff": placed[DIFF_FILE], "excerpts": placed[EXCERPTS_FILE], "residue": residue,
        "verification": "raw-object-ids-match", "mode": mode, "lines": lines,
    }
    if mode != "first":
        value.update(since={path: (order.get("since") or {}).get(path) for path in selected},
                     earlier_flags=list(order.get("earlier_flags") or []),
                     gained_unknown=sorted(order.get("gained_unknown") or []))
    value["metadata_sha256"] = _digest(value)
    # The diff first, so a record that stands always has its diff.
    try:
        if diff is not None and inline[DIFF_FILE]:
            recipient_tree.write_record(record.with_suffix(".diff"), diff)
        recipient_tree.write_record(
            record, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n")
    except OSError:
        # A diff whose record never stood belongs to no reading.
        record.with_suffix(".diff").unlink(missing_ok=True)
        raise
    return record


def reading_record(root: Path, records_home: Path) -> Path:
    """A reading's record: in the entrance's records, or beside its tree where the former layout wrote it."""
    # A reading recorded beside its tree still counts for the pull request that holds it; a record found in
    # neither place is named where it belongs, so a lost record is reported there.
    record = recipient_tree.record_path(root, records_home)
    former = recipient_tree.former_record_path(root)
    return former if not record.exists() and former.exists() else record


def load_metadata(path: Path) -> dict:
    try:
        value = json.loads(Path(path).read_bytes())
    except (OSError, ValueError) as exc:
        raise ColdReaderError(f"cannot read reading metadata: {path}") from exc
    if not isinstance(value, dict) or value.get("schema_version") not in SCHEMA_VERSIONS:
        raise ColdReaderError("reading metadata has an unsupported shape")
    claimed = value.pop("metadata_sha256", None)
    if claimed != _digest(value):
        raise ColdReaderError("reading metadata digest does not match")
    value["metadata_sha256"] = claimed
    return value


def tree_held(metadata: dict, source: Path) -> bool:
    """Whether a reading tree still stands as built: clean, its commit the claimed files, and each its object.

    Checked again when a builder's reader returns, so an edit made while it read leaves no counting
    report. Design: lib/DESIGN.md#a-builders-own-checks-and-writes
    """
    root = Path(metadata["tree_root"])
    try:
        recipient_tree._prove_neutral_repository(root, source)
        if recipient_tree._text(root, "status", "--porcelain", "--untracked-files=all", "--ignored"):
            return False
        # A clean status only compares the files with HEAD, so an amended commit is held to the claims too.
        if recipient_tree._tree_files(root, "HEAD") != (metadata.get("files") or {}):
            return False
        for name, claim in (metadata.get("files") or {}).items():
            content = (root / Path(*PurePosixPath(name).parts)).read_bytes()
            if recipient_tree._blob_oid(source, content) != claim.get("oid"):
                return False
    except (recipient_tree.RecipientTreeError, OSError):
        return False
    return True


def mode_of(metadata: dict) -> str:
    """A reading's mode; a version 1 record read whatever it covered whole, as a first reading does."""
    return metadata.get("mode", "first") if metadata.get("schema_version") == SCHEMA_VERSION else "first"


def _flag_form() -> str:
    return ("One line each, in the form `path:lines " + EM_DASH + " KIND " + EM_DASH + " text`, where KIND "
            "is one of " + ", ".join(f"`{kind}`" for kind in FLAG_KINDS) + ". `lines` is one line, one range, "
            "or several of either separated by commas, such as `path:12`, `path:12-18` or `path:12,40-44,97`.")


def _compose_v1(metadata: dict, standard: str, diff_text: str | None) -> bytes:
    # The prompt a version 1 reading was launched with, kept word for word so its report is still recomposed.
    covered = sorted(metadata["coverage"])
    parts = [
        "You are the cold reader for one change. Perform this one reading and return your "
        "account in your final message. Dispatch nothing of your own. Your root is a detached "
        "neutral commit holding only the changed files, the design documents the files this "
        "reading covers point to, and the files linked inside those pointed sections; any "
        "always-on text reaching you from elsewhere is not your governing text. Links to an issue tracker or pull request are "
        "outside your material: do not follow them.",
        "## The standard the code is read against\n\n" + standard.strip(),
        ("## The diff of the files this reading covers\n\n```diff\n" + diff_text.rstrip("\n") + "\n```")
        if diff_text is not None
        else f"## The diff of the files this reading covers\n\nIt is the file `{DIFF_FILE}` at your root.",
    ]
    if not metadata.get("whole"):
        parts.append(
            "## What this reading covers\n\nThis is a reread. It covers only these paths; the other "
            "files are there for reference only:\n\n" + "\n".join(f"- `{path}`" for path in covered))
    parts.append(
        "## Your account\n\nReturn exactly these four headings, in this order:\n\n"
        "## Sections\nFor each changed section: its location (path and line range), what it is for, "
        "why it is that way, and where you found the reason (a code line, a design-document section "
        "or a decision record). Where you can't tell, say so.\n\n"
        "## Flags\n" + _flag_form() + " A flag may name a carried file the "
        "change didn't alter, such as a design-document section missing an entry. With no flags, "
        "write the single word `none`. Each flag names a file in your root, and a flag on the diff names "
        "the changed file whose lines it shows.\n\n"
        "## Why this change was made\nIts first line is exactly `Can tell: yes` or `Can tell: no`. "
        "Then say which file the reason came from, or why you can't tell."
        + ("" if metadata.get("whole") else " Answer only for the paths this reread covers.")
        + "\n\n## Worth a look\nAt most " + str(MAX_NOMINATIONS) + " nominations, each a "
        "`path:lines` range from the diff's added or changed lines, with one line on why it's "
        "worth reading.")
    return ("\n\n".join(parts) + "\n").encode("utf-8")


def _diff_part(heading: str, diff_text: str | None) -> str:
    return (f"## {heading}\n\n```diff\n" + diff_text.rstrip("\n") + "\n```") if diff_text is not None else (
        f"## {heading}\n\nIt is the file `{DIFF_FILE}` at your root.")


def earlier_line(flag: dict) -> str:
    return f"{flag['id']}. `{flag['path']}" + (f":{flag['lines']}" if flag.get("lines") else "") + (
        f"` {EM_DASH} {flag['kind']} {EM_DASH} {flag['text']}")


WHY_QUESTION = ("## Why this change was made\nIts first line is exactly `Can tell: yes` or `Can tell: no`. "
                "Then say which file the reason came from, or why you can't tell.")


def compose_prompt(metadata: dict, standard: str, diff_text: str | None, excerpts_text: str | None = None) -> bytes:
    """The reader's instructions, composed by mode from the sealed record and the material regenerated for it."""
    if metadata.get("schema_version") != SCHEMA_VERSION:
        return _compose_v1(metadata, standard, diff_text)
    mode = mode_of(metadata)
    opening = (
        "You are the cold reader for one change. Perform this one reading and return your "
        "account in your final message. Dispatch nothing of your own. Your root is a detached "
        "neutral commit holding only the changed files, the design documents the files this "
        "reading covers point to, and the files linked inside those pointed sections; any "
        "always-on text reaching you from elsewhere is not your governing text. Links to an issue tracker or pull request are "
        "outside your material: do not follow them.")
    standard_part = "## The standard the code is read against\n\n" + standard.strip()
    if mode == "first":
        return ("\n\n".join([
            opening, standard_part, _diff_part("The diff of the files this reading covers", diff_text),
            "## Your account\n\nReturn exactly these four headings, in this order:\n\n"
            "## Sections\nFor each changed section: its location (path and line range), what it is for, "
            "why it is that way, and where you found the reason (a code line, a design-document section "
            "or a decision record). Where you can't tell, say so.\n\n"
            "## Flags\n" + _flag_form() + " Flag only what this change wrote: a line the diff adds or "
            "changes, or, where the diff only removes lines, the line just before or just after the "
            "removal, numbered as the file now stands. Older lines of a file the change only edits are not "
            "flagged, even where they fall short of the standard, so a flag on such a file gives its lines. "
            "An `in-force-missing` or `dead-end-pointer` flag may also name a document a covered file points "
            "to, for a gap this change leaves there. With no flags, write the single word `none`. Each flag "
            "names a file in your root, and a flag on the diff names the changed file whose lines it shows."
            "\n\n" + WHY_QUESTION + "\n\n## Worth a look\nAt most " + str(MAX_NOMINATIONS) + " nominations, "
            "each a `path:lines` range from the diff's added or changed lines, with one line on why it's "
            "worth reading."]) + "\n").encode("utf-8")
    earlier = metadata.get("earlier_flags") or []
    parts = [
        opening,
        "## What this reading is\n\nThis is a reread. The change was read whole earlier, its flags were "
        "answered with fixes or accepted, and this reading checks those fixes and judges nothing else again. "
        "Judge each earlier flag below against the code and documents as they now stand, and flag only the "
        "marked lines.",
        standard_part,
        "## The earlier flags\n\n" + ("\n".join(earlier_line(flag) for flag in earlier)
                                      + "\n\nAn earlier flag's lines are numbered as its file stood when the flag "
                                      "was raised, so a fix since may have moved them." if earlier else "None."),
        "## The lines to judge\n\n" + (
            excerpts_text.rstrip("\n") if excerpts_text is not None
            else f"They are in the file `{EXCERPTS_FILE}` at your root.")
        + "\n\nEach excerpt numbers the file's lines as it now stands and marks each line to judge with `>`.",
    ]
    if mode == "why-check":
        parts.append(_diff_part("The diff of the whole change", diff_text)
                     + "\n\nAn earlier reading could not tell why this change was made. This diff is shown so "
                     "you can say whether you now can; it opens no other line to a flag.")
    headings = "these two headings" if mode == "fix-check" else "these three headings"
    parts.append(
        "## What you may flag\n\nOnly a marked line may be flagged, whatever the flag's kind. A gap a fix "
        "leaves in another document is flagged at the marked line that creates it, such as the pointer or "
        "the decision the fix adds. The rest of your root is for following code across files only.")
    parts.append(
        f"## Your account\n\nReturn exactly {headings}, in this order:\n\n"
        "## Earlier flags\nOne line for each earlier flag, `F1 " + EM_DASH + " answered " + EM_DASH + " why` "
        "when the code or documents as they now stand settle its point, or `F1 " + EM_DASH + " not-answered "
        + EM_DASH + " why` when they don't. With no earlier flags, write the single word `none`.\n\n"
        "## Flags\nNew flags on marked lines only. " + _flag_form() + " With no flags, write the single "
        "word `none`. Each flag names a file in your root."
        + ("\n\n" + WHY_QUESTION if mode == "why-check" else ""))
    return ("\n\n".join(parts) + "\n").encode("utf-8")


def _sections(text: str, headings: tuple[str, ...] = HEADINGS) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    heading = None
    for line in text.replace("\r\n", "\n").split("\n"):
        stripped = line.rstrip()
        if stripped in headings:
            heading = stripped
            found.setdefault(heading, [])
        elif heading is not None:
            found[heading].append(stripped)
    return found


def flaggable(metadata: dict) -> set[str]:
    """The paths a flag may name: every carried file, and every covered path the change deleted."""
    # A deleted file isn't carried, yet the diff shows its removed lines and a later reading covering it
    # can clear a flag on it.
    deleted = {path for path, entry in metadata["coverage"].items() if entry["blob"] == "deleted"}
    return (set(metadata["files"]) - set(GENERATED)) | deleted


def _inferred_mode(text: str) -> str:
    # A return read without its record, as a builder's posted report is, says its mode by its headings.
    found = _sections(text, MODE_HEADINGS["why-check"] + HEADINGS)
    if EARLIER_HEADING not in found:
        return "first"
    return "why-check" if "## Why this change was made" in found else "fix-check"


def form_errors(text: str, carried: set[str] | None = None, *, mode: str | None = None,
                earlier: list[str] | None = None) -> list[str]:
    """Check only the account's form; everything else is the reader's judgement.

    `mode` names the headings the account owes, inferred from the text when not given; `earlier` names
    the earlier flags a reread must judge, each once, and none it doesn't hold.
    """
    mode = mode or _inferred_mode(text)
    headings = MODE_HEADINGS[mode]
    found = _sections(text, headings)
    errors = [f"missing heading {heading}" for heading in headings if heading not in found]
    if "## Sections" in found and not any(line.strip() for line in found["## Sections"]):
        errors.append("## Sections holds nothing")
    flags = [line for line in found.get("## Flags", []) if line.strip()]
    if "## Flags" in found and not (len(flags) == 1 and NO_FLAGS.match(flags[0].strip())):
        errors.extend(f"malformed flag line: {line}" for line in flags if not FLAG_LINE.match(line))
        named = [match.group("path").removeprefix("./") for match in map(FLAG_LINE.match, flags) if match]
        # The generated files aren't part of the change, so a flag on one names nothing a later reading reaches.
        errors.extend(f"flag names the diff file rather than the changed file it shows: {path}"
                      for path in named if path in GENERATED)
        # A flag on a file the reading never held could never be cleared by a later reading.
        if carried is not None:
            errors.extend(f"flag names a path outside the reading's tree: {path}"
                          for path in named if path not in GENERATED and path not in carried)
        if not flags:
            errors.append("## Flags holds neither flag lines nor `none`")
    if EARLIER_HEADING in found:
        lines = [line for line in found[EARLIER_HEADING] if line.strip()]
        if not (len(lines) == 1 and NO_FLAGS.match(lines[0].strip())):
            errors.extend(f"malformed earlier-flag line: {line}" for line in lines if not VERDICT_LINE.match(line))
            ids = [match.group("id") for match in map(VERDICT_LINE.match, lines) if match]
            if not lines:
                errors.append(f"{EARLIER_HEADING} holds neither verdict lines nor `none`")
            errors.extend(f"earlier flag {flag} has more than one verdict"
                          for flag in sorted(set(ids)) if ids.count(flag) > 1)
            if earlier is not None:
                errors.extend(f"earlier flag {flag} is not one this reading was given"
                              for flag in sorted(set(ids)) if flag not in earlier)
        else:
            ids = []
        if earlier is not None:
            errors.extend(f"earlier flag {flag} has no verdict" for flag in earlier if flag not in ids)
    why = [line for line in found.get("## Why this change was made", []) if line.strip()]
    if "## Why this change was made" in found and (not why or not CAN_TELL.match(why[0])):
        errors.append("## Why this change was made does not open with `Can tell: yes` or `Can tell: no`")
    return errors


def account_errors(metadata: dict, text: str) -> list[str]:
    """The form check of a return against the reading its record describes."""
    earlier = [flag["id"] for flag in metadata.get("earlier_flags") or []]
    mode = mode_of(metadata)
    return form_errors(text, flaggable(metadata), mode=mode, earlier=earlier if mode != "first" else None)


def parse_account(text: str, mode: str | None = None) -> dict:
    mode = mode or _inferred_mode(text)
    found = _sections(text, MODE_HEADINGS[mode])
    flags = []
    for line in found.get("## Flags", []):
        match = FLAG_LINE.match(line)
        if match:
            flags.append({"path": match.group("path").removeprefix("./"), "lines": match.group("lines"),
                          "kind": match.group("kind"), "text": match.group("text")})
    verdicts = {}
    for line in found.get(EARLIER_HEADING, []):
        match = VERDICT_LINE.match(line)
        if match:
            verdicts[match.group("id")] = {"verdict": match.group("verdict"), "why": match.group("why") or ""}
    why = [line for line in found.get("## Why this change was made", []) if line.strip()]
    tell = CAN_TELL.match(why[0]) if why else None
    return {"flags": flags, "can_tell": None if tell is None else tell.group(1) == "yes", "verdicts": verdicts}


def reading_flags(metadata: dict, account: dict) -> list[dict]:
    """A reading's flags in acceptance order: its own, then each earlier flag it returned `not-answered`.

    A carried flag keeps its path, lines, kind and text, so the usual acceptance line names it, and
    records the flag it carries.
    """
    carried = []
    for earlier in metadata.get("earlier_flags") or []:
        verdict = account.get("verdicts", {}).get(earlier["id"])
        if verdict is not None and verdict["verdict"] == "not-answered":
            carried.append({"path": earlier["path"], "lines": earlier.get("lines"), "kind": earlier["kind"],
                            "text": earlier["text"], "carries": earlier["id"]})
    return [*account["flags"], *carried]


def flag_line(flag: dict) -> str:
    location = flag["path"] + (":" + flag["lines"] if flag.get("lines") else "")
    return f"{location} {EM_DASH} {flag['kind']} {EM_DASH} {flag['text']}"


def _same_lines(left: str | None, right: str | None) -> bool:
    # The same items in the same order, whatever the dash or comma spacing; part of a list names no flag.
    def items(lines: str | None) -> str:
        return re.sub(r"\s", "", lines or "").replace(EN_DASH, "-")
    return items(left) == items(right)


def acceptances(comment: str, flags: list[dict]) -> tuple[dict[int, str], list[str]]:
    """Match the holder's acceptance lines, beneath its review heading, to the account's flags.

    Returns each accepted flag's position with its reason, and an error naming each line that
    doesn't name exactly one flag.
    """
    accepted, errors, in_review = {}, [], False
    for line in comment.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        if stripped.strip("#* :").replace(chr(0x2019), "'") == REVIEW_HEADING:
            in_review = True
            continue
        if not in_review or not ACCEPTANCE_START.match(stripped):
            continue
        match = ACCEPTANCE.match(stripped)
        if match is None:
            errors.append(f"malformed acceptance line: {stripped}")
            continue
        path, rest = match.group("path").removeprefix("./"), match.group("rest")
        candidates = [position for position, flag in enumerate(flags)
                      if flag["path"] == path and flag["kind"] == match.group("kind")
                      and (match.group("lines") is None or _same_lines(flag.get("lines"), match.group("lines")))]
        reasons = {position: rest for position in candidates}
        if len(candidates) > 1:
            # Flags sharing a location and kind are told apart by the flag's text, written before the reason.
            reasons = {}
            for position in candidates:
                text = flags[position]["text"]
                separator = SEPARATOR.match(rest[len(text):]) if rest.startswith(text) else None
                if separator:
                    reasons[position] = rest[len(text) + separator.end():]
        if len(reasons) != 1:
            errors.append(("acceptance matches no flag in the account: " if not candidates
                           else "acceptance matches more than one flag in the account; write the flag's "
                           "text before the reason: ") + stripped)
            continue
        accepted.update(reasons)
    return accepted, errors


def _reaches(reading: dict, path: str) -> bool:
    return path in reading["coverage"] or any(
        path in dependency_paths(entry) for entry in reading["coverage"].values())


def _version_one(reading: dict) -> bool:
    return reading["record"].get("schema_version") != SCHEMA_VERSION


def record_lines(root: Path, reading: dict, cache: dict) -> dict[str, object] | None:
    """The change's lines in each file a reading covered, at its head: sealed, or recomputed for version 1.

    None where a version 1 reading's base or head can't be read, so its flags stand as recorded.
    """
    record = reading["record"]
    if not _version_one(reading):
        return {path: value["change"] for path, value in record["lines"].items()}
    key = (record["base"], record["head"])
    if key not in cache:
        try:
            cache[key] = change_lines(root, record["base"], record["head"])
        except ColdReaderError:
            cache[key] = None
    lines = cache[key]
    return None if lines is None else {path: lines.get(path, []) for path in record["coverage"]}


def _whole_file(ranges: object, count: int | None) -> bool:
    if ranges == WHOLE:
        return True
    return count is not None and set(range(1, count + 1)) <= numbers_of(ranges)


def placement(reading: dict, lines: dict[str, object] | None) -> list[dict]:
    """Whether each of a reading's flags stands, or falls outside the change, with the reason.

    A newly raised flag stands where it touches a judged line of a covered file; where it names no
    lines, on a covered file judged whole; and, in a first reading only, where it is one of the two
    document gaps on a document a covered file's pointer reaches. A carried flag stands by its verdict.
    """
    record = reading["record"]
    version_one = _version_one(reading)
    first = mode_of(record) == "first"
    if version_one:
        judged, counts = lines, {}
    else:
        judged = {path: value["judged"] for path, value in record["lines"].items()}
        counts = {path: value["count"] for path, value in record["lines"].items()}
    reached = set().union(*(dependency_paths(entry) for entry in record["coverage"].values())) if first else set()
    placed = []
    for flag in reading["flags"]:
        path, numbers = flag["path"], flag_numbers(flag.get("lines"))
        # A version 1 reader was never told to give lines, so its line-less flag stands as it did.
        if "carries" in flag or judged is None or (version_one and not numbers):
            placed.append({"stands": True, "reason": None})
            continue
        stands = False
        if path in judged:
            ranges = judged[path]
            if ranges == WHOLE:
                stands = True
            elif numbers:
                stands = bool(numbers & numbers_of(ranges))
            else:
                stands = _whole_file(ranges, counts.get(path))
        if not stands and first and flag["kind"] in DOCUMENT_GAPS and path in reached:
            stands = True
        if stands:
            placed.append({"stands": True, "reason": None})
        elif path in judged or path in reached:
            placed.append({"stands": False, "reason": "old-line" if numbers else "no-lines"})
        else:
            placed.append({"stands": False, "reason": "not-reached"})
    return placed


def assess(readings: list[dict], present: dict, root: Path) -> dict:
    """Judge the current change set against readings ordered oldest first, and order the next reading.

    Each reading carries its sealed record, its parsed account, its flags in acceptance order and the
    positions its `open` accepted. A path is unread while it has lines gained since its last reading;
    a flag stands until a later reread judges it or the holder accepts it.
    """
    changed = present["change_set"]
    cache: dict = {}
    placements = {reading["id"]: placement(reading, record_lines(root, reading, cache)) for reading in readings}
    # Each earlier flag a reread judged, by the reading that raised it and its place there.
    judged_later = {}
    for index, reading in enumerate(readings):
        for earlier in reading["record"].get("earlier_flags") or []:
            judged_later[(earlier["reading"], earlier["position"])] = index
    reachable = set(changed).union(*(dependency_paths(entry) for entry in present["coverage"].values()))
    standing = []
    for index, reading in enumerate(readings):
        digest = reading["record"]["metadata_sha256"]
        for position, flag in enumerate(reading["flags"]):
            if not placements[reading["id"]][position]["stands"]:
                continue
            # The holder accepted it with a reason, which the owner judges from the release report.
            if position in reading.get("accepted", {}):
                continue
            # A later reread judged it: `answered` cleared it, and `not-answered` carried it into that reading.
            if judged_later.get((digest, position), -1) > index:
                continue
            # A later reading of whole files, version 1 or a first reading, that reaches it judged it again, as
            # every reading did before rereads checked fixes; it is how two version 1 readings still clear.
            if any(mode_of(later["record"]) == "first" and _reaches(later, flag["path"])
                   for later in readings[index + 1:]):
                continue
            # Nothing in the change reaches it any more, so the reading of what changed answers for it.
            if flag["path"] not in reachable:
                continue
            standing.append({**flag, "reading": reading["id"], "digest": digest, "position": position})
    latest: dict[str, dict] = {}
    for reading in readings:
        for path in reading["coverage"]:
            latest[path] = reading
    diffs: dict[str, dict | None] = {}

    def since_diff(head: str) -> dict | None:
        if head not in diffs:
            try:
                diffs[head] = file_diffs(root, head, present["head"])
            except ColdReaderError:
                diffs[head] = None
        return diffs[head]

    now: dict[str, object] | None = None
    unread: dict[str, object] = {}
    since: dict[str, str | None] = {}
    unknown = []
    for path, blob in changed.items():
        reading, earlier_path = latest.get(path), path
        if reading is None and readings:
            # A file renamed since its last reading is read on from its earlier path.
            moved = (since_diff(readings[-1]["head"]) or {}).get(path)
            if moved is not None and moved["old"] in latest:
                earlier_path = moved["old"]
                reading = latest[earlier_path]
        since[path] = None if reading is None else reading["head"]
        same_blob = reading is not None and reading["coverage"][earlier_path]["blob"] == blob
        if same_blob and earlier_path == path and reading["record"]["base"] == present["base"]:
            continue
        if now is None:
            now = change_lines(root, present["base"], present["head"])
        lines = now.get(path, [])
        if reading is None:
            found = lines
        else:
            earlier = record_lines(root, reading, cache)
            between = since_diff(reading["head"])
            if earlier is None or between is None:
                # Where the earlier reading can't be placed, every line of the file is read again.
                found = lines
                unknown.append(path)
            else:
                found = gained(lines, earlier.get(earlier_path, []), between.get(path), same_blob=same_blob)
        if found:
            unread[path] = found
    said_no = [index for index, reading in enumerate(readings) if reading["account"]["can_tell"] is False]
    # A reread narrower than the change answers only for the files it read.
    standing_no = bool(said_no) and not any(
        reading["account"]["can_tell"] is True and set(changed) <= set(reading["coverage"])
        for reading in readings[said_no[-1] + 1:])
    earlier_flags = [{"id": f"F{number}", "reading": flag["digest"], "position": flag["position"],
                      "path": flag["path"], "lines": flag.get("lines"), "kind": flag["kind"], "text": flag["text"]}
                     for number, flag in enumerate(standing, 1)]
    if not readings:
        order = {"mode": "first", "covered": sorted(changed)}
    elif standing_no:
        # Only a reading of the whole change clears a `no`, but its flags stay on the lines gained since.
        order = {"mode": "why-check", "covered": sorted(changed),
                 "judged": {path: unread.get(path, []) for path in changed}}
    elif unread or standing:
        order = {"mode": "fix-check", "covered": sorted(unread), "judged": dict(unread)}
    else:
        order = None
    if order is not None and order["mode"] != "first":
        order.update(since={path: since[path] for path in order["covered"]}, earlier_flags=earlier_flags,
                     gained_unknown=sorted(path for path in unknown if path in order["covered"]))
    return {"stale": sorted(unread), "unread": unread, "flags": standing, "standing_no": standing_no,
            "owed": [] if order is None else order["covered"], "placements": placements,
            "gained_unknown": sorted(unknown), "order": order}


def counted_findings(metadata: dict, text: str, root: Path) -> tuple[list[str], list[dict]]:
    """A reading's findings as a builder's record answers them, and, apart, its flags outside the change.

    The findings are each flag that stands, its own and each earlier one it left `not-answered`, then a
    `Can tell: no`; a flag outside the change needs nothing, so no record owes it an entry.
    """
    account = parse_account(text, mode_of(metadata))
    reading = {"record": metadata, "flags": reading_flags(metadata, account)}
    placed = placement(reading, record_lines(root, reading, {}))
    findings = [flag_line(flag) for flag, entry in zip(reading["flags"], placed) if entry["stands"]]
    if account["can_tell"] is False:
        findings.append("Can tell: no")
    outside = [{"flag": flag_line(flag), "reason": entry["reason"]}
               for flag, entry in zip(reading["flags"], placed) if not entry["stands"]]
    return findings, outside
