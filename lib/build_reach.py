"""Measure committed builder contributions and enforce explicit holder accounts."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zlib

import preflight
import run_lifecycle as lifecycle
import seat_process


SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z", re.I)
PRESERVATION = (
    "Remove or rewrite existing content only where a governing row or criterion requires it; "
    "keep the rest, and name in your return any additional removal or rewrite you recommend."
)
REFERENCES = {"row-or-criterion": "requirement", "generator": "generator",
              "restored": "restored_by", "owner-ruling": "ruling_source", "own-turn": "added_by"}


class ReachError(ValueError):
    """Evidence cannot establish reach; the holder must restore or settle it."""


class ReachTimeout(ReachError):
    """A read stopped because time ran out, which is not a missing object.

    Design: lib/DESIGN.md#the-entrances-work-before-a-launch
    """

    def __init__(self, limit):
        super().__init__("time ran out before this read finished: " + limit)
        self.limit = limit


def test_path(path):
    parts = path.replace("\\", "/").split("/")
    if any(part.lower() in {"test", "tests", "__tests__", "spec", "specs"} for part in parts[:-1]):
        return True
    name = parts[-1]
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return bool(re.match(r"test[_\-.]", name, re.I)
                or re.search(r"_(?:test|spec)$", stem, re.I)
                or re.search(r"\.(?:test|spec)(?:\.|$)", stem, re.I)
                or re.match(r"Test(?:[A-Z0-9_]|$)", stem)
                or re.search(r"(?:Test|Tests|Spec|Specs)$", stem))


def moment(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, AttributeError, TypeError):
        return None


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReachError("duplicate JSON field: " + key)
        result[key] = value
    return result


def _items(value):
    if not isinstance(value, list):
        raise ReachError("reach items must be a list")
    paths = set()
    for item in value:
        if not isinstance(item, dict) or not _nonempty(item.get("path")):
            raise ReachError("reach item needs an exact path")
        if item["path"] in paths:
            raise ReachError("duplicate reach path: " + item["path"])
        paths.add(item["path"])
        disposition = item.get("disposition")
        field = REFERENCES.get(disposition) if isinstance(disposition, str) else None
        if field is None:
            raise ReachError("unknown reach disposition")
        if set(item) != {"path", "disposition", "basis", field} or not _nonempty(item.get("basis")):
            raise ReachError("reach item needs nonempty basis and only its disposition's reference field")
        reference = item[field]
        if field == "restored_by":
            if (not isinstance(reference, dict) or set(reference) != {"dispatch_id", "head"}
                    or not _nonempty(reference["dispatch_id"]) or not isinstance(reference["head"], str)
                    or not SHA.fullmatch(reference["head"])):
                raise ReachError("restored_by needs a later dispatch_id and full head")
        elif not _nonempty(reference):
            raise ReachError("reach disposition reference is empty: " + field)


def payload(body):
    """One exact fenced object; marker provenance is checked by the entrance."""
    blocks = re.findall(r"(?m)^```json[ \t]*\r?\n([\s\S]*?)^```[ \t]*\r?$", body)
    if len(blocks) != 1:
        raise ReachError("reach reading needs exactly one fenced JSON object")
    try:
        value = json.loads(blocks[0], object_pairs_hook=_unique_object)
    except (ValueError, TypeError) as exc:
        raise ReachError("invalid reach reading JSON: " + str(exc)) from exc
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int
            or value["schema_version"] != 1 or "turns" not in value
            or set(value) - {"schema_version", "turns", "superset_settlements"}):
        raise ReachError("invalid reach reading schema")
    shapes = {
        "turns": ({"dispatch_id", "items"}, "dispatch_id"),
        "superset_settlements": ({"turn_reference", "reason", "basis", "pull_request", "base",
                                  "merge_base", "head", "items"}, "turn_reference"),
    }
    for name, (fields, key) in shapes.items():
        entries = value.setdefault(name, [])
        if not isinstance(entries, list):
            raise ReachError(name + " must be a list")
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != fields or not _nonempty(entry.get(key)):
                raise ReachError("invalid " + name + " entry")
            if entry[key] in seen:
                raise ReachError("duplicate " + name + " entry")
            seen.add(entry[key])
            _items(entry["items"])
            if name == "superset_settlements":
                if (entry["basis"] != "pr-superset" or not _nonempty(entry["reason"])
                        or type(entry["pull_request"]) is not int or entry["pull_request"] <= 0
                        or any(not isinstance(entry[f], str) or not SHA.fullmatch(entry[f])
                               for f in ("base", "merge_base", "head"))):
                    raise ReachError("superset settlement needs exact PR bounds and reason")
    return value


# Full object ids name content that cannot change, so these reads keep their answer for the run.
MEMOISED = frozenset({"rev-list", "diff", "show", "ls-tree", "merge-base", "cat-file"})
CONSTANT_READS = frozenset({("rev-parse", "--path-format=absolute", "--git-path", "objects"),
                            ("rev-parse", "--show-object-format")})
OBJECT_TYPES = frozenset({"blob", "tree", "commit", "tag"})
READ_BOUND_SECONDS = 120
SNIFF_BYTES = 8000


def _environment():
    return {key: value for key, value in os.environ.items()
            if key not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR"}}


def run_git(command, root):
    """One bounded Git read through the contained read route; `Git`'s default runner.

    Design: lib/DESIGN.md#the-entrances-work-before-a-launch
    """
    return seat_process.run_read(["git", "-C", str(root), *command], input=b"", cwd=Path.cwd(),
                                 timeout=lifecycle.probe_timeout(READ_BOUND_SECONDS), env=_environment(),
                                 cleanup_deadline=lifecycle.cleanup_deadline())


def _full_id(argument):
    argument = argument[1:] if argument.startswith("^") else argument
    argument = argument[:-len("^{commit}")] if argument.endswith("^{commit}") else argument
    return SHA.fullmatch(argument) is not None


def _memo_for(args):
    """The scope dict a successful read is kept in, or None when it is read every time.

    Design: lib/DESIGN.md#the-entrances-work-before-a-launch
    """
    opened = preflight.current()
    if opened is None or not args:
        return None
    if args in CONSTANT_READS:
        return opened.memo
    if args[0] == "rev-parse" and len(args) == 3 and args[1] == "--verify":
        if args[2].startswith("refs/heads/"):
            # A builder's return moves its branch, so a refresh forgets this answer.
            return opened.ref_memo
        return opened.memo if args[2].endswith("^{commit}") and _full_id(args[2]) else None
    # A blob's verdict is kept instead of its content, so memory stays bounded by one blob.
    if args[0] not in MEMOISED or args[:2] == ("cat-file", "blob"):
        return None
    operands = args[1:args.index("--")] if "--" in args else args[1:]
    revisions = [value for value in operands if not value.startswith("-")
                 and not (args[0] == "cat-file" and value in OBJECT_TYPES)]
    return opened.memo if revisions and all(_full_id(value) for value in revisions) else None


def _spent():
    try:
        lifecycle.probe_timeout(READ_BOUND_SECONDS)
    except lifecycle.RunTimeout:
        return True
    return False


def _check_time():
    """Once the run's time is spent, a read stops here instead of starting a process."""
    if lifecycle.current_deadline() is None:
        return
    try:
        lifecycle.probe_timeout(READ_BOUND_SECONDS)
    except lifecycle.RunTimeout as exc:
        raise ReachTimeout(exc.limit) from exc


