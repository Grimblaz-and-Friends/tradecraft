"""One-time cloud setup: the create body and its read-back verification (#938 row 3)."""
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
    value = setup.create_body(REPO, "env_1", PRACTICE, "cloud-practice")
    value.pop("clear_mcp_connections")
    value.update(id="trig_1", model="claude-opus-5-5", effort_level="high", mcp_connections=[],
                 triggers=[{"type": "api"}])
    value.update(changes)
    return value


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


def verify(machine, value, *, phase="complete", pins=None):
    path = machine["tmp"] / "readback.json"
    path.write_text(json.dumps(value))
    args = argparse.Namespace(repo=REPO, environment="env_1", practice_repo=PRACTICE,
                              practice_branch="cloud-practice", readback=str(path), phase=phase,
                              token_file=str(machine["token"]), routine_id=None)
    return setup.verify(args, home=machine["home"], transport=pins or Pins(False),
                        plugin=machine["plugin"], install_path=machine["install"])


def test_ac_3_1_body_carries_what_row_3_requires():
    body = setup.create_body(REPO, "env_1", PRACTICE, "cloud-practice")
    assert body["clear_mcp_connections"] is True and "PushNotification" in body["disallowed_tools"]
    assert "cron_expression" not in body and "run_once_at" not in body
    assert body["sources"][1] == {"repository": PRACTICE, "revision": "cloud-practice",
                                  "sparse_checkout_exclude_patterns": ["/CLAUDE.md", "/AGENTS.md", "/.claude/"]}
    assert "/home/user/tradecraft/hooks/cloud.py check" in body["prompt"]


def test_ac_3_1_and_5_5_a_clean_complete_writes_the_entry_and_creates_the_pin(machine, capsys):
    pins = Pins(False)
    assert verify(machine, readback(), pins=pins) == 0
    record = cloud.read_record(cloud.record_path(machine["home"]))
    assert record["repositories"][REPO]["routine_id"] == "trig_1"
    assert pins.writes == [("POST", f"repos/{PRACTICE}/git/refs",
                            {"ref": "refs/heads/cloud-practice", "sha": INSTALLED})]
    kept = json.loads((machine["home"] / ".tradecraft" / "cloud-setup" / "Owner__product.json").read_text())
    assert kept["diff"] == [] and kept["readback"]["mcp_connections"] == []
    existing = Pins(True)
    assert verify(machine, readback(), pins=existing) == 0 and existing.writes == []
    assert "sk-ant-secret" not in capsys.readouterr().out


@pytest.mark.parametrize("change, field", [
    ({"mcp_connections": [{"name": "slack"}]}, "connectors"),
    ({"cron_expression": "0 * * * *"}, "cron_expression"),
    ({"disallowed_tools": []}, "disallowed_tools"),
    ({"effort_level": "medium"}, "effort_level"),
    ({"model": "claude-sonnet-5"}, "model"),
    ({"triggers": []}, "trigger"),
    ({"sources": [{"repository": REPO}, {"repository": PRACTICE, "revision": "cloud-practice"}]}, "sources"),
])
def test_ac_3_2_any_differing_field_fails_and_writes_no_entry(machine, capsys, change, field):
    assert verify(machine, readback(**change)) == 1
    assert f"setup FAILED: {field}" in capsys.readouterr().err
    assert not cloud.record_path(machine["home"]).exists()


def test_ac_10_1_the_practice_repository_is_refused():
    for repo in (PRACTICE, "Someone/tradecraft"):
        with pytest.raises(setup.SetupError, match="row 10"):
            setup.create_body(repo, "env", PRACTICE, "cloud-practice")
    assert setup.main(["body", "--repo", PRACTICE, "--environment", "env"]) == 1
