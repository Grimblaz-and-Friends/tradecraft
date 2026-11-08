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
ARROW = chr(0x2192)  # built at runtime so the source stays ASCII


class Entrance:
    """A fake entrance: logs each run and answers a fixed decision."""

    def __init__(self, decision: dict | None = None, prs: list | None = None,
                 comments: list | None = None, pr_view: dict | None = None):
        self.calls: list[list[str]] = []
        self.gh_calls: list[list[str]] = []
        self.prs = prs or []
        self.comments = comments or []
        self.pr_view = pr_view
        self.decision = decision or {"stage": "waiting", "status": "waiting",
                                     "reason": "latest-check-run-pending", "floor": None}

    def __call__(self, argv, **kwargs):
        assert kwargs.get("stdin") is subprocess.DEVNULL and kwargs.get("capture_output") is True
        if argv[0] == "gh":
            self.gh_calls.append(list(argv))
            if argv[1] == "api":
                answer = [[comment if isinstance(comment, dict)
                           else {"body": comment, "user": {"login": "Grimblaz"}}
                           for comment in self.comments]]
            elif argv[1:3] == ["pr", "view"]:
                answer = self.pr_view
            else:
                answer = self.prs
            return SimpleNamespace(returncode=0, stdout=json.dumps(answer), stderr="")
        self.calls.append(list(argv))
        return SimpleNamespace(returncode=0, stdout=json.dumps(self.decision), stderr="")


@pytest.fixture
def home(tmp_path):
    root = tmp_path / "home"
    (root / ".tradecraft" / "dispatches").mkdir(parents=True)
    return root


def ctx_at(home: Path, now: float, runner=None, environ=None, liveness=None):
    return core.Ctx(home=home, now=now, runner=runner or Entrance(),
                    environ=environ if environ is not None else {},
                    liveness=liveness or (lambda identity: "unresolved"))


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
                 dispatch_id: str = "d1", log_mtime: float | None = None,
                 processes: dict | None = None) -> Path:
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
           "attempts": [{"stdout": str(stdout), "stderr": str(directory / "missing.log")}],
           **(processes or {})}
    (directory / "result.md.run.json").write_text(json.dumps(run), encoding="utf-8")
    return directory


def tick(home: Path, now: float, title=None, runner=None, liveness=None):
    return core.tick(ctx_at(home, now, runner, liveness=liveness), {
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
                      "issue": 888, "root": "D:/Code/x", "entrance": None,
                      "instalment": None}
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
        ["plugin", "install", "holder-pane@tradecraft-holder-pane", "--scope", "local"],
        ["plugin", "uninstall", "holder-pane@tradecraft-holder-pane", "--scope", "local"],
        ["plugin", "marketplace", "remove", "tradecraft-holder-pane", "--scope", "local"],
    ]
    assert all(argv[-2:] == ["--scope", "local"] for argv in tools.claude)
    # #915 row 1: the Steward's wake owns its marketplace name; the pane never names it.
    wake = _marketplace_name(REPO / "tools" / "steward-wake")
    assert not any(wake in part for argv in tools.claude for part in argv)


def _marketplace_name(folder: Path) -> str:
    path = folder / ".claude-plugin" / "marketplace.json"
    return json.loads(path.read_bytes().decode("utf-8"))["name"]


def test_the_pane_marketplace_cannot_share_the_wakes_name():
    """#915 row 1: a second `marketplace add` under a registered name repoints it,
    and the pane's uninstall removes its marketplace by name, so the two lab mods'
    marketplaces must differ, and the installer must name only the pane's own."""
    pane = _marketplace_name(PANE / "marketplace")
    wake = _marketplace_name(REPO / "tools" / "steward-wake")
    assert pane != wake
    assert installer.MARKETPLACE == pane
    assert installer.PLUGIN_REF == f"holder-pane@{pane}"


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
        "extraKnownMarketplaces": {"tradecraft-holder-pane": {"source": {"source": "directory",
                                                                  "path": "M"}}},
        "enabledPlugins": {"holder-pane@tradecraft-holder-pane": True, "other@x": True},
        "env": {"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"}}), encoding="utf-8")
    worktree = tmp_path / "wt"
    (worktree / ".claude").mkdir(parents=True)
    installer.install_worktree(worktree, checkout, FakeTools())
    copied = json.loads((worktree / ".claude" / "settings.local.json").read_text())
    assert copied["enabledPlugins"] == {"holder-pane@tradecraft-holder-pane": True}
    assert "tradecraft-holder-pane" in copied["extraKnownMarketplaces"]
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
    runner.decision = {"stage": "terminal", "status": "terminal",
                       "reason": "issue-or-pull-request-terminal"}
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
    # The entrance, then the PR lookup inside the same floored read: the body search,
    # and, finding no PR there, the issue's comments for a marker. Nothing else.
    assert len(seen) == 3 and seen[0][2:] == ["--repo", REPO_NAME, "--issue", "888",
                                               "--root", "D:/root"]
    assert seen[1][:3] == ["gh", "pr", "list"] and "--state" in seen[1]
    assert seen[2][:3] == ["gh", "api", f"repos/{REPO_NAME}/issues/888/comments"]


def test_c3_3_read_returns_at_once_when_refused(home, tmp_path):
    bound_for_reads(home, tmp_path)
    runner = Entrance()
    core.read(ctx_at(home, T0, runner), {"session_id": SID})
    assert core.read(ctx_at(home, T0 + 1, runner), {"session_id": SID}) == {
        "ran": False, "why": "floor"}
    assert len(runner.calls) == 1 and len(runner.gh_calls) == 2


def decision_dict(stage, status, reason, *, dispatch=False, detail=None, **extra):
    """`lib/work.py` Decision.as_dict's keys, as `_emit_report` prints them."""
    report = {
        "schema_version": 1, "work": f"{REPO_NAME}#888", "producer_version": "0.195.0",
        "stage": stage, "dispatch": dispatch, "status": status, "continuity": None,
        "reason": reason, "detail": detail, "lawful_markers": [], "invalid_markers": [],
        "quotations": [], "latest_checks": [], "launch_settings": None,
        "synchronization": {"base": "main", "head": "abc", "behind": 0, "strict": True,
                            "conflict": False, "mergeability_known": True,
                            "uncertainties": []},
        "use_application": None,
        "floor": {"base": "main", "policy": ".github/change-proof.json", "head": "abc",
                  "outcome": "ci-met", "checks": [], "executions": [], "excluded": [],
                  "limitations": []},
        "raw_output": None, "version_obligation": None, "proof_version_obligation": None,
        "reach": None, "artifact_interpretation": None,
    }
    report.update(extra)
    return report


RELEASE_REPORT_OUTPUT = json.dumps(decision_dict(
    "release-report", "holder-owned", "all-evidence-complete-release-report-ready",
    required_gate={"verdict": "green", "head": "abc", "reason": "", "requirement_known": True},
    path_departures={"restate": False, "instruction": "no restatement"},
    holder_close={"instruction": "close"},
))


def test_c3_4_holder_only_stage_return_reads_its_own_output(home):
    runner = Entrance()
    command = f"python lib/work.py run release-report --repo {REPO_NAME} --issue 888 --root D:/r"
    assert bind(home, command=command, output="noise\n" + RELEASE_REPORT_OUTPUT)["bound"]
    view = tick(home, T0 + 5, runner=runner)["view"]
    assert runner.calls == []
    assert view["next_step"] == "post the release report"
    assert view["waiting_on"] == "holder" and view["source"] == "stage-return"
    assert view["gate"] == "green" and view["floor"] == {"outcome": "ci-met", "satisfied": None}


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


def seed_pull_request(home, number=900, state="OPEN", merged=False):
    key = core.change_key(REPO_NAME, 888)
    path = core.change_path(ctx_at(home, T0), key)
    change = core.load_change(ctx_at(home, T0), key)
    change["pull_request"] = {"number": number, "state": state, "merged": merged}
    core._write_json(path, change)


def shown(target: int) -> str:
    """The comment URL a successful post prints (`gh pr comment`, or `gh api --jq .html_url`)."""
    return f"https://github.com/o/r/pull/{target}#issuecomment-6712"


def report_body(tmp_path: Path, issue: int = 888, pr: int = 900, head: str | None = None,
                name: str = "r.md") -> Path:
    path = tmp_path / name
    tail = f" at head `{head}`" if head else ""
    path.write_text(f"**Release report: #{issue} {ARROW} PR #{pr}**{tail}\n\nBody.\n",
                    encoding="utf-8")
    return path


def test_c5_4_release_report_posted_waits_on_the_owner(home, tmp_path):
    seed_pull_request(home, 900)
    body = report_body(tmp_path)
    command = f"python lib/work.py run release-report --repo {REPO_NAME} --issue 888 --root D:/r"
    bind(home, command=command, output=RELEASE_REPORT_OUTPUT)
    core.observe(ctx_at(home, T0 + 10), {"session_id": SID, "output": "",
                                         "command": f"gh pr comment 901 -F {body.as_posix()}"})
    assert tick(home, T0 + 11)["view"]["waiting_on"] == "holder"
    core.observe(ctx_at(home, T0 + 12), {"session_id": SID, "output": shown(900),
                                         "command": f"gh pr comment 900 --body-file "
                                                    f"{body.as_posix()}"})
    view = tick(home, T0 + 13)["view"]
    assert view["waiting_on"] == "owner" and view["next_step"] == "merge"
    assert view["label"] == "waiting on you"


def test_c5_4_release_report_handoff_with_the_pr_unknown_takes_the_named_pr(home, tmp_path):
    # The real report carries no PR number (thread 4255043360): with none cached
    # either, the holder's own `gh pr comment <n>` names it.
    body = report_body(tmp_path)
    command = f"python lib/work.py run release-report --repo {REPO_NAME} --issue 888 --root D:/r"
    bind(home, command=command, output=RELEASE_REPORT_OUTPUT)
    core.observe(ctx_at(home, T0 + 1), {"session_id": SID, "output": shown(900),
                                        "command": f"gh pr comment 900 --body-file {body}"})
    view = tick(home, T0 + 2)["view"]
    assert view["waiting_on"] == "owner" and view["next_step"] == "merge"


