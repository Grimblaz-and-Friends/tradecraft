"""Tests for the lab's desktop keep-warm mod (#983 row 5): its core, installer and module.

The core is `tools/keep_warm/marketplace/keep-warm/core/keep_warm_desktop.py`
and the installer `tools/keep_warm/install.py`. Every test passes its own state
directory, transcript root and install record under pytest's temporary
directory; git and the Claude Code CLI are recording fakes, so no test reaches
the real home, a real plugin registry or a real repository. Criterion ids
(AC31 ...) are the affirmed brief's row 5 acceptance criteria on #983.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

TOOLS = Path(__file__).resolve().parents[1]
REPO = TOOLS.parent
KEEP_WARM = TOOLS / "keep_warm"
PLUGIN = KEEP_WARM / "marketplace" / "keep-warm"
CORE = PLUGIN / "core" / "keep_warm_desktop.py"
MODULE = PLUGIN / "hooks" / "register.ts"
README = KEEP_WARM / "README.md"
WAKE_AND_COVER = REPO / "docs" / "cells" / "steward" / "references" / "wake-and-cover.md"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


kw = _load("keep_warm_desktop_core", CORE)
installer = _load("keep_warm_install", KEEP_WARM / "install.py")

SID = "0f3c2a1e-5b6d-4e7f-8a9b-0c1d2e3f4a5b"
T0 = 1_800_000_000.0
HOUR = 3600
ELLIPSIS = chr(0x2026)  # built at runtime so the source stays ASCII


class Git:
    """`git worktree list --porcelain` answering a fixed main checkout first."""

    def __init__(self, main: Path | None):
        self.main = main
        self.calls: list[list[str]] = []

    def __call__(self, argv, **kwargs):
        assert kwargs.get("stdin") is subprocess.DEVNULL and kwargs.get("capture_output") is True
        self.calls.append(list(argv))
        if self.main is None:
            return SimpleNamespace(returncode=128, stdout=b"", stderr=b"not a git repository")
        text = (f"worktree {self.main}\nHEAD 0123abcd\nbranch refs/heads/main\n\n"
                f"worktree {self.main.parent / 'linked'}\nHEAD 4567ef01\ndetached\n\n")
        return SimpleNamespace(returncode=0, stdout=text.encode("utf-8"), stderr=b"")


class Transcript:
    """The session's native transcript under a temporary CLAUDE_CONFIG_DIR."""

    def __init__(self, config: Path, session: str = SID):
        self.path = config / "projects" / "D--Code-practice-checkout" / f"{session}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(b"")

    def _add(self, entry: dict) -> None:
        with self.path.open("ab") as stream:
            stream.write((json.dumps(entry) + "\n").encode("utf-8"))

    def prompt(self, at: float, text: str) -> None:
        self._add({"type": "user", "timestamp": kw.iso(at),
                   "message": {"role": "user", "content": text}})

    def call(self, at: float, read: int = 150_000, written: int = 800, tools=()) -> None:
        content = [{"type": "text", "text": "Warm."}] + [
            {"type": "tool_use", "id": f"toolu_{index}", "name": name, "input": {}}
            for index, name in enumerate(tools)]
        self._add({"type": "assistant", "timestamp": kw.iso(at), "message": {
            "role": "assistant", "model": "claude-opus", "content": content,
            "usage": {"input_tokens": 3, "output_tokens": 2,
                      "cache_read_input_tokens": read, "cache_creation_input_tokens": written}}})


@pytest.fixture
def lab(tmp_path):
    """A practice repository's main checkout, a worktree of it, and a transcript root."""
    main = tmp_path / "practice"
    (main / ".tradecraft").mkdir(parents=True)
    (main / ".tradecraft" / "work.json").write_text("{}", encoding="utf-8")
    worktree = tmp_path / "practice-worktree"
    worktree.mkdir()
    config = tmp_path / "claude-config"
    return SimpleNamespace(main=main, worktree=worktree, state=tmp_path / "state",
                           environ={"CLAUDE_CONFIG_DIR": str(config)},
                           transcript=Transcript(config), git=Git(main))


