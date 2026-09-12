"""A subprocess stand-in that records the real input and emits runtime fixtures."""
import base64
import json
from pathlib import Path
import sys
import time

vendor, scenario_path = sys.argv[1:3]
flags = sys.argv[3:]
scenario = json.loads(Path(scenario_path).read_bytes()).get(vendor, {})
prompt = sys.stdin.buffer.read()
capture = {"argv": flags, "cwd": str(Path.cwd()), "stdin": base64.b64encode(prompt).decode()}
Path(f"seen-{vendor}.json").write_bytes(json.dumps(capture).encode())
if scenario.get("sleep"):
    time.sleep(scenario["sleep"])
message = scenario.get("message", "would not\nA concrete problem in the submitted artifact.")
if vendor == "codex":
    if message is not None:
        last = bytes.fromhex(scenario["last_hex"]) if "last_hex" in scenario else message.encode("utf-8")
        Path(flags[flags.index("--output-last-message") + 1]).write_bytes(last)
    stdout = scenario.get("stdout", json.dumps({"type": "turn.completed", "usage": {"input_tokens": 20, "output_tokens": 10}}))
else:
    stdout = scenario.get("stdout", json.dumps({"type": "result", "is_error": False, "subtype": "success", "result": message, "modelUsage": {"fixture": {"inputTokens": 20}}}))
sys.stdout.buffer.write(stdout.encode("utf-8"))
sys.stderr.buffer.write(scenario.get("stderr", "").encode("utf-8"))
sys.exit(scenario.get("exit", 0))
