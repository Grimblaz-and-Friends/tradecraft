"""The cloud route: record, token, practice pin, fire, finish and checks."""
import argparse
import base64
import json
from pathlib import Path
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import cloud_build as cloud  # noqa: E402
import change_cost  # noqa: E402

REPO, PRACTICE = "Owner/product", "Grimblaz-and-Friends/tradecraft"
INSTALLED, OLD_PIN = "1" * 40, "0" * 40
TIP, AFTER, HOLDER = "a" * 40, "b" * 40, "c" * 40
TOKEN = "sk-ant-PLANTED-token-value-0123456789"


class Deadline:
    def __init__(self, polls=5):
        self.polls = polls

    def remaining(self, **_):
        self.polls -= 1
        if self.polls < 0:
            raise TimeoutError("caller limit leaves no useful launch window")
        return 100.0


class Fake(cloud.Transport):
    """GitHub, the fire endpoint and the CLI, with a run that pushes its report on fire."""

    def __init__(self, *, compare="ahead", report=b"built\n", practice_ok=True, skip_ci=True,
                 advance=True, holder_on_remote=True, usage_practice=None, fire_status=200):
        self.calls, self.files, self.compare, self.fired = [], {}, compare, []
        self.report, self.practice_ok, self.skip_ci, self.advance = report, practice_ok, skip_ci, advance
        self.holder_on_remote, self.usage_practice, self.fire_status = holder_on_remote, usage_practice, fire_status
        self.change_tip, self.cli_calls, self.comments, self.deleted = TIP, [], [], []
        self.ledger = [{"id": "m1", "model": "claude-opus-5-5", "file": "main",
                        "input": 10, "output": 20, "cache_read": 30, "cache_creation": 0}]
        self.read_errors = 0
        self.environment = dict(cloud.CLOUD_ENVIRONMENT)

    def github(self, method, path, body=None):
        self.calls.append((method, path, body))
        if path.endswith("/git/ref/heads/cloud-practice"):
            return 200, {"object": {"sha": OLD_PIN}}
        if "/compare/" + OLD_PIN in path:
            return (404, {}) if self.compare == 404 else (200, {"status": self.compare})
        if method == "PATCH":
            return 200, {}
        if path.endswith("/git/ref/heads/tradecraft/77-x"):
            return 200, {"object": {"sha": self.change_tip}}
        if "/git/ref/heads/claude/" in path:
            return 200, {"object": {"sha": "d" * 40}}
        if path.split("/")[3:4] == ["commits"]:
            return (200, {}) if self.holder_on_remote else (422, {})
        if method == "GET" and "/git/commits/" in path:
            return 200, {"tree": {"sha": "t" * 40}}
        if method == "POST" and path.endswith("/git/blobs"):
            self.dispatch = base64.b64decode(body["content"])
            return 201, {"sha": "e" * 40}
        if method == "POST" and path.endswith("/git/trees"):
            return 201, {"sha": "f" * 40}
        if method == "POST" and path.endswith("/git/commits"):
            assert body["message"].endswith("[skip ci]")
            return 201, {"sha": "9" * 40}
        if method == "POST" and path.endswith("/git/refs"):
            self.branch = body["ref"][len("refs/heads/"):]
            return 201, {}
        if "/contents/tradecraft-cloud/" in path:
            if self.read_errors:
                self.read_errors -= 1
                return 502, "bad gateway"
            name = path.split("tradecraft-cloud/")[1].split("?")[0]
            if name not in self.files:
                return 404, {}
            return 200, {"encoding": "base64", "content": base64.b64encode(self.files[name]).decode()}
        if "/compare/" + "9" * 40 in path:
            message = "builder report [skip ci]" if self.skip_ci else "builder report"
            return 200, {"commits": [{"sha": "5" * 40, "commit": {"message": message}},
                                     {"sha": "6" * 40, "commit": {"message": "usage stop 1 [skip ci]"}}]}
        if f"/compare/{TIP}..." in path:
            return 200, ({"status": "ahead", "commits": [{"sha": AFTER}]} if self.advance
                         else {"status": "identical", "commits": []})
        if path.endswith("/comments"):
            self.comments.append(body["body"])
            return 201, {"html_url": "https://github.com/x/comment"}
        if method == "DELETE":
            self.deleted.append(path)
            return 204, None
        raise AssertionError(f"unexpected {method} {path}")

    def _run(self):
        """What the cloud run and its Stop hook push to the report branch."""
        if self.advance:
            self.change_tip = AFTER
        check = {"ok": True, "commit": INSTALLED} if self.practice_ok else {
            "ok": False, "expected": INSTALLED, "found": OLD_PIN, "excluded_present": []}
        report = self.report if self.practice_ok else f"PRACTICE MISMATCH expected {INSTALLED} found {OLD_PIN}\n".encode()
        totals = {}
        for row in self.ledger:
            model = totals.setdefault(row["model"], {})
            for key in ("input", "output", "cache_read", "cache_creation"):
                model[key] = model.get(key, 0) + row[key]
        usage = {"report_blob": cloud.git_blob_sha(report), "totals_by_model": totals, "ledger": self.ledger,
                 "files_present": ["main"], "files_read": [{"file": "main", "usage_entries": 1}],
                 "files_unread": [], "profile": {"models": ["claude-opus-5-5"], "efforts": ["high"]},
                 "permission_mode": {"values": ["auto"], "source": "hook-input"},
                 "environment": self.environment,
                 "practice_check": self.usage_practice if self.usage_practice is not None else check}
        self.files.update({"report.md": report, "instructions.md": b"/home/user/product/CLAUDE.md\n",
                           "practice-check.json": json.dumps(check).encode(),
                           "usage.json": json.dumps(usage).encode()})

    def fire(self, routine, token, text):
        self.fired.append((routine, token, text))
        if self.fire_status != 200:
            return self.fire_status, "nope"
        self._run()
        return 200, json.dumps({"claude_code_session_id": "cse_ABC123",
                                "claude_code_session_url": "https://claude.ai/code/cse_ABC123",
                                "type": "routine_fire"})

    def cli(self, argv, env):
        self.cli_calls.append((argv, env))
        self.change_tip = TIP  # the local tree followed the last attempt
        if argv[1:3] == ["auth", "status"]:
            return 0, json.dumps({"authMethod": self.auth}).encode()
        self.ledger = [*self.ledger, {"id": f"m{len(self.ledger) + 1}", "model": "claude-opus-5-5", "file": "main",
                                      "input": 5, "output": 20, "cache_read": 0, "cache_creation": 0}]
        self._run()
        return 0, json.dumps({"ok": True, "session_id": argv[4], "url": "u"}).encode()

    auth = "claude.ai"

    def git(self, root, *arguments):
        self.calls.append(("git", arguments, None))
        return 0, ""

    def remote(self, root):
        return "product-remote"

    def sleep(self, seconds):
        pass


@pytest.fixture
def machine(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    plugin = tmp_path / "plugin"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "tradecraft", "version": "0.206.0"}))
    install = tmp_path / "installed_plugins.json"
    install.write_text(json.dumps({"plugins": {"tradecraft@tradecraft": [{
        "scope": "user", "installPath": str(tmp_path / "elsewhere"), "version": "0.206.0",
        "gitCommitSha": INSTALLED}]}}))
    token = tmp_path / "product.token"
    token.write_text(TOKEN + "\n")
    root = tmp_path / "tree"
    root.mkdir()
    monkeypatch.setattr(cloud.records, "git_revision", lambda _root: TIP)
    entry = {"repository": REPO, "practice": {"repository": PRACTICE, "branch": "cloud-practice"},
             "routine_id": "trig_1", "token_file": str(token), "setup_record": "s", "set_up_at": "t"}
    return {"plugin": plugin, "install": install, "token": token, "root": root, "entry": entry,
            "records": tmp_path / "records", "tmp": tmp_path}


