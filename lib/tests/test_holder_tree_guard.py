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


@pytest.fixture
def machine_state(tmp_path, monkeypatch):
    home = tmp_path / "home"
    directory = home / ".tradecraft"
    directory.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return directory


def machine_target(directory, name, spelling):
    target = directory / name
    if spelling == "relative":
        return name
    if spelling == "home-relative":
        return f"~/.tradecraft/{name}"
    if spelling == "case-and-separators" and os.name == "nt":
        return str(target).upper().replace("\\", "/")
    return str(target)


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
    assert "implementation worktree registry" in reason
    assert "cannot prove command read-only" in reason
    assert "to edit" not in reason


@pytest.mark.parametrize(("tool", "command"), [
    ("Bash", "echo changed > result.md"),
    ("PowerShell", "Set-Content result.md changed"),
])
def test_shell_write_from_registry_directory_allows_sibling_but_denies_registry(
        tmp_path, monkeypatch, tool, command):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    directory = guard.registry_path().parent
    directory.mkdir()
    reason = guard.decision({
        "tool_name": tool,
        "cwd": str(directory),
        "tool_input": {"command": command},
    }, [])
    assert reason is None
    reason = guard.decision({
        "tool_name": tool,
        "cwd": str(directory),
        "tool_input": {"command": command.replace("result.md", "implementation-worktrees.json")},
    }, [])
    assert "implementation worktree registry" in reason
    assert "cannot prove command read-only" in reason


@pytest.mark.parametrize(("tool", "field"), list(guard.FILE_TOOLS.items()))
@pytest.mark.parametrize("registered", [False, True])
@pytest.mark.parametrize("spelling", ["absolute", "relative", "home-relative", "case-and-separators"])
@pytest.mark.parametrize(("name", "subject"), [
    ("implementation-worktrees.json", "implementation worktree registry"),
    ("implementer-vendor", "machine vendor choice"),
    ("dispatches", "dispatch store"),
    ("dispatches/build/prompt.txt", "dispatch store"),
    ("dispatches/build/return.md", "dispatch store"),
    ("dispatches/build/record.json", "dispatch store"),
    ("model-rulings.json", None),
    ("result.md", None),
    ("dispatches-other/return.md", None),
    ("implementation-worktrees.json.bak", None),
    ("implementer-vendor.old", None),
])
def test_machine_file_boundaries(machine_state, roots, tool, field, registered, spelling, name, subject):
    payload = {
        "tool_name": tool, "cwd": str(machine_state),
        "tool_input": {field: machine_target(machine_state, name, spelling)},
    }
    reason = guard.decision(payload, roots[2] if registered else [])
    if subject:
        assert subject in reason
        assert "not the holder's to edit" in reason
    else:
        assert reason is None


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
@pytest.mark.parametrize("registered", [False, True])
@pytest.mark.parametrize("spelling", ["absolute", "relative", "home-relative", "case-and-separators"])
@pytest.mark.parametrize(("name", "subject"), [
    ("implementation-worktrees.json", "implementation worktree registry"),
    ("implementer-vendor", "machine vendor choice"),
])
@pytest.mark.parametrize("command", [
    "Set-Content '{target}' changed",
    "echo changed > '{target}'",
    "python hash.py '{target}'",
    "cat '{target}'",
    "Get-Content -Raw '{target}'",
    "Test-Path '{target}'",
])
def test_machine_protected_shell_files(
        machine_state, roots, tool, registered, spelling, name, subject, command):
    payload = {
        "tool_name": tool, "cwd": str(machine_state),
        "tool_input": {"command": command.format(target=machine_target(machine_state, name, spelling))},
    }
    reason = guard.decision(payload, roots[2] if registered else [])
    if command.startswith(("Get-Content", "Test-Path")):
        assert reason is None
    else:
        assert subject in reason
        assert "cannot prove command read-only" in reason
        assert "to edit" not in reason


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
@pytest.mark.parametrize("registered", [False, True])
@pytest.mark.parametrize("spelling", ["absolute", "relative", "home-relative"])
@pytest.mark.parametrize("command", [
    "cat '{bundle}'",
    "Get-Content -Raw '{bundle}'",
    "sha256sum '{bundle}'",
    "Get-FileHash '{bundle}'",
    "python hash.py '{bundle}'",
    "gh issue comment 743 --body-file '{bundle}'",
    "python launcher.py --prompt-file '{bundle}'",
    "Set-Content '{bundle}' changed",
    "echo changed > '{bundle}'",
])
def test_dispatch_shell_handling_is_open(machine_state, roots, tool, registered, spelling, command):
    payload = {
        "tool_name": tool, "cwd": str(machine_state),
        "tool_input": {"command": command.format(
            bundle=machine_target(machine_state, "dispatches/build/return.md", spelling))},
    }
    assert guard.decision(payload, roots[2] if registered else []) is None


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
@pytest.mark.parametrize("registered", [False, True])
@pytest.mark.parametrize("name", [
    "dispatches", "model-rulings.json", "result.md", "dispatches-other/return.md",
    "implementation-worktrees.json.bak", "implementer-vendor.old",
])
def test_machine_siblings_do_not_invoke_shell_protection(machine_state, roots, tool, registered, name):
    for target in (name, str(machine_state / name)):
        assert guard.decision({
            "tool_name": tool, "cwd": str(machine_state),
            "tool_input": {"command": f"Set-Content '{target}' changed"},
        }, roots[2] if registered else []) is None


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
@pytest.mark.parametrize("registered", [False, True])
@pytest.mark.parametrize("command", [
    "rm -rf '{target}'", "Remove-Item -Recurse -Force '{target}'", "mv '{target}' tc-old",
    "Set-Content '{target}' changed",
])
def test_shell_containing_directory_cannot_remove_protected_files(machine_state, roots, tool, registered, command):
    _protected, outside, active = roots
    for directory in (machine_state, *machine_state.parents):
        reason = guard.decision({
            "tool_name": tool, "cwd": str(outside),
            "tool_input": {"command": command.format(target=directory.as_posix())},
        }, active if registered else [])
        assert "implementation worktree registry" in reason
        assert "cannot prove command read-only" in reason
    for target in (".", "~/.tradecraft", "~"):
        reason = guard.decision({
            "tool_name": tool, "cwd": str(machine_state),
            "tool_input": {"command": command.format(target=target)},
        }, active if registered else [])
        assert "implementation worktree registry" in reason


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
@pytest.mark.parametrize("registered", [False, True])
@pytest.mark.parametrize(("command", "subject"), [
    ("rm ~/.tradecraft/implementation-*", "implementation worktree registry"),
    ("Set-Content ~/.tradecraft/implementer-vendo? codex", "machine vendor choice"),
    ("Remove-Item ~/.tradecraft/implementation-[w]orktrees.json", "implementation worktree registry"),
    ("rm ~/.tradecraft/implementer-[v]endor", "machine vendor choice"),
    ("rm -rf ~/.tradecraft*", "implementation worktree registry"),
    ("rm -rf ~/.tradecraf?", "implementation worktree registry"),
    ("Remove-Item ~/.tradecraft/implementer-[u-z]endor", "machine vendor choice"),
])
def test_shell_patterns_cannot_change_protected_files(machine_state, roots, tool, registered, command, subject):
    reason = guard.decision({
        "tool_name": tool, "cwd": str(roots[1]), "tool_input": {"command": command},
    }, roots[2] if registered else [])
    assert subject in reason
    assert "cannot prove command read-only" in reason
    assert "to edit" not in reason


