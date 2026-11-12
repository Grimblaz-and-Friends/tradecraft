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


def _allowance_at(tmp_path, monkeypatch, argv, *, pr=True):
    """Run the allowance command as the entrance does: on the issue's state, with BRANCH's tree registered."""
    tree = tmp_path / "bound-tree"
    if not tree.exists():
        _bound_tree(tmp_path)
    monkeypatch.setattr(work, "resolve_implementation_root",
                        lambda *_a, **_k: (tree.resolve(), BRANCH, False))
    argv = [value.replace("{tree}", str(tree)) for value in argv]
    args = work.parser().parse_args([*argv, "--repo", "example/product", "--issue", "12",
                                     "--root", str(tree)])
    return work._allowance_command(args, state=state(pr=pr), root=tree)


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
                            (True, github_allowance.cloud_sentence(stage))):
        prompt = work._stage_prompt(fixture, work.Decision(stage, True, "fresh", "fixture"),
                                    branch=BRANCH, floor_command="python check.py", cloud=cloud).decode()
        assert expected in prompt and "**Write requests**" in prompt


def test_ac10_the_allowance_command_prints_the_sentence(tmp_path, monkeypatch, capsys):
    assert _allowance_at(tmp_path, monkeypatch, ["allowance", "build", "--implementation-root", "{tree}"],
                         pr=False) == 0
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
    # One list, with its status: the release report carries the entrance report's bound.
    assert report["github_write_bound"] == bound
    assert "write_grants" not in report and "write_refusals" not in report


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
    rows.append((2, "b3", {"dispatch_id": "d3", "stage": "build"},
                 {"github_write_refusals": [], "github_write_refusals_unknown": "OSError: lost"}))
    report = work._github_write_report(fixture)
    assert report["status"] == "unknown" and "d3: OSError: lost" in report["reason"]
    assert len(report["refusals"]) == 1
    # An armed check whose refusals were never read is unknown; a check that never ran is not.
    # A launch that prepared a log (it names child settings) and never read it is unknown, a Codex
    # launch whose own check did not run included; a cloud run prepared none.
    armed = {"command_check": {"status": "armed"}, "child_settings": "c.json", "allowance": {"grants": []}}
    codex = {"command_check": {"status": "not-run"}, "child_settings": "c.json"}
    cloud = {"route": "cloud", "command_check": {"status": "not-run"}}
    rows[:] = [(0, "b1", {"dispatch_id": "d4", "stage": "build"}, {"github_write_bound": armed}),
               (1, "b2", {"dispatch_id": "d5", "stage": "build"}, {"github_write_bound": codex}),
               (2, "b3", {"dispatch_id": "d6", "stage": "build"}, {"github_write_bound": cloud})]
    report = work._github_write_report(fixture)
    assert report["status"] == "unknown" and "d4: its refusals were never read" in report["reason"]
    assert "d5: its refusals were never read" in report["reason"] and "d6" not in report["reason"]
    rows[0][3]["github_write_refusals"] = []
    rows[1][3]["github_write_refusals"] = []
    assert work._github_write_report(fixture)["status"] == "read"


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


@pytest.mark.parametrize("arguments, missing", [
    (["allowance", "build"], "--implementation-root"),
    (["allowance", "floor"], "--implementation-root"),
    (["allowance", "review-disposition", "--implementation-root", "{tree}"], "has no pull request yet"),
    # Naming a number does not help: the issue has none, so the message says that instead.
    (["allowance", "review-disposition", "--implementation-root", "{tree}", "--pull-request", "7"],
     "no thread to answer"),
    (["allowance", "build", "--implementation-root", "{tree}", "--pull-request", "7"],
     "has no pull request yet"),
])
def test_the_allowance_command_refuses_rather_than_print_the_wrong_sentence(tmp_path, monkeypatch, capsys,
                                                                            arguments, missing):
    with pytest.raises(work.WorkError, match=missing):
        _allowance_at(tmp_path, monkeypatch, arguments, pr=False)
    assert capsys.readouterr().out == ""


