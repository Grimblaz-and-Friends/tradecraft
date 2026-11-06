"""One-time cloud setup: the create body and its read-back verification."""
import argparse
import json
from pathlib import Path
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import cloud_build as cloud  # noqa: E402
import cloud_setup as setup  # noqa: E402

REPO, PRACTICE, INSTALLED = "Owner/product", "Grimblaz-and-Friends/tradecraft", "1" * 40


def readback(**changes):
    """A read-back in the shape `RemoteTrigger get` returns."""
    sent = setup.create_body(REPO, "env_1", PRACTICE, "cloud-practice")
    ccr = json.loads(json.dumps(sent["job_config"]["ccr"]))
    ccr["session_context"].update(model="claude-opus-5-5", effort_level="high",
                                  allowed_tools=["preset:default", "Bash"])
    flat = [{"type": "git_repository", "sparse_checkout_paths": [],
             "sparse_checkout_exclude_patterns": [], **row["git_repository"]}
            for row in ccr["session_context"]["sources"]]
    value = {"id": "trig_1", "name": sent["name"], "cron_expression": "", "mcp_connections": [],
             "api_token_hint": "", "enabled": True, "job_config": {"ccr": ccr},
             "session_request": {"config": {"mcp_servers": [], "model": "claude-opus-5-5",
                                            "effort_level": "high", "disallowed_tools": list(cloud.ROUTINE_DISALLOWED_TOOLS),
                                            "sources": flat}}}
    for path, item in changes.items():
        target = value
        keys = path.split(".")
        for key in keys[:-1]:
            target = target[int(key)] if key.isdigit() else target[key]
        last = keys[-1]
        if item is DROP:
            target.pop(last)
        else:
            target[last] = item
    return value


DROP = object()
CONTEXT = "job_config.ccr.session_context"


class Pins:
    def __init__(self, exists):
        self.exists, self.writes = exists, []

    def github(self, method, path, body=None):
        if method == "GET":
            return (200, {}) if self.exists else (404, {})
        self.writes.append((method, path, body))
        return 201, {}


@pytest.fixture
def machine(tmp_path):
    plugin = tmp_path / "plugin"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "tradecraft", "version": "0.206.0"}))
    install = tmp_path / "installed.json"
    install.write_text(json.dumps({"plugins": {"tradecraft@tradecraft": [
        {"scope": "user", "installPath": "x", "version": "0.206.0", "gitCommitSha": INSTALLED}]}}))
    token = tmp_path / "t.token"
    token.write_text("sk-ant-secret\n")
    return {"home": tmp_path / "home", "plugin": plugin, "install": install, "token": token, "tmp": tmp_path}


def verify(machine, value, *, phase="complete", pins=None, saved_tool_output=False):
    path = machine["tmp"] / "readback.json"
    path.write_text(("HTTP 200\n" if saved_tool_output else "") + json.dumps(value))
    args = argparse.Namespace(repo=REPO, environment="env_1", practice_repo=PRACTICE,
                              practice_branch="cloud-practice", readback=str(path), phase=phase,
                              token_file=str(machine["token"]), routine_id=None)
    return setup.verify(args, home=machine["home"], transport=pins or Pins(False),
                        plugin=machine["plugin"], install_path=machine["install"])


def test_body_carries_what_setup_requires():
    body = setup.create_body(REPO, "env_1", PRACTICE, "cloud-practice")
    context = body["job_config"]["ccr"]["session_context"]
    assert body["clear_mcp_connections"] is True
    assert context["disallowed_tools"] == ["PushNotification", "Monitor", "ScheduleWakeup", "CronCreate", "Workflow"]
    assert body["cron_expression"] == "" and "run_once_at" not in body
    assert context["sources"] == [
        {"git_repository": {"url": f"https://github.com/{REPO}"}},
        {"git_repository": {"url": f"https://github.com/{PRACTICE}", "revision": "cloud-practice",
                            "sparse_checkout_exclude_patterns": ["/CLAUDE.md", "/AGENTS.md", "/.claude/"]}}]
    prompt = body["job_config"]["ccr"]["events"][0]["data"]["message"]["content"]
    assert "/home/user/tradecraft/hooks/cloud.py check" in prompt
    assert body == setup.create_body(REPO, "env_1", PRACTICE, "cloud-practice")  # stable to re-verify


