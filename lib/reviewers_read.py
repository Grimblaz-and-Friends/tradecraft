"""The release report's section on what the reviewers read: the head the pull request was first marked ready at.

It says which head that was, how long after the build began and after how many cold readings, whether a fix
was pushed before the last report on that head, whether the first cold reading followed the answers, and what
changed between that head and the one merged. Every part the entrance cannot read is unknown with its reason.

Design: lib/DESIGN.md#the-cold-reader
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import subprocess

import build_reach

# Committer dates are what a commit carries; when it was pushed is not on record, so the section names the basis.
COMPARED = "committer dates"
REVIEWERS_FIRST, COLD_READING_FIRST = "reviewers-first", "cold-reading-first"


def unknown(reason: str) -> dict:
    return {"status": "unknown", "reason": reason}


def _time(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.utcoffset() is not None else None


def _short(sha):
    return sha[:7] if isinstance(sha, str) else "an unknown commit"


def fetch_timeline(transport, repo: str, number: int) -> list[dict]:
    """The pull request's whole issue timeline; a read error propagates for the caller to make unknown."""
    endpoint = f"repos/{repo}/issues/{number}/timeline"
    events = transport.get(endpoint, paginate=True)
    if not isinstance(events, list):
        raise ValueError(f"GitHub returned a non-list for {endpoint}")
    return events


def ready_head(timeline) -> dict:
    """The head the pull request had when first marked ready: the last commit before its first ready event."""
    if not isinstance(timeline, list):
        return unknown("the pull request's timeline is unreadable")
    head = None
    for event in timeline:
        if not isinstance(event, dict):
            continue
        if event.get("event") == "committed" and isinstance(event.get("sha"), str):
            head = event["sha"]
        elif event.get("event") == "ready_for_review":
            if head is None:
                return unknown("no commit precedes the pull request's first ready-for-review event")
            if _time(event.get("created_at")) is None:
                return unknown("the pull request's first ready-for-review event has no readable time")
            return {"status": "read", "head": head, "ready_at": event["created_at"]}
    return unknown("the pull request has no ready-for-review event: it was never a draft, or is not yet marked ready")


def first_reviews(timeline, reviewers, counts=None) -> dict[str, dict]:
    """Each named reviewer's first submitted review, ``{login: {"commit", "at"}}``, keyed as the caller named it.

    ``counts(event)`` says whether a review event is a review at all; the entrance passes its own receipt rule, so a
    reviewer's notice that it skipped or is rate-limited is not taken for its look.
    """
    wanted = {name.casefold(): name for name in reviewers}
    found: dict[str, dict] = {}
    for event in timeline if isinstance(timeline, list) else ():
        if not isinstance(event, dict) or event.get("event") != "reviewed":
            continue
        if counts is not None and not counts(event):
            continue
        user = event.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        name = wanted.get(login.casefold()) if isinstance(login, str) else None
        if name is not None and name not in found:
            found[name] = {"commit": event.get("commit_id"), "at": event.get("submitted_at")}
    return found


def other_heads(ready: dict, reviews: dict[str, dict]) -> list[dict]:
    """Each reviewer whose first review names a commit other than the ready head, as ``{"reviewer", "commit"}``."""
    head = ready.get("head") if ready.get("status") == "read" else None
    return [{"reviewer": name, "commit": review.get("commit")} for name, review in reviews.items()
            if head is not None and review.get("commit") != head]


def _git_failure(root, old, new, result, run):
    for sha in (old, new):
        try:
            present = run(["cat-file", "-e", f"{sha}^{{commit}}"], root).returncode == 0
        except (OSError, TimeoutError, subprocess.TimeoutExpired):
            continue
        if not present:
            return f"commit {sha} is not in the holder's objects"
    diagnostic = result.stderr.decode("utf-8", errors="backslashreplace").strip()
    return f"git diff failed between {old} and {new}: {diagnostic or result.returncode}"


