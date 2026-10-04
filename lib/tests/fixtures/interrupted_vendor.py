"""A deterministic vendor with persistent knowledge and a blocked descendant."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

vendor, store = sys.argv[1], Path(sys.argv[2])


def announce(name, content):
    pending = store / (name + ".pending")
    pending.write_bytes(content)
    os.replace(pending, store / name)


if vendor == "blocked-command":
    announce("child-ready", str(os.getpid()).encode("ascii"))
    while not (store / "release").exists():
        time.sleep(0.05)
    raise SystemExit(0)
flags = sys.argv[3:]
sys.stdin.buffer.read()
session = "0199a213-81c0-7800-8aa1-bbab2a035a53"
resume = "--resume" in flags or "resume" in flags
if resume:
    option = "--resume" if "--resume" in flags else "resume"
    assert flags[flags.index(option) + 1] == session
    knowledge = json.loads((store / "knowledge.json").read_bytes())
else:
    knowledge = {"nonce": (store / "nonce").read_bytes().decode("ascii")}
    (store / "knowledge.json").write_bytes(json.dumps(knowledge).encode())
event = ({"type": "thread.started", "thread_id": session} if vendor == "codex"
         else {"type": "system", "subtype": "init", "session_id": session})
print(json.dumps(event), flush=True)
if not resume:
    child = subprocess.Popen([sys.executable, __file__, "blocked-command", str(store)],
                             stdin=subprocess.DEVNULL, stdout=sys.stdout, stderr=sys.stderr)
    while not (store / "child-ready").exists():
        time.sleep(0.05)
    native_child = int((store / "child-ready").read_bytes())
    announce("blocked.json", json.dumps(sorted({os.getpid(), child.pid, native_child})).encode())
    while not (store / "release").exists():
        time.sleep(0.05)
else:
    message = "Recovered knowledge: " + knowledge["nonce"]
    if vendor == "codex":
        Path(flags[flags.index("--output-last-message") + 1]).write_bytes(message.encode())
        print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 20, "output_tokens": 10}}))
    else:
        print(json.dumps({"type": "result", "session_id": session, "is_error": False,
                          "subtype": "success", "result": message,
                          "modelUsage": {"fixture": {"inputTokens": 20}}}))