def _timed_out(exc):
    """Name the limit that stopped a read: the run's own, or the read's own bound."""
    limit = getattr(exc, "limit", None)
    if not limit:
        deadline = lifecycle.current_deadline()
        bound = getattr(exc, "timeout", None)
        if deadline is not None and (bound is None or _spent()):
            limit = lifecycle.limit_phrase(deadline)
        elif isinstance(bound, (int, float)):
            limit = f"this read's own {bound:g}-second bound"
        else:
            limit = "this read's own bound"
    return ReachTimeout(limit)


def _build_view(view, objects, object_format):
    (view / "objects" / "info").mkdir(parents=True)
    (view / "refs").mkdir()
    (view / "HEAD").write_bytes(b"ref: refs/heads/unused\n")
    (view / "config").write_bytes(b"[core]\nrepositoryformatversion = 1\nbare = true\n"
                                   b"[extensions]\nobjectformat = " + object_format + b"\n")
    # Bare diffs can consult the compared tree's .gitattributes too.
    # Pin the attribute source to an empty tree in this disposable
    # object store; the holder's shared objects remain untouched.
    empty = b"tree 0\0"
    tree = hashlib.new(object_format.decode("ascii"), empty).hexdigest()
    loose = view / "objects" / tree[:2]
    loose.mkdir()
    (loose / tree[2:]).write_bytes(zlib.compress(empty))
    (view / "objects" / "info" / "alternates").write_bytes(
        (json.dumps(_path(objects), ensure_ascii=False) + "\n").encode("utf-8"))
    attributes = view / "attributes"
    attributes.write_bytes(b"* diff\n")
    return view, attributes, tree


def _batch_line(stream):
    line = stream.stdout.readline(4096)
    if not line.endswith(b"\n"):
        stream.remaining()
        raise ReachError("restore local Git read capability and retry: cat-file batch ended early")
    return line


