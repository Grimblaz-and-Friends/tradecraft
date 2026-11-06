#!/usr/bin/env python3
"""The practice's cloud hook: practice check, usage totals and profile.

Usage: cloud.py stop     (Stop hook; hook input JSON on stdin)
       cloud.py prompt   (UserPromptSubmit hook; hook input JSON on stdin)
       cloud.py check --expect SHA --report-branch NAME --repository OWNER/REPO

It acts only in a Claude Code cloud session (``CLAUDE_CODE_REMOTE`` set) whose
prompt carries a ``TRADECRAFT-CLOUD-RUN v1`` header; elsewhere it does nothing
and prints nothing. Design: lib/DESIGN.md#the-cloud-route
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HEADER = "TRADECRAFT-CLOUD-RUN v1"
PREFIX = "tradecraft-cloud/"
# The practice repository's own doctrine; loaded into a product build it would govern that build,
# so a clone holding any of them is as wrong as a clone at another commit.
EXCLUDED = ("CLAUDE.md", "AGENTS.md", ".claude")
# Claude Code writes these for messages no model produced; they carry no usage.
SYNTHETIC_MODEL = "<synthetic>"
FIGURES = ("input", "output", "cache_read", "cache_write_5m", "cache_write_1h", "cache_creation")


class HookError(RuntimeError):
    pass


def parse_header(text: str) -> dict[str, str] | None:
    """The run's fields from the first header in ``text``, or None."""
    if not isinstance(text, str) or HEADER not in text:
        return None
    fields: dict[str, str] = {}
    for line in text[text.index(HEADER) + len(HEADER):].splitlines()[1:]:
        if ":" not in line:
            if line.strip():
                break
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if not key or " " in key:
            break
        fields[key] = value.strip()
    return fields if "report-branch" in fields else None


def _text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(block.get("text", "") for block in content
                         if isinstance(block, dict) and isinstance(block.get("text"), str))
    return ""


def read_jsonl(path: Path) -> list[dict]:
    """Every object line of a transcript; a malformed line is skipped."""
    entries = []
    with path.open("rb") as stream:
        for line in stream:
            try:
                value = json.loads(line)
            except (UnicodeError, ValueError):
                continue
            if isinstance(value, dict):
                entries.append(value)
    return entries


def list_files(transcript_path: Path, session: str) -> list[Path]:
    """The main transcript and every ``*.jsonl`` under the session's directory."""
    found = [transcript_path]
    directory = transcript_path.parent / session
    if directory.is_dir():
        found.extend(sorted(path for path in directory.rglob("*.jsonl")))
    return found


def _label(path: Path, transcript_path: Path, session: str) -> str:
    if path == transcript_path:
        return "main"
    return path.relative_to(transcript_path.parent / session).as_posix()


def _figures(usage: dict) -> dict[str, int]:
    row = {"input": usage.get("input_tokens", 0), "output": usage.get("output_tokens", 0),
           "cache_read": usage.get("cache_read_input_tokens", 0)}
    split = usage.get("cache_creation")
    if isinstance(split, dict) and ("ephemeral_5m_input_tokens" in split
                                    or "ephemeral_1h_input_tokens" in split):
        row["cache_write_5m"] = split.get("ephemeral_5m_input_tokens", 0)
        row["cache_write_1h"] = split.get("ephemeral_1h_input_tokens", 0)
    else:
        row["cache_creation"] = usage.get("cache_creation_input_tokens", 0)
    return {key: int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0
            for key, value in row.items()}


