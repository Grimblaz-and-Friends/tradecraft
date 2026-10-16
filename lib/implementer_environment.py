"""Attempt-local observations; requests never certify runtime holdings."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

CATEGORIES = ("plugins", "integrations", "tools", "skills", "instructions", "memory", "permissions")
# claude.ai account skills reach Claude sessions under this namespace without
# any reported plugin owning it.
ACCOUNT_SKILL_NAMESPACE = "anthropic-skills"
UNCLASSIFIED_NOTE = ("unclassified means not checked, not clean: the runtime did not report "
                     "these entries' origin, so they are not counted as excess")


def category(status="unknown", values=None, reason="runtime did not report this inventory", source=None):
    return {"status": status, "values": [] if values is None else values,
            "reason": reason, "sources": [source] if source else []}


def unknown(reason, *, vendor=None, version=None):
    return {"schema_version": 1, "vendor": vendor, "runtime_version": version,
            "session_id": None, "turn_id": None, "boundary": "unobserved",
            "categories": {name: category(reason=reason) for name in CATEGORIES},
            "facts": {}, "excess": [], "unclassified": [], "unclassified_note": UNCLASSIFIED_NOTE}


def coordinate(path, line, field):
    return {"path": str(path), "line": line, "field": field}


def valid_category(value):
    """A serialized known inventory needs its runtime source coordinates."""
    if not isinstance(value, dict) or value.get("status") not in {"known", "partial", "unknown"}:
        return False
    if not isinstance(value.get("values"), list) or not isinstance(value.get("sources"), list):
        return False
    if (value["status"] == "known" or value["values"]) and not value["sources"]:
        return False
    if value["status"] != "known" and not isinstance(value.get("reason"), str):
        return False
    return all(isinstance(source, dict) and isinstance(source.get("path"), str)
        and isinstance(source.get("field"), str) and type(source.get("line")) is int
        and source["line"] > 0 for source in value["sources"])


def _identity(value):
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        source = value.get("source")
        candidates = [source] if isinstance(source, str) and "@" in source else []
        candidates.extend(value.get(key) for key in ("id", "name", "path"))
        return next((identity for identity in candidates if isinstance(identity, str) and identity), None)
    return None


def inventory_value(value):
    """Normalize inventory identities/provenance, never runtime configuration."""
    if not isinstance(value, dict):
        return value if isinstance(value, str) else None
    keys = ("id", "name", "path", "source", "version", "status", "type", "kind",
            "plugin_id", "server", "classification")
    result = {key: value[key] for key in keys if isinstance(value.get(key), str)}
    if isinstance(value.get("source"), dict):
        result["source"] = {key: value["source"][key] for key in ("id", "name", "path", "source")
            if isinstance(value["source"].get(key), str)}
    return result


def _excess(environment, allowed):
    environment["excess"] = []
    for name in ("plugins", "skills", "integrations", "tools"):
        for value in environment["categories"][name]["values"]:
            identity = _identity(value)
            if not identity:
                continue
            foreign = (isinstance(value, dict) and value.get("classification") == "foreign")
            if name == "plugins":
                foreign = foreign or (identity not in allowed and not (
                    isinstance(value, dict) and value.get("classification") == "builtin"))
            elif name == "integrations":
                foreign = True
            elif name == "tools":
                foreign = foreign or identity.startswith(("mcp__", "mcp_", "cua_"))
            if foreign:
                entry = {"category": name, "identity": identity,
                    "sources": environment["categories"][name]["sources"]}
                if isinstance(value, dict) and isinstance(value.get("provenance"), str):
                    entry["provenance"] = value["provenance"]
                environment["excess"].append(entry)


def _skill(name, owners):
    if ":" not in name:
        return {"name": name, "classification": "unclassified"}
    namespace = name.split(":", 1)[0]
    if namespace in owners:
        value = {"name": name, "classification": owners[namespace]}
        if owners[namespace] == "foreign":
            value["provenance"] = f"reported foreign plugin namespace {namespace}"
        return value
    return {"name": name, "classification": "foreign", "provenance": (
        "claude.ai account skill" if namespace == ACCOUNT_SKILL_NAMESPACE
        else f"namespace {namespace} not reported by any runtime plugin")}


def claude_init(environment, event, *, path, line, allowed=()):
    if event.get("type") != "system" or event.get("subtype") != "init":
        return False
    environment.update(session_id=event.get("session_id"), boundary="Claude system.init snapshot")
    cats = environment["categories"]
    for value in cats.values():
        if value["status"] == "unknown":
            value["reason"] = "Claude init does not report this inventory"
    for name, field in (("plugins", "plugins"), ("integrations", "mcp_servers"),
                        ("skills", "skills"), ("tools", "tools")):
        values = event.get(field)
        if not isinstance(values, list):
            continue
        values = [inventory_value(v) for v in values]
        if name == "plugins":
            for value in values:
                if isinstance(value, dict):
                    identity = _identity(value)
                    value["classification"] = ("builtin" if str(identity).endswith("@builtin")
                        else "tradecraft" if identity in allowed else "foreign")
        incomplete = any(not _identity(v) for v in values)
        cats[name] = category("partial" if incomplete else "known", values,
            "runtime inventory contains entries without identities" if incomplete else None,
            coordinate(path, line, field))
    # A reported plugin namespace supplies ownership for its reported skills.
    # A namespaced skill that neither tradecraft nor a reported built-in owns
    # is foreign: claude.ai account skills arrive this way. Only bare names,
    # whose origin the runtime does not report, stay unclassified.
    owners = {_identity(v).split("@", 1)[0]: v.get("classification")
        for v in cats["plugins"]["values"]
        if isinstance(v, dict) and isinstance(_identity(v), str)}
    for identity in allowed:
        owners.setdefault(str(identity).split("@", 1)[0], "tradecraft")
    cats["skills"]["values"] = [_skill(v, owners) if isinstance(v, str) else v
        for v in cats["skills"]["values"]]
    memory = event.get("memory_paths")
    if isinstance(memory, dict):
        paths = [{"kind": k, "path": v} for k, v in memory.items() if isinstance(v, str)]
        unsupported = any(v is not None and not isinstance(v, str) for v in memory.values())
        cats["memory"] = category("partial" if paths else "unknown", paths,
            "runtime memory paths contain unsupported values", coordinate(path, line, "memory_paths")) if unsupported else category(
                "known", paths, None, coordinate(path, line, "memory_paths"))
    mode = event.get("permissionMode") or event.get("permission_mode")
    if isinstance(mode, str):
        cats["permissions"] = category("partial", [{"mode": mode}],
            "runtime reports permission mode, not an OS sandbox implementation",
            coordinate(path, line, "permissionMode" if "permissionMode" in event else "permission_mode"))
    files = event.get("instruction_files")
    if isinstance(files, list):
        files = [inventory_value(v) for v in files]
        incomplete = any(not _identity(v) for v in files)
        cats["instructions"] = category("partial" if incomplete else "known", files,
            "runtime instruction inventory contains entries without identities" if incomplete else None,
            coordinate(path, line, "instruction_files"))
    environment["unclassified"] = [v for v in cats["tools"]["values"]
        if isinstance(v, str) and not v.startswith(("mcp__", "mcp_", "cua_"))]
    environment["unclassified"].extend(v for v in cats["skills"]["values"]
        if isinstance(v, dict) and v.get("classification") == "unclassified")
    _excess(environment, allowed)
    return True


# The launcher's AGENTS.md shim is <git dir or invocation temporary
# directory>/<INSTRUCTION_SHIM_PREFIX><dispatch id>/CLAUDE.md (#893 R2).
INSTRUCTION_SHIM_PREFIX = "tradecraft-instructions-"
INVOCATION_TEMPORARY_PREFIX = "tradecraft-implementer-"


def launcher_shim(path, *, shim=None, git_dir=None):
    """A recorded instruction file the launcher wrote, from this or an earlier invocation."""
    path = Path(path)
    if shim is not None and _same_path(path, Path(shim) / "CLAUDE.md"):
        return True
    if path.name != "CLAUDE.md" or not path.parent.name.startswith(INSTRUCTION_SHIM_PREFIX):
        return False
    home = path.parent.parent
    return (home.name.startswith(INVOCATION_TEMPORARY_PREFIX)
            or (git_dir is not None and _same_path(home, git_dir)))


def claude_projects(env=None):
    """The transcript root a Claude child launched with this environment writes."""
    configured = (os.environ if env is None else env).get("CLAUDE_CONFIG_DIR", "")
    return (Path(configured).expanduser() if configured else Path.home() / ".claude") / "projects"


def claude_transcript(projects, session):
    """The one native transcript for a session id, or why it cannot be named."""
    if not isinstance(session, str) or not re.fullmatch(r"[0-9a-f-]{36}", session, re.I):
        return None, "runtime returned no session identity"
    try:
        found = list(Path(projects).glob(f"*/{session}.jsonl"))
    except OSError as exc:
        return None, f"transcript directory unreadable: {exc}"
    if len(found) != 1:
        return None, (f"no transcript for session {session} under {projects}" if not found
                      else f"{len(found)} transcripts for session {session} under {projects}")
    return found[0], None


def transcript_size(projects, session):
    path, _reason = claude_transcript(projects, session)
    try:
        return path.stat().st_size if path is not None else None
    except OSError:
        return None


def _same_path(left, right):
    return os.path.normcase(os.path.normpath(str(left))) == os.path.normcase(os.path.normpath(str(right)))


def claude_instructions(environment, *, projects, session, offset, resumed, shim=None, git_dir=None):
    """Record the instruction files the runtime's transcript says it delivered.

    The session transcript's ``instructions`` attachments name each file with
    the content the runtime loaded. Nothing is inferred from launch flags, the
    files on disk or what the launcher meant to supply; only digests are kept.
    """
    cats = environment["categories"]
    if cats["instructions"]["status"] != "unknown":
        return environment  # a runtime init inventory keeps priority

    def unknown(reason):
        cats["instructions"] = category(reason="Claude transcript instructions: " + reason)
        return environment

    if resumed and offset is None:
        return unknown("the resumed transcript was not found before launch, so this "
                       "invocation's attachments cannot be told from earlier ones")
    path, reason = claude_transcript(projects, session)
    if path is None:
        return unknown(reason)
    try:
        lines = path.read_bytes().split(b"\n")
    except OSError as exc:
        return unknown(f"transcript unreadable: {exc}")
    files, sources, current, position = {}, [], False, 0
    for number, line in enumerate(lines, 1):
        start, position = position, position + len(line) + 1
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except (UnicodeError, ValueError):
            if number == len(lines):
                continue  # an interrupted final write
            return unknown(f"transcript line {number} is unparseable")
        attachment = event.get("attachment") if isinstance(event, dict) else None
        if (not isinstance(attachment, dict) or event.get("type") != "attachment"
                or attachment.get("type") != "instructions" or event.get("sessionId") != session):
            continue
        entries = attachment.get("files")
        if not isinstance(entries, list) or not all(
                isinstance(v, dict) and all(isinstance(v.get(key), str) for key in ("path", "type", "content"))
                for v in entries):
            return unknown(f"transcript line {number} has an unsupported instructions attachment")
        delivered = "this-invocation" if start >= offset else "earlier-in-session"
        current = current or delivered == "this-invocation"
        sources.append(coordinate(path, number, "attachment.files"))
        for entry in entries:
            content = entry["content"].encode("utf-8")
            # A later entry for the same path replaces an earlier one.
            files[os.path.normcase(os.path.normpath(entry["path"]))] = {
                "path": entry["path"], "runtime_type": entry["type"],
                "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content),
                "delivered": delivered,
                "launcher_shim": launcher_shim(entry["path"], shim=shim, git_dir=git_dir)}
    if not sources:
        return unknown("no instructions attachment for this session")
    if resumed:
        status, reason = "partial", "resume attachments list new or changed files; earlier entries carried"
    elif current:
        status, reason = "known", None
    else:
        return unknown("no instructions attachment from this invocation")
    cats["instructions"] = category(status, list(files.values()), reason)
    cats["instructions"]["sources"] = sources
    return environment


def skill_catalog(body):
    """Decode only native catalog paths and its own aliases, never skill contents."""
    roots = dict(re.findall(r"^- `([^`]+)` = `([^`]+)`", body, re.M))
    values = []
    for name, location in re.findall(r"^- ([^:\n]+(?::[^:\n]+)?): .*?\(file: ([^)]+)\)\s*$", body, re.M):
        alias, separator, tail = location.partition("/")
        path = roots[alias].rstrip("/\\") + "/" + tail if separator and alias in roots else location
        normalized = path.replace("\\", "/")
        match = re.search(r"/plugins/cache/([^/]+)/([^/]+)/([^/]+)/", normalized)
        value = {"name": name, "path": path, "reported_path": location}
        if match:
            marketplace, plugin, version = match.groups()
            value.update(plugin_id=f"{plugin}@{marketplace}", version=version,
                         plugin_root=normalized[:match.end()].rstrip("/"))
        elif "/skills/.system/" in normalized:
            value["classification"] = "builtin"
        values.append(value)
    return values


def codex_log(environment, path, *, session, turn, cwd, boundary=0, allowed=(), instruction_sources=None):
    """Attribute a complete world-state adjacent to this turn, never an older one."""
    cats = environment["categories"]
    try:
        raw = Path(path).read_bytes()
        lines = raw.splitlines()
        events = [json.loads(line) for line in lines]
        if not all(isinstance(e, dict) for e in events):
            raise ValueError("non-object native event")
        meta = next((e.get("payload", {}) for e in events if e.get("type") == "session_meta"), {})
        if meta.get("id", meta.get("session_id")) != session:
            raise ValueError("session metadata does not match reported identity")
        contexts = [(i, e["payload"]) for i, e in enumerate(events)
                    if e.get("type") == "turn_context" and isinstance(e.get("payload"), dict)
                    and e["payload"].get("turn_id") == turn]
        if len(contexts) != 1:
            raise ValueError("current turn context missing or ambiguous")
        index, context = contexts[0]
        if os.path.normcase(os.path.normpath(context.get("cwd", ""))) != os.path.normcase(os.path.normpath(str(cwd))):
            raise ValueError("current turn cwd does not match recipient")
        if sum(len(line) + 1 for line in lines[:index]) < boundary:
            raise ValueError("current turn precedes frozen resume boundary")
        environment.update(session_id=session, turn_id=turn, boundary="matched current-turn session log")
        permission_keys = ("approval_policy", "approvals_reviewer", "sandbox_policy", "permission_profile")
        values = {key: context[key] for key in permission_keys if key in context}
        if values:
            cats["permissions"] = category("partial", [values],
                "sandbox implementation is not reported", coordinate(path, index + 1, "payload"))
        # The supported format places a full snapshot immediately before its
        # turn_context. A reused older snapshot or undocumented delta is unknown.
        previous = events[index - 1] if index else {}
        payload = previous.get("payload", {})
        if previous.get("type") != "world_state" or payload.get("full") is not True:
            raise ValueError("current turn has no attributable full world-state snapshot")
        state = payload.get("state")
        if not isinstance(state, dict):
            raise ValueError("unsupported native world-state format")
        environment.pop("observation_error", None)
        for name in ("plugins", "skills", "integrations", "tools", "memory", "instructions"):
            if cats[name]["status"] == "unknown":
                cats[name]["reason"] = "current native report does not supply this inventory"
        source = coordinate(path, index, "payload.state")
        for key in ("apps_instructions", "plugins_instructions"):
            if isinstance(state.get(key), bool):
                environment["facts"][key] = {"value": state[key], "source": {**source, "field": "payload.state." + key}}
        host = state.get("host_skills")
        if isinstance(host, dict) and isinstance(host.get("body"), str):
            skills = skill_catalog(host["body"])
            for value in skills:
                identity = value.get("plugin_id")
                if identity:
                    value["classification"] = "tradecraft" if identity in allowed else "foreign"
            cats["skills"] = category("partial", skills, "native host-skill catalog only",
                {**source, "field": "payload.state.host_skills.body"})
            plugins = {v["plugin_id"]: {"id": v["plugin_id"], "version": v.get("version"),
                "path": v["plugin_root"], "classification": v["classification"]}
                for v in skills if v.get("plugin_id")}
            cats["plugins"] = category("partial", list(plugins.values()),
                "visible skill-providing plugins only; runtime supplies no complete inventory",
                {**source, "field": "payload.state.host_skills.body"})
        instructions = state.get("agents_md")
        if isinstance(instructions, dict) and isinstance(instructions.get("text"), str):
            environment["facts"]["instruction_context"] = {"sha256": hashlib.sha256(
                instructions["text"].encode("utf-8")).hexdigest(), "source": {**source, "field": "payload.state.agents_md.text"}}
    except (OSError, ValueError, UnicodeError, TypeError, KeyError, AttributeError) as exc:
        environment["observation_error"] = str(exc)
        for name in ("plugins", "skills", "instructions", "integrations", "tools", "memory"):
            if cats[name]["status"] == "unknown":
                cats[name]["reason"] = "native log unavailable or unattributable: " + str(exc)
    if isinstance(instruction_sources, list):
        files = [v for v in instruction_sources if isinstance(v, dict) and isinstance(v.get("path"), str)]
        if files:
            cats["instructions"] = category("partial", files, "native startup instructionSources; log file inventory unavailable",
                environment.get("instruction_sources_coordinate"))
    _excess(environment, allowed)
    return environment


def log_path(session, reported=None, *, home=None):
    """Use exact native identity, refusing ambiguous candidates."""
    if reported:
        return Path(reported)
    if not isinstance(session, str) or not re.fullmatch(r"[0-9a-f-]{36}", session, re.I):
        return None
    root = home or Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    try:
        candidates = list((root / "sessions").glob(f"*/*/*/*{session}.jsonl"))
    except OSError:
        return None
    return candidates[0] if len(candidates) == 1 else None
