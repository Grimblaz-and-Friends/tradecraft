"""Assemble the release report's builder-route section and its row-check readings.

Design: lib/DESIGN.md#the-builder-route
"""
from __future__ import annotations


HOLDS, FAILS, NOT_STATED, NOT_APPLICABLE, NOT_OCCURRED, UNKNOWN = (
    "holds", "fails", "not-stated", "not-applicable", "not-occurred", "unknown")
COST_FIGURES = ("holder_before", "holder_after", "builder")
# The owner-affirmed lane that has no plan and owes no use, so row 2 reads it on its own terms.
MECHANICAL_LANE = "mechanical"
# The classes of a seat or implementer bundle begun after ready that row 4 allows the holder.
AFTER_READY_ALLOWED = ("bought-panel", "source-verification", "send-back", "catch-up-resume")


# What each row check asserts, under a stable label (row.check), so a release report's reader needs nothing
# else. 5.1 is the launcher's own tests, with nothing in a change's records to read, and 6.1 the holder writes
# from the run, so neither is computed.
ROW_CHECKS = {
    "1.1": "at the last ready record's head, the entrance reads nothing still owed by the builder",
    "1.2": "every check the record names was launched by this builder and composed by the entrance",
    "1.3": "between the handoff and the ready report, the holder sent the builder nothing, launched nothing, and "
           "made every reply after a message from the owner or another session",
    "2.1": "the handoff the builder received is the one the entrance composes from the settled plan",
    "2.2": "every use check the builder launched was composed from the plan's use job",
    "2.3": "no plan-writer session was launched in the term",
    "3.1": "every finding of every counted check report has one record entry, a fix or a reasoned decline",
    "3.2": "each of the builder's posted check reports is byte for byte its stored return",
    "3.3": "every check the builder launched was composed by the entrance",
    "4.1": "after the ready report, the holder launched no session other than a bought panel, a source verification, "
           "a send-back or a catch-up resume",
    "4.2": "the holder sent the builder back at most once",
    "5.2": "each refusal the launch logged is paired with one the record reports",
    "5.3": "a builder refused a call still ended in success with a ready record",
    "5.4": "each check that errored was launched again, both launches recorded",
    "5.5": "a builder started by hand has a record saying it ran under its instructions alone",
    "6.2": "a builder started by hand reached ready, or named the first check it could not launch",
    "6.3": "the vendor and model that built are observed in the run's own log",
    "7.1": "with no word from the owner, the change took the builder route by default",
    "7.2": "a change the owner asked to keep on today's route took the relay route",
    "7.3": "the holder's cost before and after the handoff and the builder's cost are priced",
}
# What a row check asserts on the mechanical lane, where it differs from ``ROW_CHECKS``.
MECHANICAL_ROW_CHECKS = {
    "2.1": "the handoff the builder received is the one the entrance composes from the affirmed brief, the lane "
           "having no plan",
}
MECHANICAL_NO_USE = "the mechanical lane owes no use, so there is no use job to compare"


def _entry(check, reading, field, reason=None, *, asserts=None):
    return {"check": check, "asserts": asserts or ROW_CHECKS[check], "reading": reading, "field": field,
            "reason": reason}


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


def _unknown_reading(value):
    """The reason a reader's ``{"status": "unknown", "reason": ...}`` gives, or None for any other value."""
    if isinstance(value, dict) and value.get("status") == UNKNOWN:
        return value.get("reason") or "unknown"
    return None


def _owed(owed_at_ready):
    """``owed_at_ready`` is ``{"first": list, "last": list}``, a ``last`` of None for no ready record, or unknown."""
    field = "owed_at_ready.last"
    unknown = _unknown_reading(owed_at_ready)
    if unknown is not None:
        return _entry("1.1", UNKNOWN, "owed_at_ready", unknown)
    if not isinstance(owed_at_ready, dict) or "last" not in owed_at_ready:
        return _missing("1.1", field)
    last = owed_at_ready["last"]
    if last is None:
        return _entry("1.1", NOT_OCCURRED, field, "no ready record")
    unknown = _unknown_reading(last)
    if unknown is not None:
        return _entry("1.1", UNKNOWN, field, unknown)
    if not isinstance(last, list):
        return _entry("1.1", UNKNOWN, field, field + " is not a list")
    if not last:
        return _entry("1.1", HOLDS, field)
    return _entry("1.1", FAILS, field, f"{len(last)} check(s) still owed at the last ready record")


def _quiet(holder_quiet):
    field = "holder_quiet"
    if not isinstance(holder_quiet, dict):
        return _missing("1.3", field)
    unknown = _unknown_reading(holder_quiet)
    if unknown is not None:
        return _entry("1.3", UNKNOWN, field, unknown)
    lists = {name: holder_quiet.get(name) for name in ("calls", "launches", "unprompted")}
    if not all(isinstance(value, list) for value in lists.values()):
        return _entry("1.3", UNKNOWN, field, "holder_quiet has no calls, launches and unprompted lists")
    if not any(lists.values()):
        return _entry("1.3", HOLDS, field)
    return _entry("1.3", FAILS, field, f"{len(lists['calls'])} call(s), {len(lists['launches'])} launch(es) and "
                                       f"{len(lists['unprompted'])} unprompted reply(ies) during the handoff")


