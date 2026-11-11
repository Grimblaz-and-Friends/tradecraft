"""The write bound of a Claude launch that can write (#906).

A builder's or author's file-editing tools are confined to its tree and its
session scratchpad by a launch-owned PreToolUse hook (``tree_write_guard``).
Shell commands have no fence, so the Claude author and builder launches and the
Claude use consumer given a shell also compare what they must not touch before
and after the run. Other Claude seats given a shell are not compared.
A change the launcher cannot attribute to another live recorded run is a
finding the holder must account for; the entrance holds the change until then.
A Claude launch also compares each covered repository's working copies and
branches, and holds only on those its own record names.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import subprocess
import sys
import tempfile
import time

from holder_tree_guard import contains, path_key
import run_lifecycle as lifecycle
from seat_process import run_process
from tree_write_guard import (BUILTIN_SAFE_TYPES, WORKTREE_TOOLS, Refusal, agent_definitions,
                              logged_raw)

GUARD = Path(__file__).resolve().with_name("tree_write_guard.py")
FILE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
GUARD_MATCHER = "|".join(FILE_TOOLS + WORKTREE_TOOLS)
MEMORY_SWITCH = "CLAUDE_CODE_DISABLE_AUTO_MEMORY"
SLUG_LIMIT = 200
SCHEMA_VERSION = 1
NOT_RECORDED = "not recorded: launched before #906"
SHELL = "no OS fence"
IMPLEMENTER_BOUNDARY = (
    "Claude auto permission mode; user settings only; file tools confined to the tree and session "
    "scratchpad by a launch path check; covered items compared before and after; shell commands "
    "have no OS fence"
)


class BoundError(OSError):
    """The write bound could not be prepared; nothing launches unguarded."""


# --- D3: the scratchpad the runtime gives this session -----------------------

def _temp_base(env: dict[str, str]) -> str:
    supplied = env.get("CLAUDE_CODE_TMPDIR")
    if supplied:
        return supplied
    names = ("TEMP", "TMP") if os.name == "nt" else ("TMPDIR",)
    for name in names:
        if env.get(name):
            return env[name]
    return tempfile.gettempdir()


def scratchpad(root: Path, session: str, env: dict[str, str]) -> dict[str, str]:
    """The runtime's scratchpad: <temp>/claude/<slug of root>/<session>/scratchpad.

    A slug over the runtime's limit carries a hash suffix this launcher does not
    reproduce; it is matched by a narrow pattern, and a wrong derivation refuses
    the real scratchpad (a visible failure), never widens the bound.
    """
    parent = Path(os.path.realpath(Path(_temp_base(env)) / "claude"))
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(root))
    if len(slug) <= SLUG_LIMIT:
        path = parent / slug / session / "scratchpad"
        return {"scratchpad_form": "exact", "scratchpad": str(path),
                "scratchpad_parent": str(parent)}
    prefix = slug[:SLUG_LIMIT] + "-"
    return {"scratchpad_form": "long-prefix", "scratchpad": None,
            "scratchpad_parent": str(parent), "scratchpad_slug_prefix": prefix,
            "scratchpad_pattern": str(parent / (prefix + "<[0-9a-z]+>") / session / "scratchpad")}


def allowed_scratchpad(config: dict) -> str:
    return config.get("scratchpad") or config["scratchpad_pattern"]


# --- D1: the guard's config, settings, self-test and outcome -----------------

def _quoted(path: Path | str) -> str:
    return '"' + str(path).replace("\\", "/") + '"'


def hook_settings(config_path: Path) -> dict[str, object]:
    """The settings ``hooks`` key; one string works under Git Bash and cmd."""
    command = f"{_quoted(sys.executable)} {_quoted(GUARD)} --config {_quoted(config_path)}"
    return {"PreToolUse": [{"matcher": GUARD_MATCHER,
                            "hooks": [{"type": "command", "command": command}]}]}


def agent_dirs(root: Path, env: dict[str, str], launcher_plugin: Path | None,
               builtin_plugins: list[tuple[str, str]] = ()) -> list[dict[str, str | None]]:
    """Where a launched session's agent definitions can come from.

    The launch disables every other plugin, so these are the user's agents, the
    tree's, the launcher plugin's and each built-in plugin's.
    Design: lib/DESIGN.md#the-launchs-working-copies-and-branches
    """
    home = env.get("USERPROFILE") if os.name == "nt" else env.get("HOME")
    config = Path(env.get("CLAUDE_CONFIG_DIR") or Path(home or os.path.expanduser("~")) / ".claude")
    dirs: list[dict[str, str | None]] = [
        {"path": str(config / "agents"), "namespace": None},
        {"path": str(Path(root).resolve(strict=False) / ".claude" / "agents"), "namespace": None}]
    if launcher_plugin is not None:
        dirs.append({"path": str(Path(launcher_plugin) / "agents"), "namespace": "tradecraft"})
    for name, path in builtin_plugins:
        dirs.append({"path": str(Path(path) / "agents"), "namespace": name})
    return dirs


def guard_config(root: Path, session: str, env: dict[str, str], log: Path,
                 agents: list[dict] | None = None) -> dict[str, object]:
    home = env.get("USERPROFILE") if os.name == "nt" else env.get("HOME")
    return {"schema_version": SCHEMA_VERSION, "root": str(Path(root).resolve(strict=False)),
            "session": session, "home": home or os.path.expanduser("~"), "log": str(log),
            "agent_dirs": agents if agents is not None else agent_dirs(root, env, None),
            **scratchpad(Path(root).resolve(strict=False), session, env)}


def _write_json(path: Path, value: object) -> None:
    path.write_bytes((json.dumps(value, ensure_ascii=True, indent=2) + "\n").encode("utf-8"))


def _self_test_targets(config: dict, outside: Path) -> list[tuple[str, str, str]]:
    root = Path(config["root"])
    if config["scratchpad_form"] == "exact":
        inside_pad = Path(config["scratchpad"]) / "tradecraft-self-test.txt"
    else:
        inside_pad = (Path(config["scratchpad_parent"]) / (config["scratchpad_slug_prefix"] + "0")
                      / config["session"] / "scratchpad" / "tradecraft-self-test.txt")
    return [("outside", str(outside), "deny"),
            ("owner settings", "~/.claude/settings.json", "deny"),
            ("tree", str(root / "tradecraft-self-test.txt"), "allow"),
            ("scratchpad", str(inside_pad), "allow")]


SELF_TEST_ISOLATING = "tradecraft-self-test-isolating"


def _self_test_helper_cases() -> list[tuple[str, str, dict, str]]:
    """Helper calls the guard must decide before launch."""
    return [("isolated helper", "Agent", {"prompt": "x", "isolation": "worktree"}, "deny"),
            ("plain helper", "Agent", {"prompt": "x", "subagent_type": "general-purpose"}, "allow"),
            ("isolating definition", "Agent", {"prompt": "x", "subagent_type": SELF_TEST_ISOLATING},
             "deny"),
            ("unknown type", "Agent", {"prompt": "x", "subagent_type": "tradecraft-self-test-unknown"},
             "deny"),
            ("enter worktree", "EnterWorktree", {"name": "tradecraft-self-test"}, "deny")]


def prepare_guard(temporary: Path, root: Path, session: str, env: dict[str, str], deadline,
                  agents: list[dict] | None = None) -> dict[str, object]:
    """Write the guard config, prove it with its own self-test, then create its log.

    The self-test has its own config and log in a separate directory, so its
    denials never reach the launch's decision log.
    """
    temporary = Path(temporary)
    for path in (sys.executable, GUARD, temporary / "write-guard.json"):
        # The hook command quotes each path; a quote inside one would break it,
        # and the argument-list self-test would not notice.
        if '"' in str(path):
            raise BoundError(f"write guard path contains a double quote: {path}")
    config_path = temporary / "write-guard.json"
    log = temporary / "write-guard.log.jsonl"
    config = guard_config(root, session, env, log, agents)
    try:
        # Every definition is read now, so one the guard can't read fails the
        # launch here rather than refusing every helper call mid-turn.
        agent_definitions(config, "")
    except Refusal as exc:
        raise BoundError(f"an agent definition can't be read with certainty: {exc}") from exc
    test_dir = temporary / "write-guard-self-test"
    test_dir.mkdir()
    test_config_path = test_dir / "write-guard.json"
    fixture = test_dir / "agents"
    fixture.mkdir()
    (fixture / "isolating.md").write_bytes(
        f"---\nname: {SELF_TEST_ISOLATING}\nisolation: worktree\n---\nself-test\n".encode("utf-8"))
    test_config = guard_config(root, session, env, test_dir / "write-guard.log.jsonl",
                               [{"path": str(fixture), "namespace": None}])
    _write_json(test_config_path, test_config)
    results = []
    cases = [(label, "Write", {"file_path": raw, "content": ""}, expected)
             for label, raw, expected in _self_test_targets(test_config, test_dir / "outside.txt")]
    for label, tool, tool_input, expected in cases + _self_test_helper_cases():
        raw = tool_input.get("file_path") or json.dumps(tool_input, sort_keys=True)
        payload = {"tool_name": tool, "tool_use_id": f"self-test-{label}",
                   "tool_input": tool_input, "cwd": str(root)}
        try:
            result = run_process([sys.executable, str(GUARD), "--config", str(test_config_path)],
                                 input=json.dumps(payload).encode("utf-8"), cwd=Path(root),
                                 timeout=deadline.probe() if deadline else 20, env=env,
                                 cleanup_deadline=deadline.cleanup_end if deadline else None)
        except (OSError, subprocess.TimeoutExpired, TimeoutError) as exc:
            raise BoundError(f"write guard self-test could not run: {exc}") from exc
        observed = "deny" if b'"permissionDecision":"deny"' in result.stdout else "allow"
        if result.returncode != 0:
            observed = f"exit {result.returncode}"
        results.append({"case": label, "expected": expected, "observed": observed})
        if observed != expected:
            raise BoundError(f"write guard self-test failed: {label} target {raw} gave {observed}, "
                             f"expected {expected}; " + result.stderr.decode("utf-8", "replace")[:500])
    _write_json(config_path, config)
    log.write_bytes(b"")
    return {"config": config, "config_path": str(config_path), "log": str(log),
            "hooks": hook_settings(config_path), "self_test": results}


def file_tools_record(prepared: dict, settings_sha256: str) -> dict[str, object]:
    config = prepared["config"]
    return {"tools": list(FILE_TOOLS), "allowed": [config["root"], allowed_scratchpad(config)],
            "scratchpad_form": config["scratchpad_form"], "guard": str(GUARD),
            "guard_self_test": "passed", "settings_sha256": settings_sha256,
            "worktree_tools": list(WORKTREE_TOOLS), "agent_dirs": config.get("agent_dirs") or [],
            "builtin_safe_types": dict(BUILTIN_SAFE_TYPES)}


def memory_record() -> dict[str, str]:
    return {"requested": f"disabled by child process environment {MEMORY_SWITCH}=1",
            "fallback": "file-tool writes to the memory store are outside the allowed set"}


def _stream_events(raw: bytes) -> list[dict]:
    events = []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except (UnicodeError, ValueError):
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _blocks(event: dict) -> list[dict]:
    message = event.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []


def guard_outcome(stdout: bytes, log: Path | str) -> tuple[dict[str, object], str]:
    """Cross-check the stream's guarded calls against the guard's decisions.

    A deny fails the turn. A call that completed, or has no result at all, and
    has no decision fails it as unproved: the hook may never have started. A
    call the runtime rejected before it ran wrote nothing and is only listed.
    """
    decisions = []
    try:
        for line in Path(log).read_bytes().splitlines():
            try:
                entry = json.loads(line)
            except (UnicodeError, ValueError):
                continue
            if isinstance(entry, dict):
                decisions.append(entry)
    except OSError:
        decisions = []
    calls, results = [], {}
    for event in _stream_events(stdout):
        for block in _blocks(event):
            if block.get("type") == "tool_use" and (block.get("name") in FILE_TOOLS
                                                    or block.get("name") in WORKTREE_TOOLS):
                tool_input = block.get("input") if isinstance(block.get("input"), dict) else {}
                calls.append({"tool": block["name"], "raw": logged_raw(block["name"], tool_input),
                              "tool_use_id": block.get("id")})
            elif block.get("type") == "tool_result" and block.get("tool_use_id"):
                results[block["tool_use_id"]] = block.get("is_error") is True
    refusals = [{"tool": d.get("tool"), "raw": d.get("raw"), "canonical": d.get("canonical"),
                 "reason": d.get("reason")} for d in decisions if d.get("decision") == "deny"]
    unmatched = list(decisions)
    unguarded, rejected = [], []

    def take(call):
        for index, entry in enumerate(unmatched):
            if call["tool_use_id"] and entry.get("tool_use_id") == call["tool_use_id"]:
                return unmatched.pop(index)
        for index, entry in enumerate(unmatched):
            if not entry.get("tool_use_id") and (entry.get("tool"), entry.get("raw")) == (
                    call["tool"], call["raw"]):
                return unmatched.pop(index)
        return None

    for call in calls:
        decided = take(call)
        state = results.get(call["tool_use_id"])
        if decided is not None:
            continue
        if state is True:
            rejected.append(call)
        else:
            unguarded.append({**call, "result": "none" if state is None else "completed"})
    reasons = [f"launch bound refused {r['tool']} {r['canonical'] or r['raw']}" for r in refusals]
    reasons += [f"write bound unproved: {u['tool']} {u['raw']} completed with no guard decision"
                for u in unguarded]
    record = {"decisions": len(decisions), "refusals": refusals, "unguarded": unguarded,
              "rejected_before_run": rejected}
    return record, "; ".join(reasons)


# --- D6: coverage, snapshots, diff and attribution ---------------------------

def registry_path(home: Path) -> Path:
    return home / ".tradecraft" / "implementation-worktrees.json"


def _registry_rows(path: Path) -> list[dict] | None:
    try:
        value = json.loads(path.read_bytes())
    except FileNotFoundError:
        return []
    except (OSError, UnicodeError, ValueError):
        return None
    if (not isinstance(value, dict) or value.get("schema_version") != 1
            or not isinstance(value.get("worktrees"), list)
            or not all(isinstance(row, dict) for row in value["worktrees"])):
        return None
    return value["worktrees"]


def _git_lines(root: Path, *arguments: str) -> list[str]:
    try:
        result = run_process(["git", "-C", str(root), *arguments], input=b"", cwd=Path(root),
                             timeout=lifecycle.probe_timeout(), on_tick=lambda: None,
                             cleanup_deadline=lifecycle.cleanup_deadline())
    except (OSError, subprocess.TimeoutExpired, TimeoutError):
        return []
    if result.returncode:
        return []
    return result.stdout.decode("utf-8", "replace").splitlines()


def main_clone(root: Path) -> Path | None:
    for line in _git_lines(root, "worktree", "list", "--porcelain"):
        if line.startswith("worktree "):
            return Path(line[len("worktree "):])
    return None


def coverage_plan(*, root: Path, home: Path, env: dict[str, str], launcher_plugin: Path,
                  store: Path, own_request: Path, refs: bool = False) -> list[dict[str, str]]:
    """What this launch must not touch, fixed before it starts."""
    config = Path(env.get("CLAUDE_CONFIG_DIR") or home / ".claude")
    cache = Path(env.get("CLAUDE_CODE_PLUGIN_CACHE_DIR") or config / "plugins")
    tradecraft = home / ".tradecraft"
    plan = [
        {"item": "switch", "path": str(tradecraft / "implementer-vendor"), "method": "sha256"},
        # The cloud route's machine switch; a local build that edits it is caught.
        {"item": "cloud-switch", "path": str(tradecraft / "cloud-builds.json"), "method": "sha256"},
        # The keep-warm machine setting; a build that edits it is caught.
        {"item": "keep-warm-switch", "path": str(tradecraft / "keep-warm.json"), "method": "sha256"},
        {"item": "rulings", "path": str(tradecraft / "model-rulings.json"), "method": "sha256"},
        {"item": "claude-settings", "path": str(config / "settings.json"), "method": "sha256"},
        {"item": "claude-md", "path": str(config / "CLAUDE.md"), "method": "sha256"},
        {"item": "plugins", "path": str(cache), "method": "tree"},
        {"item": "registry", "path": str(registry_path(home)), "method": "registry"},
        {"item": "dispatch-records", "path": str(store), "method": "records"},
        {"item": "own-request", "path": str(own_request), "method": "sha256"},
    ]
    own = path_key(Path(root).resolve(strict=False))
    checkouts: dict[str, Path] = {}
    rows = _registry_rows(registry_path(home)) or []
    registered = []
    for row in rows:
        if row.get("active") is not True:
            continue
        for key in ("root", "holder_root"):
            if isinstance(row.get(key), str) and row[key]:
                registered.append(Path(row[key]).resolve(strict=False))
    for path in list(registered):
        clone = main_clone(path) if path.is_dir() else None
        if clone is not None:
            registered.append(clone.resolve(strict=False))
    for path in registered:
        if path_key(path) != own:
            checkouts.setdefault(path_key(path), path)
    plugin = Path(launcher_plugin).resolve(strict=False)
    if path_key(plugin) not in checkouts and path_key(plugin) != own:
        plan.append({"item": "launcher-plugin", "path": str(plugin), "method": "checkout"})
    for _key, path in sorted(checkouts.items()):
        plan.append({"item": "checkout:" + str(path), "path": str(path), "method": "checkout"})
    if refs:
        plan.extend(refs_plan(Path(root), [Path(item["path"]) for item in plan
                                           if item["method"] == "checkout"]))
    return plan


class _Expired(Exception):
    pass


def _check(end: float) -> None:
    if time.monotonic() > end:
        raise _Expired("comparison walk ran out of time")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _walk(top: Path, end: float, *, checkout: bool) -> dict[str, object]:
    """Key every entry by relative path; links are recorded, never followed."""
    entries: dict[str, object] = {}
    pending = [(top, "")]
    while pending:
        directory, prefix = pending.pop()
        with os.scandir(directory) as listing:
            children = list(listing)
        for child in children:
            _check(end)
            relative = prefix + child.name
            if child.name == ".git" and (not checkout or not prefix):
                continue  # The top's .git (or, in a plugin tree, every .git).
            if child.is_symlink() or (os.name == "nt" and _is_junction(child)):
                entries[relative] = ("link", os.readlink(child.path) if hasattr(os, "readlink") else "")
                continue
            if child.is_dir(follow_symlinks=False):
                if checkout and os.path.lexists(os.path.join(child.path, ".git")):
                    continue  # A nested worktree or clone is its own checkout.
                entries[relative] = ("dir",)
                pending.append((Path(child.path), relative + "/"))
            else:
                status = child.stat(follow_symlinks=False)
                entries[relative] = ("file", status.st_size, status.st_mtime_ns)
    return entries


def _is_junction(entry: os.DirEntry) -> bool:
    try:
        return entry.is_junction()
    except AttributeError:
        return False


def _bundle_files(directory: Path, base: str) -> dict[str, object]:
    files = {}
    for child in directory.iterdir():
        if child.name == base or child.name.startswith(base + "."):
            status = child.stat()
            files[str(child)] = ("file", status.st_size, status.st_mtime_ns)
    return files


def _completed_bundles(store: Path, own_base: Path) -> list[tuple[str, str]]:
    bundles = []
    if not store.is_dir():
        return bundles
    for request in store.rglob("*.request.json"):
        base = request.name.removesuffix(".request.json")
        if path_key(request.parent / base) == path_key(own_base):
            continue
        try:
            run = json.loads(request.with_name(base + ".run.json").read_bytes())
        except (OSError, UnicodeError, ValueError):
            continue
        if isinstance(run, dict) and run.get("completed_at"):
            bundles.append((str(request.parent), base))
    return sorted(bundles)


def snapshot(plan: list[dict], *, seconds: float, own_output: Path,
             before: dict | None = None) -> dict[str, dict]:
    """One state per covered item; an item that can't be read is uncompared."""
    end = time.monotonic() + max(0.0, seconds)
    states: dict[str, dict] = {}
    for item in plan:
        path = Path(item["path"])
        try:
            _check(end)
            if item["method"] == REFS_METHOD:
                state = _refs_state(item, end)
            elif item["method"] in {"sha256", "registry"}:
                if not path.exists():
                    state = {"status": "absent"}
                else:
                    state = {"status": "compared", "digest": _sha256(path)}
                    if item["method"] == "registry":
                        rows = _registry_rows(path)
                        if rows is None:
                            raise ValueError("registry has an unsupported shape")
                        state["rows"] = {str(row.get("root", "")).casefold(): row for row in rows}
            elif item["method"] == "records":
                if before is not None:
                    bundles = (before.get(item["item"]) or {}).get("bundles") or []
                else:
                    bundles = _completed_bundles(path, own_output)
                entries: dict[str, object] = {}
                for directory, base in bundles:
                    _check(end)
                    if Path(directory).is_dir():
                        entries.update(_bundle_files(Path(directory), base))
                state = {"status": "compared", "bundles": bundles, "entries": entries}
            elif not path.exists():
                state = {"status": "absent"}
            else:
                state = {"status": "compared",
                         "entries": _walk(path, end, checkout=item["method"] == "checkout")}
        except _Expired as exc:
            state = {"status": "uncompared", "reason": str(exc)}
        except (OSError, UnicodeError, ValueError) as exc:
            state = {"status": "uncompared", "reason": f"{type(exc).__name__}: {exc}"}
        states[item["item"]] = state
    return states