def test_floored_read_finds_the_implementing_pr_and_the_gate_is_not_unreached(home, tmp_path):
    bound_for_reads(home, tmp_path)
    runner = Entrance(decision=decision_dict("waiting", "waiting", "latest-check-run-pending"),
                      prs=[{"number": 700, "state": "OPEN", "mergedAt": None,
                            "body": "mentions 888 but closes nothing"},
                           {"number": 905, "state": "OPEN", "mergedAt": None,
                            "body": "Builds it.\n\nCloses #888\n"}])
    assert core.read(ctx_at(home, T0, runner), {"session_id": SID})["ok"] is True
    change = core.load_change(ctx_at(home, T0), core.change_key(REPO_NAME, 888))
    assert change["pull_request"] == {"number": 905, "state": "OPEN", "merged": False}
    view = tick(home, T0 + 1)["view"]
    assert view["gate"] != "not reached" and view["waiting_on"] == "ci"


def test_lookup_prefers_open_then_newest_merged():
    runner = Entrance(prs=[{"number": 1, "state": "MERGED", "mergedAt": "x", "body": "Fixes #888"},
                           {"number": 3, "state": "CLOSED", "mergedAt": None, "body": "closes #888"},
                           {"number": 2, "state": "MERGED", "mergedAt": "y", "body": "Closes #888"},
                           {"number": 9, "state": "OPEN", "mergedAt": None, "body": "Closes #8880"}])
    ctx = core.Ctx(home=Path("."), now=T0, runner=runner, environ={})
    assert core.lookup_pull_request(ctx, REPO_NAME, 888) == {"number": 2, "state": "MERGED",
                                                             "merged": True}


def test_catch_up_launches_nobody_and_reads_its_next_decision(home):
    # The real catch-up report: no reason, dispatch false, and the entrance's next decision.
    report = {"schema_version": 1, "stage": "catch-up", "dispatch": False,
              "status": "holder-owned", "starting_head": "a", "pinned_base": "b", "head": "c",
              "version_adjustment": None, "landing": "", "landing_error": "",
              "next": decision_dict("waiting", "waiting", "latest-check-run-pending")}
    command = f"python lib/work.py run catch-up --repo {REPO_NAME} --issue 888 --root D:/r"
    bind(home, command=command, output=json.dumps(report))
    view = tick(home, T0 + 700)["view"]
    assert view["record_pending"] is False and view["running"] is None
    assert view["waiting_on"] == "ci" and view["label"] == "waiting on CI"
    assert "no dispatch record" not in view["next_step"]


@pytest.mark.parametrize("stage,reason,step", [
    ("build", "build-budget-holder-owned", "resolve the build budget"),
    ("floor", "floor-command-missing", "rerun floor with --floor-command"),
    ("implementation-scope", "implementation-instalment-required",
     "run the entrance with --instalment"),
])
def test_holder_owned_refusal_of_a_dispatching_stage_is_the_reading(home, stage, reason, step):
    report = decision_dict(stage, "holder-owned", reason)
    run = "floor" if stage == "floor" else "build"
    command = f"python lib/work.py run {run} --repo {REPO_NAME} --issue 888 --root D:/r"
    bind(home, command=command, output=json.dumps(report))
    view = tick(home, T0 + 1)["view"]
    assert view["record_pending"] is False and view["waiting_on"] == "holder"
    assert view["next_step"] == step
    assert remind(home, T0 + 2) == f"next: {step} (yours)"


def test_successful_proof_never_asks_the_holder_to_post_it(home):
    report = {"schema_version": 1, "work": f"{REPO_NAME}#888", "producer_version": "0.195.0",
              "stage": "proof", "status": "holder-owned", "head": "abc",
              "comment": {"id": 1}, "gate_reruns": []}
    command = f"python lib/work.py run proof --repo {REPO_NAME} --issue 888 --root D:/r"
    bind(home, command=command, output=json.dumps(report))
    view = tick(home, T0 + 1)["view"]
    assert "post the generated proof" not in view["next_step"]
    assert "post" not in (remind(home, T0 + 2) or "")


def test_merged_with_the_issue_open_is_holder_owned_not_final(home, tmp_path):
    bound_for_reads(home, tmp_path)
    runner = Entrance(decision=decision_dict(
        "merged-pull-request", "holder-owned",
        "implementing-pull-request-merged-while-issue-open"))
    core.read(ctx_at(home, T0, runner), {"session_id": SID})
    answer = tick(home, T0 + 1)
    assert answer["stopped"] is False and answer["view"]["final"] is None
    assert answer["view"]["waiting_on"] == "holder"
    assert remind(home, T0 + 2) is not None
    assert core.read(ctx_at(home, T0 + 3000, runner), {"session_id": SID})["ran"] is True


@pytest.mark.parametrize("pr,label", [
    ({"number": 905, "state": "MERGED", "mergedAt": "x", "body": "Closes #888"}, "merged"),
    ({"number": 905, "state": "CLOSED", "mergedAt": None, "body": "Closes #888"}, "closed"),
    (None, "closed"),
])
def test_terminal_label_comes_from_the_pull_request(home, tmp_path, pr, label):
    bound_for_reads(home, tmp_path)
    runner = Entrance(decision=decision_dict("terminal", "terminal",
                                             "issue-or-pull-request-terminal"),
                      prs=[pr] if pr else [])
    core.read(ctx_at(home, T0, runner), {"session_id": SID})
    answer = tick(home, T0 + 1)
    assert answer["view"]["label"] == label and answer["stopped"] is True


def test_dead_or_superseded_running_bundle_does_not_overlay(home):
    bind(home, output="12345\n")
    dead = {"launcher_process": {"pid": 1, "host": "h", "birth": "1"},
            "recipient_process": {"pid": 2, "host": "h", "birth": "2"}}
    write_bundle(home, "b1", stage="build", launched=T0, lifecycle="running", dispatch_id="old",
                 processes=dead)
    alive = tick(home, T0 + 60, liveness=lambda identity: "active")["view"]
    assert alive["running"] is not None
    gone = tick(home, T0 + 120, liveness=lambda identity: "stopped")["view"]
    assert gone["running"] is None
    write_bundle(home, "b2", stage="build", launched=T0 + 200, lifecycle="completed",
                 dispatch_id="new")
    superseded = tick(home, T0 + 300, liveness=lambda identity: "active")["view"]
    assert superseded["running"] is None


def test_instalment_is_kept_and_passed_on_every_read(home, tmp_path):
    entrance = tmp_path / "work.py"
    entrance.write_text("", encoding="utf-8")
    command = (f"python {entrance.as_posix()} run proof --repo {REPO_NAME} --issue 888 "
               f"--root D:/root --instalment b")
    bind(home, command=command)
    path = core.binding_path(ctx_at(home, T0), SID)
    binding = json.loads(path.read_text())
    assert binding["instalment"] == "b"
    binding["entrance"] = str(entrance)
    path.write_text(json.dumps(binding), encoding="utf-8")
    runner = Entrance()
    core.read(ctx_at(home, T0, runner), {"session_id": SID})
    assert runner.calls[0][-2:] == ["--instalment", "b"]


def test_uninstall_keeps_an_opt_in_that_predates_the_install(checkout):
    path = checkout / ".claude" / "settings.local.json"
    path.write_text(json.dumps({"env": {"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1",
                                        "OTHER": "x"}}), encoding="utf-8")
    tools = FakeTools()
    installer.install(checkout, Path("claude.exe"), tools, marketplace=Path("M"))
    installer.uninstall(checkout, Path("claude.exe"), tools)
    assert json.loads(path.read_text())["env"] == {"CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1",
                                                   "OTHER": "x"}


def test_worktree_copy_requires_the_enabled_plugin_entry(checkout, tmp_path):
    (checkout / ".claude" / "settings.local.json").write_text(json.dumps({
        "extraKnownMarketplaces": {"tradecraft-holder-pane": {"source": {"source": "directory",
                                                                  "path": "M"}}},
        "enabledPlugins": {"other@x": True}}), encoding="utf-8")
    worktree = tmp_path / "wt2"
    (worktree / ".claude").mkdir(parents=True)
    with pytest.raises(installer.Refused):
        installer.install_worktree(worktree, checkout, FakeTools())
    assert not (worktree / ".claude" / "settings.local.json").exists()


# --- the second review round ------------------------------------------------------------

@pytest.mark.parametrize("stage", ["release-report", "proof", "ready-reviewers", "catch-up"])
def test_a_failed_holder_only_stage_is_no_return(home, stage):
    # Thread 4255672027: a failed `work.py` run prints only `work: <error>` on stderr
    # and exits 1, so the call's text carries no report.
    bind(home, output=json.dumps(decision_dict("waiting", "waiting",
                                               "latest-check-run-pending")),
         command=f"python lib/work.py run build --repo {REPO_NAME} --issue 888 --root D:/r")
    before = tick(home, T0 + 1)["view"]
    command = f"python lib/work.py run {stage} --repo {REPO_NAME} --issue 888 --root D:/r"
    core.observe(ctx_at(home, T0 + 10), {
        "session_id": SID, "command": command, "started_at": T0 + 9, "ended_at": T0 + 10,
        "output": "work: GitHub request failed: 502\n", "title": allow_title("Start 888", "auto")})
    view = tick(home, T0 + 11)["view"]
    assert (view["stage"], view["waiting_on"], view["next_step"]) == (
        before["stage"], before["waiting_on"], before["next_step"])
    assert view["failure"].startswith(f"{stage} failed")
    assert remind(home, T0 + 12) is None


class Clock:
    def __init__(self, now):
        self.value = now

    def __call__(self):
        return self.value


def test_a_stage_return_during_a_read_stays_newer(home, tmp_path):
    # Thread 4255672038: the entrance reading is stamped with the read's start.
    bound_for_reads(home, tmp_path)
    clock = Clock(T0)
    command = f"python lib/work.py run release-report --repo {REPO_NAME} --issue 888 --root D:/r"
    old = decision_dict("release-report", "holder-owned",
                        "all-evidence-complete-release-report-ready")

    class Overlapping(Entrance):
        def __call__(self, argv, **kwargs):
            if argv[0] != "gh":
                clock.value = T0 + 20
                core.observe(ctx_at(home, T0 + 20), {
                    "session_id": SID, "command": command, "started_at": T0 + 19,
                    "ended_at": T0 + 20, "output": RELEASE_REPORT_OUTPUT})
                clock.value = T0 + 40
            return super().__call__(argv, **kwargs)

    ctx = core.Ctx(home=home, runner=Overlapping(decision=old), environ={},
                   liveness=lambda identity: "unresolved")
    ctx.now = clock
    assert core.read(ctx, {"session_id": SID})["ok"] is True
    view = tick(home, T0 + 41)["view"]
    assert view["source"] == "stage-return" and view["next_step"] == "post the release report"


