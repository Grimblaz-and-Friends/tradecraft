"""The GitHub write bound in composed prompts, the allowance command, grants and the report."""
from __future__ import annotations

import re
import subprocess

import pytest

from test_work import (AFFIRMED, ARTIFACT, DAEMON_RULES, HOLDER, NOT_PROTECTED, PRODUCER,
                       PROTECTION_ENDPOINT, RULES_ENDPOINT, WOULD, ThreadTransport, _disposition_prompt,
                       _thread, _thread_page, git, state, work)
import github_allowance
import github_write_guard as guard

BRANCH = "tradecraft/894-ab"


def _bound_tree(tmp_path):
    tree = tmp_path / "bound-tree"
    tree.mkdir()
    git(tree, "init", "-q", "-b", BRANCH)
    git(tree, "remote", "add", "origin", "https://github.com/example/product.git")
    git(tree, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "x")
    git(tree, "config", f"branch.{BRANCH}.remote", "origin")
    git(tree, "config", f"branch.{BRANCH}.merge", f"refs/heads/{BRANCH}")
    git(tree, "update-ref", f"refs/remotes/origin/{BRANCH}", "HEAD")
    return tree


def _prompt_commands(prompt):
    """Every command a composed prompt gives: a line or code span opening with gh or git."""
    found = [line.strip() for line in prompt.splitlines() if re.match(r"^(gh|git) ", line.strip())]
    found.extend(re.findall(r"`((?:gh|git) [^`]+)`", prompt))
    return found


def test_ac5_every_command_a_composed_prompt_gives_passes_its_allowance(tmp_path, monkeypatch):
    tree = _bound_tree(tmp_path)
    monkeypatch.setattr(guard, "thread_owner", lambda thread: ("example/product", 7))
    known = ThreadTransport({RULES_ENDPOINT: DAEMON_RULES, PROTECTION_ENDPOINT: NOT_PROTECTED},
                            pages=[_thread_page([_thread("PRRT_x", 701, "reviewer-fixture")])])
    unknown = ThreadTransport({RULES_ENDPOINT: DAEMON_RULES, PROTECTION_ENDPOINT: NOT_PROTECTED},
                              thread_error=work.WorkError("GraphQL 502"))
    prompts = {
        "review-disposition": [_disposition_prompt(work._collect_synchronization(t, state(pr=True).pr))
                               for t in (known, unknown)],
        "build": [work._stage_prompt(state(AFFIRMED, ARTIFACT, WOULD, HOLDER, pr=True),
                                     work.Decision("build", True, "fresh", "fixture"),
                                     branch=BRANCH).decode()],
    }
    checked = []
    for stage, texts in prompts.items():
        allowance = github_allowance.allowance_for(stage, repository="example/product", branch=BRANCH,
                                                   pull_request=7)
        config = {"allowance": allowance, "root": str(tree), "child_settings": str(tree / "c.json")}
        for text in texts:
            for command in _prompt_commands(text.replace("THREAD_ID", "PRRT_x")):
                verdict = guard.decide(command, str(tree), config)
                assert verdict["decision"] == "allow", (stage, command, verdict["reason"])
                checked.append(command)
    # Non-vacuous: the resolve command, the GET fetches and the thread-id read were all found.
    assert any("resolveReviewThread" in command for command in checked)
    assert any(command.startswith("gh api --method GET") for command in checked)
    assert any(command.startswith("gh api graphql") and "mutation" not in command for command in checked)


@pytest.mark.parametrize("stage", ["artifact", "build", "floor", "review-disposition"])
def test_ac11_every_composed_implementer_prompt_names_its_writes(stage, monkeypatch):
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, pr=True)
    monkeypatch.setattr(work, "_artifact_source_problem", lambda *_a: None)
    allowance = github_allowance.allowance_for(stage, repository="example/product", branch=BRANCH,
                                               pull_request=7)
    for cloud, expected in ((False, github_allowance.sentence(allowance)),
                            (True, github_allowance.cloud_sentence())):
        prompt = work._stage_prompt(fixture, work.Decision(stage, True, "fresh", "fixture"),
                                    branch=BRANCH, floor_command="python check.py", cloud=cloud).decode()
        assert expected in prompt and "**Write requests**" in prompt