def _numstat_entries(output: bytes) -> list[dict]:
    tokens = output.split(b"\0")
    entries, index = [], 0
    while index < len(tokens) and tokens[index]:
        added, removed, path = tokens[index].split(b"\t", 2)
        index += 1
        source = None
        # Under -z a rename leaves the path empty and gives its old and new paths as the next two fields.
        if not path:
            source, path = tokens[index], tokens[index + 1]
            index += 2
        binary = added == b"-" and removed == b"-"
        entry = {"path": path.decode("utf-8", errors="backslashreplace"),
                 "added": None if binary else int(added), "removed": None if binary else int(removed)}
        if source is not None:
            entry["from"] = source.decode("utf-8", errors="backslashreplace")
        if binary:
            entry["binary"] = True
        entries.append(entry)
    return entries


def numstat(root: Path, old: str, new: str, *, run=None) -> dict:
    """The files and lines changed from ``old`` to ``new`` in the repository at ``root``, as Git counts them.

    ``run(command, root)`` is a Git read returning a completed process; the entrance's contained read by
    default. A binary file has no line counts and is left out of the totals.
    """
    run = run or build_reach.run_git
    ends = {"from": old, "to": new}
    command = ["diff", "--numstat", "-z", "-M", "--no-ext-diff", "--no-textconv", old, new, "--"]
    try:
        result = run(command, root)
    except (OSError, TimeoutError, subprocess.TimeoutExpired) as exc:
        return {**unknown(f"git could not be run in {root}: {exc}"), **ends}
    if result.returncode:
        return {**unknown(_git_failure(root, old, new, result, run)), **ends}
    try:
        files = _numstat_entries(result.stdout)
    except (ValueError, IndexError):
        return {**unknown(f"git diff --numstat output between {old} and {new} is unreadable"), **ends}
    counted = [entry for entry in files if not entry.get("binary")]
    return {"status": "read", **ends, "files": files, "added": sum(entry["added"] for entry in counted),
            "removed": sum(entry["removed"] for entry in counted), "nothing_changed": old == new or not files}


def _git_text(run, root, command):
    result = run(command, root)
    if result.returncode:
        diagnostic = result.stderr.decode("utf-8", errors="backslashreplace").strip()
        raise OSError(f"git {command[0]} failed: {diagnostic or result.returncode}")
    return result.stdout.decode("utf-8")


def _is_ancestor(run, root, ancestor: str, descendant: str) -> bool:
    # Git exits 1 for "not an ancestor" and otherwise only on an error, which leaves the answer unread, not false.
    result = run(["merge-base", "--is-ancestor", ancestor, descendant], root)
    if result.returncode not in (0, 1):
        diagnostic = result.stderr.decode("utf-8", errors="backslashreplace").strip()
        raise OSError(f"git merge-base --is-ancestor {ancestor} {descendant} failed: "
                      f"{diagnostic or result.returncode}")
    return result.returncode == 0


def _imports_only(run, root, sha: str) -> bool:
    """Whether a merge's every hunk came from one of its parents: its combined diff, which leaves those out, is empty.
    A merge carrying a change of its own, a hand-resolved conflict included, is the builder's and can be a fix."""
    return not _git_text(run, root, ["show", "--cc", "--format=", "--no-ext-diff", "--no-textconv", sha]).strip()


def commits_between(root: Path, old: str, new: str, base: str, *, run=None) -> dict:
    """The branch's own commits after ``old`` up to ``new``, oldest first, as ``section`` takes them.

    Each is ``{"sha", "committed_at", "base_merge"}``; a base merge is a merge whose other parent is already in
    ``base`` and that carries no change of its own. Only the first-parent line is read, so the base's own commits a
    catch-up brings in are not listed.
    """
    run = run or build_reach.run_git
    try:
        for sha in (old, new):
            if run(["cat-file", "-e", f"{sha}^{{commit}}"], root).returncode:
                return unknown(f"commit {sha} is not in the holder's objects")
        if not _is_ancestor(run, root, old, new):
            return unknown(f"{old} is not an ancestor of {new}: the branch's history was rewritten after it")
        listing = _git_text(run, root, ["log", "--no-show-signature", "--first-parent", "--reverse", "-z",
                                        "--format=%H%x09%cI%x09%P", f"{old}..{new}", "--"])
        commits = []
        for record in filter(None, listing.split("\0")):
            sha, committed_at, parents = record.strip("\n").split("\t")
            others = parents.split()[1:]
            # A merge whose other side the base already holds brings in the base, never a fix of the branch's own.
            merged = (bool(others) and all(_is_ancestor(run, root, parent, base) for parent in others)
                      and _imports_only(run, root, sha))
            commits.append({"sha": sha, "committed_at": committed_at, "base_merge": merged})
    except (OSError, TimeoutError, subprocess.TimeoutExpired, UnicodeError, ValueError) as exc:
        return unknown(f"the commits from {old} to {new} could not be read: {exc}")
    return {"status": "read", "commits": commits}


