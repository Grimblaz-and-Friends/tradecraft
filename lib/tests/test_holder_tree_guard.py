import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import holder_tree_guard as guard


@pytest.fixture
def roots(tmp_path):
    protected = tmp_path / "Implementation Tree"
    outside = tmp_path / "holder"
    protected.mkdir()
    outside.mkdir()
    registry = tmp_path / "implementation-worktrees.json"
    registry.write_bytes((json.dumps({
        "schema_version": 1,
        "worktrees": [{"root": str(protected), "active": True}],
    }) + "\n").encode())
    return protected.resolve(), outside.resolve(), guard.active_roots(registry)


@pytest.mark.parametrize(("tool", "field"), [
    ("Edit", "file_path"), ("Write", "file_path"), ("NotebookEdit", "notebook_path"),
])
def test_each_file_tool_is_denied_inside_and_has_no_decision_outside(roots, tool, field):
    protected, outside, registered = roots
    inside_payload = {"tool_name": tool, "tool_input": {field: str(protected / "target.txt")}}
    outside_payload = {"tool_name": tool, "tool_input": {field: str(outside / "target.txt")}}
    assert "denied under registered" in guard.decision(inside_payload, registered)
    assert guard.decision(outside_payload, registered) is None


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
def test_write_capable_shell_is_denied_inside_and_unanswered_outside(roots, tool):
    protected, outside, registered = roots
    command = "Set-Content target.txt changed" if tool == "PowerShell" else "echo changed > target.txt"
    assert guard.decision({"tool_name": tool, "cwd": str(protected),
                           "tool_input": {"command": command}}, registered)
    assert guard.decision({"tool_name": tool, "cwd": str(outside),
                           "tool_input": {"command": command}}, registered) is None


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
def test_shell_command_naming_registered_target_is_denied_from_outside(roots, tool):
    protected, outside, registered = roots
    target = protected / "target.txt"
    command = f"Set-Content '{target}' changed" if tool == "PowerShell" else f"echo changed > '{target}'"
    assert guard.decision({"tool_name": tool, "cwd": str(outside),
                           "tool_input": {"command": command}}, registered)


def test_guard_protects_by_path_without_a_work_launcher_allowlist(roots):
    protected, outside, registered = roots
    direct = f'python lib/dispatch_implementer.py --root "{protected}"'
    holder = (
        "python lib/work.py run build --repo acme/widget --issue 7 "
        f'--root "{outside}" --holder-session-id holder'
    )
    assert guard.decision({
        "tool_name": "PowerShell", "cwd": str(outside),
        "tool_input": {"command": direct},
    }, registered)
    assert guard.decision({
        "tool_name": "PowerShell", "cwd": str(outside),
        "tool_input": {"command": holder},
    }, registered) is None


def test_native_git_option_path_has_both_guard_polarities(roots):
    protected, outside, registered = roots
    protected_command = f'git --git-dir="{protected / ".git"}" status'
    outside_command = f'git --git-dir="{outside / ".git"}" status'

    assert guard.decision({
        "tool_name": "PowerShell",
        "cwd": str(outside),
        "tool_input": {"command": protected_command},
    }, registered)
    assert guard.decision({
        "tool_name": "PowerShell",
        "cwd": str(outside),
        "tool_input": {"command": outside_command},
    }, registered) is None


def test_posix_git_option_path_has_both_guard_polarities():
    protected_text = "/tmp/tradecraft-guard/Implementation Tree"
    outside_text = "/tmp/tradecraft-guard/holder"
    protected = guard.canonical(Path(protected_text))
    outside = guard.canonical(Path(outside_text))
    protected_command = f'git --git-dir="{protected_text}/.git" status'
    outside_command = 'git --git-dir="/tmp/tradecraft-guard/Other Tree/.git" status'

    assert guard.decision({
        "tool_name": "Bash",
        "cwd": str(outside),
        "tool_input": {"command": protected_command},
    }, [protected])
    assert guard.decision({
        "tool_name": "Bash",
        "cwd": str(outside),
        "tool_input": {"command": outside_command},
    }, [protected]) is None


def test_separate_git_output_path_has_both_guard_polarities(roots):
    protected, outside, registered = roots
    protected_command = f'git log -o "{protected / "holder.patch"}"'
    outside_command = f'git log -o "{outside / "holder.patch"}"'

    assert guard.decision({
        "tool_name": "PowerShell",
        "cwd": str(outside),
        "tool_input": {"command": protected_command},
    }, registered)
    assert guard.decision({
        "tool_name": "PowerShell",
        "cwd": str(outside),
        "tool_input": {"command": outside_command},
    }, registered) is None