def test_lookup_uses_the_entrances_whole_line_closing_reference():
    # Thread 4255672051: an inline mention is not a closing reference.
    runner = Entrance(prs=[
        {"number": 905, "state": "OPEN", "mergedAt": None, "body": "Builds it.\n\nCloses #888\n"},
        {"number": 950, "state": "OPEN", "mergedAt": None,
         "body": "This records evidence and mentions closes #888 inline."}])
    ctx = core.Ctx(home=Path("."), now=T0, runner=runner, environ={})
    assert core.lookup_pull_request(ctx, REPO_NAME, 888)["number"] == 905
    assert len(runner.gh_calls) == 1


def test_lookup_honours_the_implementing_pr_marker_when_no_body_closes(home):
    runner = Entrance(
        prs=[{"number": 950, "state": "OPEN", "mergedAt": None,
              "body": "mentions closes #888 inline."}],
        comments=["plain comment",
                  "<!-- tradecraft:implementing-pr:v1 number=905 -->"],
        pr_view={"number": 905, "state": "MERGED", "mergedAt": "2026-10-13T00:00:00Z"})
    ctx = core.Ctx(home=Path("."), now=T0, runner=runner, environ={})
    assert core.lookup_pull_request(ctx, REPO_NAME, 888,
                                    producers=frozenset({"grimblaz"})) == {
        "number": 905, "state": "MERGED", "merged": True}
    assert [argv[:2] for argv in runner.gh_calls] == [["gh", "pr"], ["gh", "api"], ["gh", "pr"]]


def test_lookup_ignores_a_marker_from_an_author_who_is_no_producer(tmp_path):
    # The entrance honours a marker only from `.tradecraft/work.json`'s marker_producers.
    root = tmp_path / "checkout"
    (root / ".tradecraft").mkdir(parents=True)
    (root / ".tradecraft" / "work.json").write_text(
        json.dumps({"schema_version": 1, "marker_producers": ["Grimblaz"]}), encoding="utf-8")
    producers = core.marker_producers(str(root))
    assert producers == frozenset({"grimblaz"})
    runner = Entrance(
        comments=[{"body": "<!-- tradecraft:implementing-pr:v1 number=777 -->",
                   "user": {"login": "someone-else"}}],
        pr_view={"number": 777, "state": "OPEN", "mergedAt": None})
    ctx = core.Ctx(home=Path("."), now=T0, runner=runner, environ={})
    assert core.lookup_pull_request(ctx, REPO_NAME, 888, producers=producers) is None
    assert [argv[:2] for argv in runner.gh_calls] == [["gh", "pr"], ["gh", "api"]]
    assert core.marker_producers(str(tmp_path / "missing")) == frozenset()


def test_read_budget_fits_inside_the_shims_timeout():
    # Thread 4255672080: the entrance plus every gh call, with margin, under the kill.
    source = REGISTER.read_text(encoding="utf-8")
    shim_ms = int(re.search(r"READ_TIMEOUT_MS = ([0-9_]+)", source).group(1).replace("_", ""))
    assert shim_ms == core.SHIM_READ_TIMEOUT_SECONDS * 1000
    worst = core.ENTRANCE_TIMEOUT_SECONDS + 3 * core.GH_TIMEOUT_SECONDS
    assert worst <= core.READ_BUDGET_SECONDS <= core.SHIM_READ_TIMEOUT_SECONDS - 30
    assert core.STALE_LOCK_SECONDS <= core.SHIM_READ_TIMEOUT_SECONDS


def test_a_killed_read_shows_read_failed_and_leaves_no_blocking_lock(home, tmp_path):
    bound_for_reads(home, tmp_path)
    key = core.change_key(REPO_NAME, 888)
    seen = {}

    class Killed(Entrance):
        def __call__(self, argv, **kwargs):
            # What is on disk at the step the shim's timeout can kill.
            seen["change"] = core.load_change(ctx_at(home, T0), key)
            raise KeyboardInterrupt  # stands for the kill: nothing after this runs

    with pytest.raises(KeyboardInterrupt):
        core.read(ctx_at(home, T0, Killed()), {"session_id": SID})
    assert seen["change"]["read_open"] == T0
    assert tick(home, T0 + 100)["view"]["read_failed_at"] is None
    assert tick(home, T0 + core.READ_BUDGET_SECONDS + 1)["view"]["read_failed_at"] == T0
    # A lock whose owner is gone does not block the next read once the floor allows.
    core.lock_path(ctx_at(home, T0), key).write_text(
        json.dumps({"pid": 4, "host": "h", "birth": "1", "started_at": T0 + 2200}),
        encoding="utf-8")
    later = core.Ctx(home=home, now=T0 + 2201, runner=Entrance(), environ={},
                     liveness=lambda identity: "stopped")
    assert core.read(later, {"session_id": SID})["ran"] is True


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


# --- the holder's own steps: background stages, posts and the release report -----------------
#
# Replays of a real holder's recorded calls: stages run in the background with their output
# redirected, a release report and use markers posted from files, and catch-up run seconds
# after a post. Fixtures are synthesized in the recorded shapes (command strings, minimal
# reports with stage, status, reason, head and `next`, and title-line body files); nothing is
# copied from the recorded output.

from datetime import datetime  # noqa: E402

DAEMON = "Grimblaz-and-Friends/Daemon"
HOLDER = "ea06bae1-665b-4ae3-a362-8b97ccd26630"
HEAD = "f53375268c52d70680370be0dba89b7f856e11fe"
HEAD2 = "0123456789abcdef0123456789abcdef01234567"


def at(clock: str, day: int = 6) -> float:
    return datetime.fromisoformat(f"2026-11-{day:02d}T{clock}+00:00").timestamp()


class Forbidden:
    """A runner for every path but `read()`: working out the holder's steps must start no
    subprocess, so nothing new reaches GitHub or a model."""

    def __call__(self, argv, **kwargs):
        raise AssertionError(f"no subprocess outside read(): {argv}")


class Holder:
    """A holder session that runs stages in the background and posts from files, driven
    through observe, tick and remind at the times its calls were made."""

    def __init__(self, home: Path, tmp_path: Path, session: str = HOLDER):
        self.home, self.session = home, session
        self.wt = tmp_path / "wt"
        self.scratch = tmp_path / "scratch"
        self.tasks = tmp_path / "tasks"
        for folder in (self.wt, self.scratch / "inst1", self.tasks):
            folder.mkdir(parents=True, exist_ok=True)
        self.statuses: list[dict] = []
        core.bind(self.ctx(at("00:00:00")), session, {
            "repository": DAEMON, "issue": 95, "root": str(self.wt),
            "entrance": "C:/cache/lib/work.py"}, {"readable": False})

    def ctx(self, now: float):
        return core.Ctx(home=self.home, now=now, runner=Forbidden(), environ={},
                        liveness=lambda identity: "unresolved")

    def observe(self, now: float, command: str, output: str = "", *, started: float | None = None,
                **extra):
        return core.observe(self.ctx(now), {
            "session_id": self.session, "command": command, "output": output,
            "started_at": started if started is not None else now - 1, "ended_at": now,
            "title": allow_title("Start #95", "auto"), "root": str(self.wt), **extra})

    def tick(self, now: float) -> dict:
        answer = core.tick(self.ctx(now), {"session_id": self.session,
                                           "title": allow_title("Start #95", "auto")})
        key = core.change_key(DAEMON, 95)
        self.statuses.append(json.loads(core.status_path(self.ctx(now), key).read_text()))
        return answer["view"]

    def remind(self, now: float, tasks=None) -> str | None:
        payload = {"session_id": self.session, "stop_hook_active": False}
        if tasks is not None:
            payload["background_tasks"] = tasks
        return core.remind(self.ctx(now), payload)["block"]

    def stage(self, stage: str, *, redirect: bool = True) -> str:
        tail = (f" > {self.scratch.as_posix()}/inst1/run-{stage}.out 2>&1; echo \"exit=$?\"; "
                f"date -u +%H:%M:%S") if redirect else ""
        return (f"cd {self.wt.as_posix()} && date -u +%H:%M:%S && python C:/cache/lib/work.py "
                f"run {stage} --repo {DAEMON} --issue 95 --root {self.wt.as_posix()} "
                f"--holder-session-id {self.session}{tail}")

    def launched(self, task: str) -> str:
        return (f"Command running in background with ID: {task}. Output is being written to: "
                f"{self.tasks}\\{task}.output. You will be notified when it completes.")

    def write_report(self, stage: str, report: dict, when: float) -> Path:
        path = self.scratch / "inst1" / f"run-{stage}.out"
        path.write_text("starting\n" + json.dumps(report, indent=2) + "\n", encoding="utf-8")
        os.utime(path, (when, when))
        return path

    def entrance(self, read_at: float, decision: dict) -> None:
        key = core.change_key(DAEMON, 95)
        path = core.change_path(self.ctx(read_at), key)
        change = core.load_change(self.ctx(read_at), key)
        change["reading"] = core.reading_from_decision(decision, "entrance", read_at,
                                                       change.get("pull_request"))
        core._write_json(path, change)

    def pull_request(self, number: int = 116, merged: bool = False) -> None:
        key = core.change_key(DAEMON, 95)
        path = core.change_path(self.ctx(0), key)
        change = core.load_change(self.ctx(0), key)
        change["pull_request"] = {"number": number, "state": "MERGED" if merged else "OPEN",
                                  "merged": merged}
        core._write_json(path, change)

    def post(self, now: float, body: Path, issue: int = 116) -> dict:
        return self.observe(now, f"cd {self.wt.as_posix()} && gh api --method POST repos/{DAEMON}/"
                                 f"issues/{issue}/comments -F body=@{body.as_posix()} --jq "
                                 f"'\"\\(.id) \\(.created_at) \\(.html_url)\"'",
                            f"6712 2026-11-06T06:58:33Z {shown(issue)}")

    def use_return(self, now: float) -> None:
        write_bundle(self.home, f"use-{int(now)}", stage="use", launched=now,
                     lifecycle="completed", work=f"{DAEMON}#95", dispatch_id=f"u{int(now)}")
        self.observe(now, self.stage("use", redirect=False), "", started=now - 2)


