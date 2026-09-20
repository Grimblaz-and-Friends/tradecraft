import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import dispatch_seat as seat
from vendor_cli import CliNotFound

NOW = datetime(2026, 9, 12, 12, tzinfo=timezone.utc)


def git(root, *arguments):
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=True,
    )


@pytest.fixture(scope="module")
def primary_template(tmp_path_factory):
    """The primary repository below, built once and copied per test.

    Three `git` launches make it, and on Windows each costs an order of
    magnitude more than the copy that reproduces it. Nothing is shared between
    tests as a result: each still gets its own primary, byte-identical and
    observable by nothing else. A repository with one ordinary commit records
    no absolute path, so the copy is valid wherever it lands.

    The worktree is **not** part of the template and cannot be: `.git` and
    `worktrees/<name>/gitdir` hold absolute paths, so a copied worktree points
    back at the directory it came from. `worktree add` and its teardown stay
    per test. [#649]
    """
    template = tmp_path_factory.mktemp("primary-template")
    git(template, "init")
    (template / "fixture.txt").write_bytes(b"fixture\n")
    git(template, "add", "fixture.txt")
    git(template, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-m", "fixture")
    return template


def linked_detached_worktree(root, template):
    primary = root.parent / "primary"
    shutil.copytree(template, primary)
    git(primary, "worktree", "add", "--detach", str(root))
    return primary


@pytest.fixture
def job(tmp_path, monkeypatch, primary_template):
    root = tmp_path / "root with spaces"
    primary = linked_detached_worktree(root, primary_template)
    dispatch = tmp_path / "dispatch.txt"
    dispatch.write_bytes(b"Read the supplied artifact and return your verdict.\n")
    scenario = tmp_path / "scenario.json"
    scenario.write_bytes(b"{}")
    args = seat.parser().parse_args([
        "--dispatch", str(dispatch), "--root", str(root), "--vendor", "claude",
        "--own-vendor", "codex", "--output", str(tmp_path / "verdict.md"),
        "--work", "issue-592", "--stage", "cold-read",
        "--classification", "ordinary",
        "--requires", "read",
        "--settings-source", "issuecomment-5655702442",
        "--settings-scope", "Codex turns after the artifact",
        "--hold-file", str(tmp_path / "holds"), "--timeout-seconds", "10",
    ])
    def resolver(vendor, explicit):
        return [sys.executable, str(LIB / "tests/seat_cli.py"), vendor, str(scenario)]
    monkeypatch.setattr(seat, "resolve_command", resolver)
    monkeypatch.setattr(seat.records, "runtime_version", lambda *_: "fixture-cli 1.0")
    yield args, scenario
    git(primary, "worktree", "remove", "--force", str(root))


def configure(job, config):
    job[1].write_bytes(json.dumps(config).encode())


def record(args):
    return json.loads(seat.sidecar(args.output, ".run.json").read_bytes())


def seen(args, vendor):
    return json.loads((args.root / f"seen-{vendor}.json").read_bytes())


@pytest.mark.parametrize(("vendor", "required_capability"), [
    ("claude", "read"), ("claude", "execute"), ("codex", "read"),
])
def test_real_child_receives_large_utf8_dispatch_and_exact_launch(job, vendor, required_capability):
    args, _ = job
    args.vendor = vendor
    args.own_vendor = "claude" if vendor == "codex" else "codex"
    args.requires = required_capability
    prompt = (("quoted ' \" $() ` & | ; % ! " + chr(0x1F680) + "\n") * 2500).encode()
    args.dispatch.write_bytes(prompt)
    assert seat.run_dispatch(args) == 0
    observed = seen(args, vendor)
    assert base64.b64decode(observed["stdin"]) == prompt
    assert Path(observed["cwd"]) == args.root.resolve()
    flags = observed["argv"]
    if vendor == "claude":
        tools = "Read,Glob,Grep,Bash" if required_capability == "execute" else "Read,Glob,Grep"
        assert flags == ["-p", "--model", "opus", "--effort", "xhigh", "--output-format", "json",
                         "--no-session-persistence", "--safe-mode", "--tools", tools,
                         "--allowedTools", tools, "--permission-mode", "dontAsk", "--strict-mcp-config"]
    else:
        last = flags[flags.index("--output-last-message") + 1]
        assert flags == ["exec", "--strict-config", "--ephemeral", "--sandbox", "read-only",
                         "--json", "--color", "never", "--model", "gpt-5.6-sol",
                         "-c", "apps._default.enabled=false",
                         "-c", 'model_reasoning_effort="xhigh"', "-C", str(args.root),
                         "--skip-git-repo-check", "--output-last-message", last, "-"]
        assert not Path(last).exists()
    assert args.output.read_bytes().startswith(b"would not\n")
    logged = record(args)
    assert len(logged["attempts"]) == 1
    request = json.loads(seat.sidecar(args.output, ".request.json").read_bytes())
    assert request["work"] == "issue-592"
    assert request["stage"] == "cold-read"
    assert request["requested"]["required_capability"] == required_capability
    for boundary in (
        request["requested"]["permission_boundary"],
        logged["attempts"][0]["permission_boundary"],
    ):
        if vendor == "codex":
            assert "sandbox=read-only" in boundary
            assert "apps=disabled-by-config" in boundary
            assert "connector_surface=not_constrained_by_dispatch_seat" not in boundary
        else:
            assert "apps=disabled-by-config" not in boundary


@pytest.mark.parametrize(
    ("vendor", "required_capability", "expected"),
    [
        ("claude", "read", "Claude tools=Read,Glob,Grep; safe_mode=true; permission_mode=dontAsk; strict_mcp_config=true; os_sandbox=none"),
        ("claude", "execute", "Claude tools=Read,Glob,Grep,Bash; safe_mode=true; permission_mode=dontAsk; strict_mcp_config=true; os_sandbox=none"),
        ("codex", "read", "Codex sandbox=read-only; apps=disabled-by-config"),
    ],
)
def test_permission_boundary_states_the_selected_vendor_mode_and_root(job, vendor, required_capability, expected):
    args, _ = job
    assert seat.permission_boundary(vendor, required_capability, args.root.resolve()) == (
        f"{expected}; detached_root_verified={args.root.resolve()}"
    )


def test_execute_capability_refuses_codex_before_resolving_or_reserving(job, monkeypatch):
    args, _ = job
    args.vendor = "codex"
    args.own_vendor = "codex"
    args.requires = "execute"
    calls = []
    monkeypatch.setattr(seat, "resolve_command", lambda *values: calls.append(values))
    with pytest.raises(
        seat.DispatchError,
        match="codex cannot supply required capability execute; no process was launched",
    ):
        seat.run_dispatch(args)
    assert calls == []
    assert not list(args.output.parent.glob("verdict.md*"))


def test_execute_capability_skips_incapable_primary_and_tries_capable_fallback(job, monkeypatch):
    args, _ = job
    args.vendor = "codex"
    args.own_vendor = "claude"
    args.requires = "execute"
    calls = []
    resolver = seat.resolve_command

    def tracked(chosen, explicit):
        calls.append(chosen)
        return resolver(chosen, explicit)

    monkeypatch.setattr(seat, "resolve_command", tracked)
    assert seat.run_dispatch(args) == 0
    logged = record(args)
    codex, claude = logged["attempts"]
    assert calls == ["claude"]
    assert codex["launched"] is False
    assert codex["permission_boundary"] is None
    assert codex["reason"] == "codex cannot supply required capability execute; no process was launched"
    assert claude["launched"] is True
    assert logged["actual_vendor"] == "claude"


def test_execute_capability_fallback_records_its_unequipped_refusal(job, monkeypatch):
    args, _ = job
    args.requires = "execute"
    configure(job, {"claude": {"message": "Not logged in"}})
    calls = []
    resolver = seat.resolve_command

    def tracked(chosen, explicit):
        calls.append(chosen)
        return resolver(chosen, explicit)

    monkeypatch.setattr(seat, "resolve_command", tracked)
    assert seat.run_dispatch(args) == 1
    logged = record(args)
    claude, codex = logged["attempts"]
    assert calls == ["claude"]
    assert "Read,Glob,Grep,Bash" in seen(args, "claude")["argv"]
    assert claude["permission_boundary"] is not None
    assert claude["permission_boundary_unavailable_reason"] is None
    assert codex["permission_boundary"] is None
    assert codex["permission_boundary_unavailable_reason"] == codex["reason"]
    assert codex["reason"] == "codex cannot supply required capability execute; no process was launched"


def test_execute_capability_does_not_preflight_an_irrelevant_explicit_fallback(job, monkeypatch):
    args, _ = job
    args.requires = "execute"
    args.codex = str(args.output.with_name("missing-codex.exe"))
    configure(job, {"claude": {"message": "Not logged in"}})
    calls = []
    resolver = seat.resolve_command

    def tracked(chosen, explicit):
        calls.append((chosen, explicit))
        return resolver(chosen, explicit)

    monkeypatch.setattr(seat, "resolve_command", tracked)
    assert seat.run_dispatch(args) == 1
    assert calls == [("claude", None)]
    assert record(args)["attempts"][1]["reason"] == (
        "codex cannot supply required capability execute; no process was launched"
    )


def test_root_guard_changes_only_when_the_same_worktree_detaches(job, monkeypatch):
    args, _ = job
    calls = []
    resolver = seat.resolve_command

    def tracked(chosen, explicit):
        calls.append(chosen)
        return resolver(chosen, explicit)

    monkeypatch.setattr(seat, "resolve_command", tracked)
    git(args.root, "checkout", "-B", "attached")
    with pytest.raises(seat.DispatchError, match="Root must be the top level of a detached Git worktree"):
        seat.run_dispatch(args)
    assert calls == []
    git(args.root, "checkout", "--detach")
    assert seat.run_dispatch(args) == 0
    assert calls == ["claude"]


def test_root_guard_rejects_plain_directory_and_worktree_subdirectory(job, tmp_path, monkeypatch):
    args, _ = job
    calls = []
    monkeypatch.setattr(seat, "resolve_command", lambda *values: calls.append(values))
    plain = tmp_path / "plain"
    plain.mkdir()
    subdirectory = args.root / "subdirectory"
    subdirectory.mkdir()
    for root in (plain, subdirectory):
        args.root = root
        with pytest.raises(seat.DispatchError, match="Root must be the top level of a detached Git worktree"):
            seat.run_dispatch(args)
    assert calls == []


def test_linked_detached_worktree_is_accepted_by_the_root_guard(job):
    args, _ = job
    assert seat.detached_worktree_root(args.root.resolve()) is None


def test_root_guard_reasons_distinguish_attached_subdirectory_and_nonrepository(job, tmp_path):
    args, _ = job
    git(args.root, "checkout", "-B", "attached")
    assert "HEAD is attached" in seat.detached_worktree_root(args.root.resolve())
    git(args.root, "checkout", "--detach")
    subdirectory = args.root / "subdirectory"
    subdirectory.mkdir()
    assert "not the worktree top level" in seat.detached_worktree_root(subdirectory.resolve())
    plain = tmp_path / "plain"
    plain.mkdir()
    assert "not a Git worktree" in seat.detached_worktree_root(plain.resolve())


def test_root_guard_keeps_a_lawful_root_when_git_trace_writes_stderr(job, monkeypatch):
    args, _ = job
    monkeypatch.setenv("GIT_TRACE", "1")
    assert seat.detached_worktree_root(args.root.resolve()) is None


def test_root_guard_ignores_inherited_git_directory_variables(job, tmp_path, monkeypatch):
    args, _ = job
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.setenv("GIT_DIR", str(args.root / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(plain))
    monkeypatch.setenv("GIT_COMMON_DIR", str(args.root / ".git"))
    try:
        assert "not a Git worktree" in seat.detached_worktree_root(plain.resolve())
    finally:
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR"):
            monkeypatch.delenv(name, raising=False)


def test_root_guard_surfaces_a_git_probe_failure(job, monkeypatch):
    args, _ = job
    monkeypatch.setattr(
        seat.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 128, b"", b"fatal: fixture Git failure"),
    )
    assert "Git root probe failed: fatal: fixture Git failure" in seat.detached_worktree_root(
        args.root.resolve()
    )


@pytest.mark.parametrize("classification,expected", [
    ("ordinary", "xhigh"), ("cold", "max"), ("terminal", "max"),
])
def test_claude_effort_defaults_from_judgment_classification(job, classification, expected):
    args, _ = job
    args.classification = classification
    assert seat.run_dispatch(args) == 0
    flags = seen(args, "claude")["argv"]
    assert flags[flags.index("--effort") + 1] == expected
    assert record(args)["attempts"][0]["classification"] == classification


def test_explicit_claude_effort_overrides_classification(job):
    args, _ = job
    args.classification = "cold"
    args.claude_effort = "medium"
    assert seat.run_dispatch(args) == 0
    flags = seen(args, "claude")["argv"]
    assert flags[flags.index("--effort") + 1] == "medium"


@pytest.mark.parametrize("vendor", seat.VENDORS)
@pytest.mark.parametrize("kind", ["missing", "auth", "quota", "zero_exit", "hold"])
def test_unavailable_falls_back_once_and_records_reason(job, monkeypatch, vendor, kind):
    args, _ = job
    args.vendor = vendor
    args.own_vendor = "claude" if vendor == "codex" else "codex"
    reason = "Not logged in" if kind == "auth" else "You've hit your usage limit. Try again tomorrow."
    if kind == "missing":
        resolver = seat.resolve_command
        def missing(chosen, explicit):
            if chosen == vendor:
                raise CliNotFound(f"{vendor} not installed")
            return resolver(chosen, explicit)
        monkeypatch.setattr(seat, "resolve_command", missing)
    elif kind == "hold":
        args.hold_file.write_bytes(f"{vendor} 2026-09-13T00:00:00Z\n".encode())
    elif kind == "zero_exit":
        configure(job, {vendor: {"message": reason}})
    elif vendor == "codex":
        configure(job, {vendor: {"exit": 1, "message": "partial verdict must not escape",
                                "stdout": json.dumps({"type": "turn.failed", "error": {"message": reason}})}})
    else:
        configure(job, {vendor: {"exit": 1, "stdout": json.dumps({"type": "result", "subtype": "error_during_execution",
                          "is_error": True, "errors": [reason], "result": "partial verdict must not escape"})}})
    before = args.hold_file.read_bytes() if args.hold_file.exists() else None
    assert seat.run_dispatch(args, now=NOW) == 0
    verdict = args.output.read_text(encoding="utf-8")
    assert verdict.startswith(f"Fallback: {vendor} -> {args.own_vendor}; reason: ")
    assert "partial verdict" not in verdict
    log = record(args)
    assert [a["vendor"] for a in log["attempts"]] == [vendor, args.own_vendor]
    assert log["actual_vendor"] == args.own_vendor
    assert log["fallback_reason"]
    assert base64.b64decode(seen(args, args.own_vendor)["stdin"]) == args.dispatch.read_bytes()
    fallback = log["attempts"][1]
    expected_effort = (
        seat.CLAUDE_EFFORTS[args.classification]
        if args.own_vendor == "claude" else seat.DEFAULT_CODEX_EFFORT
    )
    assert (fallback["model"], fallback["effort"]) == (
        seat.DEFAULT_MODELS[args.own_vendor], expected_effort
    )
    assert (args.hold_file.read_bytes() if args.hold_file.exists() else None) == before


@pytest.mark.parametrize("vendor", seat.VENDORS)
@pytest.mark.parametrize("scenario", [
    {"exit": 2, "stderr": "invalid argument --bad"},
    {"stdout": "not JSON"},
    {"message": ""},
    {"sleep": 20},
])
def test_other_failures_never_fallback_or_publish(job, vendor, scenario):
    args, _ = job
    args.vendor = vendor
    args.own_vendor = "claude" if vendor == "codex" else "codex"
    configure(job, {vendor: scenario})
    if "sleep" in scenario:
        args.timeout_seconds = 0.1
    assert seat.run_dispatch(args) == 1
    assert not args.output.exists()
    assert len(record(args)["attempts"]) == 1
    assert not (args.root / f"seen-{args.own_vendor}.json").exists()


@pytest.mark.parametrize("vendor", seat.VENDORS)
def test_successful_quotes_are_not_outages(job, vendor):
    args, _ = job
    args.vendor = vendor
    message = 'would\nThe diagnostic "Not logged in" is handled; "rate limit exceeded" is quoted evidence.\n'
    configure(job, {vendor: {"message": message}})
    assert seat.run_dispatch(args) == 0
    assert args.output.read_text() == message
    assert len(record(args)["attempts"]) == 1


@pytest.mark.parametrize("same_vendor", [False, True])
def test_no_fallback_loop_when_both_vendors_held_or_same(job, same_vendor):
    args, _ = job
    if same_vendor:
        args.own_vendor = args.vendor
    args.hold_file.write_bytes(b"claude 2026-09-13T00:00:00Z\ncodex 2026-09-13T00:00:00Z\n")
    assert seat.run_dispatch(args, now=NOW) == 1
    assert not args.output.exists()
    assert len(record(args)["attempts"]) == (1 if same_vendor else 2)
    assert not list(args.root.glob("seen-*"))


def test_fallback_error_retains_both_attempts_without_verdict(job):
    args, _ = job
    configure(job, {"claude": {"message": "Not logged in"}, "codex": {"exit": 3}})
    assert seat.run_dispatch(args) == 1
    assert not args.output.exists()
    assert [a["outcome"] for a in record(args)["attempts"]] == ["unavailable", "error"]


@pytest.mark.parametrize("timestamp", ["2026-09-11T12:00:00Z", "2026-09-12T08:00:00-04:00"])
def test_expired_and_exact_reset_are_tried_without_editing_hold(job, timestamp):
    args, _ = job
    original = f"claude {timestamp}\n".encode()
    args.hold_file.write_bytes(original)
    assert seat.run_dispatch(args, now=NOW) == 0
    assert record(args)["actual_vendor"] == "claude"
    assert args.hold_file.read_bytes() == original


@pytest.mark.parametrize("content", ["claude tomorrow", "claude 2026-09-12T12:00:00", "unknown 2026-09-13T00:00:00Z",
                                     "# comment", "claude 2026-09-13T00:00:00Z\nclaude 2026-09-14T00:00:00Z"])
def test_invalid_hold_fails_before_a_launch(job, content):
    args, _ = job
    args.hold_file.write_bytes(content.encode())
    with pytest.raises(seat.DispatchError, match="one row per vendor"):
        seat.run_dispatch(args)
    assert not args.output.exists()
    assert not list(args.root.glob("seen-*"))


def test_default_hold_path_is_independent_of_working_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    first = seat.default_hold_file()
    (tmp_path / "other").mkdir()
    monkeypatch.chdir(tmp_path / "other")
    assert seat.default_hold_file() == first == tmp_path / ".tradecraft/vendor-holds"


@pytest.mark.parametrize("suffix", ["", ".run.json", ".codex.stdout.log", ".claude.stderr.log"])
def test_existing_output_is_preserved_without_spending_usage(job, suffix):
    args, _ = job
    target = seat.sidecar(args.output, suffix)
    target.write_bytes(b"old evidence")
    with pytest.raises(seat.DispatchError, match="Refusing existing output"):
        seat.run_dispatch(args)
    assert target.read_bytes() == b"old evidence"
    assert not list(args.root.glob("seen-*"))


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
def test_invalid_timeout_is_preflight_error(job, timeout):
    args, _ = job
    args.timeout_seconds = timeout
    with pytest.raises(seat.DispatchError, match="finite and positive"):
        seat.run_dispatch(args)
    assert not list(args.root.glob("seen-*"))


def test_permission_error_explains_host_route_without_fallback(job, monkeypatch):
    args, _ = job
    def denied(*a, **k):
        raise PermissionError("access denied")
    monkeypatch.setattr(seat, "run_process", denied)
    with pytest.raises(seat.DispatchError, match="approval-managed host execution"):
        seat.run_dispatch(args)
    assert len(record(args)["attempts"]) == 1
    assert not args.output.exists()


def test_claude_tool_denial_is_failure_even_with_final_prose(job):
    args, _ = job
    configure(job, {"claude": {"stdout": json.dumps({"type": "result", "subtype": "success", "is_error": False,
                  "result": "I could not read that", "permission_denials": [{"tool_name": "Read"}]})}})
    assert seat.run_dispatch(args) == 1
    assert not args.output.exists()
    assert len(record(args)["attempts"]) == 1


@pytest.mark.parametrize("code", ["rate_limit", "authentication_failed"])
def test_claude_error_category_causes_fallback(job, code):
    args, _ = job
    configure(job, {"claude": {"stdout": json.dumps({"type": "result", "subtype": "error_during_execution", "is_error": True,
                                                   "error": code, "result": "The seat did not finish"})}})
    assert seat.run_dispatch(args) == 0
    assert record(args)["actual_vendor"] == "codex"


def test_hold_added_during_primary_run_is_obeyed_before_fallback(job, monkeypatch):
    args, _ = job
    configure(job, {"claude": {"message": "Not logged in"}})
    original = seat.interpret
    def interpret(*values):
        args.hold_file.write_bytes(b"codex 2026-09-13T00:00:00Z\n")
        return original(*values)
    monkeypatch.setattr(seat, "interpret", interpret)
    assert seat.run_dispatch(args, now=NOW) == 1
    assert not (args.root / "seen-codex.json").exists()
    assert "owner hold" in record(args)["attempts"][1]["reason"]


def test_invalid_final_utf8_keeps_runtime_logs_and_no_verdict(job):
    args, _ = job
    args.vendor = "codex"
    configure(job, {"codex": {"last_hex": "ff", "stderr": "runtime diagnostic"}})
    with pytest.raises(UnicodeError):
        seat.run_dispatch(args)
    assert seat.sidecar(args.output, ".codex.stderr.log").read_bytes() == b"runtime diagnostic"
    assert not args.output.exists()


def test_empty_dispatch_is_a_preflight_error(job):
    args, _ = job
    args.dispatch.write_bytes(b"  \n")
    with pytest.raises(seat.DispatchError, match="empty"):
        seat.run_dispatch(args)
    assert not list(args.root.glob("seen-*"))


@pytest.mark.parametrize("suffix", ["", ".run.json", ".claude.stdout.log"])
def test_output_cannot_create_the_hold_file(job, suffix):
    args, _ = job
    args.hold_file = seat.sidecar(args.output, suffix)
    with pytest.raises(seat.DispatchError, match="also an input"):
        seat.run_dispatch(args)
    assert not args.hold_file.exists()
    assert not list(args.root.glob("seen-*"))


def test_relocated_library_has_no_repository_dependency(tmp_path):
    copied = tmp_path / "installed/lib"
    shutil.copytree(LIB, copied, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    help_run = subprocess.run([sys.executable, str(copied / "dispatch_seat.py"), "--help"], cwd=tmp_path,
                              stdin=subprocess.DEVNULL, capture_output=True)
    assert help_run.returncode == 0
    assert b"--own-vendor" in help_run.stdout
    assert b"--requires {read,execute}" in help_run.stdout
    suite = subprocess.run([sys.executable, "-m", "pytest", str(copied / "tests"), "-q", "-k", "not relocated"],
                           cwd=tmp_path, stdin=subprocess.DEVNULL, capture_output=True)
    assert suite.returncode == 0, suite.stdout.decode(errors="replace") + suite.stderr.decode(errors="replace")


@pytest.mark.parametrize("vendor", seat.VENDORS)
@pytest.mark.parametrize("message", [
    "API Error: 401 is a literal used by the implementation; no authentication failure occurred.",
    "Rate limit exceeded. This is the diagnostic covered by the patch; the implementation is correct.",
])
def test_explanatory_diagnostic_prefix_keeps_the_original_verdict(job, vendor, message):
    args, _ = job
    args.vendor = vendor
    args.own_vendor = "claude" if vendor == "codex" else "codex"
    configure(job, {vendor: {"message": message}})
    assert seat.run_dispatch(args) == 0
    assert args.output.read_text(encoding="utf-8") == message
    assert len(record(args)["attempts"]) == 1


def test_malformed_claude_bytes_are_rejected_and_recoverable(job, monkeypatch):
    args, _ = job
    raw = b'{"type":"result","subtype":"success","is_error":false,"result":"would \xff not"}'
    code = "import sys; sys.stdout.buffer.write(bytes.fromhex(" + repr(raw.hex()) + "))"
    monkeypatch.setattr(seat, "resolve_command", lambda *a: [sys.executable, "-c", code])
    with pytest.raises(UnicodeError):
        seat.run_dispatch(args)
    assert not args.output.exists()
    assert len(record(args)["attempts"]) == 1
    retained = json.loads(seat.sidecar(args.output, ".claude.stdout.log").read_bytes())
    assert retained["encoding"] == "base64"
    assert base64.b64decode(retained["data"]) == raw


@pytest.mark.parametrize("http_status", [401, 429])
def test_captured_codex_http_failures_fall_back_without_discarding_success(job, http_status):
    args, _ = job
    args.vendor, args.own_vendor = "codex", "claude"
    fixtures = json.loads((LIB / "tests/fixtures/codex-errors.json").read_bytes())
    captured = fixtures["cases"][str(http_status)]
    configure(job, {"codex": {"exit": 1, "stdout": captured, "message": "discard partial"}})
    assert seat.run_dispatch(args) == 0
    assert record(args)["actual_vendor"] == "claude"
    assert len(record(args)["attempts"]) == 2
    assert "discard partial" not in args.output.read_text(encoding="utf-8")
    # The same status words in a successful answer are not a failed event.
    args.output = args.output.with_name("quoted.md")
    message = json.loads(captured.splitlines()[-1])["error"]["message"] + " -- this is an example."
    configure(job, {"codex": {"message": message}})
    assert seat.run_dispatch(args) == 0
    assert args.output.read_text(encoding="utf-8") == message
    args.output = args.output.with_name("server-error.md")
    configure(job, {"codex": {"exit": 1, "stdout": fixtures["cases"]["500"]}})
    assert seat.run_dispatch(args) == 1
    assert len(record(args)["attempts"]) == 1
    assert not args.output.exists()


def test_uncreatable_sidecar_fails_before_child_runs(job):
    args, _ = job
    args.output = args.output.with_name("a" * 242)
    if os.name == "nt":
        args.output = Path("\\\\?\\" + str(args.output))
    with pytest.raises(OSError):
        seat.run_dispatch(args)
    assert not list(args.root.glob("seen-*"))
    assert not seat.sidecar(args.output, ".run.json").exists()
    args.output = args.output.with_name("a" * 237)
    assert seat.run_dispatch(args) == 0
    assert args.output.exists()


def test_fallback_cannot_read_discarded_transcript_but_caller_can(job, monkeypatch):
    args, _ = job
    primary = json.dumps({"type": "result", "subtype": "error_during_execution", "is_error": True,
                          "error": "rate_limit", "result": "DISCARDED_PARTIAL_VERDICT"})
    first = "import sys; sys.stdout.write(" + repr(primary) + ")"
    second = (
        "import sys\nfrom pathlib import Path\n"
        "found = any(b'DISCARDED_PARTIAL_VERDICT' in p.read_bytes() for p in Path.cwd().rglob('*.stdout.log'))\n"
        "Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_bytes(str(found).encode())\n"
        "print('{\"type\":\"turn.completed\"}')\n"
    )
    monkeypatch.setattr(seat, "resolve_command", lambda vendor, explicit: [
        sys.executable, "-c", first if vendor == "claude" else second])
    args.output = args.root / "in.md"
    with pytest.raises(seat.records.RecordError, match="outside the recipient root"):
        seat.run_dispatch(args)
    assert not list(args.root.glob("seen-*"))

    args.output = args.root.parent / "out.md"
    assert seat.run_dispatch(args) == 0
    assert args.output.read_text(encoding="utf-8").endswith("False")
    assert b"DISCARDED_PARTIAL_VERDICT" in seat.sidecar(args.output, ".claude.stdout.log").read_bytes()


def test_timeout_stops_a_started_descendant(job, monkeypatch):
    args, _ = job
    child = args.root / "child.py"
    child.write_bytes(b"import time\nfrom pathlib import Path\nPath('started').write_bytes(b'yes')\ntime.sleep(2)\nPath('finished').write_bytes(b'yes')\n")
    wrapper = "import subprocess,sys,time; subprocess.Popen([sys.executable,sys.argv[1]],stdin=sys.stdin,stdout=sys.stdout,stderr=sys.stderr); time.sleep(5)"
    monkeypatch.setattr(seat, "resolve_command", lambda *a: [sys.executable, "-c", wrapper, str(child)])
    args.timeout_seconds = 1
    started = time.monotonic()
    assert seat.run_dispatch(args) == 1
    elapsed = time.monotonic() - started
    assert (args.root / "started").exists(), "The descendant must actually start before cancellation."
    time.sleep(max(0, 2.3 - elapsed))
    assert not (args.root / "finished").exists(), "The descendant continued after the deadline."
    assert elapsed < 2, "Pipe-owning descendants delayed timeout cleanup."
    assert not args.output.exists()
    assert len(record(args)["attempts"]) == 1


@pytest.mark.parametrize("failure", ["write", "flush", "close"])
def test_record_failure_never_publishes_a_verdict(job, monkeypatch, failure):
    args, _ = job
    original = Path.open
    record_path = seat.sidecar(args.output, ".run.json")
    class FailingRecord:
        def __init__(self, stream):
            self.stream = stream
        def write(self, content):
            if failure == "write":
                self.stream.write(content[:5])
                raise OSError("record write failed")
            return self.stream.write(content)
        def flush(self):
            if failure == "flush":
                raise OSError("record flush failed")
            self.stream.flush()
        def close(self):
            self.stream.close()
            if failure == "close":
                raise OSError("record close failed")
    def opened(path, mode="r", *a, **kw):
        stream = original(path, mode, *a, **kw)
        return FailingRecord(stream) if path == record_path and mode == "xb" else stream
    if failure == "close":
        monkeypatch.setattr(Path, "open", opened)
    else:
        monkeypatch.setattr(
            seat.records, "finalize_reserved_json",
            lambda *_args: (_ for _ in ()).throw(OSError(f"record {failure} failed")),
        )
    with pytest.raises(OSError, match="record"):
        seat.run_dispatch(args)
    assert not args.output.exists()


def test_partial_verdict_write_is_not_published(job, monkeypatch):
    args, _ = job
    def partial(path, content):
        with path.open("xb") as stream:
            stream.write(content[:3])
        raise OSError("verdict write failed")
    monkeypatch.setattr(seat.records, "write_bytes", partial)
    with pytest.raises(OSError, match="verdict write failed"):
        seat.run_dispatch(args)
    assert not args.output.exists()
    assert not list(args.output.parent.glob(".tradecraft-publish-*"))
    assert record(args)["attempts"][0]["outcome"] == "success"


def test_verdict_publication_race_is_recorded_without_a_false_success(job, monkeypatch):
    args, _ = job
    link = os.link
    def raced(source, destination):
        if source == args.output:
            return link(source, destination)
        assert seat.sidecar(args.output, ".run.json").read_bytes() == b""
        assert Path(source).read_bytes()
        destination.write_bytes(b"another caller")
        link(source, destination)
    monkeypatch.setattr(seat.records.os, "link", raced)
    with pytest.raises(FileExistsError):
        seat.run_dispatch(args)
    assert args.output.read_bytes() == b"another caller"
    logged = record(args)
    assert logged["outcome"] == "error"
    assert logged["result"]["published_output"] is None
    source = Path(logged["result"]["source_output"])
    assert source.read_bytes().startswith(b"would not\n")
    assert not list(args.output.parent.glob(".tradecraft-publish-*"))


def test_unsupported_atomic_publication_fails_before_usage(job, monkeypatch):
    args, _ = job
    def unsupported(*args):
        raise OSError("hard links unavailable")
    monkeypatch.setattr(os, "link", unsupported)
    with pytest.raises(OSError, match="hard links unavailable"):
        seat.run_dispatch(args)
    assert not list(args.root.glob("seen-*"))
    assert not args.output.exists()
    assert not seat.sidecar(args.output, ".run.json").exists()
    assert not list(args.output.parent.glob(".tradecraft-publish-*"))


def test_classification_is_required_by_the_cli(job):
    args, _ = job
    argv = [
        "--dispatch", str(args.dispatch), "--root", str(args.root),
        "--vendor", "claude", "--own-vendor", "codex",
        "--work", "issue", "--stage", "cold-read",
        "--settings-source", "brief", "--settings-scope", "cold seat",
    ]
    with pytest.raises(SystemExit):
        seat.parser().parse_args(argv)


def test_capability_is_required_by_the_cli(job, capsys):
    args, _ = job
    argv = [
        "--dispatch", str(args.dispatch), "--root", str(args.root),
        "--vendor", "claude", "--own-vendor", "codex",
        "--work", "issue", "--stage", "cold-read", "--classification", "ordinary",
        "--settings-source", "brief", "--settings-scope", "cold seat",
    ]
    with pytest.raises(SystemExit):
        seat.parser().parse_args(argv)
    assert "--requires" in capsys.readouterr().err


def test_skipped_attempt_has_unknown_elapsed_with_reason(job):
    args, _ = job
    args.hold_file.write_bytes(b"claude 2026-09-13T00:00:00Z\ncodex 2026-09-13T00:00:00Z\n")
    assert seat.run_dispatch(args, now=NOW) == 1
    for attempt in record(args)["attempts"]:
        assert attempt["elapsed_seconds"] is None
        assert attempt["elapsed_seconds_unavailable_reason"] == attempt["reason"]


def test_interpretation_failure_still_completes_the_attempt(job, monkeypatch):
    args, _ = job
    monkeypatch.setattr(
        seat, "interpret", lambda *_: (_ for _ in ()).throw(UnicodeError("bad final text"))
    )
    with pytest.raises(UnicodeError, match="bad final text"):
        seat.run_dispatch(args)
    logged = record(args)
    attempt = logged["attempts"][0]
    assert logged["error"] == "bad final text"
    assert attempt["reason"] == "could not interpret claude return: bad final text"
    assert attempt["observed"]["raw"] is not None
    assert attempt["elapsed_seconds"] >= 0


def test_fallback_cannot_read_primary_transcript_until_it_finishes(job, monkeypatch):
    args, _ = job
    configure(job, {"claude": {"message": "Not logged in"}})
    original = seat.run_process
    calls = 0
    def checked(command, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            assert seat.sidecar(args.output, ".claude.stdout.log").read_bytes() == b""
            assert seat.sidecar(args.output, ".claude.stderr.log").read_bytes() == b""
        return original(command, **kwargs)
    monkeypatch.setattr(seat, "run_process", checked)
    assert seat.run_dispatch(args) == 0
    assert calls == 2
    assert seat.sidecar(args.output, ".claude.stdout.log").read_bytes()


def test_setting_sources_name_classification_and_default_model(job):
    args, _ = job
    assert seat.run_dispatch(args) == 0
    request = json.loads(seat.sidecar(args.output, ".request.json").read_bytes())
    sources = request["requested"]["sources"]
    assert sources["classification"] == "issuecomment-5655702442"
    assert sources["model"] == "dispatch_seat default"
    assert sources["effort"] == "classification mapping"
    assert sources["required_capability"] == "issuecomment-5655702442"


def test_unknown_capability_does_not_fall_through_to_read_mode(job):
    args, _ = job
    with pytest.raises(seat.DispatchError, match="unknown required capability"):
        seat.can_supply("claude", "network")
    with pytest.raises(seat.DispatchError, match="unknown required capability"):
        seat.build_command("claude", ["claude"], args.root, args.output, "opus", "xhigh", "network")
    with pytest.raises(seat.DispatchError, match="unknown required capability"):
        seat.permission_boundary("claude", "network", args.root)


def test_failed_dispatch_prints_its_id_and_bundle_path(job, capsys):
    args, _ = job
    configure(job, {"claude": {"exit": 2, "stderr": "bad option"}})
    assert seat.run_dispatch(args) == 1
    logged = record(args)
    assert logged["result"]["published_output"] is None
    output = capsys.readouterr().out
    assert logged["dispatch_id"] in output
    assert str(args.output) in output


def test_explicit_empty_model_is_rejected_without_a_bundle(job):
    args, _ = job
    args.claude_model = ""
    with pytest.raises(seat.DispatchError, match="claude model and effort must be nonempty"):
        seat.run_dispatch(args)
    assert not list(args.output.parent.glob("verdict.md*"))


def test_publication_failure_is_recorded_without_a_false_published_path(job, monkeypatch):
    args, _ = job
    monkeypatch.setattr(
        seat.records, "publish_output",
        lambda *_args: (_ for _ in ()).throw(OSError("hard link failed")),
    )
    with pytest.raises(OSError, match="hard link failed"):
        seat.run_dispatch(args)
    logged = record(args)
    assert logged["outcome"] == "error"
    assert logged["attempts"][0]["outcome"] == "success"
    assert logged["result"]["published_output"] is None
    assert "hard link failed" in logged["result"]["published_output_unavailable_reason"]
    assert not args.output.exists()