def launch(machine, transport, *, stage="build", resume=None, brief=b"", copy=None, polls=5, entry=True,
           preset=None, model="claude-opus-5-5", effort="high", timeout_seconds=600):
    output = machine["records"] / f"{stage}-{len(list(machine['tmp'].glob('**/*.request.json')))}" / "result.md"
    args = argparse.Namespace(
        root=machine["root"], output=output, work=f"{REPO}#77", stage=stage, resume=resume,
        settings_source="s", settings_scope="scope", model=model, effort=effort,
        retry_of=None, holder_session_id=None, lineage_branch=None if stage == "artifact" else "tradecraft/77-x",
        lineage_pull_request=None, timeout_seconds=timeout_seconds, artifact_brief_source="brief",
        artifact_brief=None)
    code = cloud.run(args, Deadline(polls), entry=machine["entry"] if entry else None, route_source="test",
                     effective_prompt=b"the task\n", prompt=b"the task\n", context=b"",
                     artifact_brief=brief, metadata={"artifact_copy": copy} if copy else {},
                     composition={"origin": "holder"}, settings_sources={"vendor": "v", "model": "m", "effort": "e"},
                     validate=lambda expected, returned: {"status": "pass"}, transport=transport,
                     record_root=machine["records"], plugin=machine["plugin"], install_path=machine["install"],
                     preset_failure=preset)
    request = json.loads((output.parent / "result.md.request.json").read_text())
    run = json.loads((output.parent / "result.md.run.json").read_text())
    return code, request, run, output


def everything(machine):
    return b"".join(path.read_bytes() for path in machine["records"].rglob("*") if path.is_file())


def test_a_build_records_its_session_and_checks_the_change_branch(machine):
    fake = Fake()
    code, request, run, output = launch(machine, fake)
    assert code == 0 and run["outcome"] == "success"
    assert request["route"] == "cloud" and request["transport"] == "claude-cloud-routine"
    assert request["cloud"]["session_id"] == "cse_ABC123"
    assert request["cloud"]["session_url"] == "https://claude.ai/code/cse_ABC123"
    attempt = run["attempts"][0]
    assert attempt["cloud"]["cloud_checks"]["change_branch"]["ok"] is True
    assert attempt["cloud"]["profile"]["off_profile"] is False
    assert attempt["cloud"]["profile"]["permission_mode"] == ["auto"]
    assert output.read_bytes() == b"built\n"
    assert run["launch_comparison"]["status"] == "cloud-not-run"
    assert request["write_bound"]["comparison"] == cloud.COMPARISON_REASON
    assert request["instructions_applied"] == cloud.INSTRUCTIONS_APPLIED
    assert attempt["cloud"]["instructions_loaded"] == ["/home/user/product/CLAUDE.md"]
    text = fake.fired[0][2]
    assert text.startswith(cloud.HEADER) and "checkout: branch tradecraft/77-x" in text
    assert f"practice-commit: {INSTALLED}" in text and len(text) < cloud.FIRE_TEXT_LIMIT
    assert fake.dispatch == b"the task\n"


def test_an_unchanged_change_branch_fails_and_holds(machine):
    import work
    _code, _request, run, _output = launch(machine, Fake(advance=False))
    check = run["attempts"][0]["cloud"]["cloud_checks"]["change_branch"]
    assert check["ok"] is False and "unchanged" in check["faults"][0]
    assert [finding["id"] for finding in work._cloud_check_findings(run)] == ["cloud-check:change_branch"]


def test_token_refusals_print_and_keep_nothing_of_the_file(machine, capsys):
    for content in (None, b"", b"two\nlines", bytes([0x74, 0xc3, 0xb6, 0x6b])):
        if content is None:
            machine["token"].unlink(missing_ok=True)
        else:
            machine["token"].write_bytes(content + (TOKEN.encode() if content == b"two\nlines" else b""))
        fake = Fake()
        code, _request, run, _output = launch(machine, fake)
        assert code == 1 and run["outcome"] == "refused"
        assert str(machine["token"]) in run["attempts"][0]["reason"]
        assert fake.fired == [] and fake.cli_calls == []
    seen = capsys.readouterr()
    assert TOKEN.encode() not in everything(machine)
    assert TOKEN not in seen.out + seen.err


def test_artifact_checks_out_the_holder_commit_and_publishes_the_report(machine):
    report = b"> brief\n\n# Artifact\n"
    fake = Fake(report=report)
    copy = {"source_commit": HOLDER}
    code, request, run, output = launch(machine, fake, stage="artifact", brief=b"> brief\n", copy=copy)
    assert code == 0
    assert f"checkout: commit {HOLDER}" in fake.fired[0][2]
    assert ("POST", f"repos/{REPO}/git/refs") in [(m, p) for m, p, _b in fake.calls]
    assert not any(c[0] == "git" for c in fake.calls)  # the change branch is not published
    assert output.read_bytes() == report  # instructions.md never reaches the output
    assert b"CLAUDE.md" not in output.read_bytes()
    missing = Fake(holder_on_remote=False)
    code, _request, run, _output = launch(machine, missing, stage="artifact", brief=b"> brief\n", copy=copy)
    assert code == 1 and HOLDER in run["attempts"][0]["reason"] and missing.fired == []


def test_a_failed_fire_is_recorded_and_never_falls_back(machine):
    code, _request, run, _output = launch(machine, Fake(fire_status=403))
    assert code == 1 and run["outcome"] == "error" and "fire failed: HTTP 403" in run["attempts"][0]["reason"]
    code, _request, run, _output = launch(machine, Fake(), preset="cloud record x is malformed")
    assert run["outcome"] == "refused" and "malformed" in run["attempts"][0]["reason"]


def test_route_selection_and_a_broken_record(tmp_path):
    path = tmp_path / "cloud-builds.json"
    assert cloud.route_for(f"{REPO}#1", path)[0] is None
    path.write_text(json.dumps({"schema_version": 1, "practice": {"repository": PRACTICE},
                                "repositories": {REPO: {"routine_id": "trig", "token_file": "t",
                                                        "setup_record": "s", "set_up_at": "x"}}}))
    entry, source = cloud.route_for(f"{REPO}#1", path)
    assert entry["routine_id"] == "trig" and entry["practice"]["branch"] == "cloud-practice"
    assert cloud.route_for("Owner/other#1", path)[0] is None
    for broken in ("{", json.dumps({"schema_version": 2}),
                   json.dumps({"schema_version": 1, "practice": {"repository": PRACTICE},
                               "repositories": {REPO: {"routine_id": "trig"}}})):
        path.write_text(broken)
        with pytest.raises(cloud.CloudRefusal):
            cloud.route_for(f"{REPO}#1", path)


def test_a_record_naming_the_practice_refuses(tmp_path):
    path = tmp_path / "cloud-builds.json"
    path.write_text(json.dumps({"schema_version": 1, "practice": {"repository": PRACTICE},
                                "repositories": {"Someone/tradecraft": {}}}))
    with pytest.raises(cloud.CloudRefusal, match="practice's own repository"):
        cloud.route_for(f"{REPO}#1", path)


def test_pin_fast_forwards_once(machine):
    fake = Fake()
    assert cloud.compare_pin(fake, machine["entry"]["practice"], INSTALLED).startswith("fast-forwarded")
    fake.compare = "identical"
    assert cloud.compare_pin(fake, machine["entry"]["practice"], INSTALLED) == "unchanged"
    patches = [body for method, _p, body in fake.calls if method == "PATCH"]
    assert patches == [{"sha": INSTALLED, "force": False}]