def tally(transcript_path: Path, session: str) -> dict[str, object]:
    """Usage over distinct message ids across every transcript file the session wrote."""
    present = list_files(transcript_path, session)
    read, unread, rows, main_entries = [], [], {}, []
    for path in present:
        label = _label(path, transcript_path, session)
        try:
            entries = read_jsonl(path)
        except OSError as exc:
            unread.append({"file": label, "error": f"{type(exc).__name__}: {exc}"})
            continue
        if label == "main":
            main_entries = entries
        bearing = 0
        for entry in entries:
            message = entry.get("message")
            if not isinstance(message, dict) or not isinstance(message.get("usage"), dict):
                continue
            identity, model = message.get("id"), message.get("model")
            if not isinstance(identity, str) or not isinstance(model, str) or model == SYNTHETIC_MODEL:
                continue
            bearing += 1
            # The last entry for an id carries its final usage; a repeat counts once.
            rows[identity] = {"id": identity, "model": model, "file": label, **_figures(message["usage"])}
        read.append({"file": label, "usage_entries": bearing})
    totals: dict[str, dict[str, int]] = {}
    for row in rows.values():
        model_totals = totals.setdefault(row["model"], {})
        for key in FIGURES:
            if key in row:
                model_totals[key] = model_totals.get(key, 0) + row[key]
    return {"files_present": [_label(path, transcript_path, session) for path in present],
            "files_read": read, "files_unread": unread,
            "totals_by_model": totals, "ledger": sorted(rows.values(), key=lambda row: row["id"]),
            "main_entries": main_entries}


def _effort(entry: dict) -> object:
    for holder in (entry, entry.get("message") if isinstance(entry.get("message"), dict) else {}):
        for key in ("effort", "perTurnEffort"):
            value = holder.get(key)
            if isinstance(value, str) and value:
                return value
            if isinstance(value, dict) and isinstance(value.get("level"), str):
                return value["level"]
    return None


def profile(main_entries: list[dict]) -> dict[str, list[str]]:
    """Models and efforts from the main session's own entries, sidechains excluded."""
    models, efforts = set(), set()
    for entry in main_entries:
        if entry.get("isSidechain") is True:
            continue
        message = entry.get("message")
        if entry.get("type") == "assistant" and isinstance(message, dict):
            model = message.get("model")
            if isinstance(model, str) and model != SYNTHETIC_MODEL:
                models.add(model)
        effort = _effort(entry)
        if effort is not None:
            efforts.add(effort)
    return {"models": sorted(models), "efforts": sorted(efforts)}


def permission_mode(hook_input: dict, main_entries: list[dict]) -> dict[str, object]:
    value = hook_input.get("permission_mode")
    if isinstance(value, str) and value:
        return {"values": [value], "source": "hook-input"}
    values = sorted({entry["permissionMode"] for entry in main_entries
                     if entry.get("type") == "user" and isinstance(entry.get("permissionMode"), str)})
    if values:
        return {"values": values, "source": "transcript"}
    return {"values": ["unknown"], "source": None}


def latest_header(main_entries: list[dict]) -> dict[str, str] | None:
    found = None
    for entry in main_entries:
        if entry.get("type") != "user" or entry.get("isSidechain") is True:
            continue
        message = entry.get("message")
        header = parse_header(_text(message.get("content") if isinstance(message, dict) else None))
        if header is not None:
            found = header
    return found


# ---- git plumbing on the product clone ------------------------------------

def _git(clone: Path, *arguments: str, env: dict | None = None, data: bytes | None = None) -> str:
    result = subprocess.run(["git", "-C", str(clone), *arguments], input=data if data is not None else b"",
                            capture_output=True, env=env, timeout=120)
    if result.returncode:
        raise HookError(f"git {' '.join(arguments[:2])} failed: "
                        + result.stderr.decode("utf-8", "replace").strip()[:300])
    return result.stdout.decode("utf-8", "replace").strip()


def clone_for(repository: str) -> Path:
    """The product clone a multi-source session lands beside the practice."""
    base = Path(os.environ.get("TRADECRAFT_CLOUD_HOME") or "/home/user")
    return base / repository.split("/")[-1]


