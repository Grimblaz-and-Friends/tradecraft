"""The entrance's pre-launch work at scale: each piece done once, no listing, time named.

Design: lib/DESIGN.md#the-entrances-work-before-a-launch
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import build_reach  # noqa: E402
import preflight  # noqa: E402
import run_lifecycle  # noqa: E402
import work  # noqa: E402
import test_work as tw  # noqa: E402  (a module alias, so pytest collects none of its tests here)

REPO = "example/product"
BASE = f"repos/{REPO}"
BRANCH = "reach-change"

# An audit hook cannot be removed, so it records only while a test holds `_AUDIT["on"]`.
_AUDIT = {"on": False, "opens": [], "gh": []}


def _gh_argv(arguments):
    command = arguments[1] if len(arguments) > 1 else None
    if command is None:
        command = arguments[0]
    if isinstance(command, (str, bytes)):
        # Windows audits the joined command line; POSIX audits the argument list.
        command = shlex.split(os.fsdecode(command), posix=os.name != "nt")
    argv = [os.fsdecode(part).strip('"') for part in command]
    return argv if argv and Path(argv[0]).name.lower() in {"gh", "gh.exe"} else None


def _audit(event, arguments):
    if not _AUDIT["on"]:
        return
    if (event == "open" and isinstance(arguments[0], (str, bytes, os.PathLike))
            and set(str(arguments[1] or "r")) <= {"r", "b", "t"}):
        name = os.fsdecode(arguments[0])
        if name.endswith((".request.json", ".run.json")):
            _AUDIT["opens"].append(str(Path(name).resolve()))
    elif event == "subprocess.Popen":
        argv = _gh_argv(arguments)
        if argv is not None:
            _AUDIT["gh"].append(argv)


if not getattr(sys, "_tradecraft_978_scale_audit", False):
    sys.addaudithook(_audit)
    sys._tradecraft_978_scale_audit = True


@pytest.fixture
def audit():
    _AUDIT.update(on=False, opens=[], gh=[])
    try:
        yield _AUDIT
    finally:
        _AUDIT["on"] = False


# --- The allowed requests: each read scoped to one named object, with R the scenario's repository. ---

SHA_ID = r"[0-9a-f]{40}(?:[0-9a-f]{24})?"


def allowed_rest(repo):
    r = re.escape(f"repos/{repo}")
    return {
        "the repository's own record": rf"{r}",
        "its rules for one branch": rf"{r}/rules/branches/[^?]+",
        "one branch's ref": rf"{r}/git/ref/heads/[^?]+",
        "one issue": rf"{r}/issues/[0-9]+",
        "one issue's comments": rf"{r}/issues/[0-9]+/comments",
        "one issue's timeline": rf"{r}/issues/[0-9]+/timeline",
        "one pull request": rf"{r}/pulls/[0-9]+",
        "beneath one pull request": rf"{r}/pulls/[0-9]+/[^?]+",
        "one commit's check runs": rf"{r}/commits/{SHA_ID}/check-runs",
        "one comparison of two commits": rf"{r}/compare/{SHA_ID}\.\.\.{SHA_ID}",
        "one tree": rf"{r}/git/trees/{SHA_ID}",
        "one path's contents at a commit": rf"{r}/contents/[^?]+",
        "one comment by id": rf"{r}/issues/comments/[0-9]+",
        "one workflow run by id": rf"{r}/actions/runs/[0-9]+",
        # Each also scoped to one object: the review workflow
        # run's jobs and the base branch's protection (read_state for an open pull request),
        # and one commit by its sha (use evidence classifying each commit since a use marker).
        "one workflow run's jobs": rf"{r}/actions/runs/[0-9]+/jobs",
        "one commit": rf"{r}/commits/{SHA_ID}",
        "one branch's protection": rf"{r}/branches/[^/?]+/protection",
        "the authenticated account": r"user",
    }


def allowed_queries():
    return {work.CLOSING_PULL_REQUESTS_QUERY: "the closing-references query for one issue",
            work.REVIEW_THREADS_QUERY: "REVIEW_THREADS_QUERY",
            work.WORKFLOW_RUN_FILES_QUERY: "WORKFLOW_RUN_FILES_QUERY"}


def rest_allowed(endpoint, repo):
    path, _, query = endpoint.partition("?")
    for name, pattern in allowed_rest(repo).items():
        if re.fullmatch(pattern, path):
            if name == "one path's contents at a commit":
                return re.search(rf"(?:^|&)ref={SHA_ID}(?:&|$)", query) is not None
            return True
    return False


def gh_allowed(argv, repo):
    if len(argv) < 3 or argv[1] != "api":
        return False
    rest = argv[2:]
    if rest[0] == "graphql":
        queries = [value.split("=", 1)[1] for value in rest[1:] if value.startswith("query=")]
        return len(queries) == 1 and queries[0] in allowed_queries()
    method = "GET"
    fields = False
    paths = []
    index = 0
    while index < len(rest):
        token = rest[index]
        if token in {"-X", "--method"}:
            method = rest[index + 1].upper() if index + 1 < len(rest) else ""
            index += 2
            continue
        if token in {"-f", "-F", "--field", "--raw-field", "--input"}:
            fields = True
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        paths.append(token)
        index += 1
    # gh api turns fields into a POST unless the method is named.
    if method != "GET" or (fields and "-X" not in rest and "--method" not in rest) or len(paths) != 1:
        return False
    return rest_allowed(paths[0].lstrip("/"), repo)


def unlisted(requests, gh_argvs, repo):
    """Every request or `gh` process not on the allowed list, named."""
    found = []
    for kind, value in requests:
        if kind == "GET":
            if not rest_allowed(value, repo):
                found.append(f"GET {value}")
        elif kind == "GRAPHQL":
            if value not in allowed_queries():
                found.append("GraphQL " + " ".join(value.split())[:160])
        else:
            found.append(f"{kind} {value}")
    for argv in gh_argvs:
        if not gh_allowed(argv, repo):
            found.append("gh " + " ".join(argv[1:]))
    return found


class Recorder:
    """The scenario's GitHub: every request recorded, each answered from the fixture."""

    def __init__(self, fixture):
        self.fixture = fixture
        self.head = fixture.pr["head"]["sha"]
        self.requests = []

    def _pull(self):
        return {**deepcopy(self.fixture.pr), "head": {**self.fixture.pr["head"], "sha": self.head}}

    def get(self, endpoint, *, paginate=False):
        self.requests.append(("GET", endpoint))
        if endpoint == f"{BASE}/issues/12":
            return deepcopy(self.fixture.issue)
        if endpoint == f"{BASE}/issues/12/comments":
            return deepcopy(self.fixture.issue_comments)
        if endpoint == f"{BASE}/issues/12/timeline?per_page=100":
            return [{"event": "cross-referenced", "source": {"type": "issue", "issue": {
                "number": 7, "pull_request": {}, "repository": {"full_name": REPO}}}}]
        if "/pulls/7" in endpoint:
            return self._pull()
        return tw.FakeTransport({}).get(endpoint, paginate=paginate)

    def closing_pull_requests(self, query, variables):
        self.requests.append(("GRAPHQL", query))
        return tw.closing_page([7], REPO)

    def review_threads(self, query, variables):
        self.requests.append(("GRAPHQL", query))
        return {"data": {"repository": {"pullRequest": {"reviewThreads": {
            "pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": []}}}}}

    def workflow_run_files(self, query, variables):
        self.requests.append(("GRAPHQL", query))
        return {"data": {"nodes": []}}

    def graphql(self, query, variables):
        self.requests.append(("GRAPHQL", query))
        raise AssertionError("the scenario answers no other GraphQL query")

    def __getattr__(self, name):
        def unexpected(*arguments, **_keywords):
            self.requests.append((name.upper(), repr(arguments)[:160]))
            raise AssertionError(f"unexpected GitHub call {name}")
        return unexpected


