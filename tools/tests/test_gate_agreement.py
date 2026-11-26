"""Run change-proof's gate, copied at a named commit, over proofs the entrance composes in this run.

The entrance and the gate are two implementations of one proof contract. Each case stands up one in-process
GitHub over a real Git history, has the entrance collect it and publish its proof there through its own publish
step, then has the copied gate read the same GitHub. A red means the entrance under test composes a proof the
copied gate refuses; `tools/gate/README.md#what-a-red-means` says what a session may and may not do about it.
"""
from __future__ import annotations

import base64
from datetime import timedelta
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import urllib.parse

import pytest

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "tools" / "gate"
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(ROOT / "lib" / "tests"))
import route_fixture  # noqa: E402
import work  # noqa: E402

REPO, ISSUE, NUMBER, PRODUCER = route_fixture.REPO, route_fixture.ISSUE, 7, route_fixture.PRODUCER
OBSERVED = route_fixture.START + timedelta(days=1)
POLICY, CONFIG = ".github/change-proof.json", ".tradecraft/work.json"
WORKFLOW, JOB = ".github/workflows/ci.yml", "lint-and-test"
# A closing test fails unless each ran and passed in this session.
CASES = ("builder-report-at-head", "builder-report-at-earlier-commit", "relay-use-marker", "mechanical-lane",
         "no-use")
PASSED: set[str] = set()
NAMED_SOURCES: dict[str, set[str]] = {"use": set(), "floor": set()}
RED = ("The entrance under test composed a proof the copied gate refuses. Where this change meant to alter what a "
       "proof names, the gate must change first: the builder returns it to its holder as a gate change owed, and the "
       "holder tells the Steward. Otherwise it is a defect: repair the entrance. Never edit a case or the copy to "
       "pass; refresh the copy only in this change's diff, to a commit already on change-proof's main. "
       "tools/gate/README.md says more.")


def source_record() -> dict:
    return json.loads((GATE / "source.json").read_bytes())


def test_the_copy_is_the_recorded_gate_script():
    recorded = source_record()
    copy = GATE / "check.py"
    assert copy.is_file(), f"{copy} is absent; restore it from {recorded['repository']} at {recorded['commit']}"
    data = copy.read_bytes()
    assert (len(data), hashlib.sha256(data).hexdigest()) == (recorded["bytes"], recorded["sha256"]), (
        f"{copy} is not {recorded['path']} at {recorded['repository']} {recorded['commit']}: refresh it from a "
        "commit already on change-proof's main, in this change's diff, never by editing it")


@pytest.fixture(scope="module")
def gate():
    copy = GATE / "check.py"
    if not copy.is_file():
        pytest.fail(f"{copy} is absent, so no case can run", pytrace=False)
    spec = importlib.util.spec_from_file_location("change_proof_gate_copy", copy)
    module = importlib.util.module_from_spec(spec)
    # The script's dataclasses resolve their annotations through their module, so it is registered first.
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[spec.name]
        raise
    return module


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """No case reaches the network or starts `gh`: both readers' GitHub is the stand-in."""
    def refused(*_args, **_kwargs):
        raise OSError("test_gate_agreement: no network; the cases' GitHub is in-process")

    monkeypatch.setattr(socket.socket, "connect", refused)
    monkeypatch.setattr(socket, "create_connection", refused)
    real = subprocess.run

    def run(command, *args, **kwargs):
        if isinstance(command, (list, tuple)) and command and Path(str(command[0])).stem.lower() == "gh":
            raise AssertionError(f"test_gate_agreement: gh was started: {command}")
        return real(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)


def git(root: Path, *words: str) -> str:
    return route_fixture.git(root, *words)


