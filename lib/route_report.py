"""Assemble the release report's builder-route section, its row-check readings, and where each part is placed.

Design: lib/DESIGN.md#the-builder-route
"""
from __future__ import annotations


HOLDS, FAILS, NOT_STATED, NOT_APPLICABLE, NOT_OCCURRED, UNKNOWN = (
    "holds", "fails", "not-stated", "not-applicable", "not-occurred", "unknown")
# The payload's fields, each given by the entrance as read; the row checks are computed from them.
FIELDS = ("route", "readiness", "owed_at_ready", "send_back", "catch_up_resumes", "reviewer_declines",
          "holder_after_ready", "holder_quiet", "handoff_plan", "plan_writer_launches", "limits",
          "cost_split", "route_comparison", "refusals", "hand_record", "check_dispatches", "check_reports",
          "stretch_outcome")
COST_FIGURES = ("holder_before", "holder_after", "builder")
HOLDER_VIEWS = frozenset({"agrees", "differs", "cannot-judge"})


def _entry(check, reading, field, reason=None):
    return {"check": check, "reading": reading, "field": field, "reason": reason}


def _missing(check, field):
    return _entry(check, UNKNOWN, field, field + " was not read")


def _list_of_dicts(value):
    return isinstance(value, list) and all(isinstance(item, dict) for item in value)


def _readiness_field(readiness, check, field, key):
    """The readiness reading's value under ``key``, or the unknown entry that stands for it."""
    if not isinstance(readiness, dict) or readiness.get("record") is None:
        return None, _entry(check, UNKNOWN, field, "no lawful readiness record was read")
    if key not in readiness:
        return None, _missing(check, field)
    return readiness[key], None


def _bool_check(readiness, check, key, false_reason):
    field = "readiness." + key
    value, missing = _readiness_field(readiness, check, field, key)
    if missing is not None:
        return missing
    if value is True:
        return _entry(check, HOLDS, field)
    if value is False:
        return _entry(check, FAILS, field, false_reason)
    return _entry(check, UNKNOWN, field, field + " is not true or false")


def _owed(owed_at_ready):
    field = "owed_at_ready.last"
    if not isinstance(owed_at_ready, dict) or "last" not in owed_at_ready:
        return _missing("1.1", field)
    last = owed_at_ready["last"]
    if last is None:
        return _entry("1.1", NOT_OCCURRED, field, "no ready record")
    if not isinstance(last, list):
        return _entry("1.1", UNKNOWN, field, field + " is not a list")
    if not last:
        return _entry("1.1", HOLDS, field)
    return _entry("1.1", FAILS, field, f"{len(last)} check(s) still owed at the last ready record")


def _quiet(holder_quiet):
    field = "holder_quiet"
    if not isinstance(holder_quiet, dict):
        return _missing("1.3", field)
    if holder_quiet.get("status") == "unknown":
        return _entry("1.3", UNKNOWN, field, holder_quiet.get("reason") or "the holder's transcript is unreadable")
    calls, unprompted = holder_quiet.get("calls"), holder_quiet.get("unprompted")
    if not isinstance(calls, list) or not isinstance(unprompted, list):
        return _entry("1.3", UNKNOWN, field, "holder_quiet has no calls and unprompted lists")
    if not calls and not unprompted:
        return _entry("1.3", HOLDS, field)
    return _entry("1.3", FAILS, field,
                  f"{len(calls)} call(s) and {len(unprompted)} unprompted reply(ies) during the handoff")


def _handoff(handoff_plan):
    field = "handoff_plan.reading"
    if not isinstance(handoff_plan, dict) or not isinstance(handoff_plan.get("reading"), str):
        return _missing("2.1", field)
    if handoff_plan["reading"] == "composed":
        return _entry("2.1", HOLDS, field)
    return _entry("2.1", FAILS if handoff_plan["reading"] != UNKNOWN else UNKNOWN, field,
                  handoff_plan.get("reason") or handoff_plan["reading"])


