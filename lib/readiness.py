"""Read a builder's readiness record, count its check reports' findings, and reconcile the two.

Design: lib/DESIGN.md#the-builder-route
"""
from __future__ import annotations

import json
import re

import cold_reader


SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z", re.I)
DISPATCH = re.compile(r"[0-9a-f]{32}\Z")
FINDING = re.compile(r"F(?:0|[1-9][0-9]*)\Z")
STATUSES = frozenset({"ready", "stopped"})
STAGES = frozenset({"use", "acceptance-criterion", "cold-reader", "floor", "reach"})
STARTED_BY = frozenset({"launch", "hand"})
CARRIED_BY = frozenset({"test", "check", "fresh-reader"})
STOP_KINDS = frozenset({"shape", "cannot-launch"})
FIELDS = frozenset({"schema_version", "builder", "checks", "findings", "rows", "decisions", "refusals", "stop"})
SHAPES = {
    "builder": frozenset({"vendor", "model", "started_by", "usage_log"}),
    "checks": frozenset({"stage", "criterion", "row", "dispatch", "head", "report", "relaunch_of"}),
    "rows": frozenset({"row", "carried_by", "where"}),
    "decisions": frozenset({"text", "recommendation", "row"}),
    "refusals": frozenset({"command", "reason", "then"}),
    "stop": frozenset({"kind", "reason", "check"}),
}
# Each disposition carries the one field that lets the entrance test it.
DISPOSITIONS = {"fixed": "commit", "declined": "reason"}

# Appended to a composed check's dispatch so its return's findings can be counted.
RETURN_TAILS = {
    "acceptance-criterion": (
        "Open your return with exactly one of these lines: `Result: pass`, `Result: fail` or "
        "`Result: unable` (you could not tell whether the criterion holds). Say why on the lines after it."),
    "use": (
        "Close your return with a section that opens with the line `Findings:` and lists each problem "
        "you found on its own line as `F1. ...`, `F2. ...`, numbered from 1, with nothing after the list. "
        "With no problems, close your return with the single line `Findings: none`."),
    "cold-reader": (
        "Keep your account's form exactly as given above: the `## Flags` lines, or the single word "
        "`none`, and the `Can tell: yes` or `Can tell: no` line opening `## Why this change was made` "
        "are what your holder answers, each flag and a `Can tell: no` as one finding."),
}
UNREADABLE = [{"finding": "F0", "text": "findings-unreadable"}]
RESULT = re.compile(r"Result: (pass|fail|unable)\Z")
FINDINGS_HEADER = re.compile(r"Findings:(?:[ \t]+(?P<none>none\.?))?\Z", re.I)
FINDING_LINE = re.compile(r"(?:[-*][ \t]+)?(?P<id>F[1-9][0-9]*)\.[ \t]+(?P<text>\S.*)\Z")


class ReadinessError(ValueError):
    """The readiness record cannot be read; the builder must post it again in its exact form."""


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _row(value):
    return type(value) is int and value > 0


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReadinessError("duplicate JSON field: " + key)
        result[key] = value
    return result


def _shaped(value, name):
    if not isinstance(value, dict) or set(value) != SHAPES[name]:
        raise ReadinessError("invalid " + name + " entry")
    return value


def _check(entry):
    _shaped(entry, "checks")
    if entry["stage"] not in STAGES:
        raise ReadinessError("unknown check stage")
    criterion = entry["criterion"]
    if criterion is not None and not _nonempty(criterion):
        raise ReadinessError("check criterion must be named or null")
    # A criterion check judges one named criterion, so it cannot leave that name out.
    if entry["stage"] == "acceptance-criterion" and criterion is None:
        raise ReadinessError("an acceptance-criterion check names its criterion")
    if entry["row"] is not None and not _row(entry["row"]):
        raise ReadinessError("check row must be a positive integer or null")
    for field in ("dispatch", "relaunch_of"):
        if entry[field] is not None and not (isinstance(entry[field], str) and DISPATCH.match(entry[field])):
            raise ReadinessError("check " + field + " must be a dispatch id or null")
    if not isinstance(entry["head"], str) or not SHA.match(entry["head"]):
        raise ReadinessError("check head must be a full commit id")
    # A reach reading that flagged nothing posts no report, so only reach may list a null one.
    if not _row(entry["report"]) and not (entry["stage"] == "reach" and entry["report"] is None):
        raise ReadinessError("check report must be a comment id")


