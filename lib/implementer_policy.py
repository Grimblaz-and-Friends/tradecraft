"""Invocation-owned targeted exclusions without replacing operating settings."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from seat_process import run_process

TRADECRAFT_ID = "tradecraft@tradecraft"
HOMEPAGE = "https://github.com/Grimblaz-and-Friends/tradecraft"
FEATURES = ("apps", "computer_use", "browser_use", "browser_use_external", "in_app_browser")


class PreparationError(OSError):
    """The requested isolation could not be prepared; no unrestricted fallback."""


def _read(path, *, optional=False):
    try:
        return json.loads(path.read_bytes())
    except FileNotFoundError:
        if optional:
            return {}
        raise
    except (UnicodeError, ValueError) as exc:
        raise PreparationError(f"invalid plugin metadata at {path}: {exc}") from exc


def verified_root(root):
    try:
        manifest = _read(Path(root) / ".claude-plugin" / "plugin.json")
    except (OSError, ValueError):
        return False
    return isinstance(manifest, dict) and manifest.get("name") == "tradecraft" and manifest.get("homepage") == HOMEPAGE


def discover(vendor, executable, cwd, deadline, *, env=None):
    result = run_process([*executable, "plugin", "list", "--json"], input=b"", cwd=cwd,
                         timeout=deadline.probe(), env=env, cleanup_deadline=deadline.cleanup_end)
    if result.returncode:
        raise PreparationError(f"{vendor} plugin discovery exited {result.returncode}: " + result.stderr.decode("utf-8", "replace")[:1000])
    try:
        value = json.loads(result.stdout)
    except (UnicodeError, ValueError) as exc:
        raise PreparationError(f"{vendor} plugin discovery returned invalid JSON") from exc
    entries = value if vendor == "claude" else value.get("installed") if isinstance(value, dict) else None
    if not isinstance(entries, list) or not all(isinstance(v, dict) for v in entries):
        raise PreparationError(f"{vendor} plugin discovery returned an unsupported inventory")
    return entries


def foreign_ids(entries, vendor):
    foreign, allowed = set(), []
    for entry in entries:
        identity = entry.get("id" if vendor == "claude" else "pluginId")
        if not isinstance(identity, str) or not identity:
            raise PreparationError("plugin discovery entry lacks exact identity")
        source = entry.get("source") or {}
        root = entry.get("installPath") if vendor == "claude" else source.get("path")
        if identity == TRADECRAFT_ID and root and verified_root(root):
            allowed.append({"id": identity, "path": str(Path(root).resolve())})
        elif vendor == "claude" and identity.endswith("@builtin"):
            continue
        else:
            foreign.add(identity)
    return foreign, allowed


def claude_prepare(executable, cwd, deadline, temporary, plugin_root, *, env=None):
    child = dict(os.environ if env is None else env)
    if not verified_root(plugin_root):
        raise PreparationError("explicit tradecraft plugin directory failed identity verification")
    entries = discover("claude", executable, cwd, deadline, env=child)
    ids, allowed = foreign_ids(entries, "claude")
    config = Path(child.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    if not config.is_absolute():
        raise PreparationError("Claude native configuration root must be absolute")
    cache = Path(child.get("CLAUDE_CODE_PLUGIN_CACHE_DIR") or config / "plugins")
    paths = [config / "settings.json", cache / "installed_plugins.json"]
    for path in paths:
        value = _read(path, optional=True)
        if not isinstance(value, dict):
            raise PreparationError(f"unsupported plugin metadata at {path}")
        declarations = value.get("enabledPlugins", {})
        installs = value.get("plugins", {})
        for identity in (*declarations, *installs):
            if identity != TRADECRAFT_ID and not identity.endswith("@builtin"):
                ids.add(identity)
    # Supplemental origin manifests supply identities even without install
    # records. Read metadata only; no plugin hook/mod executes in preparation.
    for origin in (cache / "synced", config / "skills"):
        if not origin.exists():
            continue
        for manifest in origin.glob("**/.claude-plugin/plugin.json"):
            value = _read(manifest)
            if isinstance(value, dict) and isinstance(value.get("name"), str):
                name = value["name"]
                suffix = "@synced" if origin.name == "synced" else "@skills-dir"
                ids.add(name + suffix)
                paths.append(manifest)
    # Inherited inline directories are session inputs, not owner config. Their
    # names are disabled as well as suppressing the child-only sideload source.
    for key in ("CLAUDE_CODE_PLUGIN_DIR", "CLAUDE_CODE_PLUGIN_DIRS"):
        supplied = child.pop(key, None)
        if supplied:
            for directory in supplied.split(os.pathsep):
                path = Path(directory) / ".claude-plugin/plugin.json"
                value = _read(path)
                if isinstance(value, dict) and isinstance(value.get("name"), str):
                    ids.add(value["name"] + "@inline")
                    paths.append(path)
    override = Path(temporary) / "claude-settings.json"
    data = (json.dumps({"enabledPlugins": {identity: False for identity in sorted(ids)}},
                       ensure_ascii=True) + "\n").encode("utf-8")
    override.write_bytes(data)
    if os.name != "nt":
        override.chmod(0o600)
    return {"disabled_plugin_ids": sorted(ids), "allowed_plugins": [
        *allowed, {"id": "tradecraft@inline", "path": str(plugin_root)}],
        "discovery_sources": ["claude plugin list --json", *map(str, paths)],
        "override_sha256": hashlib.sha256(data).hexdigest(),
        "settings_path": str(override)}, child


def codex_prepare(executable, cwd, deadline, *, env=None):
    entries = discover("codex", executable, cwd, deadline, env=env)
    ids, allowed = foreign_ids(entries, "codex")
    return {"disabled_plugin_ids": sorted(ids), "allowed_plugins": allowed,
            "discovery_sources": ["codex plugin list --json"]}


def restriction_config(config, intent):
    """Exact dictionary keys survive dots/quotes; empty tables do not override."""
    servers = set(config.get("mcp_servers", {}))
    plugins = set(config.get("plugins", {})) - {v["id"] for v in intent["allowed_plugins"]}
    for allowed in intent["allowed_plugins"]:
        root = Path(allowed["path"])
        for path in (root / ".mcp.json",):
            value = _read(path, optional=True)
            if isinstance(value, dict):
                servers.update(value.get("mcpServers", value))
        manifest = _read(root / ".claude-plugin" / "plugin.json", optional=True)
        if isinstance(manifest, dict) and isinstance(manifest.get("mcpServers"), dict):
            servers.update(manifest["mcpServers"])
    overrides = {"apps._default.enabled": False}
    if servers:
        # Native thread config replaces each transport table. A disabled entry
        # still needs a valid transport; use an inert command instead of copying
        # owner commands, environment, URLs or credentials into the transcript.
        overrides["mcp_servers"] = {name: {"enabled": False,
            "command": "tradecraft-disabled-mcp-server"} for name in sorted(servers)}
    if plugins:
        overrides["plugins"] = {name: {"enabled": False} for name in sorted(plugins)}
    intent["disabled_mcp_servers"] = sorted(servers)
    intent["disabled_configured_plugins"] = sorted(plugins)
    intent["restriction_sha256"] = hashlib.sha256(json.dumps(overrides, sort_keys=True).encode()).hexdigest()
    return overrides