def _composed(check, check_dispatches, stage):
    """Every builder check dispatch (of ``stage``, where one is named) reads composed."""
    field = "check_dispatches" if stage is None else f"check_dispatches[stage={stage}]"
    if not _list_of_dicts(check_dispatches):
        return _missing(check, "check_dispatches")
    entries = [entry for entry in check_dispatches if stage is None or entry.get("stage") == stage]
    if not entries:
        return _entry(check, NOT_OCCURRED, field, "the builder launched no such check")
    off = [entry for entry in entries if entry.get("status") not in ("composed", UNKNOWN)]
    if off:
        return _entry(check, FAILS, field, "; ".join(
            f"{entry.get('dispatch')}: {entry.get('status')}" for entry in off))
    unread = [entry for entry in entries if entry.get("status") == UNKNOWN]
    if unread:
        return _entry(check, UNKNOWN, field, "; ".join(f"{entry.get('dispatch')}: unknown" for entry in unread))
    return _entry(check, HOLDS, field)


def _plan_writers(plan_writer_launches):
    field = "plan_writer_launches"
    if not isinstance(plan_writer_launches, list):
        return _missing("2.3", field)
    if not plan_writer_launches:
        return _entry("2.3", HOLDS, field)
    return _entry("2.3", FAILS, field, f"{len(plan_writer_launches)} plan-writer launch(es)")


def _store_and_posted(check_reports):
    field = "check_reports"
    if not _list_of_dicts(check_reports):
        return _missing("3.2", field)
    differ = [entry for entry in check_reports if entry.get("builder")
              and "store-and-posted-differ" in (entry.get("invalid") or [])]
    if differ:
        return _entry("3.2", FAILS, field, "store-and-posted-differ: " + ", ".join(
            str(entry.get("comment", entry.get("report"))) for entry in differ))
    return _entry("3.2", HOLDS, field)


def _after_ready(holder_after_ready):
    field = "holder_after_ready"
    if not isinstance(holder_after_ready, dict):
        return _missing("4.1", field)
    bundles, transcript = holder_after_ready.get("bundles"), holder_after_ready.get("transcript")
    if not _list_of_dicts(bundles) or not isinstance(transcript, dict):
        return _entry("4.1", UNKNOWN, field, "holder_after_ready has no bundles list and transcript part")
    other = [bundle for bundle in bundles if bundle.get("class") == "other"]
    calls = transcript.get("calls")
    reasons = []
    if other:
        reasons.append(f"{len(other)} bundle(s) classed other")
    if isinstance(calls, list) and calls:
        reasons.append(f"{len(calls)} transcript call(s)")
    if reasons:
        return _entry("4.1", FAILS, field, "; ".join(reasons))
    if transcript.get("status") == UNKNOWN or not isinstance(calls, list):
        return _entry("4.1", UNKNOWN, field + ".transcript",
                      transcript.get("reason") or "the holder's transcript is unreadable")
    return _entry("4.1", HOLDS, field)


def _send_back(send_back):
    field = "send_back.count"
    count = send_back.get("count") if isinstance(send_back, dict) else None
    if type(count) is not int or count < 0:
        return _missing("4.2", field)
    if count <= 1:
        return _entry("4.2", HOLDS, field)
    return _entry("4.2", FAILS, field, f"{count} send-backs")


def _refusal_key(entry):
    return (entry.get("command"), entry.get("reason"))


def _stretch_refusals(refusals):
    if not isinstance(refusals, dict) or not _list_of_dicts(refusals.get("stretch")):
        return None
    return refusals["stretch"]


