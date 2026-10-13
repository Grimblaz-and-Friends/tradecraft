"""A deterministic vendor with persistent knowledge and a blocked descendant."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import run_lifecycle as lifecycle

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
if flags[:3] == ["plugin", "list", "--json"]:
    print(json.dumps([] if vendor == "claude" else {"installed": []}))
    raise SystemExit(0)
session = "0199a213-81c0-7800-8aa1-bbab2a035a53"
turn = "0199a214-81c0-7800-8aa1-bbab2a035a53"
native = vendor == "codex" and flags[:1] == ["app-server"]
resume = "--resume" in flags or "resume" in flags
if native:
    def emit(value):
        print(json.dumps(value), flush=True)

    for line in sys.stdin.buffer:
        request = json.loads(line)
        method = request.get("method")
        if method == "initialize":
            emit({"id": request["id"], "result": {"userAgent": "interruption fixture"}})
        elif method == "config/read":
            emit({"id": request["id"], "result": {"config": {}}})
        elif method in ("thread/start", "thread/resume"):
            resume = method == "thread/resume"
            if resume:
                assert request["params"]["threadId"] == session
            emit({"id": request["id"], "result": {"thread": {"id": session}, "instructionSources": []}})
        elif method == "turn/start":
            emit({"id": request["id"], "result": {"turn": {"id": turn, "status": "inProgress"}}})
            break
    else:
        raise SystemExit(0)  # A discovery process owns no model turn or knowledge.
else:
    sys.stdin.buffer.read()
if resume:
    if not native:
        option = "--resume" if "--resume" in flags else "resume"
        assert flags[flags.index(option) + 1] == session
    knowledge = json.loads((store / "knowledge.json").read_bytes())
else:
    knowledge = {"nonce": (store / "nonce").read_bytes().decode("ascii")}
    (store / "knowledge.json").write_bytes(json.dumps(knowledge).encode())
event = ({"type": "thread.started", "thread_id": session} if vendor == "codex"
         else {"type": "system", "subtype": "init", "session_id": session})
if not native:
    print(json.dumps(event), flush=True)
if not resume:
    child = subprocess.Popen([sys.executable, __file__, "blocked-command", str(store)],
                             stdin=subprocess.DEVNULL, stdout=sys.stdout, stderr=sys.stderr)
    while not (store / "child-ready").exists():
        time.sleep(0.05)
    native_child = int((store / "child-ready").read_bytes())
    identities = [lifecycle.process_identity(pid) for pid in sorted({os.getpid(), child.pid, native_child})]
    announce("blocked-identities.json", json.dumps(identities).encode())
    announce("blocked.json", json.dumps(sorted({os.getpid(), child.pid, native_child})).encode())
    while not (store / "release").exists():
        time.sleep(0.05)
else:
    message = "Recovered knowledge: " + knowledge["nonce"]
    if native:
        emit({"method": "item/completed", "params": {"threadId": session, "turnId": turn,
            "item": {"type": "agentMessage", "text": message}}})
        emit({"method": "thread/tokenUsage/updated", "params": {"threadId": session, "turnId": turn,
            "tokenUsage": {"total": {"inputTokens": 20, "outputTokens": 10}}}})
        emit({"method": "turn/completed", "params": {"threadId": session,
            "turn": {"id": turn, "status": "completed"}}})
    elif vendor == "codex":
        Path(flags[flags.index("--output-last-message") + 1]).write_bytes(message.encode())
        print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 20, "output_tokens": 10}}))
    else:
        print(json.dumps({"type": "result", "session_id": session, "is_error": False,
                          "subtype": "success", "result": message,
                          "modelUsage": {"fixture": {"inputTokens": 20}}}))