def _batch_verdict(stream, blob):
    """Read one blob from the batch, holding only its first bytes for the NUL test."""
    stream.remaining()
    stream.stdin.write(blob + b"\n")
    if hasattr(stream.stdin, "flush"):
        stream.stdin.flush()
    fields = _batch_line(stream).split()
    name = blob.decode("ascii", errors="replace")
    if len(fields) == 2 and fields[1] in {b"missing", b"ambiguous"}:
        raise ReachError("restore required Git objects/read capability and retry: blob "
                         + name + " " + fields[1].decode("ascii"))
    if len(fields) != 3 or fields[0].lower() != blob.lower() or fields[1] != b"blob" or not fields[2].isdigit():
        raise ReachError("unsupported cat-file batch header for blob " + name)
    size = int(fields[2])
    head = bytearray()
    remaining = size + 1  # the blob, then the batch's own newline
    last = b""
    while remaining:
        chunk = stream.stdout.read(min(remaining, 65536))
        if not chunk:
            stream.remaining()
            raise ReachError("restore local Git read capability and retry: cat-file batch ended early")
        if len(head) < SNIFF_BYTES:
            head += chunk[:SNIFF_BYTES - len(head)]
        remaining -= len(chunk)
        last = chunk[-1:]
    if last != b"\n":
        raise ReachError("unsupported cat-file batch record for blob " + name)
    return b"\0" in head[:min(SNIFF_BYTES, size)]


class Git:
    """Read-only Git with the entrance's bounded subprocess adapter.

    Inside a preflight scope, successful reads of fixed objects are kept for the
    run, so a turn already measured starts no process.
    Design: lib/DESIGN.md#the-entrances-work-before-a-launch
    """

    def __init__(self, root, run=None):
        self.root, self.run = Path(root), run or run_git
        self._binary = {}

    def _key(self, kind, args):
        return (str(self.root.resolve()), kind, tuple(args))

    def read(self, *args):
        return self._read(args, "read", args)

    def _read(self, args, kind, invocation):
        memo = _memo_for(args)
        key = self._key(kind, args) if memo is not None else None
        if memo is not None and key in memo:
            return memo[key]
        _check_time()
        try:
            result = self.run(["-c", "core.quotePath=true", *invocation], self.root)
        except (TimeoutError, subprocess.TimeoutExpired) as exc:
            raise _timed_out(exc) from exc
        except (OSError, subprocess.SubprocessError) as exc:
            raise ReachError("restore local Git read capability and retry: " + str(exc)) from exc
        if result.returncode:
            reason = result.stderr.decode("utf-8", errors="replace").strip()
            raise ReachError("restore required Git objects/read capability and retry: " + reason)
        if memo is not None:
            memo[key] = result.stdout
        return result.stdout

    def commit(self, revision):
        if not isinstance(revision, str) or not SHA.fullmatch(revision):
            raise ReachError("missing or invalid full commit endpoint: " + str(revision))
        try:
            resolved = self.read("rev-parse", "--verify", revision + "^{commit}").decode("ascii").strip()
        except ReachTimeout:
            raise
        except ReachError as exc:
            raise ReachError(f"commit object {revision} unavailable: fetch that revision into the holder checkout "
                             f"or restore Git read capability and retry: {exc}") from exc
        if resolved.lower() != revision.lower():
            raise ReachError("incompatible commit endpoint: " + revision)
        return resolved

    def path(self, before, after):
        before, after = self.commit(before), self.commit(after)
        if before == after:
            return []
        rows = [row.split() for row in self.read(
            "rev-list", "--first-parent", "--parents", after, "^" + before).decode("ascii").splitlines()]
        if not rows or len(rows[-1]) < 2 or rows[-1][1] != before:
            raise ReachError("unexpected ancestry: before is not on after's first-parent path")
        return list(reversed(rows))

    def ancestor(self, before, after):
        self.commit(before)
        self.commit(after)
        try:
            self.path(before, after)
            return True
        except ReachError as exc:
            if str(exc).startswith("unexpected ancestry"):
                return False
            raise

    def _known(self, blob):
        if blob in self._binary:
            return self._binary[blob]
        opened = preflight.current()
        return opened.memo.get(self._key("binary", (blob,))) if opened is not None else None

    def _remember(self, blob, verdict):
        self._binary[blob] = verdict
        opened = preflight.current()
        if opened is not None:
            opened.memo[self._key("binary", (blob,))] = verdict

    def binary(self, blob):
        verdict = self._known(blob)
        if verdict is None:
            verdict = b"\0" in self.read("cat-file", "blob", blob.decode("ascii"))[:SNIFF_BYTES]
            self._remember(blob, verdict)
        return verdict

    def classify(self, blobs):
        """Learn every unknown blob's verdict through one `cat-file --batch`, one blob at a time.

        Design: lib/DESIGN.md#the-entrances-work-before-a-launch
        """
        wanted = list(dict.fromkeys(blob for blob in blobs if self._known(blob) is None))
        if not wanted:
            return
        _check_time()
        try:
            with seat_process.stream_read(["git", "-C", str(self.root), "cat-file", "--batch"], cwd=Path.cwd(),
                                          timeout=lifecycle.probe_timeout(READ_BOUND_SECONDS),
                                          cleanup_deadline=lifecycle.cleanup_deadline()) as stream:
                for blob in wanted:
                    try:
                        verdict = _batch_verdict(stream, blob)
                    except OSError:
                        # A pipe the bound closed is time running out, not a missing object.
                        stream.remaining()
                        raise
                    self._remember(blob, verdict)
        except seat_process.ContainmentRefused:
            # Without containment, `binary` reads each remaining blob alone through the read route.
            return
        except (TimeoutError, subprocess.TimeoutExpired) as exc:
            raise _timed_out(exc) from exc
        except (OSError, subprocess.SubprocessError) as exc:
            raise ReachError("restore local Git read capability and retry: " + str(exc)) from exc

    @contextmanager
    def _view(self):
        # One bare view per root serves a whole scope; outside a scope each read builds its own.
        opened = preflight.current()
        key = self._key("view", ())
        if opened is not None and key in opened.memo:
            yield opened.memo[key]
            return
        objects = self.read("rev-parse", "--path-format=absolute", "--git-path", "objects").rstrip(b"\r\n")
        object_format = self.read("rev-parse", "--show-object-format").strip()
        if opened is None:
            with tempfile.TemporaryDirectory(prefix="tradecraft-reach-") as directory:
                yield _build_view(Path(directory), objects, object_format)
            return
        directory = tempfile.mkdtemp(prefix="tradecraft-reach-")
        opened.on_close(lambda: shutil.rmtree(directory, ignore_errors=True))
        opened.memo[key] = _build_view(Path(directory), objects, object_format)
        yield opened.memo[key]

    def text_read(self, *args):
        # --text does not override binary attributes for numstat or combined
        # patches. An ephemeral bare view shares only the holder's objects:
        # no worktree/index/info attributes, and our rule overrides global or
        # system attributes. No objects or files in the checkout are written.
        memo = _memo_for(args)
        if memo is not None and self._key("text", args) in memo:
            return memo[self._key("text", args)]
        with self._view() as (view, attributes, tree):
            return self._read(args, "text", ("--git-dir=" + str(view), "--attr-source=" + tree, "-c",
                                             "core.bare=true", "-c", "core.attributesFile=" + str(attributes),
                                             *args))


