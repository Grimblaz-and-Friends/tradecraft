"""The holder pane's core, installer and shim, checked against the settled artifact (#888).

Lab-only: CI does not collect this directory. Run it as
`python -m pytest tools/holder_pane/tests -q`.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
PANE = HERE.parent
PLUGIN = PANE / "marketplace" / "holder-pane"
REPO = PANE.parent.parent
REGISTER = PLUGIN / "hooks" / "register.ts"
README = PANE / "README.md"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


core = _load("holder_pane_core", PLUGIN / "core" / "holder_pane.py")
installer = _load("holder_pane_install", PANE / "install.py")

REPO_NAME = "Grimblaz-and-Friends/tradecraft"
SID = "11111111-2222-3333-4444-555555555555"
T0 = 1_800_000_000.0


class Entrance:
    """A fake entrance: logs each run and answers a fixed decision."""

    def __init__(self, decision: dict | None = None):
        self.calls: list[list[str]] = []
        self.decision = decision or {"stage": "waiting", "status": "waiting",
                                     "reason": "latest-check-run-pending", "floor": None}

    def __call__(self, argv, **kwargs):
        assert kwargs.get("stdin") is subprocess.DEVNULL and kwargs.get("capture_output") is True
        self.calls.append(list(argv))
        return SimpleNamespace(returncode=0, stdout=json.dumps(self.decision), stderr="")


@pytest.fixture
def home(tmp_path):
    root = tmp_path / "home"
    (root / ".tradecraft" / "dispatches").mkdir(parents=True)
    return root


def ctx_at(home: Path, now: float, runner=None, environ=None):
    return core.Ctx(home=home, now=now, runner=runner or Entrance(),
                    environ=environ if environ is not None else {})


def allow_title(title: str, source: str | None = None) -> dict:
    body = {"sessionId": "local_x", "title": title}
    if source is not None:
        body["titleSource"] = source
    return {"decision": "allow", "text": json.dumps(body)}


RUN_BUILD = (f"python launch_stage.py build1 -- run build --repo {REPO_NAME} --issue 888 "
             f"--root D:/Code/tradecraft/.claude/worktrees/start-888")


def bind(home: Path, now: float = T0, title=None, command: str = RUN_BUILD, output: str = ""):
    return core.observe(ctx_at(home, now), {
        "session_id": SID, "command": command, "output": output,
        "started_at": now - 1, "ended_at": now, "title": title or allow_title("Start 888", "auto"),
    })


def write_bundle(home: Path, name: str, *, stage: str, launched: float, lifecycle: str,
                 work: str = f"{REPO_NAME}#888", limit: float | None = 7200.0,
                 dispatch_id: str = "d1", log_mtime: float | None = None) -> Path:
    directory = home / ".tradecraft" / "dispatches" / name
    directory.mkdir(parents=True, exist_ok=True)
    stdout = directory / "result.md.claude.stdout.log"
    stdout.write_bytes(b"")
    if log_mtime is not None:
        os.utime(stdout, (log_mtime, log_mtime))
    from datetime import datetime, timezone
    request = {"work": work, "stage": stage, "dispatch_id": dispatch_id,
               "launched_at": datetime.fromtimestamp(launched, tz=timezone.utc).isoformat(),
               "caller_limit_seconds": limit, "stage_ceiling_seconds": 9000.0}
    (directory / "result.md.request.json").write_text(json.dumps(request), encoding="utf-8")
    run = {"dispatch_id": dispatch_id, "lifecycle": lifecycle,
           "attempts": [{"stdout": str(stdout), "stderr": str(directory / "missing.log")}]}
    (directory / "result.md.run.json").write_text(json.dumps(run), encoding="utf-8")
    return directory


def tick(home: Path, now: float, title=None, runner=None):
    return core.tick(ctx_at(home, now, runner), {
        "session_id": SID, "title": title if title is not None else allow_title("Start 888", "auto")})


def remind(home: Path, now: float, active: bool = False):
    return core.remind(ctx_at(home, now), {"session_id": SID, "stop_hook_active": active})["block"]


def tree_files(root: Path) -> set[str]:
    return {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}


# --- row 2: binding and inertness -------------------------------------------------------

def test_c2_3_unbound_session_reads_and_writes_nothing(home):
    before = tree_files(home)
    runner = Entrance()
    ctx = ctx_at(home, T0, runner)
    assert core.recover(ctx, SID, str(home)) is None
    assert core.read(ctx, {"session_id": SID}) == {"ran": False, "why": "unbound"}
    assert core.tick(ctx, {"session_id": SID, "title": allow_title("Steward", "tool")}) == {
        "bound": False}
    assert core.remind(ctx, {"session_id": SID, "stop_hook_active": False}) == {"block": None}
    assert core.observe(ctx, {"session_id": SID, "command": "git status", "output": "",
                              "title": allow_title("Steward")}) == {"bound": False}
    assert runner.calls == []
    assert tree_files(home) == before
    assert not (home / ".tradecraft" / "status").exists()


def test_c2_4_steward_title_never_binds(home):
    assert bind(home, title=allow_title("  steward ", "tool")) == {"bound": False}
    assert not core.binding_path(ctx_at(home, T0), SID).exists()
    # A bound session later titled Steward becomes unbound and is never renamed.
    assert bind(home)["bound"] is True
    assert tick(home, T0 + 60, title=allow_title("Steward", "tool")) == {"bound": False}
    assert not core.binding_path(ctx_at(home, T0), SID).exists()


def test_c2_4_unreadable_title_binds_but_never_renames(home):
    assert bind(home, title={"decision": "ask", "text": None})["bound"] is True
    for offset in (60, 120):
        answer = tick(home, T0 + offset, title={"decision": "ask", "text": None})
        assert answer["rename"] is None
        assert answer["view"]["rename_note"] == "rename skipped (title source unknown)"


def test_c2_5_detached_wrapper_binds_and_read_only_does_not(home):
    parsed = core.parse_entrance_call(
        f"python launch_stage.py artifact1 -- run artifact --repo {REPO_NAME} --issue 888 "
        f"--root D:/Code/x")
    assert parsed == {"verb": "run", "stage": "artifact", "repository": REPO_NAME,
                      "issue": 888, "root": "D:/Code/x", "entrance": None}
    named = core.parse_entrance_call(
        f'python "C:/p/lib/work.py" run build --repo {REPO_NAME} --issue 888 --root D:/x')
    assert named["entrance"] == "C:/p/lib/work.py"
    assert core.parse_entrance_call(
        f"python C:/p/lib/work.py --repo {REPO_NAME} --issue 888 --root D:/x") is None
    assert core.observe(ctx_at(home, T0), {
        "session_id": SID, "command": f"python lib/work.py --repo {REPO_NAME} --issue 888 "
                                      f"--root D:/x", "output": "{}"}) == {"bound": False}
    assert bind(home)["bound"] is True


def test_c2_6_restart_recovery_binds_exactly_one_registry_row(home, tmp_path):
    holder_root = tmp_path / "holder"
    holder_root.mkdir()
    registry = home / ".tradecraft" / "implementation-worktrees.json"

    def rows(*items):
        registry.write_text(json.dumps({"schema_version": 1, "worktrees": list(items)}),
                            encoding="utf-8")

    row = {"repository": REPO_NAME, "issue": 888, "active": True,
           "holder_session_id": SID, "holder_root": str(holder_root)}
    rows(row)
    found = core.recover(ctx_at(home, T0), SID, str(holder_root))
    assert (found["repository"], found["issue"]) == (REPO_NAME, 888)
    rows()
    assert core.recover(ctx_at(home, T0), SID, str(holder_root)) is None
    rows(row, {**row, "issue": 889})
    assert core.recover(ctx_at(home, T0), SID, str(holder_root)) is None
    rows({**row, "active": False})
    assert core.recover(ctx_at(home, T0), SID, str(holder_root)) is None


# --- row 2 / row 8: the installer -------------------------------------------------------

class FakeTools:
    """git answers from a fixture; claude records argv."""

    def __init__(self, tracked=False, ignored=True):
        self.tracked, self.ignored = tracked, ignored
        self.claude: list[list[str]] = []

    def __call__(self, argv, **kwargs):
        assert kwargs.get("stdin") is subprocess.DEVNULL and kwargs.get("capture_output") is True
        if argv[0] == "git":
            if "ls-files" in argv:
                return SimpleNamespace(returncode=0 if self.tracked else 1, stdout=b"", stderr=b"")
            if "check-ignore" in argv:
                return SimpleNamespace(returncode=0 if self.ignored else 1, stdout=b"", stderr=b"")
            raise AssertionError(argv)
        self.claude.append(list(argv))
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / "checkout"
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "settings.local.json").write_text(
        json.dumps({"permissions": {"allow": ["Bash(ls)"]}}), encoding="utf-8")
    return root


def test_c2_1_install_and_uninstall_stay_local(checkout, home):
    user_settings = home / ".claude" / "settings.json"
    user_settings.parent.mkdir(parents=True)
    user_settings.write_bytes(b'{"theme": "dark"}\n')
    before = user_settings.read_bytes()
    original = json.loads((checkout / ".claude" / "settings.local.json").read_text())
    tools = FakeTools()
    installer.install(checkout, Path("claude.exe"), tools, marketplace=Path("M"))
    local = json.loads((checkout / ".claude" / "settings.local.json").read_text())
    assert local["env"] == {"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"}
    assert local["permissions"] == original["permissions"]
    installer.uninstall(checkout, Path("claude.exe"), tools)
    assert json.loads((checkout / ".claude" / "settings.local.json").read_text()) == original
    assert user_settings.read_bytes() == before
    assert [argv[1:] for argv in tools.claude] == [
        ["plugin", "marketplace", "add", "M", "--scope", "local"],
        ["plugin", "install", "holder-pane@tradecraft-lab", "--scope", "local"],
        ["plugin", "uninstall", "holder-pane@tradecraft-lab", "--scope", "local"],
        ["plugin", "marketplace", "remove", "tradecraft-lab", "--scope", "local"],
    ]
    assert all(argv[-2:] == ["--scope", "local"] for argv in tools.claude)


@pytest.mark.parametrize("tracked,ignored", [(True, True), (True, False), (False, False)])
def test_c2_2_install_refuses_tracked_or_unignored_local_file(checkout, tracked, ignored):
    path = checkout / ".claude" / "settings.local.json"
    before = path.read_bytes()
    tools = FakeTools(tracked=tracked, ignored=ignored)
    with pytest.raises(installer.Refused):
        installer.install(checkout, Path("claude.exe"), tools)
    assert path.read_bytes() == before
    assert tools.claude == []


def test_c2_7_worktree_install_copies_keys_under_the_same_refusal(checkout, tmp_path):
    main_local = checkout / ".claude" / "settings.local.json"
    main_local.write_text(json.dumps({
        "extraKnownMarketplaces": {"tradecraft-lab": {"source": {"source": "directory",
                                                                  "path": "M"}}},
        "enabledPlugins": {"holder-pane@tradecraft-lab": True, "other@x": True},
        "env": {"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"}}), encoding="utf-8")
    worktree = tmp_path / "wt"
    (worktree / ".claude").mkdir(parents=True)
    installer.install_worktree(worktree, checkout, FakeTools())
    copied = json.loads((worktree / ".claude" / "settings.local.json").read_text())
    assert copied["enabledPlugins"] == {"holder-pane@tradecraft-lab": True}
    assert "tradecraft-lab" in copied["extraKnownMarketplaces"]
    assert copied["env"]["CLAUDE_CODE_ENABLE_FUNCTION_HOOKS"] == "1"
    with pytest.raises(installer.Refused):
        installer.install_worktree(tmp_path / "wt", checkout, FakeTools(tracked=True))


# --- row 3: the read floor ------------------------------------------------------------------

def bound_for_reads(home, tmp_path):
    entrance = tmp_path / "work.py"
    entrance.write_text("", encoding="utf-8")
    command = (f"python {entrance.as_posix()}/../lib/work.py run proof --repo {REPO_NAME} "
               f"--issue 888 --root D:/root")
    assert bind(home, command=command, output="")["bound"] is True
    path = core.binding_path(ctx_at(home, T0), SID)
    binding = json.loads(path.read_text())
    binding["entrance"] = str(entrance)
    path.write_text(json.dumps(binding), encoding="utf-8")
    return entrance


def test_c3_1_floor_and_single_flight_across_sessions(home, tmp_path):
    entrance = bound_for_reads(home, tmp_path)
    other = "99999999-0000-0000-0000-000000000000"
    other_binding = json.loads(core.binding_path(ctx_at(home, T0), SID).read_text())
    core._write_json(core.binding_path(ctx_at(home, T0), other), {**other_binding,
                                                                   "session_id": other})
    runner = Entrance()
    for step in range(50):
        now = T0 + step * 84  # 50 triggers over 70 minutes
        session = SID if step % 2 == 0 else other
        core.read(core.Ctx(home=home, now=now, runner=runner, environ={}), {"session_id": session})
    assert len(runner.calls) == 2
    assert runner.calls[0] == [sys.executable, str(entrance), "--repo", REPO_NAME, "--issue",
                               "888", "--root", "D:/root"]
    # A held lock blocks a start; a stale one is replaced.
    key = core.change_key(REPO_NAME, 888)
    later = T0 + 10_000
    lock = core.lock_path(ctx_at(home, later), key)
    lock.write_text(json.dumps({"pid": 1, "started_at": later - 60}), encoding="utf-8")
    assert core.read(ctx_at(home, later, runner), {"session_id": SID})["why"] == "locked"
    lock.write_text(json.dumps({"pid": 1, "started_at": later - 700}), encoding="utf-8")
    assert core.read(ctx_at(home, later, runner), {"session_id": SID})["ran"] is True
    assert len(runner.calls) == 3 and not lock.exists()
    # Nothing runs after a terminal reading.
    runner.decision = {"stage": "merged-pull-request", "status": "holder-owned",
                       "reason": "merged"}
    assert core.read(ctx_at(home, later + 3000, runner), {"session_id": SID})["ran"] is True
    assert core.read(ctx_at(home, later + 9000, runner), {"session_id": SID})["why"] == "stopped"
    assert len(runner.calls) == 4


def test_c3_1_failed_read_counts_against_the_floor(home, tmp_path):
    bound_for_reads(home, tmp_path)

    def broken(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, 540)

    assert core.read(ctx_at(home, T0, broken), {"session_id": SID}) == {"ran": True, "ok": False}
    assert core.read(ctx_at(home, T0 + 100, Entrance()), {"session_id": SID})["why"] == "floor"
    assert tick(home, T0 + 120)["view"]["read_failed_at"] == T0


def test_c3_2_only_subprocess_is_the_entrance(home, tmp_path, monkeypatch):
    bound_for_reads(home, tmp_path)
    seen = []

    def fake(argv, **kwargs):
        seen.append(argv)
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("Popen"))
    ctx = core.Ctx(home=home, now=T0, environ={})
    core.read(ctx, {"session_id": SID})
    tick(home, T0 + 1)
    remind(home, T0 + 2)
    assert len(seen) == 1 and seen[0][2:] == ["--repo", REPO_NAME, "--issue", "888",
                                               "--root", "D:/root"]


def test_c3_3_read_returns_at_once_when_refused(home, tmp_path):
    bound_for_reads(home, tmp_path)
    runner = Entrance()
    core.read(ctx_at(home, T0, runner), {"session_id": SID})
    assert core.read(ctx_at(home, T0 + 1, runner), {"session_id": SID}) == {
        "ran": False, "why": "floor"}
    assert len(runner.calls) == 1


RELEASE_REPORT_OUTPUT = json.dumps({
    "stage": "release-report", "status": "holder-owned",
    "reason": "all-evidence-complete-release-report-ready", "dispatch": False,
    "synchronization": {"pull_request": 900}, "floor": {"outcome": "ci-met", "satisfied": True,
                                                        "head": "abc"},
    "required_gate": {"verdict": "green", "head": "abc"},
})


def test_c3_4_holder_only_stage_return_reads_its_own_output(home):
    runner = Entrance()
    command = f"python lib/work.py run release-report --repo {REPO_NAME} --issue 888 --root D:/r"
    assert bind(home, command=command, output="noise\n" + RELEASE_REPORT_OUTPUT)["bound"]
    view = tick(home, T0 + 5, runner=runner)["view"]
    assert runner.calls == []
    assert view["next_step"] == "post the release report"
    assert view["waiting_on"] == "holder" and view["source"] == "stage-return"
    assert view["gate"] == "green" and view["floor"] == {"outcome": "ci-met", "satisfied": True}


def test_c3_5_detached_dispatch_reads_running_until_its_bundle_returns(home):
    write_bundle(home, "other-change", stage="build", launched=T0, lifecycle="running",
                 work=f"{REPO_NAME}#1", dispatch_id="x")
    assert bind(home, output="12345\n")["bound"]
    view = tick(home, T0 + 1)["view"]
    assert view["record_pending"] is True and view["label"] == "build running"
    assert remind(home, T0 + 2) is None
    bundle = write_bundle(home, "b1", stage="build", launched=T0, lifecycle="running",
                          dispatch_id="d-888")
    view = tick(home, T0 + 70)["view"]
    assert view["waiting_on"] == "builder" and view["label"] == "build running"
    assert view["running"] is not None
    assert remind(home, T0 + 71) is None
    run = json.loads((bundle / "result.md.run.json").read_text())
    run["lifecycle"] = "completed"
    (bundle / "result.md.run.json").write_text(json.dumps(run), encoding="utf-8")
    view = tick(home, T0 + 130)["view"]
    assert view["waiting_on"] == "holder"
    assert view["next_step"] == "read the builder's return and record it"
    assert view["dispatch_id"] == "d-888"
    assert remind(home, T0 + 131) == "next: read the builder's return and record it (yours)"
    assert remind(home, T0 + 132) is None


def test_c3_5_pending_record_turns_into_a_holder_check_after_ten_minutes(home):
    assert bind(home, output="12345\n")["bound"]
    view = tick(home, T0 + 601)["view"]
    assert view["waiting_on"] == "holder"
    assert view["next_step"] == "check the build run (no dispatch record)"


@pytest.mark.parametrize("decision,waiting,label", [
    ({"stage": "product-incident-required", "status": "refused",
      "reason": "practice-work-has-no-product-incident"}, "owner", "waiting on you"),
    ({"stage": "waiting", "status": "waiting", "reason": "latest-check-run-pending"},
     "ci", "waiting on CI"),
])
def test_c3_5_refused_or_waiting_dispatch_without_bundle_reads_its_decision(home, decision,
                                                                            waiting, label):
    assert bind(home, output=json.dumps(decision))["bound"]
    view = tick(home, T0 + 1)["view"]
    assert view["source"] == "stage-return"
    assert view["waiting_on"] == waiting and view["label"] == label
    assert view["record_pending"] is False
    assert remind(home, T0 + 2) is None


# --- row 4: the name ---------------------------------------------------------------------------

def test_c4_1_label_ignores_quiet_elapsed_read_time_and_step_text():
    base = {"issue": 888, "stage": "build", "waiting_on": "builder", "next_step": "x",
            "final": None, "running": {"stalled": False, "elapsed": 10, "quiet": 5}}
    assert core._label(base) == "build running"
    assert core._label({**base, "next_step": "y", "running": {"stalled": False, "elapsed": 99,
                                                              "quiet": 99}}) == "build running"
    assert core._label({**base, "running": {"stalled": True}}) == "build stalled"
    assert core._label({**base, "stage": "cold-seat"}) == "cold-seat seat running"
    for waiting, label in [("owner", "waiting on you"), ("holder", "holder: build"),
                           ("ci", "waiting on CI"), ("reviewer", "waiting on review"),
                           ("unknown", "build")]:
        assert core._label({**base, "running": None, "waiting_on": waiting}) == label
    assert core._label({**base, "final": "merged"}) == "merged"


def desktop(tmp_path: Path, source) -> dict:
    appdata = tmp_path / "appdata"
    folder = appdata / "Claude" / "claude-code-sessions" / "acct" / "org"
    folder.mkdir(parents=True, exist_ok=True)
    record = {"cliSessionId": SID, "title": "Start 888", "sessionId": "local_1"}
    if source is not None:
        record["titleSource"] = source
    (folder / "local_1.json").write_text(json.dumps(record), encoding="utf-8")
    (folder / "local_2.json").write_text(json.dumps({"cliSessionId": "other",
                                                     "titleSource": "auto"}), encoding="utf-8")
    return {"APPDATA": str(appdata)}


@pytest.mark.parametrize("source,renames", [("auto", True), ("tool", True), ("user", False),
                                            (None, False), ("weird", False)])
def test_c4_2_rename_only_for_auto_or_tool_sources(home, tmp_path, source, renames):
    environ = desktop(tmp_path, source)
    title = allow_title("Start 888")  # 2.1.295's get_session: no titleSource
    core.observe(core.Ctx(home=home, now=T0, environ=environ), {
        "session_id": SID, "command": RUN_BUILD, "output": "", "started_at": T0 - 1,
        "ended_at": T0, "title": title})
    answer = core.tick(core.Ctx(home=home, now=T0 + 1, environ=environ),
                       {"session_id": SID, "title": title})
    assert (answer["rename"] is not None) is renames
    if source == "user":
        assert answer["view"]["rename_note"] == "rename skipped (owner-set title)"
        later = core.tick(core.Ctx(home=home, now=T0 + 2000, environ=environ),
                          {"session_id": SID, "title": allow_title("x", "auto")})
        assert later["rename"] is None


def test_c4_2_rename_happens_once_per_label(home):
    bind(home)
    first = tick(home, T0 + 1)
    assert first["rename"] == {"label": "build running"}
    core.renamed(ctx_at(home, T0 + 2), {"session_id": SID, "label": "build running",
                                        "title": "#888 x", "outcome": "renamed"})
    assert tick(home, T0 + 61)["rename"] is None


def test_c4_4_would_prompt_disables_renaming_and_unreadable_keeps_last_title(home):
    bind(home, title={"decision": "ask", "text": None})
    tick(home, T0 + 1, title={"decision": "ask", "text": None})
    record = json.loads(core.status_path(ctx_at(home, T0), core.change_key(REPO_NAME, 888))
                        .read_text())
    assert record["session_name"] is None
    core.renamed(ctx_at(home, T0 + 2), {"session_id": SID, "label": "waiting on CI",
                                        "title": "#900 waiting on CI", "outcome": "renamed"})
    tick(home, T0 + 3, title={"decision": "deny", "text": None})
    record = json.loads(core.status_path(ctx_at(home, T0), core.change_key(REPO_NAME, 888))
                        .read_text())
    assert record["session_name"] == "#900 waiting on CI"
    core.renamed(ctx_at(home, T0 + 4), {"session_id": SID, "label": "y", "title": "t",
                                        "outcome": "would-prompt"})
    answer = tick(home, T0 + 5)
    assert answer["rename"] is None
    assert answer["view"]["rename_note"] == "rename skipped (would prompt)"


# --- row 5: what is shown ------------------------------------------------------------------------

def test_c5_1_view_carries_every_field(home):
    bind(home)
    write_bundle(home, "b1", stage="build", launched=T0, lifecycle="running", dispatch_id="d")
    view = tick(home, T0 + 600)["view"]
    for field in ("stage", "waiting_on", "next_step", "gate", "floor", "read_at_local",
                  "source", "label"):
        assert view[field] not in (None, ""), field
    assert set(view["running"]) >= {"elapsed", "deadline", "quiet", "stalled"}


def test_c5_2_quiet_is_not_stalled_until_the_deadline(home):
    bind(home)
    write_bundle(home, "b1", stage="build", launched=T0, lifecycle="running", dispatch_id="d",
                 limit=7200.0, log_mtime=T0 + 60)
    view = tick(home, T0 + 60 + 26 * 60)["view"]
    assert view["running"]["stalled"] is False
    assert int(view["running"]["quiet"] // 60) == 26
    assert view["label"] == "build running"
    view = tick(home, T0 + 7300)["view"]
    assert view["running"]["stalled"] is True and view["label"] == "build stalled"


def test_c5_2_entrance_reported_stall(home):
    bind(home, command=RUN_BUILD.replace("run build", "run floor"))
    write_bundle(home, "b1", stage="floor", launched=T0, lifecycle="running", dispatch_id="d")
    key = core.change_key(REPO_NAME, 888)
    core._write_json(core.change_path(ctx_at(home, T0), key), {"reading": core.reading_from_decision(
        {"stage": "floor-stalled", "status": "holder-owned", "reason": "declared-floor-stalled",
         "floor": {"outcome": "stalled", "satisfied": False}}, "entrance", T0 + 5)})
    assert tick(home, T0 + 60)["view"]["running"]["stalled"] is True


def _text(node):
    """A string expression as ("exact", text), ("prefix", leading text) or ("dynamic", "")."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return "exact", node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        kind, text = _text(node.left)
        return ("prefix", text) if kind != "dynamic" else ("dynamic", "")
    if isinstance(node, ast.JoinedStr):
        lead = ""
        for part in node.values:
            if isinstance(part, ast.Constant):
                lead += str(part.value)
            else:
                return ("prefix", lead) if lead else ("dynamic", "")
        return "exact", lead
    return "dynamic", ""