def _since_build_began(ready_at, build_began):
    if ready_at is None:
        return unknown("the head the reviewers read is unknown")
    if build_began is None:
        return unknown("no builder launch on record")
    began = _time(build_began)
    if began is None:
        return unknown(f"the first builder launch's time is unreadable: {build_began!r}")
    if began > ready_at:
        # The brief was affirmed again after the ready step, so the term's first launch can't date the build's start.
        return unknown(f"the term's first builder launch, {build_began}, came after the ready step")
    return {"status": "read", "seconds": round((ready_at - began).total_seconds())}


def _cold_readings_before(ready_at, cold_launches):
    if ready_at is None:
        return unknown("the head the reviewers read is unknown")
    if cold_launches is None:
        return unknown("the cold-reader launches for this pull request were not read")
    times = [_time(value) for value in cold_launches]
    if None in times:
        return unknown(f"a cold-reader launch time is unreadable: {cold_launches[times.index(None)]!r}")
    return {"status": "read", "count": sum(1 for when in times if when < ready_at)}


def _commit_list(commits):
    """The commit list, or the reason it is unknown; ``commits`` is a list, ``commits_between``'s answer or None."""
    if isinstance(commits, dict):
        if commits.get("status") == "read" and isinstance(commits.get("commits"), list):
            return commits["commits"], None
        return None, commits.get("reason") or "the commits after the head the reviewers read were not read"
    if isinstance(commits, list):
        return commits, None
    return None, "the commits after the head the reviewers read were not read"


def _fix_before_last_report(ready_at, commits, reports, unread_reports):
    def no_answer(reason):
        return {**unknown(reason), "compared": COMPARED}
    if ready_at is None:
        return no_answer("the head the reviewers read is unknown")
    commits, missing = _commit_list(commits)
    if missing:
        return no_answer(missing)
    unread = list(unread_reports) + [report.get("name") for report in reports if _time(report.get("at")) is None]
    timed = [(_time(report["at"]), report) for report in reports if _time(report.get("at")) is not None]
    fixes = [commit for commit in commits if not commit.get("base_merge")]
    if timed:
        last_at, last = max(timed, key=lambda pair: pair[0])
        # A merge bringing in the base answers no report, so only the builder's own commits can be a fix.
        for commit in fixes:
            when = _time(commit.get("committed_at"))
            if when is not None and when < last_at:
                return {"status": "read", "value": True, "commit": commit.get("sha"),
                        "last_report": {"name": last.get("name"), "at": last.get("at")}, "compared": COMPARED}
    if unread:
        return {**no_answer("no fix was found before the last report the entrance could read, and the entrance "
                            "cannot read " + ", ".join(str(name) for name in unread)), "unread": unread}
    if not timed:
        return no_answer("no report on that head is on record")
    undated = [commit.get("sha") for commit in fixes if _time(commit.get("committed_at")) is None]
    if undated:
        return no_answer(f"commit {undated[0]} has no readable committer date")
    return {"status": "read", "value": False, "commit": None,
            "last_report": {"name": last.get("name"), "at": last.get("at")}, "compared": COMPARED}


