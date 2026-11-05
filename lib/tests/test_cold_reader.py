"""The cold reader's tree, prompt, account form and currency judgement.

Design: lib/DESIGN.md#the-cold-reader
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cold_reader  # noqa: E402
import dispatch_seat  # noqa: E402
import launch_settings  # noqa: E402
import recipient_tree  # noqa: E402
import test_work  # noqa: E402
import work  # noqa: E402

BRANCH = "feature/fixture-branch"
# Assembled at run time, so a search of the library for issue references or dates finds only real ones.
ISSUE = "#" + str(12)
WORK = "example/product" + ISSUE
DAY = "-".join(("2026", "11", "04"))


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True,
                          stdin=subprocess.DEVNULL,
                          text=True).stdout.strip()


def commit(root, files, message):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    git(root, "add", "--all")
    git(root, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-q", "-m", message)
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "core.autocrlf", "false")
    base = commit(root, {
        "design/x.md": "# Design\n\n## S\n\nIn force: [D1](../decisions/D1.md). See [g](../notes/guide.md).\n\n"
                       "## Other\n\n[D2](../decisions/D2.md) and [w](../other/w.md).\n",
        "design/y.md": "# Y\n", "notes/z.md": "# Z\n", "notes/guide.md": "# Guide\n",
        "decisions/D1.md": "# D1\n", "decisions/D2.md": "# D2\n", "other/w.md": "# W\n",
    }, "base")
    head = commit(root, {
        "a.py": "# Design: design/x.md#s\n# See design/y.md for more.\nPATH = \"notes/z.md\"\n",
        "b.py": "# Design: design/missing.md#s\n",
        "decisions/D3.md": "# D3\n\nDecided in " + ISSUE + ".\n",
    }, "change")
    return SimpleNamespace(root=root, base=base, head=head, tmp=tmp_path)


def build(repository, covered=None, name="reading", branch=BRANCH):
    return cold_reader.build_tree(
        source=repository.root, output=repository.tmp / name, work=WORK,
        producer_version="0.206.0", base_tip=repository.base, head=repository.head,
        covered=covered, branch=branch, numbers=[12, 7])


def test_tree_carries_only_changed_files_pointed_sections_and_every_link_inside_them(repository):
    metadata = cold_reader.load_metadata(build(repository))
    assert sorted(metadata["files"]) == ["a.py", "b.py", "decisions/D1.md", "decisions/D3.md",
                                        "design/x.md", "notes/guide.md"]
    tree = repository.tmp / "reading"
    for absent in ("design/y.md", "notes/z.md", "decisions/D2.md", "other/w.md"):
        assert not (tree / absent).exists()
    assert metadata["coverage"]["b.py"]["dependencies"][0]["blob"] == "absent"
    assert metadata["whole"] is True
    assert metadata["residue"] == {"decisions/D3.md": {ISSUE: 1}}
    assert git(tree, "rev-list", "--count", "HEAD") == "1"
    assert git(tree, "remote") == ""


def test_tree_naming_the_branch_is_refused_before_launch(repository):
    commit(repository.root, {"c.py": "# from " + BRANCH + "\n"}, "leak")
    repository.head = git(repository.root, "rev-parse", "HEAD")
    with pytest.raises(cold_reader.ColdReaderError, match="names the change's branch"):
        build(repository)


def test_prompt_carries_the_standard_and_the_account_form(repository):
    metadata = cold_reader.load_metadata(build(repository))
    prompt = cold_reader.compose_prompt(metadata, "STANDARD TEXT", "diff body").decode("utf-8")
    for heading in cold_reader.HEADINGS:
        assert heading in prompt
    for kind in cold_reader.FLAG_KINDS:
        assert kind in prompt
    assert "Can tell: yes" in prompt and "STANDARD TEXT" in prompt and "At most 5" in prompt


def test_reread_prompt_names_its_covered_paths_for_reference_only(repository):
    metadata = cold_reader.load_metadata(build(repository, covered=["a.py"]))
    prompt = cold_reader.compose_prompt(metadata, "S", "d").decode("utf-8")
    assert metadata["whole"] is False and "- `a.py`" in prompt and "reference only" in prompt


ACCOUNT = """## Sections
a.py:1-3 {dash} opens with its pointer; reason found in design/x.md.

## Flags
a.py:2 {dash} what-comment {dash} the second line restates the code

## Why this change was made
Can tell: {tell}
decisions/D3.md says why.