DIFF_OPTIONS = ("--no-ext-diff", "--no-textconv", "--no-renames", "--no-color", "--text",
                "--diff-algorithm=myers", "--no-indent-heuristic", "--ignore-submodules=none")


def _path(raw):
    return raw.decode("utf-8", errors="surrogateescape")


def _item(path, deleted, added, removed, portion):
    return {"path": path, "deleted": deleted, "added": added, "removed": removed,
            "binary": added is None, "removed_test": test_path(path), "contributions": [portion]}


def _ordinary(git, before, after):
    status = git.read("diff", *DIFF_OPTIONS, "--raw", "--no-abbrev", "-z", before, after, "--").split(b"\0")
    numbers = git.text_read("diff", *DIFF_OPTIONS, "--numstat", "-z", before, after, "--").split(b"\0")
    if status[-1] != b"" or numbers[-1] != b"" or len(status[:-1]) % 2:
        raise ReachError("unsupported NUL-delimited diff inventory")
    counts = {}
    for row in numbers[:-1]:
        fields = row.split(b"\t", 2)
        if len(fields) != 3:
            raise ReachError("unsupported numeric diff record")
        added, removed, name = fields
        if added == removed == b"-":
            counts[_path(name)] = (None, None)
        elif added.isdigit() and removed.isdigit():
            counts[_path(name)] = (int(added), int(removed))
        else:
            raise ReachError("unavailable numeric diff counts")
    rows = []
    for index in range(0, len(status) - 1, 2):
        metadata, name = status[index:index + 2]
        fields = metadata.split()
        name = _path(name)
        if len(fields) != 5 or not fields[0].startswith(b":"):
            raise ReachError("unsupported raw diff inventory")
        kind = fields[-1]
        if kind not in {b"A", b"M", b"D", b"T"} or name not in counts:
            raise ReachError("incomplete diff inventory/counts: " + name)
        rows.append((name, kind, [fields[0].lstrip(b":"), fields[1]], fields[2:4]))
    # One batch learns every blob in this inventory, so processes do not grow with files.
    git.classify(blob for _name, _kind, modes, blobs in rows for blob in _content_blobs(modes, blobs))
    items = []
    for name, kind, modes, blobs in rows:
        binary = _binary_blobs(git, modes, blobs)
        numbers = counts.pop(name)
        items.append(_item(name, kind == b"D", *((None, None) if binary else numbers),
                           {"basis": "non-merge", "before": before, "after": after}))
    if counts:
        raise ReachError("numeric diff contains paths outside inventory")
    return items


def _content_blobs(modes, blobs):
    # Gitlinks are commit pointers, rather than blobs to read as file content.
    return [blob for mode, blob in zip(modes, blobs) if mode.startswith(b"100") or mode == b"120000"]


def _binary_blobs(git, modes, blobs):
    # Match Git's content heuristic, independently of attributes and drivers.
    return any(git.binary(blob) for blob in _content_blobs(modes, blobs))