def _finding(entry):
    field = DISPOSITIONS.get(entry.get("disposition")) if isinstance(entry, dict) else None
    if field is None or set(entry) != {"report", "finding", "disposition", field}:
        raise ReadinessError("invalid findings entry")
    if not _row(entry["report"]) or not isinstance(entry["finding"], str) or not FINDING.match(entry["finding"]):
        raise ReadinessError("findings entry must name a report comment id and a finding F<n>")
    # An empty reason is left for reconciliation to name, so the builder learns which finding lacks one.
    if field == "commit" and not (isinstance(entry["commit"], str) and SHA.match(entry["commit"])):
        raise ReadinessError("fixed finding must name a full commit id")
    if field == "reason" and not isinstance(entry["reason"], str):
        raise ReadinessError("declined finding reason must be a string")


def _stop(value, status):
    if status == "ready":
        if value is not None:
            raise ReadinessError("a ready record carries no stop")
        return
    _shaped(value, "stop")
    if value["kind"] not in STOP_KINDS or not _nonempty(value["reason"]):
        raise ReadinessError("stop needs a known kind and a reason")
    if value["kind"] == "cannot-launch" and not _nonempty(value["check"]):
        raise ReadinessError("a cannot-launch stop names the check it could not launch")
    if value["check"] is not None and not _nonempty(value["check"]):
        raise ReadinessError("stop check must be named or null")


def payload(body: str, status: str) -> dict:
    """One exact fenced object; the marker's head and dispatch are checked by the entrance."""
    if status not in STATUSES:
        raise ReadinessError("unknown readiness status")
    blocks = re.findall(r"(?m)^```json[ \t]*\r?\n([\s\S]*?)^```[ \t]*\r?$", body)
    if len(blocks) != 1:
        raise ReadinessError("readiness record needs exactly one fenced JSON object")
    try:
        value = json.loads(blocks[0], object_pairs_hook=_unique_object)
    except (ValueError, TypeError) as exc:
        raise ReadinessError("invalid readiness record JSON: " + str(exc)) from exc
    if (not isinstance(value, dict) or set(value) != FIELDS
            or type(value["schema_version"]) is not int or value["schema_version"] != 1):
        raise ReadinessError("invalid readiness record schema")
    builder = _shaped(value["builder"], "builder")
    if (not _nonempty(builder["vendor"]) or not _nonempty(builder["model"])
            or builder["started_by"] not in STARTED_BY
            or builder["usage_log"] is not None and not _nonempty(builder["usage_log"])):
        raise ReadinessError("builder needs vendor, model, how it started, and a usage log or null")
    for name in ("checks", "findings", "rows", "decisions", "refusals"):
        if not isinstance(value[name], list):
            raise ReadinessError(name + " must be a list")
    for entry in value["checks"]:
        _check(entry)
    answered = set()
    for entry in value["findings"]:
        _finding(entry)
        key = (entry["report"], entry["finding"])
        if key in answered:
            raise ReadinessError(f"finding answered twice: {entry['finding']} of report {entry['report']}")
        answered.add(key)
    for entry in value["rows"]:
        _shaped(entry, "rows")
        if not _row(entry["row"]) or entry["carried_by"] not in CARRIED_BY or not _nonempty(entry["where"]):
            raise ReadinessError("rows entry needs a row, what carries it, and where")
    for entry in value["decisions"]:
        _shaped(entry, "decisions")
        if (not _nonempty(entry["text"]) or not _nonempty(entry["recommendation"])
                or entry["row"] is not None and not _row(entry["row"])):
            raise ReadinessError("decision needs text, a recommendation, and a row or null")
    for entry in value["refusals"]:
        _shaped(entry, "refusals")
        if not all(_nonempty(entry[field]) for field in SHAPES["refusals"]):
            raise ReadinessError("refusal needs its command, reason, and what the builder did then")
    _stop(value["stop"], status)
    return value


def marker_error(attributes: dict, body: str) -> str | None:
    """Why a readiness marker cannot be read, or None when it can."""
    if set(attributes) != {"head", "status", "dispatch"}:
        return "readiness marker needs exactly head, status and dispatch"
    if not isinstance(attributes["head"], str) or not SHA.match(attributes["head"]):
        return "readiness marker head must be a full commit id"
    if attributes["status"] not in STATUSES:
        return "readiness marker status must be ready or stopped"
    if not isinstance(attributes["dispatch"], str) or not DISPATCH.match(attributes["dispatch"]):
        return "readiness marker dispatch must be a dispatch id"
    try:
        payload(body, attributes["status"])
    except ReadinessError as exc:
        return str(exc)
    return None