def at(lab, now: float, settings=None):
    return kw.Ctx(lab.state, now=now, environ=lab.environ, runner=lab.git, settings=settings)


def due(lab, now: float, running: bool = False, tokens: int = 120_000, window=None):
    return kw.due(at(lab, now), SID, running, tokens, window)


def state(lab) -> dict:
    return json.loads((lab.state / "sessions" / f"{SID}.json").read_text(encoding="utf-8"))


def log_lines(lab) -> list[dict]:
    path = lab.state / "log.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def real_turn(lab, now: float) -> None:
    lab.transcript.prompt(now - 30, "the owner's prompt")
    lab.transcript.call(now - 5)
    kw.turn_end(at(lab, now), SID, own=False)


def keep_warm_turn(lab, now: float, read: int = 150_000, written: int = 800, tools=()) -> dict:
    kw.submitted(at(lab, now), SID)
    lab.transcript.prompt(now + 1, f"The keep-warm plugin sent a message: {kw.TEXT}")
    lab.transcript.call(now + 4, read=read, written=written, tools=tools)
    return kw.turn_end(at(lab, now + 5), SID, own=True)


def started(lab, now: float = T0) -> None:
    """A session loaded in the worktree, its last real turn ending at `now`."""
    kw.load(at(lab, now), SID, str(lab.worktree))
    real_turn(lab, now)


# --- the turn's text ----------------------------------------------------------------------

def test_the_turn_says_it_is_not_the_owner_and_asks_for_one_word_and_no_tools():
    assert kw.TEXT.startswith(kw.MARK)
    for words in ("not the owner speaking", "one word", "use no tools"):
        assert words in kw.TEXT


# --- AC35: a repository without the practice ---------------------------------------------------

def test_ac35_a_root_whose_main_checkout_lacks_work_json_is_inert(lab, tmp_path):
    bare = tmp_path / "other"
    (bare / "wt").mkdir(parents=True)
    git = Git(bare)
    ctx = kw.Ctx(lab.state, now=T0, environ=lab.environ, runner=git)
    answer = kw.load(ctx, SID, str(bare / "wt"))
    assert answer["inert"] is True and git.calls[0][-3:] == ["worktree", "list", "--porcelain"]
    real_turn(lab, T0)
    for offset in (0, 3300, 3360, 3400, 2 * HOUR, 9 * HOUR):
        for running in (False, True):
            assert due(lab, T0 + offset, running) == {"submit": False, "reason": "inert"}


def test_ac35_the_main_checkout_is_gits_first_worktree_else_the_root(lab):
    assert kw.load(at(lab, T0), SID, str(lab.worktree))["inert"] is False
    lab.git.main = None  # not a repository: the root itself is read, and it lacks work.json
    assert kw.load(at(lab, T0), SID, str(lab.worktree))["inert"] is True


# --- AC31: the cap ---------------------------------------------------------------------------

def test_ac31_eight_turns_at_the_interval_then_none_at_the_turn_count(lab):
    started(lab)
    last = T0 - 5
    submissions = []
    for _ in range(8):
        assert due(lab, last + kw.INTERVAL_SECONDS - 60)["reason"] == "not-yet"
        now = last + kw.INTERVAL_SECONDS
        answer = due(lab, now)
        assert answer == {"submit": True, "text": kw.TEXT}
        assert keep_warm_turn(lab, now)["fault"] is None
        submissions.append(now)
        last = now + 4
    assert state(lab)["count"] == 8
    assert all(b - a >= kw.INTERVAL_SECONDS for a, b in zip(submissions, submissions[1:]))
    assert due(lab, last + kw.INTERVAL_SECONDS) == {"submit": False, "reason": "cap-turns"}


@pytest.mark.parametrize("count", range(0, 8))
def test_ac31_eight_hours_after_the_last_real_turn_is_false_at_any_count(lab, count):
    started(lab)
    now = T0 + 8 * HOUR
    lab.transcript.call(now - kw.INTERVAL_SECONDS - 60)
    held = state(lab)
    held["count"] = count
    kw.save_state(at(lab, now), SID, held)
    assert due(lab, now) == {"submit": False, "reason": "cap-hours"}
    assert due(lab, now - 60)["submit"] is True  # a minute short of eight hours


