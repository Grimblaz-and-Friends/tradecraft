"""Authored inventories contradict intent and exercise coverage/attribution."""
import hashlib
import json
from pathlib import Path

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import implementer_environment as env

SESSION = "0199a213-81c0-7800-8aa1-bbab2a035a53"
TURN = "0199a214-81c0-7800-8aa1-bbab2a035a53"


def test_claude_actual_snapshot_names_excess_and_not_requested_values():
    result = env.unknown("not reported", vendor="claude")
    init = {"type": "system", "subtype": "init", "session_id": SESSION,
        "plugins": [{"name": "tradecraft@inline"}, {"name": "foreign@market"}, {"name": "native@builtin"}],
        "mcp_servers": [{"name": "desktop", "status": "connected"}],
        "tools": ["Read", "mcp__desktop__click", "Unfamiliar"],
        "skills": ["tradecraft:charter", "foreign:send"], "memory_paths": {"auto": "/native/memory"},
        "permissionMode": "default"}
    assert env.claude_init(result, init, path="stdout.log", line=7, allowed=["tradecraft@inline"])
    assert result["categories"]["permissions"]["values"] == [{"mode": "default"}]
    assert result["categories"]["memory"]["values"] == [{"kind": "auto", "path": "/native/memory"}]
    assert result["categories"]["instructions"]["status"] == "unknown"
    assert {v["identity"] for v in result["excess"]} == {"foreign@market", "foreign:send", "desktop", "mcp__desktop__click"}
    assert result["unclassified"] == ["Read", "Unfamiliar"]
    assert result["categories"]["plugins"]["sources"] == [{"path": "stdout.log", "line": 7, "field": "plugins"}]
    before = json.dumps(result)
    assert not env.claude_init(result, {"type": "result", "is_error": True}, path="stdout.log", line=8)
    assert json.dumps(result) == before


@pytest.mark.parametrize("field", ["plugins", "mcp_servers", "tools", "skills"])
def test_claude_missing_inventory_is_unknown_but_explicit_empty_is_known(field):
    result = env.unknown("missing")
    init = {"type": "system", "subtype": "init"}
    env.claude_init(result, init, path="out", line=1)
    name = {"mcp_servers": "integrations"}.get(field, field)
    assert result["categories"][name]["status"] == "unknown"
    init[field] = []
    env.claude_init(result, init, path="out", line=2)
    assert result["categories"][name]["status"] == "known"
    assert result["categories"][name]["values"] == []


def test_normalized_inventory_does_not_copy_credentials_or_full_settings():
    result = env.unknown("missing")
    init = {"type": "system", "subtype": "init", "plugins": [{"name": "foreign", "source": "foreign@market",
        "version": "1", "credentials": "private-token", "settings": {"secret": "hidden"}}],
        "mcp_servers": [{"name": "server", "status": "connected", "env": {"TOKEN": "private-token"}}]}
    env.claude_init(result, init, path="native", line=1)
    text = json.dumps(result)
    assert "private-token" not in text and "hidden" not in text
    assert result["categories"]["plugins"]["values"][0]["source"] == "foreign@market"


@pytest.mark.parametrize("field", ["id", "name", "path", "version", "status", "type", "kind",
                                  "plugin_id", "server", "classification", "source"])
def test_unsupported_identity_payload_cannot_smuggle_configuration_into_inventory(field):
    result = env.unknown("missing")
    env.claude_init(result, {"type": "system", "subtype": "init", "tools": [
        {field: {"credentials": "private-token", "settings": {"secret": "hidden"}}},
        [{"credentials": "private-token"}], "mcp__desktop__click"]}, path="native", line=1)
    text = json.dumps(result)
    assert "private-token" not in text and "hidden" not in text
    assert result["categories"]["tools"]["status"] == "partial"
    assert result["excess"][0]["identity"] == "mcp__desktop__click"


def test_unsupported_inventory_entries_and_memory_shape_cannot_certify_empty():
    result = env.unknown("missing")
    env.claude_init(result, {"type": "system", "subtype": "init", "plugins": [{}],
        "memory_paths": {"auto": {"unsupported": True}}}, path="native", line=1)
    assert result["categories"]["plugins"]["status"] == "partial"
    assert result["categories"]["memory"]["status"] == "unknown"


@pytest.mark.parametrize("identity", [None, True, 7, [], {"unsupported": True}, ""])
def test_malformed_tool_identity_is_partial_observation_without_a_callback_error(identity):
    result = env.unknown("not reported")
    env.claude_init(result, {"type": "system", "subtype": "init",
        "tools": [{"id": identity}, "mcp__desktop__click"],
        "instruction_files": [{}]}, path="native.stdout", line=1)
    assert result["categories"]["tools"]["status"] == "partial"
    assert result["categories"]["instructions"]["status"] == "partial"
    assert result["excess"][0]["identity"] == "mcp__desktop__click"


def log(tmp_path, *, full=True, turn=TURN, cwd=None, extra=()):
    path = tmp_path / "rollout.jsonl"
    body = """### Skill roots
- `r0` = `/owner/.codex/skills/.system`
- `r1` = `/owner/.codex/plugins/cache/tradecraft/tradecraft/0.194.0/skills`
- `r2` = `/owner/.codex/plugins/cache/foreign/drive/1.0/skills`
### Available skills
- imagegen: Native skill. (file: r0/imagegen/SKILL.md)
- tradecraft:charter: Practice skill. (file: r1/charter/SKILL.md)
- drive:send: Account skill. (file: r2/send/SKILL.md)
"""
    events = [{"type": "session_meta", "payload": {"id": SESSION, "cwd": "/old/root"}},
        *extra,
        {"type": "world_state", "payload": {"full": full, "state": {"host_skills": {"body": body},
            "agents_md": {"text": "private global text", "directory": str(tmp_path)},
            "apps_instructions": False, "plugins_instructions": False}}},
        {"type": "turn_context", "payload": {"turn_id": turn, "cwd": str(cwd or tmp_path),
            "approval_policy": "on-request", "approvals_reviewer": "auto_review",
            "sandbox_policy": {"type": "workspace-write", "network_access": True}}}]
    path.write_bytes(b"\n".join(json.dumps(e).encode() for e in events) + b"\n")
    return path