@pytest.mark.parametrize("state, phrase", [("behind", "reload"), ("diverged", "diverged"), (404, "absent")])
def test_pin_refusals(machine, state, phrase):
    fake = Fake(compare=state)
    code, _request, run, _output = launch(machine, fake)
    assert code == 1 and run["outcome"] == "refused" and phrase in run["attempts"][0]["reason"]
    assert fake.fired == []


def test_install_record_not_head_decides(machine):
    practice = cloud.installed_practice(machine["plugin"], machine["install"])
    assert practice["commit"] == INSTALLED
    (machine["plugin"] / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "tradecraft", "version": "0.205.0"}))
    with pytest.raises(cloud.CloudRefusal, match="reload"):
        cloud.installed_practice(machine["plugin"], machine["install"])
    source = (LIB / "cloud_build.py").read_text("utf-8")
    assert '"rev-parse", "HEAD"' not in source and "git status" not in source


def test_a_mismatch_is_recorded_without_waiting(machine):
    code, _request, run, _output = launch(machine, Fake(practice_ok=False), polls=2)
    assert run["outcome"] == "practice_mismatch"
    assert INSTALLED in run["attempts"][0]["reason"] and OLD_PIN in run["attempts"][0]["reason"]
    assert "change_branch" not in run["attempts"][0]["cloud"]["cloud_checks"]


def test_no_recorded_practice_check_fails_and_holds(machine):
    import work
    _code, _request, run, _output = launch(machine, Fake(usage_practice={"ok": None, "reason": "none"}))
    assert run["attempts"][0]["cloud"]["cloud_checks"]["practice"]["ok"] is False
    assert "cloud-check:practice" in [f["id"] for f in work._cloud_check_findings(run)]


def test_report_is_posted_whole_and_its_branch_deleted(machine):
    report = ("x" * 70_000 + "\n").encode()
    fake = Fake(report=report)
    launch(machine, fake)
    assert len(fake.comments) == 2 and "part 1 of 2" in fake.comments[0]
    body = "".join(comment.split("\n\n", 1)[1] for comment in fake.comments)
    assert body.encode() == report
    assert fake.deleted == [f"repos/{REPO}/git/refs/heads/{fake.branch}"]


def test_delete_refuses_any_other_name():
    request = {"work": f"{REPO}#77", "stage": "build", "dispatch_id": "d" * 32,
               "cloud": {"issue": 77, "report_branch": "claude/tradecraft-report-77-build-eeeeeeeeeeee"}}
    with pytest.raises(cloud.CloudError):
        cloud.delete_report_branch(Fake(), request)
    request["cloud"]["report_branch"] = "main"
    with pytest.raises(cloud.CloudError):
        cloud.delete_report_branch(Fake(), request)
    source = (LIB / "cloud_build.py").read_text("utf-8")
    assert source.count('"DELETE"') == 1


def test_a_report_commit_without_skip_ci_fails_and_holds(machine):
    import work
    _code, _request, run, _output = launch(machine, Fake(skip_ci=False))
    check = run["attempts"][0]["cloud"]["cloud_checks"]["skip_ci"]
    assert check == {"ok": False, "commits_without_marker": ["5" * 40]}
    assert "cloud-check:skip_ci" in [f["id"] for f in work._cloud_check_findings(run)]


def test_default_effort_is_marked():
    for profile in ({"models": ["claude-opus-5-5"], "efforts": []},
                    {"models": ["claude-opus-5-5"], "efforts": ["medium"]},
                    {"models": ["claude-opus-5-5"], "efforts": ["high", "medium"]},
                    {"models": ["claude-sonnet-5"], "efforts": ["high"]}):
        assert cloud.cloud_profile({"profile": profile})["off_profile"] is True
    assert cloud.cloud_profile({"profile": {"models": ["claude-opus-5-5"], "efforts": []}})["effort"] \
        == "medium (Opus 5.5 default; no effort key in transcript)"


def test_build_plus_repair_is_one_running_total_priced_as_known(machine):
    fake = Fake()
    launch(machine, fake)
    fake.auth = "claude.ai"
    code, request, run, _output = launch(machine, fake, stage="review-disposition", resume="cse_ABC123")
    assert code == 0 and request["cloud"]["session_id"] == "cse_ABC123"
    cloud_attempt = run["attempts"][0]["cloud"]
    assert cloud_attempt["delta"] == {"claude-opus-5-5": {"input": 5, "output": 20, "cache_read": 0,
                                                          "cache_creation": 0}}
    assert cloud_attempt["ledger_check"] == {"ok": True, "faults": []}
    assert cloud_attempt["running_total"] == {"claude-opus-5-5": {"input": 15, "output": 40, "cache_read": 30,
                                                                  "cache_creation": 0}}
    price = change_cost._price(change_cost._Attempt(usage=run["attempts"][0]["usage"]),
                               change_cost.load_rates(LIB / "rates.json"))
    assert price["status"] == "known" and float(price["amount"]) > 0
    argv = fake.cli_calls[-1][0]
    assert argv[:2] == ["claude", "-p"] and argv[3:5] == ["--cloud", "cse_ABC123"]
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in fake.cli_calls[-1][1]


def test_follow_up_after_an_update_keeps_the_loaded_commit(machine):
    fake = Fake()
    launch(machine, fake)
    install = json.loads(machine["install"].read_text())
    install["plugins"]["tradecraft@tradecraft"][0].update(gitCommitSha="2" * 40, version="0.207.0")
    machine["install"].write_text(json.dumps(install))
    calls_before = len(fake.calls)
    code, request, _run, _output = launch(machine, fake, stage="floor", resume="cse_ABC123")
    practice = request["cloud"]["practice"]
    assert practice == {"session_loaded": INSTALLED, "installed_at_send": "2" * 40, "drift": True,
                        "commit": INSTALLED, "repository": PRACTICE}
    assert not any(method == "PATCH" or "/compare/" + OLD_PIN in path for method, path, _b in fake.calls[calls_before:])
    assert f"practice-commit: {INSTALLED}" in fake.cli_calls[-1][0][2]


def test_a_missing_starting_record_is_an_error_not_a_refusal(machine):
    code, _request, run, _output = launch(machine, Fake(), stage="floor", resume="cse_NOPE")
    assert run["outcome"] == "error" and "starting attempts" in run["attempts"][0]["reason"]


def test_no_claude_ai_login_refuses(machine):
    launch(machine, Fake())
    fake = Fake()
    fake.auth = "oauth_token"
    code, _request, run, _output = launch(machine, fake, stage="floor", resume="cse_ABC123")
    assert run["outcome"] == "refused" and "no claude.ai login" in run["attempts"][0]["reason"]
    assert len(fake.cli_calls) == 1


def test_revision_resumes_the_author_at_the_current_holder_commit(machine):
    fake = Fake(report=b"> brief\n\ndraft\n")
    launch(machine, fake, stage="artifact", brief=b"> brief\n", copy={"source_commit": HOLDER})
    code, request, _run, _output = launch(machine, fake, stage="artifact", brief=b"> brief\n",
                                          copy={"source_commit": "8" * 40}, resume="cse_ABC123")
    assert request["cloud"]["session_id"] == "cse_ABC123" and len(fake.fired) == 1
    assert "checkout: commit " + "8" * 40 in fake.cli_calls[-1][0][2]


