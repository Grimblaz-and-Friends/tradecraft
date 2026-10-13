"""One owned native Codex turn, with explicit RPC and turn attribution."""
from __future__ import annotations

import json
from pathlib import Path
import time

from seat_process import DuplexInput, run_process
import implementer_environment as environments
from implementer_policy import DISCOVERY_PROBE_SECONDS, FEATURES, PreparationError, restriction_config


def command(executable, pytest_overrides, *, artifact=False):
    argv = [*executable, "app-server", "--stdio"]
    for feature in FEATURES:
        argv.extend(("--disable", feature))
    argv.extend(("-c", "apps._default.enabled=false"))
    for override in pytest_overrides:
        argv.extend(("-c", override))
    if artifact:
        for override in ('sandbox_mode="workspace-write"', "sandbox_workspace_write.writable_roots=[]",
                         "sandbox_workspace_write.exclude_slash_tmp=true",
                         "sandbox_workspace_write.exclude_tmpdir_env_var=true"):
            argv.extend(("-c", override))
    return argv


def encode(value):
    return (json.dumps(value, ensure_ascii=True) + "\n").encode("utf-8")


def read_config(argv, cwd, deadline, *, env=None):
    """No model turn: discovery of effective project/system/user server keys."""
    source = DuplexInput()
    source.send(encode({"id": 1, "method": "initialize", "params": {
        "clientInfo": {"name": "tradecraft-builder-discovery", "version": "1"},
        "capabilities": {"experimentalApi": True}}}))
    pending, found, error = b"", None, None

    def output(name, chunk):
        nonlocal pending, found, error
        if name != "stdout":
            return
        pending += chunk
        while b"\n" in pending:
            line, pending = pending.split(b"\n", 1)
            try:
                event = json.loads(line)
            except ValueError:
                error = "invalid JSON during config discovery"
                source.close()
                continue
            if event.get("id") == 1:
                if "error" in event:
                    error = str(event["error"])
                    source.close()
                else:
                    source.send(encode({"method": "initialized", "params": {}}))
                    source.send(encode({"id": 2, "method": "config/read", "params": {
                        "cwd": str(cwd), "includeLayers": False}}))
            elif event.get("id") == 2:
                found = event.get("result", {}).get("config")
                error = str(event["error"]) if "error" in event else error
                source.close()
    result = run_process(argv, input=source, cwd=cwd, timeout=deadline.probe(DISCOVERY_PROBE_SECONDS), env=env,
                         on_output=output, cleanup_deadline=deadline.cleanup_end)
    if result.returncode or error or not isinstance(found, dict):
        raise PreparationError("Codex effective config discovery failed: " + str(error or result.stderr.decode("utf-8", "replace")[:500]))
    return found