# --- AC32 and AC40: a keep-warm turn that broke its rules ------------------------------------

def _stopped_until_a_real_turn(lab, now: float) -> None:
    for offset in (0, 60, kw.INTERVAL_SECONDS, kw.INTERVAL_SECONDS + 60):
        lab.transcript.call(now + offset - kw.INTERVAL_SECONDS)
        assert due(lab, now + offset)["reason"] == "stopped"
    later = now + 2 * kw.INTERVAL_SECONDS
    real_turn(lab, later)
    assert state(lab)["stopped"] is None and state(lab)["count"] == 0
    assert due(lab, later + kw.INTERVAL_SECONDS)["submit"] is True


def test_ac32_a_tool_call_in_a_keep_warm_turn_records_a_fault_and_stops(lab):
    started(lab)
    now = T0 + kw.INTERVAL_SECONDS
    answer = keep_warm_turn(lab, now, tools=("Bash",))
    assert answer["fault"] == "tool-use"
    assert state(lab)["stopped"]["reason"] == "tool-use" and state(lab)["turn_open"] is False
    assert any(line["event"] == "stopped" and line["reason"] == "tool-use"
               and line["tools"] == ["Bash"] for line in log_lines(lab))
    _stopped_until_a_real_turn(lab, now + 10)


@pytest.mark.parametrize("written", [162_530, 5_000])
def test_ac40_a_first_call_that_read_nothing_is_a_miss_and_the_last(lab, written):
    started(lab)
    now = T0 + kw.INTERVAL_SECONDS
    answer = keep_warm_turn(lab, now, read=0, written=written)
    assert answer["fault"] == "miss"
    assert state(lab)["stopped"]["reason"] == "miss"
    assert any(line["event"] == "stopped" and line["cache_read"] == 0
               and line["cache_write"] == written for line in log_lines(lab))
    _stopped_until_a_real_turn(lab, now + 10)


@pytest.mark.parametrize("read,written,miss", [
    (100_000, 20_000, False), (100_000, 20_001, True),
    (1_000_000, 50_000, False), (1_000_000, 50_001, True), (0, 0, True)])
def test_the_write_rule_boundaries(read, written, miss):
    assert kw.missed(read, written) is miss


def test_a_warm_keep_warm_turn_is_logged_and_does_not_stop(lab):
    started(lab)
    answer = keep_warm_turn(lab, T0 + kw.INTERVAL_SECONDS, read=150_000, written=900)
    assert answer["fault"] is None and state(lab)["stopped"] is None
    assert log_lines(lab)[-1]["event"] == "warm"


def test_a_keep_warm_turn_missing_from_the_transcript_stops_unverified(lab):
    started(lab)
    kw.submitted(at(lab, T0 + kw.INTERVAL_SECONDS), SID)
    answer = kw.turn_end(at(lab, T0 + kw.INTERVAL_SECONDS + 5), SID, own=True)
    assert answer["fault"] == "unverified" and state(lab)["turn_open"] is False


# --- AC33: a session reopened after the cache lapsed -------------------------------------------

def test_ac33_a_last_call_seventy_minutes_old_lapses_until_a_real_turn(lab):
    lab.transcript.prompt(T0 - 70 * 60 - 20, "the owner's prompt")
    lab.transcript.call(T0 - 70 * 60)
    kw.load(at(lab, T0), SID, str(lab.worktree))
    assert state(lab)["last_real_end"] == T0 - 70 * 60
    assert due(lab, T0) == {"submit": False, "reason": "lapsed"}
    for tick in range(1, 6):
        assert due(lab, T0 + 60 * tick)["submit"] is False
    real_turn(lab, T0 + 600)
    assert due(lab, T0 + 600 + 55 * 60)["submit"] is True


