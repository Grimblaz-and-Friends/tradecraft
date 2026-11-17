"""Every report carries the run's timing split, and a launched stage's line after the return carries it to the spawn."""
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import preflight
import work
from test_work import AFFIRMED, state
from version_fixture import REPO, adopted_repository, fixture_state

PARTS = ("github", "removals", "markers", "launch_preparation", "vendor", "unattributed")
D = 2.0


def split_lines(text):
    """The `preflight` objects in printed JSON lines, in order."""
    found = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("work: preflight "):
            found.append(json.loads(line.removeprefix("work: preflight ")))
            continue
        if not line.startswith("{"):
            continue
        value = json.loads(line)
        if isinstance(value, dict) and isinstance(value.get("preflight"), dict):
            found.append(value["preflight"])
    return found


def assert_sums(split):
    # The parts and the unattributed remainder sum to the total within one second.
    assert set(split["parts"]) == {f"{name}_seconds" for name in PARTS}
    assert abs(sum(split["parts"].values()) - split["total_seconds"]) <= 1


def launcher(store, *, vendor_delay=0.0):
    """A fake launcher: continues the entrance's split from the handoff and writes its bundle into the store."""
    written = {}

    def run(command, **_kwargs):
        def argument(name):
            return command[command.index(name) + 1]
        seed = preflight.load_handoff(Path(argument("--preflight-input")))
        assert seed is not None
        scope = preflight.Scope(seed=seed)
        dispatch_id = uuid.uuid4().hex
        request = work.records.request_record(
            dispatch_id=dispatch_id, work=argument("--work"), stage=argument("--stage"),
            settings_source="fixture", settings_scope="implementer", vendor="claude", model="fixture",
            effort="fixture", continuity="fresh", permission_boundary="fixture", root=None)
        request["preflight"] = scope.snapshot("request-record")
        folder = store / f"fixture-{dispatch_id}"
        folder.mkdir(parents=True)
        (folder / "result.md.request.json").write_text(json.dumps(request), encoding="utf-8")
        mark = scope.mark()
        if vendor_delay:
            with_part(scope, "vendor", vendor_delay)
        seconds, parts = scope.since(mark)
        attempt = {"vendor": "claude", "pre_spawn_seconds": seconds, "pre_spawn_parts": parts}
        run_record = {"schema_version": work.records.SCHEMA_VERSION, "dispatch_id": dispatch_id,
                      "attempts": [attempt]}
        (folder / "result.md.run.json").write_text(json.dumps(run_record), encoding="utf-8")
        written.update(request=request, attempt=attempt)
        return subprocess.CompletedProcess(command, 0)
    return run, written


def with_part(scope, name, seconds):
    scope.enter(name)
    try:
        time.sleep(seconds)
    finally:
        scope.leave()


def once(original, seconds):
    """Wrap `original` so its first call sleeps `seconds` inside whatever part encloses it."""
    calls = []

    def wrapped(*args, **kwargs):
        if not calls and seconds:
            time.sleep(seconds)
        calls.append(True)
        return original(*args, **kwargs)
    return wrapped


def launched_build(monkeypatch, tmp_path, read_output, delayed=None, seconds=D):
    """Drive a named `run build` through `execute_stage` to a fake launcher; return what it printed after the return."""
    delays = {name: seconds if name == delayed else 0.0 for name in PARTS}
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    fixture = state(AFFIRMED)
    store = work.records.default_record_root().expanduser().resolve()
    root = tmp_path / "implementation"
    root.mkdir(parents=True)
    monkeypatch.setattr(work, "_dispatch_root", lambda *_a, **_k: (root, None, False))
    monkeypatch.setattr(work, "_runtime_argument", lambda vendor, explicit=None: [f"--{vendor}", "fixture"])
    # Each delay lands inside the code its part covers.
    probe = work._run_probe

    def transport(command, **kwargs):
        # GitHub answers through a fake transport; every other probe runs as it would.
        if command[0] != "gh":
            return probe(command, **kwargs)
        time.sleep(delays["github"])
        return subprocess.CompletedProcess(command, 0, b"{}", b"")
    monkeypatch.setattr(work, "_run_probe", transport)
    monkeypatch.setattr(work, "_evaluate_reach_in_part", once(work._evaluate_reach_in_part, delays["removals"]))
    monkeypatch.setattr(work, "_validate_marker_claims", once(work._validate_marker_claims, delays["markers"]))
    monkeypatch.setattr(work, "_stage_prompt", once(work._stage_prompt, delays["launch_preparation"]))
    fake, written = launcher(store, vendor_delay=delays["vendor"])

    def recipient(command, **kwargs):
        read_output()  # Everything printed before the return is not the line after it.
        return fake(command, **kwargs)
    monkeypatch.setattr(work, "_recipient_run", recipient)
    decision = work.Decision("build", True, "fresh", "holder-named-stage")
    with preflight.scope():
        # The entrance's state read goes through GitHub before the decision.
        work.GitHubREST().get(f"repos/{fixture.repo}/issues/{fixture.issue_number}")
        assert work.execute_stage(fixture, decision, tmp_path, None, "holder",
                                  floor_command="python fixture-check.py") == 0
    return read_output(), written


