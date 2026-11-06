"""The practice's cloud hook: totals, profile, practice check and finish record."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "lib"))
import cloud  # noqa: E402  (hooks/cloud.py)
import cloud_build  # noqa: E402

SESSION = "11111111-2222-3333-4444-555555555555"


def entry(message_id, model, *, sidechain=False, effort=None, output=10, split=True, kind="assistant"):
    usage = {"input_tokens": 3, "output_tokens": output, "cache_read_input_tokens": 100}
    if split:
        usage["cache_creation"] = {"ephemeral_5m_input_tokens": 7, "ephemeral_1h_input_tokens": 11}
    else:
        usage["cache_creation_input_tokens"] = 18
    value = {"type": kind, "isSidechain": sidechain,
             "message": {"id": message_id, "model": model, "usage": usage}}
    if effort:
        value["effort"] = effort
    return value


def write(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(value) + "\n" for value in entries), "utf-8")


def header(branch="claude/tradecraft-report-77-build-abc", repository="Owner/product"):
    return cloud_build.header(work=f"{repository}#77", stage="build", dispatch_id="abc" * 11,
                              checkout="branch tradecraft/77-x", practice_commit="a" * 40,
                              branch=branch)


@pytest.fixture
def session(tmp_path):
    """A session laid out as Claude Code writes one: main, subagents, workflows."""
    projects = tmp_path / "projects" / "slug"
    main = projects / f"{SESSION}.jsonl"
    write(main, [
        {"type": "user", "permissionMode": "auto", "message": {"role": "user", "content": header()}},
        entry("m1", "claude-opus-5-5", effort="high"),
        entry("m1", "claude-opus-5-5", effort="high"),  # one message, two content blocks
        entry("m2", "claude-opus-5-5", effort="high", split=False),
        entry("s1", "claude-sonnet-5", sidechain=True, effort="medium"),
    ])
    write(projects / SESSION / "subagents" / "agent-a.jsonl", [entry("h1", "claude-haiku-4-5-20251001")])
    nested = projects / SESSION / "subagents" / "workflows" / "w1"
    write(nested / "agent-b.jsonl", [entry("h2", "claude-haiku-4-5-20251001", output=5)])
    write(nested / "journal.jsonl", [{"type": "journal", "note": "no usage"}])
    return main


def test_totals_count_distinct_ids_per_model_across_every_file(session):
    counted = cloud.tally(session, SESSION)
    totals = counted["totals_by_model"]
    assert totals["claude-opus-5-5"] == {"input": 6, "output": 20, "cache_read": 200,
                                         "cache_write_5m": 7, "cache_write_1h": 11, "cache_creation": 18}
    assert totals["claude-haiku-4-5-20251001"]["output"] == 15  # subagent usage under its own model
    assert totals["claude-sonnet-5"]["output"] == 10
    assert sorted(row["id"] for row in counted["ledger"]) == ["h1", "h2", "m1", "m2", "s1"]
    files = {row["file"]: row["usage_entries"] for row in counted["files_read"]}
    assert files["main"] == 4 and files["subagents/workflows/w1/journal.jsonl"] == 0
    assert counted["files_unread"] == []
    usage = {key: counted[key] for key in ("files_present", "files_read", "files_unread",
                                           "totals_by_model", "ledger")}
    assert cloud_build.ledger_check(usage, None)["ok"] is True


def test_an_unreadable_listed_file_fails_the_unread_files_check(session):
    (session.parent / SESSION / "subagents" / "agent-x.jsonl").mkdir()
    counted = cloud.tally(session, SESSION)
    assert [row["file"] for row in counted["files_unread"]] == ["subagents/agent-x.jsonl"]
    usage = {key: counted[key] for key in ("files_present", "files_read", "files_unread",
                                           "totals_by_model", "ledger")}
    result = cloud_build.ledger_check(usage, None)
    assert result["ok"] is False and any(fault.startswith("unread files") for fault in result["faults"])


def test_profile_reads_the_main_session_only(session):
    counted = cloud.tally(session, SESSION)
    seen = cloud.profile(counted["main_entries"])
    assert seen == {"models": ["claude-opus-5-5"], "efforts": ["high"]}
    marked = cloud_build.cloud_profile({"profile": seen, "permission_mode": {"values": ["auto"]}})
    assert marked["off_profile"] is False and marked["effort"] == "high"


def test_permission_mode_sources(session):
    entries = cloud.tally(session, SESSION)["main_entries"]
    assert cloud.permission_mode({"permission_mode": "auto"}, entries) == {"values": ["auto"], "source": "hook-input"}
    assert cloud.permission_mode({}, entries) == {"values": ["auto"], "source": "transcript"}
    assert cloud.permission_mode({}, []) == {"values": ["unknown"], "source": None}


def test_header_round_trips():
    fields = cloud.parse_header("prefix\n" + header())
    assert fields["report-branch"] == "claude/tradecraft-report-77-build-abc"
    assert fields["practice-commit"] == "a" * 40 and fields["repository"] == "Owner/product"


# ---- git-backed: a bare remote, the product clone and a practice clone ---------

def git(cwd, *arguments):
    return subprocess.run(["git", "-C", str(cwd), *arguments], check=True, capture_output=True,
                          text=True, stdin=subprocess.DEVNULL).stdout.strip()


@pytest.fixture
def cloud_home(tmp_path, monkeypatch):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True, stdin=subprocess.DEVNULL, capture_output=True)
    seed = tmp_path / "seed"
    subprocess.run(["git", "init", "-q", str(seed)], check=True, stdin=subprocess.DEVNULL, capture_output=True)
    for key, value in (("user.name", "t"), ("user.email", "t@t")):
        git(seed, "config", key, value)
    (seed / "README").write_text("x")
    git(seed, "add", ".")
    git(seed, "commit", "-qm", "seed")
    git(seed, "push", "-q", str(remote), "HEAD:refs/heads/claude/tradecraft-report-77-build-abc")
    home = tmp_path / "home"
    subprocess.run(["git", "clone", "-q", str(remote), str(home / "product")], check=True, stdin=subprocess.DEVNULL, capture_output=True)
    practice = tmp_path / "practice"
    subprocess.run(["git", "init", "-q", str(practice)], check=True, stdin=subprocess.DEVNULL, capture_output=True)
    for key, value in (("user.name", "t"), ("user.email", "t@t")):
        git(practice, "config", key, value)
    (practice / "skills").mkdir()
    (practice / "skills" / "x.md").write_text("x")
    git(practice, "add", ".")
    git(practice, "commit", "-qm", "practice")
    monkeypatch.setenv("TRADECRAFT_CLOUD_HOME", str(home))
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(practice))
    monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")
    return {"remote": remote, "practice": practice, "commit": git(practice, "rev-parse", "HEAD"),
            "branch": cloud.ReportBranch(home / "product", "claude/tradecraft-report-77-build-abc")}


def branch_file(state, name):
    state["branch"].fetch()
    raw = state["branch"].read(name)
    return raw


def messages(state):
    return git(state["remote"], "log", "--format=%s", "claude/tradecraft-report-77-build-abc").splitlines()


def test_prompt_hook_blocks_a_mismatch_and_writes_the_finish_record(cloud_home):
    (cloud_home["practice"] / "AGENTS.md").write_text("doctrine")
    code = cloud.run_prompt({"prompt": header()})
    assert code == 2
    check = json.loads(branch_file(cloud_home, "practice-check.json"))
    assert check["ok"] is False and check["expected"] == "a" * 40 and check["found"] == cloud_home["commit"]
    assert check["excluded_present"] == ["AGENTS.md"]
    files = {name: branch_file(cloud_home, name) for name in ("report.md", "usage.json")}
    assert cloud_build.finished(files)  # the launcher stops waiting on this
    assert b"PRACTICE MISMATCH" in files["report.md"]
    assert all("[skip ci]" in line for line in messages(cloud_home)[:-1])


def test_fallback_check_then_stop_keeps_the_mismatch(cloud_home, session):
    assert cloud.run_check("b" * 40, "claude/tradecraft-report-77-build-abc", "Owner/product") == 1
    assert cloud.run_stop({"session_id": SESSION, "transcript_path": str(session)}) == 0
    usage = json.loads(branch_file(cloud_home, "usage.json"))
    assert usage["practice_check"]["ok"] is False
    assert usage["report_blob"] == cloud_home["branch"].blob("report.md")
    # A later pass never overwrites a recorded mismatch.
    assert cloud.run_check(cloud_home["commit"], "claude/tradecraft-report-77-build-abc", "Owner/product") == 0
    assert json.loads(branch_file(cloud_home, "practice-check.json"))["ok"] is False


def test_stop_without_a_practice_check_writes_ok_null(cloud_home, session):
    assert cloud.run_stop({"session_id": SESSION, "transcript_path": str(session)}) == 0
    usage = json.loads(branch_file(cloud_home, "usage.json"))
    assert usage["practice_check"] == {"ok": None, "reason": "no practice check recorded on the report branch"}
    assert cloud_build.practice_record_check(None, usage)["ok"] is False


def test_hook_commits_carry_skip_ci_and_stop_finishes_after_the_report(cloud_home, session, monkeypatch):
    for name, value in cloud_build.CLOUD_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    assert cloud.run_check(cloud_home["commit"], "claude/tradecraft-report-77-build-abc", "Owner/product") == 0
    cloud_home["branch"].commit({"report.md": b"built\n", "instructions.md": b"CLAUDE.md\n"},
                                "builder report [skip ci]")
    assert cloud.run_stop({"session_id": SESSION, "transcript_path": str(session),
                           "permission_mode": "auto"}) == 0
    files = {name: branch_file(cloud_home, name) for name in ("report.md", "usage.json")}
    assert cloud_build.finished(files)
    usage = json.loads(files["usage.json"])
    assert usage["stop_index"] == 1 and usage["practice_check"]["ok"] is True
    assert usage["permission_mode"]["values"] == ["auto"]
    assert cloud_build.environment_check(usage)["ok"] is True
    assert all("[skip ci]" in line for line in messages(cloud_home)[:-1])
    assert messages(cloud_home)[0].startswith(f"tradecraft cloud usage {SESSION} stop 1")


def test_outside_the_cloud_the_hook_prints_nothing(monkeypatch, capsys):
    monkeypatch.delenv("CLAUDE_CODE_REMOTE", raising=False)
    assert cloud.main(["stop"]) == 0 and cloud.main(["prompt"]) == 0
    assert capsys.readouterr() == ("", "")
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text("utf-8"))["hooks"]
    for event in ("Stop", "UserPromptSubmit"):
        command = hooks[event][0]["hooks"][0]["command"]
        assert command.startswith('[ -n "$CLAUDE_CODE_REMOTE" ] && exec python3 ') and command.endswith("|| true")


def hook_commands():
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text("utf-8"))["hooks"]
    return [hook for event in hooks.values() for group in event for hook in group["hooks"]]


def test_every_hook_names_bash_so_powershell_never_runs_the_posix_guard():
    # Claude Code runs a shell-form hook through PowerShell on a Windows machine without
    # Git Bash unless the hook names its shell; the guard is POSIX syntax.
    assert hook_commands() and all(hook.get("shell") == "bash" for hook in hook_commands())


def posix_shell(name):
    """The shell Claude Code would run a hook through: on Windows, Git for Windows' own."""
    import shutil
    if os.name != "nt":
        return shutil.which(name)
    # System32's bash.exe is the WSL launcher, which Claude Code never uses for a hook.
    configured = os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")
    if configured and name == "bash":
        return configured if Path(configured).is_file() else None
    try:
        exec_path = subprocess.run(["git", "--exec-path"], capture_output=True, text=True,
                                   stdin=subprocess.DEVNULL).stdout.strip()
    except OSError:
        return None
    if not exec_path:
        return None
    root = Path(exec_path).parents[2]  # <git>/mingw64/libexec/git-core
    for candidate in (root / "bin" / f"{name}.exe", root / "usr" / "bin" / f"{name}.exe"):
        if candidate.is_file():
            return str(candidate)
    return None