def test_ac10_the_allowance_command_prints_the_sentence(tmp_path, capsys):
    tree = _bound_tree(tmp_path)
    args = work.parser().parse_args(["allowance", "build", "--repo", "example/product", "--issue", "12",
                                     "--root", str(tree), "--implementation-root", str(tree)])
    assert work._allowance_command(args) == 0
    expected = github_allowance.sentence(github_allowance.allowance_for(
        "build", repository="example/product", branch=BRANCH, pull_request=None))
    assert capsys.readouterr().out.strip() == expected


GRANT_BRIEF = """**Rows**

**4. A write outside the allowance is granted only where the affirmed brief names it.**
   - The artifact must test a real push to its probe branch.
"""


def _grant_state(body):
    from source_claims import Marker
    fixture = state(pr=True)
    fixture.issue_comments = [{"id": 9001, "body": body, "user": {"login": PRODUCER}}]
    brief = Marker("affirmed-brief", {}, GRANT_BRIEF, PRODUCER, "issue-comment", "7001")
    return fixture, brief


def _grant_body(**values):
    fields = {"brief": 7001, "row": 4, "stage": "artifact", "write": "push",
              "target": "example/product:refs/heads/probe", **values}
    return ("<!-- tradecraft:write-grant:v1 brief={brief} row={row} stage={stage} write={write} "
            "target={target} -->\n> The artifact must test a real push\n").format(**fields)


def test_ac14_a_grant_resting_on_an_affirmed_row_is_carried(monkeypatch):
    fixture, brief = _grant_state(_grant_body())
    monkeypatch.setattr(work, "_affirmed_review", lambda _state: (brief, ("ordinary", "connected")))
    assert work.validated_grants(fixture, [9001], "artifact", "resume") == [
        {"marker": 9001, "brief": 7001, "row": 4, "stage": "artifact", "write": "push",
         "target": "example/product:refs/heads/probe"}]


@pytest.mark.parametrize("body, stage, continuity, ids", [
    (_grant_body(brief=7002), "artifact", "resume", [9001]),
    (_grant_body(row=9), "artifact", "resume", [9001]),
    (_grant_body().replace("real push", "real deploy"), "artifact", "resume", [9001]),
    (_grant_body(), "build", "resume", [9001]),
    (_grant_body(), "artifact", "fresh", [9001]),
    (_grant_body(), "artifact", "resume", [9002]),
    (_grant_body(target="refs/tags/x"), "artifact", "resume", [9001]),
])
def test_ac14_a_grant_without_an_affirmed_row_is_refused_before_launch(
        monkeypatch, body, stage, continuity, ids):
    fixture, brief = _grant_state(body)
    monkeypatch.setattr(work, "_affirmed_review", lambda _state: (brief, ("ordinary", "connected")))
    with pytest.raises(work.WorkError, match="grant"):
        work.validated_grants(fixture, ids, stage, continuity)


@pytest.mark.parametrize("grant_brief", [7002, 7001])
def test_ac14_run_refuses_a_grant_before_any_executor_or_launcher_runs(
        tmp_path, monkeypatch, capsys, grant_brief):
    from test_work import FakeTransport, write_policy
    fixture, brief = _grant_state(_grant_body(brief=grant_brief))
    git(tmp_path, "init", "-q")
    write_policy(tmp_path)
    monkeypatch.setattr(work, "read_state", lambda *_a, **_k: fixture)
    monkeypatch.setattr(work, "_affirmed_review", lambda _state: (brief, ("ordinary", "connected")))
    launched = []
    monkeypatch.setattr(work, "_invoke_recipient", lambda *a, **k: launched.append("launcher"))

    def executor(*_a, **kwargs):
        launched.append(("executor", kwargs.get("github_write_grants")))
        return 0

    class Transport:
        def get(self, endpoint, *, paginate=False):
            if endpoint == "repos/example/product/pulls/7":
                return fixture.pr
            return FakeTransport({}).get(endpoint, paginate=paginate)

    # A fresh artifact turn: the grant is refused because the turn is not a resume, and,
    # for 7002, because it cites no affirmed brief comment.
    args = work.parser().parse_args([
        "run", "artifact", "--repo", "example/product", "--issue", "12", "--root", str(tmp_path),
        "--holder-session-id", "holder-session", "--grant", "9001"])
    monkeypatch.setattr(work, "_named_continuity", lambda *_a: "fresh")
    with pytest.raises(work.WorkError, match="--grant 9001 refused"):
        work.run(args, transport=Transport(), executor=executor)
    assert launched == []
    # Resumed, the valid grant reaches the executor; the one citing no brief row still launches nothing.
    monkeypatch.setattr(work, "_named_continuity", lambda *_a: "resume")
    if grant_brief == 7002:
        with pytest.raises(work.WorkError, match="--grant 9001 refused"):
            work.run(args, transport=Transport(), executor=executor)
        assert launched == []
    else:
        assert work.run(args, transport=Transport(), executor=executor) == 0
        assert [entry[0] for entry in launched] == ["executor"]


