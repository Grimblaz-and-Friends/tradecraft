"""Starting a process nobody waits on, its output in files."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import textwrap
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import detached  # noqa: E402
import keep_warm  # noqa: E402

# Writes its start, then its end a few seconds later, so a caller that waited is seen.
CHILD = textwrap.dedent("""
    import os, sys, time
    open(sys.argv[1], "w").write(os.getcwd() + "|" + os.environ.get("DETACHED_PASSED", ""))
    print("to stdout", flush=True)
    print("to stderr", file=sys.stderr, flush=True)
    time.sleep(3)
    open(sys.argv[2], "w").write("done")
""")


def wait_for(path: Path, seconds: float = 30) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end and not (path.exists() and path.read_text()):
        time.sleep(0.25)
    assert path.exists(), f"{path.name} never appeared"


def test_1011_spawn_returns_before_its_child_ends(tmp_path):
    started, done = tmp_path / "started.txt", tmp_path / "done.txt"
    out, err = tmp_path / "out.log", tmp_path / "err.log"
    env = {**os.environ, "DETACHED_PASSED": "yes"}
    begin = time.monotonic()
    detached.spawn([sys.executable, "-B", "-c", CHILD, str(started), str(done)], cwd=tmp_path, env=env,
                   stdout=out, stderr=err)
    assert time.monotonic() - begin < 2.5
    assert not done.exists()
    wait_for(done)
    cwd, passed = started.read_text().split("|")
    assert os.path.samefile(cwd, tmp_path) and passed == "yes"
    assert out.read_text().strip() == "to stdout"
    assert err.read_text().strip() == "to stderr"


def test_1011_one_file_named_for_both_streams_holds_both(tmp_path):
    started, done, log = tmp_path / "started.txt", tmp_path / "done.txt", tmp_path / "both.log"
    detached.spawn([sys.executable, "-B", "-c", CHILD, str(started), str(done)], cwd=tmp_path,
                   stdout=log, stderr=log)
    wait_for(done)
    assert log.read_text().split() == ["to", "stdout", "to", "stderr"]


@pytest.mark.parametrize("windows", [True, False])
def test_1011_spawn_picks_the_platform_starter(monkeypatch, tmp_path, windows):
    seen = []
    monkeypatch.setattr(detached, "WINDOWS", windows)
    monkeypatch.setattr(detached, "windows_spawn", lambda argv, cwd, env: seen.append(("nt", argv, cwd)) or 7)
    monkeypatch.setattr(detached, "posix_spawn",
                        lambda argv, cwd, env, **streams: seen.append(("posix", argv, cwd, streams)) or 0)
    detached.spawn(["tool", "a"], cwd=tmp_path, env={"A": "1"})
    detached.spawn(["tool", "a"], cwd=tmp_path, env={"A": "1"}, stdout=tmp_path / "o")
    if windows:
        assert seen[0] == ("nt", ["tool", "a"], tmp_path)
        assert seen[1][1][3] == detached.DETACH_TO_FILES and seen[1][1][-2:] == ["tool", "a"]
        assert seen[1][1][4:7] == [str(tmp_path), str(tmp_path / "o"), ""]
    else:
        assert seen[0] == ("posix", ["tool", "a"], tmp_path, {"stdout": None, "stderr": None})
        assert seen[1][3] == {"stdout": tmp_path / "o", "stderr": None}


def test_1011_keep_warm_reports_a_failed_start_as_its_own(monkeypatch, tmp_path):
    def refused(*_args):
        raise detached.DetachError("starter exited 1")
    monkeypatch.setattr(keep_warm, "_windows_spawn", refused)
    monkeypatch.setattr(keep_warm, "_posix_spawn", refused)
    with pytest.raises(keep_warm.KeepWarmError, match="starter exited 1"):
        keep_warm.spawn(["x"], tmp_path, {})
