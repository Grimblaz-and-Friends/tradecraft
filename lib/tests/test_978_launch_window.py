"""An implementer's window: its whole limit from its start, whatever came before it.

Design: lib/DESIGN.md#a-runs-window-and-the-entrances-cap
"""
import base64
import json
from pathlib import Path
import sys
import time

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(LIB / "tests"))
import cap_declaration
import dispatch_implementer as implementer
import run_lifecycle as lifecycle
from test_dispatch_implementer import claude_job, job, record, seen_claude  # noqa: F401 - fixtures


def metadata(args, seconds):
    args.lifecycle_input = args.dispatch.with_name("lifecycle.json")
    args.lifecycle_input.write_bytes(json.dumps({"recipient_allocation_seconds": seconds}).encode())


def request_of(args):
    return json.loads(implementer.records.sidecar(args.output, ".request.json").read_bytes())


def test_978_slow_entrance_allots_the_limit(job, monkeypatch):
    args, _ = claude_job(job, monkeypatch)
    args.timeout_seconds = 7200
    metadata(args, 7200)
    # Ten minutes were spent before the launcher ran.
    args.invocation_started_monotonic = time.monotonic() - 600
    assert implementer.run_implementer(args) == 0
    request = request_of(args)
    assert request["recipient_allocation_seconds"] == 7200
    assert request["launch_controls"]["command_ceiling_ms"] == 7200000
    assert "up to 7200 seconds" in request["launch_controls"]["notice"]
    assert record(args)["attempts"][0]["allocation_seconds"] >= 7199
    observed = seen_claude(args)
    assert observed["command_ceiling"] == "7200000"
    assert b"up to 7200 seconds" in base64.b64decode(observed["stdin"])


def test_978_codex_route_gets_the_whole_limit(job):
    args, _ = job
    args.timeout_seconds = 1800
    args.invocation_started_monotonic = time.monotonic() - 600
    implementer.run_implementer(args)  # The fixture's Codex turn returns no build; its allotment is what counts.
    assert request_of(args)["recipient_allocation_seconds"] == 1800
    assert record(args)["attempts"][0]["allocation_seconds"] >= 1799


@pytest.mark.parametrize("stage", ["floor", "review-disposition"])
def test_978_floor_ceiling_through_the_launcher(job, monkeypatch, stage):
    args, _ = claude_job(job, monkeypatch)
    args.stage, args.timeout_seconds = stage, 10800
    args.invocation_started_monotonic = time.monotonic() - 600
    assert implementer.run_implementer(args) == 0
    request = request_of(args)
    assert request["recipient_allocation_seconds"] == 3600
    assert request["caller_limit_seconds"] == 10800 and request["stage_ceiling_seconds"] == 3600
    assert record(args)["attempts"][0]["allocation_seconds"] >= 3599


def test_978_declared_cap_through_the_launcher(job, monkeypatch, tmp_path, capsys):
    args, _ = claude_job(job, monkeypatch)
    home = tmp_path / "records-home"
    monkeypatch.setattr(cap_declaration, "records_home", lambda: home)
    args.preflight_cap_seconds, args.preflight_cap_reason = 1800.0, "large repository"
    args.print_window = True  # Called directly, as a holder calls it for a panel's seat.
    args.invocation_started_monotonic = time.monotonic() - 1000
    assert implementer.run_implementer(args) == 0
    first = capsys.readouterr().out.splitlines()[0]
    assert first.startswith("implementer: window ")
    window = json.loads(first.removeprefix("implementer: window "))
    request = request_of(args)
    assert request["preflight_cap"] == {"seconds": 1800, "source": "declared", "reason": "large repository"}
    assert request["latest_return_at"] == window["latest_return_at"]
    assert window["latest_return_seconds"] == 1800 + 60 + 10
    declared = json.loads(Path(window["cap_record"]).read_bytes())
    assert declared["outcome"] == "launched"
    assert declared["bundle"] == str(implementer.records.sidecar(args.output, ".run.json"))


@pytest.mark.parametrize("flags", [(1800.0, None), (None, "x"), (1800.0, "  "), (900.0, "x")])
def test_978_an_invalid_cap_is_refused_by_the_launcher(job, flags):
    args, _ = job
    args.preflight_cap_seconds, args.preflight_cap_reason = flags
    with pytest.raises(implementer.ImplementerError, match="preflight-cap"):
        implementer.run_implementer(args)
    assert not args.output.parent.exists() or not any(args.output.parent.iterdir())


def test_978_a_launcher_past_its_cap_refuses_and_records_it(job, monkeypatch, tmp_path):
    args, _ = claude_job(job, monkeypatch)
    home = tmp_path / "records-home"
    monkeypatch.setattr(cap_declaration, "records_home", lambda: home)
    args.preflight_cap_seconds, args.preflight_cap_reason = 1800.0, "large repository"
    args.print_window = True
    args.invocation_started_monotonic = time.monotonic() - 1801
    with pytest.raises(lifecycle.PreflightCapExceeded, match="1800-second cap"):
        implementer.run_implementer(args)
    assert not args.output.parent.exists() or not any(args.output.parent.iterdir())
    assert not (args.root / "seen-claude.json").exists()
    [declared] = list((home / "preflight-caps").rglob("*.json"))
    assert json.loads(declared.read_bytes())["outcome"] == "refused-at-cap"


def test_978_at_the_request_write_the_cap_must_cover_the_steps_to_the_spawn(job, monkeypatch):
    args, _ = claude_job(job, monkeypatch)
    # Three seconds are left: less than the margin every launch keeps for its steps after the write.
    args.invocation_started_monotonic = time.monotonic() - (lifecycle.PREFLIGHT_CAP_SECONDS - 3)
    with pytest.raises(lifecycle.PreflightCapExceeded):
        implementer.run_implementer(args)
    assert not args.output.parent.exists() or not any(args.output.parent.iterdir())
    assert not (args.root / "seen-claude.json").exists()


def test_978_an_implementer_that_spawned_nothing_names_no_spawn(job, monkeypatch):
    args, _ = job

    def gone(*_a, **_k):
        raise FileNotFoundError("the codex executable disappeared")
    monkeypatch.setattr(implementer.native_codex, "run_process", gone)
    monkeypatch.setattr(implementer, "run_process", gone)
    implementer.run_implementer(args)
    attempt = record(args)["attempts"][0]
    assert attempt["launched"] is False
    assert "pre_spawn_seconds" not in attempt and "pre_spawn_parts" not in attempt


def test_978_two_works_sharing_a_folder_name_keep_their_own_declared_caps(tmp_path):
    deadline = lifecycle.stage_deadline("build", 600, cap=1800, cap_reason="large repository")
    window = lifecycle.window_line(deadline)
    # Both works flatten to the folder `my-org-repo-12`.
    cap_declaration.write(tmp_path, "my-org/repo#12", "build", deadline, window)
    cap_declaration.write(tmp_path, "my/org-repo#12", "proof", deadline, window)
    assert [row["stage"] for row in cap_declaration.read(tmp_path, "my-org/repo#12")] == ["build"]
    assert [row["stage"] for row in cap_declaration.read(tmp_path, "my/org-repo#12")] == ["proof"]