def _follows_answers(reading, ready, ready_at, launched, commits, reports, unread_reports):
    """Whether the first reading came after the fix batch: launched once every report on the ready head was in,
    on a head at or after each fix committed before its launch. A fix after the launch is the reading's own repair,
    since every report it could answer was already in."""
    if ready_at is None:
        return unknown("the head the reviewers read is unknown")
    if launched < ready_at:
        return {"status": "read", "value": False, "reason": "it precedes the ready step"}
    commits, missing = _commit_list(commits)
    if missing:
        return unknown(missing)
    unread = list(unread_reports) + [report.get("name") for report in reports if _time(report.get("at")) is None]
    if unread:
        return unknown("whether every report was in before it can't be told: the entrance cannot read "
                       + ", ".join(str(name) for name in unread))
    timed = [(_time(report["at"]), report) for report in reports]
    if not timed:
        return unknown("no report on that head is on record")
    last_at, last = max(timed, key=lambda pair: pair[0])
    if launched < last_at:
        return {"status": "read", "value": False,
                "reason": f"it was launched before the last report on that head, {last.get('name')}"}
    fixes = [commit for commit in commits if not commit.get("base_merge")]
    undated = [commit.get("sha") for commit in fixes if _time(commit.get("committed_at")) is None]
    if undated:
        return unknown(f"commit {undated[0]} has no readable committer date")
    answering = [commit for commit in fixes if _time(commit["committed_at"]) <= launched]
    if not answering:
        return {"status": "read", "value": True, "reason": "every report was in and none needed a fix"}
    order = [commit.get("sha") for commit in commits]
    head = reading.get("head")
    if head == ready["head"]:
        position = -1
    elif head in order:
        position = order.index(head)
    else:
        return unknown(f"its head {head} is neither the ready head nor a commit after it")
    last = answering[-1].get("sha")
    if position >= order.index(last):
        return {"status": "read", "value": True, "reason": f"it read {_short(head)}, at or after the last answer"}
    return {"status": "read", "value": False,
            "reason": f"it read {_short(head)}, before the answering commit {_short(last)}"}


def _first_reading(first_reading, ready, ready_at, commits, reports, unread_reports):
    if first_reading is None:
        return {"status": "none", "reason": "no cold reading has been launched for this pull request"}
    if first_reading.get("status") == "unknown":
        return first_reading
    head, launched = first_reading.get("head"), _time(first_reading.get("launched_at"))
    part = {"status": "read", "head": head, "launched_at": first_reading.get("launched_at")}
    if launched is None:
        return {**part, "follows_answers": unknown("the first cold reading's launch time is unreadable")}
    return {**part, "follows_answers": _follows_answers(first_reading, ready, ready_at, launched, commits, reports,
                                                        unread_reports)}


def _plural(count, word):
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _duration(seconds):
    hours = seconds / 3600
    return f"{hours:.1f} hours" if abs(hours) >= 1 else _plural(round(seconds / 60), "minute")