def test_pricing_needs_a_passing_ledger_and_a_rate_row():
    rates = change_cost.load_rates(LIB / "rates.json")

    def item(model, ok=True):
        usage = {"dispatch": {"launched_at": "2026-11-05T00:00:00+00:00", "actual_vendor": "claude",
                              "continuity": "resume"}, "model": {"requested": model, "reported": [model]},
                 "tokens": {"models": {model: {"input": 1000, "output": 1000, "cache_read": 0,
                                               "cache_creation": 0, "cache_write_5m": 0}}},
                 "source": "cloud-stop-hook", "scope": "session-delta",
                 "ledger_check": {"ok": ok, "faults": [] if ok else ["unread files: listed files went unread: x"]}}
        return change_cost._Attempt(usage=usage)

    known = change_cost._price(item("claude-opus-5-5"), rates)
    assert known["status"] == "known" and float(known["amount"]) > 0
    unknown = change_cost._price(item("claude-unrated-9"), rates)
    assert unknown["status"] == "unknown" and "amount" not in unknown
    ledger = change_cost._price(item("claude-opus-5-5", ok=False), rates)
    assert ledger["status"] == "unknown" and "unread files" in json.dumps(ledger)


def test_cloud_not_run_is_clear_and_local_still_compares():
    import launch_bound
    import work
    assert "cloud-not-run" in work.LAUNCH_CLEAR_STATUSES
    value = launch_bound.cloud_not_run()
    assert value["status"] == "cloud-not-run" and "cannot reach" in value["reason"] and value["findings"] == []
    assert {"clean", "not-launched"} <= work.LAUNCH_CLEAR_STATUSES


def test_cse_sessions_are_resumable_only_from_a_cloud_source(tmp_path):
    import work
    assert work._session_shaped("cse_ABC", {"route": "cloud"})
    assert not work._session_shaped("cse_ABC", {"route": "local"})
    assert not work._session_shaped("cse_ABC", {"route": "local"}, vendor="claude")
    assert work._session_shaped("cse_ABC", vendor="claude")
    assert not work._session_shaped("cse_ABC", vendor="codex")
    assert work._session_shaped("01234567-89ab-cdef-0123-456789abcdef", {})
    state = work.WorkState(REPO, 77, {})

    def marker(session, vendor):
        return work.Marker("builder-session", {"session": session, "vendor": vendor}, "", "producer")

    state.validated_markers = [marker("cse_CLAUDE", "claude"), marker("cse_CODEX", "codex")]
    # The newest marker names a Codex vendor, so its cloud-shaped id is never resumed.
    assert work.resume_session(state, "build", tmp_path) == "cse_CLAUDE"


def test_the_saved_prompt_forbids_posting_and_messaging():
    prompt = cloud.ROUTINE_PROMPT
    assert "Never comment on the issue, never message another session" in prompt
    assert "[skip ci]" in prompt and "instructions.md" in prompt and "report.md" in prompt


def test_a_temporary_read_error_is_retried_within_the_wait(machine):
    fake = Fake()
    fake.read_errors = 2
    code, _request, run, _output = launch(machine, fake, polls=5)
    assert code == 0 and run["outcome"] == "success"


def test_a_wait_that_never_reads_the_branch_says_why(machine):
    fake = Fake()
    fake.read_errors = 1000
    code, _request, run, _output = launch(machine, fake, polls=3)
    assert run["outcome"] == "interrupted"
    assert "last read error" in run["attempts"][0]["reason"] and "HTTP 502" in run["attempts"][0]["reason"]


def test_a_cloud_attempt_reports_its_launch_controls_as_not_applicable():
    import work
    request, attempt = {"route": "cloud"}, {"vendor": "claude", "launched": True,
                                            "source_format": "claude-cloud-routine"}
    controls = work._launch_controls_report(request, {"lifecycle": "completed"}, attempt)
    assert controls["status"] == "cloud-environment" and "cloud environment" in controls["reason"]
    assert controls["expected"] == cloud.CLOUD_ENVIRONMENT
    assert controls["disallowed_tools"] == ["PushNotification", "Monitor", "ScheduleWakeup", "CronCreate",
                                            "Workflow"]
    assert work._stream_check_report({"lifecycle": "completed"}, attempt)["status"] == "not-applicable"
    assert work.launch_bound.cloud_not_run()["reason"] == cloud.COMPARISON_REASON


def test_a_resumed_build_is_held_to_the_change_branch(machine):
    fake = Fake()
    launch(machine, fake)
    fake.advance = False
    _code, _request, run, _output = launch(machine, fake, stage="build", resume="cse_ABC123")
    check = run["attempts"][0]["cloud"]["cloud_checks"]["change_branch"]
    assert check["checked"] is True and check["ok"] is False


def test_a_repair_that_makes_no_commit_is_not_held(machine):
    fake = Fake()
    launch(machine, fake)
    fake.advance = False
    _code, _request, run, _output = launch(machine, fake, stage="review-disposition", resume="cse_ABC123")
    check = run["attempts"][0]["cloud"]["cloud_checks"]["change_branch"]
    assert check["checked"] is False and check["ok"] is True


def test_a_session_without_the_cloud_environment_fails_and_holds(machine):
    import work
    fake = Fake()
    longer = str(int(cloud.CLOUD_ENVIRONMENT["BASH_MAX_TIMEOUT_MS"]) + 1)
    fake.environment = {"CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": None, "BASH_MAX_TIMEOUT_MS": longer}
    _code, _request, run, _output = launch(machine, fake)
    check = run["attempts"][0]["cloud"]["cloud_checks"]["environment"]
    assert check["ok"] is False and len(check["faults"]) == 2
    assert "cloud-check:environment" in [finding["id"] for finding in work._cloud_check_findings(run)]


def test_a_fire_text_over_the_limit_refuses_before_firing(machine, monkeypatch):
    monkeypatch.setattr(cloud, "FIRE_TEXT_LIMIT", 10)
    fake = Fake()
    code, _request, run, _output = launch(machine, fake)
    assert code == 1 and run["outcome"] == "refused" and "report branch" in run["attempts"][0]["reason"]
    assert fake.fired == []


def test_a_diverged_pin_asks_the_owner_rather_than_a_reload(machine):
    _code, _request, run, _output = launch(machine, Fake(compare="diverged"))
    reason = run["attempts"][0]["reason"]
    assert "move it back to a release" in reason and "reload" not in reason


def test_a_practice_mismatch_records_only_the_mismatch(machine):
    import work
    fake = Fake(practice_ok=False)
    fake.environment = {}  # the mismatch finish record carries no environment
    _code, _request, run, _output = launch(machine, fake)
    assert run["outcome"] == "practice_mismatch"
    assert list(run["attempts"][0]["cloud"]["cloud_checks"]) == ["practice"]
    assert work._cloud_check_findings(run) == []


@pytest.mark.parametrize("ceiling, ok", [(None, True), ("1000", True), ("0", False), ("x", False),
                                         ("bigger", False)])
def test_the_command_ceiling_may_be_shorter_but_never_longer(ceiling, ok):
    limit = int(cloud.CLOUD_ENVIRONMENT["BASH_MAX_TIMEOUT_MS"])
    value = {None: str(limit), "bigger": str(limit + 1)}.get(ceiling, ceiling)
    usage = {"environment": {"CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1", "BASH_MAX_TIMEOUT_MS": value}}
    assert cloud.environment_check(usage)["ok"] is ok


def test_background_tasks_must_be_off_exactly():
    usage = {"environment": {"CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "0",
                             "BASH_MAX_TIMEOUT_MS": cloud.CLOUD_ENVIRONMENT["BASH_MAX_TIMEOUT_MS"]}}
    assert cloud.environment_check(usage)["ok"] is False


def test_an_artifact_run_is_judged_against_the_profile_setup_verifies(machine, monkeypatch):
    import dispatch_implementer
    monkeypatch.setitem(dispatch_implementer.PROFILES, "artifact_author",
                        {**dispatch_implementer.PROFILES["artifact_author"], "claude": ("claude-other", "low")})
    fake = Fake(report=b"> brief\n\ndraft\n")
    _code, _request, run, _output = launch(machine, fake, stage="artifact", brief=b"> brief\n",
                                            copy={"source_commit": HOLDER}, model="claude-other", effort="low")
    # The launch carried the artifact author's role-resolved settings; the run is still judged
    # against the implementer profile the routine was set up with.
    assert run["attempts"][0]["cloud"]["profile"]["off_profile"] is False
    assert run["attempts"][0]["cloud"]["profile"]["profile"] == "/".join(cloud.builder_profile())