@pytest.mark.parametrize(("tool", "field"), [
    ("Edit", "file_path"), ("Write", "file_path"), ("NotebookEdit", "notebook_path"),
])
def test_each_file_tool_is_denied_at_registry_and_unanswered_elsewhere_in_home(
        tmp_path, monkeypatch, tool, field):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    registry = guard.registry_path()
    unrelated = tmp_path / "notes.txt"

    registry_payload = {"tool_name": tool, "tool_input": {field: str(registry)}}
    unrelated_payload = {"tool_name": tool, "tool_input": {field: str(unrelated)}}

    assert "registry is not the holder's to edit" in guard.decision(registry_payload, [])
    assert guard.decision(unrelated_payload, []) is None


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
def test_registry_bare_name_and_repository_config_path_do_not_imply_registry_access(
        tmp_path, monkeypatch, tool):
    home = tmp_path / "home"
    repository = tmp_path / "repository"
    (repository / ".tradecraft").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)

    for command in ('cat .tradecraft/work.json', 'echo ".tradecraft"'):
        assert guard.decision({
            "tool_name": tool,
            "cwd": str(repository),
            "tool_input": {"command": command},
        }, []) is None


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
def test_read_only_registry_paths_and_registry_working_directory_are_allowed(
        tmp_path, monkeypatch, tool):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    registry = guard.registry_path()
    registry.parent.mkdir()
    bundle = registry.parent / "dispatches" / "build" / "result.md"

    for cwd, command in (
        (tmp_path, f"Get-Content -Raw '{bundle}'"),
        (registry.parent, f"Get-Content -Raw '{registry.name}'"),
    ):
        assert guard.decision({
            "tool_name": tool,
            "cwd": str(cwd),
            "tool_input": {"command": command},
        }, []) is None


@pytest.mark.parametrize(("tool", "command"), [
    ("Bash", 'echo changed > "{registry}"'),
    ("PowerShell", "Set-Content '{registry}' changed"),
])
def test_shell_write_to_resolved_registry_path_is_denied(
        tmp_path, monkeypatch, tool, command):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    registry = guard.registry_path()
    reason = guard.decision({
        "tool_name": tool,
        "cwd": str(tmp_path),
        "tool_input": {"command": command.format(registry=registry)},
    }, [])
    assert "registry is not the holder's to edit" in reason


@pytest.mark.parametrize(("tool", "command"), [
    ("Bash", "echo changed > result.md"),
    ("PowerShell", "Set-Content result.md changed"),
])
def test_shell_write_from_registry_directory_is_denied(
        tmp_path, monkeypatch, tool, command):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    directory = guard.registry_path().parent
    directory.mkdir()
    reason = guard.decision({
        "tool_name": tool,
        "cwd": str(directory),
        "tool_input": {"command": command},
    }, [])
    assert "registry is not the holder's to edit" in reason


@pytest.mark.parametrize("command", [
    "git status --porcelain",
    "git diff --no-textconv --no-ext-diff --stat",
    "git show --no-textconv --no-ext-diff --stat",
    "git show --no-patch",
    "git log --no-textconv --no-ext-diff --stat",
    "git log --oneline",
    "Get-Content -Raw README.md",
    "Test-Path README.md",
])
def test_finite_read_only_commands_are_allowed_inside_registered_root(roots, command):
    protected, _outside, registered = roots
    assert guard.decision({"tool_name": "PowerShell", "cwd": str(protected),
                           "tool_input": {"command": command}}, registered) is None


@pytest.mark.parametrize("command", ["git diff", "git show", "git log --stat"])
def test_git_diffing_commands_name_the_helper_guards_they_require(roots, command):
    protected, _outside, registered = roots
    reason = guard.decision({
        "tool_name": "Bash",
        "cwd": str(protected),
        "tool_input": {"command": command},
    }, registered)
    assert "--no-textconv" in reason
    assert "--no-ext-diff" in reason