class GitHub:
    """One case's GitHub, served to the entrance and the copied gate alike from records and a real Git history.

    A read it does not serve fails the case, so neither reader can pass on a record the stand-in never held.
    """

    def __init__(self, root: Path, comments: list, not_found: type[Exception]):
        self.root, self.issue_comments, self.not_found = root, comments, not_found
        self.pr_comments: list[dict] = []
        self.check_runs: list[dict] = []
        self.runs: dict[int, dict] = {}
        self.jobs: dict[int, list[dict]] = {}
        self.unserved: list[str] = []
        self.history: dict[tuple, object] = {}
        self.issue = {"number": ISSUE, "state": "open", "body": "", "labels": [], "user": {"login": PRODUCER},
                      "html_url": f"https://github.invalid/{REPO}/issues/{ISSUE}"}
        self.pr: dict = {}

    def open_pull_request(self, base: str, head: str) -> None:
        files = [{"filename": path, "status": "modified"}
                 for path in git(self.root, "diff", "--name-only", f"{base}...{head}").splitlines()]
        self.files = files
        self.pr = {"number": NUMBER, "state": "open", "draft": False, "merged_at": None, "mergeable": True,
                   "mergeable_state": "clean", "changed_files": len(files), "user": {"login": PRODUCER},
                   "body": "**Path departures:** none; the expected path ran.\n\nCloses #5\n",
                   "html_url": f"https://github.invalid/{REPO}/pull/{NUMBER}",
                   "head": {"sha": head, "ref": "tradecraft/5-fixture", "repo": {"full_name": REPO, "id": 1}},
                   "base": {"sha": base, "ref": "main", "repo": {"full_name": REPO, "id": 1}}}

    def declared_ci(self) -> None:
        """One successful run of the declared floor job at the head, as GitHub Actions reports it."""
        head, at = self.pr["head"]["sha"], (route_fixture.START + timedelta(hours=1)).isoformat()
        run = {"id": 91, "path": WORKFLOW, "repository": {"full_name": REPO}, "head_sha": head, "workflow_id": 71,
               "check_suite_id": 191, "check_suite_node_id": "CS_191", "run_attempt": 1, "status": "completed",
               "conclusion": "success", "created_at": at, "run_started_at": at,
               "html_url": f"https://github.com/{REPO}/actions/runs/91", "referenced_workflows": [],
               "event": "pull_request"}
        self.runs[91] = run
        self.jobs[91] = [{"id": 1081, "run_id": 91, "head_sha": head, "run_attempt": 1, "name": JOB,
                          "check_run_url": f"https://api.github.com/repos/{REPO}/check-runs/81",
                          "status": "completed", "conclusion": "success", "started_at": at, "completed_at": at}]
        self.check_runs.append({"id": 81, "name": JOB, "head_sha": head, "app": {"id": 15368, "slug": "github-actions"},
                                "check_suite": {"id": 191},
                                "details_url": f"https://github.com/{REPO}/actions/runs/91/job/1081",
                                "status": "completed", "conclusion": "success", "started_at": at,
                                "completed_at": at})

    # --- reads ---------------------------------------------------------------------------------------------

    def get(self, endpoint: str, *, paginate: bool = False) -> object:
        path, _, query = endpoint.partition("?")
        params = {name: value for name, value in urllib.parse.parse_qsl(query) if name != "per_page"}
        if path == f"repos/{REPO}/branches/main/protection":
            raise self.not_found("the base branch is unprotected, as GitHub answers it")  # a 404 GitHub gives
        value = self._serve(path, params)
        if value is None:
            self.unserved.append(endpoint)
            raise self.not_found(f"the stand-in GitHub serves no {endpoint}")
        if paginate:
            return list(value) if isinstance(value, list) else [value]
        return value

    def _serve(self, path: str, params: dict) -> object:
        prefix = f"repos/{REPO}/"
        if path == "user":
            return {"login": PRODUCER}
        if not path.startswith(prefix):
            return None
        path = path[len(prefix):]
        head, base = self.pr["head"]["sha"], self.pr["base"]["sha"]
        simple = {f"issues/{ISSUE}": self.issue, f"issues/{ISSUE}/comments": self.issue_comments,
                  f"issues/{ISSUE}/timeline": [], f"pulls/{NUMBER}": self.pr,
                  f"issues/{NUMBER}/comments": self.pr_comments, f"pulls/{NUMBER}/reviews": [],
                  f"pulls/{NUMBER}/comments": [], f"pulls/{NUMBER}/files": self.files,
                  "git/ref/heads/main": {"object": {"sha": base}}, "rules/branches/main": [],
                  f"commits/{head}/check-runs": {"total_count": len(self.check_runs), "check_runs": self.check_runs}}
        if path in simple:
            return simple[path]
        if path == "actions/runs" and params.get("head_sha") == head:
            runs = list(self.runs.values())
            return {"total_count": len(runs), "workflow_runs": runs}
        parts = path.split("/")
        if parts[:2] == ["actions", "runs"] and len(parts) in (3, 4) and parts[2].isdigit():
            identity = int(parts[2])
            if len(parts) == 3:
                return self.runs.get(identity)
            if parts[3] == "jobs" and identity in self.jobs:
                return {"total_count": len(self.jobs[identity]), "jobs": self.jobs[identity]}
            return None
        if path.startswith("contents/"):
            return self._contents(urllib.parse.unquote(path[len("contents/"):]), params.get("ref", ""))
        if path.startswith("compare/"):
            return self._compare(*urllib.parse.unquote(path[len("compare/"):]).split("...", 1))
        if path.startswith("commits/") and len(parts) == 2:
            return self._commit(parts[1])
        if path.startswith("git/trees/") and len(parts) == 3:
            if self._revision(parts[2]) is None:
                return None
            entries = self._text("ls-tree", "-r", parts[2]).splitlines()
            return {"truncated": False, "tree": [{"path": line.split("\t", 1)[1], "type": "blob"}
                                                 for line in entries]}
        return None

    def _git(self, *words: str) -> object:
        """A Git read of the history, kept: every read names full commit ids, which never change."""
        if words not in self.history:
            try:
                self.history[words] = subprocess.run(["git", "-C", str(self.root), *words], check=True,
                                                     capture_output=True, stdin=subprocess.DEVNULL).stdout
            except subprocess.CalledProcessError:
                self.history[words] = None
        return self.history[words]

    def _text(self, *words: str) -> str:
        return self._git(*words).decode("utf-8").strip()

    def _revision(self, revision: str) -> str | None:
        if work.HEAD_SHA.fullmatch(revision or "") is None:
            return None
        found = self._git("rev-parse", "--verify", "--quiet", revision + "^{commit}")
        return found.decode("ascii").strip() if found is not None else None

    def _contents(self, path: str, ref: str) -> object:
        if self._revision(ref) is None:
            return None
        data = self._git("show", f"{ref}:{path}")
        if data is None:
            return None
        return {"type": "file", "path": path, "encoding": "base64", "content": base64.b64encode(data).decode()}

    def _commit(self, revision: str) -> object:
        sha = self._revision(revision)
        if sha is None:
            return None
        parents = self._text("rev-list", "--parents", "-n", "1", sha).split()[1:]
        names = self._text("diff-tree", "--no-commit-id", "-r", "--name-only", "--root", sha).splitlines()
        return {"sha": sha, "parents": [{"sha": parent} for parent in parents],
                "files": [{"filename": name, "status": "modified"} for name in names]}

    def _compare(self, first: str, second: str) -> object:
        if self._revision(first) is None or self._revision(second) is None:
            return None
        merge_base = self._text("merge-base", first, second)
        ahead = self._text("rev-list", "--reverse", f"{first}..{second}").split()
        behind = self._text("rev-list", f"{second}..{first}").split()
        status = ("identical" if not ahead and not behind else "ahead" if not behind
                  else "behind" if not ahead else "diverged")
        return {"status": status, "ahead_by": len(ahead), "behind_by": len(behind),
                "merge_base_commit": {"sha": merge_base}, "commits": [{"sha": sha} for sha in ahead],
                "total_commits": len(ahead)}

    def closing_pull_requests(self, _query: str, _variables: dict) -> object:
        return {"data": {"repository": {"issue": {"closedByPullRequestsReferences": {
            "nodes": [{"number": NUMBER, "repository": {"nameWithOwner": REPO}}],
            "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}}

    def workflow_run_files(self, _query: str, variables: dict) -> object:
        nodes = [{"id": run["check_suite_node_id"], "workflowRun": {
                    "databaseId": run["id"], "workflow": {"databaseId": run["workflow_id"]},
                    "file": {"path": run["path"], "repositoryName": REPO}}}
                 for run in self.runs.values() if run["check_suite_node_id"] in variables["ids"]]
        return {"data": {"nodes": nodes}}

    # --- the one write: the entrance's proof comment ------------------------------------------------------

    def post(self, endpoint: str, payload: dict) -> object:
        if endpoint != f"repos/{REPO}/issues/{NUMBER}/comments":
            raise AssertionError(f"the entrance wrote {endpoint}; only its proof comment is expected")
        identity = 900 + len(self.pr_comments)
        comment = {"id": identity, "body": payload["body"], "user": {"login": PRODUCER},
                   "created_at": (OBSERVED - timedelta(minutes=1)).isoformat(),
                   "html_url": f"https://github.invalid/{REPO}/pull/{NUMBER}#issuecomment-{identity}"}
        self.pr_comments.append(comment)
        return comment


class Case:
    """One stand-in change: its holder checkout with Git history, its issue records and its launch records."""

    def __init__(self, tmp_path: Path, gate, *, mechanical: bool = False, declared: bool = False):
        self.fixture = route_fixture.Fixture(tmp_path, mechanical=mechanical)
        self.root = self.fixture.holder
        # A read the stand-in doesn't serve is a 404 to each reader, caught by that reader's own not-found handling.
        not_found = type("NotServed", (work.WorkError, gate.GitHubNotFound), {"http_status": 404})
        self.github = GitHub(self.root, self.fixture.comments, not_found)
        rules = {**route_fixture.RULES, **({"floor": {"jobs": [{"workflow": WORKFLOW, "job": JOB}]}}
                                           if declared else {})}
        self.rules = rules
        files = {".gitattributes": "* text=auto eol=lf\n", POLICY: json.dumps(rules, indent=2) + "\n",
                 CONFIG: json.dumps({"schema_version": 1, "product_repositories": [], "connected_reviewers": [],
                                     "marker_producers": [PRODUCER]}, indent=2) + "\n",
                 "skill/SKILL.md": "how an adopter loads the job\n"}
        self.write(files)
        git(self.root, "init", "-q", "-b", "main")
        self.base = self.commit("base")
        git(self.root, "checkout", "-q", "-b", "tradecraft/5-fixture")

    def write(self, files: dict[str, str]) -> None:
        for path, text in files.items():
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            (self.root / path).write_bytes(text.encode("utf-8"))

    def commit(self, message: str, files: dict[str, str] | None = None) -> str:
        self.write(files or {})
        git(self.root, "add", "--all")
        git(self.root, "commit", "-q", "-m", message)
        return git(self.root, "rev-parse", "HEAD")

    def open(self, head: str) -> None:
        self.github.open_pull_request(self.base, head)
        self.fixture.pull_request(head, route_fixture.CLEAR)
        self.fixture.pr.update(self.github.pr)

    def builder(self) -> str:
        """A hand-started builder of the change, recorded as `run handoff --by-hand` records it."""
        return self.fixture.hand_stretch(self.root)["dispatch_id"]

    def use_report(self, builder: str) -> int:
        report, _dispatch = self.fixture.use_report(self.fixture.state(), self.root, builder)
        return report

    def post(self, body: str, *, on_pull_request: bool = False) -> int:
        if not on_pull_request:
            return self.fixture.post(body)
        comment = {"id": 800 + len(self.github.pr_comments), "body": body, "user": {"login": PRODUCER},
                   "created_at": (route_fixture.START + timedelta(hours=2)).isoformat()}
        comment["html_url"] = f"https://github.invalid/{REPO}/pull/{NUMBER}#issuecomment-{comment['id']}"
        self.github.pr_comments.append(comment)
        return comment["id"]

    def publish(self, monkeypatch) -> tuple[str, list[dict]]:
        """The entrance's proof for this state, composed and posted through its own publish step."""
        # What the stand-in cannot hold is stood in for: the cold reader's `clean` is a launched seat's bundle,
        # and reach is read from the holder's own launch turns. Neither is what a proof names.
        monkeypatch.setattr(work, "_cold_reading_hold", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(work, "_evaluate_reach", lambda checked: setattr(checked, "reach", {"state": "not-due"}))
        reports: list[dict] = []
        monkeypatch.setattr(work, "_emit_report", lambda payload, *_args, **_kwargs: reports.append(payload))
        published: list[str] = []
        publish = work._publish_proof_comment

        def recorded(transport, state, body, head):
            published.append(body)
            return publish(transport, state, body, head)

        monkeypatch.setattr(work, "_publish_proof_comment", recorded)
        policy = self.root / POLICY
        rules = work.load_use_rules(policy)
        config = work.load_work_config(self.root)
        state = work._read_policy_state(self.github, REPO, ISSUE, config, rules, str(policy),
                                        policy_bytes=policy.read_bytes())
        state.record_root = self.fixture.store
        state.holder_root = self.root
        snapshot = work._capture_policy_snapshot(self.root, REPO, policy, enforce_clean=True)
        state.policy_sources = snapshot.sources
        work._evaluate_raw_output(state, rules, str(policy))
        code = work._publish_current_proof(self.github, state, self.root, rules, policy, snapshot)
        assert code == 0 and len(published) == 1, ("the entrance published no proof", reports)
        return published[0], reports

    def judge(self, gate) -> tuple[int, str]:
        output = io.StringIO()
        code = gate.run({"GITHUB_TOKEN": "stand-in", "GITHUB_REPOSITORY": REPO,
                         "PULL_REQUEST_NUMBER": str(NUMBER), "PULL_REQUEST_HEAD_SHA": self.github.pr["head"]["sha"]},
                        transport=self.github, output=output, observed_at=OBSERVED)
        return code, output.getvalue()


def floor_marker(head: str) -> str:
    return f"<!-- tradecraft:floor:v1 head={head} status=pass -->\n\n```\n{route_fixture.FLOOR}\n```\n\n1 passed\n"


JOB_FILE = {"job/job.md": "run the job\n"}
NOTE_FILE = {"notes.md": "a note no use buys\n"}


def builder_report_at_head(tmp_path, gate) -> Case:
    case = Case(tmp_path, gate)
    head = case.commit("job", JOB_FILE)
    case.open(head)
    case.use_report(case.builder())
    case.post(floor_marker(head))
    return case


def builder_report_at_earlier_commit(tmp_path, gate) -> Case:
    case = Case(tmp_path, gate)
    earlier = case.commit("job", JOB_FILE)
    case.open(earlier)
    case.use_report(case.builder())
    head = case.commit("note", NOTE_FILE)
    case.open(head)
    case.post(floor_marker(head))
    case.earlier = earlier
    return case


def relay_use_marker(tmp_path, gate) -> Case:
    case = Case(tmp_path, gate)
    case.post(route_fixture.RELAY_ASK)
    head = case.commit("job", JOB_FILE)
    case.open(head)
    case.post(f"<!-- tradecraft:use:v1 head={head} status=pass changed=false staffing_status=qualified -->\n\n"
              "The job ran as an adopter runs it.\n", on_pull_request=True)
    case.post(floor_marker(head), on_pull_request=True)
    return case


def mechanical_lane(tmp_path, gate) -> Case:
    case = Case(tmp_path, gate, mechanical=True, declared=True)
    head = case.commit("job", JOB_FILE)
    case.open(head)
    case.github.declared_ci()
    return case


def no_use(tmp_path, gate) -> Case:
    case = Case(tmp_path, gate, declared=True)
    head = case.commit("note", NOTE_FILE)
    case.open(head)
    case.github.declared_ci()
    return case


def payload(body: str) -> dict:
    """The proof document a proof comment carries, as the gate reads it."""
    return json.loads(body.split("```json\n", 1)[1].split("\n```", 1)[0])


BUILDERS = {"builder-report-at-head": builder_report_at_head,
            "builder-report-at-earlier-commit": builder_report_at_earlier_commit,
            "relay-use-marker": relay_use_marker, "mechanical-lane": mechanical_lane, "no-use": no_use}


@pytest.mark.parametrize("name", CASES)
def test_the_copied_gate_passes_the_proof_the_entrance_composed(name, tmp_path, gate, monkeypatch):
    case = BUILDERS[name](tmp_path, gate)
    try:
        body, _reports = case.publish(monkeypatch)
        code, output = case.judge(gate)
    finally:
        case.fixture.stop()
    read = [item["body"] for item in case.github.pr_comments if "tradecraft:proof:v1" in item["body"]]
    assert read == [body], "the gate must read exactly the body the entrance handed its publish step"
    missing = [line for line in output.splitlines() if line.startswith("missing:")]
    assert code == 0 and output.startswith("change-proof: PASS"), (
        f"{name}: {RED}\n" + "\n".join(missing or output.splitlines()))
    assert not case.github.unserved, f"{name}: reads the stand-in does not serve: {case.github.unserved}"
    lines = output.splitlines()
    document = payload(body)
    for kind in ("use", "floor"):
        source = document[kind]["source"]
        if source is not None:
            # Read by the gate's own parser: the marker a source opens with is what the gate judges it by.
            records = case.github.issue_comments if source["kind"] == "issue-comment" else case.github.pr_comments
            found = gate.markers([next(item for item in records if item["id"] == source["id"])])
            NAMED_SOURCES[kind].add(found[0].name if found else None)
    if name == "builder-report-at-head":
        assert any(line.startswith("verified: trusted policy requires use and the builder's use report "
                                   f"issue-comment #") and line.endswith("is current-head") for line in lines), output
    if name == "builder-report-at-earlier-commit":
        assert any(line.startswith("verified: trusted policy requires use and the builder's use report ")
                   and line.endswith(f"at {case.earlier} remains applicable") for line in lines), output
    if name == "relay-use-marker":
        assert "verified: trusted policy requires use and the public use source is current-head" in lines, output
    PASSED.add(name)


SHARED = ROOT / "skills" / "work" / "references" / "proof-fixtures" / "v1-builder-use-report.json"


def test_the_shared_use_report_cases_read_at_the_copied_gate_as_expected(tmp_path, gate, monkeypatch):
    """Each shared case's comment stands as the use report a builder-route proof names, as the fixtures' README says."""
    shared = json.loads(SHARED.read_bytes())
    case = builder_report_at_head(tmp_path, gate)
    try:
        body, _reports = case.publish(monkeypatch)
    finally:
        case.fixture.stop()
    head = case.github.pr["head"]["sha"]
    document = payload(body)
    report = next(item for item in case.github.issue_comments if item["id"] == document["use"]["source"]["id"])
    proof_comment = next(item for item in case.github.pr_comments if item["body"] == body)
    wrong = []
    for item in shared["cases"]:
        comment, expected = item["comment"], item["expected"]
        author = PRODUCER if comment["author"] in shared["marker_producers"] else comment["author"]
        report.update(body=comment["body"].replace(shared["evidence_head"], head), user={"login": author})
        named = json.loads(json.dumps(document))
        named["use"]["source"]["author"] = author
        proof_comment["body"] = work.proof_document.document(named)
        code, output = case.judge(gate)
        lines = output.splitlines()
        refusals = [line for line in lines if line.startswith("missing: an authorized valid public use source")]
        if expected["result"] == "counts":
            met = code == 0 and not refusals and any("the builder's use report" in line for line in lines)
        else:
            wanted = [f"opens with {expected['opens_with']}; "] + [
                fact.replace(shared["evidence_head"], head) for fact in expected["facts"]]
            met = code == 1 and len(refusals) == 1 and all(part in refusals[0] for part in wanted)
        if not met:
            wrong.append(f"{item['name']} (expected {expected}): " + " | ".join(refusals or lines))
    assert not wrong, "shared use-report cases the copied gate reads otherwise:\n" + "\n".join(wrong)


def test_the_marker_reference_names_every_report_attribute_the_gate_reads(gate):
    text = (ROOT / "skills" / "work" / "references" / "markers.md").read_text(encoding="utf-8")
    section = text.split("## `check-report`", 1)[1].split("## `", 1)[0]
    passage = section.partition("**What the required gate reads of a use report.**")[2]
    assert passage, "markers.md's check-report section says nothing of what the required gate reads of a report"
    unnamed = sorted(name for name in gate.REPORT_ATTRIBUTES if f"`{name}" not in passage)
    assert not unnamed, ("markers.md's check-report section omits report attributes the copied gate reads: "
                         + ", ".join(unnamed))


# The closing tests: they run after every case, in this file's order; under `--dist loadfile`, which the declared
# CI floor runs, one worker runs the whole file.
def test_every_case_ran_and_passed():
    assert PASSED == set(CASES), (
        "cases that did not run and pass in this session: " + ", ".join(sorted(set(CASES) - PASSED))
        + ". Each is required; deselecting or skipping one leaves the check untrusted.")


def test_every_marker_the_entrance_may_name_as_a_source_is_covered_by_a_case():
    uncovered = {evidence: sorted(names - NAMED_SOURCES[evidence])
                 for evidence, names in work.PROOF_SOURCE_MARKERS.items() if names - NAMED_SOURCES[evidence]}
    assert not uncovered, (
        "the entrance may name a source by a marker no case's proof named: "
        + "; ".join(f"{evidence}: {', '.join(names)}" for evidence, names in uncovered.items())
        + ". Add a case whose proof names it (lib/work.py PROOF_SOURCE_MARKERS).")