def test_a_stopped_cloud_session_is_a_recovery_source(monkeypatch):
    import work
    import work_recovery
    request = {"route": "cloud", "requested": {"vendor": "claude"}}
    monkeypatch.setattr(work_recovery, "latest_stopped", lambda *_a, **_k: (1, "bundle", request, {}))
    monkeypatch.setattr(work_recovery, "handover_predecessor", lambda *_a: None)
    monkeypatch.setattr(work_recovery.lifecycle, "recovery_session", lambda *_a: "cse_STOPPED")
    monkeypatch.setattr(work_recovery, "validate_target", lambda *_a, **_k: None)
    source = work_recovery.stopped_source(object(), "build")
    assert source.session == "cse_STOPPED"
    monkeypatch.setattr(work_recovery, "latest_stopped",
                        lambda *_a, **_k: (1, "bundle", {"route": "local"}, {}))
    with pytest.raises(work.WorkError, match="invalid session identity"):
        work_recovery.stopped_source(object(), "build")


def test_a_follow_up_after_an_interrupted_first_attempt_uses_the_fired_commit():
    request = {"requested": {"continuity": "fresh"}, "cloud": {"practice": {"commit": INSTALLED}}}
    interrupted = {"attempts": [{"cloud": {}}]}
    assert cloud.loaded_commit([(request, interrupted)], "cse_X")[1] == INSTALLED
    disagreeing = {"attempts": [{"cloud": {"practice_check": {"commit": OLD_PIN}}}]}
    with pytest.raises(cloud.CloudError):
        cloud.loaded_commit([(request, disagreeing)], "cse_X")


def test_a_repair_that_moves_the_branch_must_descend_from_the_fire_tip():
    held = cloud.change_branch_check(TIP, AFTER, [], "diverged", repair=True)
    assert held["ok"] is False and held["checked"] is True
    assert cloud.change_branch_check(TIP, AFTER, [AFTER], "ahead", repair=True)["ok"] is True
    assert cloud.change_branch_check(TIP, TIP, [], "identical", repair=True)["ok"] is True


def test_a_run_outside_auto_mode_fails_and_holds(machine):
    import work
    fake = Fake()
    real_run = fake._run

    def plan_mode():
        real_run()
        usage = json.loads(fake.files["usage.json"])
        usage["permission_mode"] = {"values": ["plan"], "source": "hook-input"}
        fake.files["usage.json"] = json.dumps(usage).encode()

    fake._run = plan_mode
    _code, _request, run, _output = launch(machine, fake)
    assert run["attempts"][0]["cloud"]["cloud_checks"]["permission_mode"]["ok"] is False
    assert "cloud-check:permission_mode" in [f["id"] for f in work._cloud_check_findings(run)]


def test_a_local_tree_that_did_not_follow_holds_the_next_stage(machine):
    import work
    fake = Fake()
    fake.git = lambda root, *arguments: (1, "not a fast-forward") if arguments[0] == "merge" else (0, "")
    _code, _request, run, _output = launch(machine, fake)
    assert run["outcome"] == "success" and fake.comments
    assert run["attempts"][0]["cloud"]["cloud_checks"]["local_tree"]["ok"] is False
    assert "cloud-check:local_tree" in [f["id"] for f in work._cloud_check_findings(run)]


def test_repository_keys_match_without_regard_to_case(tmp_path):
    path = tmp_path / "cloud-builds.json"
    entry = {"routine_id": "trig", "token_file": "t", "setup_record": "s", "set_up_at": "x"}
    path.write_text(json.dumps({"schema_version": 1, "practice": {"repository": PRACTICE},
                                "repositories": {"owner/Product": entry}}))
    assert cloud.route_for("Owner/product#1", path)[0]["routine_id"] == "trig"
    path.write_text(json.dumps({"schema_version": 1, "practice": {"repository": PRACTICE},
                                "repositories": {"owner/Product": entry, "Owner/product": entry}}))
    with pytest.raises(cloud.CloudRefusal, match="more than once"):
        cloud.route_for("Owner/product#1", path)


def test_branch_operations_use_the_selected_remote(machine):
    fake = Fake()
    launch(machine, fake)
    gits = [call[1] for call in fake.calls if call[0] == "git"]
    assert ("push", "product-remote", "HEAD:refs/heads/tradecraft/77-x") in gits
    assert ("fetch", "product-remote", "tradecraft/77-x") in gits
    assert not any("origin" in arguments for arguments in gits)


def test_a_follow_up_uses_the_selected_claude_executable(machine, monkeypatch):
    import vendor_cli
    fake = Fake()
    launch(machine, fake)
    monkeypatch.setattr(vendor_cli, "resolve_command", lambda vendor, path: [path])
    output = machine["records"] / "follow" / "result.md"
    args = argparse.Namespace(
        root=machine["root"], output=output, work=f"{REPO}#77", stage="floor", resume="cse_ABC123",
        settings_source="s", settings_scope="scope", model="claude-opus-5-5", effort="high",
        retry_of=None, holder_session_id=None, lineage_branch="tradecraft/77-x",
        lineage_pull_request=None, timeout_seconds=600, artifact_brief_source="brief",
        artifact_brief=None, claude="C:/tools/claude.exe")
    cloud.run(args, Deadline(5), entry=None, route_source="test", effective_prompt=b"t", prompt=b"t",
              context=b"", artifact_brief=b"", metadata={}, composition={"origin": "holder"},
              settings_sources={"vendor": "v", "model": "m", "effort": "e"},
              validate=lambda *_: {"status": "pass"}, transport=fake, record_root=machine["records"],
              plugin=machine["plugin"], install_path=machine["install"])
    assert {argv[0] for argv, _env in fake.cli_calls[-2:]} == {"C:/tools/claude.exe"}


def test_a_cloud_attempt_counts_against_the_build_budget(machine):
    import run_lifecycle
    _code, request, run, _output = launch(machine, Fake())
    assert request["recipient_allocation_seconds"] == 600
    bounds = run_lifecycle.runtime_bounds(request, run)
    assert bounds["basis"] == "measured recipient runtime" and bounds["upper_seconds"] >= 0


@pytest.mark.parametrize("bad", [{"id": "m1", "model": "x", "input": "10"}, {"id": ["m1"], "model": "x"},
                                 "row"])
def test_malformed_ledger_evidence_fails_the_check_without_raising(bad):
    usage = {"ledger": [bad], "totals_by_model": {}, "files_present": [], "files_read": []}
    assert cloud.ledger_check(usage, None)["ok"] is False


def test_unreadable_transcript_lines_fail_the_check():
    usage = {"ledger": [], "totals_by_model": {}, "files_present": ["main"],
             "files_read": [{"file": "main", "usage_entries": 0, "malformed_lines": 2}]}
    result = cloud.ledger_check(usage, None)
    assert result["ok"] is False and any(f.startswith("unread files") for f in result["faults"])


def test_a_failed_earlier_ledger_is_no_baseline_for_a_priced_delta(machine, monkeypatch):
    fake = Fake()
    launch(machine, fake)
    for path in machine["records"].rglob("*.run.json"):
        record = json.loads(path.read_text())
        record["attempts"][0]["cloud"]["ledger_check"] = {"ok": False, "faults": ["sums: x"]}
        path.write_text(json.dumps(record))
    _code, _request, run, _output = launch(machine, fake, stage="floor", resume="cse_ABC123")
    check = run["attempts"][0]["cloud"]["ledger_check"]
    assert check["ok"] is False and "earlier ledger" in check["faults"][-1]
    price = change_cost._price(change_cost._Attempt(usage=run["attempts"][0]["usage"]),
                               change_cost.load_rates(LIB / "rates.json"))
    assert price["status"] == "unknown"