def _entrance_holder_stages(tree):
    function = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.FunctionDef) and node.name == "_decision_status")
    found = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Set) and all(isinstance(item, ast.Constant) for item in node.elts):
            found |= {item.value for item in node.elts}
    assert "release-report" in found
    return found


def waiting_decisions():
    """Every Decision/result whose status derives to waiting by `_decision_status`'s rule."""
    tree = ast.parse((REPO / "lib" / "work.py").read_text(encoding="utf-8"))
    holder_stages = _entrance_holder_stages(tree)
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", getattr(node.func, "attr", None))
        if name not in ("Decision", "result") or len(node.args) < 4:
            continue
        dispatch = node.args[1]
        if not (isinstance(dispatch, ast.Constant) and dispatch.value is False):
            continue
        status = next((keyword.value for keyword in node.keywords if keyword.arg == "status"),
                      None)
        position = 5 if name == "result" else 7
        if status is None and len(node.args) > position:
            status = node.args[position]
        if status is not None and not (isinstance(status, ast.Constant) and status.value is None):
            if isinstance(status, ast.Constant) and status.value != "waiting":
                continue
            if not isinstance(status, ast.Constant):
                continue
        stage_kind, stage = _text(node.args[0])
        reason_kind, reason = _text(node.args[3])
        if reason_kind == "dynamic":
            continue
        if stage_kind == "exact" and (stage in holder_stages or stage == "terminal"):
            continue
        if any(word in reason for word in ("version", "refused", "unproved")):
            continue
        sample_stage = stage if stage_kind == "exact" else (stage + "x" if stage else "build")
        sample_reason = reason if reason_kind == "exact" else reason + "x"
        found.add((sample_stage, sample_reason))
    return found