def posted_head(holder: Holder) -> str | None:
    """The head recorded with the session's one posted release report."""
    reports = core.load_session(holder.ctx(0), HOLDER)["release_reports_posted"]
    (record,) = reports.values()
    return record["head"]


def title_file(holder: Holder, name: str = "release-report.md", head: str | None = HEAD,
               issue: int = 95, pr: int = 116) -> Path:
    path = holder.scratch / "inst1" / name
    tail = f" at head `{head}`" if head else ""
    path.write_text(f"**Release report: #{issue} {ARROW} PR #{pr}**{tail}\n\n## What changed\n",
                    encoding="utf-8")
    return path


PROOF_REPORT = {"schema_version": 1, "work": f"{DAEMON}#95", "stage": "proof",
                "status": "holder-owned", "head": HEAD, "comment": {"id": 1}}
RR_REPORT = {"schema_version": 1, "work": f"{DAEMON}#95", "stage": "release-report",
             "status": "holder-owned", "reason": "holder-named-stage",
             "required_gate": {"verdict": "green", "head": HEAD}}


def rr_decision(head: str | None = HEAD, status: str = "runnable") -> dict:
    gate = {"verdict": "green", "head": head} if head else {"verdict": "green"}
    return {"stage": "release-report", "status": status,
            "reason": "all-evidence-complete-release-report-ready", "required_gate": gate}


def test_c1_1_background_stages_and_a_file_posted_report_wait_on_the_owner(home, tmp_path):
    holder = Holder(home, tmp_path)
    holder.use_return(at("06:30:00"))
    # Proof in the background, its output redirected to a file.
    holder.observe(at("06:41:57"), holder.stage("proof"), holder.launched("bproof"),
                   started=at("06:41:56"), background=True)
    view = holder.tick(at("06:42:30"))
    assert view["label"] == "proof running" and view["running"] is not None
    assert holder.remind(at("06:42:38")) is None
    # The entrance read that started after the launch shows proof as the holder's.
    holder.entrance(at("06:44:51"), {"stage": "proof", "status": "runnable", "reason": "x"})
    holder.observe(at("06:49:20"), holder.stage("release-report"), holder.launched("brr"),
                   started=at("06:49:19"), background=True)
    holder.write_report("proof", PROOF_REPORT, at("06:49:05"))
    assert holder.remind(at("06:49:56")) is None
    holder.write_report("release-report", RR_REPORT, at("06:54:49"))
    view = holder.tick(at("06:55:30"))
    assert view["next_step"] == "post the release report" and view["waiting_on"] == "holder"
    posted_from = len(holder.statuses)
    holder.post(at("06:58:32"), title_file(holder))
    for stop in (at("06:58:40"), at("07:30:00")):
        view = holder.tick(stop)
        assert (view["waiting_on"], view["next_step"]) == ("owner", "merge")
        assert holder.remind(stop) is None
    for read_at in (at("07:55:49"), at("08:31:00"), at("21:00:00")):
        holder.entrance(read_at, rr_decision())
        view = holder.tick(read_at + 30)
        assert (view["waiting_on"], view["next_step"]) == ("owner", "merge")
        assert holder.remind(read_at + 31) is None
    holder.pull_request(116, merged=True)
    assert holder.remind(at("21:53:26")) is None
    assert holder.tick(at("21:53:30"))["waiting_on"] == "owner"
    assert all(status["waiting_on"] == "owner" for status in holder.statuses[posted_from:])
    holder.entrance(at("22:30:00"), {"stage": "terminal", "status": "terminal",
                                     "reason": "issue-or-pull-request-terminal"})
    assert holder.tick(at("22:30:30"))["final"] == "merged"


@pytest.mark.parametrize("form", ["literal", "variable", "relative"])
def test_c1_2_foreground_report_posted_with_gh_pr_comment_body_file(home, tmp_path, form):
    holder = Holder(home, tmp_path)
    holder.observe(at("06:50:00"), holder.stage("release-report", redirect=False),
                   json.dumps(RR_REPORT))
    assert holder.remind(at("06:50:10")) == "next: post the release report (yours)"
    body = title_file(holder)
    command = {
        "literal": f"gh pr comment 116 --repo {DAEMON} --body-file {body.as_posix()}",
        "variable": f"S={holder.scratch.as_posix()}; gh pr comment 116 --body-file $S/inst1/"
                    f"release-report.md",
        "relative": f"cd {holder.scratch.as_posix()} && gh pr comment 116 --body-file "
                    f"inst1/release-report.md",
    }[form]
    holder.observe(at("06:58:32"), command, shown(116))
    view = holder.tick(at("06:58:40"))
    assert (view["waiting_on"], view["next_step"], view["label"]) == ("owner", "merge",
                                                                      "waiting on you")
    assert holder.remind(at("06:58:41")) is None


@pytest.mark.parametrize("case", ["inline", "other-file", "other-issue", "other-pr"])
def test_c1_3_another_comment_leaves_the_report_the_holders(home, tmp_path, case):
    holder = Holder(home, tmp_path)
    holder.pull_request(116)
    holder.observe(at("06:50:00"), holder.stage("release-report", redirect=False),
                   json.dumps(RR_REPORT))
    if case == "inline":
        command = 'gh pr comment 116 --body "Thanks"'
    elif case == "other-file":
        other = holder.scratch / "note.md"
        other.write_text("A note, not the report.\n", encoding="utf-8")
        command = f"gh pr comment 116 --body-file {other.as_posix()}"
    else:
        body = title_file(holder, issue=94) if case == "other-issue" else title_file(holder, pr=117)
        command = f"gh pr comment 116 --body-file {body.as_posix()}"
    holder.observe(at("06:55:00"), command, "")
    view = holder.tick(at("06:55:10"))
    assert view["waiting_on"] == "holder" and view["posted"] is False
    assert holder.remind(at("06:55:11")) == "next: post the release report (yours)"
    assert holder.remind(at("06:55:12")) is None


USE_NOTE_COMMAND = (
    "S={scratch}; python - \"$S\" <<'PY'\n"
    "import pathlib, sys\n"
    "# gh pr comment 116 --body 'not a call: this is inside the heredoc'\n"
    "pathlib.Path(sys.argv[1], 'use95a').mkdir(exist_ok=True)\n"
    "PY\n"
    "cd {wt} && gh api --method POST repos/" + DAEMON + "/issues/116/comments "
    "-F body=@$S/use95a/use-note.md --jq '\"\\(.id) \\(.created_at) \\(.html_url)\"'")


def marker_post(holder: Holder, now: float) -> None:
    (holder.scratch / "use95a").mkdir(exist_ok=True)
    (holder.scratch / "use95a" / "use-note.md").write_text(
        "<!-- tradecraft:use:v1 -->\nThe use note.\n", encoding="utf-8")
    command = USE_NOTE_COMMAND.format(scratch=holder.scratch.as_posix(), wt=holder.wt.as_posix())
    holder.observe(now, command, "1 2026-11-06T04:25:58Z https://github.com/x")


def test_c1_4_a_posted_use_marker_is_not_reminded(home, tmp_path):
    holder = Holder(home, tmp_path)
    holder.pull_request(116)
    holder.use_return(at("04:20:00"))
    marker_post(holder, at("04:25:57"))
    view = holder.tick(at("04:26:00"))
    assert view["label"] == "use posted, unconfirmed" and view["posted"] is True
    assert view["next_step"].endswith("(posted, unconfirmed)")
    assert holder.statuses[-1]["waiting_on"] != "holder"
    assert holder.remind(at("04:26:01")) is None
    # An entrance read after the post that still shows the step as the holder's restores it.
    holder.entrance(at("05:00:00"), {"stage": "use", "status": "holder-owned",
                                     "reason": "use-marker-missing"})
    blocks = [holder.remind(at("05:01:00")), holder.remind(at("05:02:00"))]
    assert [block for block in blocks if block] == ["next: run use (yours)"]


def test_c1_4_recorded_continuations_after_a_marker_post(home, tmp_path):
    holder = Holder(home, tmp_path)
    holder.use_return(at("04:20:00"))
    marker_post(holder, at("04:25:57"))
    catch_up = {"schema_version": 1, "stage": "catch-up", "dispatch": False,
                "status": "holder-owned", "head": HEAD,
                "next": {"stage": "waiting", "status": "waiting",
                         "reason": "latest-check-run-pending"}}
    holder.write_report("catch-up", catch_up, at("04:26:30"))
    holder.observe(at("04:26:40"), holder.stage("catch-up"), "", started=at("04:26:10"))
    view = holder.tick(at("04:27:00"))
    assert view["waiting_on"] == "ci" and view["failure"] is None
    assert holder.remind(at("04:28:46")) is None
    holder.write_report("ready-reviewers", {"stage": "ready-reviewers",
                                            "status": "holder-owned", "head": HEAD},
                        at("05:28:30"))
    holder.observe(at("05:28:40"), holder.stage("ready-reviewers"), "", started=at("05:28:17"))
    view = holder.tick(at("05:28:50"))
    assert view["waiting_on"] == "reviewer"
    assert holder.remind(at("05:28:55")) is None


def test_c1_5_an_unposted_holder_step_is_still_reminded_once(home, tmp_path):
    holder = Holder(home, tmp_path)
    holder.pull_request(116)
    holder.entrance(at("06:00:00"), {"stage": "proof", "status": "runnable", "reason": "x"})
    holder.observe(at("06:10:00"), 'gh pr comment 116 --body "Pushed the fix."', "")
    view = holder.tick(at("06:10:05"))
    assert view["waiting_on"] == "holder" and view["posted"] is False
    blocks = [holder.remind(at("06:10:10")), holder.remind(at("06:11:00"))]
    assert blocks == ["next: run proof (yours)", None]


