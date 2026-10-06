"""Measure committed builder contributions and enforce explicit holder accounts."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess


SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z", re.I)
PRESERVATION = (
    "Remove or rewrite existing content only where a governing row or criterion requires it; "
    "keep the rest, and name in your return any additional removal or rewrite you recommend."
)
REFERENCES = {"row-or-criterion": "requirement", "generator": "generator",
              "restored": "restored_by", "owner-ruling": "ruling_source"}


class ReachError(ValueError):
    """Evidence cannot establish reach; the holder must restore or settle it."""


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
    blocks = re.findall(r"(?m)^```json[ \t]*\r?\n([\s\S]*?)^```[ \t]*$", body)
    if len(blocks) != 1:
        raise ReachError("reach reading needs exactly one fenced JSON object")
    try:
        value = json.loads(blocks[0], object_pairs_hook=_unique_object)
    except (ValueError, TypeError) as exc:
        raise ReachError("invalid reach reading JSON: " + str(exc)) from exc
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int
            or value["schema_version"] != 1 or "turns" not in value
            or set(value) - {"schema_version", "turns", "recovered_ranges", "superset_settlements"}):
        raise ReachError("invalid reach reading schema")
    shapes = {
        "turns": ({"dispatch_id", "items"}, "dispatch_id"),
        "recovered_ranges": ({"dispatch_id", "before", "after", "basis"}, "dispatch_id"),
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
            if name != "recovered_ranges":
                _items(entry["items"])
            else:
                if not _nonempty(entry["basis"]):
                    raise ReachError("recovered range needs its contemporaneous evidence basis")
                for field in ("before", "after"):
                    if not isinstance(entry[field], str) or not SHA.fullmatch(entry[field]):
                        raise ReachError("recovered range needs full endpoints")
            if name == "superset_settlements":
                if (entry["basis"] != "pr-superset" or not _nonempty(entry["reason"])
                        or type(entry["pull_request"]) is not int or entry["pull_request"] <= 0
                        or any(not isinstance(entry[f], str) or not SHA.fullmatch(entry[f])
                               for f in ("base", "merge_base", "head"))):
                    raise ReachError("superset settlement needs exact PR bounds and reason")
    return value


class Git:
    """Read-only Git with the entrance's bounded subprocess adapter."""

    def __init__(self, root, run):
        self.root, self.run = Path(root), run

    def read(self, *args, missing_ok=False):
        try:
            result = self.run(["-c", "core.quotePath=true", *args], self.root)
        except (OSError, TimeoutError, subprocess.SubprocessError) as exc:
            raise ReachError("restore local Git read capability and retry: " + str(exc)) from exc
        # Only quiet revision verification uses status 1 for an absent object.
        # Fatal Git/read errors still name their evidence repair.
        if missing_ok and result.returncode == 1:
            return None
        if result.returncode:
            reason = result.stderr.decode("utf-8", errors="replace").strip()
            raise ReachError("restore required Git objects/read capability and retry: " + reason)
        return result.stdout

    def commit(self, revision):
        if not isinstance(revision, str) or not SHA.fullmatch(revision):
            raise ReachError("missing or invalid full commit endpoint: " + str(revision))
        resolved = self.read("rev-parse", "--verify", revision + "^{commit}").decode("ascii").strip()
        if resolved.lower() != revision.lower():
            raise ReachError("incompatible commit endpoint: " + revision)
        return resolved

    def path(self, before, after):
        before, after = self.commit(before), self.commit(after)
        rows = self.read("rev-list", "--first-parent", "--parents", after).decode("ascii").splitlines()
        result = []
        for row in rows:
            fields = row.split()
            if fields[0] == before:
                return list(reversed(result))
            result.append(fields)
        raise ReachError("unexpected ancestry: before is not on after's first-parent path")

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


DIFF_OPTIONS = ("--no-ext-diff", "--no-textconv", "--no-renames", "--no-color",
                "--diff-algorithm=myers", "--no-indent-heuristic", "--ignore-submodules=none")