def _combined_counts(section, parents):
    added = removed = 0
    remaining = None
    binary = False
    for line in section.split(b"\n")[1:]:
        if remaining is not None and any(remaining):
            if line.startswith(b"\\ No newline at end of file"):
                continue
            columns = line[:parents]
            if len(columns) != parents or any(c not in b" +-" for c in columns):
                raise ReachError("unsupported combined hunk columns")
            deletion = b"-" in columns
            consumed = ([c == ord("-") for c in columns] + [False] if deletion else
                        [c == ord(" ") for c in columns] + [True])
            remaining = [n - int(c) for n, c in zip(remaining, consumed)]
            if any(n < 0 for n in remaining):
                raise ReachError("combined hunk exceeds declared ranges")
            if columns == b"+" * parents:
                added += 1
            elif columns == b"-" * parents:
                removed += 1
        elif line.startswith(b"@" * (parents + 1) + b" "):
            pattern = rb"^" + b"@" * (parents + 1) + rb" ((?:-\d+(?:,\d+)? ){%d})\+\d+(?:,\d+)? " % parents
            match = re.match(pattern, line)
            if not match:
                raise ReachError("unsupported combined hunk header")
            ranges = re.findall(rb"[+-]\d+(?:,(\d+))?", line[:line.find(b" " + b"@" * (parents + 1))])
            if len(ranges) != parents + 1:
                raise ReachError("unsupported combined hunk ranges")
            remaining = [int(n) if n else 1 for n in ranges]
        elif line.startswith((b"Binary files ", b"GIT binary patch")):
            binary = True
    if remaining is not None and any(remaining):
        raise ReachError("incomplete combined patch hunk")
    return (None, None) if binary else (added, removed)


def _merge(git, revision, parents):
    raw = git.read("show", "--format=", "-c", "--raw", "--no-abbrev", "-z", *DIFF_OPTIONS, revision, "--")
    records = raw.split(b"\0")
    if records[-1] != b"" or len(records[:-1]) % 2:
        raise ReachError("unsupported combined raw inventory")
    inventory = []
    for index in range(0, len(records) - 1, 2):
        metadata, name = records[index:index + 2]
        fields = metadata.split()
        if (not metadata.startswith(b":" * len(parents)) or metadata.startswith(b":" * (len(parents) + 1))
                or len(fields) != 2 * (len(parents) + 1) + 1
                or len(fields[-1]) != len(parents) or any(c not in b"AMDT" for c in fields[-1])):
            raise ReachError("unsupported combined raw record")
        width = len(parents) + 1
        inventory.append((_path(name), fields[-1] == b"D" * len(parents),
                          [mode.lstrip(b":") for mode in fields[:width]], fields[width:2 * width]))
    git.classify(blob for _name, _deleted, modes, blobs in inventory for blob in _content_blobs(modes, blobs))
    inventory = [(name, deleted, _binary_blobs(git, modes, blobs)) for name, deleted, modes, blobs in inventory]
    patch = git.text_read("show", "--format=", "-c", "--patch", "--unified=3", "--inter-hunk-context=0",
                     *DIFF_OPTIONS, revision, "--")
    sections = re.split(rb"(?m)^diff --(?:combined|cc) ", patch)[1:]
    if len(sections) != len(inventory):
        raise ReachError("combined inventory and full patch disagree")
    return [_item(name, deleted, *((None, None) if binary else _combined_counts(section, len(parents))),
                  {"basis": "combined-all-parent-columns", "head": revision, "parents": parents})
            for (name, deleted, binary), section in zip(inventory, sections)]


def _aggregate(items, conservative=False, *, include_all=False):
    totals = {}
    candidates = set()
    for item in items:
        name = item["path"]
        if item["deleted"] or item["removed"] is not None and item["removed"] > 0:
            candidates.add(name)
        if name not in totals:
            totals[name] = {**item, "contributions": list(item["contributions"])}
            continue
        target = totals[name]
        target["deleted"] |= item["deleted"]
        target["binary"] |= item["binary"]
        for key in ("added", "removed"):
            target[key] = (target[key] + item[key] if target[key] is not None and item[key] is not None else None)
        target["contributions"].extend(item["contributions"])
    return [item for name, item in sorted(totals.items()) if include_all or
            item["deleted"] or (name in candidates if conservative else
            item["removed"] is not None and item["removed"] > item["added"])]


def measure(git, before, after, *, base=None, conservative=False, observations=None, existing_paths=None):
    """Prove the first-parent bounds, then measure every non-base authored branch."""
    git.path(before, after)
    arguments = ["rev-list", "--topo-order", "--reverse", "--parents", after, "^" + before]
    if base is not None:
        base = git.commit(base)
        arguments.append("^" + base)
    history = [row.split() for row in git.read(*arguments).decode("ascii").splitlines()]
    parents_by_id = {row[0]: row[1:] for row in history}
    children = {revision: [] for revision in parents_by_id}
    for revision, *parents in history:
        for parent in parents:
            if parent in children:
                children[parent].append(revision)
    items = []
    measured = set()
    for revision, *parents in history:
        if revision in measured:
            continue
        measured.add(revision)
        if len(parents) > 1:
            items.extend(_merge(git, revision, parents))
        elif len(parents) == 1:
            end = revision
            # Collapse a linear authored stretch, preserving endpoint net
            # counts and restoration/equality controls. Forks and merges are
            # boundaries so a shared contribution is never visited twice.
            while not conservative and len(children[end]) == 1:
                child = children[end][0]
                if len(parents_by_id[child]) != 1:
                    break
                measured.add(child)
                end = child
            items.extend(_ordinary(git, parents[0], end))
        else:
            raise ReachError("incomplete authored turn ancestry; restore commit objects and retry")
    if observations is not None:
        observations.extend(_aggregate(items, include_all=True))
    flags = _aggregate(items, conservative)
    return [item for item in flags if existing_paths is None or item["path"] in existing_paths]