def test_c5_3_every_waiting_decision_the_entrance_emits_is_mapped():
    decisions = waiting_decisions()
    assert ("convergence", "affirmed-brief-marker-absent") in decisions
    assert ("waiting", "latest-check-run-pending") in decisions
    unmapped = sorted(pair for pair in decisions if core.classify(
        {"stage": pair[0], "status": "waiting", "reason": pair[1]})["waiting_on"] == "unknown")
    assert unmapped == []


@pytest.mark.parametrize("stage,reason,status,party", [
    ("convergence", "affirmed-brief-marker-absent", "waiting", "owner"),
    ("artifact-source", "artifact-source-unusable", "holder-owned", "holder"),
    ("build", "build-budget-holder-owned", "holder-owned", "holder"),
    ("implementation-scope", "implementation-instalment-required", "holder-owned", "holder"),
    ("build", "fresh-build-requires-released-registration", "refused", "holder"),
])
def test_c5_3_stage_level_decisions_name_their_party(stage, reason, status, party):
    answer = core.classify({"stage": stage, "status": status, "reason": reason})
    assert answer["waiting_on"] == party
    assert answer["next_step"] not in ("", reason)
    view = {"issue": 888, "stage": stage, "waiting_on": party, "final": None, "running": None}
    assert core._label(view) == ("waiting on you" if party == "owner" else f"holder: {stage}")