@pytest.mark.parametrize(("tool", "pattern", "denied"), [
    ("Bash", "implementer-vendor?", False),
    ("PowerShell", "implementer-vendor?", True),
    ("Bash", "implementer-[!x]endor", True),
    ("PowerShell", "implementer-[!x]endor", False),
    ("Bash", "implementer-[!v]endor", False),
    ("PowerShell", "implementer-[!v]endor", True),
    ("Bash", "implementer-[^x]endor", True),
    ("PowerShell", "implementer-[^x]endor", False),
    ("Bash", "implementer-vendor[?]", False),
    ("PowerShell", "implementer-vendor[?]", False),
])
def test_shell_pattern_characters_follow_shell_rules(machine_state, roots, tool, pattern, denied):
    reason = guard.decision({
        "tool_name": tool, "cwd": str(machine_state),
        "tool_input": {"command": f"rm {pattern}"},
    }, roots[2])
    assert (reason is not None) == denied
    if denied:
        assert "machine vendor choice" in reason


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
def test_shell_pattern_path_case_and_separators_follow_platform(machine_state, roots, tool):
    target = str(machine_state / "implementer-vendo?")
    if os.name == "nt":
        target = target.upper().replace("\\", "/")
    reason = guard.decision({
        "tool_name": tool, "cwd": str(roots[1]),
        "tool_input": {"command": f"Set-Content '{target}' codex"},
    }, roots[2])
    assert "machine vendor choice" in reason


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
@pytest.mark.parametrize("registered", [False, True])
@pytest.mark.parametrize("change", ["cd", "pushd", "chdir", "Set-Location", "Set-Location -LiteralPath"])
@pytest.mark.parametrize("separator", [" && ", " || ", "; ", "\n"])
@pytest.mark.parametrize(("write", "subject"), [
    ("echo codex > implementer-vendor", "machine vendor choice"),
    ("Set-Content implementer-vendor codex", "machine vendor choice"),
    ("rm implementation-worktrees.json", "implementation worktree registry"),
])
def test_shell_changed_directory_resolves_protected_files(
        machine_state, roots, tool, registered, change, separator, write, subject):
    reason = guard.decision({
        "tool_name": tool, "cwd": str(roots[1]),
        "tool_input": {"command": f"{change} ~/.tradecraft{separator}{write}"},
    }, roots[2] if registered else [])
    assert subject in reason
    assert "cannot prove command read-only" in reason


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
@pytest.mark.parametrize("registered", [False, True])
@pytest.mark.parametrize("operator", [">", ">>", "2>", "&>"])
@pytest.mark.parametrize("name", ["implementation-worktrees.json", "implementer-vendor"])
def test_shell_attached_redirection_resolves_protected_file(machine_state, roots, tool, registered, operator, name):
    reason = guard.decision({
        "tool_name": tool, "cwd": str(machine_state),
        "tool_input": {"command": f"echo changed {operator}{name}"},
    }, roots[2] if registered else [])
    assert ("registry" if name == "implementation-worktrees.json" else "vendor choice") in reason
    assert "cannot prove command read-only" in reason


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
@pytest.mark.parametrize("registered", [False, True])
@pytest.mark.parametrize("command", [
    "cd ~/.tradecraft/dispatches/build && sha256sum result.md",
    "Set-Location ~/.tradecraft/dispatches/build; Get-FileHash result.md",
    "Set-Content ~/.tradecraft/model-rulings.json changed",
    "echo changed >~/.tradecraft/model-rulings.json",
    "cd ~/.tradecraft; Set-Content model-rulings.json changed",
    "cp ~/.tradecraft/dispatches/build/return.md result.md",
    "rm ~/.tradecraft/dispatches/*/result.md",
    "rm ~/.tradecraft/implementation-*.bak",
    "Set-Content ~/.tradecraft/implementer-vendo[x] changed",
    "rm ~/.tradecraft/*/implementation-worktrees.json",
    "Get-ChildItem ~/.tradecraft",
    "Test-Path ~/.tradecraft/implementer-vendo?",
    "cd ~/.tradecraft", "pushd ~", "chdir ~/.tradecraft", "Set-Location ~/.tradecraft",
    "cd ~/.tradecraft; cd ../..; echo changed >implementer-vendor",
])
def test_shell_machine_path_negative_controls_remain_open(machine_state, roots, tool, registered, command):
    assert guard.decision({
        "tool_name": tool, "cwd": str(roots[1]), "tool_input": {"command": command},
    }, roots[2] if registered else []) is None


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
@pytest.mark.parametrize("command", [
    "cd ~/.tradecraft; cd dispatches/build; cd ../..; echo codex >implementer-vendor",
    "cd ~/.tradecraft; rm implementation-[w]orktrees.json",
    "bash -c 'cd ~/.tradecraft && echo codex >implementer-vendor'",
    "pwsh -Command 'Set-Location ~/.tradecraft; Set-Content implementer-vendor codex'",
])
def test_shell_nested_and_multiple_directory_changes_protect_files(machine_state, roots, tool, command):
    reason = guard.decision({
        "tool_name": tool, "cwd": str(roots[1]), "tool_input": {"command": command},
    }, roots[2])
    assert "cannot prove command read-only" in reason
    assert "registered implementation trees" not in reason


