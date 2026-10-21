"""The catch-up consumer scenario, driven end to end through the command line (#910 C15's route)."""
import json
import os
from pathlib import Path
import subprocess
import sys

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
import version_fixture


def cli(*arguments, env):
    result = subprocess.run([sys.executable, str(TESTS / "version_fixture.py"), *arguments],
                            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def git(cwd, *arguments, env):
    result = subprocess.run(["git", "-C", str(cwd), *arguments], env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert result.returncode == 0, result.stderr
    return result.stdout.decode("utf-8").strip()


def test_cli_catch_up_keeps_base_version_and_readiness_refuses_a_moved_one(tmp_path):
    # Stand in for the person's own home: every consumer command must leave it untouched.
    real_home = tmp_path / "real-home"
    real_home.mkdir()
    env = {**os.environ, "USERPROFILE": str(real_home), "HOME": str(real_home)}
    root = tmp_path / "s"
    setup = cli("setup", str(root), "--scenario", "catch-up", env=env)
    layout = version_fixture.catch_up_layout(root)
    assert setup["holder_session_id"] == version_fixture.CATCH_UP_HOLDER_SESSION

    recommended = cli("inspect", str(root), env=env)
    assert (recommended["stage"], recommended["reason"]) == ("catch-up", "strict-base-behind")

    landed = cli("catch-up", str(root), env=env)
    assert landed["status"] == "holder-owned" and landed["landing_error"] == ""
    decision = landed["version_decision"]
    assert (decision["owed"], decision["base_value"], decision["value"]) == (False, "1.4.0", None)
    assert decision["reason"] == "not owed: field already holds the base's 1.4.0"
    assert landed["version_adjustment"] is None
    assert landed["next"]["version_obligation"]["status"] == "not-required"
    head = git(layout["implementation"], "rev-parse", "HEAD", env=env)
    assert git(layout["origin"], "rev-parse", f"refs/heads/{version_fixture.CATCH_UP_BRANCH}", env=env) == head
    assert json.loads((layout["implementation"] / "version.json").read_bytes())["version"] == "1.4.0"

    # A builder bumps the field unasked on a change that owes no version.
    target = layout["implementation"] / "version.json"
    target.write_bytes(target.read_bytes().replace(b'"1.4.0"', b'"1.5.0"'))
    git(layout["implementation"], "commit", "-am", "Bump the version unasked", env=env)
    git(layout["implementation"], "push", env=env)
    refused = cli("ready-reviewers", str(root), env=env)
    assert (refused["stage"], refused["reason"]) == ("ready-reviewers", "version-obligation-blocked")
    assert refused["version_obligation"]["unowed"] is True
    assert "no version is owed" in refused["detail"] and "restore 1.4.0" in refused["detail"]
    assert cli("effects", str(root), env=env) == {"effects": []}

    # The entrance's registry and records landed in the scenario's home, never the person's.
    assert (layout["home"] / ".tradecraft" / "implementation-worktrees.json").is_file()
    assert list(real_home.iterdir()) == []