@pytest.mark.parametrize("reason", ["holder-session-id-required-for-build",
                                    "resume-session-identifies-holder-for-build"])
def test_c5_3_reasons_passed_through_a_parameter_are_mapped(reason):
    # `_holder_identity_decision(state, decision, reason)` builds these from an argument,
    # which the ast walk above cannot follow; their status derives to waiting.
    assert core.classify({"stage": "build", "status": "waiting", "reason": reason})[
        "waiting_on"] == "holder"


def test_c5_3_classifier_order():
    assert core.classify({"stage": "affirmation-invalid", "status": "waiting",
                          "reason": "review-risk-lane-missing-or-mismatched"})["waiting_on"] == "owner"
    assert core.classify({"stage": "build", "status": "runnable", "reason": "x"}) == {
        "waiting_on": "holder", "next_step": "run build"}
    assert core.classify({"stage": "build", "status": "refused", "reason": "bad"}) == {
        "waiting_on": "holder", "next_step": "resolve: bad"}
    assert core.classify({"stage": "terminal", "status": "terminal", "reason": "x"})[
        "waiting_on"] == "none"
    assert core.classify({"stage": "x", "status": "waiting", "reason": "new-reason"})[
        "waiting_on"] == "unknown"


def test_c5_4_release_report_posted_waits_on_the_owner(home):
    command = f"python lib/work.py run release-report --repo {REPO_NAME} --issue 888 --root D:/r"
    bind(home, command=command, output=RELEASE_REPORT_OUTPUT)
    core.observe(ctx_at(home, T0 + 10), {"session_id": SID, "command": "gh pr comment 901 -F x",
                                         "output": ""})
    assert tick(home, T0 + 11)["view"]["waiting_on"] == "holder"
    core.observe(ctx_at(home, T0 + 12), {"session_id": SID,
                                         "command": "gh pr comment 900 --body-file r.md",
                                         "output": ""})
    view = tick(home, T0 + 13)["view"]
    assert view["waiting_on"] == "owner" and view["next_step"] == "merge"
    assert view["label"] == "waiting on you"


