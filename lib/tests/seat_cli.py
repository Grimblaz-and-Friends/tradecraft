"""A subprocess stand-in that records the real input and emits runtime fixtures."""
import base64
import json
import os
from pathlib import Path
import sys
import subprocess
import time

vendor, scenario_path = sys.argv[1:3]
flags = sys.argv[3:]
scenario = json.loads(Path(scenario_path).read_bytes()).get(vendor, {})
native = vendor == "codex" and flags[:1] == ["app-server"]
if flags[:3] == ["plugin", "list", "--json"]:
    time.sleep(scenario.get("discovery_sleep", 0))
    print(json.dumps(scenario.get("plugin_list", [] if vendor == "claude" else {"installed": []})))
    sys.exit(scenario.get("discovery_exit", 0))
requests = []
session = "0199a213-81c0-7800-8aa1-bbab2a035a53"
turn = "0199a214-81c0-7800-8aa1-bbab2a035a53"
if native:
    try:
        old_events = [json.loads(line) for line in scenario.get("stdout", "").splitlines() if line.strip()]
    except ValueError:
        old_events = []
    ids = [e["thread_id"] for e in old_events if e.get("type") == "thread.started"]
    if ids:
        session = ids[-1]
    else:
        import re
        header = re.search(r"session id:\s*([0-9a-f-]{36})", scenario.get("stderr", ""))
        if header:
            session = header[1]
    if "native_session" in scenario:
        session = scenario["native_session"]
    def emit(value):
        print(json.dumps(value), flush=True)
    for line in sys.stdin.buffer:
        request = json.loads(line)
        requests.append(request)
        method = request.get("method")
        if method and method == scenario.get("fail_method"):
            emit({"id": request["id"], "error": {"code": -32000, "message": "fixture " + method + " failure"}})
            sys.exit(1)
        if method == "initialize":
            emit({"id": request["id"], "result": {"userAgent": "fixture"}})
        elif method == "config/read":
            emit({"id": request["id"], "result": {"config": scenario.get("effective_config", {})}})
        elif method in ("thread/start", "thread/resume"):
            emit({"id": request["id"], "result": {"thread": {} if scenario.get("missing_identity") else {"id": session}, "instructionSources": []}})
        elif method == "turn/start":
            emit({"id": request["id"], "result": {"turn": {"id": turn, "status": "inProgress"}}})
            prompt = request["params"]["input"][0]["text"].encode("utf-8")
            break
    else:
        sys.exit(0)
else:
    prompt = sys.stdin.buffer.read()
capture = {"argv": flags, "cwd": str(Path.cwd()), "stdin": base64.b64encode(prompt).decode()}
capture["pytest_addopts"] = os.environ.get("PYTEST_ADDOPTS")
if native:
    capture["requests"] = requests
if scenario.get("author_writes"):
    def git(*args):
        result = subprocess.run(["git", *args], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return result.stdout.decode("utf-8").strip()
    capture["git_before"] = {"head": git("rev-parse", "HEAD"), "refs": git("show-ref"),
        "index": git("ls-files", "--stage"), "status": git("status", "--porcelain=v1"),
        "remotes": git("remote"), "git_dir": git("rev-parse", "--absolute-git-dir"),
        "common_dir": git("rev-parse", "--path-format=absolute", "--git-common-dir")}
    capture["draft_before"] = Path("draft.txt").read_bytes().hex() if Path("draft.txt").exists() else None
    capture["git_bindings"] = {key: value for key, value in os.environ.items() if key in {
        "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"}}
    if not scenario.get("resume_probe_only"):
        git("switch", "-c", "author-draft")
        Path("author-commit.txt").write_bytes(b"author commit\n")
        git("add", "author-commit.txt")
        git("-c", "user.name=author", "-c", "user.email=author@example.com", "commit", "-m", "author draft")
        Path("draft.txt").write_bytes(b"unfinished draft\n")
        git("add", "draft.txt")
        Path("loose-author.txt").write_bytes(b"loose author note\n")
    capture["git_after"] = {"head": git("rev-parse", "HEAD"), "refs": git("show-ref"),
        "index": git("ls-files", "--stage"), "status": git("status", "--porcelain=v1")}
if scenario.get("capture_path"):
    Path(scenario["capture_path"]).write_bytes(json.dumps(capture).encode())
Path(f"seen-{vendor}.json").write_bytes(json.dumps(capture).encode())
if scenario.get("sleep"):
    time.sleep(scenario["sleep"])
message = scenario.get("message", "would not\nA concrete problem in the submitted artifact.")
if vendor == "codex":
    if native:
        if "native_stdout" in scenario:
            sys.stdout.buffer.write(scenario["native_stdout"].encode("utf-8"))
        else:
            def notify(method, **params):
                emit({"method": method, "params": {"threadId": session, "turnId": turn, **params}})
            for event in old_events:
                if event.get("type") == "error":
                    notify("error", error=event)
            completed = [e for e in old_events if e.get("type") == "turn.completed"]
            failed = any(e.get("type") == "turn.failed" for e in old_events)
            finals = [e.get("item", {}).get("text") for e in old_events
                      if e.get("type") == "item.completed" and e.get("item", {}).get("type") == "agent_message"]
            final = message if message else finals[-1] if finals else None
            if "last_hex" in scenario:
                final = bytes.fromhex(scenario["last_hex"]).decode("utf-8")
            if final is not None:
                notify("item/completed", item={"type": "agentMessage", "text": final})
            if completed:
                usage = completed[-1].get("usage", {})
                mapping = {"input_tokens": "inputTokens", "cached_input_tokens": "cachedInputTokens",
                           "output_tokens": "outputTokens", "reasoning_output_tokens": "reasoningOutputTokens"}
                notify("thread/tokenUsage/updated", tokenUsage={"total": {
                    mapping.get(k, k): v for k, v in usage.items()}, "last": {"inputTokens": 1}})
                notify("turn/completed", turn={"id": turn, "status": "failed" if failed else "completed"})
            elif failed:
                notify("turn/completed", turn={"id": turn, "status": "failed"})
            elif scenario.get("stdout"):
                sys.stdout.buffer.write(scenario["stdout"].encode("utf-8"))
        sys.stdout.buffer.flush()
        sys.stderr.buffer.write(scenario.get("stderr", "").encode("utf-8"))
        sys.exit(scenario.get("exit", 0))
    if message is not None:
        last = bytes.fromhex(scenario["last_hex"]) if "last_hex" in scenario else message.encode("utf-8")
        Path(flags[flags.index("--output-last-message") + 1]).write_bytes(last)
    stdout = scenario.get("stdout", json.dumps({"type": "turn.completed", "usage": {"input_tokens": 20, "output_tokens": 10}}))
else:
    stdout = scenario.get("stdout", json.dumps({"type": "result", "is_error": False, "subtype": "success", "result": message, "modelUsage": {"fixture": {"inputTokens": 20}}}))
sys.stdout.buffer.write(stdout.encode("utf-8"))
sys.stderr.buffer.write(scenario.get("stderr", "").encode("utf-8"))
sys.exit(scenario.get("exit", 0))