## Worth a look
a.py:1 {dash} a pointer done right.
"""


def test_account_form_is_checked_and_parsed():
    assert cold_reader.form_errors(ACCOUNT.format(dash=cold_reader.EM_DASH, tell="yes")) == []
    parsed = cold_reader.parse_account(ACCOUNT.format(dash=cold_reader.EM_DASH, tell="no"))
    assert parsed["can_tell"] is False and parsed["flags"][0]["kind"] == "what-comment"
    missing = ACCOUNT.format(dash=cold_reader.EM_DASH, tell="yes").replace("## Flags", "## Flagz")
    assert "missing heading ## Flags" in cold_reader.form_errors(missing)
    no_line = ACCOUNT.format(dash=cold_reader.EM_DASH, tell="maybe")
    assert any("Can tell" in error for error in cold_reader.form_errors(no_line))


def entry(blob, dependencies=()):
    return {"blob": blob, "dependencies": list(dependencies)}


def reading(identity, coverage, *, flags=(), tell=True):
    return {"id": identity, "coverage": coverage,
            "account": {"flags": [{"path": path, "kind": "cannot-tell", "text": "t"} for path in flags],
                        "can_tell": tell}}


X = {"pointer": "design/x.md#s", "path": "design/x.md", "blob": "x1", "records": []}


def present(**coverage):
    return {"change_set": {path: value["blob"] for path, value in coverage.items()},
            "coverage": coverage}


def test_assess_rereads_only_the_changed_file():
    first = reading("r1", {"a": entry("a1"), "b": entry("b1")})
    result = cold_reader.assess([first], present(a=entry("a2"), b=entry("b1")))
    assert result["stale"] == ["a"]


def test_assess_rereads_a_file_whose_pointed_document_changed():
    first = reading("r1", {"a": entry("a1", [X])})
    moved = {**X, "blob": "x2"}
    assert cold_reader.assess([first], present(a=entry("a1", [moved])))["stale"] == ["a"]
    absent = reading("r1", {"a": entry("a1", [{**X, "blob": "absent"}])})
    assert cold_reader.assess([absent], present(a=entry("a1", [X])))["stale"] == ["a"]


def test_assess_holds_a_flag_on_an_unchanged_dependency():
    first = reading("r1", {"a": entry("a1", [X])}, flags=["design/x.md"])
    result = cold_reader.assess([first], present(a=entry("a1", [X])))
    assert not result["stale"] and result["flags"]


def test_assess_only_a_whole_reading_clears_cannot_tell():
    whole = {"a": entry("a2"), "b": entry("b1")}
    said_no = reading("r1", {"a": entry("a1"), "b": entry("b1")}, tell=False)
    narrow_yes = reading("r2", {"a": entry("a2")}, tell=True)
    assert cold_reader.assess([said_no, narrow_yes], present(**whole))["standing_no"] is True
    whole_yes = reading("r3", whole, tell=True)
    assert cold_reader.assess([said_no, narrow_yes, whole_yes], present(**whole))["standing_no"] is False


def test_cold_reader_role_defaults_to_the_cold_classification():
    args = SimpleNamespace(role=None, stage="cold-reader", classification="cold")
    assert dispatch_seat.selected_role(args) == "cold_reader"
    assert "cold_reader" in launch_settings.ROLES
    assert work.MODEL_OVERRIDE_ROLES["cold-reader"] == "cold_reader"
    assert dispatch_seat.CLAUDE_EFFORTS["cold"] == "xhigh"


def test_cold_reader_seat_reads_without_a_shell_or_web_tool():
    boundary = dispatch_seat.permission_boundary("claude", "read", Path("root"))
    assert "tools=Read,Glob,Grep;" in boundary
    assert "Codex sandbox=read-only" in dispatch_seat.permission_boundary("codex", "read", Path("root"))


def test_cold_reading_marker_contract_and_stage_are_declared():
    assert "cold-reader" in work.COMMANDS
    assert work.MARKER_CONTRACTS["cold-reading"]["required"] == {"head", "status", "staffing_status"}
    assert work.STAGE_SAFETY["cold-reader"][0][0] == work.COLD_READER_VERSION


def bundle(store, name, account, tree_root, completed=DAY + "T10:00:00Z"):
    store.mkdir(parents=True, exist_ok=True)
    (store / f"{name}.source.bin").write_text(account, encoding="utf-8")
    (store / f"{name}.request.json").write_text(json.dumps({
        "schema_version": work.records.SCHEMA_VERSION, "work": WORK,
        "stage": "cold-reader", "root": str(tree_root)}), encoding="utf-8")
    (store / f"{name}.run.json").write_text(json.dumps({
        "schema_version": work.records.SCHEMA_VERSION, "outcome": "success",
        "completed_at": completed, "staffing_status": "degraded",
        "staffing_qualification": {"same_vendor_reason": "owner-selected-claude-implementer"},
        "result": {"source_output": f"{name}.source.bin"}}), encoding="utf-8")


@pytest.mark.cold_reading
def test_an_open_reading_counts_only_with_the_seat_return_unaltered(repository):
    metadata = build(repository)
    store = repository.tmp / "records"
    account = ACCOUNT.format(dash=cold_reader.EM_DASH, tell="yes")
    bundle(store, "r1", account, repository.tmp / "reading")
    marker = ("<!-- tradecraft:cold-reading:v1 head=" + repository.head + " status=open "
              "staffing_status=degraded same_vendor_reason=owner-selected-claude-implementer -->\n\n")
    review = "\n\n### Holder's review against the brief\n\nNone.\n"
    producer = "holder-bot"
    config = work.WorkConfig(marker_producers=frozenset({producer}))

    def state(body):
        fixture = work.WorkState("example/product", 12, {"number": 12, "state": "open", "body": ""},
                                 issue_comments=[{"id": 5, "body": body, "user": {"login": producer},
                                                  "created_at": DAY + "T11:00:00Z"}],
                                 config=config, record_root=store)
        work.validate_marker_claims(fixture)
        return fixture

    assert metadata.exists()
    kept = state(marker + account + review)
    assert [m.name for m in kept.markers if m.name == "cold-reading"] == ["cold-reading"]
    edited = state(marker + account.replace("restates the code", "restates code") + review)
    assert not [m for m in edited.markers if m.name == "cold-reading"]
    assert any(claim["name"] == "cold-reading" for claim in edited.invalid_marker_claims)


CLEAN = ACCOUNT.replace("a.py:2 {dash} what-comment {dash} the second line restates the code", "none")
# The brief posts at the clock's start, so every comment and turn the harness adds orders after it.
CLOCK_START = datetime(*map(int, DAY.split("-")), 10, tzinfo=timezone.utc)


def flagged(path, tell="yes"):
    return ACCOUNT.replace("a.py:2", path + ":1").format(dash=cold_reader.EM_DASH, tell=tell)


def clean(tell="yes"):
    return CLEAN.format(dash=cold_reader.EM_DASH, tell=tell)


class Change:
    """One implementing pull request whose reading the gate judges."""

    def __init__(self, tmp_path, monkeypatch, brief=test_work.MECHANICAL, config=test_work.CONFIG):
        self.tmp, self.config, self.brief = tmp_path, config, brief
        self.root = tmp_path / "source"
        self.root.mkdir()
        self.store = tmp_path / "store"
        self.clock = CLOCK_START
        self.comments = []
        self.readings = 0
        # The ledger comparison has its own suite; here it would read an unrelated store.
        monkeypatch.setattr(work, "_governing_terms_decision", lambda _state: None)
        monkeypatch.setattr(work, "_cold_reading_source", lambda _state: self.store)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "core.autocrlf", "false")
        self.base = commit(self.root, {
            "design/x.md": "# Design\n\n## S\n\nIn force: [D1](../decisions/D1.md).\n",
            "decisions/D1.md": "# D1\n",
        }, "base")
        git(self.root, "checkout", "-q", "-b", "feature")
        self.head = commit(self.root, {"a.py": "# Design: design/x.md#s\nA = 1\n",
                                       "b.py": "# Design: design/missing.md#s\nB = 1\n"}, "change")
        self.builder_turn("the first build")

    def tick(self):
        self.clock += timedelta(minutes=1)
        return self.clock.isoformat()

    def commit(self, files):
        self.head = commit(self.root, files, "repair")
        return self.head

    def merge_base_change(self, files):
        git(self.root, "checkout", "-q", "main")
        self.base = commit(self.root, files, "base moves")
        git(self.root, "checkout", "-q", "feature")
        git(self.root, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
            "merge", "-q", "--no-edit", "main")
        self.head = git(self.root, "rev-parse", "HEAD")

    def builder_turn(self, prompt):
        turns = len(list(self.store.glob("build-*.run.json"))) if self.store.exists() else 0
        name = f"build-{turns}"
        self.store.mkdir(parents=True, exist_ok=True)
        launched = self.tick()
        (self.store / f"{name}.dispatch.bin").write_text(prompt, encoding="utf-8")
        (self.store / f"{name}.request.json").write_text(json.dumps({
            "schema_version": work.records.SCHEMA_VERSION, "work": WORK, "stage": "build",
            "launched_at": launched}), encoding="utf-8")
        (self.store / f"{name}.run.json").write_text(json.dumps({
            "schema_version": work.records.SCHEMA_VERSION, "outcome": "success",
            "completed_at": self.tick()}), encoding="utf-8")
        return name

    def read(self, account, covered=None):
        self.readings += 1
        name = f"reading-{self.readings}"
        cold_reader.build_tree(source=self.root, output=self.tmp / name, work=WORK,
                               producer_version="0.206.0", base_tip=self.base, head=self.head,
                               covered=covered, branch=BRANCH, numbers=[12])
        bundle(self.store, name, account, self.tmp / name, completed=self.tick())
        return account

    def post(self, body):
        self.comments.append({"id": len(self.comments) + 100, "body": body,
                              "user": {"login": test_work.PRODUCER}, "created_at": self.tick()})
        return body

    def post_open(self, account):
        return self.post(f"<!-- tradecraft:cold-reading:v1 head={self.head} status=open "
                         "staffing_status=degraded same_vendor_reason=owner-selected-claude-implementer -->\n\n"
                         + account + "\n\n### Holder's review against the brief\n\nNo misreading.\n")

    def review(self, opened):
        return self.builder_turn("--- cold reading begin ---\n" + opened + "\n--- cold reading end ---")

    def post_clean(self):
        return self.post(f"<!-- tradecraft:cold-reading:v1 head={self.head} status=clean "
                         "staffing_status=degraded same_vendor_reason=owner-selected-claude-implementer -->\n"
                         "The builder found no misreading.")

    def reviewed(self, account, covered=None):
        """A reading, its posted account and the builder's review of it."""
        self.read(account, covered)
        self.review(self.post_open(account))

    def state(self, draft=True):
        fixture = test_work.state(self.brief, pr=True, draft=draft, config=self.config)
        fixture.issue_comments[0]["created_at"] = CLOCK_START.isoformat()
        fixture.issue_comments.extend(self.comments)
        fixture.issue_comments.append({"body": f"<!-- tradecraft:floor:v1 head={self.head} status=pass -->",
                                       "user": {"login": test_work.PRODUCER}})
        fixture.pr["head"].update(sha=self.head, ref=BRANCH)
        fixture.pr["base"]["sha"] = self.base
        fixture.holder_root = self.root
        return fixture

    def decide(self, draft=True):
        fixture = self.state(draft)
        decision = work.decide(fixture, test_work.RULES)
        invalid = [claim for claim in fixture.invalid_marker_claims if claim["name"] == "cold-reading"]
        return SimpleNamespace(stage=decision.stage, reason=decision.reason, detail=decision.detail,
                               continuity=decision.continuity, invalid=invalid)