class ReportBranch:
    """The run's report branch, read and extended through git plumbing.

    A temporary index and ``commit-tree`` add files without touching the clone's
    checkout, index or branch, which the builder is working in.
    """

    def __init__(self, clone: Path, branch: str):
        self.clone, self.branch = clone, branch
        self.ref = f"refs/tradecraft-cloud/{branch}"

    def fetch(self) -> str:
        _git(self.clone, "fetch", "--quiet", "origin", f"+refs/heads/{self.branch}:{self.ref}")
        return _git(self.clone, "rev-parse", self.ref)

    def read(self, name: str) -> bytes | None:
        result = subprocess.run(["git", "-C", str(self.clone), "cat-file", "blob", f"{self.ref}:{PREFIX}{name}"],
                                capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
        return result.stdout if result.returncode == 0 else None

    def blob(self, name: str) -> str | None:
        result = subprocess.run(["git", "-C", str(self.clone), "rev-parse", "--verify", "--quiet",
                                 f"{self.ref}:{PREFIX}{name}"],
                                capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
        return result.stdout.decode("ascii").strip() if result.returncode == 0 else None

    def commit(self, files: dict[str, bytes], message: str) -> str:
        """One commit adding ``files`` on the branch tip; a raced push is retried once."""
        for _attempt in range(2):
            tip = self.fetch()
            with tempfile.TemporaryDirectory() as temporary:
                env = {**os.environ, "GIT_INDEX_FILE": str(Path(temporary) / "index")}
                _git(self.clone, "read-tree", tip, env=env)
                for name, content in files.items():
                    blob = _git(self.clone, "hash-object", "-w", "--stdin", data=content)
                    _git(self.clone, "update-index", "--add", "--cacheinfo",
                         f"100644,{blob},{PREFIX}{name}", env=env)
                tree = _git(self.clone, "write-tree", env=env)
            identity = {**os.environ, "GIT_AUTHOR_NAME": "tradecraft cloud hook",
                        "GIT_AUTHOR_EMAIL": "tradecraft-cloud@invalid",
                        "GIT_COMMITTER_NAME": "tradecraft cloud hook",
                        "GIT_COMMITTER_EMAIL": "tradecraft-cloud@invalid"}
            commit = _git(self.clone, "commit-tree", tree, "-p", tip, "-m", message, env=identity)
            try:
                _git(self.clone, "push", "--quiet", "origin", f"{commit}:refs/heads/{self.branch}")
                return commit
            except HookError:
                continue
        raise HookError(f"could not push to report branch {self.branch}")


def _json(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


# ---- the practice check ---------------------------------------------------

def practice_state(plugin_root: Path, expect: str) -> dict[str, object]:
    try:
        found = _git(plugin_root, "rev-parse", "HEAD")
    except (HookError, OSError) as exc:
        found = f"unreadable: {exc}"
    excluded = [name for name in EXCLUDED if (plugin_root / name).exists()]
    ok = found == expect and not excluded
    return {"ok": ok, "commit": found} if ok else {
        "ok": False, "expected": expect, "found": found, "excluded_present": excluded}


def record_practice(branch: ReportBranch, result: dict[str, object]) -> None:
    """Commit the check's result; a recorded mismatch also writes the finish record."""
    existing = branch.read("practice-check.json") if branch.fetch() else None
    if result["ok"]:
        try:
            if existing and json.loads(existing).get("ok") is False:
                # The prompt hook and the saved prompt's check both run; a pass after a mismatch
                # would let the launcher read a stopped run as one that built.
                return
        except ValueError:
            pass
        branch.commit({"practice-check.json": _json(result)},
                      f"tradecraft cloud practice check pass [skip ci]")
        return
    report = (f"PRACTICE MISMATCH expected {result['expected']} found {result['found']}\n"
              + (f"excluded paths present in the practice clone: {', '.join(result['excluded_present'])}\n"
                 if result["excluded_present"] else ""))
    report_bytes = report.encode("utf-8")
    blob = subprocess.run(["git", "hash-object", "--stdin"], input=report_bytes,
                          capture_output=True, timeout=60).stdout.decode("ascii").strip()
    usage = {"schema_version": 1, "practice_check": result, "report_blob": blob,
             "finish": "practice-mismatch"}
    branch.commit({"practice-check.json": _json(result), "report.md": report_bytes,
                   "usage.json": _json(usage)}, "tradecraft cloud practice mismatch [skip ci]")


def _plugin_root() -> Path:
    return Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parents[1])


def run_check(expect: str, report_branch: str, repository: str) -> int:
    result = practice_state(_plugin_root(), expect)
    record_practice(ReportBranch(clone_for(repository), report_branch), result)
    if not result["ok"]:
        print(f"practice check failed: {json.dumps(result, sort_keys=True)}", file=sys.stderr)
        return 1
    print(f"practice check passed at {expect}")
    return 0


def run_prompt(hook_input: dict) -> int:
    header = parse_header(hook_input.get("prompt") or "")
    if header is None or "practice-commit" not in header or "repository" not in header:
        return 0
    result = practice_state(_plugin_root(), header["practice-commit"])
    try:
        record_practice(ReportBranch(clone_for(header["repository"]), header["report-branch"]), result)
    except (HookError, OSError, subprocess.SubprocessError) as exc:
        print(f"tradecraft cloud: practice record failed: {exc}", file=sys.stderr)
    if result["ok"]:
        return 0
    print(f"PRACTICE MISMATCH: {json.dumps(result, sort_keys=True)}; stop before building",
          file=sys.stderr)
    return 2  # Blocks the prompt: the builder never receives it.


# ---- the Stop hook --------------------------------------------------------

def _error_store(session: str) -> Path:
    return Path(tempfile.gettempdir()) / f"tradecraft-cloud-{session}.errors.json"


def run_stop(hook_input: dict) -> int:
    session = hook_input.get("session_id")
    transcript = hook_input.get("transcript_path")
    if not isinstance(session, str) or not isinstance(transcript, str):
        return 0
    transcript_path = Path(transcript)
    store = _error_store(session)
    try:
        counted = tally(transcript_path, session)
        header = latest_header(counted["main_entries"])
        if header is None or "repository" not in header:
            return 0
        branch = ReportBranch(clone_for(header["repository"]), header["report-branch"])
        branch.fetch()
        previous = branch.read("usage.json")
        try:
            index = int(json.loads(previous).get("stop_index", 0)) + 1 if previous else 1
        except (ValueError, AttributeError, TypeError):
            index = 1
        check = branch.read("practice-check.json")
        try:
            practice = json.loads(check) if check else None
        except ValueError:
            practice = {"ok": None, "reason": "practice-check.json on the report branch is not JSON"}
        try:
            earlier = json.loads(store.read_text("utf-8")) if store.exists() else []
        except (OSError, ValueError):
            earlier = []
        usage = {
            "schema_version": 1, "session": session, "stop_index": index,
            "files_present": counted["files_present"], "files_read": counted["files_read"],
            "files_unread": counted["files_unread"],
            "totals_by_model": counted["totals_by_model"], "ledger": counted["ledger"],
            "profile": profile(counted["main_entries"]),
            "permission_mode": permission_mode(hook_input, counted["main_entries"]),
            "report_blob": branch.blob("report.md"),
            "practice_check": practice if practice is not None else {
                "ok": None, "reason": "no practice check recorded on the report branch"},
            "hook_errors": earlier,
        }
        branch.commit({"usage.json": _json(usage)},
                      f"tradecraft cloud usage {session} stop {index} [skip ci]")
        store.unlink(missing_ok=True)
    except Exception as exc:  # The hook never blocks a turn.
        message = f"{type(exc).__name__}: {exc}"
        print(f"tradecraft cloud usage hook: {message}", file=sys.stderr)
        try:
            earlier = json.loads(store.read_text("utf-8")) if store.exists() else []
            store.write_text(json.dumps([*earlier, message]), "utf-8")
        except (OSError, ValueError):
            pass
    return 0


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", newline="")
    sys.stderr.reconfigure(encoding="utf-8", newline="")
    argv = list(sys.argv[1:] if argv is None else argv)
    if not os.environ.get("CLAUDE_CODE_REMOTE"):
        return 0
    mode = argv[0] if argv else ""
    if mode == "check":
        import argparse
        parser = argparse.ArgumentParser(prog="cloud.py check")
        parser.add_argument("--expect", required=True)
        parser.add_argument("--report-branch", required=True)
        parser.add_argument("--repository", required=True)
        args = parser.parse_args(argv[1:])
        try:
            return run_check(args.expect, args.report_branch, args.repository)
        except (HookError, OSError, subprocess.SubprocessError) as exc:
            print(f"practice check could not record its result: {exc}", file=sys.stderr)
            return 1
    try:
        hook_input = json.loads(sys.stdin.buffer.read() or b"{}")
    except (UnicodeError, ValueError):
        return 0
    if not isinstance(hook_input, dict):
        return 0
    if mode == "stop":
        return run_stop(hook_input)
    if mode == "prompt":
        return run_prompt(hook_input)
    return 0


if __name__ == "__main__":
    sys.exit(main())