def after_return_split(printed):
    splits = split_lines(printed)
    assert splits, f"no preflight in the output after the return: {printed!r}"
    return splits[-1]


def test_978_post_return_split(tmp_path, monkeypatch, capsys):
    printed, written = launched_build(monkeypatch, tmp_path, lambda: capsys.readouterr().out)
    split = after_return_split(printed)
    assert split["until"] == "spawn"
    assert_sums(split)
    record = written["request"]["preflight"]
    assert record["until"] == "request-record"
    assert_sums(record)
    attempt = written["attempt"]
    assert abs(sum(attempt["pre_spawn_parts"].values()) - attempt["pre_spawn_seconds"]) <= 1
    assert abs(split["total_seconds"] - (record["total_seconds"] + attempt["pre_spawn_seconds"])) <= 1
    assert split == preflight.combine(record, attempt["pre_spawn_seconds"], attempt["pre_spawn_parts"])


def test_978_post_return_split_without_a_split_falls_back_to_the_report(tmp_path, monkeypatch, capsys):
    """An old launcher's bundle carries no split: the line after the return carries the report's own."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    fixture = state(AFFIRMED)
    root = tmp_path / "implementation"
    root.mkdir()
    monkeypatch.setattr(work, "_dispatch_root", lambda *_a, **_k: (root, None, False))
    monkeypatch.setattr(work, "_runtime_argument", lambda vendor, explicit=None: [f"--{vendor}", "fixture"])

    def recipient(command, **_kwargs):
        capsys.readouterr()
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(work, "_recipient_run", recipient)
    with preflight.scope():
        assert work.execute_stage(fixture, work.Decision("build", True, "fresh", "holder-named-stage"),
                                  tmp_path, None, "holder", floor_command="python fixture-check.py") == 0
    split = after_return_split(capsys.readouterr().out)
    assert split["until"] == "report"
    assert_sums(split)


def test_978_refusal_split(tmp_path, monkeypatch, capsys):
    transport = fixture_state()[1]
    root = tmp_path / "adopter"
    adopted_repository(root)
    monkeypatch.setattr(work, "GitHubREST", lambda: transport)
    # `run use` without a job refuses, through `work.main` as a holder runs it.
    assert work.main(["run", "use", "--repo", REPO, "--issue", "12", "--root", str(root)]) == 0
    reports = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    assert reports[-1]["reason"] == "use-requires-holder-job-and-tree"
    split = reports[-1]["preflight"]
    assert split["until"] == "report"
    assert_sums(split)

    # The refusal path through `work.main`'s exception handler, with and without a report.
    def refuse(*_args, **_kwargs):
        error = work.WorkError("fixture refusal")
        error.raw_output = {"status": "clean"}
        raise error
    monkeypatch.setattr(work, "_run", refuse)
    assert work.main(["run", "build", "--repo", REPO, "--issue", "12", "--root", str(root)]) == 1
    captured = capsys.readouterr()
    reported = json.loads(captured.out)
    assert reported["status"] == "refused" and reported["reason"] == "fixture refusal"
    assert_sums(reported["preflight"])
    printed = split_lines(captured.err)
    assert len(printed) == 1 and printed[0]["until"] == "report"
    assert_sums(printed[0])

    def plain(*_args, **_kwargs):
        raise work.WorkError("fixture refusal without a report")
    monkeypatch.setattr(work, "_run", plain)
    assert work.main(["run", "build", "--repo", REPO, "--issue", "12", "--root", str(root)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    printed = split_lines(captured.err)
    assert len(printed) == 1
    assert_sums(printed[0])


def test_978_decide_split(tmp_path, monkeypatch, capsys):
    transport = fixture_state()[1]
    root = tmp_path / "adopter"
    adopted_repository(root)
    monkeypatch.setattr(work, "GitHubREST", lambda: transport)
    assert work.main(["--repo", REPO, "--issue", "12", "--root", str(root)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert "stage" in report and "dispatch" in report
    split = report["preflight"]
    assert split["until"] == "report"
    assert_sums(split)


@pytest.mark.parametrize("delayed", ["github", "removals", "markers", "launch_preparation", "vendor"])
def test_978_split_attributes_delay(tmp_path, monkeypatch, capsys, delayed):
    """A delay of D in one part shows in that part, read in the line after the return, and not in another."""
    read = lambda: capsys.readouterr().out  # noqa: E731
    with monkeypatch.context() as undelayed:
        baseline = after_return_split(launched_build(undelayed, tmp_path / "baseline", read)[0])
    split = after_return_split(launched_build(monkeypatch, tmp_path / "delayed", read, delayed)[0])
    assert baseline["until"] == split["until"] == "spawn"
    assert_sums(split)
    for name in PARTS:
        grown = split["parts"][f"{name}_seconds"] - baseline["parts"][f"{name}_seconds"]
        if name == delayed:
            # Both figures are rounded to hundredths, and the part's own undelayed work varies
            # between the two runs by a few hundredths, so the growth is read within that.
            assert grown >= D - 0.05, (name, baseline, split)
        else:
            assert grown < D / 2, (name, delayed, baseline, split)