def test_a_failed_record_write_rolls_back_the_published_output(machine, monkeypatch):
    import dispatch_lifecycle
    monkeypatch.setattr(dispatch_lifecycle.GrowingRun, "finish",
                        lambda self: (_ for _ in ()).throw(OSError("disk full")))
    output = machine["records"] / "rollback" / "result.md"
    args = argparse.Namespace(
        root=machine["root"], output=output, work=f"{REPO}#77", stage="build", resume=None,
        settings_source="s", settings_scope="scope", model="claude-opus-5-5", effort="high",
        retry_of=None, holder_session_id=None, lineage_branch="tradecraft/77-x",
        lineage_pull_request=None, timeout_seconds=600, artifact_brief_source="brief", artifact_brief=None)
    with pytest.raises(OSError):
        cloud.run(args, Deadline(5), entry=machine["entry"], route_source="test", effective_prompt=b"t",
                  prompt=b"t", context=b"", artifact_brief=b"", metadata={}, composition={"origin": "holder"},
                  settings_sources={"vendor": "v", "model": "m", "effort": "e"},
                  validate=lambda *_: {"status": "pass"}, transport=Fake(), record_root=machine["records"],
                  plugin=machine["plugin"], install_path=machine["install"])
    assert not output.exists()


def test_the_owners_ruling_is_the_expected_profile(monkeypatch):
    import launch_settings
    ruled = launch_settings.LaunchSettings("claude-ruled", "max", "ruling", "ruling")
    monkeypatch.setattr(launch_settings, "resolve", lambda *_a, **_k: ruled)
    monkeypatch.setattr(launch_settings, "read_bridge", lambda *_a, **_k: None)
    assert cloud.builder_profile() == ("claude-ruled", "max")
    marked = cloud.cloud_profile({"profile": {"models": ["claude-opus-5-5"], "efforts": ["high"]}},
                                 cloud.builder_profile())
    assert marked["off_profile"] is True and marked["profile"] == "claude-ruled/max"


def test_a_reservation_failure_fires_nothing(machine, monkeypatch):
    def refuse(*_a, **_k):
        raise OSError("disk refused the reservation")
    monkeypatch.setattr(cloud.records, "reserve_bundle", refuse)
    fake = Fake()
    with pytest.raises(OSError):
        launch(machine, fake)
    assert fake.fired == []


def test_a_handover_onto_the_cloud_is_recorded_against_the_cloud_session(machine):
    output = machine["records"] / "handover" / "result.md"
    args = argparse.Namespace(
        root=machine["root"], output=output, work=f"{REPO}#77", stage="build", resume=None,
        settings_source="s", settings_scope="scope", model="claude-opus-5-5", effort="high",
        retry_of=None, holder_session_id=None, lineage_branch="tradecraft/77-x",
        lineage_pull_request=None, timeout_seconds=600, artifact_brief_source="brief", artifact_brief=None,
        handover_from="C:/records/codex/result.md.run.json")
    cloud.run(args, Deadline(5), entry=machine["entry"], route_source="test", effective_prompt=b"t",
              prompt=b"t", context=b"", artifact_brief=b"", metadata={}, composition={"origin": "holder"},
              settings_sources={"vendor": "v", "model": "m", "effort": "e"},
              validate=lambda *_: {"status": "pass"}, transport=Fake(), record_root=machine["records"],
              plugin=machine["plugin"], install_path=machine["install"])
    request = json.loads((output.parent / "result.md.request.json").read_text())
    assert request["handover"]["replacement_session"] == "cse_ABC123"
    assert request["handover"]["from_bundle"] == "C:/records/codex/result.md.run.json"


@pytest.mark.parametrize("answer", ["lost", "no-session"])
def test_an_ambiguous_fire_is_unresolved_and_blocks_a_replacement(machine, answer):
    import run_lifecycle
    fake = Fake()

    def fire(routine, token, text):
        fake.fired.append((routine, token, text))
        if answer == "lost":
            raise OSError("connection reset")
        return 200, "{}"

    fake.fire = fire
    _code, request, run, _output = launch(machine, fake)
    assert run["launch_unresolved"] is True and run["attempts"][0]["launched"] is None
    assert "resolved on claude.ai" in run["attempts"][0]["reason"]
    with pytest.raises(ValueError, match="unresolved"):
        run_lifecycle.recovery_session(request, run)


def test_a_client_error_fire_is_refused_not_unresolved(machine):
    _code, request, run, _output = launch(machine, Fake(fire_status=403))
    assert not run.get("launch_unresolved") and run["attempts"][0]["launched"] is False
    assert request["cloud"]["fire_state"] == "refused"


@pytest.mark.parametrize("status", [500, 502, 504])
def test_a_server_error_fire_is_unresolved_and_blocks_a_replacement(machine, status):
    import run_lifecycle
    _code, request, run, _output = launch(machine, Fake(fire_status=status))
    assert run["launch_unresolved"] is True and run["attempts"][0]["launched"] is None
    assert request["cloud"]["fire_state"] == "unresolved" and "resolved on claude.ai" in run["attempts"][0]["reason"]
    with pytest.raises(ValueError, match="unresolved"):
        run_lifecycle.recovery_session(request, run)


def test_a_second_build_after_a_cloud_build_within_budget_is_not_refused(machine):
    import run_lifecycle
    _code, request, run, _output = launch(machine, Fake())
    account = run_lifecycle.runtime_account([(1, "bundle", request, run)])
    assert account["upper_seconds"] is not None and account["remaining_seconds"] > 0
    assert run_lifecycle.allocation(account, 600) > 0


def test_a_floor_declaration_reads_one_cloud_model_and_effort():
    import work
    single = {"cloud": {"profile": {"model": ["claude-opus-5-5"], "effort": "high"}}}
    assert work._cloud_declared_profile(single) == ("claude-opus-5-5", "high")
    several = {"cloud": {"profile": {"model": ["a", "b"], "effort": ["high", "low"]}}}
    assert work._cloud_declared_profile(several) == (None, None)
    unrecorded = {"cloud": {"profile": {"model": [], "effort": cloud.NO_EFFORT_LABEL}}}
    assert work._cloud_declared_profile(unrecorded) == (None, None)
    assert work._cloud_declared_profile({"vendor": "claude"}) == (None, None)


def test_a_cloud_repairs_merge_instruction_names_the_cloud_practice_path(tmp_path, monkeypatch):
    import types
    import work
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    switch = tmp_path / ".tradecraft" / "cloud-builds.json"
    switch.parent.mkdir(parents=True)
    switch.write_text(json.dumps({"schema_version": 1, "practice": {"repository": PRACTICE},
                                  "repositories": {REPO: {"routine_id": "trig", "token_file": "t",
                                                          "setup_record": "s", "set_up_at": "x"}}}))
    state = types.SimpleNamespace(repo=REPO, issue_number=77)
    script = work._cloud_merge_script(state, "review-disposition", "claude")
    assert script == "/home/user/tradecraft/skills/persist-changes/scripts/persist.py"
    assert work._cloud_merge_script(state, "review-disposition", "codex") is None
    local = types.SimpleNamespace(session="01234567-89ab-cdef-0123-456789abcdef")
    assert work._cloud_merge_script(state, "review-disposition", "claude", local) is None
    obligation = work.MergeObligation("h" * 40, REPO, "main", "p" * 40, (), None)
    assert json.dumps(script) in obligation.prompt("tradecraft/77-x", script)