def _finding_id(item: str, path: str, change: str) -> str:
    return hashlib.sha256(f"{item}\0{path}\0{change}".encode("utf-8")).hexdigest()[:12]


def _moment(value) -> datetime | None:
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return moment if moment.tzinfo else None


def recorded_runs(store: Path, own_dispatch: str) -> list[dict]:
    """Every other recorded run, with what attribution needs from it."""
    runs = []
    if not Path(store).is_dir():
        return runs
    for request_path in Path(store).rglob("*.request.json"):
        try:
            request = json.loads(request_path.read_bytes())
        except (OSError, UnicodeError, ValueError):
            continue
        if not isinstance(request, dict) or request.get("dispatch_id") == own_dispatch:
            continue
        base = request_path.name.removesuffix(".request.json")
        try:
            run = json.loads(request_path.with_name(base + ".run.json").read_bytes())
        except (OSError, UnicodeError, ValueError):
            run = {}
        runs.append({"dispatch_id": request.get("dispatch_id"), "root": request.get("root"),
                     "holder_session_id": request.get("holder_session_id"),
                     "work": request.get("work"),
                     "opened": _moment(request.get("launched_at")),
                     "closed": _moment(run.get("completed_at")) if isinstance(run, dict) else None,
                     "run": run if isinstance(run, dict) else {}})
    return runs


