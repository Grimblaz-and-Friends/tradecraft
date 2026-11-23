"""A builder the owner starts by hand: its stretch record, how long it is live, and its declared identity.

Design: lib/DESIGN.md#the-builder-route
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import uuid

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))

import launch_tree  # noqa: E402
import run_lifecycle as lifecycle  # noqa: E402
import work  # noqa: E402

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
WORK = "o/r#5"


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in (*launch_tree.VARIABLES, "CLAUDE_CODE_SESSION_ID"):
        monkeypatch.delenv(name, raising=False)


def hand(store, *, work_name=WORK, holder_session_id=None):
    dispatch_id = uuid.uuid4().hex
    handoff = {"dispatch": dispatch_id, "tree": str(Path(store) / "tree"), "branch": "b",
               "store": str(store), "sha256": "0" * 64}
    if holder_session_id is not None:
        handoff["holder_session_id"] = holder_session_id
    return launch_tree.write_hand_record(Path(store), work=work_name, vendor="codex", model="gpt-x",
                                         handoff=handoff, now=NOW)


def launched(store):
    """A pointer as a launched stretch writes one, its launcher this test process."""
    dispatch_id = uuid.uuid4().hex
    run = Path(store) / f"{dispatch_id}.run.json"
    run.parent.mkdir(parents=True, exist_ok=True)
    run.write_text("{}", encoding="utf-8")
    launch_tree.write_pointer(Path(store), dispatch_id=dispatch_id, work=WORK,
                              request=run.with_name(f"{dispatch_id}.request.json"), run=run,
                              session_id="s", launcher=lifecycle.process_identity(), root=Path(store))
    return dispatch_id


def test_1011_the_hand_record_says_who_started_it_and_under_what(tmp_path):
    written = hand(tmp_path)
    request = json.loads(written["request"].read_bytes())
    assert request["stage"] == "stretch" and request["work"] == WORK
    assert request["dispatch_id"] == written["dispatch_id"]
    assert request["requested"]["vendor"] == "codex" and request["requested"]["model"] == "gpt-x"
    assert {name: request[name] for name in ("started_by", "launch_block", "identity", "ran_under")} == {
        "started_by": "hand", "launch_block": "none", "identity": "declared",
        "ran_under": "its instructions alone, with no launch block"}
    assert request["handoff"]["dispatch"] == written["dispatch_id"]
    assert not written["run"].exists()
    pointer = json.loads(written["pointer"].read_bytes())
    assert written["pointer"].parent == launch_tree.pointer_directory(tmp_path)
    assert pointer["hand"] is True and pointer["work"] == WORK
    assert pointer["request"] == str(written["request"]) and pointer["run"] == str(written["run"])
    assert "launcher_process" not in pointer and "recipient_process" not in pointer


def test_1011_a_hand_record_is_live_until_it_completes(tmp_path):
    written = hand(tmp_path)
    assert [launch["dispatch_id"] for launch in launch_tree.live_launches(tmp_path)] == [written["dispatch_id"]]
    launch_tree.complete_hand_record(tmp_path, written["dispatch_id"], completed_by="readiness", now=NOW)
    run = json.loads(written["run"].read_bytes())
    assert run["completed_by"] == "readiness" and run["completed_at"] and "reason" not in run
    assert launch_tree.live_launches(tmp_path) == []
    with pytest.raises(ValueError, match="already written"):
        launch_tree.complete_hand_record(tmp_path, written["dispatch_id"], completed_by="ended-reason")


def test_1011_an_ended_record_keeps_its_reason(tmp_path):
    written = hand(tmp_path)
    launch_tree.complete_hand_record(tmp_path, written["dispatch_id"], completed_by="ended-reason",
                                     reason="the owner stopped it")
    assert json.loads(written["run"].read_bytes())["reason"] == "the owner stopped it"


def test_1011_only_a_hand_record_completes_by_hand(tmp_path):
    with pytest.raises(ValueError, match="not a hand-started record"):
        launch_tree.complete_hand_record(tmp_path, launched(tmp_path), completed_by="readiness")


def test_1011_the_variable_naming_a_live_hand_record_holds_as_declared(tmp_path, monkeypatch):
    written = hand(tmp_path)
    assert launch_tree.stretch_holding(tmp_path).state == "none"
    monkeypatch.setenv(launch_tree.DISPATCH_VARIABLE, written["dispatch_id"])
    holding = launch_tree.stretch_holding(tmp_path)
    assert (holding.state, holding.hand, holding.identity) == ("held", True, "declared")
    assert holding.launch["dispatch_id"] == written["dispatch_id"]


def test_1011_a_launched_tree_holds_before_a_hand_record(tmp_path, monkeypatch):
    written = hand(tmp_path)
    tree = launched(tmp_path)
    monkeypatch.setattr(launch_tree, "holds", lambda launch: launch["dispatch_id"] == tree)
    monkeypatch.setenv(launch_tree.DISPATCH_VARIABLE, written["dispatch_id"])
    holding = launch_tree.stretch_holding(tmp_path)
    assert (holding.state, holding.hand, holding.launch["dispatch_id"]) == ("held", False, tree)


def test_1011_an_unknown_tree_check_is_not_answered_by_a_hand_record(tmp_path, monkeypatch):
    written = hand(tmp_path)
    launched(tmp_path)

    def failing(launch):
        raise launch_tree.TreeUnknown("job unreadable")
    monkeypatch.setattr(launch_tree, "holds", failing)
    monkeypatch.setenv(launch_tree.DISPATCH_VARIABLE, written["dispatch_id"])
    assert launch_tree.stretch_holding(tmp_path).state == "unknown"


def identity(store, monkeypatch, issue=5):
    monkeypatch.setattr(work.records, "default_record_root", lambda: Path(store))
    return work._builder_identity(SimpleNamespace(repo="o/r", issue=issue))


def test_1011_the_entrance_takes_a_live_hand_record_as_a_declared_builder(tmp_path, monkeypatch):
    written = hand(tmp_path)
    monkeypatch.setenv(launch_tree.DISPATCH_VARIABLE, written["dispatch_id"])
    builder = identity(tmp_path, monkeypatch)
    assert builder["dispatch_id"] == written["dispatch_id"] and builder["identity"] == "declared"
    assert builder["root"] == str(tmp_path / "tree")


@pytest.mark.parametrize("case", ["completed", "foreign-work"])
def test_1011_a_completed_or_foreign_hand_record_is_refused_as_unproved(tmp_path, monkeypatch, case):
    written = hand(tmp_path, work_name="o/r#6" if case == "foreign-work" else WORK)
    if case == "completed":
        launch_tree.complete_hand_record(tmp_path, written["dispatch_id"], completed_by="readiness")
    monkeypatch.setenv(launch_tree.DISPATCH_VARIABLE, written["dispatch_id"])
    with pytest.raises(work.BuilderRefused) as refused:
        identity(tmp_path, monkeypatch)
    assert refused.value.code == "builder-identity-unproved"
    if case == "completed":
        # A seat's attribution refuses the variable as it refuses one naming no live launch.
        with pytest.raises(launch_tree.LaunchRefused, match="builder-identity-unproved"):
            launch_tree.attribution(tmp_path)


def test_1011_a_hand_holding_attributes_the_seat_as_hand_started(tmp_path, monkeypatch):
    written = hand(tmp_path)
    expected = {"role": "builder", "dispatch_id": written["dispatch_id"], "session_id": None,
                "started_by": "hand", "identity": "declared"}
    monkeypatch.setenv(launch_tree.DISPATCH_VARIABLE, written["dispatch_id"])
    assert launch_tree.attribution(tmp_path) == {"launched_by": expected, "dispatch_origin": "caller"}
    # The entrance drops the variable before a seat starts and names the record by its flags.
    monkeypatch.delenv(launch_tree.DISPATCH_VARIABLE)
    fields = launch_tree.attribution(tmp_path, dispatch=written["dispatch_id"], session="None", origin="entrance")
    assert fields == {"launched_by": expected, "dispatch_origin": "entrance"}


@pytest.mark.parametrize("holder", ["h", None])
def test_1011_a_hand_holding_records_a_present_session_as_declared(tmp_path, monkeypatch, holder):
    # A record whose handoff named no holder session has none to refuse.
    written = hand(tmp_path, holder_session_id=holder)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s")
    expected = {"role": "builder", "dispatch_id": written["dispatch_id"], "session_id": "s",
                "started_by": "hand", "identity": "declared"}
    monkeypatch.setenv(launch_tree.DISPATCH_VARIABLE, written["dispatch_id"])
    assert launch_tree.attribution(tmp_path) == {"launched_by": expected, "dispatch_origin": "caller"}
    monkeypatch.delenv(launch_tree.DISPATCH_VARIABLE)
    fields = launch_tree.attribution(tmp_path, dispatch=written["dispatch_id"], session="s", origin="entrance")
    assert fields == {"launched_by": expected, "dispatch_origin": "entrance"}


def test_1011_the_holder_session_is_refused_as_its_own_hand_builder(tmp_path, monkeypatch):
    written = hand(tmp_path, holder_session_id="h")
    assert json.loads(written["pointer"].read_bytes())["holder_session_id"] == "h"
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "h")
    monkeypatch.setenv(launch_tree.DISPATCH_VARIABLE, written["dispatch_id"])
    with pytest.raises(launch_tree.LaunchRefused, match="builder-identity-unproved") as refused:
        launch_tree.attribution(tmp_path)
    assert refused.value.code == "builder-identity-unproved" and "holder" in refused.value.detail
    monkeypatch.delenv(launch_tree.DISPATCH_VARIABLE)
    with pytest.raises(launch_tree.LaunchRefused, match="builder-identity-unproved"):
        launch_tree.attribution(tmp_path, dispatch=written["dispatch_id"], origin="entrance")


def test_1011_a_launched_holding_still_refuses_a_session_not_its_own(tmp_path, monkeypatch):
    tree = launched(tmp_path)
    monkeypatch.setattr(launch_tree, "holds", lambda launch: launch["dispatch_id"] == tree)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "other")
    with pytest.raises(launch_tree.LaunchRefused, match="builder-identity-unproved"):
        launch_tree.attribution(tmp_path)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s")
    assert launch_tree.attribution(tmp_path)["launched_by"] == {
        "role": "builder", "dispatch_id": tree, "session_id": "s", "identity": "proved"}


def test_1011_a_flag_naming_a_completed_hand_record_is_refused_outside_every_tree(tmp_path):
    written = hand(tmp_path)
    launch_tree.complete_hand_record(tmp_path, written["dispatch_id"], completed_by="readiness")
    with pytest.raises(launch_tree.LaunchRefused, match="launched-by-outside-a-stretch"):
        launch_tree.attribution(tmp_path, dispatch=written["dispatch_id"], origin="entrance")


def test_1011_the_entrance_takes_a_hand_started_claude_session_as_declared(tmp_path, monkeypatch):
    written = hand(tmp_path, holder_session_id="h")
    monkeypatch.setenv(launch_tree.DISPATCH_VARIABLE, written["dispatch_id"])
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s")
    builder = identity(tmp_path, monkeypatch)
    assert (builder["session_id"], builder["identity"]) == ("s", "declared")
    # The holder can't be its own builder.
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "h")
    with pytest.raises(work.BuilderRefused) as refused:
        identity(tmp_path, monkeypatch)
    assert refused.value.code == "builder-identity-unproved"