def test_git_helper_probe_and_guarded_negative_control(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()
    helper = tmp_path / "helper.py"
    sentinel = tmp_path / "helper-ran"
    helper.write_bytes(
        b"import pathlib, sys\n"
        b"pathlib.Path(sys.argv[1]).write_bytes(b'ran\\n')\n"
        b"if len(sys.argv) == 3:\n"
        b"    sys.stdout.buffer.write(pathlib.Path(sys.argv[2]).read_bytes())\n"
    )

    def git(*arguments):
        result = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
        return result

    git("init")
    git("config", "user.name", "fixture")
    git("config", "user.email", "fixture@example.com")
    (repository / ".gitattributes").write_bytes(b"sample.bin diff=probe\n")
    sample = repository / "sample.bin"
    sample.write_bytes(b"before\n")
    git("add", ".gitattributes", "sample.bin")
    git("commit", "-m", "fixture")
    sample.write_bytes(b"after\n")
    helper_command = f'"{Path(sys.executable).as_posix()}" "{helper.as_posix()}" "{sentinel.as_posix()}"'

    git("config", "diff.probe.textconv", helper_command)
    textconv_commands = [
        (("diff", "--", "sample.bin"),
         ("diff", "--no-textconv", "--no-ext-diff", "--", "sample.bin")),
        (("show", "HEAD"),
         ("show", "--no-textconv", "--no-ext-diff", "HEAD")),
        (("log", "-p", "-1"),
         ("log", "--no-textconv", "--no-ext-diff", "-p", "-1")),
    ]
    for unguarded, guarded in textconv_commands:
        git(*unguarded)
        assert sentinel.is_file()
        sentinel.unlink()
        git(*guarded)
        assert not sentinel.exists()

    git("config", "--unset", "diff.probe.textconv")
    git("config", "diff.probe.command", helper_command)
    git("diff", "--", "sample.bin")
    assert sentinel.is_file()
    sentinel.unlink()
    git("diff", "--no-textconv", "--no-ext-diff", "--", "sample.bin")
    assert not sentinel.exists()


@pytest.mark.parametrize("command", [
    "git diff --output=holder.patch",
    "git log -o x",
    "git diff --output holder.patch",
    "git diff --output-directory=out",
    "git diff --ext-diff",
    "git diff --textconv",
    "git diff --no-textconv --textconv",
    "git -c core.pager=cat diff",
    "git --config-env=core.pager=PAGER diff",
    "git --exec-path=x status",
    "git --git-dir=x status",
    "git --work-tree=x status",
    "git diff --unknown-option",
    "git grep --open-files-in-pager pattern",
    "git branch new-holder-branch",
    "Get-Content -Unknown README.md",
])
def test_write_capable_helper_and_unknown_options_are_denied_inside_root(roots, command):
    protected, _outside, registered = roots
    assert guard.decision({
        "tool_name": "PowerShell",
        "cwd": str(protected),
        "tool_input": {"command": command},
    }, registered)


@pytest.mark.parametrize("command", [
    "git status > state.txt", "git status; Set-Content x y",
    "python -c 'print(1)'", "Get-Content x | Set-Content y",
])
def test_unproved_or_nested_commands_are_denied_inside_registered_root(roots, command):
    protected, _outside, registered = roots
    assert guard.decision({"tool_name": "PowerShell", "cwd": str(protected),
                           "tool_input": {"command": command}}, registered)


@pytest.mark.parametrize("command", [
    "bash -c 'cd protected-tree; echo changed > file'",
    "sh -c 'cd protected-tree; echo changed > file'",
    "zsh -c 'cd protected-tree; echo changed > file'",
    "pwsh -Command 'Set-Location protected-tree; Set-Content file changed'",
    "powershell -c 'chdir protected-tree; Set-Content file changed'",
    "cmd /c 'cd protected-tree && echo changed > file'",
    "eval 'cd protected-tree; echo changed > file'",
    "/usr/bin/bash -c 'cd protected-tree; echo changed > file'",
])
def test_nested_shell_entering_registered_root_is_denied(tmp_path, command):
    protected = (tmp_path / "protected-tree").resolve()
    protected.mkdir()
    payload = {"tool_name": "Bash", "cwd": str(tmp_path),
               "tool_input": {"command": command}}
    assert guard.decision(payload, [protected])
    assert guard.decision(payload, []) is None


@pytest.mark.parametrize("options", ["-lc", "-ec", "-xc", "-cl", "-ce", "-cx"])
def test_clustered_nested_shell_options_entering_registered_root_are_denied(
        tmp_path, options):
    protected = (tmp_path / "protected-root").resolve()
    protected.mkdir()
    payload = {
        "tool_name": "Bash",
        "cwd": str(tmp_path),
        "tool_input": {
            "command": f"bash {options} 'cd protected-root && printf x > owned'",
        },
    }
    assert guard.decision(payload, [protected])
    assert guard.decision(payload, []) is None


@pytest.mark.parametrize("command", ["bash -c 'git status'", "bash -lc 'git status'"])
def test_read_only_nested_shell_outside_root_is_allowed(roots, command):
    _protected, outside, registered = roots
    payload = {"tool_name": "Bash", "cwd": str(outside),
               "tool_input": {"command": command}}
    assert guard.decision(payload, registered) is None


def test_unknown_nested_shell_option_is_denied_when_a_root_is_registered(roots):
    _protected, outside, registered = roots
    payload = {
        "tool_name": "Bash",
        "cwd": str(outside),
        "tool_input": {"command": "bash --unknown-option 'cd protected-root'"},
    }
    assert "cannot be identified" in guard.decision(payload, registered)
    assert guard.decision(payload, []) is None


def test_nested_body_that_cannot_be_split_is_denied_when_a_root_is_registered(roots):
    _protected, outside, registered = roots
    payload = {"tool_name": "Bash", "cwd": str(outside),
               "tool_input": {"command": 'bash -c "git \'status"'}}
    assert "cannot be split" in guard.decision(payload, registered)
    assert guard.decision(payload, []) is None


@pytest.mark.parametrize("command", [
    "python -c 'open(\"protected-tree/file\", \"w\")'",
    "python -\nopen(\"protected-tree/file\", \"w\")",
    "node -e 'writeFileSync(\"protected-tree/file\", \"x\")'",
    "perl -e 'open my $fh, \">\", \"protected-tree/file\"'",
])
def test_inline_interpreter_path_scan_has_both_polarities(tmp_path, command):
    protected = (tmp_path / "protected-tree").resolve()
    protected.mkdir()
    payload = {"tool_name": "Bash", "cwd": str(tmp_path),
               "tool_input": {"command": command}}
    assert guard.decision(payload, [protected])
    assert guard.decision(payload, []) is None


def test_path_case_and_separator_normalization_matches_on_windows(roots):
    protected, _outside, registered = roots
    variant = str(protected / "nested" / "target.txt")
    if os.name == "nt":
        variant = variant.upper().replace("\\", "/")
    payload = {"tool_name": "Write", "tool_input": {"file_path": variant}}
    assert guard.decision(payload, registered)


def test_hook_reads_registry_afresh_for_each_call(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    target = tmp_path / "tree"
    target.mkdir()
    registry = guard.registry_path()
    registry.parent.mkdir()
    registry.write_bytes(b'{"schema_version":1,"worktrees":[]}\n')
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(target / "x")}}
    assert guard.decision(payload, guard.active_roots()) is None
    registry.write_bytes((json.dumps({"schema_version": 1, "worktrees": [
        {"root": str(target), "active": True}
    ]}) + "\n").encode())
    assert guard.decision(payload, guard.active_roots())


