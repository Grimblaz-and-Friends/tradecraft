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


@pytest.fixture
def job(tmp_path, monkeypatch):
    root = tmp_path / "root with spaces"
    root.mkdir()
    dispatch = tmp_path / "dispatch.txt"
    dispatch.write_bytes(b"Read the supplied artifact and return your verdict.\n")
    scenario = tmp_path / "scenario.json"
    scenario.write_bytes(b"{}")
    args = seat.parser().parse_args([
        "--dispatch", str(dispatch), "--root", str(root), "--vendor", "claude",
        "--own-vendor", "codex", "--output", str(tmp_path / "verdict.md"),
        "--hold-file", str(tmp_path / "holds"), "--timeout-seconds", "10",
    ])
    def resolver(vendor, explicit):
        return [sys.executable, str(LIB / "tests/seat_cli.py"), vendor, str(scenario)]
    monkeypatch.setattr(seat, "resolve_command", resolver)
    return args, scenario


def configure(job, config):
    job[1].write_bytes(json.dumps(config).encode())


def record(args):
    return json.loads(seat.sidecar(args.output, ".run.json").read_bytes())


def seen(args, vendor):
    return json.loads((args.root / f"seen-{vendor}.json").read_bytes())


@pytest.mark.parametrize("vendor", seat.VENDORS)
def test_real_child_receives_large_utf8_dispatch_and_exact_launch(job, vendor):
    args, _ = job
    args.vendor = vendor
    args.own_vendor = "claude" if vendor == "codex" else "codex"
    prompt = (("quoted ' \" $() ` & | ; % ! " + chr(0x1F680) + "\n") * 2500).encode()
    args.dispatch.write_bytes(prompt)
    assert seat.run_dispatch(args) == 0
    observed = seen(args, vendor)
    assert base64.b64decode(observed["stdin"]) == prompt
    assert Path(observed["cwd"]) == args.root.resolve()
    flags = observed["argv"]
    if vendor == "claude":
        assert flags == ["-p", "--model", "opus", "--effort", "max", "--output-format", "json",
                         "--no-session-persistence", "--safe-mode", "--tools", "Read,Glob,Grep",
                         "--allowedTools", "Read,Glob,Grep", "--permission-mode", "dontAsk", "--strict-mcp-config"]
    else:
        last = flags[flags.index("--output-last-message") + 1]
        assert flags == ["exec", "--ephemeral", "--sandbox", "read-only", "--json", "--color", "never",
                         "--model", "gpt-6-astra", "-c", 'model_reasoning_effort="xhigh"', "-C", str(args.root),
                         "--skip-git-repo-check", "--output-last-message", last, "-"]
        assert not Path(last).exists()
    assert args.output.read_bytes().startswith(b"would not\n")
    assert len(record(args)["attempts"]) == 1


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
    assert (fallback["model"], fallback["effort"]) == seat.DEFAULTS[args.own_vendor]
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
    for inside in (True, False):
        # Separate roots prevent a completed earlier bundle becoming input.
        args.root = args.root.parent / ("inside" if inside else "outside")
        args.root.mkdir()
        args.output = (args.root if inside else args.root.parent) / ("in.md" if inside else "out.md")
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
    monkeypatch.setattr(Path, "open", opened)
    with pytest.raises(OSError, match="record"):
        seat.run_dispatch(args)
    assert not args.output.exists()


def test_partial_verdict_write_is_not_published(job, monkeypatch):
    args, _ = job
    def partial(path, content):
        with path.open("xb") as stream:
            stream.write(content[:3])
        raise OSError("verdict write failed")
    monkeypatch.setattr(seat, "write_bytes", partial)
    with pytest.raises(OSError, match="verdict write failed"):
        seat.run_dispatch(args)
    assert not args.output.exists()
    assert not list(args.output.parent.glob(".tradecraft-publish-*"))
    assert record(args)["attempts"][0]["outcome"] == "success"


def test_verdict_publication_follows_complete_record_and_refuses_a_race(job, monkeypatch):
    args, _ = job
    link = os.link
    def raced(source, destination):
        if source == args.output:
            return link(source, destination)
        assert record(args)["actual_vendor"] == "claude"
        assert Path(source).read_bytes()
        destination.write_bytes(b"another caller")
        link(source, destination)
    monkeypatch.setattr(seat.os, "link", raced)
    with pytest.raises(FileExistsError):
        seat.run_dispatch(args)
    assert args.output.read_bytes() == b"another caller"
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