@pytest.mark.parametrize(("tool", "field"), list(guard.FILE_TOOLS.items()))
def test_file_tool_containing_directory_matching_is_unchanged(machine_state, roots, tool, field):
    for directory in (machine_state, machine_state.parent):
        assert guard.decision({
            "tool_name": tool, "tool_input": {field: str(directory)},
        }, roots[2]) is None


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
def test_refused_registry_deletion_keeps_active_roots(machine_state, roots, tool):
    protected, outside, _registered = roots
    registry = machine_state / "implementation-worktrees.json"
    before = (json.dumps({"schema_version": 1, "worktrees": [
        {"root": str(protected), "active": True},
    ]}) + "\n").encode("utf-8")
    registry.write_bytes(before)
    command = "rm -rf ~/.tradecraft" if tool == "Bash" else "Remove-Item -Recurse -Force ~/.tradecraft"
    reason = guard.decision({
        "tool_name": tool, "cwd": str(outside), "tool_input": {"command": command},
    }, guard.active_roots())
    assert reason is not None
    assert registry.read_bytes() == before
    assert guard.active_roots() == [protected]
    assert guard.decision({
        "tool_name": "Write", "tool_input": {"file_path": str(protected / "file.txt")},
    }, guard.active_roots()) is not None


@pytest.mark.parametrize("name", ["implementation-worktrees.json", "implementer-vendor", "dispatches/x"])
@pytest.mark.parametrize(("tool", "field"), list(guard.FILE_TOOLS.items()))
def test_repository_machine_state_names_are_unrelated(machine_state, roots, name, tool, field):
    _protected, outside, registered = roots
    target = outside / ".tradecraft" / name
    assert guard.decision({
        "tool_name": tool, "tool_input": {field: str(target)},
    }, registered) is None
    assert guard.decision({
        "tool_name": "PowerShell", "cwd": str(outside),
        "tool_input": {"command": f"Set-Content '{target}' changed"},
    }, registered) is None