def covered(decision):
    return json.loads(decision.detail)["covered"]


def settled(change):
    # The "would" fixture carries a brief, a draft, its cold verdict, a settlement and holder readings.
    fixture = test_work._source_fixture("would")
    change.brief = fixture.issue_comments[0]["body"]
    change.comments = [dict(comment, created_at=change.tick()) for comment in fixture.issue_comments[1:]]


@pytest.fixture
def change(tmp_path, monkeypatch):
    return Change(tmp_path, monkeypatch)


@pytest.mark.cold_reading
def test_no_reading_owes_a_reader_of_the_whole_change(change):
    decision = change.decide()
    assert (decision.stage, decision.reason, decision.continuity) == ("cold-reader", "cold-reading-absent", "fresh")
    assert covered(decision) == ["a.py", "b.py"]


@pytest.mark.cold_reading
def test_an_unposted_reading_is_the_holders_to_post(change):
    change.read(clean())
    assert change.decide().reason == "cold-reading-post-owed"


@pytest.mark.cold_reading
def test_an_open_reading_resumes_the_builder(change):
    change.read(clean())
    change.post_open(clean())
    decision = change.decide()
    assert (decision.stage, decision.continuity, decision.reason) == ("build", "resume", "cold-reading-review-owed")


@pytest.mark.cold_reading
def test_a_builder_commit_rereads_exactly_the_changed_file(change):
    change.reviewed(clean())
    change.commit({"a.py": "# Design: design/x.md#s\nA = 2\n"})
    decision = change.decide()
    assert (decision.stage, decision.reason, covered(decision)) == ("cold-reader", "cold-reading-stale", ["a.py"])


