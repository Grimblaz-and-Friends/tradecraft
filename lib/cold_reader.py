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

SCHEMA_VERSION = 1
FLAG_KINDS = (
    "cannot-tell", "missing-reason", "what-comment", "changeable-number", "history",
    "dead-end-pointer", "in-force-missing",
)
HEADINGS = ("## Sections", "## Flags", "## Why this change was made", "## Worth a look")
MAX_NOMINATIONS = 5
# Above this the diff travels as a file, so the prompt stays readable.
INLINE_DIFF_CHARACTERS = 60_000
DIFF_FILE = "CHANGE.diff"
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
# Lenient on dashes, bullets and backticks, so a reader's stray formatting doesn't refuse a whole account.
FLAG_LINE = re.compile(
    r"^(?:[-*][ \t]+)?`?(?P<path>[^\s:`]+)(?::(?P<lines>[0-9]+(?:[-" + EN_DASH + r"][0-9]+)?))?`?"
    r"[ \t]+[" + EM_DASH + r"-][ \t]+(?P<kind>" + "|".join(FLAG_KINDS) + r")[ \t]+["
    + EM_DASH + r"-][ \t]+(?P<text>\S.*)$"
)
NO_FLAGS = re.compile(r"^(?:[-*][ \t]+)?`?none\.?`?\.?$", re.IGNORECASE)
CAN_TELL = re.compile(r"^Can tell: (yes|no)$")
REVIEW_HEADING = "Holder's review against the brief"
# A mistyped acceptance must fail the `open`, so it never silently accepts nothing.
ACCEPTANCE = re.compile(
    r"^(?:[-*][ \t]+)?Accepted:[ \t]+`?(?P<path>[^\s:`]+)(?::(?P<lines>[0-9]+(?:[-" + EN_DASH
    + r"][0-9]+)?))?`?[ \t]+[" + EM_DASH + r"-][ \t]+(?P<kind>" + "|".join(FLAG_KINDS) + r")[ \t]+["
    + EM_DASH + r"-][ \t]+(?P<rest>\S.*)$"
)
ACCEPTANCE_START = re.compile(r"^(?:[-*][ \t]+)?Accepted:")
SEPARATOR = re.compile(r"^[ \t]+[" + EM_DASH + r"-][ \t]+(?=\S)")


class ColdReaderError(RuntimeError):
    """The reading cannot be built or judged from committed bytes."""


def _git(root: Path, *arguments: str) -> bytes:
    try:
        return recipient_tree._git(root, *arguments)
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