# --- row 6: the reminder ------------------------------------------------------------------------------

def test_c6_1_once_per_distinct_step_and_never_while_active(home):
    command = f"python lib/work.py run proof --repo {REPO_NAME} --issue 888 --root D:/r"
    bind(home, command=command, output=json.dumps({"stage": "floor", "status": "holder-owned",
                                                   "reason": "run proof after CI"}))
    blocks = [remind(home, T0 + step, active=bool(step % 2)) for step in range(20)]
    assert len([block for block in blocks if block]) == 1
    bind(home, command=command.replace("run proof", "run release-report"),
         output=RELEASE_REPORT_OUTPUT, now=T0 + 100)
    blocks = [remind(home, T0 + 100 + step) for step in range(5)]
    assert [block for block in blocks if block] == ["next: post the release report (yours)"]


def test_c6_2_no_reminder_when_another_party_holds_the_step(home):
    bind(home, output=json.dumps({"stage": "waiting", "status": "waiting",
                                  "reason": "required-connected-reviewer-has-not-run"}))
    assert remind(home, T0 + 1) is None


# --- row 7: the status file -------------------------------------------------------------------------

def test_c7_1_status_file_tracks_the_live_title(home, tmp_path):
    environ = desktop(tmp_path, "user")
    core.observe(core.Ctx(home=home, now=T0, environ=environ), {
        "session_id": SID, "command": RUN_BUILD, "output": "", "title": allow_title("Start 900")})
    path = core.status_path(ctx_at(home, T0), core.change_key(REPO_NAME, 888))
    answer = core.tick(core.Ctx(home=home, now=T0 + 1, environ=environ),
                       {"session_id": SID, "title": allow_title("Start 900")})
    record = json.loads(path.read_text())
    assert record["session_name"] == "Start 900" and answer["rename"] is None
    assert list(record) == sorted(core.STATUS_FIELDS)
    mtime = path.stat().st_mtime_ns
    os.utime(path, ns=(mtime - 10_000_000, mtime - 10_000_000))
    stamped = path.stat().st_mtime_ns
    core.tick(core.Ctx(home=home, now=T0 + 2, environ=environ),
              {"session_id": SID, "title": allow_title("Start 900")})
    assert path.stat().st_mtime_ns == stamped
    core.tick(core.Ctx(home=home, now=T0 + 3, environ=environ),
              {"session_id": SID, "title": allow_title("Ordering")})
    assert json.loads(path.read_text())["session_name"] == "Ordering"
    assert not list(path.parent.glob("*.tmp"))