def test_main_emits_ascii_deny_json_and_silence_for_outside(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    protected = tmp_path / "tree"
    protected.mkdir()
    registry = guard.registry_path()
    registry.parent.mkdir()
    registry.write_bytes((json.dumps({"schema_version": 1, "worktrees": [
        {"root": str(protected), "active": True}
    ]}) + "\n").encode())
    payload = json.dumps({"tool_name": "Write", "tool_input": {
        "file_path": str(protected / ("snow-" + chr(0x2603)))
    }}).encode()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(payload), encoding="utf-8"))
    assert guard.main() == 0
    output = capsys.readouterr().out.encode("ascii")
    parsed = json.loads(output)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_configured_hook_process_denies_without_changing_revision_or_status(tmp_path):
    protected = tmp_path / "tree"
    protected.mkdir()
    subprocess.run(["git", "init", str(protected)], stdin=subprocess.DEVNULL,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    before_revision = subprocess.run(
        ["git", "-C", str(protected), "rev-parse", "HEAD"], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout
    before_status = subprocess.run(
        ["git", "-C", str(protected), "status", "--porcelain"], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    ).stdout
    registry = tmp_path / ".tradecraft" / "implementation-worktrees.json"
    registry.parent.mkdir()
    registry.write_bytes((json.dumps({"schema_version": 1, "worktrees": [
        {"root": str(protected), "active": True}
    ]}) + "\n").encode())
    payload = json.dumps({"tool_name": "Write", "tool_input": {
        "file_path": str(protected / "blocked.txt")
    }}).encode()
    result = subprocess.run(
        [sys.executable, str(LIB / "holder_tree_guard.py")], input=payload,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        env={**os.environ, "HOME": str(tmp_path), "USERPROFILE": str(tmp_path)},
    )
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert not (protected / "blocked.txt").exists()
    assert subprocess.run(
        ["git", "-C", str(protected), "rev-parse", "HEAD"], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout == before_revision
    assert subprocess.run(
        ["git", "-C", str(protected), "status", "--porcelain"], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    ).stdout == before_status