def test_the_windows_shell_is_never_the_wsl_launcher():
    for name in ("bash", "sh"):
        found = posix_shell(name)
        assert found is None or "system32" not in found.lower()


@pytest.mark.parametrize("shell", ["bash", "sh"])
def test_the_guarded_command_is_silent_outside_the_cloud(tmp_path, shell):
    resolved = posix_shell(shell)
    if not resolved:
        pytest.skip(f"no {shell} from Git for Windows on this machine" if os.name == "nt"
                    else f"no {shell} on this machine")
    shell = resolved
    env = {key: value for key, value in os.environ.items() if key != "CLAUDE_CODE_REMOTE"}
    for hook in hook_commands():
        # Claude Code substitutes the plugin root into the command text before the shell runs it.
        placeholder = "${" + "CLAUDE_PLUGIN_ROOT}"
        command = hook["command"].replace(placeholder, str(tmp_path / "absent"))
        result = subprocess.run([shell, "-c", command], input=b"{}", capture_output=True, env=env)
        assert (result.returncode, result.stdout, result.stderr) == (0, b"", b"")


def test_only_a_line_opening_header_counts_and_the_last_wins():
    saved = cloud_build.ROUTINE_PROMPT.format(practice_name="tradecraft")
    payload = "<routine-fire-payload>" + header(branch="claude/tradecraft-report-77-build-real") + "</routine-fire-payload>"
    fields = cloud.parse_header(saved + "\n" + payload)
    assert fields["report-branch"] == "claude/tradecraft-report-77-build-real"
    assert cloud.parse_header(saved) is None


def test_a_modified_practice_file_fails_the_check(cloud_home):
    (cloud_home["practice"] / "skills" / "x.md").write_text("changed")
    result = cloud.practice_state(cloud_home["practice"], cloud_home["commit"])
    assert result["ok"] is False and result["modified"] == ["skills/x.md"]
    assert cloud.run_check(cloud_home["commit"], "claude/tradecraft-report-77-build-abc", "Owner/product") == 1
    report = branch_file(cloud_home, "report.md")
    assert b"not committed in the practice clone: skills/x.md" in report


def test_a_malformed_line_and_a_bad_counter_are_recorded(session):
    with session.open("a", encoding="utf-8") as stream:
        stream.write("{not json\n")
    bad = entry("m9", "claude-opus-5-5")
    bad["message"]["usage"]["output_tokens"] = "lots"
    with session.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(bad) + "\n")
    counted = cloud.tally(session, SESSION)
    assert {row["file"]: row["malformed_lines"] for row in counted["files_read"]}["main"] == 1
    usage = {key: counted[key] for key in ("files_present", "files_read", "files_unread",
                                           "totals_by_model", "ledger")}
    assert cloud_build.ledger_check(usage, None)["ok"] is False