def _refusals_reported(refusals):
    field = "refusals"
    stretch = _stretch_refusals(refusals)
    if stretch is None or not _list_of_dicts(refusals.get("reported")):
        return _missing("5.2", field)
    if not stretch:
        return _entry("5.2", NOT_OCCURRED, field, "the stretch was refused nothing")
    reported = {_refusal_key(entry) for entry in refusals["reported"]}
    absent = [entry for entry in stretch if _refusal_key(entry) not in reported]
    if absent:
        return _entry("5.2", FAILS, field, "not reported: " + "; ".join(
            f"{entry.get('command')} ({entry.get('reason')})" for entry in absent))
    return _entry("5.2", HOLDS, field)


def _refused_then_ready(refusals, stretch_outcome, readiness):
    field = "stretch_outcome"
    stretch = _stretch_refusals(refusals)
    if stretch is None:
        return _missing("5.3", "refusals")
    if not stretch:
        return _entry("5.3", NOT_OCCURRED, field, "the stretch was refused nothing")
    if not isinstance(stretch_outcome, str):
        return _missing("5.3", field)
    status, missing = _readiness_field(readiness, "5.3", "readiness.status", "status")
    if missing is not None:
        return missing
    if stretch_outcome == "success" and status == "ready":
        return _entry("5.3", HOLDS, field)
    return _entry("5.3", FAILS, field, f"outcome {stretch_outcome}, readiness status {status}")


def _relaunches(readiness):
    field = "readiness.relaunches.unpaired"
    value, missing = _readiness_field(readiness, "5.4", field, "relaunches")
    if missing is not None:
        return missing
    unpaired = value.get("unpaired") if isinstance(value, dict) else None
    if not isinstance(unpaired, list):
        return _missing("5.4", field)
    if not unpaired:
        return _entry("5.4", HOLDS, field)
    return _entry("5.4", FAILS, field, f"{len(unpaired)} errored check(s) never relaunched")


def _hand_started(readiness, hand_record):
    builder = readiness.get("builder") if isinstance(readiness, dict) else None
    return hand_record is not None or (isinstance(builder, dict) and builder.get("started_by") == "hand")


def _ran_under(hand_record):
    field = "hand_record.ran_under"
    if hand_record is None:
        return _entry("5.5", NOT_APPLICABLE, field, "the builder was not started by hand")
    if not isinstance(hand_record, dict):
        return _missing("5.5", "hand_record")
    if hand_record.get("ran_under"):
        return _entry("5.5", HOLDS, field)
    return _entry("5.5", FAILS, field, "the hand-started record names nothing it ran under")


def _hand_answered(readiness, hand_record):
    field = "readiness.status"
    if not _hand_started(readiness, hand_record):
        return _entry("6.2", NOT_APPLICABLE, field, "the builder was not started by hand")
    status, missing = _readiness_field(readiness, "6.2", field, "status")
    if missing is not None:
        return missing
    if status == "ready":
        return _entry("6.2", HOLDS, field)
    stop = readiness.get("stop") if isinstance(readiness.get("stop"), dict) else {}
    if stop.get("kind") == "cannot-launch" and stop.get("check"):
        return _entry("6.2", HOLDS, "readiness.stop")
    return _entry("6.2", FAILS, field, f"status {status}, stop kind {stop.get('kind')}")


def _vendor_model(readiness):
    """``readiness.vendor_model`` is ``{"source": "observed"|"declared", "log": "readable"|"unreadable"|None}``."""
    field = "readiness.vendor_model.source"
    value, missing = _readiness_field(readiness, "6.3", field, "vendor_model")
    if missing is not None:
        return missing
    if not isinstance(value, dict) or value.get("source") not in ("observed", "declared"):
        return _missing("6.3", field)
    readable = value.get("log") == "readable"
    if value["source"] == "observed":
        return _entry("6.3", HOLDS, field)
    if readable:
        return _entry("6.3", FAILS, field, "declared though a readable usage log exists")
    return _entry("6.3", NOT_STATED, field, value.get("reason") or (
        "declared: the usage log is unreadable" if value.get("log") == "unreadable" else "declared: no usage log"))


