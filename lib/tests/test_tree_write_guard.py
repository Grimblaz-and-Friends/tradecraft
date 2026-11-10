"""The launch write bound's PreToolUse guard (#906 D1, D2; AC-1 to AC-5)."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import launch_bound
import tree_write_guard as guard

SESSION = "f3e5084f-7317-4d52-9d4f-fa0cdffc3775"


@pytest.fixture
def bound(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".claude" / "projects" / "x" / "memory").mkdir(parents=True)
    (home / ".tradecraft").mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    root = tmp_path / "Tree"
    root.mkdir()
    temp = tmp_path / "temp"
    temp.mkdir()
    env = {"CLAUDE_CODE_TMPDIR": str(temp), "USERPROFILE": str(home), "HOME": str(home)}
    config = launch_bound.guard_config(root, SESSION, env, tmp_path / "log.jsonl")
    other = tmp_path / "other-checkout"
    other.mkdir()
    return {"root": root.resolve(), "home": home, "config": config, "other": other,
            "scratchpad": Path(config["scratchpad"]), "tmp": tmp_path}


def decide(bound, raw, tool="Write", cwd=None):
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    payload = {"tool_name": tool, "tool_use_id": "toolu_1", "tool_input": {key: raw},
               "cwd": str(cwd or bound["root"])}
    return guard.decide(payload, bound["config"])


@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit", "NotebookEdit"])
def test_outside_targets_are_denied_for_every_file_tool(bound, tool):
    home = bound["home"]
    for raw in (str(home / ".claude" / "settings.json"),
                str(home / ".claude" / "projects" / "x" / "memory" / "MEMORY.md"),
                str(home / ".tradecraft" / "implementer-vendor"),
                str(bound["other"] / "file.py"),
                "~/.claude/settings.json", "~/.tradecraft/implementer-vendor"):
        result = decide(bound, raw, tool)
        assert result["decision"] == "deny", raw
        assert raw in result["reason"]


def test_raw_home_form_resolves_to_home_not_under_the_tree(bound):
    result = decide(bound, "~/.claude/settings.json")
    assert result["canonical"] == str((bound["home"] / ".claude" / "settings.json").resolve())


def test_tree_new_subdirectory_and_scratchpad_are_allowed(bound):
    for raw in (str(bound["root"] / "a.py"), str(bound["root"] / "new" / "deeper" / "b.py"),
                "relative/c.py", str(bound["scratchpad"] / "notes.md")):
        assert decide(bound, raw)["decision"] == "allow", raw


def test_scratchpad_derivation_reproduces_both_observed_paths():
    env = {"CLAUDE_CODE_TMPDIR": r"C:\Users\Micah\AppData\Local\Temp"}
    session = "f3e5084f-7317-4d52-9d4f-fa0cdffc3775"
    for suffix in ("9b67a6805ab241ed8b0368b6b6d44bc7", "9b7706228a8d418db26625c2538293de"):
        root = rf"C:\Users\Micah\AppData\Local\Temp\tradecraft-artifact-{suffix}"
        derived = launch_bound.scratchpad(Path(root), session, env)
        slug = "C--Users-Micah-AppData-Local-Temp-tradecraft-artifact-" + suffix
        assert derived["scratchpad_form"] == "exact"
        assert derived["scratchpad"].endswith(os.sep.join(("claude", slug, session, "scratchpad")))


def test_long_slug_is_matched_by_its_narrow_pattern(bound, tmp_path):
    root = tmp_path / ("d" * 230)
    env = {"CLAUDE_CODE_TMPDIR": str(tmp_path / "temp")}
    config = {**bound["config"], **launch_bound.scratchpad(root, SESSION, env), "root": str(root)}
    parent = Path(config["scratchpad_parent"])
    good = parent / (config["scratchpad_slug_prefix"] + "abc123") / SESSION / "scratchpad" / "n.md"
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(good)}, "cwd": str(root)}
    assert guard.decide(payload, config)["decision"] == "allow"
    for bad in (parent / (config["scratchpad_slug_prefix"] + "ab_c") / SESSION / "scratchpad" / "n.md",
                parent / (config["scratchpad_slug_prefix"] + "abc") / "other" / "scratchpad" / "n.md",
                parent / (config["scratchpad_slug_prefix"] + "abc") / SESSION / "n.md"):
        payload["tool_input"]["file_path"] = str(bad)
        assert guard.decide(payload, config)["decision"] == "deny", bad


def test_dotdot_mixed_case_and_slashes(bound):
    assert decide(bound, "../other-checkout/x.py")["decision"] == "deny"
    assert decide(bound, str(bound["root"] / ".." / "other-checkout" / "x.py"))["decision"] == "deny"
    assert decide(bound, str(bound["root"]).replace("\\", "/") + "/ok.py")["decision"] == "allow"
    if os.name == "nt":
        assert decide(bound, str(bound["root"]).upper() + "\\ok.py")["decision"] == "allow"


@pytest.mark.parametrize("raw", [
    "", "a\x00b", r"\\?\C:\x", r"\\.\C:\x", r"\\server\share\x", "//server/share/x", "C:foo",
    "~user/x", "~foo", "%APPDATA%\\x", "$HOME/x", "${HOME}/x", "dir/$_x",
])
def test_ambiguous_forms_are_refused(bound, raw):
    assert decide(bound, raw)["decision"] == "deny"


def test_home_expansion_decides_by_where_it_lands(bound, monkeypatch):
    assert decide(bound, "~")["decision"] == "deny"
    monkeypatch.setenv("USERPROFILE", str(bound["root"]))
    monkeypatch.setenv("HOME", str(bound["root"]))
    assert decide(bound, "~/inside.py")["decision"] == "allow"
    assert decide(bound, "~\\inside.py")["decision"] == "allow"


def test_link_inside_the_tree_pointing_outside_is_refused(bound):
    link = bound["root"] / "escape"
    try:
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(bound["other"])],
                           check=True, stdin=subprocess.DEVNULL, capture_output=True)
        else:
            link.symlink_to(bound["other"], target_is_directory=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        pytest.skip(f"the OS refused to create a link or junction: {exc}")
    result = decide(bound, str(link / "x.py"))
    assert result["decision"] == "deny"
    assert "other-checkout" in result["canonical"]


def test_hard_linked_file_is_refused(bound):
    outside = bound["other"] / "real.txt"
    outside.write_bytes(b"x")
    inside = bound["root"] / "alias.txt"
    try:
        os.link(outside, inside)
    except OSError as exc:
        pytest.skip(f"the OS refused to create a hard link: {exc}")
    assert "hard-linked" in decide(bound, str(inside))["reason"]


@pytest.mark.skipif(os.name != "nt", reason="8.3 short names exist only on Windows")
def test_short_name_of_an_outside_directory_is_refused(bound):
    import ctypes
    long_dir = bound["tmp"] / "a long outside directory"
    long_dir.mkdir()
    buffer = ctypes.create_unicode_buffer(1024)
    if not ctypes.windll.kernel32.GetShortPathNameW(str(long_dir), buffer, 1024) or \
            buffer.value == str(long_dir):
        pytest.skip("this volume has no 8.3 short names")
    result = decide(bound, buffer.value + "\\x.py")
    assert result["decision"] == "deny"
    assert result["canonical"].lower().startswith(str(long_dir.resolve()).lower())


def run_hook(config_path, payload, env=None):
    return subprocess.run([sys.executable, str(guard.__file__), "--config", str(config_path)],
                          input=json.dumps(payload).encode(), capture_output=True, env=env)


def test_hook_process_denies_logs_and_fails_closed(bound, tmp_path):
    config_path = tmp_path / "config.json"
    log = Path(bound["config"]["log"])
    config_path.write_text(json.dumps(bound["config"]), encoding="utf-8")
    outside = {"tool_name": "Write", "tool_use_id": "t1",
               "tool_input": {"file_path": str(bound["other"] / "x")}, "cwd": str(bound["root"])}
    denied = run_hook(config_path, outside)
    assert json.loads(denied.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    inside = {**outside, "tool_use_id": "t2", "tool_input": {"file_path": str(bound["root"] / "y")}}
    assert run_hook(config_path, inside).stdout.strip() == b""
    lines = [json.loads(line) for line in log.read_bytes().splitlines()]
    assert [(line["tool_use_id"], line["decision"]) for line in lines] == [("t1", "deny"), ("t2", "allow")]
    broken = run_hook(tmp_path / "missing.json", inside)
    assert b"could not evaluate" in broken.stdout


def test_memory_store_write_is_refused_and_memory_is_switched_off(bound):
    memory = bound["home"] / ".claude" / "projects" / "x" / "memory" / "note.md"
    assert decide(bound, str(memory))["decision"] == "deny"
    assert decide(bound, "~/.claude/projects/x/memory/note.md")["decision"] == "deny"
    assert launch_bound.memory_record()["requested"].endswith("CLAUDE_CODE_DISABLE_AUTO_MEMORY=1")


def test_a_double_quote_in_a_guard_path_refuses_preparation(bound, tmp_path):
    quoted = tmp_path / 'temp"base'
    with pytest.raises(launch_bound.BoundError, match="double quote"):
        launch_bound.prepare_guard(quoted, bound["root"], SESSION, dict(os.environ), None)
    assert not (tmp_path / 'temp"base').exists() if os.name != "nt" else True


def test_self_test_has_its_own_log_and_a_broken_guard_refuses_preparation(bound, tmp_path,
                                                                                  monkeypatch):
    env = {**os.environ, "CLAUDE_CODE_TMPDIR": str(tmp_path / "temp"),
           "USERPROFILE": str(bound["home"]), "HOME": str(bound["home"])}
    temporary = tmp_path / "invocation"
    temporary.mkdir()
    prepared = launch_bound.prepare_guard(temporary, bound["root"], SESSION, env, None)
    assert Path(prepared["log"]).read_bytes() == b""
    # The file-tool cases come first, then the helper cases.
    assert [case["observed"] for case in prepared["self_test"]] == [
        "deny", "deny", "allow", "allow", "deny", "allow", "deny", "deny", "deny"]
    assert (temporary / "write-guard-self-test" / "write-guard.log.jsonl").read_bytes().count(b"\n") == 9
    command = prepared["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert "\\" not in command and command.count('"') == 6
    broken = tmp_path / "broken"
    broken.mkdir()
    monkeypatch.setattr(launch_bound, "GUARD", tmp_path / "absent_guard.py")
    with pytest.raises(launch_bound.BoundError, match="self-test"):
        launch_bound.prepare_guard(broken, bound["root"], SESSION, env, None)
    assert not (broken / "write-guard.log.jsonl").exists()


def stream(*blocks):
    return "\n".join(json.dumps(block) for block in blocks).encode()


def use(identity, raw, tool="Write"):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": identity, "name": tool, "input": {"file_path": raw}}]}}


def answer(identity, error=False):
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": identity, "is_error": error, "content": "x"}]}}


def test_outcome_cross_check_covers_every_route(tmp_path):
    log = tmp_path / "log.jsonl"
    log.write_bytes(b"")
    completed = stream(use("a", "/t/x"), answer("a"))
    record, reason = launch_bound.guard_outcome(completed, log)
    assert "write bound unproved" in reason and record["unguarded"][0]["result"] == "completed"
    record, reason = launch_bound.guard_outcome(stream(use("a", "/t/x")), log)
    assert "write bound unproved" in reason and record["unguarded"][0]["result"] == "none"
    record, reason = launch_bound.guard_outcome(stream(use("a", "/t/x", "Edit"), answer("a", True)), log)
    assert reason == "" and record["rejected_before_run"] == [{"tool": "Edit", "raw": "/t/x", "tool_use_id": "a"}]
    log.write_bytes(json.dumps({"tool": "Write", "tool_use_id": "a", "raw": "/t/x", "canonical": "/t/x",
                                "decision": "allow"}).encode() + b"\n")
    record, reason = launch_bound.guard_outcome(completed, log)
    assert reason == "" and record["refusals"] == [] and record["decisions"] == 1
    log.write_bytes(json.dumps({"tool": "Write", "tool_use_id": "b", "raw": "/o", "canonical": "/o",
                                "decision": "deny", "reason": "r"}).encode() + b"\n")
    record, reason = launch_bound.guard_outcome(stream(use("b", "/o"), answer("b", True)), log)
    assert reason == "launch bound refused Write /o" and record["rejected_before_run"] == []