def test_c1_6_shim_registers_only_the_hook_kinds_it_did():
    source = REGISTER.read_text(encoding="utf-8")
    kinds = set(re.findall(r"\bon\('([a-zA-Z.]+)'", source))
    assert kinds == {"session.start", "command.run", "tool.call", "turn.complete",
                     "classic.Stop", "ui.render"}


@pytest.mark.parametrize("stage", ["proof", "ready-reviewers", "release-report", "catch-up"])
def test_c1_7_no_reminder_while_running_ended_or_posted(home, tmp_path, stage):
    holder = Holder(home, tmp_path)
    holder.entrance(at("06:00:00"), {"stage": stage, "status": "runnable", "reason": "x"})
    holder.observe(at("06:10:01"), holder.stage(stage), holder.launched("t1"),
                   started=at("06:10:00"), background=True)
    view = holder.tick(at("06:10:30"))
    assert view["label"] == f"{stage} running"
    assert holder.remind(at("06:11:00"), tasks=[{"id": "t1", "status": "running"}]) is None
    assert holder.tick(at("06:11:30"))["label"] == f"{stage} running"
    assert holder.remind(at("06:12:00"), tasks=[]) is None
    view = holder.tick(at("06:12:30"))
    assert view["status"] == "ended" and view["label"] == f"{stage} ended"
    assert holder.remind(at("06:13:00")) is None
    # A newer entrance reading ends it, and normal reminding resumes.
    holder.entrance(at("06:40:00"), {"stage": stage, "status": "runnable", "reason": "x"})
    assert holder.remind(at("06:41:00")) == f"next: run {stage} (yours)"


def test_c1_7_a_task_id_inside_a_longer_one_is_not_still_running(home, tmp_path):
    holder = Holder(home, tmp_path)
    holder.entrance(at("06:00:00"), {"stage": "proof", "status": "runnable", "reason": "x"})
    holder.observe(at("06:10:01"), holder.stage("proof"), holder.launched("t1"),
                   started=at("06:10:00"), background=True)
    assert holder.remind(at("06:11:00"), tasks=[{"id": "t10", "status": "running"}]) is None
    assert holder.tick(at("06:11:30"))["status"] == "ended"


def test_c1_7_posted_state_never_reminds(home, tmp_path):
    holder = Holder(home, tmp_path)
    holder.pull_request(116)
    holder.observe(at("06:50:00"), holder.stage("release-report", redirect=False),
                   json.dumps(RR_REPORT))
    holder.observe(at("06:55:00"), "gh pr comment 116 --body-file /no/such/file.md", "")
    assert holder.tick(at("06:55:05"))["posted"] is True
    assert holder.remind(at("06:55:06")) is None


BODY_FORMS = {
    "inline": "gh pr comment 116 --body '{title}'",
    "inline-double": 'gh pr comment 116 --body "{plain}"',
    "heredoc-cat": "gh pr comment 116 --body \"$(cat <<'EOF'\n{title}\nmore\nEOF\n)\"",
    "body-file-dash": "gh pr comment 116 --body-file - <<'EOF'\n{title}\nEOF",
    "raw-field": "gh api repos/{repo}/issues/116/comments -f body='{title}'",
    "field-file": "gh api repos/{repo}/issues/116/comments -F body=@{file}",
    "input-file": "gh api repos/{repo}/issues/116/comments --input {json}",
    "input-dash": "gh api repos/{repo}/issues/116/comments --input - <<'EOF'\n{json_text}\nEOF",
    "var": "S={dir}; gh pr comment 116 --body-file $S/rr.md",
    "braced-var": "S={dir}; gh pr comment 116 --body-file ${{S}}/rr.md",
    "env-var": "$S = '{dir}'; gh pr comment 116 --body-file $env:S/rr.md",
    "tilde": "gh pr comment 116 --body-file ~/rr.md",
    "relative": "cd {dir} && gh pr comment 116 --body-file rr.md",
    "msys": "gh pr comment 116 --body-file {msys}",
    "placeholders": "gh api repos/{{owner}}/{{repo}}/issues/116/comments -X POST -F body=@{file}",
    "issue-comment": "gh issue comment 116 --repo {repo} --body-file {file}",
    "url-target": "gh pr comment https://github.com/{repo}/pull/116 --body-file {file}",
    "quoted-attached-body-file": 'R={file}; gh pr comment 116 --body-file="$R"',
    "quoted-attached-body": 'gh pr comment 116 --body="{plain}"',
    "quoted-attached-input": 'gh api repos/{repo}/issues/116/comments --input="{json}"',
    "quoted-field-file": 'gh api repos/{repo}/issues/116/comments -F body=@"{file}"',
}


@pytest.mark.parametrize("form", sorted(BODY_FORMS))
@pytest.mark.parametrize("head", [f"`{HEAD}`", HEAD, None])
def test_c1_8_title_line_read_from_every_body_form(home, tmp_path, form, head):
    holder = Holder(home, tmp_path)
    holder.pull_request(116)
    folder = holder.home  # `~` resolves to the Ctx's home
    title = f"**Release report: #95 {ARROW} PR #116**" + (f" at head {head}" if head else "")
    body = folder / "rr.md"
    body.write_text(title + "\n\nBody.\n", encoding="utf-8")
    payload = folder / "rr.json"
    payload.write_text(json.dumps({"body": title + "\n"}), encoding="utf-8")
    posix = folder.as_posix()
    msys = f"/{posix[0].lower()}{posix[2:]}/rr.md" if posix[1:2] == ":" else f"{posix}/rr.md"
    command = BODY_FORMS[form].format(title=title, repo=DAEMON, file=body.as_posix(),
                                      json=payload.as_posix(), json_text=json.dumps(
                                          {"body": title}), dir=posix, msys=msys,
                                      plain=title.replace("`", ""))
    holder.entrance(at("06:00:00"), rr_decision(HEAD2))
    holder.observe(at("06:58:32"), command, shown(116))
    view = holder.tick(at("06:58:40"))
    assert (view["waiting_on"], view["next_step"]) == ("owner", "merge"), form
    recorded = posted_head(holder)
    assert recorded == (HEAD if head else HEAD2)


def test_c1_8_an_input_body_larger_than_a_body_files_cap_is_read_whole(home, tmp_path):
    holder = Holder(home, tmp_path)
    holder.pull_request(116)
    holder.observe(at("06:50:00"), holder.stage("release-report", redirect=False),
                   json.dumps(RR_REPORT))
    title = f"**Release report: #95 {ARROW} PR #116** at head `{HEAD}`"
    payload = holder.scratch / "rr.json"
    payload.write_text(json.dumps({"body": title + "\n" + "x" * (core.BODY_LIMIT_BYTES * 2)}),
                       encoding="utf-8")
    holder.observe(at("06:58:32"), f"gh api repos/{DAEMON}/issues/116/comments --input "
                                   f"{payload.as_posix()}", shown(116))
    view = holder.tick(at("06:58:40"))
    assert (view["waiting_on"], view["next_step"]) == ("owner", "merge")


@pytest.mark.parametrize("command", [
    'gh pr comment 116 --body-file "$(pwd)/x.md"',
    'gh pr comment 116 --body "**Release report: #95 ' + ARROW + ' PR #116** at head `git rev-parse HEAD`"',
    "gh api repos/" + DAEMON + "/issues/116/comments -F body=@-",
    "gh pr comment 116 --body-file D:/no/such/report.md",
    "gh pr comment 116 --body-file $UNKNOWN/report.md",
])
def test_c1_8_an_unreadable_body_is_posted_unconfirmed(home, tmp_path, command):
    holder = Holder(home, tmp_path)
    holder.pull_request(116)
    holder.observe(at("06:50:00"), holder.stage("release-report", redirect=False),
                   json.dumps(RR_REPORT))
    holder.observe(at("06:58:32"), command, "")
    view = holder.tick(at("06:58:40"))
    assert view["posted"] is True and view["label"] == "release-report posted, unconfirmed"
    assert view["waiting_on"] == "unknown" and holder.remind(at("06:58:41")) is None
    holder.entrance(at("07:30:00"), rr_decision())
    assert holder.remind(at("07:31:00")) == "next: run release-report (yours)"
    assert holder.remind(at("07:32:00")) is None


def test_c1_8_heredoc_text_and_failed_posts_are_not_posts(home, tmp_path):
    holder = Holder(home, tmp_path)
    holder.pull_request(116)
    holder.observe(at("06:50:00"), holder.stage("release-report", redirect=False),
                   json.dumps(RR_REPORT))
    body = title_file(holder)
    holder.observe(at("06:55:00"), "python - <<'PY'\nprint('gh pr comment 116 --body-file "
                                   f"{body.as_posix()}')\nPY", "")
    assert holder.tick(at("06:55:05"))["waiting_on"] == "holder"
    holder.observe(at("06:56:00"), f"gh pr comment 116 --body-file {body.as_posix()}",
                   "HTTP 502", is_error=True)
    assert holder.tick(at("06:56:05"))["waiting_on"] == "holder"
    holder.observe(at("06:57:00"), f"gh pr comment 116 --body-file {body.as_posix()}",
                   "Exit code 1\nHTTP 502")
    assert holder.tick(at("06:57:05"))["waiting_on"] == "holder"
    # Another repository's pull request of the same number is no post to this change.
    holder.observe(at("06:58:00"), f"gh pr comment 116 -R other/repo --body-file "
                                   f"{body.as_posix()}", "")
    assert holder.tick(at("06:58:05"))["waiting_on"] == "holder"


def posted_holder(home, tmp_path, before: str = "use") -> Holder:
    holder = Holder(home, tmp_path)
    holder.pull_request(116)
    if before == "use":
        holder.use_return(at("06:00:00"))
    else:
        holder.entrance(at("06:00:00"), {"stage": "proof", "status": "runnable", "reason": "x"})
    holder.post(at("06:58:32"), title_file(holder))
    view = holder.tick(at("06:58:40"))
    assert (view["waiting_on"], view["next_step"]) == ("owner", "merge")
    return holder