def test_read_tool_remains_unguarded_at_dispatch_store(machine_state, roots):
    assert guard.decision({
        "tool_name": "Read", "tool_input": {"file_path": str(machine_state / "dispatches/build/return.md")},
    }, roots[2]) is None


@pytest.mark.parametrize("name", ["implementation-worktrees.json", "implementer-vendor"])
@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
def test_bundle_argument_cannot_hide_protected_file(machine_state, roots, name, tool):
    reason = guard.decision({
        "tool_name": tool, "cwd": str(machine_state),
        "tool_input": {"command": f"python copy.py dispatches/build/return.md {name}"},
    }, roots[2])
    assert "cannot prove command read-only" in reason
    assert ("registry" if name == "implementation-worktrees.json" else "vendor choice") in reason


@pytest.mark.parametrize("name", ["dispatches/build/return.md", "model-rulings.json"])
@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
def test_open_machine_paths_do_not_open_builder_tree(machine_state, roots, name, tool):
    protected, outside, registered = roots
    target = machine_state / name
    for cwd, command in (
        (protected, f"python copy.py '{target}' file.txt"),
        (outside, f"python copy.py '{target}' '{protected / 'file.txt'}'"),
    ):
        reason = guard.decision({
            "tool_name": tool, "cwd": str(cwd), "tool_input": {"command": command},
        }, registered)
        assert "registered implementation trees" in reason
        assert "cannot prove command read-only" in reason


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


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
@pytest.mark.parametrize("boundary", ["registry", "vendor", "builder"])
@pytest.mark.parametrize("command", ["git diff", "git show", "git log --stat"])
@pytest.mark.parametrize("supplied", [(), ("--no-textconv",), ("--no-ext-diff",), guard.GIT_HELPER_GUARDS])
def test_helper_hint_alone_repairs_the_command(machine_state, roots, tool, boundary, command, supplied):
    protected, outside, registered = roots
    if boundary == "builder":
        cwd, target, subject = protected, "README.md", "registered implementation trees"
    else:
        cwd = outside
        name = "implementation-worktrees.json" if boundary == "registry" else "implementer-vendor"
        target = str(machine_state / name)
        subject = "implementation worktree registry" if boundary == "registry" else "machine vendor choice"
    payload = {
        "tool_name": tool, "cwd": str(cwd),
        "tool_input": {"command": f"{command} {' '.join(supplied)} -- '{target}'"},
    }
    reason = guard.decision(payload, registered)
    missing = tuple(flag for flag in guard.GIT_HELPER_GUARDS if flag not in supplied)
    if not missing:
        assert reason is None
        return
    assert subject in reason
    assert "cannot prove command read-only" in reason
    assert "; add " + " and ".join(missing) in reason
    for flag in supplied:
        assert flag not in reason
    payload["tool_input"]["command"] = f"{command} {' '.join((*supplied, *missing))} -- '{target}'"
    assert guard.decision(payload, registered) is None