def _route_is(check, route, name, reason):
    field = "route"
    if not isinstance(route, dict) or not isinstance(route.get("name"), str):
        return _missing(check, field)
    if route.get("name") == UNKNOWN:
        return _entry(check, UNKNOWN, field, route.get("error") or "the route is unknown")
    if route["name"] == name and route.get("reason") == reason:
        return _entry(check, HOLDS, field)
    return _entry(check, NOT_APPLICABLE, field, f"route {route['name']}/{route.get('reason')}")


def _cost(cost_split, route_comparison):
    field = "cost_split"
    due = route_comparison.get("due") if isinstance(route_comparison, dict) else None
    if not isinstance(cost_split, dict) or not all(isinstance(cost_split.get(name), dict) for name in COST_FIGURES):
        return {**_missing("7.3", field), "due": due}
    unpriced = [name for name in COST_FIGURES if cost_split[name].get("status") != "priced"]
    if not unpriced:
        return {**_entry("7.3", HOLDS, field), "due": due}
    return {**_entry("7.3", NOT_STATED, field, "; ".join(
        f"{name}: {cost_split[name].get('reason') or 'unknown'}" for name in unpriced)), "due": due}


# What each row check asks, in row_checks' order.
ROW_CHECKS = {
    "1.1": "nothing owed at the ready commit",
    "1.2": "each check named was the builder's launch",
    "1.3": "the holder sent and launched nothing unasked",
    "2.1": "the plan handed off is the settled text",
    "2.2": "the use job is the plan's",
    "2.3": "no plan writer was launched",
    "3.1": "each counted finding has one record entry",
    "3.2": "each posted report is its stored return",
    "3.3": "each check's instructions were composed",
    "4.1": "no holder launch after ready",
    "4.2": "at most one send-back",
    "5.2": "the refusals are in the record and the report",
    "5.3": "a run with a refusal still yields its ready record",
    "5.4": "a failed check's relaunch, both recorded",
    "5.5": "a hand-started record names what it ran under",
    "6.2": "a hand-started builder reaches ready or names its unlaunched check",
    "6.3": "vendor and model come from the run's own log",
    "7.1": "the first change takes the builder route by default",
    "7.2": "an owner-asked change takes today's route",
    "7.3": "the cost split, and whether the comparison is due",
}


def row_checks(payload: dict) -> list[dict]:
    """Each computed row check's reading, from the payload's named field, in row order."""
    readiness = payload.get("readiness")
    return [
        _owed(payload.get("owed_at_ready")),
        _bool_check(readiness, "1.2", "launched_by_builder", "a check the record names was not launched composed"),
        _quiet(payload.get("holder_quiet")),
        _handoff(payload.get("handoff_plan")),
        _composed("2.2", payload.get("check_dispatches"), "use"),
        _plan_writers(payload.get("plan_writer_launches")),
        _bool_check(readiness, "3.1", "reconciled", "a counted finding is not answered in the record"),
        _store_and_posted(payload.get("check_reports")),
        _composed("3.3", payload.get("check_dispatches"), None),
        _after_ready(payload.get("holder_after_ready")),
        _send_back(payload.get("send_back")),
        _refusals_reported(payload.get("refusals")),
        _refused_then_ready(payload.get("refusals"), payload.get("stretch_outcome"), readiness),
        _relaunches(readiness),
        _ran_under(payload.get("hand_record")),
        _hand_answered(readiness, payload.get("hand_record")),
        _vendor_model(readiness),
        _route_is("7.1", payload.get("route"), "builder", "default"),
        _route_is("7.2", payload.get("route"), "relay", "owner-asked"),
        _cost(payload.get("cost_split"), payload.get("route_comparison")),
    ]


