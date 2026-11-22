"""Generated, content-free transcript ledgers exercise durable time attribution."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import holder_transcript as ht
import change_cost as cost


def at(second):
    return datetime(2026, 10, 10, 12, 0, second, tzinfo=timezone.utc)


def reply(identity="m1", second=1, session="holder", model="claude-opus-5-5", agent=None,
          input=10, output=3, read=4, five=2, hour=5):
    record = {"type": "assistant", "sessionId": session, "timestamp": at(second).isoformat(),
              "message": {"id": identity, "model": model, "usage": {
                  "input_tokens": input, "output_tokens": output, "cache_read_input_tokens": read,
                  "cache_creation_input_tokens": five + hour,
                  "cache_creation": {"ephemeral_5m_input_tokens": five, "ephemeral_1h_input_tokens": hour}}}}
    if agent:
        record["agentId"] = agent
    return record


def write_lines(path, records, append=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = b"".join((json.dumps(record, ensure_ascii=True) + "\n").encode() for record in records)
    with path.open("ab" if append else "wb") as stream:
        stream.write(data)


@pytest.fixture
def source(tmp_path):
    projects = tmp_path / "projects"
    main = projects / "unrelated-slug" / "holder.jsonl"
    write_lines(main, [reply()])
    return projects, main


def capture(source, destination, second=10, session="holder", **kwargs):
    return ht.close("acme/widget", 12, destination, projects=source[0], session_id=session,
                    now=at(second), **kwargs)


def ids(row):
    return {item["id"] for item in row["holder"]["replies"]}


def test_exact_session_models_deduplication_and_snapshot_evidence(source, tmp_path):
    projects, main = source
    replay = reply(second=7)
    child = main.parent / "holder" / "subagents" / "agent-child.jsonl"
    write_lines(main, [reply(), replay, reply("m2", 2, model="claude-opus-5"), reply("shared", 3)])
    write_lines(child, [reply("shared", 4, agent="child"), reply("m3", 5, agent="child")])
    write_lines(projects / "newest" / "other.jsonl", [reply("distractor", session="other", input=999)])
    row = capture(source, tmp_path / "a.jsonl")
    assert ids(row) == {"m1", "m2", "shared", "m3"}
    assert next(item for item in row["holder"]["replies"] if item["id"] == "m1")["timestamp"] == at(1).isoformat()
    assert row["tokens"]["models"] == {
        "claude-opus-5-5": {"input": 30, "output": 9, "cache_read": 12, "cache_creation": 21,
                             "cache_write_5m": 6, "cache_write_1h": 15},
        "claude-opus-5": {"input": 10, "output": 3, "cache_read": 4, "cache_creation": 7,
                          "cache_write_5m": 2, "cache_write_1h": 5}}
    assert row["raw_source"] == str(main.resolve())
    assert row["holder"]["session_id"] == "holder"
    assert len(row["holder"]["snapshots"]) == 2
    assert all("content" not in json.dumps(item) for item in row["holder"]["replies"])
    assert not cost._contains_money_key(row)
    named = capture(source, tmp_path / "other.jsonl", session="other")
    assert ids(named) == {"distractor"}


@pytest.mark.parametrize("source_kind", ["explicit", "config", "home", "empty-config"])
def test_projects_root_precedence(source, tmp_path, monkeypatch, source_kind):
    projects, main = source
    home_projects = Path.home() / ".claude" / "projects"
    configured = tmp_path / "profile"
    write_lines(home_projects / "slug" / "holder.jsonl", [reply("home")])
    write_lines(configured / "projects" / "slug" / "holder.jsonl", [reply("config")])
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "holder")
    if source_kind in {"config", "explicit"}:
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(configured))
    elif source_kind == "empty-config":
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", "")
    row = ht.close("acme/widget", 12, tmp_path / "usage", now=at(10),
                   projects=projects if source_kind == "explicit" else None)
    expected = {"explicit": ("m1", projects, "--claude-projects"),
                "config": ("config", configured / "projects", "CLAUDE_CONFIG_DIR"),
                "home": ("home", home_projects, "home"),
                "empty-config": ("home", home_projects, "home")}[source_kind]
    assert ids(row) == {expected[0]}
    assert (row["holder"]["projects_root"], row["holder"]["projects_root_source"]) == (str(expected[1].resolve()), expected[2])


@pytest.mark.parametrize("problem,reason", [
    ("missing", "not found"), ("ambiguous", "ambiguous"), ("encoding", "cannot read"),
    ("permission", "cannot read"), ("no-identity", "identity is unavailable"),
    ("bad-identity", "usable basename"),
])
def test_discovery_failure_is_unknown_with_cause(source, tmp_path, monkeypatch, problem, reason):
    projects, main = source
    session = "holder"
    if problem == "missing":
        main.unlink()
    elif problem == "ambiguous":
        write_lines(projects / "second" / "holder.jsonl", [reply()])
    elif problem == "encoding":
        main.write_bytes(b"\xff\n")
    elif problem == "permission":
        original = Path.read_bytes
        def unreadable(path):
            if path == main:
                raise PermissionError("denied fixture")
            return original(path)
        monkeypatch.setattr(Path, "read_bytes", unreadable)
    elif problem == "no-identity":
        session = None
    elif problem == "bad-identity":
        session = "../holder"
    row = capture(source, tmp_path / "usage", session=session)
    assert row["tokens"] is None
    assert reason in row["tokens_unknown_reason"]
    assert row["holder"]["status"] == "unknown" and not row["holder"]["observed_empty"]
    assert row["holder"]["requested_session_id"] == session
    assert row["holder"]["attempted_source"].startswith(str(projects))
    value = cost.rate_card_equivalent(row, cost.load_rates(LIB / "rates.json"))
    assert value["status"] == "unknown" and "amount" not in value


@pytest.mark.parametrize("fault,reason", [
    ("negative", "nonnegative integer"), ("fraction", "nonnegative integer"),
    ("boolean", "nonnegative integer"), ("missing-count", "nonnegative integer"),
    ("missing-id", "message id"), ("missing-model", "observed model"),
    ("naive-time", "timezone-aware"), ("parent", "parent session identity"),
    ("duration", "disagree"), ("conflict", "conflicting"), ("partial", "malformed"),
    ("no-duration", "duration breakdown"),
    ("invalid-extra", "nonnegative integer"),
])
def test_partial_evidence_is_visible_and_readable_population_is_a_floor(source, tmp_path, fault, reason):
    _, main = source
    broken = reply("bad", 2)
    usage = broken["message"]["usage"]
    if fault in {"negative", "fraction", "boolean"}:
        usage["input_tokens"] = {"negative": -1, "fraction": 1.5, "boolean": True}[fault]
    elif fault == "missing-count":
        del usage["output_tokens"]
    elif fault == "missing-id":
        del broken["message"]["id"]
    elif fault == "missing-model":
        del broken["message"]["model"]
    elif fault == "naive-time":
        broken["timestamp"] = "2026-10-10T12:00:02"
    elif fault == "parent":
        broken["sessionId"] = "wrong"
    elif fault == "duration":
        usage["cache_creation_input_tokens"] = 50
    elif fault == "no-duration":
        del usage["cache_creation"]
    elif fault == "invalid-extra":
        usage["new_billable_tokens"] = float("nan")
    elif fault == "conflict":
        write_lines(main, [reply("bad", 2)], append=True)
        usage["input_tokens"] = 999
    if fault == "partial":
        with main.open("ab") as stream:
            stream.write(b'{"type":"assistant"')
    else:
        write_lines(main, [broken], append=True)
    row = capture(source, tmp_path / "usage")
    assert ids(row) == {"m1"}
    assert any(reason in gap["reason"] for gap in row["holder"]["gaps"])
    value = cost.rate_card_equivalent(row, cost.load_rates(LIB / "rates.json"))
    assert value["status"] == "known" and value["floor"]
    assert any(reason in why for why in value["floor_reasons"])


def test_empty_window_is_observed_known_zero_and_zero_writes_need_no_breakdown(source, tmp_path):
    _, main = source
    main.write_bytes(b"")
    row = capture(source, tmp_path / "usage")
    assert row["holder"]["observed_empty"] and row["tokens"] == {"models": {}}
    value = cost.rate_card_equivalent(row, cost.load_rates(LIB / "rates.json"))
    assert value["status"] == "known" and value["amount"] == "0" and not value["floor"]
    record = reply("zero", 12, five=0, hour=0)
    del record["message"]["usage"]["cache_creation"]
    write_lines(main, [record])
    assert ids(capture(source, tmp_path / "usage", second=20)) == {"zero"}


def test_shared_history_cross_changes_destinations_equal_boundary_replays_and_late_receipt(source, tmp_path):
    _, main = source
    write_lines(main, [reply("first", 1), reply("instalment", 10)])
    a, b = tmp_path / "a" / "usage", tmp_path / "b" / "usage"
    first = capture(source, a)
    # Replays can arrive out of order, with a later content-block timestamp.
    write_lines(main, [reply("new", 12), reply("first", 15), reply("late", 8)], append=True)
    second = ht.close("elsewhere/product", 99, b, projects=source[0], session_id="holder", now=at(20))
    assert ids(first) == {"first", "instalment"} and ids(second) == {"new"}
    assert second["holder"]["window"]["previous_close_id"] == first["dispatch"]["id"]
    assert second["holder"]["recovered_closes"][0]["close_id"] == first["dispatch"]["id"]
    rows, skipped = ht.holder_rows(a)
    assert skipped == [] and len(rows) == 1
    assert ids(rows[0][1]) == {"first", "instalment", "late"}
    assert rows[0][1]["holder"]["late_recording_receipts"][0]["original_close_id"] == first["dispatch"]["id"]
    write_lines(main, [reply("repair", 22)], append=True)
    third = capture(source, a, second=30)
    assert ids(third) == {"repair"}
    assert third["holder"]["recovered_closes"] == []
    rows, _ = ht.holder_rows(a)
    assert sum(row["tokens"]["models"]["claude-opus-5-5"]["input"] for _, row, _ in rows) == 40
    other = main.parent / "independent.jsonl"
    write_lines(other, [reply("separate", 2, session="independent")])
    assert ids(capture(source, a, session="independent")) == {"separate"}


def test_unknown_interval_consumes_time_and_retains_unknown_after_recovery(source, tmp_path):
    _, main = source
    saved = main.read_bytes()
    main.unlink()
    a, b = tmp_path / "a", tmp_path / "b"
    first = capture(source, a)
    main.write_bytes(saved)
    write_lines(main, [reply("later", 12)], append=True)
    second = capture(source, b, second=20)
    assert ids(second) == {"later"}
    rows, _ = ht.holder_rows(a)
    recovered = rows[0][1]
    assert ids(recovered) == {"m1"} and recovered["tokens_unknown_reason"] == first["tokens_unknown_reason"]
    assert recovered["model"]["reported"] == ["claude-opus-5-5"]
    assert cost.rate_card_equivalent(recovered, cost.load_rates(LIB / "rates.json"))["floor"]


def test_supplied_claude_boundary_prevents_automatic_recovery_but_codex_does_not(source, tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "holder")
    explicit = cost.holder_close("acme/widget", 12, "claude", None, None, "caller unknown", tmp_path / "a", now=at(10))
    write_lines(source[1], [reply("later", 12)], append=True)
    automatic = capture(source, tmp_path / "b", second=20)
    assert ids(automatic) == {"later"} and automatic["holder"]["recovered_closes"] == []
    assert explicit["holder"]["source_kind"] == "supplied"
    write_lines(source[0] / "slug" / "codex-parent.jsonl", [reply(session="codex-parent")])
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "codex-parent")
    codex = cost.holder_close("acme/widget", 12, "codex", None, None, "manual", tmp_path / "c", now=at(10))
    assert "holder" not in codex
    assert ids(capture(source, tmp_path / "d", session="codex-parent", second=20)) == {"m1"}


def test_publication_failure_cannot_advance_boundary_and_materialization_failure_is_recoverable(source, tmp_path, monkeypatch):
    destination = tmp_path / "usage"
    publish = ht._publish
    def fail(*args):
        raise OSError("injected before publication")
    monkeypatch.setattr(ht, "_publish", fail)
    with pytest.raises(OSError, match="before publication"):
        capture(source, destination)
    assert not list(ht.default_state_root().rglob("*.json"))
    monkeypatch.setattr(ht, "_publish", publish)
    monkeypatch.setattr(ht, "_materialize", fail)
    row = capture(source, destination)
    assert "materialization_error" in row and not destination.exists()
    rows, _ = ht.holder_rows(destination)
    assert ids(rows[0][1]) == {"m1"}
    later = capture(source, destination, second=20)
    assert ids(later) == set() and later["holder"]["window"]["previous_close_id"] == row["dispatch"]["id"]


def test_torn_materialization_and_conflicting_copy_keep_authoritative_journal(source, tmp_path):
    destination = tmp_path / "usage"
    row = capture(source, destination)
    destination.write_bytes(b'{"torn"')
    rows, skipped = ht.holder_rows(destination)
    assert ids(rows[0][1]) == {"m1"} and "torn" in skipped[0]["reason"]
    copied = json.loads(json.dumps(row))
    copied["tokens"]["models"]["claude-opus-5-5"]["input"] = 999
    write_lines(destination, [row, copied])
    rows, _ = ht.holder_rows(destination)
    assert rows[0][1] == row and "conflicting" in rows[0][2][0]


def test_backward_clock_and_damaged_history_never_reset(source, tmp_path):
    row = capture(source, tmp_path / "usage")
    with pytest.raises(ht.TranscriptError, match="backward"):
        capture(source, tmp_path / "next", second=5)
    journal = Path(row["holder"]["journal"])
    journal.write_bytes(b"{}")
    with pytest.raises(ht.TranscriptError, match="damaged"):
        capture(source, tmp_path / "next", second=20)


@pytest.mark.parametrize("damage", ["holder-list", "window-list", "bad-time", "reply-null", "unsupported"])
def test_damaged_row_history_fails_as_evidence_and_report_keeps_materialization(source, tmp_path, damage):
    destination = tmp_path / "usage"
    row = capture(source, destination)
    path = Path(row["holder"]["journal"])
    entry = json.loads(path.read_bytes())
    if damage == "holder-list":
        entry["row"]["holder"] = []
    elif damage == "window-list":
        entry["row"]["holder"]["window"] = []
    elif damage == "bad-time":
        entry["row"]["holder"]["window"]["previous_close_at"] = "invalid"
    elif damage == "reply-null":
        entry["row"]["holder"]["replies"] = [None]
    else:
        entry["schema_version"] = 999
    path.write_bytes(json.dumps(entry).encode())
    with pytest.raises(ht.TranscriptError):
        capture(source, destination, second=20)
    rows, skipped = ht.holder_rows(destination)
    assert rows[0][1] == row and skipped


def test_unpublished_temporary_entries_do_not_consume_window(source, tmp_path):
    import hashlib
    directory = ht.default_state_root() / hashlib.sha256(b"holder").hexdigest()
    directory.mkdir(parents=True)
    (directory / "holder-close-interrupted.tmp").write_bytes(b'{"partial":')
    row = capture(source, tmp_path / "usage")
    assert ids(row) == {"m1"} and row["holder"]["window"]["previous_close_id"] is None


def test_committed_backward_history_cannot_authorize_another_close(source, tmp_path):
    capture(source, tmp_path / "usage")
    second = capture(source, tmp_path / "usage", second=20)
    path = Path(second["holder"]["journal"])
    entry = json.loads(path.read_bytes())
    entry["row"]["holder"]["window"]["closed_at"] = at(5).isoformat()
    path.write_bytes(json.dumps(entry).encode())
    with pytest.raises(ht.TranscriptError, match="invalid time boundaries"):
        capture(source, tmp_path / "usage", second=30)


def test_copied_journal_closes_and_receipts_are_once_and_conflicts_are_named(source, tmp_path):
    import shutil
    destination = tmp_path / "usage"
    first = capture(source, destination)
    write_lines(source[1], [reply("late", 2)], append=True)
    capture(source, tmp_path / "second", second=20)
    directory = Path(first["holder"]["journal"]).parent
    copied = ht.default_state_root() / "copied"
    shutil.copytree(directory, copied)
    rows, skipped = ht.holder_rows(destination)
    assert len(rows) == 1 and ids(rows[0][1]) == {"m1", "late"} and not skipped
    assert len(rows[0][1]["holder"]["late_recording_receipts"]) == 1
    entry_path = copied / Path(first["holder"]["journal"]).name
    entry = json.loads(entry_path.read_bytes())
    entry["row"]["tokens"]["models"]["claude-opus-5-5"]["input"] = 999
    entry_path.write_bytes(json.dumps(entry).encode())
    rows, _ = ht.holder_rows(destination)
    assert any("conflicting committed" in problem for problem in rows[0][2])


def test_concurrent_subprocess_closes_spend_replies_once(source, tmp_path):
    destination = tmp_path / "usage"
    script = (
        "import sys; from pathlib import Path; from datetime import datetime, timezone; "
        f"sys.path.insert(0, {str(LIB)!r}); import holder_transcript as h; "
        "h.close('acme/widget',12,Path(sys.argv[2]),projects=Path(sys.argv[1]),session_id='holder',"
        "now=datetime(2026,10,10,12,0,10,tzinfo=timezone.utc))"
    )
    processes = [subprocess.Popen([sys.executable, "-c", script, str(source[0]), str(destination)],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
    for process in processes:
        out, err = process.communicate(timeout=30)
        assert process.returncode == 0, err
        assert out == b""
    rows, skipped = ht.holder_rows(destination)
    assert skipped == [] and len(rows) == 2
    assert sum(len(ids(row)) for _, row, _ in rows) == 1
    assert sorted(len(ids(row)) for _, row, _ in rows) == [0, 1]


def test_lock_released_on_process_death_and_timeout_has_no_row(tmp_path):
    directory = tmp_path / "locked"
    marker = tmp_path / "acquired"
    script = (f"import sys,time; from pathlib import Path; sys.path.insert(0,{str(LIB)!r}); "
              "import holder_transcript as h; "
              "lock=h.session_lock(Path(sys.argv[1])); lock.__enter__(); "
              "Path(sys.argv[2]).write_bytes(b'ready'); time.sleep(30)")
    process = subprocess.Popen([sys.executable, "-c", script, str(directory), str(marker)],
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 15
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(.05)
        assert marker.exists()
        with pytest.raises(ht.TranscriptError, match="timed out"):
            with ht.session_lock(directory, timeout=.1):
                pytest.fail("lock entered while another process owns it")
        process.kill()
        process.communicate(timeout=15)
        with ht.session_lock(directory, timeout=1):
            assert not list(directory.glob("*.json"))
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=15)


def said(identity, second, *blocks, stop="end_turn", session="holder"):
    content = [{"type": "tool_use", "id": f"{identity}-{index}", "name": name, "input": tool_input}
               for index, (name, tool_input) in enumerate(blocks)] or [{"type": "text", "text": "fixture"}]
    return {"type": "assistant", "sessionId": session, "timestamp": at(second).isoformat(),
            "message": {"id": identity, "model": "claude-opus-5-5", "stop_reason": "tool_use" if blocks else stop,
                        "content": content}}


def shell(command):
    return "Bash", {"command": command}


def heard(second, origin=None, text="fixture prompt", result=None):
    record = {"type": "user", "sessionId": "holder", "timestamp": at(second).isoformat(),
              "message": {"role": "user", "content": text}}
    if result is not None:
        record["message"]["content"] = [{"type": "tool_result", "tool_use_id": result, "content": "ok"}]
        record["toolUseResult"] = {"stdout": "ok"}
    if origin is not None:
        record["origin"] = origin
    return record


def transcript(tmp_path, records):
    projects = tmp_path / "projects"
    write_lines(projects / "slug" / "holder.jsonl", records)
    return projects


def test_1011_handoff_quiet_lists_stage_launcher_message_write_and_unprompted_reply(tmp_path):
    projects = transcript(tmp_path, [
        heard(1, {"kind": "human"}),
        said("a", 2, shell(r'python -B "C:\plugin\lib\work.py" run use 12')),
        heard(3, result="a-0"),
        said("b", 4, shell("python -B lib/dispatch_seat.py --stage review"), ("SendMessage", {"to": "builder-12"})),
        heard(5, result="b-0"),
        said("c", 6, shell("gh pr comment 12 --repo acme/widget --body done"), shell("gh issue comment 99 -b x"),
             ("SendMessage", {"to": "someone-else"})),
        heard(7, result="c-0"),
        said("d", 8),
        heard(9, {"kind": "task-notification"}, "<task-notification>done</task-notification>"),
        said("e", 10),
    ])
    found = ht.handoff_quiet("holder", at(0), at(20), builder="builder-12", change=("acme/widget", 12), home=projects)
    assert found["status"] == "not-quiet" and found["reason"] is None
    assert [(call["timestamp"], call["kinds"]) for call in found["calls"]] == [
        (at(2).isoformat(), ["work-run"]), (at(4).isoformat(), ["launcher"]),
        (at(4).isoformat(), ["message"]), (at(6).isoformat(), ["github-write"])]
    assert found["calls"][2]["description"] == "SendMessage to builder-12"
    assert found["calls"][0]["description"].endswith('work.py" run use 12')
    assert [item["timestamp"] for item in found["unprompted"]] == [at(10).isoformat()]


def test_1011_owner_and_peer_answers_and_the_decision_are_quiet(tmp_path):
    peer = "Another Claude session sent a message:\n<cross-session-message from=\"x\">go</cross-session-message>"
    projects = transcript(tmp_path, [
        heard(1, {"kind": "human"}),
        said("a", 2, shell("python -B lib/work.py 12; cat lib/dispatch_seat.py; gh pr view 12")),
        heard(3, result="a-0"),
        said("a2", 4),
        heard(5, {"kind": "peer", "name": "Steward"}, peer) | {"isMeta": True},
        said("b", 6, ("Read", {"file_path": "x"})),
        heard(7, result="b-0"),
        said("c", 8),
        # An earlier runtime records no origin; the tag still names another session.
        heard(9, text=peer),
        said("d", 10),
    ])
    found = ht.handoff_quiet("holder", at(0), at(20), builder="builder-12", change=("acme/widget", 12), home=projects)
    assert found == {"status": "quiet", "calls": [], "unprompted": [], "reason": None}
    assert ht.launch_calls("holder", at(0), at(20), home=projects)["status"] == "none"


@pytest.mark.parametrize("problem", ["missing", "unreadable", "malformed"])
def test_1011_unreadable_transcript_is_unknown_with_reason(tmp_path, problem):
    projects = transcript(tmp_path, [heard(1, {"kind": "human"}), said("a", 2)])
    main = projects / "slug" / "holder.jsonl"
    if problem == "missing":
        main.unlink()
    elif problem == "unreadable":
        main.write_bytes(b"\xff\n")
    else:
        with main.open("ab") as stream:
            stream.write(b'{"type":"assistant"')
    found = ht.handoff_quiet("holder", at(0), at(20), home=projects)
    assert found["status"] == "unknown" and found["reason"]
    assert {"missing": "not found", "unreadable": "cannot read", "malformed": "malformed"}[problem] in found["reason"]
    assert ht.launch_calls("holder", at(0), at(20), home=projects)["status"] == "unknown"


def test_1011_window_is_start_inclusive_end_exclusive(tmp_path):
    projects = transcript(tmp_path, [
        said("before", 1, shell("python lib/dispatch_implementer.py")),
        heard(2, result="before-0"),
        said("done", 3),
        said("first", 5),
        said("edge", 10, shell("python lib/work.py run build 12")),
        heard(11, result="edge-0"),
        said("after", 12),
    ])
    found = ht.handoff_quiet("holder", at(5), at(10), home=projects)
    assert found["calls"] == [] and [item["timestamp"] for item in found["unprompted"]] == [at(5).isoformat()]
    assert ht.handoff_quiet("holder", at(6), at(10), home=projects)["status"] == "quiet"
    later = ht.handoff_quiet("holder", at(10), at(13), home=projects)
    assert [call["timestamp"] for call in later["calls"]] == [at(10).isoformat()]
    assert later["unprompted"] == [{"timestamp": at(10).isoformat(), "message_id": "edge",
                                    "description": "assistant reply with no owner or peer message before it"}]


def test_1011_launch_calls_finds_agent_and_launcher_and_nothing_in_a_quiet_window(tmp_path):
    projects = transcript(tmp_path, [
        heard(1, {"kind": "human"}),
        said("a", 2, ("Agent", {"description": "probe", "prompt": "x"})),
        heard(3, result="a-0"),
        said("b", 4, shell("python -B lib/dispatch_record.py --work acme/widget#12"), ("SendMessage", {"to": "x"})),
        heard(5, result="b-0"),
        said("c", 6),
        heard(10, {"kind": "human"}),
        said("d", 11, shell("python -B lib/work.py 12")),
        heard(12, result="d-0"),
        said("e", 13),
    ])
    found = ht.launch_calls("holder", at(0), at(10), home=projects)
    assert found["status"] == "found" and found["reason"] is None
    assert [(call["tool"], call["kinds"]) for call in found["calls"]] == [("Agent", ["agent"]), ("Bash", ["launcher"])]
    assert found["calls"][0]["description"] == "Agent: probe"
    assert ht.launch_calls("holder", at(10), at(20), home=projects) == {"status": "none", "calls": [], "reason": None}


@pytest.mark.parametrize("command,writes", [
    ("gh api repos/acme/widget/issues/12/comments -f body=x", True),
    ("gh api -X PATCH repos/acme/widget/issues/12", True),
    ("gh api repos/acme/widget/issues/12/comments", False),
    ("gh api -X GET repos/acme/widget/issues/12 -f per_page=1", False),
    ("gh api repos/other/repo/issues/12/comments -f body=x", False),
    ("gh api graphql -f query='query { x }' -F number=12", False),
    ("gh api graphql -f query='mutation { x }' -F number=12", True),
    ("gh pr edit '#12' --add-label x", True),
    ("gh pr comment 13 --body x", False),
])
def test_1011_github_write_must_write_and_name_the_change(tmp_path, command, writes):
    projects = transcript(tmp_path, [heard(1, {"kind": "human"}), said("a", 2, shell(command))])
    found = ht.handoff_quiet("holder", at(0), at(20), change=("acme/widget", 12), home=projects)
    assert bool(found["calls"]) is writes
