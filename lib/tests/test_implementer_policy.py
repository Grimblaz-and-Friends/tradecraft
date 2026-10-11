"""Preparation tests cover exact identities, configured layers and late installs."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest

import implementer_policy as policy


def plugin(root, name="tradecraft", homepage=policy.HOMEPAGE):
    path = root / ".claude-plugin"
    path.mkdir(parents=True)
    (path / "plugin.json").write_bytes(json.dumps({"name": name, "homepage": homepage}).encode())
    return root


def test_verified_tradecraft_identity_and_root_not_lookalike_display_name(tmp_path):
    genuine = plugin(tmp_path / "genuine")
    impostor = plugin(tmp_path / "impostor", homepage="https://foreign.example")
    entries = [{"pluginId": policy.TRADECRAFT_ID, "source": {"path": str(genuine)}},
        {"pluginId": "tradecraft@foreign", "name": "tradecraft", "source": {"path": str(genuine)}},
        {"pluginId": "not-tradecraft@market", "name": "tradecraft", "source": {"path": str(impostor)}},
        {"pluginId": "remote@account", "source": {"source": "remote", "id": "remote-id"}}]
    foreign, allowed = policy.foreign_ids(entries, "codex")
    assert foreign == {"tradecraft@foreign", "not-tradecraft@market", "remote@account"}
    assert allowed == [{"id": policy.TRADECRAFT_ID, "path": str(genuine.resolve())}]


def test_claude_user_context_permissions_and_sync_are_not_overridden(tmp_path, monkeypatch):
    config = tmp_path / "native"
    config.mkdir()
    source = plugin(tmp_path / "tradecraft")
    inline = plugin(tmp_path / "inline", "foreign")
    settings = {"enabledPlugins": {"foreign@user": True}, "permissions": {"allow": ["Bash"]},
                "autoMode": {"instructions": "machine policy"}, "syncClaudeAiPlugins": True}
    (config / "settings.json").write_bytes(json.dumps(settings).encode())
    installed = config / "plugins"
    installed.mkdir()
    (installed / "installed_plugins.json").write_bytes(json.dumps({"plugins": {"disabled@cache": []}}).encode())
    synced = plugin(installed / "synced" / "outside-install-record", "synced-control")
    before = {p: p.read_bytes() for p in config.rglob("*") if p.is_file()}
    monkeypatch.setattr(policy, "discover", lambda *_a, **_k: [])
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    monkeypatch.setenv("CLAUDE_CODE_PLUGIN_DIR", str(inline))
    intent, child = policy.claude_prepare([], tmp_path, None, tmp_path, source)
    overrides = json.loads(Path(intent["settings_path"]).read_bytes())
    assert overrides == {"enabledPlugins": {"disabled@cache": False, "foreign@inline": False,
        "foreign@user": False, "synced-control@synced": False}}
    assert "CLAUDE_CODE_PLUGIN_DIR" not in child
    assert os.environ["CLAUDE_CODE_PLUGIN_DIR"] == str(inline)
    assert {p: p.read_bytes() for p in before} == before
    assert str(synced / ".claude-plugin/plugin.json") in intent["discovery_sources"]


@pytest.mark.parametrize("vendor", ["codex", "claude"])
def test_every_invocation_rediscovers_new_foreign_plugin(tmp_path, monkeypatch, vendor):
    calls = []
    def discover(*_a, **_k):
        calls.append(True)
        key = "pluginId" if vendor == "codex" else "id"
        return [{key: "new@market"}] if len(calls) > 1 else []
    monkeypatch.setattr(policy, "discover", discover)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "native"))
    source = plugin(tmp_path / "tradecraft")
    def prepare():
        if vendor == "claude":
            return policy.claude_prepare([], tmp_path, None, tmp_path, source)[0]
        return policy.codex_prepare([], tmp_path, None)
    assert prepare()["disabled_plugin_ids"] == []
    assert prepare()["disabled_plugin_ids"] == ["new@market"]


def test_exact_config_maps_disable_all_sources_preserving_unrelated_settings(tmp_path):
    root = plugin(tmp_path / "tradecraft")
    (root / ".mcp.json").write_bytes(b'{"mcpServers":{"allowed-plugin-server":{"command":"never execute"}}}')
    original = {"mcp_servers": {"user": {"command": "user", "token": "private"},
        "project.server": {"command": "project"}, "system": {}, "desktop": {}},
        "plugins": {"foreign.plugin@market": {"enabled": True}, policy.TRADECRAFT_ID: {"enabled": True}},
        "apps": {"mail": {"enabled": True}}, "sandbox_workspace_write": {"network_access": True},
        "shell_environment_policy": {"set": {"PYTEST_DEBUG_TEMPROOT": "/owner/temp"}}}
    before = json.dumps(original)
    intent = {"allowed_plugins": [{"id": policy.TRADECRAFT_ID, "path": str(root)}]}
    overrides = policy.restriction_config(original, intent)
    assert overrides["mcp_servers"] == {name: {"enabled": False, "command": "tradecraft-disabled-mcp-server"} for name in
        ["user", "project.server", "system", "desktop", "allowed-plugin-server"]}
    assert overrides["plugins"] == {"foreign.plugin@market": {"enabled": False}}
    assert overrides["apps._default.enabled"] is False
    assert json.dumps(original) == before
    assert "private" not in json.dumps(overrides)


def test_preparation_failure_retains_cause_without_unrestricted_substitute(tmp_path, monkeypatch):
    root = plugin(tmp_path / "tradecraft")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "native"))
    def broken(*_a, **_k):
        raise policy.PreparationError("native discovery denied")
    monkeypatch.setattr(policy, "discover", broken)
    with pytest.raises(policy.PreparationError, match="native discovery denied"):
        policy.claude_prepare([], tmp_path, None, tmp_path, root)