def _path(raw):
    return raw.decode("utf-8", errors="surrogateescape")


def _item(path, deleted, added, removed, portion):
    return {"path": path, "deleted": deleted, "added": added, "removed": removed,
            "binary": added is None, "removed_test": test_path(path), "contributions": [portion]}


def _ordinary(git, before, after):
    status = git.read("diff", *DIFF_OPTIONS, "--name-status", "-z", before, after, "--").split(b"\0")
    numbers = git.read("diff", *DIFF_OPTIONS, "--numstat", "-z", before, after, "--").split(b"\0")
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
    items = []
    for index in range(0, len(status) - 1, 2):
        kind, name = status[index:index + 2]
        name = _path(name)
        if kind not in {b"A", b"M", b"D", b"T"} or name not in counts:
            raise ReachError("incomplete diff inventory/counts: " + name)
        items.append(_item(name, kind == b"D", *counts.pop(name),
                           {"basis": "non-merge", "before": before, "after": after}))
    if counts:
        raise ReachError("numeric diff contains paths outside inventory")
    return items


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
        inventory.append((_path(name), fields[-1] == b"D" * len(parents)))
    patch = git.read("show", "--format=", "-c", "--patch", "--unified=3", "--inter-hunk-context=0",
                     *DIFF_OPTIONS, revision, "--")
    sections = re.split(rb"(?m)^diff --(?:combined|cc) ", patch)[1:]
    if len(sections) != len(inventory):
        raise ReachError("combined inventory and full patch disagree")
    return [_item(name, deleted, *_combined_counts(section, len(parents)),
                  {"basis": "combined-all-parent-columns", "head": revision, "parents": parents})
            for (name, deleted), section in zip(inventory, sections)]


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


def measure(git, before, after, *, conservative=False, observations=None):
    """Partition first-parent history; never measure a merge against one parent."""
    history = git.path(before, after)
    items = []
    start = end = before
    for fields in history:
        revision, *parents = fields
        if len(parents) > 1:
            if start != end:
                items.extend(_ordinary(git, start, end))
            items.extend(_merge(git, revision, parents))
            start = end = revision
        elif conservative:
            items.extend(_ordinary(git, end, revision))
            start = end = revision
        else:
            end = revision
    if start != end:
        items.extend(_ordinary(git, start, end))
    if observations is not None:
        observations.extend(_aggregate(items, include_all=True))
    return _aggregate(items, conservative)


def superset(git, pr, *, bounds=None):
    if not pr or type(pr.get("number")) is not int:
        raise ReachError("open the draft implementing PR through the holder's existing route before superset settlement")
    resolved = {}
    for bound in ("base", "head"):
        value = (pr.get(bound) or {}).get("sha")
        try:
            resolved[bound] = git.commit(value)
        except ReachError as exc:
            raise ReachError(f"PR #{pr['number']} requires {bound} object {value}: {exc}") from exc
    current_base, current_head = resolved["base"], resolved["head"]
    base, head = current_base, current_head
    if bounds is not None:
        if bounds["pull_request"] != pr["number"] or not git.ancestor(bounds["head"], current_head):
            raise ReachError("stale superset PR/head; record a new current-head account")
        # Base progress retains an earlier account; a replacement ancestry does not.
        if not git.ancestor(bounds["base"], current_base):
            raise ReachError("superset base ancestry changed; record a new current-head account")
        base, head = git.commit(bounds["base"]), git.commit(bounds["head"])
    common = git.read("merge-base", "--all", base, head).decode("ascii").splitlines()
    if len(common) != 1:
        raise ReachError("ambiguous PR merge base; resolve PR bounds before superset settlement")
    if bounds is not None and common[0] != bounds["merge_base"]:
        raise ReachError("superset merge-base bounds mismatch")
    # The PR merge base may be a merge's other parent. Unlike a true turn
    # range, this superset traverses every non-base authored contribution,
    # and measures each non-merge against its own parent before taking a union.
    history = git.read("rev-list", "--topo-order", "--reverse", "--parents", head,
                       "^" + common[0]).decode("ascii").splitlines()
    items = []
    for row in history:
        revision, *parents = row.split()
        if len(parents) > 1:
            items.extend(_merge(git, revision, parents))
        elif len(parents) == 1:
            items.extend(_ordinary(git, parents[0], revision))
        else:
            raise ReachError("incomplete PR superset ancestry; restore commit objects and retry")
    return {"pull_request": pr["number"], "base": base, "merge_base": common[0], "head": head,
            "basis": "pr-superset", "items": _aggregate(items, conservative=True)}


