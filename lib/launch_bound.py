"""The write bound of a Claude launch that can write (#906).

A builder's or author's file-editing tools are confined to its tree and its
session scratchpad by a launch-owned PreToolUse hook (``tree_write_guard``).
Shell commands have no fence, so the Claude author and builder launches and the
Claude use consumer given a shell also compare what they must not touch before
and after the run. Other Claude seats given a shell are not compared.
A change the launcher cannot attribute to another live recorded run is a
finding the holder must account for; the entrance holds the change until then.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

from holder_tree_guard import contains, path_key
import run_lifecycle as lifecycle
from seat_process import run_process

GUARD = Path(__file__).resolve().with_name("tree_write_guard.py")
FILE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
GUARD_MATCHER = "|".join(FILE_TOOLS)
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


def guard_config(root: Path, session: str, env: dict[str, str], log: Path) -> dict[str, object]:
    home = env.get("USERPROFILE") if os.name == "nt" else env.get("HOME")
    return {"schema_version": SCHEMA_VERSION, "root": str(Path(root).resolve(strict=False)),
            "session": session, "home": home or os.path.expanduser("~"), "log": str(log),
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


def prepare_guard(temporary: Path, root: Path, session: str, env: dict[str, str], deadline
                  ) -> dict[str, object]:
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
    test_dir = temporary / "write-guard-self-test"
    test_dir.mkdir()
    test_config_path = test_dir / "write-guard.json"
    test_config = guard_config(root, session, env, test_dir / "write-guard.log.jsonl")
    _write_json(test_config_path, test_config)
    results = []
    for label, raw, expected in _self_test_targets(test_config, test_dir / "outside.txt"):
        payload = {"tool_name": "Write", "tool_use_id": f"self-test-{label}",
                   "tool_input": {"file_path": raw, "content": ""}, "cwd": str(root)}
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
    config_path = temporary / "write-guard.json"
    log = temporary / "write-guard.log.jsonl"
    config = guard_config(root, session, env, log)
    _write_json(config_path, config)
    log.write_bytes(b"")
    return {"config": config, "config_path": str(config_path), "log": str(log),
            "hooks": hook_settings(config_path), "self_test": results}


def file_tools_record(prepared: dict, settings_sha256: str) -> dict[str, object]:
    config = prepared["config"]
    return {"tools": list(FILE_TOOLS), "allowed": [config["root"], allowed_scratchpad(config)],
            "scratchpad_form": config["scratchpad_form"], "guard": str(GUARD),
            "guard_self_test": "passed", "settings_sha256": settings_sha256}


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
    """Cross-check the stream's file-tool calls against the guard's decisions.

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
            if block.get("type") == "tool_use" and block.get("name") in FILE_TOOLS:
                tool_input = block.get("input") if isinstance(block.get("input"), dict) else {}
                key = "notebook_path" if block["name"] == "NotebookEdit" else "file_path"
                calls.append({"tool": block["name"], "raw": tool_input.get(key),
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
    reasons = [f"launch write bound refused {r['tool']} {r['canonical'] or r['raw']}" for r in refusals]
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
                  store: Path, own_request: Path) -> list[dict[str, str]]:
    """What this launch must not touch, fixed before it starts."""
    config = Path(env.get("CLAUDE_CONFIG_DIR") or home / ".claude")
    cache = Path(env.get("CLAUDE_CODE_PLUGIN_CACHE_DIR") or config / "plugins")
    tradecraft = home / ".tradecraft"
    plan = [
        {"item": "switch", "path": str(tradecraft / "implementer-vendor"), "method": "sha256"},
        # The cloud route's machine switch; a local build that edits it is caught.
        {"item": "cloud-switch", "path": str(tradecraft / "cloud-builds.json"), "method": "sha256"},
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
            if item["method"] in {"sha256", "registry"}:
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
            elapsed_seconds: float) -> dict[str, object]:
    """Findings are changes no other live recorded run accounts for (row 2)."""
    started, ended = _moment(before_at), _moment(after_at)
    changes, coverage = [], []
    for item in plan:
        name, top = item["item"], item["path"]
        first, second = before.get(name, {}), after.get(name, {})
        statuses = {first.get("status"), second.get("status")}
        if "uncompared" in statuses or None in statuses:
            reason = first.get("reason") or second.get("reason") or "no snapshot was taken"
            coverage.append({"item": name, "status": "uncompared", "reason": reason})
            changes.append({"item": name, "path": top, "change": "uncompared", "reason": reason})
            continue
        coverage.append({"item": name, "status": "absent" if statuses == {"absent"} else "compared",
                         "reason": None})
        if statuses == {"absent"}:
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
    findings.sort(key=lambda value: value["id"])
    return {"schema_version": SCHEMA_VERSION, "status": "findings" if findings else "clean",
            "before_at": before_at, "after_at": after_at, "elapsed_seconds": elapsed_seconds,
            "coverage": coverage, "findings": findings, "attributed": attributed}


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


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Comparison:
    """Before and after one writing launch; only summaries reach the records."""

    def __init__(self, *, root: Path, env: dict[str, str] | None, launcher_plugin: Path,
                 own_output: Path, own_request: Path, holder_session_id: str | None,
                 dispatch_id: str, home: Path | None = None, store: Path | None = None):
        import dispatch_record as records
        self.root, self.own_output, self.dispatch_id = Path(root), Path(own_output), dispatch_id
        self.holder_session_id = holder_session_id
        self.home = home or Path.home()
        self.store = store or records.default_record_root()
        self.plan = coverage_plan(root=self.root, home=self.home,
                                  env=dict(os.environ if env is None else env),
                                  launcher_plugin=launcher_plugin, store=self.store,
                                  own_request=own_request)
        self.before = None
        self.before_at = None
        self.started = None

    def planned(self) -> list[dict]:
        return [dict(item) for item in self.plan]

    def take_before(self, seconds: float) -> None:
        self.started = time.monotonic()
        self.before_at = now()
        self.before = snapshot(self.plan, seconds=seconds, own_output=self.own_output)

    def finish(self, seconds: float) -> dict[str, object]:
        if self.before is None:
            raise RuntimeError("no before-snapshot was taken")
        after = snapshot(self.plan, seconds=seconds, own_output=self.own_output, before=self.before)
        after_at = now()
        result = compare(self.plan, self.before, after, root=self.root,
                         holder_session_id=self.holder_session_id, store=self.store,
                         own_dispatch=self.dispatch_id, before_at=self.before_at,
                         after_at=after_at, elapsed_seconds=time.monotonic() - self.started)
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
            "attributed": []}


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
