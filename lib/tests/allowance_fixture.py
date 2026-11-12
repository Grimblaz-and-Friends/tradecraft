"""One step of a launch's comparison forced slow, for the comparison allowance checks.

Both launchers' tests use it: a covered folder whose files change during the
run, another run overlapping it, and the moments the allowance and the final
record write ended.
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import time

import dispatch_lifecycle
import dispatch_record as records
import launch_bound

OTHER = "b" * 32
# Sorted as compared: one under no run's root, one under the overlapping run's, two after.
NAMES = ("a.txt", "b/f.txt", "c.txt", "d.txt")


def git(cwd, *arguments):
    return subprocess.run(["git", "-C", str(cwd), *arguments], capture_output=True, check=True,
                          stdin=subprocess.DEVNULL)


class Slow:
    """Covered folders that change during the run, and what the comparison and record did."""

    def __init__(self, monkeypatch, tmp_path, *, folders=1, seconds=None, branch=False):
        self.monkeypatch = monkeypatch
        self.tops = [tmp_path / f"covered-{index}" for index in range(folders)]
        for top in self.tops:
            for name in NAMES:
                (top / name).parent.mkdir(parents=True, exist_ok=True)
                (top / name).write_bytes(b"x")
        self.items = ["checkout:" + str(top) for top in self.tops]
        store = records.default_record_root()
        store.mkdir(parents=True, exist_ok=True)
        launched = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        (store / "other.md.request.json").write_text(json.dumps(
            {"dispatch_id": OTHER, "root": str(self.tops[0] / "b"), "launched_at": launched}),
            encoding="utf-8")
        (store / "other.md.run.json").write_text(json.dumps(
            {"completed_at": None, "elapsed_checkpoint_seconds": 99999}), encoding="utf-8")
        self.registry = launch_bound.registry_path(Path.home())
        self.registry.parent.mkdir(parents=True, exist_ok=True)
        self.registry.write_bytes(b'{"schema_version": 1, "worktrees": []}')
        self.repo = None
        if branch:
            self.repo = tmp_path / "product"
            self.repo.mkdir()
            git(self.repo, "init", "-q", "-b", "trunk")
            git(self.repo, "-c", "user.name=t", "-c", "user.email=t@x", "commit", "--allow-empty", "-q",
                "-m", "base")
        if seconds is not None:
            monkeypatch.setattr(launch_bound, "COMPARING_SECONDS", seconds)
        self.end = None
        self.deadline = None
        self.written = None
        self._wrap()

    def _wrap(self):
        tops, repo = self.tops, self.repo
        init, snapshot = launch_bound.Comparison.__init__, launch_bound.snapshot
        compare, finish = launch_bound.compare, dispatch_lifecycle.GrowingRun.finish
        slow = self

        def covered(comparison, **kwargs):
            init(comparison, **kwargs)
            comparison.plan += [{"item": "checkout:" + str(top), "path": str(top), "method": "checkout"}
                                for top in tops]
            if repo is not None:
                comparison.plan += launch_bound.refs_plan(repo, [])

        def changed(plan, **kwargs):
            if kwargs.get("before") is not None:
                for top in tops:
                    for name in NAMES:
                        (top / name).write_bytes(b"changed")
                # A change no other run could account for, found without the store.
                slow.registry.write_bytes(b'{"schema_version": 1,  "worktrees": []}')
                if repo is not None:
                    git(repo, "branch", "loose-x")
            return snapshot(plan, **kwargs)

        def bounded(*args, **kwargs):
            slow.end = kwargs.get("end")
            slow.deadline = launch_bound.lifecycle.current_deadline()
            return compare(*args, **kwargs)

        def written(run):
            finish(run)
            slow.written = time.monotonic()

        self.monkeypatch.setattr(launch_bound.Comparison, "__init__", covered)
        self.monkeypatch.setattr(launch_bound, "snapshot", changed)
        self.monkeypatch.setattr(launch_bound, "compare", bounded)
        self.monkeypatch.setattr(dispatch_lifecycle.GrowingRun, "finish", written)

    def _past_end(self):
        time.sleep(max(0.0, self.end - time.monotonic()) + 0.2)

    def slow_crediting(self):
        """Crediting the second change of the first folder outlasts the allowance."""
        attribute, seen = launch_bound._attribute, []

        def slow(change, live, holder):
            owner = attribute(change, live, holder)
            if change["item"] == self.items[0]:
                seen.append(change["path"])
                if len(seen) == 2:
                    self._past_end()
            return owner

        self.monkeypatch.setattr(launch_bound, "_attribute", slow)

    def slow_store(self, pause=None):
        """Each run record read pauses; without ``pause``, the first outlasts the allowance."""
        read = launch_bound._recorded_run

        def slow(path, own):
            if pause is None:
                self._past_end()
            else:
                time.sleep(pause)
            return read(path, own)

        self.monkeypatch.setattr(launch_bound, "_recorded_run", slow)

    def slow_stream(self):
        """The read of the run's stream outlasts the allowance before its first line is checked."""
        read = launch_bound.read_run_record

        def slow(path, **kwargs):
            self._past_end()
            return read(path, **kwargs)

        self.monkeypatch.setattr(launch_bound, "read_run_record", slow)

    def coverage(self, comparison, item):
        return next(entry for entry in comparison["coverage"] if entry["item"] == item)

    def finding(self, comparison, item, name):
        path = str(Path(item.removeprefix("checkout:")) / name)
        return [f for f in comparison["findings"] if f["item"] == item and f["path"] == path]

    def credited(self, comparison, item):
        return [Path(a["path"]).relative_to(item.removeprefix("checkout:")).as_posix()
                for a in comparison["attributed"] if a["item"] == item]