def diagnostic(bundle):
    return "bundle:" + hashlib.sha256(str(bundle).encode("utf-8")).hexdigest()


def _known_commit(git, revision):
    if not isinstance(revision, str) or not SHA.fullmatch(revision):
        return None
    resolved = git.read("rev-parse", "--verify", "--quiet", revision + "^{commit}", missing_ok=True)
    if resolved is None:
        return None
    resolved = resolved.decode("ascii").strip()
    return resolved if resolved.lower() == revision.lower() else None


def _neighbors(entry, entries):
    ordered = [other for other in entries if other["attribution_proved"]
               and moment(other["order"]) is not None and other is not entry]
    previous = [other for other in ordered if moment(other["order"]) < moment(entry["order"])]
    following = [other for other in ordered if moment(other["order"]) > moment(entry["order"])]
    return (max(previous, key=lambda other: moment(other["order"]), default=None),
            min(following, key=lambda other: moment(other["order"]), default=None))


def _recovered_range(git, entry, recovered, entries):
    before, after = git.commit(recovered["before"]), git.commit(recovered["after"])
    known = {bound: _known_commit(git, entry[bound]) for bound in ("before", "after")}
    for bound, revision in known.items():
        if revision is not None and revision != {"before": before, "after": after}[bound]:
            raise ReachError("range recovery cannot replace valid recorded " + bound + " endpoint")
    if (moment(entry["order"]) is None or moment(entry["returned"]) is None
            or moment(entry["returned"]) <= moment(entry["order"])):
        raise ReachError("range recovery needs proved launch/return ordering; use PR superset")
    previous, following = _neighbors(entry, entries)
    prior_end = _known_commit(git, previous["after"]) if previous else None
    next_start = _known_commit(git, following["before"]) if following else None
    if prior_end and not git.ancestor(prior_end, before):
        raise ReachError("recovered before overlaps or precedes the previous builder turn")
    if next_start and not git.ancestor(after, next_start):
        raise ReachError("recovered after overlaps or follows the next builder turn")
    if before == after and ((known["before"] or prior_end) != before
                            or (known["after"] or next_start) != after):
        raise ReachError("empty recovered range needs independently recorded start and end evidence; use PR superset")
    return measure(git, before, after)


def _superset_covers_turn(git, entry, entries, account_head, current_head):
    # A current-head superset also settles replaced or unavailable old objects.
    if account_head == current_head:
        return
    endpoint = _known_commit(git, entry["after"])
    if endpoint is None:
        # A subsequent attributed launch bounds a return whose endpoint was lost.
        _previous, following = _neighbors(entry, entries)
        endpoint = _known_commit(git, following["before"]) if following else None
    if endpoint is None or not git.ancestor(endpoint, account_head):
        raise ReachError("superset head does not cover this turn's return; record a current-head account")


def _coverage(items, expected, turns, entry, reading, git, current_head):
    if {item["path"] for item in items} != {item["path"] for item in expected}:
        raise ReachError("missing or extraneous reach path coverage for " + entry["turn_reference"])
    for item in items:
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