def _last_checkpoint(run: dict) -> datetime | None:
    """An unfinished run's last durable moment: its launch plus its recorded elapsed time."""
    try:
        elapsed = float(run["run"].get("elapsed_checkpoint_seconds") or 0)
    except (TypeError, ValueError):
        elapsed = 0.0
    return run["opened"] + timedelta(seconds=max(0.0, elapsed)) if run["opened"] else None


def _overlaps(run: dict, before_at: datetime, after_at: datetime) -> bool:
    """Opened before this run's after-snapshot and not closed before its before-snapshot.

    A run that never completed, a hard-killed launcher's, is not live forever:
    it overlaps only while its process is active or when its last checkpoint
    falls at or after this run's before-snapshot.
    """
    if run["opened"] is None or run["opened"] >= after_at:
        return False
    if run["closed"] is not None and run["closed"] >= before_at:
        return True
    if lifecycle.liveness(run["run"]) == "active":
        return True
    if run["closed"] is None:
        checkpoint = _last_checkpoint(run)
        return checkpoint is not None and checkpoint >= before_at
    return False


def _diff_entries(item: str, top: str, before: dict, after: dict, method: str) -> list[dict]:
    changes = []
    prefix = "" if method == "records" else top.rstrip("\\/") + os.sep
    for key in sorted(set(before) | set(after)):
        path = prefix + key.replace("/", os.sep) if prefix else key
        if key not in after:
            changes.append({"item": item, "path": path, "change": "removed"})
        elif key not in before:
            changes.append({"item": item, "path": path, "change": "added"})
        elif before[key] != after[key]:
            changes.append({"item": item, "path": path, "change": "modified"})
    return changes