KEEPS = {
    "catch-up-refused": lambda h: h.observe(at("07:00:00"), h.stage("catch-up", redirect=False),
                                            json.dumps({"stage": "catch-up", "status": "refused",
                                                        "reason": "nothing-to-land"})),
    "catch-up-next-same-head": lambda h: h.observe(
        at("07:00:00"), h.stage("catch-up", redirect=False),
        json.dumps({"stage": "catch-up", "status": "holder-owned", "head": HEAD,
                    "next": rr_decision()})),
    "release-report-rerun": lambda h: h.observe(
        at("07:00:00"), h.stage("release-report", redirect=False), json.dumps(RR_REPORT)),
    "release-report-rerun-background": lambda h: (
        h.observe(at("07:00:00"), h.stage("release-report"), h.launched("b2"),
                  background=True),
        h.write_report("release-report", RR_REPORT, at("07:05:00"))),
    "entrance-same-head": lambda h: h.entrance(at("07:00:00"), rr_decision()),
    "entrance-unknown-head": lambda h: h.entrance(at("07:00:00"), rr_decision(None)),
}


@pytest.mark.parametrize("case", sorted(KEEPS))
@pytest.mark.parametrize("before", ["use", "proof"])
def test_c1_9_same_head_calls_keep_the_owners_merge(home, tmp_path, case, before):
    holder = posted_holder(home, tmp_path, before)
    KEEPS[case](holder)
    for now in (at("07:10:00"), at("07:20:00")):
        view = holder.tick(now)
        assert (view["waiting_on"], view["next_step"]) == ("owner", "merge"), case
        assert holder.remind(now + 1) is None


def test_c1_9_a_background_return_dated_before_the_post_keeps_it(home, tmp_path):
    holder = Holder(home, tmp_path)
    holder.pull_request(116)
    holder.observe(at("06:41:57"), holder.stage("proof"), holder.launched("bp"),
                   started=at("06:41:56"), background=True)
    holder.write_report("proof", {**PROOF_REPORT, "head": HEAD2}, at("06:49:05"))
    holder.post(at("06:58:32"), title_file(holder))
    view = holder.tick(at("06:59:00"))
    assert (view["waiting_on"], view["next_step"]) == ("owner", "merge")
    assert holder.remind(at("06:59:01")) is None


ENDS = {
    "entrance-proof": lambda h: h.entrance(at("07:00:00"), {"stage": "proof",
                                                            "status": "runnable", "reason": "x"}),
    "entrance-waiting": lambda h: h.entrance(at("07:00:00"), {
        "stage": "waiting", "status": "waiting", "reason": "latest-check-run-pending"}),
    "catch-up-lands": lambda h: h.observe(
        at("07:00:00"), h.stage("catch-up", redirect=False),
        json.dumps({"stage": "catch-up", "status": "holder-owned", "head": HEAD2,
                    "next": rr_decision(HEAD2)})),
    "entrance-new-head": lambda h: h.entrance(at("07:00:00"), rr_decision(HEAD2)),
    "catch-up-same-head-next-waiting": lambda h: h.observe(
        at("07:00:00"), h.stage("catch-up", redirect=False),
        json.dumps({"stage": "catch-up", "status": "holder-owned", "head": HEAD,
                    "next": {"stage": "waiting", "status": "waiting",
                             "reason": "latest-check-run-pending"}})),
    "build-launch": lambda h: h.observe(at("07:00:00"), h.stage("build", redirect=False),
                                        "12345"),
}


@pytest.mark.parametrize("case", sorted(ENDS))
def test_c1_9_a_new_head_another_stage_or_new_work_ends_it(home, tmp_path, case):
    holder = posted_holder(home, tmp_path)
    ENDS[case](holder)
    view = holder.tick(at("07:10:00"))
    assert (view["waiting_on"], view["next_step"]) != ("owner", "merge"), case
    if case == "entrance-new-head":
        assert holder.remind(at("07:10:01")) == "next: run release-report (yours)"
        assert holder.remind(at("07:10:02")) is None


def test_c1_9_dispatch_for_another_change_leaves_this_changes_report(home, tmp_path):
    holder = posted_holder(home, tmp_path)
    other = (f"python C:/cache/lib/work.py run build --repo {DAEMON} --issue 96 "
             f"--root {holder.wt.as_posix()}")
    holder.observe(at("07:00:00"), other, "12345")
    assert holder.tick(at("07:00:10"))["next_step"] != "merge"  # the session now shows #96
    holder.observe(at("07:05:00"), holder.stage("release-report", redirect=False),
                   json.dumps(RR_REPORT))
    view = holder.tick(at("07:05:10"))
    assert (view["waiting_on"], view["next_step"]) == ("owner", "merge")
    assert holder.remind(at("07:05:11")) is None


def test_c1_1_a_read_taken_while_a_background_stage_runs_ends_nothing(home, tmp_path):
    holder = Holder(home, tmp_path)
    holder.use_return(at("06:30:00"))
    holder.observe(at("06:41:57"), holder.stage("proof"), holder.launched("bproof"),
                   started=at("06:41:56"), background=True)
    holder.entrance(at("06:44:51"), {"stage": "proof", "status": "runnable", "reason": "x"})
    view = holder.tick(at("06:46:00"))
    assert view["label"] == "proof running"
    assert holder.remind(at("06:46:30")) is None
    holder.write_report("proof", PROOF_REPORT, at("06:49:05"))
    view = holder.tick(at("06:49:30"))
    assert view["next_step"] == "read the entrance's next step (the proof is published)"
    assert "run proof" not in (holder.remind(at("06:49:56")) or "")


def test_c1_9_a_report_counts_only_when_its_post_is_shown(home, tmp_path):
    holder = Holder(home, tmp_path)
    holder.pull_request(116)
    holder.observe(at("06:50:00"), holder.stage("release-report", redirect=False),
                   json.dumps(RR_REPORT))
    body = title_file(holder)
    failed = (f"cd {holder.wt.as_posix()} && gh api --method POST repos/{DAEMON}/issues/116/"
              f"comments -F body=@{body.as_posix()}; echo \"exit=$?\"")
    holder.observe(at("06:58:32"), failed, "HTTP 502: Bad Gateway\nexit=1")
    view = holder.tick(at("06:58:40"))
    assert view["posted"] is True and view["waiting_on"] == "unknown"
    assert holder.remind(at("06:58:41")) is None
    holder.entrance(at("07:30:00"), rr_decision())
    assert holder.remind(at("07:31:00")) == "next: run release-report (yours)"


def test_c1_9_a_backgrounded_report_post_counts_once_its_output_shows_it(home, tmp_path):
    holder = Holder(home, tmp_path)
    holder.pull_request(116)
    holder.observe(at("06:50:00"), holder.stage("release-report", redirect=False),
                   json.dumps(RR_REPORT))
    body = title_file(holder)
    holder.observe(at("06:58:32"), f"gh pr comment 116 --body-file {body.as_posix()}",
                   holder.launched("bpost"), background=True)
    assert holder.tick(at("06:58:40"))["posted"] is True
    (holder.tasks / "bpost.output").write_text(shown(116) + "\n", encoding="utf-8")
    view = holder.tick(at("06:59:00"))
    assert (view["waiting_on"], view["next_step"]) == ("owner", "merge")
    assert holder.remind(at("06:59:01")) is None


def test_c1_9_a_refused_dispatch_leaves_the_posted_report(home, tmp_path):
    holder = posted_holder(home, tmp_path)
    refused = {"stage": "floor", "status": "refused", "reason": "floor-command-missing",
               "dispatch": False}
    holder.observe(at("07:00:00"), holder.stage("floor", redirect=False), json.dumps(refused))
    view = holder.tick(at("07:00:10"))
    assert (view["waiting_on"], view["next_step"]) == ("owner", "merge")
    assert holder.remind(at("07:00:11")) is None


def test_c1_9_reports_posted_for_two_changes_are_both_kept(home, tmp_path):
    holder = posted_holder(home, tmp_path)
    other = (f"python C:/cache/lib/work.py run release-report --repo {DAEMON} --issue 96 "
             f"--root {holder.wt.as_posix()}")
    holder.observe(at("07:00:00"), other, json.dumps({**RR_REPORT, "work": f"{DAEMON}#96"}))
    body = title_file(holder, name="rr96.md", issue=96, pr=117)
    holder.observe(at("07:01:00"), f"gh api --method POST repos/{DAEMON}/issues/117/comments "
                                   f"-F body=@{body.as_posix()}", shown(117))
    assert holder.tick(at("07:01:10"))["next_step"] == "merge"
    holder.observe(at("07:05:00"), holder.stage("release-report", redirect=False),
                   json.dumps(RR_REPORT))
    view = holder.tick(at("07:05:10"))
    assert (view["issue"], view["waiting_on"], view["next_step"]) == (95, "owner", "merge")


def test_c1_9_without_at_head_the_reading_in_forces_head_is_recorded(home, tmp_path):
    holder = Holder(home, tmp_path)
    holder.pull_request(116)
    holder.observe(at("06:50:00"), holder.stage("release-report", redirect=False),
                   json.dumps(RR_REPORT))
    holder.post(at("06:58:32"), title_file(holder, head=None))
    assert posted_head(holder) == HEAD
    holder.entrance(at("07:00:00"), rr_decision(HEAD[:7].upper()))
    assert holder.tick(at("07:00:10"))["waiting_on"] == "owner"
    holder.entrance(at("07:40:00"), rr_decision(HEAD2))
    assert holder.tick(at("07:40:10"))["waiting_on"] == "holder"


def test_c1_10_a_background_failure_or_silent_end(home, tmp_path):
    holder = Holder(home, tmp_path)
    holder.entrance(at("06:00:00"), {"stage": "waiting", "status": "waiting",
                                     "reason": "latest-check-run-pending"})
    holder.observe(at("06:10:01"), holder.stage("proof"), holder.launched("t9"),
                   started=at("06:10:00"), background=True)
    out = holder.scratch / "inst1" / "run-proof.out"
    out.write_text("work: GitHub request failed: 502\n", encoding="utf-8")
    os.utime(out, (at("06:11:00"), at("06:11:00")))
    assert holder.remind(at("06:12:00"), tasks=[]) is None
    view = holder.tick(at("06:12:10"))
    assert view["failure"] == f"proof failed {core.local_hhmm(at('06:12:00'))}"
    # No `work:` line: ended, never a stale step; a report written later is still taken up.
    holder.observe(at("06:20:01"), holder.stage("ready-reviewers"), holder.launched("t10"),
                   started=at("06:20:00"), background=True)
    assert holder.remind(at("06:21:00"), tasks=[]) is None
    assert holder.tick(at("06:21:10"))["status"] == "ended"
    holder.write_report("ready-reviewers", {"stage": "ready-reviewers",
                                            "status": "holder-owned"}, at("06:22:00"))
    assert holder.tick(at("06:22:10"))["waiting_on"] == "reviewer"


