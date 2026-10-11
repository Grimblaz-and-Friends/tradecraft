#!/usr/bin/env python3
"""Opt-in native build checks; never run by ordinary CI or dispatch a stage."""
from __future__ import annotations

import argparse
from argparse import Namespace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
from winio import utf8_stdio
import dispatch_implementer as launcher
import implementer_environment as environment
import implementer_policy as policy
import codex_implementer as native
from seat_process import run_process
from vendor_cli import resolve_command
import run_lifecycle as lifecycle

PUBLIC = "4b2a04c9890e06b4d6d87204d79874133ee9cbf3"
REPOSITORY = "https://github.com/Grimblaz-and-Friends/tradecraft.git"
GLOBAL_TOKENS = ("Never use the AskUserQuestion tool", "Subagent dispatch is authorized")
NEGATIVE = "TC886_ABSENT_4baa3e20865c481e89a1c71b3e93fa81"


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return result.stdout.decode("utf-8").strip()


def setup(base):
    root = base / "consumer"
    root.mkdir(exist_ok=True)
    git(root, "init")
    return root


def launch(base, root, vendor, prompt, *, name, resume=None):
    dispatch = base / (name + ".prompt")
    dispatch.write_bytes(prompt.encode("utf-8"))
    output = base / (name + ".return")
    args = launcher.parser().parse_args(["--dispatch", str(dispatch), "--root", str(root),
        "--work", "Grimblaz-and-Friends/tradecraft#886", "--stage", "build",
        "--settings-source", "AC1-AC4 native build check", "--settings-scope", name,
        "--vendor", vendor, "--effort", "low", "--output", str(output), "--timeout-seconds", "600",
        *(["--resume", resume] if resume else [])])
    code = launcher.run_implementer(args)
    run = json.loads(launcher.records.sidecar(output, ".run.json").read_bytes())
    attempt = run["attempts"][0]
    result = {"check": name, "vendor": vendor, "exit": code, "outcome": run["outcome"],
        "session": attempt["observed"].get("session_id"), "reason": attempt.get("reason"),
        "bundle": str(launcher.records.sidecar(output, ".run.json")),
        "return": output.read_text(encoding="utf-8") if output.exists() else None,
        "coverage": {k: v["status"] for k, v in attempt["environment"]["categories"].items()},
        "excess": attempt["environment"]["excess"]}
    print(json.dumps(result, ensure_ascii=True), flush=True)
    return run, output


def operations(base, root):
    git(root, "remote", "add", "origin", REPOSITORY)
    git(root, "fetch", "--depth=1", "origin", PUBLIC)
    git(root, "checkout", "--detach", "FETCH_HEAD")
    expected = policy_env()
    for vendor in ("codex", "claude"):
        ref = "refs/heads/tc-886-build-check-" + vendor + "-" + uuid.uuid4().hex
        target = root / ("dependency-" + vendor + "-" + uuid.uuid4().hex)
        prompt = (
            "Perform only this authorized build-operation validation. No code edits, commits, "
            "agents, reviews, memory edits, issue/PR/comment writes or other refs. "
            f"From {root}, run an uncached real install: python -m pip install --no-cache-dir "
            f"--target \"{target}\" idna==3.10. Print the subprocess values of PYTEST_DEBUG_TEMPROOT "
            f"and PYTEST_ADDOPTS; the owner policy observed before launch was {json.dumps(expected)}. "
            "Do not change these settings. Then push this already-public commit to the unique test ref, "
            "verify its exact SHA, delete only that ref with the stated lease and verify absence. "
            f"Commands: git push --force-with-lease={ref}: origin {PUBLIC}:{ref}; "
            f"git ls-remote origin {ref}; git push --force-with-lease={ref}:{PUBLIC} origin :{ref}; "
            f"git ls-remote origin {ref}. A Windows keyring failure must use normal approval-managed "
            "host execution; keep credentials in the keyring. Stop on denial and report it. "
            "Return exact command results, environment values and whether cleanup was proved. "
            "No command separators are required; run each independently."
        )
        run, _ = launch(base, root, vendor, prompt, name="operations-" + vendor)
        remaining = git(root, "ls-remote", "origin", ref)
        print(json.dumps({"check": "ref-absence-" + vendor, "ref": ref, "remaining": remaining}), flush=True)
        if remaining:
            # Only this run's explicitly authorized ref, conditional on its
            # expected already-public head, can be cleaned up by the harness.
            git(root, "push", "--force-with-lease=" + ref + ":" + PUBLIC, "origin", ":" + ref)
            if git(root, "ls-remote", "origin", ref):
                raise RuntimeError("test ref cleanup not proved")
        if run["outcome"] != "success":
            raise RuntimeError(vendor + " operational check did not pass")