@pytest.mark.cold_reading
def test_a_catch_up_merge_owes_no_reread(change):
    change.reviewed(clean())
    change.merge_base_change({"elsewhere.md": "# Elsewhere\n"})
    assert change.decide().reason == "cold-reading-close"


@pytest.mark.cold_reading
def test_clean_without_a_builder_turn_is_invalid_and_held(change):
    change.read(clean())
    change.post_open(clean())
    change.post_clean()
    decision = change.decide()
    assert decision.reason == "cold-reading-review-owed" and len(decision.invalid) == 1


@pytest.mark.cold_reading
def test_a_valid_clean_reading_reaches_readiness(change):
    change.reviewed(clean())
    assert change.decide().reason == "cold-reading-close"
    change.post_clean()
    decision = change.decide()
    assert (decision.stage, decision.invalid) == ("ready-reviewers", [])


@pytest.mark.cold_reading
def test_a_reviewer_fix_after_readiness_is_read_again_before_proof(change):
    change.reviewed(clean())
    change.post_clean()
    assert change.decide(draft=False).stage != "cold-reader"
    change.commit({"b.py": "# Design: design/missing.md#s\nB = 2\n"})
    decision = change.decide(draft=False)
    assert (decision.stage, covered(decision)) == ("cold-reader", ["b.py"])


@pytest.mark.cold_reading
def test_a_fix_made_only_in_the_pointed_document_rereads_its_file(change):
    change.reviewed(flagged("a.py"))
    assert change.decide().reason == "cold-reading-flag-reread"
    change.commit({"design/x.md": "# Design\n\n## S\n\nWhy A. In force: [D1](../decisions/D1.md).\n"})
    decision = change.decide()
    assert decision.stage == "cold-reader" and "a.py" in covered(decision)


@pytest.mark.cold_reading
def test_creating_an_absent_pointer_target_rereads_its_file(change):
    change.reviewed(clean())
    change.commit({"design/missing.md": "# Missing\n\n## S\n\nNow here.\n"})
    decision = change.decide()
    assert decision.stage == "cold-reader" and "b.py" in covered(decision)