def _lines(text):
    return [line.strip() for line in text.replace("\r\n", "\n").split("\n")]


def _criterion_findings(text):
    lines = [line for line in _lines(text) if line]
    result = RESULT.match(lines[0]) if lines else None
    if result is None:
        return UNREADABLE
    if result.group(1) == "pass":
        return []
    return [{"finding": "F1", "text": " ".join(lines[1:]) or lines[0]}]


def _use_findings(text):
    lines = [line for line in _lines(text) if line]
    # The last header opens the closing section, so an earlier quoted `Findings:` does not count.
    starts = [index for index, line in enumerate(lines) if FINDINGS_HEADER.match(line)]
    if not starts:
        return UNREADABLE
    header, rest = FINDINGS_HEADER.match(lines[starts[-1]]), lines[starts[-1] + 1:]
    if header.group("none"):
        return UNREADABLE if rest else []
    found = [FINDING_LINE.match(line) for line in rest]
    ids = [match.group("id") for match in found if match]
    if not found or not all(found) or len(set(ids)) != len(ids):
        return UNREADABLE
    return [{"finding": match.group("id"), "text": match.group("text")} for match in found]


def _cold_reader_findings(text):
    if cold_reader.form_errors(text):
        return UNREADABLE
    account = cold_reader.parse_account(text)
    texts = [cold_reader.flag_line(flag) for flag in account["flags"]]
    if account["can_tell"] is False:
        texts.append("Can tell: no")
    return [{"finding": f"F{number}", "text": item} for number, item in enumerate(texts, 1)]


READERS = {"acceptance-criterion": _criterion_findings, "use": _use_findings,
           "cold-reader": _cold_reader_findings}


def report_findings(stage: str, text: str) -> list[dict]:
    """The findings a check's return counts, or the single F0 when its tail cannot be read."""
    if stage not in READERS:
        raise ReadinessError("no return tail is counted for stage: " + str(stage))
    return READERS[stage](text)


def reconcile(record: dict, reports: list[dict], reachable) -> dict:
    """Hold every finding of every counting report to exactly one answered entry in the record."""
    unreconciled = []
    entries: dict[tuple, list[dict]] = {}
    for entry in record["findings"]:
        entries.setdefault((entry.get("report"), entry.get("finding")), []).append(entry)
    expected = set()
    for report in reports:
        number = report["report"]
        if not report["named"] and report["findings"]:
            unreconciled.append({"report": number, "finding": None, "problem": "left-out-of-record"})
        for finding in report["findings"]:
            expected.add((number, finding))
            found = entries.get((number, finding), [])
            problem = None
            if not found:
                problem = "missing"
            elif found[0].get("disposition") == "fixed":
                commit = found[0].get("commit")
                problem = None if isinstance(commit, str) and reachable(commit) else "unreachable"
            elif found[0].get("disposition") == "declined":
                problem = None if _nonempty(found[0].get("reason")) else "reasonless"
            else:
                problem = "extra"
            if problem:
                unreconciled.append({"report": number, "finding": finding, "problem": problem})
            # Exactly one entry answers a finding; any second one answers nothing.
            unreconciled.extend({"report": number, "finding": finding, "problem": "extra"} for _ in found[1:])
    for (number, finding), found in entries.items():
        if (number, finding) not in expected:
            unreconciled.extend({"report": number, "finding": finding, "problem": "extra"} for _ in found)
    return {"reconciled": not unreconciled, "unreconciled": unreconciled}


def relaunches(checks: list[dict], outcomes: dict[str, str]) -> dict:
    """Pair each errored check with the later check that names it as relaunched."""
    pairs, unpaired = [], []
    for index, check in enumerate(checks):
        dispatch = check.get("dispatch")
        if dispatch is None or outcomes.get(dispatch) != "error":
            continue
        later = next((item for item in checks[index + 1:] if item.get("relaunch_of") == dispatch), None)
        if later is None:
            unpaired.append(check)
        else:
            pairs.append([check, later])
    return {"pairs": pairs, "unpaired": unpaired}


def unmapped_rows(record: dict, brief_rows: list[int]) -> list[int]:
    """The affirmed rows no entry of the record's `rows` carries, in the brief's order."""
    mapped = {entry["row"] for entry in record["rows"]}
    return list(dict.fromkeys(row for row in brief_rows if row not in mapped))