def compare(plan: list[dict], before: dict, after: dict, *, root: Path, holder_session_id: str | None,
            store: Path, own_dispatch: str, before_at: str, after_at: str,
            elapsed_seconds: float, record: Path | None = None,
            home: Path | None = None) -> dict[str, object]:
    """Findings are changes no other live recorded run accounts for (row 2).

    Working-copy and branch changes are findings only when the run's record
    names them; the rest are ``listed``.
    """
    started, ended = _moment(before_at), _moment(after_at)
    changes, coverage = [], []
    refs_entries, refs_attributed, defaults, known_copies = [], [], {}, []
    live = None
    for item in plan:
        name, top = item["item"], item["path"]
        first, second = before.get(name, {}), after.get(name, {})
        statuses = {first.get("status"), second.get("status")}
        if item["method"] == REFS_METHOD and statuses == {"not-a-repository"}:
            coverage.append({"item": name, "status": "not-a-repository", "reason": None})
            continue
        if "uncompared" in statuses or None in statuses:
            reason = first.get("reason") or second.get("reason") or "no snapshot was taken"
            coverage.append({"item": name, "status": "uncompared", "reason": reason})
            changes.append({"item": name, "path": top, "change": "uncompared", "reason": reason})
            continue
        coverage.append({"item": name, "status": "absent" if statuses == {"absent"} else "compared",
                         "reason": None})
        if statuses == {"absent"}:
            continue
        if item["method"] == REFS_METHOD:
            coverage[-1].update(default_branch=first.get("default") or second.get("default"),
                                default_rule=first.get("default_rule"))
            defaults[name] = first.get("default") or second.get("default")
            for state in (first, second):
                known_copies += [copy["path"] for copy in (state.get("copies") or {}).values()]
            if live is None:
                live = ([run for run in recorded_runs(store, own_dispatch)
                         if _overlaps(run, started, ended)] if started and ended else [])
            entries, attributed_refs = _refs_changes(name, first, second, Path(root), live)
            refs_entries += entries
            refs_attributed += attributed_refs
            continue
        if item["method"] in {"sha256", "registry"}:
            if first["status"] == "absent":
                changes.append({"item": name, "path": top, "change": "added"})
            elif second["status"] == "absent":
                changes.append({"item": name, "path": top, "change": "removed"})
            elif item["method"] == "sha256" and first["digest"] != second["digest"]:
                changes.append({"item": name, "path": top, "change": "modified"})
            if item["method"] == "registry":
                rows_before, rows_after = first.get("rows") or {}, second.get("rows") or {}
                row_changes = [key for key in sorted(set(rows_before) | set(rows_after))
                               if rows_before.get(key) != rows_after.get(key)]
                for key in row_changes:
                    row = rows_after.get(key) or rows_before.get(key)
                    changes.append({"item": name, "path": str(row.get("root") or key),
                                    "change": "row-changed",
                                    "rows": (rows_before.get(key), rows_after.get(key))})
                if not row_changes and first.get("digest") != second.get("digest") and \
                        "absent" not in statuses:
                    changes.append({"item": name, "path": top, "change": "modified"})
            continue
        changes.extend(_diff_entries(name, top, first.get("entries") or {},
                                     second.get("entries") or {}, item["method"]))
    own_root = Path(root).resolve(strict=False)
    runs = None
    findings, attributed = [], []
    for change in changes:
        if change["change"] != "uncompared" and change["item"] not in {"registry", "own-request"} \
                and contains(own_root, Path(change["path"])):
            continue  # This run's own edits are its own work.
        owner = None
        if change["change"] != "uncompared" and started and ended:
            if runs is None:
                runs = recorded_runs(store, own_dispatch)
            owner = _attribute(change, runs, started, ended, holder_session_id)
        rows = change.pop("rows", None)
        if owner is not None:
            attributed.append({**{k: change[k] for k in ("item", "path", "change")}, "to": owner})
            continue
        entry = {"id": _finding_id(change["item"], change["path"], change["change"]),
                 "item": change["item"], "path": change["path"], "change": change["change"],
                 "reason": change.get("reason")}
        if rows is not None:
            entry["reason"] = "registry row added, removed or changed"
        findings.append(entry)
    result: dict[str, object] = {}
    listed: list[dict] = []
    if any(item["method"] == REFS_METHOD for item in plan):
        unreadable, named, skipped = None, None, 0
        try:
            if record is None:
                raise ValueError("no record was passed")
            calls, skipped = read_run_record(record)
        except ValueError as exc:
            unreadable = str(exc)
        if unreadable is None and refs_entries:
            names = set()
            for entry in refs_entries:
                names.add(entry.get("branch") or "")
                names.add((entry.get("folded_branch") or {}).get("branch") or "")
            named = named_targets(calls, root=Path(root), copies=known_copies,
                                  branches=sorted(names - {""}), home=str(home or Path.home()))
        held, listed = _classify_refs(refs_entries, default=defaults, named=named,
                                      unreadable=unreadable)
        findings += held
        attributed += refs_attributed
        result["run_record"] = {"path": str(record) if record is not None else None,
                                "status": "unreadable" if unreadable else "read",
                                "reason": unreadable}
        result["record_lines_skipped"] = skipped
    findings.sort(key=lambda value: value["id"])
    listed.sort(key=lambda value: value["id"])
    return {"schema_version": SCHEMA_VERSION, "status": "findings" if findings else "clean",
            "before_at": before_at, "after_at": after_at, "elapsed_seconds": elapsed_seconds,
            "coverage": coverage, "findings": findings, "attributed": attributed,
            "listed": listed, **result}