def evaluate(turns, readings, *, head, pr, run, lineage=None, instalment=None):
    """Turns carry target errors separately from delivery-success checks."""
    report = {"schema_version": 1, "state": "not-due", "current_head": head,
              "lineage": lineage, "instalment": instalment, "turns": [], "diagnostics": []}
    entries = report["turns"]
    orders = [turn[0] for turn in turns]
    for order, bundle, request, record, target_error, pending in turns:
        attempts = record.get("attempts")
        if (isinstance(attempts, list) and attempts
                and all(isinstance(a, dict) and a.get("launched") is False for a in attempts)
                and record.get("completed_at") and not record.get("launch_unresolved")
                and not record.get("recovery_error")):
            continue
        identity = request.get("dispatch_id")
        entry = {"dispatch_id": identity, "turn_reference": identity or diagnostic(bundle),
                 "stage": request.get("stage"), "bundle": bundle, "order": order,
                 "before": request.get("revision_before"), "after": record.get("revision_after"),
                 "returned": record.get("completed_at") or record.get("reach_resolved_at"),
                 "resolved_by": record.get("reach_resolved_by"), "pending": pending, "basis": "recorded-range",
                 "state": "pending" if pending else "unmeasurable", "items": [],
                 "binary_modifications": [], "attribution_proved": not target_error and request.get("stage") in {"build", "floor", "review-disposition"},
                 "uncertainty": None, "reading_source": None, "outstanding_paths": []}
        entries.append(entry)
        error = target_error or record.get("recovery_error")
        if not error and (orders.count(order) > 1 or moment(order) is None or order.startswith("9999-")):
            error = "ambiguous or unavailable turn ordering"
        if not error and moment(entry["returned"]) is not None and moment(entry["returned"]) <= moment(order):
            error = "invalid launch/return ordering"
        if not error and (not identity or not entry["returned"] or moment(entry["returned"]) is None
                          or not isinstance(attempts, list) or not any(a.get("launched") is True for a in attempts if isinstance(a, dict))):
            error = "incomplete records or missing dispatch/launch/return attribution"
        try:
            if error:
                raise ReachError(str(error))
            git = Git(request["root"], run)
            observations = []
            entry["items"] = measure(git, entry["before"], entry["after"], observations=observations)
            entry["binary_modifications"] = [item for item in observations if item["binary"] and not item["deleted"]]
            if head and not git.ancestor(entry["after"], head):
                raise ReachError("unexpected ancestry: returned head was rebased/amended away from current head")
            entry["state"] = "pending" if pending else "reading-required" if entry["items"] else "clear"
        except (ReachError, OSError, ValueError, KeyError) as exc:
            entry["uncertainty"] = str(exc)
    # A missing recipient root may still settle through the selected PR's proved repository.
    root = (lineage or {}).get("root") if isinstance(lineage, dict) else None
    if root is None:
        root = next((turn[2].get("root") for turn in turns if turn[2].get("root")), None)
    for entry in entries:
        if entry["uncertainty"] and not entry["pending"]:
            try:
                if root is None:
                    raise ReachError("restore the selected implementation repository attribution for PR superset reads")
                entry["superset"] = superset(Git(root, run), pr)
            except (ReachError, OSError, ValueError) as exc:
                entry["superset_error"] = str(exc)
    for reading in readings:
        try:
            value = payload(reading.body)
            reading_head = reading.attributes["head"]
            if root is None or not head or not Git(root, run).ancestor(reading_head, head):
                raise ReachError("stale or unavailable reach-reading head")
            by_id = {entry["dispatch_id"]: entry for entry in entries if entry["dispatch_id"]}
            by_ref = {entry["turn_reference"]: entry for entry in entries}
            ordinary_ids = {item["dispatch_id"] for item in value["turns"]}
            recovery_ids = {item["dispatch_id"] for item in value["recovered_ranges"]}
            fallback_ids = {item["turn_reference"] for item in value["superset_settlements"]}
            if ordinary_ids - by_id.keys() or recovery_ids - by_id.keys() or fallback_ids - by_ref.keys():
                raise ReachError("extraneous or unknown reach turn reference")
            if any(by_id[key]["turn_reference"] in fallback_ids for key in ordinary_ids | recovery_ids):
                raise ReachError("duplicate ordinary/recovered and superset turn coverage")
            changes = {}
            for recovered in value["recovered_ranges"]:
                entry = by_id[recovered["dispatch_id"]]
                if not entry["uncertainty"] or entry["pending"]:
                    raise ReachError("range recovery cannot replace a measurable range or live recovery")
                original = next(turn for turn in turns if turn[2].get("dispatch_id") == entry["dispatch_id"])
                if original[4] or "ordering" in entry["uncertainty"] or "attribution" in entry["uncertainty"]:
                    raise ReachError("true-range recovery still needs proved lineage, ordering and attribution; use PR superset")
                git = Git(original[2]["root"], run)
                measured = _recovered_range(git, entry, recovered, entries)
                if not git.ancestor(recovered["after"], head):
                    raise ReachError("recovered head is outside current lineage")
                changes[entry["turn_reference"]] = {**entry, "before": recovered["before"], "after": recovered["after"],
                                                       "basis": "recovered-range", "recovery_basis": recovered["basis"],
                                                       "items": measured}
                if measured and entry["dispatch_id"] not in ordinary_ids:
                    raise ReachError("recovered flags need complete ordinary turn coverage")
            for account in value["turns"]:
                original = by_id[account["dispatch_id"]]
                entry = changes.get(original["turn_reference"], original)
                if entry["pending"] or entry["uncertainty"] and entry["basis"] != "recovered-range":
                    raise ReachError("ordinary account cannot settle an unmeasurable or pending turn")
                if not entry["items"]:
                    raise ReachError("extraneous flag-free ordinary turn account")
                if not Git(root, run).ancestor(entry["after"], reading_head):
                    raise ReachError("reading head must be a covered flagged head or initial current-head account")
                _coverage(account["items"], entry["items"], entries, entry, reading, Git(root, run), head)
                changes[entry["turn_reference"]] = {**entry, "accepted_items": account["items"]}
            for account in value["superset_settlements"]:
                entry = by_ref[account["turn_reference"]]
                if not entry["uncertainty"] or entry["pending"]:
                    raise ReachError("superset settlement needs a returned unmeasurable turn")
                if account["head"] != reading_head:
                    raise ReachError("superset head must match marker head")
                _superset_covers_turn(Git(root, run), entry, entries, account["head"], head)
                fallback = superset(Git(root, run), pr, bounds=account)
                _coverage(account["items"], fallback["items"], entries, entry, reading, Git(root, run), head)
                changes[entry["turn_reference"]] = {**entry, "basis": "pr-superset",
                                                       "superset": fallback, "accepted_items": account["items"]}
            for key, entry in changes.items():
                if (moment(reading.timestamp) is None or moment(entry["returned"]) is None
                        or moment(reading.timestamp) <= moment(entry["returned"])):
                    raise ReachError("reach reading must follow the builder return")
                entry["state"] = "clear"
                entry["reading_source"] = reading.as_dict()
            # Validate the whole claim before accepting any part of it.
            for index, entry in enumerate(entries):
                if entry["turn_reference"] in changes:
                    entries[index] = changes[entry["turn_reference"]]
        except (ReachError, KeyError, TypeError, ValueError, OSError) as exc:
            report["diagnostics"].append({"source": reading.as_dict(), "reason": str(exc)})
    for entry in entries:
        entry["outstanding_paths"] = ([item["path"] for item in entry["items"]]
                                      if entry["state"] != "clear" else [])
    states = {entry["state"] for entry in entries}
    report["state"] = next((state for state in ("pending", "unmeasurable", "reading-required", "clear")
                            if state in states), "not-due")
    return report