@pytest.mark.parametrize("boundary", ["registry", "vendor", "builder"])
@pytest.mark.parametrize("command", [
    "git diff --output=holder.patch",
    "git show --output holder.patch",
    "git log --stat --unknown-option",
    "git diff --ext-diff",
    "git diff --textconv",
    "git -c core.pager=cat diff",
    "git --config-env=core.pager=PAGER diff",
    "git diff --unknown-option",
    "git diff > holder.patch",
    "git diff; Set-Content x y",
    "bash -c 'git diff; Set-Content x y'",
    "git diff $(echo x)",
    "python diff",
])
def test_independent_refusal_does_not_recommend_helper_flags(machine_state, roots, boundary, command):
    protected, outside, registered = roots
    if boundary == "builder":
        cwd, target, subject = protected, "README.md", "registered implementation trees"
    else:
        cwd = outside
        name = "implementation-worktrees.json" if boundary == "registry" else "implementer-vendor"
        target = str(machine_state / name)
        subject = "implementation worktree registry" if boundary == "registry" else "machine vendor choice"
    reason = guard.decision({
        "tool_name": "PowerShell", "cwd": str(cwd),
        "tool_input": {"command": f"{command} '{target}'"},
    }, registered)
    assert subject in reason
    assert "cannot prove command read-only" in reason
    assert "; add " not in reason
    assert "--no-textconv" not in reason
    assert "--no-ext-diff" not in reason


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
    reason = guard.decision(payload, registered)
    assert "cannot be identified" in reason
    assert "cannot prove command read-only" in reason
    assert "registered implementation trees" in reason
    assert guard.decision(payload, []) is None


def test_nested_body_that_cannot_be_split_is_denied_when_a_root_is_registered(roots):
    _protected, outside, registered = roots
    payload = {"tool_name": "Bash", "cwd": str(outside),
               "tool_input": {"command": 'bash -c "git \'status"'}}
    reason = guard.decision(payload, registered)
    assert "cannot be split" in reason
    assert "cannot prove command read-only" in reason
    assert "registered implementation trees" in reason
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
    reason = guard.decision(payload, [protected])
    assert "inline interpreter names an implementation root" in reason
    assert "cannot prove command read-only" in reason
    assert "registered implementation trees" in reason
    assert guard.decision(payload, []) is None


@pytest.mark.parametrize("command", ["git status;", "git status; ''"])
def test_unsplittable_sequence_explains_missing_proof(roots, command):
    _protected, outside, registered = roots
    reason = guard.decision({
        "tool_name": "Bash", "cwd": str(outside), "tool_input": {"command": command},
    }, registered)
    assert "command sequence cannot be split" in reason
    assert "cannot prove command read-only" in reason
    assert "registered implementation trees" in reason


def test_malformed_command_naming_builder_explains_missing_proof(roots):
    protected, outside, registered = roots
    reason = guard.decision({
        "tool_name": "Bash", "cwd": str(outside),
        "tool_input": {"command": f"git '{protected}' 'unclosed"},
    }, registered)
    assert "cannot prove command read-only" in reason
    assert "registered implementation trees" in reason
    assert "; add " not in reason


def test_nested_depth_limit_explains_missing_proof(roots):
    protected, _outside, registered = roots
    payload = {"tool_name": "Bash", "cwd": str(protected),
               "tool_input": {"command": "eval " * 14 + "git status"}}
    reason = guard.decision(payload, registered)
    assert "nested command depth exceeds the guard limit" in reason
    assert "cannot prove command read-only" in reason
    assert "registered implementation trees" in reason
    payload["tool_input"]["command"] = "eval " * 12 + "git status"
    assert guard.decision(payload, registered) is None


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


@pytest.mark.parametrize(("payload", "registry_bytes", "explanation"), [
    (b'{', b'{"schema_version":1,"worktrees":[]}', "Expecting property name"),
    (b'[]', b'{"schema_version":1,"worktrees":[]}', "hook input must be a JSON object"),
    (b'{}', b'{"schema_version":1,"worktrees":[]}', "hook input must name tool_name"),
    (b'{"tool_name":"Write","tool_input":{}}', b'{"schema_version":1,"worktrees":[]}',
     "Write input has no absolute target path"),
    (b'{"tool_name":"Bash","tool_input":{}}', b'{"schema_version":1,"worktrees":[]}',
     "Bash input has no command"),
    (b'{"tool_name":"Read","tool_input":{}}', b'{', "cannot read implementation worktree registry"),
    (b'{"tool_name":"Read","tool_input":{}}', b'{}', "registry has an unsupported shape"),
])
def test_main_fails_closed_with_evaluation_reason(
        machine_state, monkeypatch, capsys, payload, registry_bytes, explanation):
    (machine_state / "implementation-worktrees.json").write_bytes(registry_bytes)
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(payload), encoding="utf-8"))
    assert guard.main() == 0
    result = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert result["permissionDecision"] == "deny"
    assert "could not evaluate this tool call" in result["permissionDecisionReason"]
    assert explanation in result["permissionDecisionReason"]
    assert "this write" not in result["permissionDecisionReason"]


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