def test_the_lapse_and_interval_boundaries(lab):
    started(lab)
    called = T0 - 5
    assert due(lab, called + kw.INTERVAL_SECONDS - 1)["reason"] == "not-yet"
    assert due(lab, called + kw.LAPSE_SECONDS)["submit"] is True
    assert due(lab, called + kw.LAPSE_SECONDS + 1)["reason"] == "lapsed"


# --- AC38: never while a turn runs ------------------------------------------------------------

def test_ac38_a_running_turn_is_always_false(lab):
    started(lab)
    for offset in (0, kw.INTERVAL_SECONDS - 1, kw.INTERVAL_SECONDS, kw.LAPSE_SECONDS,
                   kw.LAPSE_SECONDS + 1, 9 * HOUR):
        assert due(lab, T0 + offset, running=True) == {"submit": False,
                                                       "reason": "turn-running"}
    assert due(lab, T0 + kw.INTERVAL_SECONDS)["submit"] is True


def test_an_open_keep_warm_turn_is_never_doubled(lab):
    started(lab)
    kw.submitted(at(lab, T0 + kw.INTERVAL_SECONDS), SID)
    assert due(lab, T0 + kw.INTERVAL_SECONDS + 60)["reason"] == "turn-open"


def test_a_load_closes_a_turn_left_open_by_a_gone_process(lab):
    started(lab)
    kw.submitted(at(lab, T0 + kw.INTERVAL_SECONDS), SID)
    kw.load(at(lab, T0 + kw.INTERVAL_SECONDS + 600), SID, str(lab.worktree))
    assert state(lab)["turn_open"] is False and state(lab)["count"] == 1


# --- the context share and the window ----------------------------------------------------------

@pytest.mark.parametrize("tokens,window,submit", [
    (899_999, None, True), (900_000, None, False),
    (179_999, 200_000, True), (180_000, 200_000, False)])
def test_no_turn_at_ninety_percent_of_the_window(lab, tokens, window, submit):
    started(lab)
    answer = due(lab, T0 + kw.INTERVAL_SECONDS, tokens=tokens, window=window)
    assert answer["submit"] is submit
    if not submit:
        assert answer["reason"] == "context"


def test_no_transcript_means_no_call_and_no_turn(lab):
    kw.load(at(lab, T0), SID, str(lab.worktree))
    lab.transcript.path.unlink()
    assert due(lab, T0 + kw.INTERVAL_SECONDS)["reason"] == "no-call"


# --- the state directory and the probe-only timings -----------------------------------------

@pytest.fixture
def fake_default(tmp_path, monkeypatch):
    """The default state directory under a temporary home, never the real one."""
    home = tmp_path / "home" / ".tradecraft-lab" / "keep-warm"
    monkeypatch.setattr(kw, "default_state_dir", lambda: home)
    monkeypatch.delenv(kw.STATE_ENV, raising=False)
    return home


def test_state_dir_resolution_order(tmp_path, fake_default):
    assert kw.resolve_state_dir(str(tmp_path / "a"), {kw.STATE_ENV: str(tmp_path / "b")}) \
        == tmp_path / "a"
    assert kw.resolve_state_dir(None, {kw.STATE_ENV: str(tmp_path / "b")}) == tmp_path / "b"
    assert kw.resolve_state_dir(None, {}) == fake_default


@pytest.mark.parametrize("name", sorted(kw.PROBE_ENV))
def test_every_probe_timing_is_refused_against_the_default(name, fake_default, capsys):
    with pytest.raises(kw.KeepWarmError, match="refused against the default"):
        kw.settings_for(fake_default, {name: "30"})
    assert kw.main(["due", "--session", SID, "--turn-running", "0", "--context-tokens", "1",
                    "--env", f"{name}=30"]) == 2
    assert "refused against the default" in json.loads(capsys.readouterr().out)["error"]
    assert not fake_default.exists()