# --- The made-up change: a holder, a registered builder tree and its turns. ---

class _Terms(tw.TestGoverningTerms):
    """Writes only the newest turn, so a return changes no other record on disk."""

    def save(self, fixture):
        request_path, run_path, request, run = fixture.term_turns[-1]
        request_path.write_bytes(work.records.json_bytes(request))
        run_path.write_bytes(work.records.json_bytes(run))


TERMS = _Terms()
REACH = tw.TestBuildReach()
START = datetime(2026, 10, 5, 11, 0, tzinfo=timezone.utc)


def stamp(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def made_up_change(tmp_path, monkeypatch):
    """TestBuildReach's builder: one completed turn that removed two lines of README.md."""
    monkeypatch.setattr(work, "_governing_terms_decision", lambda _state: None)
    monkeypatch.setattr(work, "_compose_merge_obligation", lambda *_a, **_k: None)
    holder = tw.policy_repository(tmp_path, "reach-holder")
    tw.git(holder, "config", "core.autocrlf", "false")
    root = tmp_path / "reach-builder"
    tw.git(holder, "worktree", "add", "-b", BRANCH, str(root))
    row = tw.registry_row(root, holder, BRANCH)
    monkeypatch.setattr(work, "read_registry", lambda: {"schema_version": 2, "worktrees": [row]})
    fixture = tw.state(tw.MECHANICAL, pr=True, paths=["README.md"],
                       config=work.WorkConfig(marker_producers=frozenset({tw.PRODUCER}),
                                              reviewer_label="reviewers"))
    fixture.pr.update(node_id="PR_fixture", changed_files=1)
    fixture.pr["head"]["ref"] = BRANCH
    base = tw.git(root, "rev-parse", "HEAD").stdout.decode().strip()
    fixture.pr["base"]["sha"] = fixture.pr["head"]["sha"] = base
    fixture.synchronization["base"]["sha"] = base
    fixture.required_gate = {"status": "none", "sources": [], "reason": "fixture no required workflow"}
    fixture.term_root, fixture.term_registration = root, row
    fixture.term_turns = []
    fixture.holder_root = holder
    fixture.record_root = tmp_path / "reach-dispatches"
    monkeypatch.setattr(work.records, "default_record_root", lambda: fixture.record_root)
    monkeypatch.setattr(work, "_collect_synchronization", lambda *_: fixture.synchronization)
    monkeypatch.setattr(work, "_verify_floor_identity", lambda *_: None)
    fixture.issue_comments[0].update(id=101, created_at="2026-10-05T09:00:00Z")
    REACH.edit(fixture, b"a\nb\nc\n")
    before = fixture.pr["head"]["sha"]
    fixture.pr["base"]["sha"] = fixture.synchronization["base"]["sha"] = before
    REACH.edit(fixture, b"a\n")
    after = fixture.pr["head"]["sha"]
    request, run = TERMS.turn(fixture)
    request["lineage_branch"] = BRANCH
    request["revision_before"], run["revision_after"] = before, after
    TERMS.save(fixture)
    REACH.floor(fixture)
    return fixture


def add_turn(fixture, files):
    """One builder turn: one commit on the builder's branch and its completed bundle."""
    root = fixture.term_root
    before = fixture.pr["head"]["sha"]
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    tw.git(root, "add", "-A")
    tw.git(root, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
           "commit", "-q", "-m", "turn")
    after = tw.git(root, "rev-parse", "HEAD").stdout.decode().strip()
    fixture.pr["head"]["sha"] = after
    moment = START + timedelta(minutes=10 * len(fixture.term_turns))
    request, run = TERMS.turn(fixture, composed=stamp(moment), launched=stamp(moment + timedelta(minutes=1)),
                              completed=stamp(moment + timedelta(minutes=2)))
    request["lineage_branch"] = BRANCH
    request["revision_before"], run["revision_after"] = before, after
    TERMS.save(fixture)
    return request, run, before, after


def other_bundles(store, count):
    """Bundles for other changes, the bulk of a lab store."""
    schema = work.records.SCHEMA_VERSION
    for number in range(count):
        folder = store / f"other-{number:05d}"
        folder.mkdir(parents=True)
        dispatch = f"other-{number}"
        (folder / "result.md.request.json").write_bytes(json.dumps({
            "schema_version": schema, "dispatch_id": dispatch, "work": f"elsewhere/thing#{number % 97}",
            "stage": ("build", "proof", "cold-reader", "floor")[number % 4],
            "launched_at": "2026-10-01T00:00:00Z"}).encode())
        (folder / "result.md.run.json").write_bytes(json.dumps({
            "schema_version": schema, "dispatch_id": dispatch, "completed_at": "2026-10-01T00:01:00Z",
            "outcome": "success", "lifecycle": "completed"}).encode())


class _Seat:
    """`build_reach`'s view of seat_process, counting each batch process it starts."""

    def __init__(self, real, log):
        self._real, self._log = real, log

    def __getattr__(self, name):
        return getattr(self._real, name)

    def stream_read(self, command, **keywords):
        self._log.append(("batch", tuple(command)))
        return self._real.stream_read(command, **keywords)


def count_reach_processes(monkeypatch):
    """Every Git process `build_reach.Git` starts, through its runner or its batch."""
    log = []
    original = build_reach.Git.__init__

    def counted_init(self, root, run=None):
        original(self, root, run)
        inner = self.run

        def counted(command, where):
            log.append(("read", tuple(command)))
            return inner(command, where)
        self.run = counted
    monkeypatch.setattr(build_reach.Git, "__init__", counted_init)
    monkeypatch.setattr(build_reach, "seat_process", _Seat(build_reach.seat_process, log))
    return log


def decide_arguments(fixture, *stage):
    return work.parser().parse_args([*stage, "--repo", REPO, "--issue", "12",
                                     "--root", str(fixture.holder_root)])


def state_read_through(fixture):
    """The issue-scoped reads `read_state` makes before the pull request, then the fixture's state."""
    def read(transport, repo, number, config, *_arguments, **_keywords):
        issue = transport.get(f"repos/{repo}/issues/{number}")
        comments = work._get_list(transport, f"repos/{repo}/issues/{number}/comments")
        work._implementing_candidates(transport, repo, number, issue, comments, config)
        transport.get(f"repos/{repo}/pulls/7")
        fixture.reach = None
        fixture.validated_markers = None
        return fixture
    return read


def report(capsys, call):
    capsys.readouterr()
    call()
    return json.loads(capsys.readouterr().out)


# --- The standing test: each piece of the entrance's work done once, at realistic size. ---

def test_978_scale(tmp_path, monkeypatch, capsys, audit):
    fixture = made_up_change(tmp_path, monkeypatch)
    turn_files = {}
    for number in range(22):
        if number == 3:
            files = {f"wide/file-{index:02d}.txt": f"line {index}\n".encode() for index in range(39)}
            files["wide/image.bin"] = bytes(range(256)) * 8 + b"\0"
        else:
            files = {f"single/turn-{number:02d}.txt": f"turn {number}\n".encode()}
        request, _run, before, after = add_turn(fixture, files)
        turn_files[request["dispatch_id"]] = (len(files), before, after)
    other_bundles(fixture.record_root, 2000)
    REACH.floor(fixture)
    tw.write_policy(fixture.holder_root)
    assert len(list(fixture.record_root.rglob("*.request.json"))) >= 2000
    assert len(fixture.term_turns) >= 20

    transport = Recorder(fixture)
    monkeypatch.setattr(work, "read_state", state_read_through(fixture))
    monkeypatch.setattr(work, "prepare_use_evidence", lambda *_a: None)
    reach_log = count_reach_processes(monkeypatch)
    arguments = decide_arguments(fixture)

    with preflight.scope():
        audit["on"] = True
        first = report(capsys, lambda: work._run(arguments, transport=transport))
        before_second = len(reach_log)
        second = report(capsys, lambda: work._run(arguments, transport=transport))
        second_starts = reach_log[before_second:]
        # A launch returns: one completed turn is written, and the run's index is refreshed.
        audit["on"] = False
        returned, _run, _before, _after = add_turn(fixture, {"single/returned.txt": b"returned\n"})
        returned_paths = {str(path.resolve()) for path in fixture.term_turns[-1][:2]}
        transport.head = fixture.pr["head"]["sha"]
        REACH.floor(fixture)
        audit["on"] = True
        preflight.refresh()
        third = report(capsys, lambda: work._run(arguments, transport=transport))
        audit["on"] = False

    assert first.get("reach", {}).get("turns"), first.get("reach")
    assert before_second > 0, "the first report measured nothing, so (a) would pass vacuously"
    # (a) the second report starts no build_reach Git process.
    assert second_starts == [], f"the second report started {len(second_starts)}: {second_starts[:5]}"
    # (b) the turn that returned during the run is in the third report.
    third_turns = third["reach"]["turns"]
    assert any(returned["dispatch_id"] in (entry.get("dispatch_id"), entry.get("turn_reference"))
               for entry in third_turns), [entry.get("dispatch_id") for entry in third_turns]
    # (c) no request or run record is opened twice, but what the return wrote.
    counts = {}
    for path in audit["opens"]:
        counts[path] = counts.get(path, 0) + 1
    twice = {path: count for path, count in counts.items()
             if count > (2 if path in returned_paths else 1)}
    assert not twice, f"{len(twice)} records opened more than once, e.g. {sorted(twice.items())[:5]}"
    assert sum(path.endswith(".request.json") for path in counts) >= 2000, "the hook saw the store unread"
    # (d) the 40-file turn starts no more Git processes than the one-file turn, each measured afresh.
    measured = {}
    for dispatch, (files, before, after) in turn_files.items():
        if files not in measured:
            start = len(reach_log)
            with preflight.scope():
                build_reach.measure(build_reach.Git(fixture.holder_root, run=work._git), before, after)
            measured[files] = len(reach_log) - start
    assert set(measured) == {1, 40}
    assert measured[40] <= measured[1], measured
    # (e) every request is on the allowed list.
    stray = unlisted(transport.requests, audit["gh"], REPO)
    assert not stray, "requests not on the allowed list:\n" + "\n".join(stray)
    assert any(kind == "GRAPHQL" for kind, _ in transport.requests)


LISTINGS = (
    ("GET", f"{BASE}/pulls?state=all"),
    ("GET", f"{BASE}/issues?state=all"),
    ("GET", f"search/issues?q=repo:{REPO}+is:pr"),
    ("GRAPHQL", 'query { repository(owner: "example", name: "product") { pullRequests(first: 100) '
                "{ nodes { number } } } }"),
)


def test_978_scale_detector_fails_every_listing(audit):
    """The detector names each listing it is sent, so it cannot pass vacuously."""
    fixture = tw.state(pr=True)
    transport = Recorder(fixture)
    for kind, value in LISTINGS:
        before = len(transport.requests)
        if kind == "GET":
            with pytest.raises(KeyError):
                transport.get(value)
        else:
            transport.closing_pull_requests(value, {})
        assert len(transport.requests) == before + 1
    query = LISTINGS[-1][1]
    commands = (["gh", "api", "graphql", "-f", f"query={query}"],
                ["gh", "search", "issues", "--include-prs"],
                ["gh", "pr", "list"])
    audit["on"] = True
    try:
        for command in commands:
            # The same recorder the scenario uses: the audit hook's view of a process start.
            _audit("subprocess.Popen", (command[0], command, None, None))
    finally:
        audit["on"] = False
    assert len(audit["gh"]) == 3
    for request in transport.requests:
        assert unlisted([request], [], REPO), request
    for argv in audit["gh"]:
        assert unlisted([], [argv], REPO), argv
    assert len(unlisted(transport.requests, audit["gh"], REPO)) == 7
    # The allowed reads themselves pass, so the detector is not failing everything.
    assert unlisted([("GET", f"{BASE}/issues/12/timeline?per_page=100"), ("GET", f"{BASE}/pulls/7/files"),
                     ("GET", f"{BASE}/contents/a.json?ref={'c' * 40}"),
                     ("GRAPHQL", work.CLOSING_PULL_REQUESTS_QUERY)],
                    [["gh", "api", f"{BASE}/pulls/7"],
                     ["gh", "api", "graphql", "-f", f"query={work.REVIEW_THREADS_QUERY}"]], REPO) == []


# --- No count between composing the prompt and launching. ---

def test_978_no_count_between_composition_and_launch(tmp_path, monkeypatch):
    fixture = made_up_change(tmp_path, monkeypatch)
    add_turn(fixture, {"single/one.txt": b"one\n"})
    REACH.floor(fixture)
    reach_log = count_reach_processes(monkeypatch)
    window = {"composed": None, "invoked": None}
    composition = work._prompt_composition

    def composed(state):
        value = composition(state)
        window["composed"] = len(reach_log)
        return value

    def invoke(command, deadline, *_rest):
        window["invoked"] = len(reach_log)
        return 0
    monkeypatch.setattr(work, "_prompt_composition", composed)
    monkeypatch.setattr(work, "_invoke_recipient", invoke)
    monkeypatch.setattr(work, "create_implementation_root", lambda *_a: pytest.fail("created another tree"))
    monkeypatch.setattr(work, "publish_implementation_branch", lambda *_a: None)
    try:
        # `work.main` opens the run's scope; the harness enters below it, so it opens one the same way.
        with preflight.scope():
            TERMS.endpoint(fixture, monkeypatch, "build")
    except work.WorkError:
        pass  # A launch that returns no bundle is refused afterwards; the window is what is measured.
    assert window["composed"] is not None, "the build composed no prompt"
    assert window["invoked"] is not None, "the build never reached its launch"
    assert window["composed"] > 0, "the turns were never measured, so the window proves nothing"
    between = reach_log[window["composed"]:window["invoked"]]
    assert between == [], f"{len(between)} build_reach Git processes between composition and launch: {between[:5]}"


# --- The scoped report equals the unscoped one, so the index and memo change no answer. ---

class _Unscoped:
    """`build_reach`'s view of preflight with no scope open, so it keeps no memo and no shared view."""

    def __getattr__(self, name):
        return getattr(preflight, name)

    @staticmethod
    def current():
        return None


def test_978_scoped_report_equals_unscoped(tmp_path, monkeypatch, capsys):
    fixture = made_up_change(tmp_path, monkeypatch)
    for number in range(3):
        add_turn(fixture, {f"single/turn-{number}.txt": f"{number}\n".encode()})
    REACH.floor(fixture)
    REACH.reading(fixture)
    schema = work.records.SCHEMA_VERSION
    store = fixture.record_root
    for name, request, run in (
            ("cold-reader-example-product-12-a", {"schema_version": schema, "dispatch_id": "cold-a",
                                                  "work": f"{REPO}#12", "stage": "cold-reader"},
             {"schema_version": schema, "dispatch_id": "cold-a", "completed_at": "2026-10-05T12:00:00Z",
              "outcome": "success", "lifecycle": "completed"}),
            ("cold-reader-example-product-12-b", {"schema_version": schema, "dispatch_id": "cold-b",
                                                  "work": f"{REPO}#12", "stage": "cold-reader"}, b"{broken"),
            ("damaged-request", b"not json", {"schema_version": schema, "outcome": "success"})):
        folder = store / name
        folder.mkdir(parents=True)
        for suffix, value in ((".request.json", request), (".run.json", run)):
            (folder / ("result.md" + suffix)).write_bytes(
                value if isinstance(value, bytes) else json.dumps(value).encode())
    other_bundles(store, 40)
    # Invalid markers: an unauthorized author, malformed attributes, and a quoted marker.
    fixture.issue_comments.extend([
        {"id": 301, "user": {"login": "stranger"}, "created_at": "2026-10-05T13:00:00Z",
         "body": f"<!-- tradecraft:floor:v1 head={fixture.pr['head']['sha']} status=pass -->"},
        {"id": 302, "user": {"login": tw.PRODUCER}, "created_at": "2026-10-05T13:01:00Z",
         "body": "<!-- tradecraft:reach-reading:v1 head=not-a-sha -->"},
        {"id": 303, "user": {"login": tw.PRODUCER}, "created_at": "2026-10-05T13:02:00Z",
         "body": "> <!-- tradecraft:implementing-pr:v1 number=99 -->"},
    ])
    tw.write_policy(fixture.holder_root)
    transport = Recorder(fixture)
    monkeypatch.setattr(work, "read_state", state_read_through(fixture))
    monkeypatch.setattr(work, "prepare_use_evidence", lambda *_a: None)
    arguments = decide_arguments(fixture)

    with preflight.scope():
        scoped = report(capsys, lambda: work._run(arguments, transport=transport))
        assert preflight.current().indexes, "the scoped run used no store index"

    # The same run with the index and the memo disabled: every reader reads directly, as before.
    monkeypatch.setattr(run_lifecycle, "store_index", lambda _store: None)
    monkeypatch.setattr(build_reach, "preflight", _Unscoped())
    with preflight.scope():
        unscoped = report(capsys, lambda: work._run(arguments, transport=transport))

    for value in (scoped, unscoped):
        value.pop("preflight", None)
    assert scoped.get("reach", {}).get("turns"), scoped.get("reach")
    assert scoped == unscoped


# --- A count cut off by time says time ran out, and never says to fetch or restore. ---

def _searched(capfd):
    captured = capfd.readouterr()
    return captured.out, captured.err


def _assert_time_named(out, err, phrase_parts):
    for stream in (out, err):
        assert "fetch" not in stream.lower(), stream
        assert "restore" not in stream.lower(), stream
    turns = []
    for stream in (out, err):
        for line in stream.splitlines():
            try:
                value = json.loads(line)
            except ValueError:
                continue
            turns.extend(((value.get("reach") or {}).get("turns") or []) if isinstance(value, dict) else [])
    if not turns:
        try:
            value = json.loads(out)
            turns = (value.get("reach") or {}).get("turns") or []
        except ValueError:
            pass
    unmeasured = [entry for entry in turns if entry.get("uncertainty")]
    assert unmeasured, (out, err)
    for entry in unmeasured:
        uncertainty = entry["uncertainty"]
        assert "time ran out" in uncertainty, uncertainty
        for part in phrase_parts:
            assert re.search(part, uncertainty), (part, uncertainty)
    return turns


def three_turn_proof_change(tmp_path, monkeypatch):
    fixture = made_up_change(tmp_path, monkeypatch)
    for number in range(3):
        add_turn(fixture, {f"single/turn-{number}.txt": f"{number}\n".encode()})
    REACH.floor(fixture)
    tw.write_policy(fixture.holder_root)
    tw.git(fixture.holder_root, "add", "-A")
    tw.git(fixture.holder_root, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
           "commit", "-q", "--allow-empty", "-m", "policy")
    transport = Recorder(fixture)
    monkeypatch.setattr(work, "GitHubREST", lambda *_a, **_k: transport)
    monkeypatch.setattr(work, "read_state", state_read_through(fixture))
    monkeypatch.setattr(work, "prepare_use_evidence", lambda *_a: None)
    monkeypatch.setattr(work, "_publish_proof_comment", lambda *_a: {"action": "created", "id": 1})
    return fixture


def test_978_cap_cut_count(tmp_path, monkeypatch, capfd):
    # The removals count is the entrance's reading before the launch, so the cap is its bound.
    fixture = three_turn_proof_change(tmp_path, monkeypatch)
    measured = {"turns": 0}
    measure = build_reach.measure

    def counted(*arguments, **keywords):
        value = measure(*arguments, **keywords)
        measured["turns"] += 1
        return value
    monkeypatch.setattr(build_reach, "measure", counted)
    git = work._git

    def slow(command, root):
        if measured["turns"] >= 1:
            # The first turn is measured; this read outlives the entrance's cap.
            deadline = run_lifecycle.current_deadline()
            while deadline is not None and time.monotonic() <= deadline.cap_end:
                time.sleep(0.2)
        return git(command, root)
    monkeypatch.setattr(work, "_git", slow)
    capfd.readouterr()
    # The entrance has already spent all but 20 seconds of its cap when the count begins.
    work.main(["run", "proof", "--repo", REPO, "--issue", "12", "--root", str(fixture.holder_root),
               "--timeout-seconds", "20"], started=time.monotonic() - run_lifecycle.PREFLIGHT_CAP_SECONDS + 20)
    out, err = _searched(capfd)
    turns = _assert_time_named(out, err, [r"the entrance's 900-second cap"])
    assert measured["turns"] >= 1 and len(turns) >= 3, turns
    for stream in (out, err):
        assert "raise the limit" not in stream.lower(), stream
    assert "--preflight-cap-seconds" in out + err


def test_978_timeout_says_time_ran_out_without_a_run_deadline(tmp_path, monkeypatch, capfd):
    fixture = three_turn_proof_change(tmp_path, monkeypatch)
    git = work._git
    outlived = {"command": None, "times": 0}

    def bounded(command, root):
        # build_reach's own reads carry its quoting option; one removals-count diff outlives its bound.
        if outlived["command"] is None and command[:2] == ["-c", "core.quotePath=true"] and "diff" in command:
            outlived["command"] = list(command)
        if command == outlived["command"]:
            # The same read outlives its own bound each time it is made; no run deadline is open.
            assert run_lifecycle.current_deadline() is None
            outlived["times"] += 1
            raise subprocess.TimeoutExpired(command, build_reach.READ_BOUND_SECONDS)
        return git(command, root)
    monkeypatch.setattr(work, "_git", bounded)
    capfd.readouterr()
    work.main(["--repo", REPO, "--issue", "12", "--root", str(fixture.holder_root)])
    out, err = _searched(capfd)
    assert outlived["times"] >= 1
    _assert_time_named(out, err, [r"this read's own"])


class _Recording:
    """A transport wrapper recording each request before the wrapped fixture answers it."""

    def __init__(self, inner):
        self.inner = inner
        self.requests = []

    def get(self, endpoint, *, paginate=False):
        self.requests.append(("GET", endpoint))
        return self.inner.get(endpoint, paginate=paginate)

    def _query(self, name, query, variables):
        self.requests.append(("GRAPHQL", query))
        return getattr(self.inner, name)(query, variables)

    def closing_pull_requests(self, query, variables):
        return self._query("closing_pull_requests", query, variables)

    def review_threads(self, query, variables):
        return self._query("review_threads", query, variables)

    def workflow_run_files(self, query, variables):
        return self._query("workflow_run_files", query, variables)

    def __getattr__(self, name):
        def other(*arguments, **keywords):
            self.requests.append((name.upper(), repr(arguments)[:160]))
            return getattr(self.inner, name)(*arguments, **keywords)
        return other


def test_978_open_pull_request_reads_are_on_the_allowed_list():
    """The allowed list over what the standing test stubs: `read_state` for an open pull request, and use evidence."""
    ancestor = "b" * 40
    marker = (f"<!-- tradecraft:use:v1 head={ancestor} status=pass changed=false "
              "staffing_status=qualified -->")
    inner = tw.actions_transport()
    inner.values["repos/example/product/issues/12/comments"] = tw.state(
        tw.AFFIRMED, tw.ARTIFACT, tw.WOULD, tw.HOLDER, tw.FLOOR, marker).issue_comments
    transport = _Recording(inner)
    fixture = tw.collect_actions(transport)
    ancestry = _Recording(tw.AncestryTransport(ancestor, tw.SHA, {"c" * 40: [{"filename": "README.md"}]}))
    work.prepare_use_evidence(fixture, ancestry, tw.RULES)
    requests = transport.requests + ancestry.requests
    assert unlisted(requests, [], "example/product") == []
    paths = {value.partition("?")[0] for kind, value in requests if kind == "GET"}
    for read in ("pulls/7", "pulls/7/reviews", "pulls/7/files", "rules/branches/main",
                 f"commits/{tw.SHA}/check-runs", f"compare/{ancestor}...{tw.SHA}"):
        assert f"repos/example/product/{read}" in paths, read


def _proof(fixture, *extra, started=None):
    return work.main(["run", "proof", "--repo", REPO, "--issue", "12", "--root", str(fixture.holder_root),
                      *extra], started=started)


def test_978_no_launch_stages_refuse_at_the_cap_having_written_nothing(tmp_path, monkeypatch, capfd):
    fixture = three_turn_proof_change(tmp_path, monkeypatch)
    writes = []
    git = work._git

    def watched(command, root):
        if work._git_writes(command):
            writes.append(command)
        return git(command, root)
    monkeypatch.setattr(work, "_git", watched)
    monkeypatch.setattr(work, "_execute_proof", lambda *_a, **_k: pytest.fail("the stage's own work began"))
    capfd.readouterr()
    assert _proof(fixture, started=time.monotonic() - run_lifecycle.PREFLIGHT_CAP_SECONDS - 1) == 1
    out, err = _searched(capfd)
    assert "the entrance's 900-second cap" in out + err
    assert writes == []


def test_978_a_no_launch_stage_counts_its_limit_from_its_own_work(tmp_path, monkeypatch, capfd):
    fixture = three_turn_proof_change(tmp_path, monkeypatch)
    seen = {}

    def proof(*_a, **_k):
        deadline = run_lifecycle.current_deadline()
        seen.update(opened=deadline.window_opened, end=deadline.end, limit=deadline.allotted,
                    reserve=deadline.reserve, started=deadline.started)
        return 0
    monkeypatch.setattr(work, "_execute_proof", proof)
    # Five minutes were spent reading and deciding; the stage's own work still gets its whole hour.
    assert _proof(fixture, started=time.monotonic() - 300) == 0
    assert seen["opened"] is not None and seen["opened"] - seen["started"] >= 300
    assert seen["end"] - seen["opened"] == pytest.approx(seen["limit"] + seen["reserve"])


@pytest.mark.parametrize("spent, outcome", [(901, "completed"), (1801, "refused-at-cap")])
def test_978_declared_cap_record_for_a_stage_that_launches_nobody(tmp_path, monkeypatch, capfd, spent, outcome):
    fixture = three_turn_proof_change(tmp_path, monkeypatch)
    home = tmp_path / "records-home"
    monkeypatch.setattr(work, "_records_home", lambda _state: home)
    order = []
    get = Recorder.get

    def first_read(self, endpoint, **kwargs):
        order.append(sorted(str(path) for path in home.rglob("*.json")))
        return get(self, endpoint, **kwargs)
    monkeypatch.setattr(Recorder, "get", first_read)
    monkeypatch.setattr(work, "_execute_proof", lambda *_a, **_k: 0)
    _proof(fixture, "--preflight-cap-seconds", "1800", "--preflight-cap-reason", "large repository",
           started=time.monotonic() - spent)
    [declared] = list((home / "preflight-caps").rglob("*.json"))
    record = json.loads(declared.read_bytes())
    assert record["stage"] == "proof" and record["called_at"]
    assert record["preflight_cap"] == {"seconds": 1800, "source": "declared", "reason": "large repository"}
    assert record["outcome"] == outcome
    # Written before the run's first read.
    assert not order or order[0] == [str(declared)]


def test_978_cap_refusal(tmp_path, monkeypatch, capfd):
    fixture = three_turn_proof_change(tmp_path, monkeypatch)
    monkeypatch.setattr(work, "_recipient_run", lambda *_a, **_k: pytest.fail("a launcher was started"))
    store = work.records.default_record_root().expanduser().resolve()
    before = sorted(store.rglob("*")) if store.is_dir() else []
    capfd.readouterr()
    code = work.main(["run", "build", "--repo", REPO, "--issue", "12", "--root", str(fixture.holder_root),
                      "--holder-session-id", "holder"],
                     started=time.monotonic() - run_lifecycle.PREFLIGHT_CAP_SECONDS - 1)
    out, err = _searched(capfd)
    assert code == 1
    assert out.splitlines()[0].startswith("work: window ")
    reports = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    assert reports, out
    report = reports[-1]
    assert report["status"] == "refused"
    for text in ("the entrance's 900-second cap", "--preflight-cap-seconds", "--preflight-cap-reason"):
        assert text in report["reason"]
    lines = [line for line in err.splitlines() if line.startswith("work: preflight ")]
    assert lines, err
    split = json.loads(lines[-1].removeprefix("work: preflight "))
    assert abs(sum(split["parts"].values()) - split["total_seconds"]) <= 1
    assert (sorted(store.rglob("*")) if store.is_dir() else []) == before


def test_978_declared_caps_for_held_and_launching_stages_reach_the_release_report(tmp_path, monkeypatch, capfd):
    fixture = three_turn_proof_change(tmp_path, monkeypatch)
    home = tmp_path / "records-home"
    monkeypatch.setattr(work, "_records_home", lambda _state: home)
    declared = ["--preflight-cap-seconds", "1800", "--preflight-cap-reason", "large repository"]
    # A floor with no command holds by decision without launching.
    work.main(["run", "floor", "--repo", REPO, "--issue", "12", "--root", str(fixture.holder_root),
               "--holder-session-id", "holder", *declared])
    # A build whose entrance spent the declared cap refuses before any launch.
    monkeypatch.setattr(work, "_recipient_run", lambda *_a, **_k: pytest.fail("a launcher was started"))
    work.main(["run", "build", "--repo", REPO, "--issue", "12", "--root", str(fixture.holder_root),
               "--holder-session-id", "holder", *declared], started=time.monotonic() - 1801)
    rows = work.declared_caps(f"{REPO}#12", None)
    assert sorted((row["stage"], row["outcome"]) for row in rows) == [
        ("build", "refused-at-cap"), ("floor", "held")]
    assert all(row["preflight_cap"]["reason"] == "large repository" for row in rows)


@pytest.mark.parametrize("limit", [1, 7200])
def test_978_write_in_flight_at_the_cap_through_run_build(tmp_path, monkeypatch, capfd, limit):
    fixture = three_turn_proof_change(tmp_path, monkeypatch)
    writes, deadlines = [], []
    probe = work._run_probe

    def fake_writes(command, **kwargs):
        if command[3:5] == ["worktree", "add"]:
            deadline = run_lifecycle.current_deadline()
            deadlines.append(deadline)
            began = time.monotonic()
            writes.append(("worktree", began, kwargs["timeout"]))
            # The worktree's creation is still running four seconds after the cap's end.
            time.sleep(max(0.0, min(deadline.cap_end + 4 - began, kwargs["timeout"])))
            return subprocess.CompletedProcess(command, 0, b"", b"")
        if work._git_writes(command[3:]):
            writes.append((command[3], time.monotonic(), kwargs["timeout"]))
            return subprocess.CompletedProcess(command, 0, b"", b"")
        return probe(command, **kwargs)
    monkeypatch.setattr(work, "_run_probe", fake_writes)

    def stage_root(state, decision, root, instalment, holder):
        work._git(["worktree", "add", str(tmp_path / "implementation")], fixture.holder_root)
        work._git(["push", "origin", "HEAD"], fixture.holder_root)  # The write queued after it.
        return tmp_path / "implementation", "tradecraft/12-x", False
    monkeypatch.setattr(work, "_dispatch_root", stage_root)
    monkeypatch.setattr(work, "_recipient_run", lambda *_a, **_k: pytest.fail("a launcher was started"))
    capfd.readouterr()
    called = time.monotonic()
    code = work.main(["run", "build", "--repo", REPO, "--issue", "12", "--root", str(fixture.holder_root),
                      "--holder-session-id", "holder", "--timeout-seconds", str(limit)],
                     started=called - run_lifecycle.PREFLIGHT_CAP_SECONDS + 20)
    returned = time.monotonic()
    out, err = _searched(capfd)
    assert code == 1 and "the entrance's 900-second cap" in out + err, (out, err)
    [deadline] = deadlines
    [(kind, began, bound)] = writes  # The queued write was never begun after the cap.
    assert kind == "worktree" and began < deadline.cap_end
    if limit == 1:
        # Cut where it would outlast the printed return less the reserve: the cap's end plus the limit.
        assert began + bound == pytest.approx(deadline.cap_end + 1, abs=0.5)
    else:
        # At a default limit the write runs to its end, four seconds past the cap, then the run refuses.
        assert bound == 120 and returned >= deadline.cap_end + 4 - 0.2
    assert returned < deadline.latest_end


NO_LAUNCH_STAGES = ["catch-up", "proof", "ready-reviewers", "release-report"]


def _noting(remaining, order, home):
    """Each bound a read asks for is a read about to start: note what the records home held then."""
    def noted(self, **kwargs):
        order.append(sorted(str(path) for path in home.rglob("*.json")))
        return remaining(self, **kwargs)
    return noted
STAGE_WORK = {"catch-up": "_execute_catch_up", "proof": "_execute_proof",
              "ready-reviewers": "_execute_ready_reviewers"}


def _files(*roots):
    return sorted((str(path), path.stat().st_mtime_ns) for root in roots if Path(root).is_dir()
                  for path in Path(root).rglob("*") if path.is_file())


def _no_launch_run(fixture, stage, *extra, started):
    return work.main(["run", stage, "--repo", REPO, "--issue", "12", "--root", str(fixture.holder_root),
                      "--holder-session-id", "holder", *extra], started=started)


@pytest.mark.parametrize("stage", NO_LAUNCH_STAGES)
def test_978_no_launch_stages(tmp_path, monkeypatch, capfd, stage):
    fixture = three_turn_proof_change(tmp_path, monkeypatch)
    writes = []
    git = work._git

    def watched(command, root):
        if work._git_writes(command) or command[:1] in (["commit"], ["checkout"], ["reset"], ["update-ref"],
                                                       ["merge"], ["worktree"]):
            writes.append(command)
        return git(command, root)
    monkeypatch.setattr(work, "_git", watched)
    transport = work.GitHubREST()
    store = work.records.default_record_root().expanduser().resolve()
    before = (_files(fixture.holder_root, store), work.read_registry())
    capfd.readouterr()
    # The cap is spent: the stage refuses having written nothing.
    assert _no_launch_run(fixture, stage, started=time.monotonic() - run_lifecycle.PREFLIGHT_CAP_SECONDS - 1) == 1
    out, err = _searched(capfd)
    assert "the entrance's 900-second cap" in out + err
    assert writes == []
    assert all(kind in {"GET", "GRAPHQL"} for kind, _value in transport.requests)
    assert (_files(fixture.holder_root, store), work.read_registry()) == before
    # Five minutes of reading and deciding: the stage's own work still gets its whole limit.
    seen = {}
    opened = work._open_stage_work_window

    def window():
        opened()
        deadline = run_lifecycle.current_deadline()
        seen.update(opened=deadline.window_opened, end=deadline.end, allotted=deadline.allotted,
                    reserve=deadline.reserve, started=deadline.started)
        raise work.WorkError("the test stops the stage's own work here")
    monkeypatch.setattr(work, "_open_stage_work_window", window)
    _no_launch_run(fixture, stage, started=time.monotonic() - 300)
    assert seen, _searched(capfd)
    assert seen["opened"] - seen["started"] >= 300
    assert seen["end"] - seen["opened"] == pytest.approx(seen["allotted"] + seen["reserve"])


@pytest.mark.parametrize("stage", NO_LAUNCH_STAGES)
@pytest.mark.parametrize("spent, outcome", [(901, "completed"), (1801, "refused-at-cap")])
def test_978_declared_cap_record_for_each_stage_that_launches_nobody(tmp_path, monkeypatch, capfd, stage,
                                                                     spent, outcome):
    fixture = three_turn_proof_change(tmp_path, monkeypatch)
    home = tmp_path / "records-home"
    monkeypatch.setattr(work, "_records_home", lambda _state: home)
    order = []
    get = Recorder.get

    def first_read(self, endpoint, **kwargs):
        order.append(sorted(str(path) for path in home.rglob("*.json")))
        return get(self, endpoint, **kwargs)
    monkeypatch.setattr(Recorder, "get", first_read)
    probe = work._run_probe

    def first_probe(command, **kwargs):
        order.append(sorted(str(path) for path in home.rglob("*.json")))
        return probe(command, **kwargs)
    monkeypatch.setattr(work, "_run_probe", first_probe)
    # A spent cap may refuse before any read starts; the declaration still exists.
    monkeypatch.setattr(work.lifecycle.Deadline, "remaining", _noting(work.lifecycle.Deadline.remaining, order, home))
    if stage in STAGE_WORK:
        monkeypatch.setattr(work, STAGE_WORK[stage], lambda *_a, **_k: 0)
    _no_launch_run(fixture, stage, "--preflight-cap-seconds", "1800", "--preflight-cap-reason", "large repository",
                   started=time.monotonic() - spent)
    [declared] = list((home / "preflight-caps").rglob("*.json"))
    record = json.loads(declared.read_bytes())
    assert record["stage"] == stage and record["called_at"]
    assert record["preflight_cap"] == {"seconds": 1800, "source": "declared", "reason": "large repository"}
    assert record["outcome"] == outcome, _searched(capfd)
    # Written before the run's first read.
    assert order and order[0] == [str(declared)]


def _real_launch(tmp_path, monkeypatch, fixture):
    """The entrance's launch goes to the real implementer launcher, with a Codex stand-in, in this fixture's store."""
    home = tmp_path / "launch-home"
    home.mkdir()
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(home))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    scenario = tmp_path / "scenario.json"
    # The stand-in answers as the session the fixture's builder turns recorded, as a resumed builder does.
    from version_fixture import BUILDER_SESSION
    scenario.write_bytes(json.dumps({"codex": {"native_session": BUILDER_SESSION}}).encode())
    # The build resumes the fixture's own builder, in the root its turns recorded.
    recorded = [json.loads(path.read_bytes()) for path in fixture.record_root.rglob("*.request.json")]
    root = Path(next(request["root"] for request in recorded if request.get("root")))
    branch = next((request["lineage_branch"] for request in recorded if request.get("lineage_branch")), None)
    monkeypatch.setattr(work, "_dispatch_root", lambda *_a, **_k: (root, branch, False))
    monkeypatch.setattr(work, "_attached_branch", lambda _root: branch)
    monkeypatch.setattr(work, "_runtime_argument", lambda vendor, explicit=None: [f"--{vendor}", "fixture"])
    monkeypatch.setattr(work, "_selected_runtime_argument", lambda *_a, **_k: [])
    setting = home / ".tradecraft" / "implementer-vendor"
    setting.parent.mkdir(parents=True)
    setting.write_bytes(b"codex")
    original = work._recipient_run
    commands = []

    def launch(command, **kwargs):
        commands.append(command)
        if Path(command[1]).name != "dispatch_implementer.py":
            return original(command, **kwargs)
        output = fixture.record_root / f"launch-{len(commands)}" / "result.md"
        actual = [sys.executable, str(LIB / "tests" / "fixtures" / "window_launcher.py"), str(scenario),
                  *command[2:], "--output", str(output)]
        return original(actual, **kwargs)
    monkeypatch.setattr(work, "_recipient_run", launch)
    return commands