def test_release_report_lists_grants_and_refusals(tmp_path, capsys, monkeypatch):
    from test_work import RULES, release_ready, run_release
    fixture = release_ready("clean")
    bound = {"status": "refused, not made",
             "refusals": [{"dispatch_id": "d1", "stage": "use", "command": "gh issue comment 1"}],
             "grants": [{"dispatch_id": "d2", "stage": "artifact", "marker": 9001, "brief": 7001,
                         "row": 4, "write": "push", "target": "example/product:refs/heads/probe"}]}
    monkeypatch.setattr(work, "_github_write_report", lambda _state: bound)
    report = run_release(fixture, tmp_path, capsys, reason=work.decide(fixture, RULES).reason)
    assert report["reason"] == "all-evidence-complete"
    assert report["write_grants"] == bound["grants"]
    assert report["write_refusals"] == bound["refusals"]


def test_ac9_ac20_the_entrance_report_names_refusals_and_grants(tmp_path, monkeypatch):
    fixture = state(pr=True)
    fixture.record_root = tmp_path
    refusal = {"scope": "parent", "entry": "prefix", "command": "gh issue comment 1",
               "reason": "refused", "allowance": {"kind": "none"}}
    grant = {"marker": 9001, "brief": 7001, "row": 4, "write": "push", "target": "x"}
    rows = [(0, "b1", {"dispatch_id": "d1", "stage": "use"}, {"github_write_refusals": [refusal]}),
            (1, "b2", {"dispatch_id": "d2", "stage": "artifact"},
             {"github_write_bound": {"allowance": {"grants": [grant]}}})]
    seen = {}

    def bundles(_store, _work, stages, **_k):
        seen["stages"] = stages
        return rows

    monkeypatch.setattr(work.lifecycle, "launch_bundles", bundles)
    monkeypatch.setattr(work.work_recovery, "scoped", lambda _state, found, **_k: found)
    report = work._github_write_report(fixture)
    assert "use" in seen["stages"]
    assert report["status"] == "read"
    assert report["refusals"] == [{"dispatch_id": "d1", "stage": "use", **refusal}]
    assert report["grants"] == [{"dispatch_id": "d2", "stage": "artifact", **grant}]


def test_ac7_the_cloud_routine_still_names_only_its_two_pushes_and_no_posting():
    import cloud_build
    assert "never push any branch other than the change branch and" in cloud_build._ROUTINE_PROMPT
    assert "Never comment on the issue" in cloud_build._ROUTINE_PROMPT


def test_a_composed_prompt_names_the_grants_in_force(monkeypatch):
    fixture = state(AFFIRMED, ARTIFACT, WOULD, HOLDER, pr=True)
    monkeypatch.setattr(work, "_artifact_source_problem", lambda *_a: None)
    grant = {"marker": 9001, "brief": 7001, "row": 4, "stage": "build", "write": "push",
             "target": "example/product:refs/heads/probe"}
    prompt = work._stage_prompt(fixture, work.Decision("build", True, "resume", "fixture"),
                                branch=BRANCH, grants=[grant]).decode()
    allowance = github_allowance.allowance_for("build", repository="example/product", branch=BRANCH,
                                               pull_request=7, grants=[grant])
    assert github_allowance.sentence(allowance) in prompt
    assert prompt.count(github_allowance.SENTENCE_OPENING) == 1