def test_k2_an_incomplete_or_stale_report_file_is_no_return(tmp_path):
    path = tmp_path / "run.out"
    report = json.dumps(RR_REPORT, indent=2)
    path.write_text(report[: len(report) // 2], encoding="utf-8")
    os.utime(path, (T0, T0))
    assert core.report_file(path, T0)[0] is None
    path.write_text("x\n" + report + "\n", encoding="utf-8")
    os.utime(path, (T0, T0))
    assert core.report_file(path, T0)[0]["stage"] == "release-report"
    assert core.report_file(path, T0 + 60)[0] is None  # an earlier run's file


@pytest.mark.parametrize("command,expected", [
    ("python lib/work.py run proof --repo R/x --issue 1 > {d}/a.out 2>&1", "a.out"),
    ("python lib/work.py run proof --repo R/x --issue 1 >{d}/a.out", "a.out"),
    ("python lib/work.py run proof --repo R/x --issue 1 >> {d}/a.out", "a.out"),
    ("python lib/work.py run proof --repo R/x --issue 1 &> {d}/a.out", "a.out"),
    ("python lib/work.py run proof --repo R/x --issue 1 *> {d}/a.out", "a.out"),
    ("python lib/work.py run proof --repo R/x --issue 1 | tee -a {d}/a.out", "a.out"),
    ("python lib/work.py run proof --repo R/x --issue 1 | Tee-Object -FilePath {d}/a.out",
     "a.out"),
    ("python lib/work.py run proof --repo R/x --issue 1 | Out-File {d}/a.out", "a.out"),
    ("python lib/work.py run proof --repo R/x --issue 1 2> {d}/err.out", None),
    ("python lib/work.py run proof --repo R/x --issue 1 > $NOPE/a.out", None),
])
def test_k3_redirect_targets(tmp_path, command, expected):
    commands = core.Commands(core.Ctx(home=tmp_path, now=T0, environ={}),
                             command.format(d=tmp_path.as_posix()), None)
    found = commands.redirect()
    assert (found.name if found else None) == expected


# --- finding the desktop app's session records -----------------------------------------------

def current_desktop(tmp_path: Path, source: str | None = "tool", title: str = "Start 888",
                    session: str = SID) -> dict:
    local = tmp_path / "localappdata"
    folder = local / "Claude-Data" / "claude_x" / "claude-code-sessions" / "a" / "b"
    folder.mkdir(parents=True, exist_ok=True)
    record = {"cliSessionId": session, "title": title, "sessionId": "local_1"}
    if source is not None:
        record["titleSource"] = source
    (folder / "local_1.json").write_text(json.dumps(record), encoding="utf-8")
    return {"LOCALAPPDATA": str(local)}


@pytest.mark.parametrize("source,renames", [("tool", True), ("auto", True), ("user", False)])
def test_c2_1_records_in_the_apps_current_place_are_found(home, tmp_path, source, renames):
    environ = current_desktop(tmp_path, source)
    title = allow_title("Start 888")
    core.observe(core.Ctx(home=home, now=T0, environ=environ), {
        "session_id": SID, "command": RUN_BUILD, "output": "", "started_at": T0 - 1,
        "ended_at": T0, "title": title})
    answer = core.tick(core.Ctx(home=home, now=T0 + 1, environ=environ),
                       {"session_id": SID, "title": title})
    assert (answer["rename"] is not None) is renames
    if source == "user":
        assert answer["view"]["rename_note"] == "rename skipped (owner-set title)"
        return
    core.renamed(core.Ctx(home=home, now=T0 + 2, environ=environ), {
        "session_id": SID, "label": answer["rename"]["label"], "title": "#888 x",
        "outcome": "renamed"})
    write_bundle(home, "b1", stage="build", launched=T0, lifecycle="completed", dispatch_id="d")
    again = core.tick(core.Ctx(home=home, now=T0 + 70, environ=environ),
                      {"session_id": SID, "title": title})
    assert again["rename"] == {"label": "holder: build"}


def test_c2_1_old_places_are_still_searched(home, tmp_path):
    environ = desktop(tmp_path, "tool")
    environ["LOCALAPPDATA"] = str(tmp_path / "empty-local")
    core.observe(core.Ctx(home=home, now=T0, environ=environ), {
        "session_id": SID, "command": RUN_BUILD, "output": "", "title": allow_title("Start 888")})
    assert core.tick(core.Ctx(home=home, now=T0 + 1, environ=environ), {
        "session_id": SID, "title": allow_title("Start 888")})["rename"] is not None


def test_c2_2_no_record_anywhere_says_rename_off(home, tmp_path):
    environ = {"LOCALAPPDATA": str(tmp_path / "local"), "APPDATA": str(tmp_path / "roaming")}
    title = allow_title("Start 888")
    core.observe(core.Ctx(home=home, now=T0, environ=environ), {
        "session_id": SID, "command": RUN_BUILD, "output": "", "title": title})
    answer = core.tick(core.Ctx(home=home, now=T0 + 1, environ=environ),
                       {"session_id": SID, "title": title})
    assert answer["rename"] is None
    assert answer["view"]["rename_note"] == "rename off: the app's session records weren't found"
    environ.update(current_desktop(tmp_path, "tool"))
    environ["LOCALAPPDATA"] = str(tmp_path / "localappdata")
    soon = core.tick(core.Ctx(home=home, now=T0 + 60, environ=environ),
                     {"session_id": SID, "title": title})
    assert soon["rename"] is None  # not searched again inside the interval
    later = core.tick(core.Ctx(home=home, now=T0 + core.RECORD_SEARCH_SECONDS + 2,
                               environ=environ), {"session_id": SID, "title": title})
    assert later["rename"] is not None and later["view"]["rename_note"] is None


# --- every repository's Steward is left alone ------------------------------------------------

@pytest.mark.parametrize("name", ["Daemon Steward", "Steward", " daemon steward "])
def test_c3_1_a_steward_draws_nothing_and_writes_nothing(home, tmp_path, name):
    before = tree_files(home)
    assert bind(home, title=allow_title(name, "user")) == {"bound": False}
    holder_root = tmp_path / "holder"
    holder_root.mkdir()
    (home / ".tradecraft" / "implementation-worktrees.json").write_text(json.dumps({
        "worktrees": [{"repository": REPO_NAME, "issue": 888, "active": True,
                       "holder_session_id": SID, "holder_root": str(holder_root)}]}),
        encoding="utf-8")
    candidate = core.recover(ctx_at(home, T0), SID, str(holder_root))
    assert candidate is not None
    assert core._bind_command(ctx_at(home, T0), {"session_id": SID, "binding": candidate,
                                                "title": allow_title(name, "user")}) == {
        "bound": False}
    after = tree_files(home) - {str(Path(".tradecraft") / "implementation-worktrees.json")}
    assert after == before


def test_c3_1_an_unreadable_title_falls_back_to_the_desktop_record(home, tmp_path):
    environ = current_desktop(tmp_path, "user", title="Daemon Steward")
    answer = core.observe(core.Ctx(home=home, now=T0, environ=environ), {
        "session_id": SID, "command": RUN_BUILD, "output": "",
        "title": {"decision": "ask", "text": None}})
    assert answer == {"bound": False}
    assert not core.binding_path(ctx_at(home, T0), SID).exists()
    assert not core.session_path(ctx_at(home, T0), SID).exists()


def test_c3_1_a_session_retitled_steward_is_unbound_and_its_files_removed(home):
    assert bind(home)["bound"] is True
    tick(home, T0 + 1)
    assert core.session_path(ctx_at(home, T0), SID).exists()
    assert tick(home, T0 + 60, title=allow_title("Daemon Steward", "user")) == {"bound": False}
    assert not core.binding_path(ctx_at(home, T0), SID).exists()
    assert not core.session_path(ctx_at(home, T0), SID).exists()


def _bound_and_written(home):
    assert bind(home)["bound"] is True
    tick(home, T0 + 1)
    ctx = ctx_at(home, T0)
    status = core.status_path(ctx, core.change_key(REPO_NAME, 888))
    assert core.binding_path(ctx, SID).exists() and core.session_path(ctx, SID).exists()
    assert status.exists()
    return ctx, status


def test_c3_1_a_steward_met_at_a_stage_call_leaves_no_files(home):
    ctx, status = _bound_and_written(home)
    assert bind(home, now=T0 + 60, title=allow_title("Daemon Steward", "user")) == {
        "bound": False}
    assert not core.binding_path(ctx, SID).exists()
    assert not core.session_path(ctx, SID).exists()
    assert not status.exists()


def test_c3_1_a_steward_met_at_any_other_call_leaves_no_files(home, tmp_path):
    ctx, status = _bound_and_written(home)
    environ = current_desktop(tmp_path, "user", title="Daemon Steward")
    later = T0 + core.RECORD_SEARCH_SECONDS + 5  # past the miss the first tick recorded
    answer = core.observe(core.Ctx(home=home, now=later, environ=environ), {
        "session_id": SID, "command": 'gh pr comment 900 --body "hello"', "output": ""})
    assert answer == {"bound": False}
    assert not core.binding_path(ctx, SID).exists()
    assert not core.session_path(ctx, SID).exists()
    assert not status.exists()


@pytest.mark.parametrize("name", ["Start #95: M6 finals", "Steward review", "Stewardship"])
def test_c3_1_other_titles_still_bind(home, name):
    assert not core.is_steward(name)
    assert bind(home, title=allow_title(name, "auto"))["bound"] is True


# --- a restart binds only by the session's own id --------------------------------------------

OTHER = "c5f2f6e3-0000-4000-8000-000000000000"


def registry(home: Path, *rows: dict) -> None:
    (home / ".tradecraft" / "implementation-worktrees.json").write_text(
        json.dumps({"schema_version": 1, "worktrees": list(rows)}), encoding="utf-8")


def test_c4_1_a_worktree_whose_row_names_another_session_stays_empty(home, tmp_path):
    root = tmp_path / "start-94-da5419"
    root.mkdir()
    registry(home, {"repository": DAEMON, "issue": 95, "active": True, "instalment": "stage-2",
                    "holder_session_id": HOLDER, "holder_root": str(root)})
    assert core.recover(ctx_at(home, T0), OTHER, str(root)) is None


def test_c4_2_a_restarted_holder_gets_its_own_change_back(home, tmp_path):
    root, elsewhere = tmp_path / "wt", tmp_path / "elsewhere"
    root.mkdir()
    elsewhere.mkdir()
    row = {"repository": DAEMON, "issue": 95, "active": True, "instalment": "stage-2",
           "holder_session_id": HOLDER, "holder_root": str(root)}
    registry(home, row)
    found = core.recover(ctx_at(home, T0), HOLDER, str(root))
    assert (found["repository"], found["issue"], found["instalment"]) == (DAEMON, 95, "stage-2")
    # One id on two active changes: narrowed by root, and nothing when still ambiguous.
    registry(home, row, {**row, "issue": 96, "holder_root": str(elsewhere)})
    assert core.recover(ctx_at(home, T0), HOLDER, str(root))["issue"] == 95
    registry(home, row, {**row, "issue": 96})
    assert core.recover(ctx_at(home, T0), HOLDER, str(root)) is None
    # No row naming it: empty until its next stage call binds it.
    registry(home, {**row, "holder_session_id": OTHER})
    assert core.recover(ctx_at(home, T0), HOLDER, str(root)) is None
    command = f"python lib/work.py run proof --repo {DAEMON} --issue 95 --root {root.as_posix()}"
    assert core.observe(ctx_at(home, T0), {"session_id": HOLDER, "command": command,
                                           "output": "", "title": allow_title("x", "auto")})[
        "bound"] is True


# --- the installer across several checkouts --------------------------------------------------

class FakeClaude(FakeTools):
    """The CLI's local-scope effects on the checkout's local file, as the real CLI makes them."""

    def __call__(self, argv, **kwargs):
        answer = super().__call__(argv, **kwargs)
        if argv[0] == "git":
            return answer
        path = Path(kwargs["cwd"]) / ".claude" / "settings.local.json"
        try:
            settings = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except ValueError:
            return answer  # a file that isn't JSON is left alone
        action = argv[1:4]
        if action[:3] == ["plugin", "marketplace", "add"]:
            settings.setdefault("extraKnownMarketplaces", {})[installer.MARKETPLACE] = {
                "source": {"source": "directory", "path": "M"}}
        elif action[:2] == ["plugin", "install"]:
            settings.setdefault("enabledPlugins", {})[installer.PLUGIN_REF] = True
        elif action[:2] == ["plugin", "uninstall"]:
            settings.get("enabledPlugins", {}).pop(installer.PLUGIN_REF, None)
        elif action[:3] == ["plugin", "marketplace", "remove"]:
            settings.get("extraKnownMarketplaces", {}).pop(installer.MARKETPLACE, None)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        return answer


@pytest.fixture
def records(tmp_path, monkeypatch):
    path = tmp_path / "records" / "installs.json"
    monkeypatch.setattr(installer, "_install_record_path", lambda: path)
    return path


def removes(tools: FakeTools) -> int:
    return sum(argv[1:4] == ["plugin", "marketplace", "remove"] for argv in tools.claude)


def test_c5_1_the_shared_marketplace_stays_until_the_last_checkout(tmp_path, records):
    first, second = tmp_path / "a", tmp_path / "b"
    for root in (first, second):
        (root / ".claude").mkdir(parents=True)
    tools = FakeClaude()
    installer.install(first, Path("claude.exe"), tools, marketplace=Path("M"))
    installer.install(second, Path("claude.exe"), tools, marketplace=Path("M"))
    second_bytes = (second / ".claude" / "settings.local.json").read_bytes()
    messages = installer.uninstall(first, Path("claude.exe"), tools)
    assert removes(tools) == 0
    assert any(str(second) in message for message in messages)
    assert (second / ".claude" / "settings.local.json").read_bytes() == second_bytes
    assert str(second) in json.loads(records.read_text())
    installer.uninstall(second, Path("claude.exe"), tools)
    assert removes(tools) == 1


@pytest.mark.parametrize("how", ["gone", "disabled"])
def test_c5_1_a_dead_record_does_not_keep_the_marketplace(tmp_path, records, how):
    first, second = tmp_path / "a", tmp_path / "b"
    for root in (first, second):
        (root / ".claude").mkdir(parents=True)
    tools = FakeClaude()
    installer.install(first, Path("claude.exe"), tools, marketplace=Path("M"))
    installer.install(second, Path("claude.exe"), tools, marketplace=Path("M"))
    if how == "gone":
        import shutil
        shutil.rmtree(second)
    else:
        (second / ".claude" / "settings.local.json").write_text("{}", encoding="utf-8")
    installer.uninstall(first, Path("claude.exe"), tools)
    assert removes(tools) == 1


def test_c5_2_an_absent_local_file_is_absent_again(tmp_path, records):
    root = tmp_path / "a"
    root.mkdir()
    tools = FakeClaude()
    installer.install(root, Path("claude.exe"), tools, marketplace=Path("M"))
    assert (root / ".claude" / "settings.local.json").exists()
    installer.uninstall(root, Path("claude.exe"), tools)
    assert not (root / ".claude" / "settings.local.json").exists()


def test_c5_2_a_present_local_file_comes_back_byte_for_byte(tmp_path, records):
    root = tmp_path / "a"
    (root / ".claude").mkdir(parents=True)
    original = b'{\r\n  "permissions": {"allow": ["Bash(ls)"]},\r\n  "env": {"X": "1"}\r\n}'
    path = root / ".claude" / "settings.local.json"
    path.write_bytes(original)
    tools = FakeClaude()
    installer.install(root, Path("claude.exe"), tools, marketplace=Path("M"))
    installer.install(root, Path("claude.exe"), tools, marketplace=Path("M"))  # a reinstall
    installer.uninstall(root, Path("claude.exe"), tools)
    assert path.read_bytes() == original


def test_c5_2_a_file_changed_after_the_install_keeps_the_change(tmp_path, records):
    root = tmp_path / "a"
    (root / ".claude").mkdir(parents=True)
    path = root / ".claude" / "settings.local.json"
    path.write_text('{"permissions": {"allow": []}}', encoding="utf-8")
    tools = FakeClaude()
    installer.install(root, Path("claude.exe"), tools, marketplace=Path("M"))
    settings = json.loads(path.read_text())
    settings["permissions"]["allow"].append("Bash(git status)")
    path.write_text(json.dumps(settings), encoding="utf-8")
    messages = installer.uninstall(root, Path("claude.exe"), tools)
    assert json.loads(path.read_text()) == {"permissions": {"allow": ["Bash(git status)"]}}
    assert any("byte for byte" in message for message in messages)


def test_c5_2_a_legacy_record_leaves_no_empty_containers(tmp_path, records):
    root = tmp_path / "a"
    (root / ".claude").mkdir(parents=True)
    path = root / ".claude" / "settings.local.json"
    path.write_text('{"permissions": {"allow": []}}', encoding="utf-8")
    tools = FakeClaude()
    installer.install(root, Path("claude.exe"), tools, marketplace=Path("M"))
    records.write_text(json.dumps({str(root): {"added_opt_in": True}}), encoding="utf-8")
    installer.uninstall(root, Path("claude.exe"), tools)
    assert json.loads(path.read_text()) == {"permissions": {"allow": []}}


def test_c5_2_an_unparseable_file_or_snapshot_says_so(tmp_path, records):
    root = tmp_path / "a"
    (root / ".claude").mkdir(parents=True)
    path = root / ".claude" / "settings.local.json"
    path.write_text('{"permissions": {}}', encoding="utf-8")
    tools = FakeClaude()
    installer.install(root, Path("claude.exe"), tools, marketplace=Path("M"))
    path.write_text("not json", encoding="utf-8")
    messages = installer.uninstall(root, Path("claude.exe"), tools)
    assert path.read_text(encoding="utf-8") == "not json"
    assert any("isn't a JSON object now" in message for message in messages)
    path.write_text('{"permissions": {}}', encoding="utf-8")
    installer.install(root, Path("claude.exe"), tools, marketplace=Path("M"))
    for snapshot in ("bm90IGpzb24=", "!!not base64!!"):  # "not json", then not base64 at all
        record = json.loads(records.read_text())
        record[str(root)]["local_before"] = snapshot
        records.write_text(json.dumps(record), encoding="utf-8")
        messages = installer.uninstall(root, Path("claude.exe"), tools)
        assert any("copy taken at the install" in message for message in messages)
        # Left as it is: the installer's own opt-in is still there.
        assert json.loads(path.read_text())["env"] == {installer.OPT_IN: "1"}
        assert json.loads(records.read_text())[str(root)]["local_before"] == snapshot


def test_c5_3_the_desktop_claude_is_found_where_the_app_keeps_it(tmp_path):
    local, roaming = tmp_path / "local", tmp_path / "roaming"
    for base, version in ((local / "Claude-Data" / "claude_x" / "claude-code", "2.1.317"),
                          (local / "Claude-Data" / "claude_x" / "claude-code", "2.1.309"),
                          (roaming / "Claude" / "claude-code", "2.1.300")):
        exe = base / version / "abc123" / "claude.exe"
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"")
    found = installer.newest_desktop_claude({"LOCALAPPDATA": str(local), "APPDATA": str(roaming)})
    assert found == local / "Claude-Data" / "claude_x" / "claude-code" / "2.1.317" / "abc123" \
        / "claude.exe"
    assert installer.newest_desktop_claude({"APPDATA": str(roaming)}).parent.parent.name == \
        "2.1.300"
    assert installer.newest_desktop_claude({}) is None


# --- the trial checklist's checks and their split --------------------------------------------

def test_c6_1_the_checklist_carries_the_new_checks_and_their_split():
    text = README.read_text(encoding="utf-8")
    checklist = text[text.index("## Trial checklist"):]
    for number in range(1, 14):
        assert re.search(rf"^{number}\. \*\*", checklist, re.MULTILINE), number
    assert "Needs no stage call:** 6, 7, 9 and 12" in checklist
    assert "Needs a holder's stage calls:** 1, 2, 3, 4, 5, 8, 10, 11 and 13" in checklist