def test_the_allowance_command_prints_the_sentence_the_use_consumer_launcher_holds(tmp_path, monkeypatch,
                                                                                  capsys):
    assert _allowance_at(tmp_path, monkeypatch, ["allowance", "use"]) == 0
    printed = capsys.readouterr().out.strip()
    # The allowance dispatch_seat.use_consumer_bound holds for this work.
    held = github_allowance.allowance_for("use", repository=github_allowance.repository_of(
        "example/product#12"), branch=None, pull_request=None)
    assert held["kind"] == "none"
    assert not github_allowance.needs_notice(held, ("Use the change.\n\n" + printed).encode("utf-8"))


def test_a_stage_outside_run_or_allowance_is_refused_naming_both(tmp_path):
    args = work.parser().parse_args(["--repo", "example/product", "--issue", "12", "--root", str(tmp_path)])
    args.stage = "build"  # the state the guard refuses: a stage on neither run nor allowance
    with pytest.raises(work.WorkError, match="only after the run or allowance command"):
        work._run(args, transport=object())


def test_the_allowance_command_prints_review_dispositions_own_pull_request(tmp_path, monkeypatch, capsys):
    number = state(pr=True).pr["number"]
    assert _allowance_at(tmp_path, monkeypatch, ["allowance", "review-disposition", "--implementation-root",
                                                 "{tree}", "--pull-request", str(number)]) == 0
    assert f"example/product#{number}" in capsys.readouterr().out


def test_the_allowance_command_takes_the_launchers_tree_and_pull_request(tmp_path, monkeypatch, capsys):
    tree = _bound_tree(tmp_path)
    fixture = state(pr=True)
    registered = {"root": tree.resolve()}
    monkeypatch.setattr(work, "resolve_implementation_root",
                        lambda *_a, **_k: (registered["root"], BRANCH, False))

    def allowance(*extra):
        args = work.parser().parse_args(["allowance", "review-disposition", "--repo", "example/product",
                                         "--issue", "12", "--root", str(tree), "--implementation-root",
                                         str(tree), *extra])
        return work._allowance_command(args, state=fixture, root=tree)

    # The issue's pull request, as the launcher holds it, when none is named.
    assert allowance() == 0
    assert f"example/product#{fixture.pr['number']}" in capsys.readouterr().out
    with pytest.raises(work.WorkError, match="not this issue's pull request"):
        allowance("--pull-request", str(fixture.pr["number"] + 1))
    registered["root"] = (tmp_path / "elsewhere").resolve()
    with pytest.raises(work.WorkError, match="registered implementation tree"):
        allowance()
    assert capsys.readouterr().out == ""


def test_the_allowance_command_prints_the_cloud_routes_sentence(tmp_path, monkeypatch, capsys):
    def allowance(*arguments):
        return _allowance_at(tmp_path, monkeypatch, ["allowance", *arguments, "--cloud"])

    assert allowance("build") == 0
    printed = capsys.readouterr().out.strip()
    assert printed == github_allowance.cloud_sentence("build")
    assert github_allowance.cloud_notice("build", printed.encode()) == b""
    with pytest.raises(work.WorkError, match="never takes the cloud route"):
        allowance("use")
    with pytest.raises(work.WorkError, match="cannot ride a cloud launch"):
        allowance("build", "--grant", "9001")


def _granted_allowance_run(tmp_path, monkeypatch, capsys, *, grant_brief=7001, continuity="resume",
                           extra=()):
    """Drive the documented route: `work.py allowance build --grant ID` for a resumed, granted build."""
    from test_work import FakeTransport, write_policy
    fixture, brief = _grant_state(_grant_body(brief=grant_brief, stage="build"))
    tree = _bound_tree(tmp_path)
    write_policy(tree)
    monkeypatch.setattr(work, "read_state", lambda *_a, **_k: fixture)
    monkeypatch.setattr(work, "_affirmed_review", lambda _state: (brief, ("ordinary", "connected")))
    monkeypatch.setattr(work, "_named_continuity", lambda *_a: continuity)
    monkeypatch.setattr(work, "resolve_implementation_root",
                        lambda *_a, **_k: (tree.resolve(), BRANCH, False))

    class Transport:
        def get(self, endpoint, *, paginate=False):
            if endpoint == "repos/example/product/pulls/7":
                return fixture.pr
            return FakeTransport({}).get(endpoint, paginate=paginate)

    args = work.parser().parse_args([
        "allowance", "build", "--repo", "example/product", "--issue", "12", "--root", str(tree),
        "--implementation-root", str(tree), "--grant", "9001", *extra])
    return work.run(args, transport=Transport()), capsys.readouterr().out