@pytest.mark.cold_reading
def test_cannot_tell_holds_a_clean_and_owes_a_whole_reread(change):
    change.reviewed(clean(tell="no"))
    change.post_clean()
    decision = change.decide()
    assert (decision.reason, covered(decision)) == ("cold-reading-why-owed", ["a.py", "b.py"])
    assert len(decision.invalid) == 1


@pytest.mark.cold_reading
def test_a_whole_reread_saying_yes_after_a_decision_record_clears_cannot_tell(change):
    change.reviewed(clean(tell="no"))
    change.commit({"decisions/D2.md": "# D2\n\nWhy A and B exist.\n"})
    change.reviewed(clean())
    change.post_clean()
    assert change.decide().stage == "ready-reviewers"


@pytest.mark.cold_reading
def test_a_flag_on_an_unchanged_dependency_holds_clean(change):
    change.reviewed(flagged("design/x.md"))
    change.post_clean()
    decision = change.decide()
    assert (decision.reason, covered(decision)) == ("cold-reading-flag-reread", ["a.py"])
    assert len(decision.invalid) == 1
    change.commit({"design/x.md": "# Design\n\n## S\n\nWhy A. In force: [D1](../decisions/D1.md).\n"})
    decision = change.decide()
    assert decision.stage == "cold-reader" and "a.py" in covered(decision)
    change.reviewed(clean(), covered=covered(decision))
    assert change.decide().reason == "cold-reading-close"


@pytest.mark.cold_reading
def test_a_narrow_reread_saying_yes_cannot_clear_cannot_tell(change):
    change.reviewed(clean(tell="no"))
    change.commit({"a.py": "# Design: design/x.md#s\nA = 2\n"})
    change.reviewed(clean(), covered=["a.py"])
    change.post_clean()
    decision = change.decide()
    assert (decision.reason, covered(decision)) == ("cold-reading-why-owed", ["a.py", "b.py"])
    assert len(decision.invalid) == 1


@pytest.mark.cold_reading
def test_the_mechanical_lane_is_gated(change):
    assert change.decide().stage == "cold-reader"


@pytest.mark.cold_reading
def test_an_adopter_with_no_configuration_for_it_is_gated(tmp_path, monkeypatch):
    unconfigured = work.WorkConfig(marker_producers=frozenset({test_work.PRODUCER}))
    assert Change(tmp_path, monkeypatch, config=unconfigured).decide().stage == "cold-reader"


@pytest.mark.cold_reading
def test_a_settled_artifact_lane_is_gated_and_resumes_its_builder(tmp_path, monkeypatch):
    change = Change(tmp_path, monkeypatch, brief=test_work.AFFIRMED)
    settled(change)
    assert change.decide().stage == "cold-reader"
    change.read(clean())
    change.post_open(clean())
    decision = change.decide()
    assert (decision.stage, decision.continuity, decision.reason) == ("build", "resume", "cold-reading-review-owed")


@pytest.mark.cold_reading
@pytest.mark.parametrize("lane", ["mechanical", "settled"])
def test_the_resumed_builder_prompt_carries_the_open_reading_whole(tmp_path, monkeypatch, lane):
    change = Change(tmp_path, monkeypatch)
    if lane == "settled":
        settled(change)
    change.read(flagged("a.py"))
    opened = change.post_open(flagged("a.py"))
    fixture = change.state()
    work.validate_marker_claims(fixture)
    prompt = work._stage_prompt(fixture, work.Decision("build", True, "resume", "cold-reading-review-owed"),
                                branch=BRANCH).decode("utf-8")
    assert opened in prompt
    for sentence in ("Review the account for the reasons you decided while building",
                     "preferring the code", "write the decision record the change then owes",
                     "Never edit or restate the account", "Return your review of it"):
        assert sentence in prompt
    change.review(opened)
    fixture = change.state()
    work.validate_marker_claims(fixture)
    assert work._owed_cold_reading(fixture) is None


@pytest.mark.cold_reading
def test_an_unsupported_reading_bundle_is_unverifiable_rather_than_fatal(change):
    change.read(clean())
    run = change.store / "reading-1.run.json"
    run.write_text(json.dumps({**json.loads(run.read_text("utf-8")), "schema_version": -1}), encoding="utf-8")
    change.post_open(clean())
    decision = change.decide()
    assert decision.reason == "cold-reading-unverifiable" and "reading-1.run.json" in decision.detail
    assert any("unverifiable" in claim["reason"] for claim in decision.invalid)


@pytest.mark.cold_reading
def test_an_unsupported_builder_bundle_is_unverifiable_rather_than_fatal(change):
    change.read(clean())
    change.post_open(clean())
    broken = change.store / (change.builder_turn("an unrelated turn") + ".request.json")
    broken.write_text(json.dumps({**json.loads(broken.read_text("utf-8")), "schema_version": -1}),
                      encoding="utf-8")
    decision = change.decide()
    assert decision.reason == "cold-reading-unverifiable" and broken.stem.split(".")[0] in decision.detail


