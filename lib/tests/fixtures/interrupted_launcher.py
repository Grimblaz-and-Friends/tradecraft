"""Start the real launcher with deterministic vendor executable resolution."""
from pathlib import Path
import base64
import json
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import dispatch_implementer
import dispatch_seat
import run_lifecycle as lifecycle

kind, vendor, store = sys.argv[1:4]
module = dispatch_implementer if kind == "implementer" else dispatch_seat
module.resolve_command = lambda *_a, **_k: [sys.executable, str(Path(__file__).with_name("interrupted_vendor.py")), vendor, store]
module.records.runtime_version = lambda *_a, **_k: "deterministic fixture 1.0"
dispatch_seat.windows_codex_sandbox = lambda: dispatch_seat.WindowsSandboxSelection("unelevated", "fixture", None)
arguments = sys.argv[4:]
if kind == "seat":
    # Resolve the fixture's canonical comment locally while exercising the real
    # launcher's source grammar and frozen binding before the interrupted run.
    canonical = Path(arguments[arguments.index("--dispatch") + 1]).read_bytes().decode("utf-8")
    def fixture_get(endpoint):
        if endpoint.endswith("/.tradecraft/work.json"):
            config = {"schema_version": 1, "marker_producers": ["fixture"]}
            return {"encoding": "base64", "content": base64.b64encode(json.dumps(config).encode()).decode()}
        return {"id": 20, "body": canonical, "user": {"login": "fixture"},
                "issue_url": "https://api.github.com/repos/example/product/issues/12"}
    dispatch_seat.cold_draft._get = fixture_get
if "--snapshot-fixture" in arguments:
    index = arguments.index("--snapshot-fixture")
    snapshot = json.loads(Path(arguments[index + 1]).read_bytes())
    del arguments[index:index + 2]
    def unchanged_snapshot(*_args, **_kwargs):
        try:
            lifecycle.probe_timeout()
        except TimeoutError as exc:
            return {"head": None, "digest": None, "unavailable_reason": str(exc)}
        return dict(snapshot)
    lifecycle.content_snapshot = unchanged_snapshot
    module.records.run_process = lambda command, **_kwargs: module.subprocess.CompletedProcess(
        command, 0, snapshot["head"].encode(), b"")
fast_ceiling = "--fast-ceiling" in arguments
clock_offset = 0.0
if fast_ceiling:
    arguments.remove("--fast-ceiling")
    native_clock = time.monotonic
    started = float(arguments[arguments.index("--invocation-started-monotonic") + 1])
    limit = float(arguments[arguments.index("--timeout-seconds") + 1])
    reserve = min(60, max(lifecycle.MINIMUM_CLEANUP_RESERVE_SECONDS, limit / 10))
    run_path = Path(arguments[arguments.index("--output") + 1] + ".run.json")

    def ceiling_clock():
        global clock_offset
        current = native_clock()
        if not clock_offset and (Path(store) / "ceiling-ready").exists():
            try:
                saved = json.loads(run_path.read_bytes())
                if saved.get("session_identity", {}).get("session_id"):
                    # Advance only after the blocked command and durable identity
                    # exist. The real runner still stops and drains its tree.
                    clock_offset = max(0, started + limit - reserve + 0.01 - current)
            except (OSError, ValueError):
                pass
        return current + clock_offset

    lifecycle.time.monotonic = ceiling_clock
if "--slow-final-probe" in arguments:
    arguments.remove("--slow-final-probe")
    original_process = module.records.run_process
    from seat_process import run_process as native_process
    revision_calls = 0

    def slow_final_probe(command, **kwargs):
        global revision_calls
        if command[0] == "git":
            revision_calls += 1
            if revision_calls > 1:
                if fast_ceiling:
                    # The production-reserve seat case exercises a real slow
                    # probe. Other combinations prove the same allocation guard
                    # without spending that allowance on a sleeping subprocess.
                    deadline = lifecycle.current_deadline()
                    assert 0 < kwargs["timeout"] <= deadline.reserve / 2
                    global clock_offset
                    clock_offset += kwargs["timeout"] + 0.01
                    raise module.subprocess.TimeoutExpired(command, kwargs["timeout"])
                command = [sys.executable, "-c", "import time; time.sleep(90)"]
                return native_process(command, **kwargs)
        return original_process(command, **kwargs)

    module.records.run_process = slow_final_probe
raise SystemExit(module.main(arguments))