def builder_route(*, route: dict | None = None, readiness: dict | None = None, owed_at_ready: dict | None = None,
                  send_back: dict | None = None, catch_up_resumes: list | None = None,
                  reviewer_declines: list | None = None, holder_after_ready: dict | None = None,
                  holder_quiet: dict | None = None, handoff_plan: dict | None = None,
                  plan_writer_launches: list | None = None, limits: list | None = None,
                  cost_split: dict | None = None, route_comparison: dict | None = None,
                  refusals: dict | None = None, hand_record: dict | None = None,
                  check_dispatches: list | None = None, check_reports: list | None = None,
                  stretch_outcome: str | None = None) -> dict:
    """The release report's ``builder_route`` payload: every input under its name, plus ``row_checks``.

    A missing input reads ``unknown`` with a reason in the row checks that need it; nothing raises.
    """
    payload = {"route": route, "readiness": readiness, "owed_at_ready": owed_at_ready, "send_back": send_back,
               "catch_up_resumes": catch_up_resumes, "reviewer_declines": reviewer_declines,
               "holder_after_ready": holder_after_ready, "holder_quiet": holder_quiet,
               "handoff_plan": handoff_plan, "plan_writer_launches": plan_writer_launches, "limits": limits,
               "cost_split": cost_split, "route_comparison": route_comparison, "refusals": refusals,
               "hand_record": hand_record, "check_dispatches": check_dispatches, "check_reports": check_reports,
               "stretch_outcome": stretch_outcome}
    return {**payload, "row_checks": row_checks(payload)}


def decline_key(entry: dict) -> str:
    """The key a holder's view of one decline is given under: its own ``key``, else report and finding, else comment."""
    if entry.get("key") is not None:
        return str(entry["key"])
    if entry.get("report") is not None and entry.get("finding") is not None:
        return f"{entry['report']}:{entry['finding']}"
    return str(entry.get("comment"))


def _declines(builder_route):
    readiness = builder_route.get("readiness")
    record = readiness.get("declines") if isinstance(readiness, dict) else None
    reviewers = builder_route.get("reviewer_declines")
    return ([{**entry, "source": "check-report"} for entry in record or [] if isinstance(entry, dict)]
            + [{**entry, "source": "connected-reviewer"} for entry in reviewers or [] if isinstance(entry, dict)])


def placement(builder_route: dict, holder_views: dict) -> dict:
    """Where the release report places each part: what needs the owner's decision, every other decline
    in its own uncollapsed list grouped by reason, and what the checks settled (collapsed).

    A decline the holder gave no view of needs the owner's decision, so no decline is left only collapsed.
    """
    views = holder_views if isinstance(holder_views, dict) else {}
    needs, agreed = [], []
    for entry in _declines(builder_route):
        key = decline_key(entry)
        view = views.get(key) if views.get(key) in HOLDER_VIEWS else "not-given"
        (agreed if view == "agrees" else needs).append({**entry, "key": key, "holder_view": view})
    groups: dict = {}
    for entry in agreed:
        groups.setdefault(str(entry.get("reason")), []).append(entry)
    readiness = builder_route.get("readiness")
    decisions = readiness.get("decisions") if isinstance(readiness, dict) else None
    handoff = builder_route.get("handoff_plan")
    differs = handoff if isinstance(handoff, dict) and handoff.get("reading") != "composed" else None
    return {
        "needs_decision": {
            "declines": needs,
            "decisions": [entry for entry in decisions or [] if isinstance(entry, dict)
                          and entry.get("row") is not None],
            "handoff_plan": differs,
            "remaining_declines": f"{len(agreed)} other decline(s) the holder agrees with, listed under "
                                  "declined findings.",
        },
        "declined_findings": [{"reason": reason, "declines": entries} for reason, entries in groups.items()],
        "settled_by_checks": {
            "route": builder_route.get("route"), "cost_split": builder_route.get("cost_split"),
            "limits": builder_route.get("limits"), "catch_up_resumes": builder_route.get("catch_up_resumes"),
            "row_checks": builder_route.get("row_checks"),
        },
    }