def test_codex_native_catalog_is_partial_and_proves_foreign_skill(tmp_path):
    path = log(tmp_path)
    result = env.unknown("missing", vendor="codex")
    result["instruction_sources_coordinate"] = {"path": "stdout.log", "line": 3, "field": "result.instructionSources"}
    env.codex_log(result, path, session=SESSION, turn=TURN, cwd=tmp_path,
        allowed=["tradecraft@tradecraft"], instruction_sources=[{"path": "/owner/.codex/AGENTS.md"}])
    assert result["categories"]["plugins"]["status"] == "partial"
    assert result["categories"]["skills"]["values"][2]["path"] == "/owner/.codex/plugins/cache/foreign/drive/1.0/skills/send/SKILL.md"
    assert {v["identity"] for v in result["excess"]} == {"drive@foreign", "drive:send"}
    assert result["categories"]["integrations"]["status"] == "unknown"
    assert result["categories"]["tools"]["status"] == "unknown"
    assert result["categories"]["memory"]["status"] == "unknown"
    assert result["categories"]["instructions"]["values"] == [{"path": "/owner/.codex/AGENTS.md"}]
    assert result["facts"]["instruction_context"]["sha256"] == hashlib.sha256(b"private global text").hexdigest()
    assert "private global text" not in json.dumps(result)
    assert result["facts"]["apps_instructions"]["value"] is False


@pytest.mark.parametrize("problem", ["session", "turn", "cwd", "delta", "truncated", "boundary", "missing", "old"])
def test_codex_unattributable_evidence_never_certifies_empty(tmp_path, problem):
    path = log(tmp_path, full=problem != "delta")
    session, turn, cwd, boundary = SESSION, TURN, tmp_path, 0
    if problem == "session":
        session = "0299a213-81c0-7800-8aa1-bbab2a035a53"
    elif problem == "turn":
        turn = "old-turn"
    elif problem == "cwd":
        cwd = tmp_path / "sibling"
    elif problem == "truncated":
        path.write_bytes(path.read_bytes() + b'{"payload":')
    elif problem == "boundary":
        boundary = path.stat().st_size + 1
    elif problem == "missing":
        path.unlink()
    elif problem == "old":
        path.write_bytes(path.read_bytes() + json.dumps({"type": "turn_context",
            "payload": {"turn_id": "new-turn", "cwd": str(tmp_path)}}).encode() + b"\n")
        turn = "new-turn"
    result = env.unknown("missing")
    env.codex_log(result, path, session=session, turn=turn, cwd=cwd, boundary=boundary)
    for name in ("plugins", "skills", "integrations", "tools", "memory", "instructions"):
        assert result["categories"][name]["status"] == "unknown"
        assert result["categories"][name]["reason"]
    assert not result["excess"]


def test_log_selection_never_chooses_neighboring_latest(tmp_path):
    folder = tmp_path / "sessions/2026/10/10"
    folder.mkdir(parents=True)
    own = folder / ("rollout-" + SESSION + ".jsonl")
    own.touch()
    (folder / "rollout-other-session.jsonl").touch()
    assert env.log_path(SESSION, home=tmp_path) == own
    (folder / ("other-" + SESSION + ".jsonl")).touch()
    assert env.log_path(SESSION, home=tmp_path) is None


def test_unowned_namespaced_skills_are_excess_and_bare_names_stay_unclassified():
    result = env.unknown("not reported", vendor="claude")
    init = {"type": "system", "subtype": "init",
        "plugins": [{"name": "tradecraft@inline"}, {"name": "agents-md@builtin"}, {"name": "foreign@market"}],
        "skills": ["tradecraft:charter", "agents-md:write", "foreign:send", "anthropic-skills:import-memory",
                   "other-origin:tool", "dataviz"]}
    env.claude_init(result, init, path="stdout.log", line=3, allowed=["tradecraft@inline"])
    skills = {v["name"]: v for v in result["categories"]["skills"]["values"]}
    assert skills["tradecraft:charter"]["classification"] == "tradecraft"
    assert skills["agents-md:write"]["classification"] == "builtin"
    assert skills["dataviz"]["classification"] == "unclassified"
    excess = {v["identity"]: v.get("provenance") for v in result["excess"] if v["category"] == "skills"}
    assert excess == {"foreign:send": "reported foreign plugin namespace foreign",
        "anthropic-skills:import-memory": "claude.ai account skill",
        "other-origin:tool": "namespace other-origin not reported by any runtime plugin"}
    assert [v["name"] for v in result["unclassified"] if isinstance(v, dict)] == ["dataviz"]
    assert result["unclassified_note"] == env.UNCLASSIFIED_NOTE and "not clean" in env.UNCLASSIFIED_NOTE


def test_allowed_identity_owns_its_namespace_when_init_omits_the_plugin():
    result = env.unknown("not reported", vendor="claude")
    env.claude_init(result, {"type": "system", "subtype": "init", "plugins": [],
        "skills": ["tradecraft:charter"]}, path="stdout.log", line=1, allowed=["tradecraft@inline"])
    assert result["excess"] == []
    assert result["categories"]["skills"]["values"][0]["classification"] == "tradecraft"