def policy_env():
    from codex_pytest import _user_shell_policy
    settings = _user_shell_policy().get("set", {})
    return {key: settings.get(key, os.environ.get(key)) for key in
            ("PYTEST_DEBUG_TEMPROOT", "PYTEST_ADDOPTS")}


def claude_context(base, root):
    global_path = Path.home() / ".claude/CLAUDE.md"
    content = global_path.read_text(encoding="utf-8")
    if not all(token in content for token in GLOBAL_TOKENS) or NEGATIVE in content:
        raise RuntimeError("existing-global-token setup is invalid; choose actual tokens before running")
    prompt = ("Use no tools or agents, inspect no files, and write no files/memory/GitHub state. "
        "For each phrase below, return whether it occurs in your standing instructions OUTSIDE "
        "this question. Reject a phrase that appears only in this question. Also name the native "
        "startup auto-memory directory. Phrases: " + json.dumps([*GLOBAL_TOKENS, NEGATIVE]))
    executable = resolve_command("claude", None)
    args = launcher.parser().parse_args(["--dispatch", str(base / "unused"), "--root", str(root),
        "--work", "Grimblaz-and-Friends/tradecraft#886", "--stage", "build",
        "--settings-source", "AC4 control", "--settings-scope", "context",
        "--vendor", "claude", "--model", "claude-opus-5-5", "--effort", "low"])
    control = launcher.build_command(args, executable, base / "unused")
    control.remove("--strict-mcp-config")
    control.remove("--no-chrome")
    captured = run_process(control, input=prompt.encode(), cwd=root, timeout=240)
    control_env = environment.unknown("missing")
    for line, raw in enumerate(captured.stdout.splitlines(), 1):
        try:
            value = json.loads(raw)
        except ValueError:
            continue
        environment.claude_init(control_env, value, path="control native stdout", line=line)
    terminal = launcher.claude_terminal(captured.stdout)
    print(json.dumps({"check": "claude-context-control", "exit": captured.returncode,
        "session": terminal.get("session_id"), "return": terminal.get("result"),
        "memory": control_env["categories"]["memory"]}, ensure_ascii=True), flush=True)
    run, _ = launch(base, root, "claude", prompt, name="claude-context-restricted")
    session = run["attempts"][0]["observed"]["session_id"]
    launch(base, root, "claude", prompt, name="claude-context-resume", resume=session)


def canary_server(base):
    script = base / "canary_server.py"
    script.write_bytes(b"""import json,sys
from pathlib import Path
marker=Path(sys.argv[1])
marker.write_bytes(b"started")
for line in sys.stdin.buffer:
    value=json.loads(line)
    if "id" not in value:
        continue
    method=value.get("method")
    if method=="initialize":
        result={"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"tc886-canary","version":"1"}}
    elif method=="tools/list":
        result={"tools":[{"name":"tc886_canary","description":"Harmless launch canary TC886_MCP_PRESENT","inputSchema":{"type":"object","properties":{}}}]}
    elif method=="tools/call":
        marker.write_bytes(b"called")
        result={"content":[{"type":"text","text":"TC886_MCP_PRESENT"}]}
    else:
        result={}
    print(json.dumps({"jsonrpc":"2.0","id":value["id"],"result":result}),flush=True)
""")
    return script


