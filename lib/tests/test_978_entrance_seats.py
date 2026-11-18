"""A seat the entrance starts is allotted its declared limit, whatever the entrance spent first.

Design: lib/DESIGN.md#a-runs-window-and-the-entrances-cap
"""
from contextlib import contextmanager, nullcontext
from pathlib import Path
import subprocess
import sys
import time

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(LIB / "tests"))
import dispatch_seat
import preflight
import run_lifecycle as lifecycle
import work
from test_work import AFFIRMED, ARTIFACT, PRODUCER, SHA, git, repository, state  # noqa: F401


@contextmanager
def slow_entrance(stage, limit, spent):
    """The entrance's own run, its clock started `spent` seconds ago, with the stage's deadline."""
    with preflight.scope(started=time.monotonic() - spent) as opened:
        deadline = lifecycle.stage_deadline(stage, limit, started=opened.started, declared=True)
        with lifecycle.deadline_scope(deadline):
            yield deadline


def seat_window(command, deadline):
    """The window the seat this command starts would give its recipient."""
    assert command[command.index("--timeout-seconds") + 1] == "1800"
    assert float(command[command.index("--invocation-started-monotonic") + 1]) == deadline.started
    args = dispatch_seat.parser().parse_args(command[2:])
    seat = lifecycle.stage_deadline(args.stage, args.timeout_seconds, started=args.invocation_started_monotonic)
    seat.open_window()
    return seat


def capture_seat(monkeypatch):
    launches = []
    original_run = subprocess.run

    def run(command, *args, **kwargs):
        if len(command) > 1 and Path(command[1]).name == "dispatch_seat.py":
            launches.append(list(command))
            return subprocess.CompletedProcess(command, 0)
        return original_run(command, *args, **kwargs)
    monkeypatch.setattr(work.subprocess, "run", run)
    monkeypatch.setattr(work, "_recipient_run", run)
    return launches


def test_978_cold_seat_started_by_the_entrance_gets_the_whole_limit(tmp_path, monkeypatch):
    fixture = state(AFFIRMED, ARTIFACT + "\nArtifact body.\n")
    fixture.issue_comments[1]["id"] = 20
    monkeypatch.setattr(work, "judging_root", lambda _root: nullcontext(tmp_path))
    monkeypatch.setattr(work, "_producer_vendor", lambda *_a, **_k: ("codex", "artifact bundle"))
    monkeypatch.setattr(work, "_git_snapshot", lambda _root: (SHA, ""))
    launches = capture_seat(monkeypatch)
    runtime = Path(sys.executable).resolve()
    with slow_entrance("cold-seat", 1800, 500) as deadline:
        assert work.execute_stage(fixture, work.Decision("cold-seat", True, "fresh", "fixture"), tmp_path, None,
                                  claude_path=runtime, codex_path=runtime, timeout_seconds=1800,
                                  floor_command="python fixture-check.py") == 0
    [command] = launches
    seat = seat_window(command, deadline)
    assert seat.allotted == 1800 and seat.remaining() >= 1799


def test_978_use_consumer_started_by_the_entrance_gets_the_whole_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(work, "_producer_vendor", lambda *_a, **_k: ("codex", "builder bundle"))
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = repository(tmp_path, "holder")
    implementation, _branch = work.create_implementation_root(holder, "example/product", 12, None, "holder-session")
    (implementation / "job.md").write_bytes(b"consumer surface\n")
    (implementation / "SKILL.md").write_bytes(b"loading surface\n")
    git(implementation, "add", "job.md", "SKILL.md")
    git(implementation, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com", "commit", "-m", "consumer")
    metadata = work.recipient_tree.create_consumer_tree(
        source=implementation, output=tmp_path / "trees" / "consumer", work="example/product#12",
        producer_version=work.records.producer_version(), mode="adopter", paths=["job.md"],
        loading_surfaces=["SKILL.md"], front_page=None, root_instructions=None,
        directed_paths=[], exclusions=[], deny_texts=[], records_home=home / ".tradecraft")
    dispatch = tmp_path / "use-job.md"
    dispatch.write_bytes(b"Use the result and return a session note.\n")
    launches = capture_seat(monkeypatch)
    monkeypatch.setattr(work, "_runtime_argument", lambda vendor: [f"--{vendor}", f"/{vendor}-fixture"])
    fixture = state(AFFIRMED, pr=True, draft=False)
    with slow_entrance("use", 1800, 500) as deadline:
        assert work.execute_stage(fixture, work.Decision("use", True, "fresh", "holder-named-stage"), holder, None,
                                  dispatch_path=dispatch, tree_metadata=metadata, timeout_seconds=1800,
                                  floor_command="python fixture-check.py") == 0
    [command] = launches
    seat = seat_window(command, deadline)
    assert seat.allotted == 1800 and seat.remaining() >= 1799
