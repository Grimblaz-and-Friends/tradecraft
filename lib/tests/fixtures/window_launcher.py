"""Start the real implementer launcher with a Codex stand-in that returns at once.

Usage: window_launcher.py SCENARIO LAUNCHER-ARGUMENTS... (the entrance's own command, after the script).
Design: lib/DESIGN.md#a-runs-window-and-the-entrances-cap
"""
from pathlib import Path
import json
import sys

LIB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LIB))
import dispatch_implementer
import preflight

scenario = sys.argv[1]
dispatch_implementer.resolve_command = lambda *_a, **_k: [
    sys.executable, str(LIB / "tests" / "seat_cli.py"), "codex", scenario]
dispatch_implementer.records.runtime_version = lambda *_a, **_k: "codex-cli fixture"
# Preparation has its own tests; this stand-in exercises the launch and its records.
dispatch_implementer.policy.discover = lambda vendor, *_a, **_k: (
    json.loads(Path(scenario).read_bytes()).get(vendor, {}).get("plugin_list", []))
dispatch_implementer.native_codex.read_config = lambda *_a, **_k: {}
# The split counts from the process's creation, as the launcher run as a program does.
raise SystemExit(dispatch_implementer.main(sys.argv[2:], started=preflight.process_started()))