def test_an_interrupted_fire_leaves_an_in_flight_record_that_refuses_a_second_fire(machine):
    import run_lifecycle
    fake = Fake()

    def fire(routine, token, text):
        raise KeyboardInterrupt

    fake.fire = fire
    with pytest.raises(KeyboardInterrupt):
        launch(machine, fake)
    [request_path] = list(machine["records"].rglob("*.request.json"))
    request = json.loads(request_path.read_text())
    run = json.loads(request_path.with_name("result.md.run.json").read_text())
    assert request["cloud"]["fire_state"] == "in-flight" and run["launch_unresolved"] is True
    with pytest.raises(ValueError, match="unresolved"):
        run_lifecycle.recovery_session(request, run)


def test_an_incomplete_fire_answer_is_unresolved(machine):
    import http.client
    fake = Fake()

    def fire(routine, token, text):
        raise http.client.IncompleteRead(b"{\"claude_code_sess")

    fake.fire = fire
    _code, request, run, _output = launch(machine, fake)
    assert run["launch_unresolved"] is True and request["cloud"]["fire_state"] == "unresolved"


def test_a_handed_over_cloud_session_is_linked_to_its_reservation(machine):
    state_path = machine["tmp"] / "handover.json"
    state_path.write_text(json.dumps({"schema_version": 1, "from_bundle": "codex/result.md.run.json",
                                      "to_vendor": "claude", "phase": "reserved",
                                      "replacement_session": "01234567-89ab-cdef-0123-456789abcdef"}))
    output = machine["records"] / "handed" / "result.md"
    args = argparse.Namespace(
        root=machine["root"], output=output, work=f"{REPO}#77", stage="build", resume=None,
        settings_source="s", settings_scope="scope", model="claude-opus-5-5", effort="high",
        retry_of=None, holder_session_id=None, lineage_branch="tradecraft/77-x",
        lineage_pull_request=None, timeout_seconds=600, artifact_brief_source="brief", artifact_brief=None,
        handover_from="codex/result.md.run.json", handover_state=state_path)
    cloud.run(args, Deadline(5), entry=machine["entry"], route_source="test", effective_prompt=b"t",
              prompt=b"t", context=b"", artifact_brief=b"", metadata={}, composition={"origin": "holder"},
              settings_sources={"vendor": "v", "model": "m", "effort": "e"},
              validate=lambda *_: {"status": "pass"}, transport=Fake(), record_root=machine["records"],
              plugin=machine["plugin"], install_path=machine["install"])
    request = json.loads((output.parent / "result.md.request.json").read_text())
    # The entrance accepts a follow-up into the session only when the reservation names it.
    reservation = json.loads(state_path.read_text())
    assert reservation["replacement_session"] == "cse_ABC123" and reservation["phase"] == "running"
    assert request["handover"]["state"] == str(state_path)
    assert request["handover"]["replacement_session"] == "cse_ABC123"


def test_an_interrupted_relink_keeps_the_session_the_fire_returned(machine, monkeypatch):
    import run_lifecycle
    state_path = machine["tmp"] / "handover.json"
    state_path.write_text(json.dumps({"schema_version": 1, "from_bundle": "codex/result.md.run.json",
                                      "to_vendor": "claude", "phase": "reserved",
                                      "replacement_session": "01234567-89ab-cdef-0123-456789abcdef"}))

    def interrupted(*_a):
        raise KeyboardInterrupt

    monkeypatch.setattr(cloud, "_relink_handover", interrupted)
    output = machine["records"] / "relink" / "result.md"
    args = argparse.Namespace(
        root=machine["root"], output=output, work=f"{REPO}#77", stage="build", resume=None,
        settings_source="s", settings_scope="scope", model="claude-opus-5-5", effort="high",
        retry_of=None, holder_session_id=None, lineage_branch="tradecraft/77-x",
        lineage_pull_request=None, timeout_seconds=600, artifact_brief_source="brief", artifact_brief=None,
        handover_from="codex/result.md.run.json", handover_state=state_path)
    with pytest.raises(KeyboardInterrupt):
        cloud.run(args, Deadline(5), entry=machine["entry"], route_source="test", effective_prompt=b"t",
                  prompt=b"t", context=b"", artifact_brief=b"", metadata={}, composition={"origin": "holder"},
                  settings_sources={"vendor": "v", "model": "m", "effort": "e"},
                  validate=lambda *_: {"status": "pass"}, transport=Fake(), record_root=machine["records"],
                  plugin=machine["plugin"], install_path=machine["install"])
    request = json.loads((output.parent / "result.md.request.json").read_text())
    run = json.loads((output.parent / "result.md.run.json").read_text())
    assert request["cloud"]["session_id"] == "cse_ABC123"
    assert request["handover"]["replacement_session"] == "cse_ABC123"
    with pytest.raises(ValueError, match="unresolved"):
        run_lifecycle.recovery_session(request, run)


def test_only_the_tree_releases_the_local_tree_hold(tmp_path, monkeypatch):
    import subprocess
    import types
    import work
    from source_claims import Marker
    root = tmp_path / "tree"
    root.mkdir()
    for command in (["init", "-q"], ["-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q",
                                     "--allow-empty", "-m", "base"]):
        subprocess.run(["git", "-C", str(root), *command], check=True, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True,
                          text=True, check=True, stdin=subprocess.DEVNULL).stdout.strip()
    dispatch = "d" * 32
    request = {"dispatch_id": dispatch, "stage": "build", "root": str(root),
               "launched_at": "2026-11-06T10:00:00Z", "write_bound": {"route": "cloud"}}

    def run_with(tip, practice=False):
        checks = {"local_tree": {"ok": False, "reason": "not a fast-forward", "tip": tip}}
        if practice:
            checks["practice"] = {"ok": False, "reason": "practice clone at the wrong commit"}
        return {"completed_at": "2026-11-06T11:00:00Z", "launch_comparison": {"status": "cloud-not-run"},
                "attempts": [{"cloud": {"report_branch": "claude/r", "cloud_checks": checks}}]}

    def account(*names):
        body = ("```json\n" + json.dumps({"schema_version": 1, "findings": [
            {"id": f"cloud-check:{name}", "party": "cloud-check", "basis": f"{name}: the holder read it"}
            for name in names]}) + "\n```\n")
        return Marker("launch-account", {"dispatch": dispatch}, body, "holder", surface="issue-comment",
                      source_id="1", timestamp="2026-11-06T12:00:00Z", raw_attributes=f"dispatch={dispatch}")

    state = types.SimpleNamespace(record_root=tmp_path, repo=REPO, issue_number=77, instalment=None,
                                  config=types.SimpleNamespace(marker_producers=frozenset({"holder"})))
    monkeypatch.setattr(work, "_launch_accounts", lambda _state: [account("local_tree")])
    stale = run_with("f" * 40)
    monkeypatch.setattr(work.lifecycle, "launch_bundles", lambda *_a: [(1, "b", request, stale)])
    assert work._evaluate_launch_findings(state)["status"] == "held"  # an account can't release it
    current = run_with(head)
    monkeypatch.setattr(work.lifecycle, "launch_bundles", lambda *_a: [(1, "b", request, current)])
    assert work._evaluate_launch_findings(state)["status"] == "clear"

    # A comment naming the local-tree finding doesn't release it while the tree lacks the tip.
    monkeypatch.setattr(work, "_launch_accounts", lambda _state: [account("local_tree", "practice")])
    stale = run_with("f" * 40, practice=True)
    monkeypatch.setattr(work.lifecycle, "launch_bundles", lambda *_a: [(1, "b", request, stale)])
    entry = work._evaluate_launch_findings(state)["bundles"][0]
    assert entry["state"] == "account-required"
    assert entry["owed"] == [{"id": "cloud-check:local_tree", "item": "cloud_checks.local_tree",
                              "path": "claude/r", "change": "failed", "released_by": "tree"}]
    # Once the tree has it, the comment that named it while owed still counts.
    current = run_with(head, practice=True)
    monkeypatch.setattr(work.lifecycle, "launch_bundles", lambda *_a: [(1, "b", request, current)])
    entry = work._evaluate_launch_findings(state)["bundles"][0]
    assert entry["state"] == "accounted" and entry["owed"] == [] and entry["uncounted"] == []
    assert [value["source"] for value in entry["accounts"]] == ["issue-comment:1"]