def test_probe_timings_are_taken_in_a_probe_directory(lab, fake_default):
    settings = kw.settings_for(lab.state, {"KEEP_WARM_DESKTOP_INTERVAL_SECONDS": "120",
                                           "KEEP_WARM_DESKTOP_LAPSE_SECONDS": "240",
                                           "KEEP_WARM_DESKTOP_CAP_SECONDS": "600",
                                           "KEEP_WARM_DESKTOP_TICK_SECONDS": "10"})
    assert settings == {"interval_seconds": 120, "lapse_seconds": 240, "cap_seconds": 600,
                        "tick_seconds": 10}
    kw.load(at(lab, T0), SID, str(lab.worktree))
    real_turn(lab, T0)
    assert kw.due(at(lab, T0 + 120, settings), SID, False, 1)["submit"] is True
    assert kw.due(at(lab, T0 + 600, settings), SID, False, 1)["reason"] == "lapsed"
    assert kw.settings_for(fake_default, {"KEEP_WARM_DESKTOP_TICK_SECONDS": ""}) == \
        kw.production()


def test_production_values():
    assert kw.production() == {"interval_seconds": 3300, "lapse_seconds": 3420,
                               "cap_seconds": 8 * HOUR, "tick_seconds": 60}
    assert (kw.CAP_TURNS, kw.MISS_FLOOR_TOKENS, kw.MISS_SHARE, kw.CONTEXT_SHARE,
            kw.FALLBACK_WINDOW) == (8, 20_000, 0.05, 0.90, 1_000_000)


def test_the_transcript_root_follows_claude_config_dir(tmp_path, monkeypatch):
    assert kw.claude_projects({"CLAUDE_CONFIG_DIR": str(tmp_path)}) == tmp_path / "projects"
    monkeypatch.setattr(kw.Path, "home", classmethod(lambda cls: tmp_path / "h"))
    assert kw.claude_projects({}) == tmp_path / "h" / ".claude" / "projects"


def test_the_core_runs_as_a_script(lab, tmp_path):
    env = {**os.environ, "CLAUDE_CONFIG_DIR": lab.environ["CLAUDE_CONFIG_DIR"],
           "USERPROFILE": str(tmp_path / "home"), "HOME": str(tmp_path / "home")}
    env.pop(kw.STATE_ENV, None)
    for argv in (["due", "--turn-running", "1", "--context-tokens", "5"],
                 ["fault", "--text", "a module fault"]):
        completed = subprocess.run(
            [sys.executable, str(CORE), *argv, "--session", SID, "--state-dir", str(lab.state)],
            stdin=subprocess.DEVNULL, capture_output=True, env=env)
        assert completed.returncode == 0, completed.stderr
        json.loads(completed.stdout.decode("utf-8"))
    assert log_lines(lab)[-1] == {"at": log_lines(lab)[-1]["at"], "session": SID,
                                  "event": "module-fault", "text": "a module fault"}
    assert not (tmp_path / "home").exists()


# --- AC37: the installer ------------------------------------------------------------------------

def _marketplace_name(folder: Path) -> str:
    return json.loads((folder / ".claude-plugin" / "marketplace.json").read_bytes()
                      .decode("utf-8"))["name"]


class FakeClaude:
    """git answers from a fixture; the CLI's local-scope effects on the checkout's local file."""

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
        path = Path(kwargs["cwd"]) / ".claude" / "settings.local.json"
        settings = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        action, target = argv[1:4], argv[4] if argv[2] == "marketplace" else argv[3]
        if action == ["plugin", "marketplace", "add"]:
            settings.setdefault("extraKnownMarketplaces", {})[
                _marketplace_name(Path(target))] = {"source": {"source": "directory",
                                                               "path": target}}
        elif action[:2] == ["plugin", "install"]:
            settings.setdefault("enabledPlugins", {})[target] = True
        elif action[:2] == ["plugin", "uninstall"]:
            settings.get("enabledPlugins", {}).pop(target, None)
        elif action == ["plugin", "marketplace", "remove"]:
            settings.get("extraKnownMarketplaces", {}).pop(target, None)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")


@pytest.fixture
def records(tmp_path, monkeypatch):
    path = tmp_path / "records" / "installs.json"
    monkeypatch.setattr(installer, "_install_record_path", lambda: path)
    return path


