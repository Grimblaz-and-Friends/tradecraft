"""Start the real launcher with deterministic vendor executable resolution."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import dispatch_implementer
import dispatch_seat

kind, vendor, store = sys.argv[1:4]
module = dispatch_implementer if kind == "implementer" else dispatch_seat
module.resolve_command = lambda *_a, **_k: [sys.executable, str(Path(__file__).with_name("interrupted_vendor.py")), vendor, store]
module.records.runtime_version = lambda *_a, **_k: "deterministic fixture 1.0"
dispatch_seat.windows_codex_sandbox = lambda: dispatch_seat.WindowsSandboxSelection("unelevated", "fixture", None)
arguments = sys.argv[4:]
if "--slow-final-probe" in arguments:
    arguments.remove("--slow-final-probe")
    original_process = module.records.run_process
    revision_calls = 0

    def slow_final_probe(command, **kwargs):
        global revision_calls
        if command[0] == "git":
            revision_calls += 1
            if revision_calls > 1:
                command = [sys.executable, "-c", "import time; time.sleep(90)"]
        return original_process(command, **kwargs)

    module.records.run_process = slow_final_probe
raise SystemExit(module.main(arguments))
