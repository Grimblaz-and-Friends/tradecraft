"""Attempt-local observations; requests never certify runtime holdings."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

CATEGORIES = ("plugins", "integrations", "tools", "skills", "instructions", "memory", "permissions")


def category(status="unknown", values=None, reason="runtime did not report this inventory", source=None):
    return {"status": status, "values": [] if values is None else values,
            "reason": reason, "sources": [source] if source else []}


def unknown(reason, *, vendor=None, version=None):
    return {"schema_version": 1, "vendor": vendor, "runtime_version": version,
            "session_id": None, "turn_id": None, "boundary": "unobserved",
            "categories": {name: category(reason=reason) for name in CATEGORIES},
            "facts": {}, "excess": [], "unclassified": []}


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
                environment["excess"].append({"category": name, "identity": identity,
                    "sources": environment["categories"][name]["sources"]})


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
    # Other namespaces stay unclassified; a familiar-looking name is no proof
    # that the runtime owns it.
    owners = {_identity(v).split("@", 1)[0]: v.get("classification")
        for v in cats["plugins"]["values"]
        if isinstance(v, dict) and isinstance(_identity(v), str)}
    cats["skills"]["values"] = [{"name": v, "classification": owners.get(v.split(":", 1)[0], "unclassified")}
        if isinstance(v, str) else v for v in cats["skills"]["values"]]
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