def removes(tools: FakeClaude) -> int:
    return sum(argv[1:4] == ["plugin", "marketplace", "remove"] for argv in tools.claude)


def checkouts(tmp_path, *names):
    roots = [tmp_path / name for name in names]
    for root in roots:
        (root / ".claude").mkdir(parents=True)
    return roots


def test_ac37_uninstalling_one_checkout_leaves_the_others(tmp_path, records):
    first, second = checkouts(tmp_path, "a", "b")
    tools = FakeClaude()
    for root in (first, second):
        installer.install(root, Path("claude.exe"), tools)
    assert json.loads((first / ".claude" / "settings.local.json").read_text())["env"] == {
        installer.OPT_IN: "1"}
    second_bytes = (second / ".claude" / "settings.local.json").read_bytes()
    messages = installer.uninstall(first, Path("claude.exe"), tools)
    assert removes(tools) == 0
    assert any("kept the shared marketplace tradecraft-keep-warm" in message
               and str(second) in message for message in messages)
    assert (second / ".claude" / "settings.local.json").read_bytes() == second_bytes
    assert not (first / ".claude" / "settings.local.json").exists()  # absent again
    installer.uninstall(second, Path("claude.exe"), tools)
    assert removes(tools) == 1
    assert not (second / ".claude" / "settings.local.json").exists()
    assert [argv[1:] for argv in tools.claude][:2] == [
        ["plugin", "marketplace", "add", str(installer.MARKETPLACE_DIR), "--scope", "local"],
        ["plugin", "install", "keep-warm@tradecraft-keep-warm", "--scope", "local"]]
    assert all(argv[-2:] == ["--scope", "local"] for argv in tools.claude)
    for name in ("tradecraft-lab", "tradecraft-holder-pane"):
        assert not any(name in part for argv in tools.claude for part in argv)


OTHERS = ["holder-pane@tradecraft-holder-pane", "steward-wake@tradecraft-lab"]


@pytest.mark.parametrize("other", OTHERS)
def test_ac37_an_opt_in_found_with_the_pane_or_wake_comes_back_byte_for_byte(
        tmp_path, records, other):
    (root,) = checkouts(tmp_path, "a")
    path = root / ".claude" / "settings.local.json"
    original = json.dumps({"enabledPlugins": {other: True},
                           "env": {installer.OPT_IN: "1"}}).encode("utf-8")
    path.write_bytes(original)
    installer.install(root, Path("claude.exe"), FakeClaude())
    installer.uninstall(root, Path("claude.exe"), FakeClaude())
    assert path.read_bytes() == original


@pytest.mark.parametrize("other", OTHERS)
def test_ac37_the_opt_in_this_installer_added_stays_while_the_pane_or_wake_needs_it(
        tmp_path, records, other):
    (root,) = checkouts(tmp_path, "a")
    path = root / ".claude" / "settings.local.json"
    installer.install(root, Path("claude.exe"), FakeClaude())
    settings = json.loads(path.read_text(encoding="utf-8"))
    settings["enabledPlugins"][other] = True  # the pane or the wake, installed afterwards
    path.write_text(json.dumps(settings), encoding="utf-8")
    messages = installer.uninstall(root, Path("claude.exe"), FakeClaude())
    after = json.loads(path.read_text(encoding="utf-8"))
    assert after["enabledPlugins"] == {other: True}
    assert after["env"] == {installer.OPT_IN: "1"}
    assert "extraKnownMarketplaces" not in after
    assert any(other in message for message in messages)


@pytest.mark.parametrize("tracked,ignored", [(True, True), (True, False), (False, False)])
def test_install_refuses_a_tracked_or_unignored_local_file(tmp_path, records, tracked, ignored):
    (root,) = checkouts(tmp_path, "a")
    path = root / ".claude" / "settings.local.json"
    path.write_bytes(b"{}")
    tools = FakeClaude(tracked=tracked, ignored=ignored)
    with pytest.raises(installer.Refused):
        installer.install(root, Path("claude.exe"), tools)
    assert path.read_bytes() == b"{}" and tools.claude == [] and not records.exists()


