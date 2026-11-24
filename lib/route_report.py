"""Assemble the release report's builder-route section and its row-check readings.

Design: lib/DESIGN.md#the-builder-route
"""
from __future__ import annotations


HOLDS, FAILS, NOT_STATED, NOT_APPLICABLE, NOT_OCCURRED, UNKNOWN = (
    "holds", "fails", "not-stated", "not-applicable", "not-occurred", "unknown")
COST_FIGURES = ("holder_before", "holder_after", "builder")


# What each row check asserts, under a stable label (row.check), so a release report's reader needs nothing
# else. 5.1 is the launcher's own tests, with nothing in a change's records to read, and 6.1 the holder writes
# from the run, so neither is computed.
ROW_CHECKS = {
    "1.2": "every check the record names was launched by this builder and composed by the entrance",
    "2.1": "the handoff the builder received is the one the entrance composes from the settled plan",
    "2.2": "every use check the builder launched was composed from the plan's use job",
    "2.3": "no plan-writer session was launched in the term",
    "3.1": "every finding of every counted check report has one record entry, a fix or a reasoned decline",
    "3.2": "each of the builder's posted check reports is byte for byte its stored return",
    "3.3": "every check the builder launched was composed by the entrance",
    "4.2": "the holder sent the builder back at most once",
    "5.2": "each refusal the launch logged is paired with one the record reports",
    "5.3": "a builder refused a call still ended in success with a ready record",
    "5.4": "each check that errored was launched again, both launches recorded",
    "5.5": "a builder started by hand has a record saying it ran under its instructions alone",
    "6.2": "a builder started by hand reached ready, or named the first check it could not launch",
    "7.3": "the holder's cost before and after the handoff and the builder's cost are priced",
}


def _entry(check, reading, field, reason=None):
    return {"check": check, "asserts": ROW_CHECKS[check], "reading": reading, "field": field, "reason": reason}


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


def _send_back(send_back):
    field = "send_back.count"
    count = send_back.get("count") if isinstance(send_back, dict) else None
    if type(count) is not int or count < 0:
        return _missing("4.2", field)
    if count <= 1:
        return _entry("4.2", HOLDS, field)
    return _entry("4.2", FAILS, field, f"{count} send-backs")


def _stretch_refusals(refusals):
    if not isinstance(refusals, dict) or not _list_of_dicts(refusals.get("stretch")):
        return None
    return refusals["stretch"]


def _refusals_reported(refusals):
    field = "refusals"
    stretch = _stretch_refusals(refusals)
    launches = refusals.get("launches") if isinstance(refusals, dict) else None
    if stretch is None or not _list_of_dicts(launches):
        return _missing("5.2", field)
    if not stretch:
        return _entry("5.2", NOT_OCCURRED, field, "the stretch was refused nothing")
    # Each launch's logged refusals pair in order, not by text, with the record that launch posted: the launch
    # logs the refused command whole and the record words it its own way.
    pairs = [{"dispatch": launch.get("dispatch"), "logged": logged,
              "reported": reported[index] if index < len(reported) else None}
             for launch in launches for reported in [launch.get("reported") or []]
             for index, logged in enumerate(launch.get("logged") or [])]
    unpaired = [pair["logged"] for pair in pairs if pair["reported"] is None]
    reason = "not reported: " + "; ".join(str(entry.get("command")) for entry in unpaired) if unpaired else None
    return {**_entry("5.2", FAILS if unpaired else HOLDS, field, reason), "pairs": pairs}


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


def _cost(cost_split, route_comparison):
    field = "cost_split"
    due = route_comparison.get("due") if isinstance(route_comparison, dict) else None
    if not isinstance(cost_split, dict) or not all(isinstance(cost_split.get(name), dict) for name in COST_FIGURES):
        return {**_missing("7.3", field), "due": due}
    unpriced = [name for name in COST_FIGURES if cost_split[name].get("status") != "priced"]
    if not unpriced:
        return {**_entry("7.3", HOLDS, field), "due": due}
    # The cost is what 7.3 has the report state, so an unpriced figure is the cost not stated, with its reason.
    return {**_entry("7.3", NOT_STATED, field, "; ".join(
        f"{name}: {cost_split[name].get('reason') or 'unknown'}" for name in unpriced)), "due": due}


def row_checks(payload: dict) -> list[dict]:
    """Each computed row check's reading, from the payload's named field, in row order (``ROW_CHECKS``)."""
    readiness = payload.get("readiness")
    return [
        _bool_check(readiness, "1.2", "launched_by_builder", "a check the record names was not launched composed"),
        _handoff(payload.get("handoff_plan")),
        _composed("2.2", payload.get("check_dispatches"), "use"),
        _plan_writers(payload.get("plan_writer_launches")),
        _bool_check(readiness, "3.1", "reconciled", "a counted finding is not answered in the record"),
        _store_and_posted(payload.get("check_reports")),
        _composed("3.3", payload.get("check_dispatches"), None),
        _send_back(payload.get("send_back")),
        _refusals_reported(payload.get("refusals")),
        _refused_then_ready(payload.get("refusals"), payload.get("stretch_outcome"), readiness),
        _relaunches(readiness),
        _ran_under(payload.get("hand_record")),
        _hand_answered(readiness, payload.get("hand_record")),
        _cost(payload.get("cost_split"), payload.get("route_comparison")),
    ]


def builder_route(*, route: dict | None = None, readiness: dict | None = None,
                  send_back: dict | None = None, catch_up_resumes: list | None = None, handoff_plan: dict | None = None,
                  plan_writer_launches: list | None = None, limits: list | None = None,
                  cost_split: dict | None = None, route_comparison: dict | None = None,
                  refusals: dict | None = None, hand_record: dict | None = None,
                  check_dispatches: list | None = None, check_reports: list | None = None,
                  stretch_outcome: str | None = None) -> dict:
    """The release report's ``builder_route`` payload: every input under its name, plus ``row_checks``.

    A missing input reads ``unknown`` with a reason in the row checks that need it; nothing raises.
    """
    payload = {"route": route, "readiness": readiness, "send_back": send_back,
               "catch_up_resumes": catch_up_resumes, "handoff_plan": handoff_plan, "plan_writer_launches": plan_writer_launches, "limits": limits,
               "cost_split": cost_split, "route_comparison": route_comparison, "refusals": refusals,
               "hand_record": hand_record, "check_dispatches": check_dispatches, "check_reports": check_reports,
               "stretch_outcome": stretch_outcome}
    return {**payload, "row_checks": row_checks(payload)}