def native_arm(base, root, argv, intent, *, name, resume=None):
    args = Namespace(root=root, model="gpt-6.1-sol", effort="low", resume=resume)
    observed = environment.unknown("not observed", vendor="codex")
    prompt = b"List skills and any tc886 canary MCP tools supplied in standing context. Do not use tools, agents or write anything."
    exchange = native.NativeTurn(args=args, prompt=prompt, intent=intent,
        environment=observed, stdout_path=name + " native stdout")
    result = run_process(argv, input=exchange.input, cwd=root, timeout=300,
                         on_output=exchange.output, on_tick=exchange.refresh)
    exchange.finish()
    summary = {"check": name, "exit": result.returncode, "completed": exchange.completed,
        "valid": exchange.valid, "error": exchange.error, "session": exchange.session,
        "return": exchange.final_message, "excess": [v["identity"] for v in observed["excess"]],
        "stdout_bytes": len(result.stdout), "stdout_sha256": hashlib.sha256(result.stdout).hexdigest()}
    print(json.dumps(summary, ensure_ascii=True), flush=True)
    if not exchange.completed or not exchange.valid:
        raise RuntimeError(name + " native turn failed")
    return exchange


def canaries(base, root):
    script = canary_server(base)
    prompt = b"List the tc886 canary MCP tools and tc886-foreign-control:launch-canary skill in standing context. Use no tools, agents or writes."
    executable = resolve_command("claude", None)
    servers = {name: {"command": sys.executable, "args": [str(script), str(root / (name + ".marker"))]}
               for name in ("tc886_user", "tc886_project", "tc886_system", "tc886_desktop")}
    mcp = base / "mcp.json"
    mcp.write_bytes(json.dumps({"mcpServers": servers}).encode())
    fixture_config = base / "claude-native-canary"
    fixture_config.mkdir()
    (fixture_config / ".claude.json").write_bytes(json.dumps({"mcpServers": servers}).encode())
    child = dict(os.environ, CLAUDE_CONFIG_DIR=str(fixture_config))
    args = Namespace(vendor="claude", root=root, model="claude-opus-5-5", effort="low", resume=None, session_id=None)
    argv = launcher.build_command(args, executable, base / "unused")
    argv.remove("--strict-mcp-config")
    control = run_process(argv, input=prompt, cwd=root, timeout=240, env=child)
    control_init = next(json.loads(v) for v in control.stdout.splitlines()
                        if json.loads(v).get("subtype") == "init")
    print(json.dumps({"check": "claude-MCP-control", "exit": control.returncode,
        "servers": control_init.get("mcp_servers"), "markers": {k: (root / (k + ".marker")).exists() for k in servers}}), flush=True)
    if not all((root / (k + ".marker")).exists() for k in servers):
        raise RuntimeError("Claude MCP control did not expose every planted source")
    for name in servers:
        (root / (name + ".marker")).unlink()
    # The same native user MCP entries reach both arms. This fixture redirects
    # configuration only for the canary; global/memory preservation is checked
    # independently against the real owner context.
    deadline = lifecycle.stage_deadline("build", 600)
    with lifecycle.deadline_scope(deadline):
        intent, child = policy.claude_prepare(executable, root, deadline, base, ROOT, env=child)
    args.launch_settings_path = intent["settings_path"]
    restricted_argv = launcher.build_command(args, executable, base / "unused")
    restricted = run_process(restricted_argv, input=prompt, cwd=root, timeout=240, env=child)
    restricted_init = next(json.loads(v) for v in restricted.stdout.splitlines() if json.loads(v).get("subtype") == "init")
    print(json.dumps({"check": "claude-MCP-restricted", "exit": restricted.returncode,
        "servers": restricted_init.get("mcp_servers"),
        "markers": {k: (root / (k + ".marker")).exists() for k in servers}}), flush=True)
    if any((root / (k + ".marker")).exists() for k in servers):
        raise RuntimeError("Claude restricted launch started a canary")
    cache = base / "plugin-cache"
    foreign = cache / "foreign-plugin"
    (foreign / ".claude-plugin").mkdir(parents=True)
    (foreign / ".claude-plugin/plugin.json").write_bytes(b'{"name":"tc886-foreign-control","version":"0.0.0"}')
    (foreign / "skills/launch-canary").mkdir(parents=True)
    (foreign / "skills/launch-canary/SKILL.md").write_bytes(b"---\nname: launch-canary\ndescription: TC886_FOREIGN_PLUGIN_CANARY\n---\nHarmless catalog canary.\n")
    (cache / ".claude-plugin").mkdir()
    (cache / ".claude-plugin/marketplace.json").write_bytes(b'{"name":"tc886-fixture","owner":{"name":"build check"},"plugins":[{"name":"tc886-foreign-control","source":"./foreign-plugin"}]}')
    stamp = datetime.now(timezone.utc).isoformat()
    identity = "tc886-foreign-control@tc886-fixture"
    (cache / "installed_plugins.json").write_bytes(json.dumps({"version": 2, "plugins": {identity: [{
        "scope": "user", "installPath": str(foreign), "version": "0.0.0", "installedAt": stamp, "lastUpdated": stamp}]}}).encode())
    (cache / "known_marketplaces.json").write_bytes(json.dumps({"tc886-fixture": {
        "source": {"source": "directory", "path": str(cache)}, "installLocation": str(cache), "lastUpdated": stamp}}).encode())
    child = dict(os.environ, CLAUDE_CODE_PLUGIN_CACHE_DIR=str(cache))
    enable = base / "enable.json"
    enable.write_bytes(json.dumps({"enabledPlugins": {identity: True}}).encode())
    control = run_process([*argv, "--settings", str(enable)], input=prompt, cwd=root, timeout=240, env=child)
    init = next(json.loads(v) for v in control.stdout.splitlines() if json.loads(v).get("subtype") == "init")
    present = "tc886-foreign-control:launch-canary" in init.get("skills", [])
    print(json.dumps({"check": "claude-plugin-control", "present": present}), flush=True)
    if not present:
        raise RuntimeError("Claude installed-plugin control was invalid")
    original = os.environ.get("CLAUDE_CODE_PLUGIN_CACHE_DIR")
    try:
        os.environ["CLAUDE_CODE_PLUGIN_CACHE_DIR"] = str(cache)
        run, _ = launch(base, root, "claude", prompt.decode(), name="claude-plugin-restricted")
        session = run["attempts"][0]["observed"]["session_id"]
        late = cache / "late-plugin"
        (late / ".claude-plugin").mkdir(parents=True)
        (late / ".claude-plugin/plugin.json").write_bytes(b'{"name":"tc886-late-control","version":"0.0.0"}')
        (late / "skills/launch-canary").mkdir(parents=True)
        (late / "skills/launch-canary/SKILL.md").write_bytes(b"---\nname: launch-canary\ndescription: TC886_LATE_PLUGIN_CANARY\n---\nHarmless late catalog canary.\n")
        listing = json.loads((cache / "installed_plugins.json").read_bytes())
        late_id = "tc886-late-control@tc886-fixture"
        listing["plugins"][late_id] = [{"scope": "user", "installPath": str(late),
            "version": "0.0.0", "installedAt": stamp, "lastUpdated": stamp}]
        (cache / "installed_plugins.json").write_bytes(json.dumps(listing).encode())
        marketplace_path = cache / ".claude-plugin/marketplace.json"
        marketplace = json.loads(marketplace_path.read_bytes())
        marketplace["plugins"].append({"name": "tc886-late-control", "source": "./late-plugin"})
        marketplace_path.write_bytes(json.dumps(marketplace).encode())
        enable.write_bytes(json.dumps({"enabledPlugins": {identity: True, late_id: True}}).encode())
        late_control = run_process([*argv, "--settings", str(enable)], input=prompt, cwd=root, timeout=240, env=child)
        late_init = next(json.loads(v) for v in late_control.stdout.splitlines() if json.loads(v).get("subtype") == "init")
        if "tc886-late-control:launch-canary" not in late_init.get("skills", []):
            raise RuntimeError("newly installed foreign-plugin control was invalid")
        resumed, output = launch(base, root, "claude", prompt.decode(), name="claude-plugin-resume", resume=session)
        request = json.loads(launcher.records.sidecar(output, ".request.json").read_bytes())
        if late_id not in request["environment_request"]["disabled_plugin_ids"]:
            raise RuntimeError("resume did not rediscover the new installed plugin")
        if resumed["attempts"][0]["environment"]["excess"]:
            raise RuntimeError("restricted plugin fixture unexpectedly reached the consumer")
        print(json.dumps({"check": "new-plugin-before-resume", "identity": late_id, "control_present": True,
            "resume_rediscovered": True, "resume_excess": []}), flush=True)
    finally:
        if original is None:
            os.environ.pop("CLAUDE_CODE_PLUGIN_CACHE_DIR", None)
        else:
            os.environ["CLAUDE_CODE_PLUGIN_CACHE_DIR"] = original
    # CLI-origin fixtures leave the owner's config/auth/install files intact.
    # Native config/read must resolve them; thread restrictions use that report.
    executable = resolve_command("codex", None)
    argv = native.command(executable, launcher.implementer_pytest_overrides())
    def literal(value):
        return json.dumps(value, ensure_ascii=False)
    toml = "mcp_servers={" + ",".join(literal(k) + "={command=" + literal(v["command"]) +
        ",args=[" + ",".join(map(literal, v["args"])) + "]}" for k, v in servers.items()) + "}"
    argv.extend(("-c", toml))
    deadline = lifecycle.stage_deadline("build", 600)
    with lifecycle.deadline_scope(deadline):
        config = native.read_config(argv, root, deadline)
        intent = policy.codex_prepare(executable, root, deadline)
        # Control permits the fixture servers and all actual installed plugins.
        control_intent = {**intent, "disabled_plugin_ids": [], "thread_config": {}}
        native_arm(base, root, argv, control_intent, name="codex-control")
        if not all((root / (k + ".marker")).exists() for k in servers):
            raise RuntimeError("Codex MCP control did not expose every supplied server")
        for name in servers:
            (root / (name + ".marker")).unlink()
        intent["thread_config"] = policy.restriction_config(config, intent)
        restricted = native_arm(base, root, argv, intent, name="codex-restricted")
        native_arm(base, root, argv, intent, name="codex-restricted-resume", resume=restricted.session)
        if any((root / (k + ".marker")).exists() for k in servers):
            raise RuntimeError("Codex restricted fresh/resume started a canary")