def test_the_mods_names_are_its_own():
    """#915's failure: a second `marketplace add` under a registered name repoints it."""
    ours = _marketplace_name(KEEP_WARM / "marketplace")
    assert ours == installer.MARKETPLACE == "tradecraft-keep-warm"
    assert installer.PLUGIN_REF == "keep-warm@tradecraft-keep-warm"
    assert ours not in {_marketplace_name(TOOLS / "steward-wake"),
                        _marketplace_name(TOOLS / "holder_pane" / "marketplace")}
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert (manifest["name"], manifest["version"]) == ("keep-warm", "0.1.0")
    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    assert hooks == {"modules": ["./register.ts"]}


def test_the_install_record_lives_in_the_lab_state_root(monkeypatch, tmp_path):
    monkeypatch.setattr(installer.Path, "home", classmethod(lambda cls: tmp_path))
    assert installer._install_record_path() == tmp_path / ".tradecraft-lab" / "keep-warm" \
        / "installs.json"


# --- the module, statically --------------------------------------------------------------------

def _module() -> str:
    return MODULE.read_bytes().decode("utf-8")


def test_the_module_writes_nothing_draws_nothing_and_calls_no_model():
    text = _module()
    for forbidden in ("$.fs", "$.store", "$.model", "$.ui", "$.agent", "$.http", "writeFile",
                      "require("):
        assert forbidden not in text, forbidden
    assert text.count("$.prompt.submit(") == 1
    assert "keep_warm_desktop.py" in text


def test_the_module_submits_only_when_idle_and_refuses_tools_only_in_its_own_turn():
    text = _module()
    tick = text.split("async function tick($: $) {", 1)[1].split("\n}\n", 1)[0]
    assert tick.index("if (state.ticking || state.inert || state.turnRunning || state.pending) "
                      "return") < tick.index("'due'") < tick.index("state.pending = true") \
        < tick.index("$.prompt.submit(")
    assert "if (!state.own || next.origin.plugin !== 'engine') return next(e)" in text
    assert "return { deny: REFUSAL }" in text


def test_the_module_passes_the_state_dir_and_every_probe_timing():
    text = _module()
    assert "if (dir) flags.push('--state-dir', dir)" in text
    for name in [kw.STATE_ENV, *kw.PROBE_ENV]:
        assert f"await $.env.get('{name}')" in text


# --- the lab's documents and the wall -------------------------------------------------------------

def test_nothing_shipped_names_the_mod():
    names = ("tradecraft-keep-warm", "keep_warm_desktop", "tools/keep_warm", "KEEP_WARM_LAB",
             "KEEP_WARM_DESKTOP")
    for shipped in ("hooks", "lib", "skills", "commands", "agents", ".claude-plugin"):
        root = REPO / shipped
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in (".py", ".md", ".json", ".ts", ".js"):
                text = path.read_text(encoding="utf-8", errors="replace")
                for name in names:
                    assert name not in text, (path, name)


def test_ac39_the_readme_carries_approval_install_undo_and_the_probes():
    text = README.read_text(encoding="utf-8")
    install = text[text.index("## Install"):]
    assert re.search(r"approv", install.split("\n\n", 2)[1], re.IGNORECASE)
    for words in ("tradecraft-keep-warm", "--scope local", "CLAUDE_CODE_ENABLE_FUNCTION_HOOKS",
                  "## Undo", "one word", "python tools/keep_warm/install.py uninstall"):
        assert words in text, words
    probes = text[text.index("## Probe checklist"):]
    for number in range(1, 9):
        assert re.search(rf"^- \*\*P{number}\b", probes, re.MULTILINE), number


def test_ac39_the_wakes_undo_names_keep_warm():
    text = WAKE_AND_COVER.read_text(encoding="utf-8")
    undo = text[text.index("## Undo"):text.index("## Moving")]
    step = next(line for line in undo.splitlines() if line.startswith("3. "))
    assert f"`holder-pane@{ELLIPSIS}`" in step and f"`keep-warm@{ELLIPSIS}`" in step
    assert "keep-warm" in text[:text.index("## Undo")]
