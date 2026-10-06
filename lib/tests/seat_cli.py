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
prompt = sys.stdin.buffer.read()
capture = {"argv": flags, "cwd": str(Path.cwd()), "stdin": base64.b64encode(prompt).decode()}
capture["pytest_addopts"] = os.environ.get("PYTEST_ADDOPTS")
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
    if message is not None:
        last = bytes.fromhex(scenario["last_hex"]) if "last_hex" in scenario else message.encode("utf-8")
        Path(flags[flags.index("--output-last-message") + 1]).write_bytes(last)
    stdout = scenario.get("stdout", json.dumps({"type": "turn.completed", "usage": {"input_tokens": 20, "output_tokens": 10}}))
else:
    stdout = scenario.get("stdout", json.dumps({"type": "result", "is_error": False, "subtype": "success", "result": message, "modelUsage": {"fixture": {"inputTokens": 20}}}))
sys.stdout.buffer.write(stdout.encode("utf-8"))
sys.stderr.buffer.write(scenario.get("stderr", "").encode("utf-8"))
sys.exit(scenario.get("exit", 0))