def _sentence(part) -> str:
    head, began, before = part["head"], part["since_build_began"], part["cold_readings_before"]
    clauses = []
    if head["status"] == "read":
        lead = f"The reviewers read {_short(head['commit'])}"
        others = [f"{item['reviewer']} read {_short(item['commit'])}" for item in part["other_reviewer_heads"]]
        if others:
            lead += f" ({', '.join(others)})"
        timing = []
        if began["status"] == "read":
            timing.append(f"{_duration(began['seconds'])} after the build began")
        if before["status"] == "read":
            timing.append(f"after {_plural(before['count'], 'cold reading')}")
        clauses.append(lead + (", " + " and ".join(timing) if timing else ""))
    else:
        clauses.append(f"Which head the reviewers read is unknown: {head['reason']}")
    if began["status"] != "read" and head["status"] == "read":
        clauses.append(f"how long after the build began is unknown: {began['reason']}")
    if before["status"] != "read" and head["status"] == "read":
        clauses.append(f"how many cold readings came before it is unknown: {before['reason']}")
    fix = part["fix_before_last_report"]
    if fix["status"] != "read":
        clauses.append(f"whether a fix came before the last report is unknown: {fix['reason']}")
    elif fix["value"]:
        clauses.append(f"a fix, {_short(fix['commit'])}, was pushed before the last report on that head "
                       f"(compared by {COMPARED})")
    else:
        clauses.append(f"no fix was pushed before the last report on that head (compared by {COMPARED})")
    reading = part["first_reading"]
    if reading["status"] == "none":
        clauses.append("no cold reading has been launched")
    elif reading["status"] == "unknown":
        clauses.append(f"the first cold reading is unknown: {reading['reason']}")
    else:
        follows = reading["follows_answers"]
        if follows["status"] != "read":
            clauses.append(f"whether the first cold reading followed the answers is unknown: {follows['reason']}")
        else:
            verb = "followed the answers" if follows["value"] else "did not follow the answers"
            clauses.append(f"the first cold reading, of {_short(reading['head'])}, {verb}: {follows['reason']}")
    changed = part["changed_after"]
    if not isinstance(changed, dict) or changed.get("status") != "read":
        reason = changed.get("reason") if isinstance(changed, dict) else None
        clauses.append(f"what changed after it is unknown: {reason or 'it was not read'}")
    elif changed["nothing_changed"]:
        clauses.append("nothing changed between it and the head you merge")
    else:
        binary = sum(1 for entry in changed["files"] if entry.get("binary"))
        clauses.append(f"{_plural(len(changed['files']), 'file')} and +{changed['added']}/-{changed['removed']} "
                       f"lines changed between it and {_short(changed.get('to'))}, the head you merge"
                       + (f" ({binary} binary)" if binary else ""))
    return "; ".join(clauses) + "."


def section(*, ready: dict, build_began: str | None, cold_launches: list[str] | None,
            commits: list[dict] | dict | None, reports: list[dict], unread_reports: list[str],
            first_reading: dict | None, changed_after: dict, other_reviewer_heads: list[dict]) -> dict:
    """The release report's section on what the reviewers read, every part read or unknown with its reason.

    ``ready`` is ``ready_head``'s answer; ``commits`` the commits after that head up to the report's head, oldest
    first, each ``{"sha", "committed_at", "base_merge"}``, or ``commits_between``'s answer; ``reports`` each owed
    report the entrance read as ``{"name", "at"}``; ``unread_reports`` the name of each owed report it cannot read;
    ``first_reading`` the first cold-reader launch's ``{"head", "launched_at"}``, None, or unknown; ``changed_after``
    ``numstat``'s answer.
    """
    read = isinstance(ready, dict) and ready.get("status") == "read"
    ready_at = _time(ready.get("ready_at")) if read else None
    head = ({"status": "read", "commit": ready["head"], "ready_at": ready["ready_at"]} if ready_at is not None
            else unknown(ready.get("reason") if isinstance(ready, dict) and ready.get("reason")
                         else "the head the reviewers read was not read"))
    if ready_at is None:
        ready = {}
    part = {
        "head": head,
        "other_reviewer_heads": list(other_reviewer_heads),
        "since_build_began": _since_build_began(ready_at, build_began),
        "cold_readings_before": _cold_readings_before(ready_at, cold_launches),
        "fix_before_last_report": _fix_before_last_report(ready_at, commits, reports, unread_reports),
        "first_reading": _first_reading(first_reading, ready, ready_at, commits, reports, unread_reports),
        "changed_after": changed_after,
    }
    return {**part, "sentence": _sentence(part)}


def order_of(part: dict) -> dict:
    """Which came first for this change: the reviewers on the ready head, or a cold reading before it."""
    before = part.get("cold_readings_before") if isinstance(part, dict) else None
    if not isinstance(before, dict) or before.get("status") != "read":
        reason = before.get("reason") if isinstance(before, dict) else None
        return {"order": "unknown", "reason": f"how many cold readings came before the ready step is unknown: "
                                              f"{reason or 'the section was not read'}"}
    return {"order": REVIEWERS_FIRST if before["count"] == 0 else COLD_READING_FIRST}