class NativeTurn:
    def __init__(self, *, args, prompt, intent, environment, stdout_path, observe=None,
                 transcript=None, cwd=None):
        self.args, self.prompt, self.intent = args, prompt, intent
        self.cwd = Path(args.root if cwd is None else cwd).expanduser().resolve()
        self.environment, self.path = environment, stdout_path
        self.observe, self.transcript = observe, transcript
        self.input = DuplexInput()
        self.pending = b""
        self.line = 0
        self.session = self.turn = None
        self.log = None
        self.boundary = 0
        self.instruction_sources = None
        self.valid = True
        self.error = ""
        self.completed = False
        self.final_message = None
        self.token_usage = None
        self.events = []
        self.next_refresh = 0
        self.rpc = {}
        self.next_id = 1
        self.request("initialize", {"clientInfo": {"name": "tradecraft-builder", "version": "1"},
                                    "capabilities": {"experimentalApi": True}})

    def send(self, value):
        data = encode(value)
        if self.transcript:
            self.transcript.write(data)
            self.transcript.flush()
        self.input.send(data)

    def request(self, method, params):
        identity = self.next_id
        self.next_id += 1
        self.rpc[identity] = method
        self.send({"id": identity, "method": method, "params": params})

    def fail(self, reason):
        self.valid = False
        self.error = reason
        self.input.close()

    def output(self, name, chunk):
        if name != "stdout":
            return
        self.pending += chunk
        while b"\n" in self.pending:
            line, self.pending = self.pending.split(b"\n", 1)
            self.line += 1
            self.event(line)

    def event(self, raw):
        try:
            self._event(raw)
        except (AttributeError, KeyError, TypeError, UnicodeError, OSError) as exc:
            self.fail("invalid native protocol data: " + str(exc))

    def _event(self, raw):
        try:
            event = json.loads(raw)
            if not isinstance(event, dict):
                raise ValueError("non-object native event")
        except (UnicodeError, ValueError):
            self.fail("Codex returned invalid native JSONL")
            return
        self.events.append(event)
        method = event.get("method")
        if method and "id" in event:
            self.send({"id": event["id"], "error": {"code": -32601,
                "message": "tradecraft builder does not support person-required client requests"}})
            self.fail("unsupported native client request: " + method)
            return
        if "id" in event:
            requested = self.rpc.pop(event["id"], None)
            if requested is None:
                self.fail("unmatched native RPC response")
                return
            if "error" in event:
                self.fail(f"native {requested} failed: {event['error']}")
                return
            result = event.get("result")
            if not isinstance(result, dict):
                self.fail("native response lacks object result")
                return
            if requested == "initialize":
                self.send({"method": "initialized", "params": {}})
                params = {"cwd": str(self.cwd), "model": self.args.model,
                    "approvalPolicy": "on-request", "approvalsReviewer": "auto_review",
                    "sandbox": "workspace-write", "config": self.intent["thread_config"]}
                if self.args.resume:
                    params["threadId"] = self.args.resume
                self.request("thread/resume" if self.args.resume else "thread/start", params)
            elif requested in ("thread/start", "thread/resume"):
                thread = result.get("thread", {})
                session = thread.get("id")
                if not isinstance(session, str):
                    self.fail("native startup lacks session identity")
                    return
                self.session = session
                if self.observe:
                    self.observe(session, f"Codex native {requested} response.thread.id")
                if self.args.resume and session != self.args.resume:
                    self.fail("native resume returned a different session")
                    return
                self.environment["session_id"] = session
                reported_path = thread.get("path")
                self.log = environments.log_path(session,
                    reported_path if isinstance(reported_path, str) else None)
                if self.args.resume and self.log:
                    try:
                        self.boundary = self.log.stat().st_size
                    except OSError:
                        self.boundary = 0
                sources = result.get("instructionSources")
                self.instruction_sources = ([{"path": p} for p in sources if isinstance(p, str)]
                    if isinstance(sources, list) else None)
                self.environment["instruction_sources_coordinate"] = environments.coordinate(
                    self.path, self.line, "result.instructionSources")
                if self.instruction_sources:
                    self.environment["categories"]["instructions"] = environments.category(
                        "partial", self.instruction_sources,
                        "native startup instructionSources; log file inventory unavailable",
                        self.environment["instruction_sources_coordinate"])
                elif sources is not None and not isinstance(sources, list):
                    self.environment["categories"]["instructions"] = environments.category(
                        reason="native startup instructionSources has an unsupported format",
                        source=self.environment["instruction_sources_coordinate"])
                self.request("turn/start", {"threadId": session,
                    "input": [{"type": "text", "text": self.prompt.decode("utf-8"), "text_elements": []}],
                    "effort": self.args.effort, "disabledPluginIds": self.intent["disabled_plugin_ids"]})
            elif requested == "turn/start":
                turn = result.get("turn", {})
                identity = turn.get("id")
                if not isinstance(identity, str):
                    self.fail("native turn/start lacks turn identity")
                    return
                if self.turn and self.turn != identity:
                    self.fail("native current-turn identity mismatch")
                    return
                self.turn = identity
                self.environment["turn_id"] = identity
        elif method == "turn/started":
            params = event.get("params", {})
            if params.get("threadId") == self.session:
                identity = params.get("turn", {}).get("id")
                if isinstance(identity, str):
                    if self.turn and self.turn != identity:
                        self.fail("native current-turn identity mismatch")
                    else:
                        self.turn = identity
        elif method in ("item/completed", "thread/tokenUsage/updated", "turn/completed"):
            params = event.get("params", {})
            turn = params.get("turn", {}).get("id") if method == "turn/completed" else params.get("turnId")
            if params.get("threadId") != self.session or turn != self.turn or self.turn is None:
                return  # Historical or foreign notifications cannot own this invocation.
            if method == "item/completed":
                item = params.get("item", {})
                if item.get("type") == "agentMessage" and isinstance(item.get("text"), str):
                    self.final_message = item["text"]
            elif method == "thread/tokenUsage/updated":
                self.token_usage = params.get("tokenUsage")
            else:
                self.completed = params.get("turn", {}).get("status") == "completed"
                if not self.completed:
                    self.error = "native turn terminal status: " + str(params.get("turn", {}).get("status"))
                self.input.close()

    def refresh(self, *, force=False):
        now = time.monotonic()
        if not force and now < self.next_refresh:
            return
        self.next_refresh = now + 5
        if not self.session or not self.turn:
            return
        path = self.log or environments.log_path(self.session)
        if path:
            environments.codex_log(self.environment, path, session=self.session, turn=self.turn,
                cwd=self.cwd, boundary=self.boundary,
                allowed=[v["id"] for v in self.intent["allowed_plugins"]],
                instruction_sources=self.instruction_sources)
        else:
            for value in self.environment["categories"].values():
                if value["status"] == "unknown":
                    value["reason"] = "matching native session log unavailable or ambiguous"

    def finish(self):
        if self.pending.strip():
            self.line += 1
            self.event(self.pending)
            self.pending = b""
        self.refresh(force=True)

    def evidence(self, continuity):
        total = self.token_usage.get("total") if isinstance(self.token_usage, dict) else None
        total = total if isinstance(total, dict) else None
        names = {"inputTokens": "input_tokens", "cachedInputTokens": "cached_input_tokens",
                 "outputTokens": "output_tokens", "reasoningOutputTokens": "reasoning_output_tokens"}
        normalized = ({"scope": "invocation", **{target: total[key] for key, target in names.items()
            if isinstance(total.get(key), int) and not isinstance(total[key], bool) and total[key] >= 0}}
            if continuity == "fresh" and isinstance(total, dict) else None)
        return {"source": "Codex native thread/tokenUsage/updated.params.tokenUsage.total",
            "raw": self.token_usage, "normalized": normalized,
            "normalized_unavailable_reason": None if normalized else (
                "resume usage scope is not established without a proved invocation baseline" if continuity == "resume"
                else "runtime returned no cumulative token usage"),
            "additional_native_classes": {k: v for k, v in (total or {}).items() if k not in names},
            "reported_models": [], "reported_models_unavailable_reason": "current turn did not report a model identifier",
            "reported_effort": None, "reported_effort_unavailable_reason": "current turn did not report effort",
            "thread_ids": [self.session] if self.session else [], "turn_ids": [self.turn] if self.turn else [],
            "stream_valid": self.valid, "turn_completed": self.completed,
            "recovered_error_count": sum(e.get("method") == "error" for e in self.events),
            "turn_failed_count": int(not self.completed and bool(self.error)),
            "session_id": self.session, "session_id_source": "Codex native startup response.thread.id"}