def run_stage(change, monkeypatch, capsys, returned, builder="claude"):
    captured = {}
    output = change.tmp / ("seat-" + str(change.readings)) / "result.md"

    def invoke(command, _deadline):
        captured["command"] = command
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(returned, encoding="utf-8")
        return 0

    monkeypatch.setattr(work, "_invoke_recipient", invoke)
    monkeypatch.setattr(work, "_producer_vendor", lambda *_a, **_k: (builder, "fixture build bundle"))
    monkeypatch.setattr(work.records, "resolved_output", lambda *_a: output)
    fixture = change.state()
    work.validate_marker_claims(fixture)
    decision = work.Decision("cold-reader", True, work._named_continuity(
        fixture, "cold-reader", work.decide(fixture, test_work.RULES)), "holder-named-stage")
    capsys.readouterr()
    code = work._execute_cold_reader(fixture, decision, dispatch_path=None, tree_metadata=None,
                                     timeout_seconds=600, claude_path=None, codex_path=None)
    report = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")][-1]
    return code, captured["command"], decision, report


def option(command, name):
    return command[command.index(name) + 1]


@pytest.mark.cold_reading
def test_the_stage_launches_one_fresh_read_only_seat_for_a_first_reading_and_a_reread(change, monkeypatch, capsys):
    code, command, decision, report = run_stage(change, monkeypatch, capsys, clean())
    assert code == 0 and decision.continuity == "fresh" and report["whole"] is True
    assert (option(command, "--stage"), option(command, "--classification"), option(command, "--requires")) == (
        "cold-reader", "cold", "read")
    assert command[1].endswith("dispatch_seat.py") and option(command, "--role") == "cold_reader"
    assert not any("resume" in part or part == "--session" for part in command)
    change.reviewed(clean())
    change.commit({"a.py": "# Design: design/x.md#s\nA = 2\n"})
    code, command, decision, report = run_stage(change, monkeypatch, capsys, clean())
    assert decision.continuity == "fresh" and report["covered"] == ["a.py"] and report["whole"] is False
    assert option(command, "--stage") == "cold-reader"


@pytest.mark.cold_reading
def test_the_stage_fails_a_malformed_return_and_names_what_is_missing(change, monkeypatch, capsys):
    malformed = clean().replace("## Why this change was made\nCan tell: yes\n", "")
    code, _command, _decision, report = run_stage(change, monkeypatch, capsys, malformed)
    assert code == 1 and report["form"] == "fail"
    assert "missing heading ## Why this change was made" in report["form_errors"]


@pytest.mark.cold_reading
@pytest.mark.parametrize(("builder", "reason"), [("claude", "owner-selected-claude-implementer"), ("codex", None)])
def test_staffing_is_judged_against_the_builders_vendor(change, monkeypatch, capsys, builder, reason):
    _code, command, _decision, _report = run_stage(change, monkeypatch, capsys, clean(), builder=builder)
    assert option(command, "--vendor") == "claude" and option(command, "--own-vendor") == builder
    assert ("--same-vendor-reason" in command) == (reason is not None)
    if reason:
        assert option(command, "--same-vendor-reason") == reason


def test_a_per_issue_override_names_the_cold_reader():
    override = "<!-- tradecraft:model-override:v1 cold_reader=claude:override-model:high -->"
    fixture = test_work.state(override)
    work.validate_marker_claims(fixture)
    settings = work._launch_settings(fixture, "cold-reader", "claude", "cold")
    assert (settings.model, settings.effort) == ("override-model", "high")
    default = work._launch_settings(test_work.state(), "cold-reader", "claude", "cold")
    assert (default.model, default.effort) == (dispatch_seat.DEFAULT_MODELS["claude"],
                                               dispatch_seat.CLAUDE_EFFORTS["cold"])


@pytest.mark.cold_reading
def test_a_reading_whose_tree_metadata_is_lost_is_unverifiable_rather_than_absent(change):
    change.read(clean())
    work.recipient_tree.metadata_path(change.tmp / "reading-1").unlink()
    decision = change.decide()
    assert decision.reason == "cold-reading-unverifiable" and "reading-1.run.json" in decision.detail


@pytest.mark.cold_reading
def test_a_return_refused_for_its_form_was_never_a_reading(change):
    change.read(clean().replace("## Flags\nnone\n", ""))
    assert change.decide().reason == "cold-reading-absent"


@pytest.mark.cold_reading
def test_an_undated_cold_reading_marker_is_set_aside(change):
    change.read(clean())
    change.post_open(clean())
    del change.comments[-1]["created_at"]
    decision = change.decide()
    assert decision.reason == "cold-reading-post-owed"
    assert [claim["reason"] for claim in decision.invalid] == ["cold-reading marker has no posting time"]