def _pr_bounds(git, pr, *, head=None):
    if not pr or type(pr.get("number")) is not int:
        raise ReachError("open the draft implementing PR through the holder's existing route before superset settlement")
    resolved = {}
    for bound in ("base", "head"):
        value = (pr.get(bound) or {}).get("sha")
        try:
            resolved[bound] = git.commit(value)
        except ReachTimeout:
            raise
        except ReachError as exc:
            raise ReachError(f"PR #{pr['number']} requires {bound} object {value}: {exc}") from exc
    base, current_head = resolved["base"], resolved["head"]
    head = git.commit(head) if head is not None else current_head
    if not git.ancestor(head, current_head):
        raise ReachError("stale superset PR/head; record a new current-head account")
    common = git.read("merge-base", "--all", base, head).decode("ascii").splitlines()
    if len(common) != 1:
        raise ReachError("ambiguous PR merge base; resolve PR bounds before superset settlement")
    return {"pull_request": pr["number"], "base": base, "merge_base": common[0], "head": head,
            "basis": "pr-superset"}


def _existing_paths(git, revision):
    # NUL-delimited tree names retain empty/binary files and exact case/bytes.
    names = git.read("ls-tree", "--full-tree", "-r", "--name-only", "-z", revision, "--")
    if names and not names.endswith(b"\0"):
        raise ReachError("incomplete merge-base path inventory; restore Git read capability and retry")
    return {_path(name) for name in names.split(b"\0") if name}


def superset(git, pr, *, head=None):
    bounds = _pr_bounds(git, pr, head=head)
    existing = _existing_paths(git, bounds["merge_base"])
    head = bounds["head"]
    # The PR merge base may be a merge's other parent. Unlike a true turn
    # range, this superset traverses every non-base authored contribution,
    # and measures each non-merge against its own parent before taking a union.
    history = git.read("rev-list", "--topo-order", "--reverse", "--parents", head,
                       "^" + bounds["merge_base"]).decode("ascii").splitlines()
    items = []
    for row in history:
        revision, *parents = row.split()
        if len(parents) > 1:
            items.extend(_merge(git, revision, parents))
        elif len(parents) == 1:
            items.extend(_ordinary(git, parents[0], revision))
        else:
            raise ReachError("incomplete PR superset ancestry; restore commit objects and retry")
    return {**bounds, "items": [item for item in _aggregate(items, conservative=True)
                                if item["path"] in existing]}


def diagnostic(bundle):
    return "bundle:" + hashlib.sha256(str(bundle).encode("utf-8")).hexdigest()


def never_launched(record):
    attempts = record.get("attempts")
    return bool(isinstance(attempts, list) and attempts
                and all(isinstance(a, dict) and a.get("launched") is False for a in attempts)
                and record.get("completed_at") and not record.get("launch_unresolved")
                and not record.get("recovery_error"))


def _coverage(items, expected, turns, entry, reading, git, current_head):
    if {item["path"] for item in items} != {item["path"] for item in expected}:
        raise ReachError("missing or extraneous reach path coverage for " + entry["turn_reference"])
    for item in items:
        if item["disposition"] == "own-turn":
            earlier = [turn for turn in turns if turn["dispatch_id"] == item["added_by"]]
            launched = moment(entry["order"])
            if (len(earlier) != 1 or earlier[0]["pending"] or earlier[0]["uncertainty"]
                    or not earlier[0]["attribution_proved"] or launched is None
                    or moment(earlier[0]["order"]) is None or moment(earlier[0]["order"]) >= launched
                    or moment(earlier[0]["returned"]) is None or moment(earlier[0]["returned"]) > launched
                    or not any(addition["path"] == item["path"] and addition["added"] > 0
                               for addition in earlier[0]["authored_additions"])):
                raise ReachError("own-turn must name an earlier returned builder turn with authored additions to this path")
        if item["disposition"] != "restored":
            continue
        ref = item["restored_by"]
        later = [turn for turn in turns if turn["dispatch_id"] == ref["dispatch_id"]]
        if (len(later) != 1 or not later[0]["returned"] or later[0]["pending"]
                or not later[0]["attribution_proved"]
                or later[0]["after"] != ref["head"] or later[0]["order"] <= entry["order"]
                or moment(reading.timestamp) is None
                or moment(later[0]["returned"]) is None
                or moment(reading.timestamp) <= moment(later[0]["returned"])):
            raise ReachError("restoration does not name a later returned builder turn")
        if not git.ancestor(ref["head"], current_head):
            raise ReachError("restoration head is outside the selected current lineage")