def test_a_cloud_resume_names_its_recorded_practice_path_after_the_switch_is_removed(tmp_path, monkeypatch):
    import types
    import work
    monkeypatch.setattr(Path, "home", lambda: tmp_path)  # no switch entry at all
    state = types.SimpleNamespace(repo=REPO, issue_number=77)
    resumed = types.SimpleNamespace(session="cse_STARTED", request={
        "cloud": {"practice": {"repository": "Adopter/practice-fork"}}})
    assert work._cloud_merge_script(state, "review-disposition", "claude", resumed) == \
        "/home/user/practice-fork/skills/persist-changes/scripts/persist.py"
    assert work._cloud_merge_script(state, "review-disposition", "claude") is None


def test_the_wait_never_sleeps_past_the_allocation(machine, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(cloud.time, "monotonic", lambda: clock[0])
    fake = Fake()
    fake.files = {}
    slept = []

    def fire(routine, token, text):
        return 200, json.dumps({"claude_code_session_id": "cse_WAITING",
                                "claude_code_session_url": "https://claude.ai/code/cse_WAITING"})

    def sleep(seconds):
        slept.append(seconds)
        clock[0] += seconds

    fake.fire, fake.sleep = fire, sleep
    _code, _request, run, _output = launch(machine, fake, polls=50, timeout_seconds=45)
    assert run["outcome"] == "interrupted"
    assert sum(slept) <= 45 + 1e-9  # the caller's deadline still had time; the allocation ended the wait


class Pushed(Fake):
    """A remote that rejects a push which isn't a fast-forward, and a local tree with its own tip."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.local, self.diverged = TIP, False

    def github(self, method, path, body=None):
        if f"/compare/{AFTER}..." in path:
            return 200, {"status": "identical", "commits": []}
        return super().github(method, path, body)

    def git(self, root, *arguments):
        self.calls.append(("git", arguments, None))
        if arguments[0] == "merge":
            if self.diverged:
                return 1, "fatal: Not possible to fast-forward, aborting."
            self.local = self.change_tip
        if arguments[0] == "push" and self.local != self.change_tip:
            return 1, "! [rejected] HEAD -> tradecraft/77-x (fetch first)"
        return 0, ""

    def cli(self, argv, env):
        tip = self.change_tip
        result = super().cli(argv, env)
        if argv[1:3] == ["auth", "status"]:
            self.change_tip = tip  # a login check moves no branch
        return result


@pytest.mark.parametrize("diverged", [False, True])
def test_a_follow_up_after_an_interrupted_build_that_pushed_levels_the_tree_first(machine, monkeypatch, diverged):
    fake = Pushed()
    monkeypatch.setattr(cloud.records, "git_revision", lambda _root: fake.local)
    _code, _request, run, _output = launch(machine, fake, polls=0)
    assert run["outcome"] == "interrupted" and fake.change_tip == AFTER and fake.local == TIP
    fake.diverged = diverged
    sends = len(fake.cli_calls)
    _code, request, run, _output = launch(machine, fake, resume="cse_ABC123")
    if diverged:
        assert run["outcome"] == "refused" and TIP in run["attempts"][0]["reason"]
        assert AFTER in run["attempts"][0]["reason"]
        assert len(fake.cli_calls) == sends + 1  # the login check only; nothing was sent
    else:
        assert request["cloud"]["local_fast_forward"] == {"from": TIP, "to": AFTER}
        assert request["cloud"]["change_branch"]["tip_at_fire"] == AFTER


def test_a_failed_cloud_check_is_accounted_by_the_cloud_check_party():
    import work

    def body(identity, basis):
        return ("```json\n" + json.dumps({"schema_version": 1, "findings": [
            {"id": identity, "party": "cloud-check", "basis": basis}]}) + "\n```\n")

    verified = "skip_ci: the holder read both commits; each is the builder's report, no workflow ran"
    assert work.launch_account_payload(body("cloud-check:skip_ci", verified))["findings"][0]["party"] == "cloud-check"
    for identity, basis in (("cloud-check:skip_ci", "the holder looked"), ("unrecorded", verified)):
        with pytest.raises(ValueError, match="cloud-check account"):
            work.launch_account_payload(body(identity, basis))


def test_a_mismatch_stopped_before_any_turn_records_its_profile_as_not_run(machine):
    fake = Fake(practice_ok=False)
    real_run = fake._run

    def hook_blocked():
        # The prompt hook wrote the finish record and the model took no turn.
        real_run()
        usage = json.loads(fake.files["usage.json"])
        fake.files["usage.json"] = json.dumps({key: usage[key] for key in ("practice_check", "report_blob")}
                                              | {"finish": "practice-mismatch"}).encode()

    fake._run = hook_blocked
    _code, _request, run, _output = launch(machine, fake, polls=2)
    profile = run["attempts"][0]["cloud"]["profile"]
    assert run["outcome"] == "practice_mismatch"
    assert profile["off_profile"] is False and profile["status"] == "not run"
    assert profile["reason"] == cloud.NOT_RUN_REASON and profile["permission_mode"] == ["not run"]
    # Without a mismatch, a usage record with no turn is still marked.
    assert cloud.cloud_profile({"practice_check": {"ok": True}})["off_profile"] is True


def test_the_entrance_and_the_launcher_read_one_routing_decision(tmp_path, monkeypatch):
    import types
    import work
    monkeypatch.setattr(Path, "home", lambda: tmp_path)  # the switch entry is gone
    state = types.SimpleNamespace(repo=REPO, issue_number=77, record_root=tmp_path / "records")
    # A cse_ resume found only through a builder-session marker: no bundle, so no request.
    for stage in ("review-disposition", "floor", "build"):
        assert cloud.launch_route(stage, "cse_MARKER", f"{REPO}#77") is not None
        assert work._cloud_practice(state, stage, "claude", None, "cse_MARKER") == cloud.DEFAULT_PRACTICE
        assert work._cloud_merge_script(state, stage, "claude", None, "cse_MARKER").startswith("/home/user/")
    # A bundle that names no practice repository: the session's own starting record does.
    started = tmp_path / "records" / "start"
    started.mkdir(parents=True)
    (started / "result.md.request.json").write_text(json.dumps(
        {"cloud": {"session_id": "cse_MARKER", "practice": {"repository": "Adopter/practice-fork"}}}))
    (started / "result.md.run.json").write_text("{}")
    bare = types.SimpleNamespace(session="cse_MARKER", request={"cloud": {}})
    assert work._cloud_practice(state, "review-disposition", "claude", bare) == "Adopter/practice-fork"
    # A UUID resume is local for both.
    uuid = "01234567-89ab-cdef-0123-456789abcdef"
    assert cloud.launch_route("review-disposition", uuid, f"{REPO}#77") is None
    assert work._cloud_practice(state, "review-disposition", "claude", None, uuid) is None


def test_a_repair_change_branch_reason_names_its_stage():
    assert cloud.change_branch_check(TIP, TIP, [], "identical", repair=True, stage="floor")["reason"] \
        == "a floor turn can rightly make no commit"