def test_an_underscored_anchor_reaches_its_section_and_records(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "core.autocrlf", "false")
    base = commit(root, {"design/x.md": "# Design\n\n## gate_rules\n\nIn force: [D1](../decisions/D1.md).\n",
                         "decisions/D1.md": "# D1\n"}, "base")
    head = commit(root, {"a.py": "# Design: design/x.md#gate_rules\n"}, "change")
    entry = cold_reader.current(root, base, head)["coverage"]["a.py"]
    assert entry["dependencies"][0]["records"][0]["path"] == "decisions/D1.md"


@pytest.mark.cold_reading
def test_a_damaged_reading_stops_the_builder_prompt_rather_than_leaving_it_out(change):
    change.read(flagged("a.py"))
    change.post_open(flagged("a.py"))
    fixture = change.state()
    work.validate_marker_claims(fixture)
    work.recipient_tree.metadata_path(change.tmp / "reading-1").unlink()
    with pytest.raises(work.WorkError, match="reading-1.run.json"):
        work._stage_prompt(fixture, work.Decision("build", True, "resume", "cold-reading-review-owed"),
                           branch=BRANCH)


@pytest.mark.cold_reading
def test_the_stage_reports_a_damaged_reading_instead_of_raising(change, monkeypatch, capsys):
    change.read(clean())
    work.recipient_tree.metadata_path(change.tmp / "reading-1").unlink()
    monkeypatch.setattr(work, "_invoke_recipient", lambda *_a: pytest.fail("no seat may launch"))
    fixture = change.state()
    work.validate_marker_claims(fixture)
    code = work._execute_cold_reader(fixture, work.Decision("cold-reader", True, "fresh", "holder-named-stage"),
                                     dispatch_path=None, tree_metadata=None, timeout_seconds=600,
                                     claude_path=None, codex_path=None)
    report = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")][-1]
    assert code == 0 and report["status"] == "refused" and report["reason"].startswith("cold-reading-unverifiable")
    assert "reading-1.run.json" in report["detail"]


def test_a_flag_stands_until_a_later_reading_reads_its_path_whole_or_not():
    unwritten = {"pointer": "design/unwritten.md#s", "path": "design/unwritten.md", "blob": "absent",
                 "records": []}
    now = present(a=entry("a1", [unwritten]), b=entry("b1"))
    flagged_reading = reading("r1", {"a": entry("a1", [unwritten]), "b": entry("b1")},
                              flags=["design/unwritten.md"])
    result = cold_reader.assess([flagged_reading], now)
    assert result["flags"] and result["owed"] == ["a"]
    narrow = reading("r2", {"b": entry("b1")})
    whole = {**reading("r3", {"b": entry("b1")}), "whole": True}
    assert cold_reader.assess([flagged_reading, narrow, whole], now)["flags"]
    reached = reading("r4", {"a": entry("a1", [unwritten])})
    assert not cold_reader.assess([flagged_reading, narrow, whole, reached], now)["flags"]


def test_a_flag_nothing_in_the_change_reaches_any_more_is_answered_by_the_reread():
    first = reading("r1", {"a": entry("a1", [X])}, flags=["design/x.md"])
    assert cold_reader.assess([first], present(a=entry("a1", [X])))["flags"]
    result = cold_reader.assess([first], present(a=entry("a2")))
    assert not result["flags"] and result["owed"] == ["a"]


def test_a_flag_on_a_shared_dependency_stands_once():
    shared = reading("r1", {"a": entry("a1", [X]), "b": entry("b1", [X])}, flags=["design/x.md"])
    assert len(cold_reader.assess([shared], present(a=entry("a1", [X]), b=entry("b1", [X])))["flags"]) == 1


@pytest.mark.cold_reading
def test_a_clean_before_the_latest_reading_is_posted_is_set_aside(change):
    change.read(clean())
    change.post_clean()
    decision = change.decide()
    assert decision.reason == "cold-reading-post-owed" and len(decision.invalid) == 1


@pytest.mark.cold_reading
@pytest.mark.parametrize(("builder", "reason"), [("codex", "owner-selected-codex-cold-reader"), ("claude", None)])
def test_an_override_moves_the_reader_to_its_vendor_and_staffing_follows(change, monkeypatch, capsys,
                                                                          builder, reason):
    change.post("<!-- tradecraft:model-override:v1 cold_reader=codex:override-model:high -->")
    plans = []
    monkeypatch.setattr(work.setting_resolution, "print_plan", lambda plan, label: plans.append(plan))
    _code, command, _decision, _report = run_stage(change, monkeypatch, capsys, clean(), builder=builder)
    assert option(command, "--vendor") == "codex" and option(command, "--codex-model") == "override-model"
    assert plans[-1]["primary"]["vendor"] == "codex" and plans[-1]["fallback"]["vendor"] == builder
    assert ("--same-vendor-reason" in command) == (reason is not None)
    if reason:
        assert option(command, "--same-vendor-reason") == reason