def evaluate(turns, readings, *, root, head, pr, run, lineage=None, instalment=None):
    """Measure PR-selected turns using only the holder's repository objects."""
    return _evaluate(turns, readings, root=root, head=head, pr=pr, run=run,
                     lineage=lineage, instalment=instalment)


def uncertainty(reason, readings, *, root, head, pr, run, lineage=None, instalment=None):
    """A failed inventory/evaluator is itself a named, settleable PR uncertainty."""
    reference = "reach-evaluation:" + hashlib.sha256(reason.encode("utf-8")).hexdigest()
    turn = ("unknown", reference, {}, {"recovery_error": reason}, reason, False)
    return _evaluate([turn], readings, root=root, head=head, pr=pr, run=run,
                     lineage=lineage, instalment=instalment)


def _evaluate(turns, readings, *, root, head, pr, run, lineage=None, instalment=None):
    report = {"schema_version": 1, "state": "not-due", "current_head": head,
              "lineage": lineage, "instalment": instalment, "turns": [], "diagnostics": []}
    entries = report["turns"]
    orders = [turn[0] for turn in turns]
    baseline = None
    for order, bundle, request, record, target_error, pending in turns:
        request = request if isinstance(request, dict) else {}
        record = record if isinstance(record, dict) else {"recovery_error": "malformed run record"}
        if never_launched(record):
            continue
        identity = request.get("dispatch_id")
        identity = identity if _nonempty(identity) else None
        entry = {"dispatch_id": identity, "turn_reference": identity or diagnostic(bundle),
                 "stage": request.get("stage"), "bundle": bundle, "order": order,
                 "before": request.get("revision_before"), "after": record.get("revision_after"),
                 "returned": record.get("completed_at") or (order if not pending else None),
                 "return_basis": "recorded-return" if record.get("completed_at") else "historical-launch",
                 "pending": pending, "basis": "recorded-range",
                 "state": "pending" if pending else "unmeasurable", "items": [],
                 "binary_modifications": [], "authored_additions": [], "attribution_proved": not target_error and request.get("stage") in {"build", "floor", "review-disposition"},
                 "uncertainty": None, "reading_source": None, "outstanding_paths": []}
        entries.append(entry)
        error = target_error or record.get("recovery_error")
        if not error and (orders.count(order) > 1 or moment(order) is None or order.startswith("9999-")):
            error = "ambiguous or unavailable turn ordering"
        if not error and record.get("completed_at") and moment(entry["returned"]) is not None and moment(entry["returned"]) <= moment(order):
            error = "invalid launch/return ordering"
        if not error and record.get("completed_at") and moment(entry["returned"]) is None:
            error = "invalid return timestamp"
        if not error and not identity:
            error = "missing dispatch attribution"
        try:
            if error:
                raise ReachError(str(error))
            git = Git(root, run)
            if baseline is None:
                bounds = _pr_bounds(git, pr)
                baseline = _existing_paths(git, bounds["merge_base"])
                report["merge_base"] = bounds["merge_base"]
            observations = []
            entry["items"] = measure(git, entry["before"], entry["after"],
                                     base=(pr.get("base") or {}).get("sha") if pr else None,
                                     observations=observations, existing_paths=baseline)
            entry["authored_additions"] = [{"path": item["path"], "added": item["added"],
                                            "contributions": item["contributions"]}
                                           for item in observations if item["added"] is not None and item["added"] > 0]
            entry["binary_modifications"] = [item for item in observations if item["binary"] and not item["deleted"]]
            if head and not git.ancestor(entry["after"], head):
                raise ReachError("unexpected ancestry: returned head was rebased/amended away from current head")
            entry["state"] = "pending" if pending else "reading-required" if entry["items"] else "clear"
        except Exception as exc:
            entry["uncertainty"] = f"{type(exc).__name__}: {exc}"
            entry["items"] = []
            entry["authored_additions"] = []
    # Missing historical evidence is one PR-level obligation. Every diagnostic
    # names its own turn, but all use the same current-head conservative account.
    fallback = None
    fallback_error = None
    if any(entry["uncertainty"] and not entry["pending"] for entry in entries):
        try:
            fallback = superset(Git(root, run), pr)
            report["superset"] = fallback
        except Exception as exc:
            fallback_error = f"{type(exc).__name__}: {exc}"
            report["superset_error"] = fallback_error
    for entry in entries:
        if entry["uncertainty"] and not entry["pending"]:
            if fallback is not None:
                entry["superset"] = fallback
            else:
                entry["superset_error"] = fallback_error
    for reading in readings:
        try:
            value = payload(reading.body)
            reading_head = reading.attributes["head"]
            if root is None or not head or not Git(root, run).ancestor(reading_head, head):
                raise ReachError("stale or unavailable reach-reading head")
            by_id = {entry["dispatch_id"]: entry for entry in entries if entry["dispatch_id"]}
            by_ref = {entry["turn_reference"]: entry for entry in entries}
            ordinary_ids = {item["dispatch_id"] for item in value["turns"]}
            fallback_ids = {item["turn_reference"] for item in value["superset_settlements"]}
            if ordinary_ids - by_id.keys() or fallback_ids - by_ref.keys():
                raise ReachError("extraneous or unknown reach turn reference")
            if any(by_id[key]["turn_reference"] in fallback_ids for key in ordinary_ids):
                raise ReachError("duplicate ordinary and superset turn coverage")
            changes = {}
            for account in value["turns"]:
                original = by_id[account["dispatch_id"]]
                entry = changes.get(original["turn_reference"], original)
                if entry["pending"] or entry["uncertainty"]:
                    raise ReachError("ordinary account cannot settle an unmeasurable or pending turn")
                if not Git(root, run).ancestor(entry["after"], reading_head):
                    raise ReachError("reading head must be a covered flagged head or initial current-head account")
                git = Git(root, run)
                # Reconstruct the baseline at the account's head. Later base
                # progress can remove current flags, but cannot turn an old
                # complete account into an extraneous one (or a partial one
                # into complete coverage).
                bounds = _pr_bounds(git, pr, head=reading_head)
                expected = measure(git, entry["before"], entry["after"], base=bounds["merge_base"],
                                   existing_paths=_existing_paths(git, bounds["merge_base"]))
                if not expected:
                    raise ReachError("extraneous flag-free ordinary turn account")
                _coverage(account["items"], expected, entries, entry, reading, git, head)
                changes[entry["turn_reference"]] = {**entry, "accepted_items": account["items"]}
            if value["superset_settlements"]:
                git = Git(root, run)
                # Descendant progress retains an account only while it has no
                # later returned uncertainty. There are no per-turn recovered
                # ranges, neighboring bounds, or historical base snapshots.
                if reading_head != head:
                    posted = moment(reading.timestamp)
                    for entry in entries:
                        if not entry["uncertainty"] or entry["pending"]:
                            continue
                        returned = moment(entry["returned"])
                        if returned is None or posted is None or returned >= posted:
                            raise ReachError("later or undated unmeasurable turn needs a new current-head superset account")
                    # The PR suffix must be explained by later measured turns.
                    # This proves descendant progress without reconstructing any
                    # uncertain turn or trusting an arbitrary old empty head.
                    suffix = {row[0] for row in git.path(reading_head, head)}
                    if any(entry["uncertainty"] and isinstance(entry["after"], str)
                           and entry["after"].lower() in suffix for entry in entries):
                        raise ReachError("unmeasurable return is after the superset head; record a current-head account")
                    measured = set()
                    for entry in entries:
                        launched = moment(entry["order"])
                        if (not entry["uncertainty"] and not entry["pending"]
                                and launched is not None and posted is not None and launched > posted):
                            measured.update(row[0] for row in git.path(entry["before"], entry["after"]))
                    if suffix - measured:
                        raise ReachError("PR progress after the superset head is not covered by later measured turns; record a current-head account")
                accepted_fallback = superset(git, pr, head=reading_head)
            for account in value["superset_settlements"]:
                entry = by_ref[account["turn_reference"]]
                if not entry["uncertainty"] or entry["pending"]:
                    raise ReachError("superset settlement needs a returned unmeasurable turn")
                if account["head"] != reading_head:
                    raise ReachError("superset head must match marker head")
                if any(account[key] != accepted_fallback[key] for key in ("pull_request", "base", "merge_base", "head")):
                    raise ReachError("superset bounds must match the actual PR base, merge base and account head")
                _coverage(account["items"], accepted_fallback["items"], entries, entry, reading, Git(root, run), head)
                changes[entry["turn_reference"]] = {**entry, "basis": "pr-superset",
                                                       "superset": accepted_fallback, "accepted_items": account["items"]}
            for key, entry in changes.items():
                if (moment(reading.timestamp) is None or
                        moment(entry["returned"]) is not None and moment(reading.timestamp) <= moment(entry["returned"])):
                    raise ReachError("reach reading must follow the builder return")
                entry["state"] = "clear"
                entry["reading_source"] = reading.as_dict()
            # Validate the whole claim before accepting any part of it.
            for index, entry in enumerate(entries):
                if entry["turn_reference"] in changes:
                    entries[index] = changes[entry["turn_reference"]]
        except Exception as exc:
            report["diagnostics"].append({"source": reading.as_dict(), "reason": str(exc)})
    for entry in entries:
        entry["outstanding_paths"] = ([item["path"] for item in entry["items"]]
                                      if entry["state"] != "clear" else [])
    states = {entry["state"] for entry in entries}
    report["state"] = next((state for state in ("pending", "unmeasurable", "reading-required", "clear")
                            if state in states), "not-due")
    return report