def _handoff(handoff_plan, lane):
    field = "handoff_plan.reading"
    asserts = MECHANICAL_ROW_CHECKS["2.1"] if lane == MECHANICAL_LANE else None
    if not isinstance(handoff_plan, dict) or not isinstance(handoff_plan.get("reading"), str):
        return _entry("2.1", UNKNOWN, field, field + " was not read", asserts=asserts)
    if handoff_plan["reading"] == "composed":
        return _entry("2.1", HOLDS, field, asserts=asserts)
    return _entry("2.1", FAILS if handoff_plan["reading"] != UNKNOWN else UNKNOWN, field,
                  handoff_plan.get("reason") or handoff_plan["reading"], asserts=asserts)


def _use_composed(check_dispatches, lane):
    if lane == MECHANICAL_LANE:
        return _entry("2.2", NOT_APPLICABLE, "lane", MECHANICAL_NO_USE)
    return _composed("2.2", check_dispatches, "use")


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
    """``holder_after_ready`` is ``{"bundles": [{"class": ...}], "transcript": launch_calls(...)}``."""
    field = "holder_after_ready"
    if not isinstance(holder_after_ready, dict):
        return _missing("4.1", field)
    bundles, transcript = holder_after_ready.get("bundles"), holder_after_ready.get("transcript")
    if not _list_of_dicts(bundles) or not isinstance(transcript, dict):
        return _entry("4.1", UNKNOWN, field, _unknown_reading(holder_after_ready)
                      or "holder_after_ready has no bundles list and transcript part")
    other = [bundle for bundle in bundles if bundle.get("class") not in AFTER_READY_ALLOWED]
    calls = transcript.get("calls")
    reasons = []
    if other:
        reasons.append(f"{len(other)} bundle(s) classed other")
    if isinstance(calls, list) and calls:
        reasons.append(f"{len(calls)} transcript call(s)")
    if reasons:
        return _entry("4.1", FAILS, field, "; ".join(reasons))
    # An unread transcript might hold the launch this check looks for, unless something already fails it.
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


def _vendor_model(readiness):
    """``readiness.vendor_model`` is ``{"source": "observed"|"declared", "log": "readable"|"unreadable"|"absent"|None,
    "reason": ...}``."""
    field = "readiness.vendor_model.source"
    value, missing = _readiness_field(readiness, "6.3", field, "vendor_model")
    if missing is not None:
        return missing
    if not isinstance(value, dict) or value.get("source") not in ("observed", "declared"):
        return _missing("6.3", field)
    if value["source"] == "observed":
        return _entry("6.3", HOLDS, field)
    if value.get("log") == "readable":
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
    # The cost is what 7.3 has the report state, so an unpriced figure is the cost not stated, with its reason.
    return {**_entry("7.3", NOT_STATED, field, "; ".join(
        f"{name}: {cost_split[name].get('reason') or 'unknown'}" for name in unpriced)), "due": due}


def row_checks(payload: dict) -> list[dict]:
    """Each computed row check's reading, from the payload's named field, in row order (``ROW_CHECKS``)."""
    readiness, lane = payload.get("readiness"), payload.get("lane")
    return [
        _owed(payload.get("owed_at_ready")),
        _bool_check(readiness, "1.2", "launched_by_builder", "a check the record names was not launched composed"),
        _quiet(payload.get("holder_quiet")),
        _handoff(payload.get("handoff_plan"), lane),
        _use_composed(payload.get("check_dispatches"), lane),
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
                  reviewer_declines: list | dict | None = None, holder_after_ready: dict | None = None,
                  holder_quiet: dict | None = None, handoff_plan: dict | None = None,
                  plan_writer_launches: list | None = None, limits: list | None = None,
                  cost_split: dict | None = None, route_comparison: dict | None = None,
                  refusals: dict | None = None, hand_record: dict | None = None,
                  check_dispatches: list | None = None, check_reports: list | None = None,
                  stretch_outcome: str | None = None, stretch_seconds: list | dict | None = None,
                  lane: str | None = None) -> dict:
    """The release report's ``builder_route`` payload: every input under its name, plus ``row_checks``.

    ``lane`` is ``MECHANICAL_LANE`` for an owner-affirmed mechanical change, else None. A missing input reads
    ``unknown`` with a reason in the row checks that need it; nothing raises.
    """
    payload = {"route": route, "readiness": readiness, "owed_at_ready": owed_at_ready, "send_back": send_back,
               "catch_up_resumes": catch_up_resumes, "reviewer_declines": reviewer_declines,
               "holder_after_ready": holder_after_ready, "holder_quiet": holder_quiet,
               "handoff_plan": handoff_plan, "plan_writer_launches": plan_writer_launches, "limits": limits,
               "cost_split": cost_split, "route_comparison": route_comparison, "refusals": refusals,
               "hand_record": hand_record, "check_dispatches": check_dispatches, "check_reports": check_reports,
               "stretch_outcome": stretch_outcome, "stretch_seconds": stretch_seconds, "lane": lane}
    return {**payload, "row_checks": row_checks(payload)}