@pytest.mark.cold_reading
def test_an_override_naming_another_vendor_is_set_aside_and_the_reader_stays_on_claude(change, monkeypatch,
                                                                                      capsys):
    override = "<!-- tradecraft:model-override:v1 cold_reader=gemini:other-model:high -->"
    unvalidated = test_work.state(override)
    assert work._seat_vendor(unvalidated, "cold-reader")[0] == "claude"
    assert [claim["reason"] for claim in unvalidated.invalid_marker_claims
            if claim["name"] == "model-override"] == ["model override value is invalid"]
    change.post(override)
    _code, command, _decision, _report = run_stage(change, monkeypatch, capsys, clean())
    assert option(command, "--vendor") == "claude"


def test_the_design_section_the_new_code_points_at_names_its_decisions():
    lib = Path(__file__).resolve().parents[1]
    for name in ("cold_reader.py", "work.py"):
        assert "lib/DESIGN.md#the-cold-reader" in (lib / name).read_text("utf-8")
    body = cold_reader.section((lib / "DESIGN.md").read_text("utf-8"), "the-cold-reader")
    in_force = [line for line in (body or "").splitlines() if line.startswith("**Decisions in force:**")]
    assert len(in_force) == 1 and re.search(r"\bD-[0-9]+\b", in_force[0])


@pytest.mark.cold_reading
def test_an_unreadable_builder_prompt_holds_the_gate_naming_its_bundle(change):
    change.read(clean())
    change.post_open(clean())
    name = change.review("--- cold reading begin ---\nlost\n--- cold reading end ---")
    (change.store / f"{name}.dispatch.bin").unlink()
    decision = change.decide()
    assert decision.reason == "cold-reading-unverifiable" and name in decision.detail


@pytest.mark.cold_reading
def test_a_run_the_gate_did_not_order_is_refused(change, monkeypatch, capsys):
    change.read(clean())
    monkeypatch.setattr(work, "_invoke_recipient", lambda *_a: pytest.fail("no seat may launch"))
    fixture = change.state()
    work.validate_marker_claims(fixture)
    code = work._execute_cold_reader(fixture, work.Decision("cold-reader", True, "fresh", "holder-named-stage"),
                                     dispatch_path=None, tree_metadata=None, timeout_seconds=600,
                                     claude_path=None, codex_path=None)
    report = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")][-1]
    assert code == 0 and report["reason"].startswith("cold-reading-not-owed")
    assert "cold-reading-post-owed" in report["detail"]


@pytest.mark.cold_reading
def test_a_bad_timeout_is_refused_before_any_tree_is_built(change):
    fixture = change.state()
    work.validate_marker_claims(fixture)
    with pytest.raises(work.WorkError, match="timeout"):
        work._execute_cold_reader(fixture, work.Decision("cold-reader", True, "fresh", "holder-named-stage"),
                                  dispatch_path=None, tree_metadata=None, timeout_seconds=-1,
                                  claude_path=None, codex_path=None)
    assert not (change.tmp / "cold-reader").exists()


def test_a_flag_on_a_path_outside_the_tree_fails_the_form():
    account = flagged("elsewhere.py")
    assert cold_reader.form_errors(account) == []
    assert cold_reader.form_errors(account, {"a.py"}) == [
        "flag names a path outside the reading's tree: elsewhere.py"]


@pytest.mark.cold_reading
def test_a_reading_flagging_a_path_it_never_held_is_refused_and_run_again(change):
    change.read(flagged("elsewhere.py"))
    decision = change.decide()
    assert (decision.reason, covered(decision)) == ("cold-reading-absent", ["a.py", "b.py"])
    change.reviewed(clean())
    assert change.decide().reason == "cold-reading-close"


@pytest.mark.cold_reading
def test_a_flag_answered_without_touching_its_file_is_reread_until_clear(change):
    change.reviewed(flagged("a.py"))
    change.commit({"b.py": "# Design: design/missing.md#s\nB = 2\n"})
    decision = change.decide()
    assert (decision.reason, covered(decision)) == ("cold-reading-stale", ["a.py", "b.py"])
    change.reviewed(clean(), covered=covered(decision))
    assert change.decide().reason == "cold-reading-close"


@pytest.mark.cold_reading
def test_a_reading_that_cant_be_judged_sets_aside_a_later_clean(change):
    change.reviewed(clean())
    change.post_clean()
    fixture = change.state()
    fixture.holder_root = change.tmp / "no-repository-here"
    decision = work.decide(fixture, test_work.RULES)
    assert decision.reason == "cold-reading-unverifiable"
    assert [claim["reason"] for claim in fixture.invalid_marker_claims if claim["name"] == "cold-reading"] == [
        "cold-reading clean while the reading can't be judged"]


def test_a_flag_on_the_diff_file_is_refused_for_the_changed_file_it_shows():
    account = flagged(cold_reader.DIFF_FILE)
    message = "flag names the diff file rather than the changed file it shows: " + cold_reader.DIFF_FILE
    assert cold_reader.form_errors(account) == [message]
    assert cold_reader.form_errors(account, {"a.py", cold_reader.DIFF_FILE}) == [message]
