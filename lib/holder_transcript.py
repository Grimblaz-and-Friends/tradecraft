"""Token-only Claude transcript snapshots and serialized holder close evidence."""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
import uuid


TOKEN_CLASSES = frozenset({"input", "output", "cache_read", "cache_creation", "cache_write_5m", "cache_write_1h"})


class TranscriptError(RuntimeError):
    """Evidence or its durable close history cannot support an exact window."""


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.utcoffset() is not None else None


def projects_directory(explicit=None):
    if explicit is not None:
        return Path(explicit).expanduser().resolve(), "--claude-projects"
    configured = os.environ.get("CLAUDE_CONFIG_DIR", "")
    if configured:
        return (Path(configured).expanduser() / "projects").resolve(), "CLAUDE_CONFIG_DIR"
    return (Path.home() / ".claude" / "projects").resolve(), "home"


def session_identity(explicit=None):
    value = explicit if explicit is not None else os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    # IDs are basenames, never path expressions. Native UUIDs and fixture IDs fit.
    if value in {".", ".."} or any(char in value for char in '/\\:\x00'):
        raise TranscriptError("Claude session identity is not a usable basename")
    return value


def default_state_root():
    return Path.home() / ".tradecraft" / "holder-sessions"


def _bytes(value):
    return (json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8")


@contextmanager
def session_lock(directory, timeout=10):
    """An OS advisory lock is released even when its owner process dies."""
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "session.lock").open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise TranscriptError("holder session lock timed out; no close recorded") from exc
                time.sleep(0.05)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _publish(directory, entry):
    destination = directory / (entry["id"] + ".json")
    temporary = directory / (entry["id"] + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(_bytes(entry))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        if os.name != "nt":
            descriptor = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def _entries(directory, session=None):
    entries = []
    for path in sorted(directory.glob("*.json")):
        try:
            entry = json.loads(path.read_bytes())
        except (OSError, ValueError) as exc:
            raise TranscriptError(f"cannot read holder session journal: {path}: {exc}") from exc
        if (not isinstance(entry, dict) or entry.get("schema_version") != 1
                or entry.get("kind") not in {"close", "late-replies"}
                or entry.get("id") != path.stem
                or not isinstance(entry.get("row"), dict)
                or not isinstance(entry.get("destination"), str)
                or (session is not None and entry.get("session_id") != session)):
            raise TranscriptError(f"damaged or unsupported holder session journal: {path}")
        row = entry["row"]
        holder, dispatch = row.get("holder"), row.get("dispatch")
        if (not isinstance(holder, dict) or not isinstance(dispatch, dict)
                or holder.get("schema_version") != 1 or holder.get("session_id") != entry.get("session_id")
                or ledger_problem(holder) is not None or dispatch.get("id") != entry["id"]):
            raise TranscriptError(f"damaged holder journal row: {path}")
        entries.append(entry)
    return entries


def ledger_problem(holder):
    if (not isinstance(holder, dict) or holder.get("schema_version") != 1
            or holder.get("source_kind") not in {"transcript", "supplied"}
            or not isinstance(holder.get("window"), dict)
            or not isinstance(holder.get("replies"), list) or not isinstance(holder.get("gaps"), list)):
        return "holder transcript ledger has a damaged or unsupported shape"
    identities = set()
    for reply in holder["replies"]:
        if (not isinstance(reply, dict) or not isinstance(reply.get("id"), str) or not reply["id"]
                or reply["id"] in identities or timestamp(reply.get("timestamp")) is None
                or not isinstance(reply.get("model"), str) or not reply["model"]
                or not isinstance(reply.get("tokens"), dict)
                or not isinstance(reply.get("additional_native_classes"), dict)
                or not (reply.get("agent_id") is None or isinstance(reply.get("agent_id"), str))):
            return "holder transcript ledger has malformed or duplicate reply evidence"
        identities.add(reply["id"])
        counts = reply["tokens"]
        if (set(counts) != TOKEN_CLASSES
                or any(type(count) is not int or count < 0 for count in counts.values())
                or counts["cache_write_5m"] + counts["cache_write_1h"] != counts["cache_creation"]):
            return f"holder transcript ledger reply {reply['id']} has invalid duration/token populations"
    for gap in holder["gaps"]:
        if (not isinstance(gap, dict) or not isinstance(gap.get("source"), str)
                or not isinstance(gap.get("reason"), str)
                or (gap.get("reply_id") is not None and not isinstance(gap["reply_id"], str))
                or (gap.get("timestamp") is not None and timestamp(gap["timestamp"]) is None)):
            return "holder transcript ledger has malformed gap evidence"
    return None


def _history(entries):
    closes = {entry["id"]: entry for entry in entries if entry["kind"] == "close"}
    ordered = []
    previous = None
    while len(ordered) < len(closes):
        following = [entry for entry in closes.values()
                     if entry["row"].get("holder", {}).get("window", {}).get("previous_close_id") == previous]
        if len(following) != 1:
            raise TranscriptError("holder close history is damaged or branched; no boundary reset")
        entry = following[0]
        window = entry["row"].get("holder", {}).get("window", {})
        end = timestamp(window.get("closed_at"))
        start = timestamp(window.get("previous_close_at"))
        prior_end = timestamp(ordered[-1]["row"]["holder"]["window"]["closed_at"]) if ordered else None
        if (end is None or start != prior_end or (start is not None and end < start)
                or (window.get("previous_close_at") is not None and start is None)):
            raise TranscriptError("holder close history has invalid time boundaries")
        ordered.append(entry)
        previous = entry["id"]
    for entry in entries:
        if entry["kind"] == "late-replies" and entry.get("original_close_id") not in closes:
            raise TranscriptError("late-recording receipt has no committed original close")
    return ordered


def _counter(value, name):
    if type(value) is not int or value < 0:
        raise TranscriptError(f"{name} is not a nonnegative integer token count")
    return value


def _population(usage):
    names = {"input_tokens": "input", "output_tokens": "output",
             "cache_read_input_tokens": "cache_read", "cache_creation_input_tokens": "cache_creation"}
    counts = {target: _counter(usage.get(source), source) for source, target in names.items()}
    durations = usage.get("cache_creation")
    if counts["cache_creation"] == 0 and (durations is None or durations == {}):
        durations = {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 0}
    if not isinstance(durations, dict):
        raise TranscriptError("positive cache writes have no duration breakdown")
    counts["cache_write_5m"] = _counter(durations.get("ephemeral_5m_input_tokens"), "five-minute cache writes")
    counts["cache_write_1h"] = _counter(durations.get("ephemeral_1h_input_tokens"), "one-hour cache writes")
    if counts["cache_write_5m"] + counts["cache_write_1h"] != counts["cache_creation"]:
        raise TranscriptError("cache write duration counts disagree with aggregate cache writes")
    ignored = {*names, "cache_creation", "iterations", "output_tokens_details",
               "input_tokens_details", "thinking_tokens", "service_tier", "inference_geo"}
    extras = {}
    for name, value in usage.items():
        if name in ignored or _money_name(name):
            continue
        if name == "server_tool_use" and value is None:
            continue
        if name == "server_tool_use" and not isinstance(value, dict):
            raise TranscriptError("server_tool_use billable counters are not an object")
        if isinstance(value, dict):
            positive = {}
            for key, count in value.items():
                if _money_name(key):
                    continue
                if key.endswith(("_tokens", "Tokens", "_requests")) or name == "server_tool_use":
                    _counter(count, f"{name}.{key}")
                if isinstance(count, (int, float)) and not isinstance(count, bool) and count > 0:
                    positive[key] = count
            if positive:
                extras[name] = positive
        else:
            if name.endswith(("_tokens", "Tokens", "_requests")):
                _counter(value, name)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
                extras[name] = value
    return counts, extras


def _money_name(name):
    return any(word in name.lower() for word in ("amount", "cost", "currency", "usd", "price"))


def _fingerprint(reply):
    return {key: reply[key] for key in ("model", "tokens", "additional_native_classes")}


def snapshot(projects, session):
    candidates = [directory / (session + ".jsonl") for directory in projects.iterdir()
                  if directory.is_dir() and (directory / (session + ".jsonl")).is_file()] if projects.exists() else []
    if len(candidates) != 1:
        raise TranscriptError(f"holder transcript {'not found' if not candidates else 'ambiguous'}: {projects}/*/{session}.jsonl")
    main = candidates[0].resolve()
    children = main.parent / session / "subagents"
    paths = [main, *sorted(children.glob("agent-*.jsonl"))]
    replies = {}
    invalid_ids = set()
    gaps = []
    sources = []
    child_references = []
    for path in paths:
        agent = path.stem.removeprefix("agent-") if path != main else None
        try:
            data = path.read_bytes()
            data.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            if path == main:
                raise TranscriptError(f"cannot read holder transcript: {path}: {exc}") from exc
            gaps.append({"source": str(path), "timestamp": None, "reason": f"cannot read subagent transcript: {exc}"})
            continue
        sources.append({"path": str(path), "size_bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(), "agent_id": agent})
        for number, line in enumerate(data.splitlines(), 1):
            if not line.strip():
                continue
            location = f"{path}:{number}"
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise TranscriptError("record is not a JSON object")
            except (ValueError, TranscriptError) as exc:
                gaps.append({"source": location, "timestamp": None, "reason": f"incomplete or malformed transcript record: {exc}"})
                continue
            when = timestamp(record.get("timestamp"))
            result = record.get("toolUseResult")
            if path == main and isinstance(result, dict) and isinstance(result.get("agentId"), str):
                child_references.append((result["agentId"], location, record.get("timestamp") if when else None))
            if record.get("type") == "system" and record.get("subtype") == "compact_boundary":
                gaps.append({"source": location, "timestamp": record.get("timestamp") if when else None,
                             "reason": "compaction request usage is not identifiable in this transcript"})
            if record.get("type") != "assistant":
                continue
            message = record.get("message")
            usage = message.get("usage") if isinstance(message, dict) else None
            if usage is None:
                # Interrupted assistant records cannot establish their consumption.
                gaps.append({"source": location, "timestamp": record.get("timestamp") if when else None,
                             "reason": "assistant record has no usage"})
                continue
            identity = message.get("id")
            try:
                if not isinstance(identity, str) or not identity.strip():
                    raise TranscriptError("usage-bearing reply has no message id")
                model = message.get("model")
                if not isinstance(model, str) or not model.strip():
                    raise TranscriptError("usage-bearing reply has no observed model")
                if when is None:
                    raise TranscriptError("usage-bearing reply has no timezone-aware timestamp")
                if record.get("sessionId") != session:
                    raise TranscriptError("usage-bearing reply has a different or missing parent session identity")
                if agent is not None and record.get("agentId") != agent:
                    raise TranscriptError("subagent file and native agent identity disagree")
                if not isinstance(usage, dict):
                    raise TranscriptError("reply usage is not an object")
                counts, extras = _population(usage)
                reply = {"id": identity, "timestamp": when.isoformat(), "model": model,
                         "tokens": counts, "additional_native_classes": extras,
                         "agent_id": agent, "sources": [location]}
                old = replies.get(identity)
                if old is not None:
                    if (_fingerprint(old) != _fingerprint(reply)
                            or (old["agent_id"] is not None and agent is not None and old["agent_id"] != agent)):
                        raise TranscriptError(f"conflicting usage/model/agent for message id {identity}")
                    old["timestamp"] = min(timestamp(old["timestamp"]), when).isoformat()
                    old["agent_id"] = old["agent_id"] or agent
                    old["sources"].append(location)
                else:
                    replies[identity] = reply
            except TranscriptError as exc:
                if isinstance(identity, str) and identity:
                    invalid_ids.add(identity)
                gaps.append({"source": location, "timestamp": record.get("timestamp") if when else None,
                             "reason": str(exc), "reply_id": identity if isinstance(identity, str) else None})
    for identity in invalid_ids:
        replies.pop(identity, None)
    observed_agents = {item["agent_id"] for item in sources if item["agent_id"] is not None}
    for agent, location, when in child_references:
        if agent not in observed_agents:
            gaps.append({"source": location, "timestamp": when,
                         "reason": f"referenced subagent {agent} has no readable transcript snapshot"})
    return main, list(replies.values()), gaps, sources


def aggregate(replies):
    models = {}
    for reply in replies:
        population = models.setdefault(reply["model"], {})
        for name, count in reply["tokens"].items():
            population[name] = population.get(name, 0) + count
    return {"models": models}


def additional_counts(replies):
    models = {}
    for reply in replies:
        if not reply["additional_native_classes"]:
            continue
        population = models.setdefault(reply["model"], {})
        for name, value in reply["additional_native_classes"].items():
            previous = population.get(name)
            if previous is not None and isinstance(previous, dict) != isinstance(value, dict):
                # Each reply retains the original count. Do not invent an
                # aggregate across incompatible vendor field shapes.
                population.setdefault("unresolved_populations", []).append({name: value})
                continue
            if isinstance(value, dict):
                nested = population.setdefault(name, {})
                for key, count in value.items():
                    nested[key] = nested.get(key, 0) + count
            else:
                population[name] = population.get(name, 0) + value
    return models


def _in_window(when, lower, upper):
    return when is not None and (lower is None or lower < when) and when <= upper


def _row(repo, issue, model, identity, session, root, root_source, destination, window,
         source, replies, gaps, sources, failure):
    return {
        "change": {"repository": repo, "issue": issue, "unknown_reason": None},
        "dispatch": {"id": identity, "requested_vendor": "claude", "actual_vendor": "claude",
                     "stage": "holder-close", "continuity": "fresh", "staffing_status": "qualified",
                     "launched_at": window["closed_at"], "completed_at": window["closed_at"]},
        "model": {"requested": model, "reported": sorted({reply["model"] for reply in replies}),
                  "reported_unknown_reason": failure},
        "tokens": None if failure else aggregate(replies), "tokens_unknown_reason": failure,
        "additional_native_classes": additional_counts(replies), "scope": "invocation",
        "source_field": "Claude transcript message.usage", "raw_source": str(source) if source else None,
        "runtime_version": None, "runtime_version_unknown_reason": "runtime version was not captured from transcript metadata",
        "holder": {"schema_version": 1, "source_kind": "transcript", "session_id": session,
                   "projects_root": str(root), "projects_root_source": root_source,
                   "destination": str(destination), "window": window, "attribution": "attributed by time",
                   "status": "unknown" if failure or (gaps and not replies) else "recorded",
                   "observed_empty": not failure and not gaps and not replies,
                   "replies": replies, "snapshots": sources, "gaps": gaps},
    }


def _materialize(destination, row):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("ab") as stream:
        # A separator lets a committed journal recover a preceding torn line.
        stream.write(b"\n" + _bytes(row))
        stream.flush()
        os.fsync(stream.fileno())


def _supplied_without_boundary(row, destination, session, requested_session, session_source, root, root_source, reason):
    """Keep caller evidence usable without pretending its boundary was registered."""
    row["holder"] = {
        "schema_version": 1, "source_kind": "supplied", "session_id": session,
        "requested_session_id": requested_session, "session_id_source": session_source,
        "projects_root": str(root), "projects_root_source": root_source,
        "destination": str(destination), "replies": [], "gaps": [],
        "attribution": "supplied counters; declared scope",
        "window": {"previous_close_id": None, "previous_close_at": None,
                   "closed_at": row["dispatch"]["completed_at"], "boundary_registered": False,
                   "boundary_unknown_reason": reason},
    }
    _materialize(destination, row)
    return row


def close(repo, issue, destination, *, model=None, session_id=None, projects=None,
          state_root=None, now=None, supplied_row=None, lock_timeout=10):
    root, root_source = projects_directory(projects)
    requested_session = session_id if session_id is not None else os.environ.get("CLAUDE_CODE_SESSION_ID")
    session_source = "--session-id" if session_id is not None else "CLAUDE_CODE_SESSION_ID"
    destination = Path(destination).resolve()
    try:
        session = session_identity(session_id)
        identity_error = None
    except TranscriptError as exc:
        session, identity_error = None, str(exc)
    state_root = Path(state_root) if state_root is not None else default_state_root()
    if session is None:
        if supplied_row is not None:
            return _supplied_without_boundary(supplied_row, destination, session, requested_session,
                                              session_source, root, root_source,
                                              identity_error or "Claude session identity is unavailable")
        captured = now or datetime.now(timezone.utc)
        window = {"previous_close_id": None, "previous_close_at": None, "closed_at": captured.isoformat(),
                  "lower_exclusive": True, "upper_inclusive": True, "boundary_registered": False}
        row = _row(repo, issue, model, "holder-close-" + uuid.uuid4().hex, None, root, root_source,
                   destination, window, None, [], [], [], identity_error or "Claude session identity is unavailable")
        row["holder"].update(requested_session_id=requested_session, session_id_source=session_source,
                              attempted_source=str(root))
        _materialize(destination, row)
        return row
    directory = state_root / hashlib.sha256(session.encode("utf-8")).hexdigest()
    with ExitStack() as locks:
        try:
            locks.enter_context(session_lock(directory, lock_timeout))
            entries = _entries(directory, session)
            history = _history(entries)
        except (OSError, TranscriptError) as exc:
            if supplied_row is None:
                raise
            return _supplied_without_boundary(supplied_row, destination, session, requested_session,
                                              session_source, root, root_source, str(exc))
        previous = history[-1] if history else None
        lower = timestamp(previous["row"]["holder"]["window"]["closed_at"]) if previous else None
        captured = now or datetime.now(timezone.utc)
        if captured.utcoffset() is None or (lower is not None and captured < lower):
            raise TranscriptError("close clock moved backward or lacks timezone; no close recorded")
        identity = "holder-close-" + uuid.uuid4().hex
        window = {"previous_close_id": previous["id"] if previous else None,
                  "previous_close_at": lower.isoformat() if lower else None, "closed_at": captured.isoformat(),
                  "lower_exclusive": True, "upper_inclusive": True, "boundary_registered": True}
        recovered = []
        if supplied_row is None:
            source, replies, gaps, sources, failure = None, [], [], [], None
            try:
                source, replies, gaps, sources = snapshot(root, session)
            except (OSError, TranscriptError) as exc:
                failure = str(exc)
            seen = {}
            origins = {}
            seen_gaps = set()
            for entry in entries:
                for reply in entry["row"].get("holder", {}).get("replies", []):
                    old = seen.get(reply["id"])
                    # A later child snapshot can establish the identity of a
                    # reply first observed in the main file. Journal filename
                    # order must not erase that corroborated identity.
                    seen[reply["id"]] = old if old is not None and old["agent_id"] else reply
                    origins[reply["id"]] = entry["id"] if entry["kind"] == "close" else entry["original_close_id"]
                for gap in entry["row"]["holder"].get("gaps", []):
                    seen_gaps.add(_gap_identity(gap))
            selected = []
            late = {}
            for reply in replies:
                when = timestamp(reply["timestamp"])
                if reply["id"] in seen:
                    old = seen[reply["id"]]
                    if (_fingerprint(reply) != _fingerprint(old)
                            or (old["agent_id"] and reply["agent_id"] and old["agent_id"] != reply["agent_id"])):
                        gaps.append({"source": reply["sources"][0], "timestamp": None,
                                     "reply_id": reply["id"],
                                     "reason": f"committed reply {reply['id']} now has conflicting usage or agent identity"})
                    elif timestamp(reply["timestamp"]) != timestamp(old["timestamp"]):
                        gaps.append({"source": reply["sources"][0], "timestamp": None,
                                     "reply_id": reply["id"],
                                     "reason": f"committed reply {reply['id']} now has an earlier attribution timestamp"})
                    elif old["agent_id"] is None and reply["agent_id"] is not None:
                        # Retain the existing charge once, with enough newly
                        # observed identity to reconsider dispatch coverage.
                        original_id = origins[reply["id"]]
                        late.setdefault(original_id, {"replies": [], "gaps": []})["replies"].append(reply)
                    continue
                if _in_window(when, lower, captured):
                    selected.append(reply)
                elif lower is not None and when <= lower:
                    original = next((entry for entry in history if _in_window(
                        when, timestamp(entry["row"]["holder"]["window"].get("previous_close_at")),
                        timestamp(entry["row"]["holder"]["window"]["closed_at"]))), None)
                    if original is not None and original["row"]["holder"]["source_kind"] == "transcript":
                        late.setdefault(original["id"], {"replies": [], "gaps": []})["replies"].append(reply)
            current_gaps = []
            for gap in gaps:
                if _gap_identity(gap) in seen_gaps:
                    continue
                when = timestamp(gap["timestamp"])
                # Contradictory evidence belongs to the close that retained the
                # reply, even when the replay was written in a later interval.
                original = next((entry for entry in history if entry["id"] == origins.get(gap.get("reply_id"))), None)
                if original is None and lower is not None and when is not None and when <= lower:
                    original = next((entry for entry in history if _in_window(
                        when, timestamp(entry["row"]["holder"]["window"].get("previous_close_at")),
                        timestamp(entry["row"]["holder"]["window"]["closed_at"]))), None)
                if original is not None and original["row"]["holder"]["source_kind"] == "transcript":
                    late.setdefault(original["id"], {"replies": [], "gaps": []})["gaps"].append(gap)
                elif when is None or _in_window(when, lower, captured):
                    current_gaps.append(gap)
            for original_id, recovered_evidence in late.items():
                original = next(entry for entry in history if entry["id"] == original_id)
                receipt_id = "late-replies-" + uuid.uuid4().hex
                original_change = original["row"]["change"]
                receipt_row = _row(original_change["repository"], original_change["issue"], model,
                                   receipt_id, session, root, root_source,
                                   Path(original["destination"]), original["row"]["holder"]["window"],
                                   source, recovered_evidence["replies"], recovered_evidence["gaps"], sources, None)
                receipt = {"schema_version": 1, "kind": "late-replies", "id": receipt_id,
                           "session_id": session, "original_close_id": original_id,
                           "observed_at": captured.isoformat(), "destination": original["destination"],
                           "row": receipt_row}
                locator = _publish(directory, receipt)
                recovered.append({"close_id": original_id, "receipt_id": receipt_id,
                                  "journal": str(locator), "destination": original["destination"]})
            gaps = current_gaps
            row = _row(repo, issue, model, identity, session, root, root_source, destination,
                       window, source, selected, gaps, sources, failure)
        else:
            row = supplied_row
            row["dispatch"].update(id=identity, launched_at=captured.isoformat(), completed_at=captured.isoformat())
            row["holder"] = {"schema_version": 1, "source_kind": "supplied", "session_id": session,
                             "projects_root": str(root), "projects_root_source": root_source,
                             "destination": str(destination), "window": window, "replies": [], "gaps": [],
                             "attribution": "supplied counters; declared scope"}
        row["holder"]["recovered_closes"] = recovered
        row["holder"].update(requested_session_id=requested_session, session_id_source=session_source,
                              attempted_source=str(root / "*" / (session + ".jsonl")))
        row["holder"]["journal"] = str(directory / (identity + ".json"))
        entry = {"schema_version": 1, "kind": "close", "id": identity, "session_id": session,
                 "destination": str(destination), "row": row}
        _publish(directory, entry)
        try:
            _materialize(destination, row)
        except OSError as exc:
            # Publication already committed the row and boundary. The journal is
            # the recovery route; this diagnostic is deliberately not row content.
            return {**row, "materialization_error": str(exc)}
        return row


def _gap_identity(gap):
    return gap.get("source"), gap.get("timestamp"), gap.get("reason"), gap.get("reply_id")


def holder_rows(destination, *, state_root=None):
    """Reconcile selected materialization with committed rows and late receipts."""
    destination = Path(destination).resolve()
    root = Path(state_root) if state_root is not None else default_state_root()
    rows, problems, skipped, receipts = {}, {}, [], {}
    journal_problems = []
    for directory in sorted(root.glob("*")):
        if not directory.is_dir():
            continue
        try:
            entries = _entries(directory)
            _history(entries)
        except (OSError, TranscriptError) as exc:
            journal_problems.append({"path": str(directory), "reason": str(exc)})
            continue
        for entry in entries:
            if Path(entry["destination"]).resolve() != destination:
                continue
            if entry["kind"] == "late-replies":
                if entry["id"] in receipts and receipts[entry["id"]] != entry:
                    problems.setdefault(entry["original_close_id"], []).append(
                        f"conflicting late-recording receipt {entry['id']}")
                else:
                    receipts[entry["id"]] = entry
            else:
                if entry["id"] in rows and rows[entry["id"]] != entry["row"]:
                    problems.setdefault(entry["id"], []).append(f"conflicting committed holder close {entry['id']}")
                else:
                    rows[entry["id"]] = entry["row"]
    if destination.exists():
        try:
            data = destination.read_bytes()
        except OSError as exc:
            skipped.append({"path": str(destination), "reason": f"cannot read holder materialization: {exc}"})
            data = b""
        for number, line in enumerate(data.splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("holder row is not an object")
            except (ValueError, UnicodeError) as exc:
                skipped.append({"path": f"{destination}:{number}", "reason": f"torn or malformed holder materialization: {exc}"})
                continue
            dispatch = row.get("dispatch")
            identity = (dispatch.get("id") if isinstance(dispatch, dict) else None) or f"unidentified-holder:{number}"
            if identity in rows and row != rows[identity]:
                problems.setdefault(identity, []).append(f"conflicting holder usage for dispatch {identity}")
            else:
                rows[identity] = row
    for problem in journal_problems:
        directory = Path(problem["path"])
        # A materialized close can establish the selected destination's session
        # even when its authoritative journal cannot be read. Otherwise the
        # directory is an unattributed warning, not this change's missing spend.
        related = any(isinstance(row.get("holder"), dict)
                      and isinstance(row["holder"].get("session_id"), str)
                      and hashlib.sha256(row["holder"]["session_id"].encode("utf-8")).hexdigest() == directory.name
                      for row in rows.values())
        skipped.append(problem if related else {**problem, "report_warning": True})
    for receipt in receipts.values():
        identity = receipt["original_close_id"]
        if identity not in rows:
            skipped.append({"path": str(destination), "reason": f"receipt original close {identity} is unavailable"})
            continue
        # Copy before composing; never edit the immutable normalized close.
        row = json.loads(json.dumps(rows[identity]))
        holder = row["holder"]
        seen = {reply["id"]: reply for reply in holder["replies"]}
        for reply in receipt["row"]["holder"]["replies"]:
            old = seen.get(reply["id"])
            if old is not None and (_fingerprint(reply) != _fingerprint(old)
                    or (old["agent_id"] and reply["agent_id"] and old["agent_id"] != reply["agent_id"])):
                problems.setdefault(identity, []).append(f"conflicting late reply {reply['id']}")
            else:
                seen[reply["id"]] = old if old is not None and old["agent_id"] else reply
        holder["replies"] = list(seen.values())
        gaps = {_gap_identity(gap): gap for gap in holder["gaps"]}
        gaps.update({_gap_identity(gap): gap for gap in receipt["row"]["holder"]["gaps"]})
        holder["gaps"] = list(gaps.values())
        holder["observed_empty"] = not holder["replies"] and not holder["gaps"] and not row.get("tokens_unknown_reason")
        holder.setdefault("late_recording_receipts", []).append({
            "id": receipt["id"], "observed_at": receipt["observed_at"], "original_close_id": identity})
        # An unknown original interval stays incomplete, even with recovered tokens.
        row["tokens"] = aggregate(holder["replies"])
        row["additional_native_classes"] = additional_counts(holder["replies"])
        row["model"]["reported"] = sorted({reply["model"] for reply in holder["replies"]})
        row["model"]["reported_unknown_reason"] = None if holder["replies"] else row.get("tokens_unknown_reason")
        rows[identity] = row
    return [(identity, row, problems.get(identity, [])) for identity, row in rows.items()], skipped