def _bundles(fixture):
    """The bundles this test's launches wrote, beside the fixture's own builder turns."""
    return sorted(fixture.record_root.glob("launch-*/result.md.request.json"))


def test_978_declared_cap_through_the_entrance_to_a_real_launcher(tmp_path, monkeypatch, capfd):
    fixture = three_turn_proof_change(tmp_path, monkeypatch)
    home = tmp_path / "records-home"
    monkeypatch.setattr(work, "_records_home", lambda _state: home)
    commands = _real_launch(tmp_path, monkeypatch, fixture)
    declared = ["--preflight-cap-seconds", "1800", "--preflight-cap-reason", "large repository"]
    capfd.readouterr()
    # The entrance, past the default cap but inside the declared one, launches.
    work.main(["run", "build", "--repo", REPO, "--issue", "12", "--root", str(fixture.holder_root),
               "--holder-session-id", "holder", *declared], started=time.monotonic() - 901)
    out, err = _searched(capfd)
    window = json.loads(out.splitlines()[0].removeprefix("work: window "))
    assert _bundles(fixture), (commands, [{key: report.get(key) for key in ("stage", "status", "reason", "detail")}
                                          for report in map(json.loads, (line for line in out.splitlines()
                                                                         if line.startswith("{")))],
                               err[-1500:])
    [request_path] = _bundles(fixture)
    request = json.loads(request_path.read_bytes())
    # The entrance passed its declared cap to the launcher, whose record carries it and the same return time.
    assert "--preflight-cap-seconds" in commands[0]
    assert request["preflight_cap"] == {"seconds": 1800, "source": "declared", "reason": "large repository"}
    assert request["latest_return_at"] == window["latest_return_at"]
    record = json.loads(Path(window["cap_record"]).read_bytes())
    assert record["outcome"] == "launched"
    assert record["bundle"] == str(request_path.with_name("result.md.run.json"))
    # The real launcher's own check at its request write refuses when its cap is nearly spent.
    capfd.readouterr()
    work.main(["run", "build", "--repo", REPO, "--issue", "12", "--root", str(fixture.holder_root),
               "--holder-session-id", "holder", *declared], started=time.monotonic() - 1797)
    out, err = _searched(capfd)
    assert len(_bundles(fixture)) == 1, (out, err)
    refused = [json.loads(path.read_bytes()) for path in (home / "preflight-caps").rglob("*.json")]
    assert sorted(row["outcome"] for row in refused) == ["launched", "refused-at-cap"], [
        {key: report.get(key) for key in ("stage", "status", "reason", "detail")}
        for report in map(json.loads, (line for line in out.splitlines() if line.startswith("{")))]
    # A stage that launches nobody completes its work, one past its declared cap refuses there,
    # and a floor with no command holds by decision.
    monkeypatch.setattr(work, "_execute_proof", lambda *_a, **_k: 0)
    for stage, spent in (("proof", 901), ("proof", 1801), ("floor", 0)):
        work.main(["run", stage, "--repo", REPO, "--issue", "12", "--root", str(fixture.holder_root),
                   "--holder-session-id", "holder", *declared], started=time.monotonic() - spent)
    # A following release report lists every declared cap with its outcome.
    # This change's own fixture holds before the report for want of a reach reading, so the stage runs on
    # the release-report harness's change, reading this test's records home.
    released = tw.state(pr=True)
    released.pr["mergeable_state"] = "clean"
    released.record_root = tmp_path / "release-store"
    released.record_root.mkdir()
    monkeypatch.setattr(work.records, "default_record_root", lambda: released.record_root)

    class ReleaseTransport:
        def get(self, endpoint, *, paginate=False):
            if endpoint == f"{BASE}/pulls/7":
                return released.pr
            return tw.FakeTransport({}).get(endpoint, paginate=paginate)
    capfd.readouterr()
    assert work.execute_stage(released, work.Decision("release-report", False, None, "holder-named-stage"),
                              tmp_path, None, transport=ReleaseTransport()) == 0
    out, err = _searched(capfd)
    reports = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    assert "declared_caps" in reports[-1], [{key: report.get(key) for key in ("stage", "status", "reason")}
                                           for report in reports]
    rows = reports[-1]["declared_caps"]
    assert sorted((row["stage"], row["outcome"]) for row in rows) == [
        ("build", "launched"), ("build", "refused-at-cap"), ("floor", "held"),
        ("proof", "completed"), ("proof", "refused-at-cap")]
    assert all(row["preflight_cap"]["reason"] == "large repository" for row in rows)
    # Read with the store that holds the launch's own bundle, spelled another way, the launch is still one row.
    both = work.declared_caps(f"{REPO}#12", fixture.record_root / "launch-1" / "..")
    assert sorted((row["stage"], row["outcome"]) for row in both) == sorted(
        (row["stage"], row["outcome"]) for row in rows)
    assert all(isinstance(row[key], (str, type(None))) for row in both for key in ("record", "bundle"))