def test_a_clean_complete_writes_the_entry_and_creates_the_pin(machine, capsys):
    pins = Pins(False)
    assert verify(machine, readback(), pins=pins) == 0
    record = cloud.read_record(cloud.record_path(machine["home"]))
    assert record["repositories"][REPO]["routine_id"] == "trig_1"
    assert pins.writes == [("POST", f"repos/{PRACTICE}/git/refs",
                            {"ref": "refs/heads/cloud-practice", "sha": INSTALLED})]
    kept = json.loads((machine["home"] / ".tradecraft" / "cloud-setup" / "Owner__product.json").read_text())
    assert kept["diff"] == [] and kept["readback"]["mcp_connections"] == []
    existing = Pins(True)
    assert verify(machine, readback(), pins=existing, saved_tool_output=True) == 0 and existing.writes == []
    assert "sk-ant-secret" not in capsys.readouterr().out


@pytest.mark.parametrize("change, field", [
    ({"mcp_connections": [{"name": "slack"}]}, "connectors"),
    ({"session_request.config.mcp_servers": [{"name": "slack"}]}, "connectors"),
    ({"cron_expression": "0 * * * *"}, "cron_expression"),
    ({CONTEXT + ".disallowed_tools": []}, "disallowed_tools"),
    ({CONTEXT + ".disallowed_tools": ["PushNotification"]}, "disallowed_tools"),
    ({CONTEXT + ".effort_level": "medium"}, "effort_level"),
    ({CONTEXT + ".effort_level": DROP}, "effort_level"),
    ({CONTEXT + ".model": "claude-sonnet-5"}, "model"),
    ({CONTEXT + ".sources.1.git_repository.sparse_checkout_exclude_patterns": DROP}, "sources"),
    ({CONTEXT + ".sources.1.git_repository.revision": "main"}, "sources"),
    ({CONTEXT + ".sources": [{"git_repository": {"url": f"https://github.com/{REPO}"}}]}, "sources"),
    ({"job_config.ccr.environment_id": "env_2"}, "environment_id"),
    ({"job_config.ccr.events.0.data.message.content": "changed"}, "prompt"),
])
def test_any_differing_field_fails_and_writes_no_entry(machine, capsys, change, field):
    assert verify(machine, readback(**change)) == 1
    assert f"setup FAILED: {field}" in capsys.readouterr().err
    assert not cloud.record_path(machine["home"]).exists()


def test_the_practice_repository_is_refused():
    for repo in (PRACTICE, "Someone/tradecraft"):
        with pytest.raises(setup.SetupError, match="practice's own repository"):
            setup.create_body(repo, "env", PRACTICE, "cloud-practice")
    assert setup.main(["body", "--repo", PRACTICE, "--environment", "env"]) == 1


def test_profile_prints_the_launch_default_the_owner_sets(capsys):
    assert setup.main(["profile"]) == 0
    model, effort = cloud.builder_profile()
    environment = "".join(f"environment: {name}={value}\n" for name, value in cloud.CLOUD_ENVIRONMENT.items())
    assert capsys.readouterr().out == f"model: {model}\neffort: {effort}\n" + environment
    assert "environment: CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1\n" in environment


def test_setup_binds_the_saved_routine_id_to_the_read_back(machine, capsys):
    path = machine["tmp"] / "readback.json"
    path.write_text(json.dumps(readback()))
    args = argparse.Namespace(repo=REPO, environment="env_1", practice_repo=PRACTICE,
                              practice_branch="cloud-practice", readback=str(path), phase="complete",
                              token_file=str(machine["token"]), routine_id="trig_other")
    assert setup.verify(args, home=machine["home"], transport=Pins(False), plugin=machine["plugin"],
                        install_path=machine["install"]) == 1
    assert "setup FAILED: routine id" in capsys.readouterr().err
    assert not cloud.record_path(machine["home"]).exists()