def _attribute(change: dict, runs: list[dict], started: datetime, ended: datetime,
               holder_session_id: str | None) -> dict | None:
    live = [run for run in runs if _overlaps(run, started, ended)]
    if change["item"] == "registry" and change["change"] == "row-changed":
        before_row, after_row = change.get("rows") or (None, None)
        for row in (before_row, after_row):
            if not isinstance(row, dict):
                continue
            holder = row.get("holder_session_id")
            if not isinstance(holder, str) or not holder or holder == holder_session_id:
                continue
            work = f"{row.get('repository')}#{row.get('issue')}".casefold()
            row_root = path_key(Path(str(row.get("root") or ""))) if row.get("root") else None
            for run in live:
                if run["holder_session_id"] != holder:
                    continue
                same_work = isinstance(run["work"], str) and run["work"].casefold() == work
                same_root = (row_root is not None and isinstance(run["root"], str)
                             and path_key(Path(run["root"])) == row_root)
                if same_work or same_root:
                    return {"dispatch_id": run["dispatch_id"], "holder_session_id": holder}
        return None
    if change["item"] in {"registry", "own-request", "dispatch-records"}:
        return None
    for run in live:
        if isinstance(run["root"], str) and run["root"] and contains(Path(run["root"]), Path(change["path"])):
            return {"dispatch_id": run["dispatch_id"], "holder_session_id": None}
    return None


# --- Each covered repository's working copies and branches -------------------
# Design: lib/DESIGN.md#the-launchs-working-copies-and-branches

REFS_METHOD = "git-refs"
REF_CHAR = r"A-Za-z0-9._/-"
NAME_CHAR = r"A-Za-z0-9._-"
SPLITTER = re.compile(r"[\s\"'`;|&()<>=]")
DIRECTORY_FORMS = re.compile(
    r"(?:^|[\s;&|(])(?:cd|pushd|set-location)\s+(?:-(?:literal)?path\s+)?"
    r"(\"[^\"]*\"|'[^']*'|[^\s;&|()]+)"
    r"|(?:^|[\s;&|(])git\s+-C\s+(\"[^\"]*\"|'[^']*'|[^\s;&|()]+)", re.IGNORECASE)


def _git_run(path: Path, timeout: float, *arguments: str):
    # The C locale keeps git's messages in English, which refs_plan reads.
    env = {**os.environ, "LC_ALL": "C", "LANGUAGE": "C"}
    return run_process(["git", "-C", str(path), *arguments], input=b"", cwd=Path(path),
                       timeout=timeout, on_tick=lambda: None, env=env,
                       cleanup_deadline=lifecycle.cleanup_deadline())