def legacy_resume(base, root):
    executable = resolve_command("codex", None)
    argv = [*executable, "exec", "--approve-for-me", "--json", "--color", "never",
        "--model", "gpt-6.1-sol", "-c", 'model_reasoning_effort="low"', "--cd", str(root), "-"]
    seed = run_process(argv, input=b"Reply LEGACY-SEED. Use no tools, agents or writes.",
                       cwd=root, timeout=240)
    parsed = launcher.records.codex_stream_result(seed.stdout)
    session, source = launcher._thread_id(list(parsed.events), seed.stderr)
    if not parsed.completed or not session:
        raise RuntimeError("exec-created control session did not complete")
    print(json.dumps({"check": "legacy-exec-seed", "session": session, "source": source}), flush=True)
    run, _ = launch(base, root, "codex", "Reply NATIVE-RESUME. Use no tools, agents or writes.",
                    name="native-resume-exec", resume=session)
    if run["attempts"][0]["observed"]["session_id"] != session:
        raise RuntimeError("native resume did not retain the exec-created identity")


def main():
    utf8_stdio()
    parser = argparse.ArgumentParser(description="Run opt-in native launch acceptance checks without dispatching a pipeline stage.")
    parser.add_argument("check", choices=("operations", "claude-context", "inventory", "canaries", "legacy-resume"))
    parser.add_argument("--base", type=Path)
    args = parser.parse_args()
    base = args.base or Path(tempfile.mkdtemp(prefix="tc886-build-check-"))
    base.mkdir(exist_ok=True)
    root = setup(base)
    print(json.dumps({"check": args.check, "base": str(base), "revision": launcher.records.git_revision(ROOT)}), flush=True)
    if args.check == "operations":
        operations(base, root)
    elif args.check == "claude-context":
        claude_context(base, root)
    elif args.check == "canaries":
        canaries(base, root)
    elif args.check == "legacy-resume":
        legacy_resume(base, root)
    else:
        for vendor in ("codex", "claude"):
            launch(base, root, vendor, "Load tradecraft's charter from the supplied skill and return its purpose. "
                   "Use only the skill/file tools needed to read it; no agents, reviews or writes.",
                   name="inventory-" + vendor)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