def check_expired(slow, logged, step):
    """The final record is written soon after the allowance, completed and honest about it."""
    assert logged["lifecycle"] == "completed" and logged["completed_at"]
    assert slow.written is not None and slow.written - slow.end < 5
    comparison = logged["launch_comparison"]
    assert comparison["status"] == "findings"
    assert comparison["run_record"]["status"] == "not-read", json.dumps(comparison, indent=1)
    item = slow.items[0]
    entry = slow.coverage(comparison, item)
    uncompared = {f["item"]: f for f in comparison["findings"] if f["change"] == "uncompared"}
    if step == "stream":
        # The path changes were all examined before the stream read began.
        assert entry["status"] == "compared"
        assert slow.credited(comparison, item) == ["b/f.txt"]
        assert all(slow.finding(comparison, item, name) for name in ("a.txt", "c.txt", "d.txt"))
        [refs] = [e for e in comparison["coverage"] if e["item"].startswith("refs:")
                  and e["status"] == "uncompared"]
        assert "comparison allowance ran out" in refs["reason"]
        assert "0 of 1 changes examined" in refs["reason"] and refs["item"] in uncompared
        assert not any(e.get("branch") == "loose-x" for e in comparison["listed"] + comparison["findings"])
        return
    done = {"crediting": 2, "store": 0}[step]
    assert entry["status"] == "uncompared"
    assert "comparison allowance ran out" in entry["reason"]
    assert f"{done} of 4 changes examined" in entry["reason"]
    assert uncompared[item]["reason"] == entry["reason"]
    # No unexamined change is credited or found as itself.
    for name in NAMES[done:]:
        assert not slow.finding(comparison, item, name)
    if step == "crediting":
        assert slow.finding(comparison, item, "a.txt") and slow.credited(comparison, item) == ["b/f.txt"]
    else:
        assert slow.credited(comparison, item) == []
    # A finding made without the store, before the limit, is still listed.
    assert [f["change"] for f in comparison["findings"] if f["item"] == "registry"] == ["modified"]