def refs_plan(root: Path, checkouts: list[Path]) -> list[dict[str, str]]:
    """One ``git-refs`` item per distinct repository: the run's own and every checkout's.

    The run's own repository is never left out, because a linked copy it makes
    can lie outside its root.
    """
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, path in enumerate([Path(root), *checkouts]):
        if index and not path.is_dir():
            continue  # A stale registration has nothing to compare.
        item = {"item": "refs:" + str(path), "path": str(path), "method": REFS_METHOD,
                "git": str(path)}
        try:
            result = _git_run(path, lifecycle.probe_timeout(), "rev-parse", "--path-format=absolute",
                              "--git-common-dir")
        except (OSError, subprocess.TimeoutExpired, TimeoutError) as exc:
            items.append({**item, "unavailable": f"git could not run: {exc}"})
            continue
        if result.returncode:
            error = result.stderr.decode("utf-8", "replace").strip()
            if "not a git repository" in error.lower():
                items.append({**item, "unavailable": "not-a-repository"})
            else:
                items.append({**item, "unavailable": f"git rev-parse failed: {error[:300]}"})
            continue
        common = Path(result.stdout.decode("utf-8", "replace").strip())
        key = path_key(common)
        if key in seen:
            continue
        seen.add(key)
        main = common.parent if common.name == ".git" else path
        items.append({**item, "item": "refs:" + str(common), "path": str(main)})
    return items


def _git_out(path: Path, end: float, *arguments: str) -> list[str]:
    _check(end)
    try:
        result = _git_run(path, max(0.1, end - time.monotonic()), *arguments)
    except (subprocess.TimeoutExpired, TimeoutError) as exc:
        raise _Expired(f"git {arguments[0]} ran out of time") from exc
    if result.returncode:
        raise ValueError(f"git {' '.join(arguments[:2])} failed: "
                         + result.stderr.decode("utf-8", "replace").strip()[:300])
    return result.stdout.decode("utf-8", "replace").splitlines()


def _worktrees(lines: list[str]) -> dict[str, dict]:
    copies: dict[str, dict] = {}
    current: dict | None = None
    for line in [*lines, ""]:
        if not line.strip():
            if current is not None:
                copies[path_key(Path(current["path"]))] = current
            current = None
            continue
        word, _, value = line.partition(" ")
        if word == "worktree":
            current = {"path": value, "head": None, "branch": None, "flags": []}
        elif current is not None and word == "HEAD":
            current["head"] = value
        elif current is not None and word == "branch":
            current["branch"] = value
        elif current is not None:
            current["flags"].append(word)
    return copies


def _short(ref: str | None) -> str | None:
    return ref[len("refs/heads/"):] if ref and ref.startswith("refs/heads/") else ref


def _default_branch(remotes: list[str], copies: dict[str, dict]) -> tuple[str | None, str]:
    """The repository's default branch, by the first rule that applies.

    The remote's ``HEAD`` names the branch others share and move, so it comes
    first: ``origin``'s, else that of the only remote, since with several no one
    remote is the shared one. A repository with a remote but no such ``HEAD``
    has no default identified, because its main working copy may have a feature
    branch checked out, and exempting that would let a named change go unheld.
    Only a repository with no remote at all falls back to the branch its main
    working copy has checked out, the one branch it shares with itself.
    """
    symbolic = {}
    for line in remotes:
        ref, _, target = line.partition("\0")
        symbolic[ref] = target
    names = {ref.split("/")[2] for ref in symbolic if ref.count("/") >= 3}
    for rule, remote in (("origin HEAD", "origin"),
                         ("the only remote's HEAD", next(iter(names)) if len(names) == 1 else None)):
        target = symbolic.get(f"refs/remotes/{remote}/HEAD") if remote else None
        if target and target.startswith(f"refs/remotes/{remote}/"):
            return target[len(f"refs/remotes/{remote}/"):], rule
    if names:
        return None, "none identified: a remote has no HEAD"
    first = next(iter(copies.values()), None)
    if first and first.get("branch"):
        return _short(first["branch"]), "the main working copy's branch"
    return None, "none identified"


def _refs_state(item: dict, end: float) -> dict[str, object]:
    if item.get("unavailable") == "not-a-repository":
        return {"status": "not-a-repository"}
    if item.get("unavailable"):
        return {"status": "uncompared", "reason": item["unavailable"]}
    path = Path(item["git"])
    copies = _worktrees(_git_out(path, end, "worktree", "list", "--porcelain"))
    branches, remotes = {}, []
    for line in _git_out(path, end, "for-each-ref",
                         "--format=%(refname)%00%(objectname)%00%(symref)", "refs/heads", "refs/remotes"):
        ref, _, rest = line.partition("\0")
        tip, _, target = rest.partition("\0")
        if ref.startswith("refs/heads/"):
            branches[ref] = tip
        else:
            remotes.append(ref + "\0" + target)
    default, rule = _default_branch(remotes, copies)
    return {"status": "compared", "copies": copies, "branches": branches,
            "default": default, "default_rule": rule}


def _refs_changes(name: str, first: dict, second: dict, root: Path, live: list[dict]
                  ) -> tuple[list[dict], list[dict]]:
    """Entries for changed copies and branches, and those attributed to overlapping runs.

    Only the copy at the run's root and its checked-out branch are the run's own.
    """
    copies_before, copies_after = first.get("copies") or {}, second.get("copies") or {}
    branches_before, branches_after = first.get("branches") or {}, second.get("branches") or {}
    own_key = path_key(Path(root).resolve(strict=False))
    own_branches = {copy["branch"] for copy in (copies_before.get(own_key), copies_after.get(own_key))
                    if copy and copy.get("branch")}
    others: dict[str, str] = {}
    for run in live:
        if isinstance(run.get("root"), str) and run["root"]:
            others.setdefault(path_key(Path(run["root"]).resolve(strict=False)), run["dispatch_id"])
    other_branches = {copy["branch"]: others[key] for key in others
                      for copy in (copies_before.get(key), copies_after.get(key))
                      if copy and copy.get("branch")}
    entries, attributed = [], []
    copy_entries: dict[str, dict] = {}
    for key in sorted(set(copies_before) | set(copies_after)):
        before, after = copies_before.get(key), copies_after.get(key)
        if before and after and (before["head"], before["branch"]) == (after["head"], after["branch"]):
            continue
        if key == own_key:
            continue
        change = "added" if before is None else "removed" if after is None else "moved"
        path = (after or before)["path"]
        if key in others:
            attributed.append({"item": name, "path": path, "change": change,
                               "to": {"dispatch_id": others[key], "holder_session_id": None}})
            continue
        entry = {"kind": "working-copy", "item": name, "path": path, "change": change,
                 "branch_before": _short(before and before["branch"]),
                 "branch_after": _short(after and after["branch"]),
                 "tip_before": before and before["head"], "tip_after": after and after["head"]}
        copy_entries[key] = entry
        entries.append(entry)
    for ref in sorted(set(branches_before) | set(branches_after)):
        before, after = branches_before.get(ref), branches_after.get(ref)
        if before == after or ref in own_branches:
            continue
        change = "added" if before is None else "removed" if after is None else "moved"
        if ref in other_branches:
            attributed.append({"item": name, "path": ref, "change": change,
                               "to": {"dispatch_id": other_branches[ref], "holder_session_id": None}})
            continue
        at = next((key for key, copy in copies_after.items() if copy.get("branch") == ref), None)
        if at is None:
            at = next((key for key, copy in copies_before.items()
                       if copy.get("branch") == ref and key not in copies_after), None)
        branch = {"branch": _short(ref), "change": change, "tip_before": before, "tip_after": after}
        if at is not None and at in copy_entries:
            copy_entries[at]["folded_branch"] = branch
            continue
        entries.append({"kind": "branch", "item": name, "path": ref, **branch,
                        "checked_out_at": (copies_after.get(at) or copies_before.get(at) or {}).get("path")
                        if at else None})
    return entries, attributed


