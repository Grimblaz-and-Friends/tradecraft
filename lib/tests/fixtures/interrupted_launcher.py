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
raise SystemExit(module.main(sys.argv[4:]))