def test_978_a_worktree_add_that_outlasts_the_cap_leaves_no_orphan(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = tw.repository(tmp_path, "holder")
    probe = work._run_probe

    def slow_add(command, **kwargs):
        result = probe(command, **kwargs)
        if command[3:5] == ["worktree", "add"]:
            time.sleep(3)  # The add runs to its end, past the cap's.
        return result
    monkeypatch.setattr(work, "_run_probe", slow_add)
    deadline = run_lifecycle.stage_deadline("build", 600, started=time.monotonic() - 898)
    with run_lifecycle.deadline_scope(deadline), pytest.raises(run_lifecycle.PreflightCapExceeded):
        work.create_implementation_root(holder, "example/product", 12, None, "holder-session")
    # The refusal leaves neither a worktree nor a branch the registry does not name.
    listed = subprocess.run(["git", "-C", str(holder), "worktree", "list", "--porcelain"],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True).stdout
    assert listed.count("worktree ") == 1
    branches = subprocess.run(["git", "-C", str(holder), "branch", "--list", "tradecraft/12-*"],
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True).stdout
    assert branches.strip() == ""
    assert not list((holder / ".claude" / "worktrees").glob("issue-12-*"))


@pytest.mark.parametrize("when", ["before the add", "a failed add"])
def test_978_a_refusal_removes_nothing_the_add_did_not_make(tmp_path, monkeypatch, when):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = tw.repository(tmp_path, "holder")
    # Another run's branch already carries the name this run would choose.
    monkeypatch.setattr(work.secrets, "token_hex", lambda _n: "0123456789ab")
    tw.git(holder, "branch", "tradecraft/12-0123456789ab")
    probe = work._run_probe

    def slow_add(command, **kwargs):
        result = probe(command, **kwargs)
        if command[3:5] == ["worktree", "add"]:
            time.sleep(3)  # The add fails on the existing branch, and the cap ends meanwhile.
        return result
    monkeypatch.setattr(work, "_run_probe", slow_add)
    if when == "before the add":
        prepare = work._ensure_implementation_parent_ignored
        # The cap ends after the holder's reads and before the add begins.
        monkeypatch.setattr(work, "_ensure_implementation_parent_ignored",
                            lambda root: (prepare(root), time.sleep(3))[0])
    deadline = run_lifecycle.stage_deadline("build", 600, started=time.monotonic() - 898)
    with run_lifecycle.deadline_scope(deadline), pytest.raises((run_lifecycle.PreflightCapExceeded, work.WorkError)):
        work.create_implementation_root(holder, "example/product", 12, None, "holder-session")
    branches = subprocess.run(["git", "-C", str(holder), "branch", "--list", "tradecraft/12-*"],
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True).stdout
    assert "tradecraft/12-0123456789ab" in branches


def test_978_a_refusal_during_registration_leaves_no_unregistered_worktree(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    holder = tw.repository(tmp_path, "holder")
    snapshot = work._git_snapshot

    def slow_snapshot(path):
        time.sleep(3)  # The cap ends while the registration reads the new worktree.
        return snapshot(path)
    monkeypatch.setattr(work, "_git_snapshot", slow_snapshot)
    deadline = run_lifecycle.stage_deadline("build", 600, started=time.monotonic() - 898)
    with run_lifecycle.deadline_scope(deadline), pytest.raises(run_lifecycle.PreflightCapExceeded):
        work.create_implementation_root(holder, "example/product", 12, None, "holder-session")
    # The registry was never written, so nothing the add made is left behind.
    listed = subprocess.run(["git", "-C", str(holder), "worktree", "list", "--porcelain"],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True).stdout
    assert listed.count("worktree ") == 1
    branches = subprocess.run(["git", "-C", str(holder), "branch", "--list", "tradecraft/12-*"],
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True).stdout
    assert branches.strip() == ""
    assert not [row for row in work.read_registry()["worktrees"] if "issue-12-" in str(row.get("root"))]