def _leaves(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [leaf for item in value.values() for leaf in _leaves(item)]
    if isinstance(value, list):
        return [leaf for item in value for leaf in _leaves(item)]
    return []


def read_run_record(path: Path) -> tuple[list[dict], int]:
    """Every tool call in the run's stream, by the recipient or a helper, in order.

    The record is unreadable when it can't be opened, or when any line but a
    final unterminated one can't be decoded or is not a JSON object; that final
    line, as a killed process leaves it, perhaps cut inside a character, is
    skipped and counted.
    """
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise ValueError(f"{type(exc).__name__}: {exc}") from exc
    lines = data.split(b"\n")
    last = lines.pop()
    events, skipped = [], 0
    for number, line in enumerate(lines, 1):
        try:
            event = json.loads(line.decode("utf-8"))
        except ValueError:
            event = None
        if not isinstance(event, dict):
            raise ValueError(f"line {number} is not a JSON object")
        events.append(event)
    if last.strip():
        try:
            event = json.loads(last.decode("utf-8"))
        except ValueError:
            event = None
        if isinstance(event, dict):
            events.append(event)
        else:
            skipped = 1
    calls = []
    for event in events:
        if event.get("type") != "assistant":
            continue
        for block in _blocks(event):
            if block.get("type") == "tool_use":
                calls.append({"id": block.get("id"), "name": block.get("name"),
                              "agent": event.get("parent_tool_use_id"),
                              "strings": _leaves(block.get("input"))})
    return calls, skipped


def _normal_text(text: str, home: str, windows: bool) -> str:
    """Slashes forward, Git-Bash drives and home forms expanded, and case folded on Windows."""
    text = re.sub(r"\\+", "/", text)
    if windows:
        text = re.sub(rf"(?<![{REF_CHAR}])/([A-Za-z])(?=/|$|[^{NAME_CHAR}])",
                      lambda match: match.group(1) + ":", text)
    text = re.sub(rf"(?<![{REF_CHAR}])(?:~|\$HOME|\$env:USERPROFILE)(?=/|$|[^{NAME_CHAR}])",
                  lambda _match: home, text, flags=re.IGNORECASE)
    return text.casefold() if windows else text


def _normal_path(text: str) -> str:
    # POSIX keeps a leading "//" as its own root, but no path here is one, so it
    # folds to "/" like any other run of slashes.
    value = posixpath.normpath(text)
    return value[1:] if value.startswith("//") else value


def _deepest(path: str, tops: set[str]) -> str | None:
    """The deepest known copy whose top is ``path`` or one of its ancestors."""
    parts = path.split("/")
    for count in range(len(parts), 0, -1):
        prefix = "/".join(parts[:count]) or "/"
        if prefix in tops or prefix + "/" in tops:
            return prefix if prefix in tops else prefix + "/"
    return None


def _absolute(token: str) -> bool:
    return token.startswith("/") or re.match(r"[a-z]:/", token, re.IGNORECASE) is not None


def named_targets(calls: list[dict], *, root: Path, copies: list[str], branches: list[str],
                  home: str, windows: bool = os.name == "nt") -> dict[str, dict]:
    """Which copies (``copy:<path>``) and branches (``branch:<name>``) the run's tool calls name.

    A branch is named by its whole short name or ``refs/heads/<name>`` between
    ref-name boundaries, or as the last part of a path, as ``git worktree add
    ../x`` names the branch ``x`` it makes. A copy is named by a path at or
    inside its top that lies in no deeper known copy: an absolute path anywhere
    in the text, or a relative token resolved against each base of the agent
    that made the call. A quoted or backslash-escaped path is also tried whole,
    so a space inside it doesn't split it.
    An agent's bases are its launch root and every directory it named in
    ``cd``, ``pushd``, ``Set-Location`` or ``git -C``; they only grow.
    """
    home_text = _normal_path(_normal_text(home, "", windows))
    tops: dict[str, str] = {}
    for copy in copies:
        tops.setdefault(_normal_path(_normal_text(copy, home_text, windows)), copy)
    known = set(tops)
    occurrence = re.compile(
        rf"(?<![{REF_CHAR}])(?:{'|'.join(map(re.escape, sorted(known, key=len, reverse=True)))})"
        rf"(?=$|/|[^{NAME_CHAR}])") if known else None
    branch_set = set(branches)
    branch_names = sorted(branch_set, key=len, reverse=True)
    branch_pattern = re.compile(
        rf"(?:(?<![{REF_CHAR}])|(?<=refs/heads/))(?:{'|'.join(map(re.escape, branch_names))})"
        rf"(?![{REF_CHAR}])") if branch_names else None
    root_text = _normal_path(_normal_text(str(Path(root).resolve(strict=False)), home_text, windows))
    bases: dict[object, set[str]] = {}
    named: dict[str, dict] = {}
    cache: dict[str, str | None] = {}

    def hit(candidate: str, call: dict) -> None:
        if candidate not in cache:
            cache[candidate] = _deepest(candidate, known)
        if cache[candidate] is not None:
            named.setdefault("copy:" + tops[cache[candidate]],
                             {"tool": call["name"], "tool_use_id": call["id"]})

    def resolve(token: str, agent_bases: set[str]) -> list[str]:
        if _absolute(token):
            return [_normal_path(token)]
        return [_normal_path(base + "/" + token) for base in agent_bases]

    for call in calls:
        agent_bases = bases.setdefault(call["agent"], {root_text})
        for raw in call["strings"]:
            whole = _whole_arguments(raw)
            if branch_pattern is not None:
                for match in branch_pattern.finditer(raw):
                    named.setdefault("branch:" + match.group(0),
                                     {"tool": call["name"], "tool_use_id": call["id"]})
                for token in [*SPLITTER.split(raw), *whole]:
                    last = re.sub(r"\\+", "/", token).rstrip("/").rpartition("/")[2]
                    if "/" in token.replace("\\", "/") and last in branch_set:
                        named.setdefault("branch:" + last,
                                         {"tool": call["name"], "tool_use_id": call["id"]})
            if occurrence is None:
                continue
            text = _normal_text(raw, home_text, windows)
            for match in DIRECTORY_FORMS.finditer(text):
                target = (match.group(1) or match.group(2)).strip("\"'")
                if target:
                    agent_bases.update(resolve(target, agent_bases))
            remainder = list(text)
            for match in occurrence.finditer(text):
                end = match.end()
                while end < len(text) and not SPLITTER.match(text[end]):
                    end += 1
                hit(_normal_path(text[match.start():end]), call)
                remainder[match.start():end] = " " * (end - match.start())
            tokens = set(SPLITTER.split("".join(remainder)))
            tokens.update(_normal_text(argument, home_text, windows) for argument in whole)
            for token in tokens:
                if token:
                    for candidate in resolve(token, agent_bases):
                        hit(candidate, call)
    return named


QUOTED = re.compile(r'"([^"\n]{1,4096})"|\'([^\'\n]{1,4096})\'')
ESCAPED = re.compile(r"(?:[^\s\"'\\]|\\.)*\\ (?:[^\s\"'\\]|\\.)*")


def _whole_arguments(raw: str) -> list[str]:
    """Quoted and backslash-escaped arguments, unsplit, since a path in one may hold a space."""
    found = [first or second for first, second in QUOTED.findall(raw)]
    found += [match.replace("\\ ", " ") for match in ESCAPED.findall(raw)]
    return found


def _classify_refs(entries: list[dict], *, default: dict[str, str | None], named: dict[str, dict] | None,
                   unreadable: str | None) -> tuple[list[dict], list[dict]]:
    """Held entries the record names, and listed ones; the default branch never holds."""
    findings, listed = [], []
    for entry in entries:
        out = {"id": _finding_id(entry["item"], entry["path"], entry["change"]), **entry}
        branch_default = default.get(entry["item"])
        if branch_default and (
                (entry["kind"] == "branch" and entry["branch"] == branch_default)
                or (entry["kind"] == "working-copy" and entry["change"] == "moved"
                    and entry["branch_before"] == entry["branch_after"] == branch_default)):
            listed.append({**out, "reason": "default branch"})
            continue
        if unreadable is not None:
            findings.append({**out, "reason": f"run record unreadable: {unreadable}"})
            continue
        if entry["kind"] == "working-copy":
            folded = entry.get("folded_branch")
            keys = ["copy:" + entry["path"], *(["branch:" + folded["branch"]] if folded else [])]
        else:
            keys = ["branch:" + entry["branch"]]
        hit = next((named[key] for key in keys if named and key in named), None)
        if hit is not None:
            findings.append({**out, "reason": f"named in the run's record: {hit['tool']} call "
                                              f"{hit['tool_use_id']}"})
        else:
            listed.append({**out, "reason": "not named in the run's record"})
    return findings, listed


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Comparison:
    """Before and after one writing launch; only summaries reach the records."""

    def __init__(self, *, root: Path, env: dict[str, str] | None, launcher_plugin: Path,
                 own_output: Path, own_request: Path, holder_session_id: str | None,
                 dispatch_id: str, home: Path | None = None, store: Path | None = None,
                 refs: bool = False):
        import dispatch_record as records
        self.root, self.own_output, self.dispatch_id = Path(root), Path(own_output), dispatch_id
        self.holder_session_id = holder_session_id
        self.home = home or Path.home()
        self.store = store or records.default_record_root()
        self.plan = coverage_plan(root=self.root, home=self.home,
                                  env=dict(os.environ if env is None else env),
                                  launcher_plugin=launcher_plugin, store=self.store,
                                  own_request=own_request, refs=refs)
        self.before = None
        self.before_at = None
        self.started = None

    def planned(self) -> list[dict]:
        return [dict(item) for item in self.plan]

    def take_before(self, seconds: float) -> None:
        self.started = time.monotonic()
        self.before_at = now()
        self.before = snapshot(self.plan, seconds=seconds, own_output=self.own_output)

    def finish(self, seconds: float, *, record: Path | None = None) -> dict[str, object]:
        """The after-snapshot and comparison; a refs plan is never compared without its record.

        No record means the launch never named what its run made, so the whole
        comparison is recorded unrecorded. A record that exists but can't be read
        still lets each entry found be held one by one, so the holder sees which.
        """
        if record is None and any(item["method"] == REFS_METHOD for item in self.plan):
            raise ValueError("refs comparison needs the run's record")
        if self.before is None:
            raise RuntimeError("no before-snapshot was taken")
        after = snapshot(self.plan, seconds=seconds, own_output=self.own_output, before=self.before)
        after_at = now()
        result = compare(self.plan, self.before, after, root=self.root,
                         holder_session_id=self.holder_session_id, store=self.store,
                         own_dispatch=self.dispatch_id, before_at=self.before_at,
                         after_at=after_at, elapsed_seconds=time.monotonic() - self.started,
                         record=record, home=self.home)
        for entry in result["coverage"]:
            state = self.before.get(entry["item"]) or {}
            entries = state.get("entries")
            entry["entries"] = len(entries) if isinstance(entries, dict) else None
            entry["digest"] = state.get("digest")
            entry["path"] = next(i["path"] for i in self.plan if i["item"] == entry["item"])
        return result


def unrecorded(reason: str) -> dict[str, object]:
    """A comparison that could not run is held, never passed silently."""
    stamp = now()
    return {"schema_version": SCHEMA_VERSION, "status": "findings", "before_at": None,
            "after_at": stamp, "elapsed_seconds": 0.0, "coverage": [],
            # The id the entrance gives a missing comparison, so both routes to
            # an unrecorded comparison are named alike in an account.
            "findings": [{"id": "unrecorded", "item": "comparison",
                          "path": "", "change": "unrecorded", "reason": reason}],
            "attributed": [], "listed": []}


CLOUD_NOT_RUN_REASON = "not run: a cloud builder runs on a remote machine and cannot reach this one"


def cloud_not_run() -> dict[str, object]:
    """A cloud builder cannot reach this machine, so the comparison is not run.

    Design: lib/DESIGN.md#the-cloud-route
    """
    return {"schema_version": SCHEMA_VERSION, "status": "cloud-not-run", "before_at": None,
            "after_at": now(), "elapsed_seconds": 0.0, "coverage": [], "findings": [],
            "attributed": [],
            "reason": CLOUD_NOT_RUN_REASON}


def not_launched() -> dict[str, object]:
    """No process started, so nothing ran that could change a covered item."""
    return {"schema_version": SCHEMA_VERSION, "status": "not-launched", "before_at": None,
            "after_at": now(), "elapsed_seconds": 0.0, "coverage": [], "findings": [],
            "attributed": []}