def test_c7_2_readme_documents_every_field():
    text = README.read_text(encoding="utf-8")
    table = set(re.findall(r"^\| `([a-z_]+)` \|", text, re.MULTILINE))
    assert set(core.STATUS_FIELDS) <= table


# --- row 1 / static checks of the shim ----------------------------------------------------------------

def test_c3_2_shim_reaches_no_model_network_or_turn():
    source = REGISTER.read_text(encoding="utf-8")
    for forbidden in ("prompt.submit", "agent.spawn", "session.send", "http.fetch", "$.model",
                      "$.prompt", "$.agent", "$.http"):
        assert forbidden not in source, forbidden
    tools = set(re.findall(r"'(mcp__[a-z_]+)'", source))
    assert tools == {"mcp__ccd_session_mgmt__get_session",
                     "mcp__ccd_session_mgmt__set_session_title"}


def test_c4_4_every_tool_call_sits_behind_an_allow_check():
    source = REGISTER.read_text(encoding="utf-8")
    calls = [match.start() for match in re.finditer(r"\$\.tool\.call\(", source)]
    assert len(calls) == 1
    helper = source[source.index("async function sessionTool"):calls[0]]
    assert "$.tool.check(" in helper
    assert "if (decision !== 'allow') return" in helper


def test_no_shipped_path_names_the_mod():
    for shipped in ("hooks", "lib", "skills", "commands", "agents", ".claude-plugin"):
        root = REPO / shipped
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in (".py", ".md", ".json", ".ts"):
                assert "holder_pane" not in path.read_text(encoding="utf-8", errors="replace"), path


def test_core_runs_as_a_script(home):
    completed = subprocess.run(
        [sys.executable, str(PLUGIN / "core" / "holder_pane.py"), "classify"],
        input=json.dumps({"stage": "waiting", "status": "waiting",
                          "reason": "latest-check-run-pending"}).encode("utf-8"),
        capture_output=True, env={**os.environ, "HOME": str(home), "USERPROFILE": str(home)})
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["waiting_on"] == "ci"