def test_a_granted_turns_dispatch_built_by_the_documented_route_is_accepted(tmp_path, monkeypatch, capsys):
    code, printed = _granted_allowance_run(tmp_path, monkeypatch, capsys)
    assert code == 0
    grant = {"marker": 9001, "brief": 7001, "row": 4, "stage": "build", "write": "push",
             "target": "example/product:refs/heads/probe"}
    # The allowance the launcher builds for this granted, resumed build.
    launch = github_allowance.allowance_for("build", repository="example/product", branch=BRANCH,
                                            pull_request=None, grants=[grant])
    dispatch = ("Build the change.\n\n" + printed.strip()).encode("utf-8")
    assert github_allowance.needs_notice(launch, dispatch) is False
    assert "the granted push example/product:refs/heads/probe" in printed


@pytest.mark.parametrize("grant_brief, continuity", [(7002, "resume"), (7001, "fresh")])
def test_allowance_refuses_a_grant_the_entrance_would_refuse(tmp_path, monkeypatch, capsys,
                                                             grant_brief, continuity):
    with pytest.raises(work.WorkError, match="--grant 9001 refused") as refused:
        _granted_allowance_run(tmp_path, monkeypatch, capsys, grant_brief=grant_brief,
                               continuity=continuity)
    # The same reason run --grant gives, from the same validation.
    fixture, brief = _grant_state(_grant_body(brief=grant_brief, stage="build"))
    monkeypatch.setattr(work, "_affirmed_review", lambda _state: (brief, ("ordinary", "connected")))
    with pytest.raises(work.WorkError) as entrance:
        work.validated_grants(fixture, [9001], "build", continuity)
    assert str(refused.value) == str(entrance.value)


@pytest.mark.parametrize("continuity", ["fresh", "resume"])
def test_allowance_names_the_cloud_route_before_a_grants_validity(tmp_path, monkeypatch, capsys,
                                                                   continuity):
    with pytest.raises(work.WorkError, match="cannot ride a cloud launch"):
        _granted_allowance_run(tmp_path, monkeypatch, capsys, continuity=continuity,
                               extra=("--cloud",))


def test_a_grant_from_an_author_who_is_not_a_marker_producer_is_refused(monkeypatch):
    fixture, brief = _grant_state(_grant_body())
    fixture.issue_comments[0]["user"] = {"login": "someone-else"}
    monkeypatch.setattr(work, "_affirmed_review", lambda _state: (brief, ("ordinary", "connected")))
    with pytest.raises(work.WorkError, match="not a configured marker producer"):
        work.validated_grants(fixture, [9001], "artifact", "resume")


@pytest.mark.parametrize("quote", ["t", "push", "real push", "eal push to"])
def test_a_grant_quoting_less_than_a_phrase_of_its_row_is_refused(monkeypatch, quote):
    body = _grant_body().replace("The artifact must test a real push", quote)
    fixture, brief = _grant_state(body)
    monkeypatch.setattr(work, "_affirmed_review", lambda _state: (brief, ("ordinary", "connected")))
    with pytest.raises(work.WorkError, match="at least 3 whole words"):
        work.validated_grants(fixture, [9001], "artifact", "resume")


def test_a_grant_quoting_three_whole_words_of_its_row_is_carried(monkeypatch):
    body = _grant_body().replace("The artifact must test a real push", "a real push")
    fixture, brief = _grant_state(body)
    monkeypatch.setattr(work, "_affirmed_review", lambda _state: (brief, ("ordinary", "connected")))
    assert work.validated_grants(fixture, [9001], "artifact", "resume")[0]["row"] == 4