def build_tree(*, source: Path, output: Path, work: str, producer_version: str,
               base_tip: str, head: str, covered: list[str] | None, branch: str,
               numbers: list[int], records_home: Path) -> Path:
    """Write the reading tree, its record and diff kept in the entrance's records; refuse one naming the branch."""
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
    selected = sorted(changed if covered is None else covered)
    unknown = [path for path in selected if path not in changed]
    if unknown:
        raise ColdReaderError("covered paths are not in the change set: " + ", ".join(unknown))
    coverage = {path: state["coverage"][path] for path in selected}
    # A reread carries every changed file so the reader can follow code across files; a flag it raises on
    # one it didn't cover still stands, and the gate owes that file a reread.
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
    # A rename's old path joins the pathspec so the diff shows the edit as a rename, removed lines and all.
    moved = renames(source, state["base"], head)
    pathspec = sorted(set(selected) | {moved[path] for path in selected if path in moved})
    diff = _git(source, "diff", "--no-color", "--no-ext-diff", "-M", state["base"], head, "--", *pathspec)
    diff_text = diff.decode("utf-8", errors="replace")
    # With nothing else to carry the diff travels as a file, since the neutral commit can't be empty.
    inline = len(diff_text) <= INLINE_DIFF_CHARACTERS and bool(files)
    if not inline and DIFF_FILE in files:
        raise ColdReaderError(f"the change carries a root {DIFF_FILE}, which the generated diff would overwrite")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".tradecraft-reading-", dir=output.parent) as temporary:
        staged = Path(temporary) / "reading"
        staged.mkdir()
        try:
            claims = recipient_tree._extract_archive(source, head, files, staged, []) if files else {}
            if not inline:
                (staged / DIFF_FILE).write_bytes(diff)
                claims[DIFF_FILE] = {"mode": "100644", "oid": recipient_tree._blob_oid(source, diff)}
            # The entrance's branch names carry a unique token, so a match is the change naming itself.
            needle = branch.encode("utf-8")
            for name in sorted(claims):
                if needle and needle in (staged / Path(*PurePosixPath(name).parts)).read_bytes():
                    raise ColdReaderError(f"carried file names the change's branch: {name}")
            if needle and needle in diff:
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
    value = {
        "schema_version": SCHEMA_VERSION, "work": work, "producer_version": producer_version,
        "tree_root": str(output), "source_root": str(source), "base": state["base"], "head": head,
        "change_set": changed, "coverage": coverage, "whole": set(selected) == set(changed),
        "files": claims, "diff": "inline" if inline else DIFF_FILE, "residue": residue,
        "verification": "raw-object-ids-match",
    }
    value["metadata_sha256"] = _digest(value)
    # The diff first, so a record that stands always has its diff.
    if inline:
        recipient_tree.write_record(record.with_suffix(".diff"), diff)
    recipient_tree.write_record(
        record, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n")
    return record


def reading_record(root: Path, records_home: Path) -> Path:
    """A reading's record: in the entrance's records, or where a reading taken before that layout left it."""
    # Pull requests open when the layout changed hold readings recorded the former way, and they still count.
    record = recipient_tree.record_path(root, records_home)
    return record if record.exists() else recipient_tree.former_record_path(root)


def load_metadata(path: Path) -> dict:
    try:
        value = json.loads(Path(path).read_bytes())
    except (OSError, ValueError) as exc:
        raise ColdReaderError(f"cannot read reading metadata: {path}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise ColdReaderError("reading metadata has an unsupported shape")
    claimed = value.pop("metadata_sha256", None)
    if claimed != _digest(value):
        raise ColdReaderError("reading metadata digest does not match")
    value["metadata_sha256"] = claimed
    return value


def compose_prompt(metadata: dict, standard: str, diff_text: str | None) -> bytes:
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
        "## Flags\nOne line each, in the form `path:lines " + EM_DASH + " KIND " + EM_DASH
        + " text`, where KIND is one of "
        + ", ".join(f"`{kind}`" for kind in FLAG_KINDS) + ". A flag may name a carried file the "
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


def _sections(text: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    heading = None
    for line in text.replace("\r\n", "\n").split("\n"):
        stripped = line.rstrip()
        if stripped in HEADINGS:
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
    return (set(metadata["files"]) - {DIFF_FILE}) | deleted


def form_errors(text: str, carried: set[str] | None = None) -> list[str]:
    """Check only the account's form; everything else is the reader's judgement."""
    found = _sections(text)
    errors = [f"missing heading {heading}" for heading in HEADINGS if heading not in found]
    if "## Sections" in found and not any(line.strip() for line in found["## Sections"]):
        errors.append("## Sections holds nothing")
    flags = [line for line in found.get("## Flags", []) if line.strip()]
    if "## Flags" in found and not (len(flags) == 1 and NO_FLAGS.match(flags[0].strip())):
        errors.extend(f"malformed flag line: {line}" for line in flags if not FLAG_LINE.match(line))
        named = [match.group("path").removeprefix("./") for match in map(FLAG_LINE.match, flags) if match]
        # The diff file isn't part of the change, so a flag on it names nothing a later reading reaches.
        errors.extend(f"flag names the diff file rather than the changed file it shows: {path}"
                      for path in named if path == DIFF_FILE)
        # A flag on a file the reading never held could never be cleared by a later reading.
        if carried is not None:
            errors.extend(f"flag names a path outside the reading's tree: {path}"
                          for path in named if path != DIFF_FILE and path not in carried)
        if not flags:
            errors.append("## Flags holds neither flag lines nor `none`")
    why = [line for line in found.get("## Why this change was made", []) if line.strip()]
    if "## Why this change was made" in found and (not why or not CAN_TELL.match(why[0])):
        errors.append("## Why this change was made does not open with `Can tell: yes` or `Can tell: no`")
    return errors


def parse_account(text: str) -> dict:
    found = _sections(text)
    flags = []
    for line in found.get("## Flags", []):
        match = FLAG_LINE.match(line)
        if match:
            flags.append({"path": match.group("path").removeprefix("./"), "lines": match.group("lines"),
                          "kind": match.group("kind"), "text": match.group("text")})
    why = [line for line in found.get("## Why this change was made", []) if line.strip()]
    tell = CAN_TELL.match(why[0]) if why else None
    return {"flags": flags, "can_tell": None if tell is None else tell.group(1) == "yes"}


def flag_line(flag: dict) -> str:
    location = flag["path"] + (":" + flag["lines"] if flag.get("lines") else "")
    return f"{location} {EM_DASH} {flag['kind']} {EM_DASH} {flag['text']}"


def _same_lines(left: str | None, right: str | None) -> bool:
    return (left or "").replace(EN_DASH, "-") == (right or "").replace(EN_DASH, "-")


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


def assess(readings: list[dict], present: dict) -> dict:
    """Judge the current change set against readings ordered oldest first.

    Each reading carries its metadata coverage and its parsed account; wholeness is judged from that
    coverage against the current change set.
    """
    changed = present["change_set"]
    latest: dict[str, dict] = {}
    for reading in readings:
        for path in reading["coverage"]:
            latest[path] = reading
    stale = sorted(path for path in changed
                   if path not in latest or latest[path]["coverage"][path] != present["coverage"][path])
    reachable = set(changed).union(*(dependency_paths(entry) for entry in present["coverage"].values()))
    standing_flags, seen = [], set()
    for index, reading in enumerate(readings):
        for position, flag in enumerate(reading["account"]["flags"]):
            # The holder accepted it with a reason, which the owner judges from the release report.
            if position in reading.get("accepted", {}):
                continue
            # Fails closed: only a later reading that reaches the flag's path can clear it.
            if any(_reaches(later, flag["path"]) for later in readings[index + 1:]):
                continue
            # Nothing in the change reaches it any more, so the reread of what changed answers for it.
            if flag["path"] not in reachable:
                continue
            key = (reading["id"], flag["path"], flag["kind"], flag["text"])
            if key not in seen:
                seen.add(key)
                standing_flags.append({**flag, "reading": reading["id"]})
    # A flag answered without touching its file still needs a reading that reaches it to clear.
    owed = set(stale)
    for flag in standing_flags:
        owed.update(path for path in changed if path == flag["path"]
                    or flag["path"] in dependency_paths(present["coverage"][path]))
    said_no = [index for index, reading in enumerate(readings) if reading["account"]["can_tell"] is False]
    # A reread narrower than the change answers only for the files it read.
    standing_no = bool(said_no) and not any(
        reading["account"]["can_tell"] is True and set(changed) <= set(reading["coverage"])
        for reading in readings[said_no[-1] + 1:])
    return {"stale": stale, "flags": standing_flags, "owed": sorted(owed), "standing_no": standing_no}

