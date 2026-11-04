"""The cold reader's tree, prompt, account form and currency judgement."""
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cold_reader  # noqa: E402
import dispatch_seat  # noqa: E402
import launch_settings  # noqa: E402
import recipient_tree  # noqa: E402
import work  # noqa: E402

BRANCH = "feature/fixture-branch"
ISSUE_TITLE = "Distinctive issue title quokka"
WORK = "example/product" + "#" + str(12)
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
        "design/x.md": "# Design\n\n## S\n\nIn force: [D1](../decisions/D1.md).\n\n"
                       "## Other\n\n[D2](../decisions/D2.md) and [w](../other/w.md).\n",
        "design/y.md": "# Y\n", "notes/z.md": "# Z\n",
        "decisions/D1.md": "# D1\n", "decisions/D2.md": "# D2\n", "other/w.md": "# W\n",
    }, "base")
    head = commit(root, {
        "a.py": "# Design: design/x.md#s\n# See design/y.md for more.\nPATH = \"notes/z.md\"\n",
        "b.py": "# Design: design/missing.md#s\n",
        "decisions/D3.md": "# D3\n\nDecided in #" + "12" + ".\n",
    }, "change")
    return SimpleNamespace(root=root, base=base, head=head, tmp=tmp_path)


def build(repository, covered=None, name="reading", branch=BRANCH):
    return cold_reader.build_tree(
        source=repository.root, output=repository.tmp / name, work=WORK,
        producer_version="0.206.0", base_tip=repository.base, head=repository.head,
        covered=covered, branch=branch, numbers=[12, 7])


def test_tree_carries_only_changed_files_pointed_sections_and_their_in_force_records(repository):
    metadata = cold_reader.load_metadata(build(repository))
    assert sorted(metadata["files"]) == ["a.py", "b.py", "decisions/D1.md", "decisions/D3.md",
                                        "design/x.md"]
    tree = repository.tmp / "reading"
    for absent in ("design/y.md", "notes/z.md", "decisions/D2.md", "other/w.md"):
        assert not (tree / absent).exists()
    assert metadata["coverage"]["b.py"]["dependencies"][0]["blob"] == "absent"
    assert metadata["whole"] is True
    assert metadata["residue"] == {"decisions/D3.md": {"#" + str(12): 1}}
    assert git(tree, "rev-list", "--count", "HEAD") == "1"
    assert git(tree, "remote") == ""


def test_tree_naming_the_branch_is_refused_before_launch(repository):
    commit(repository.root, {"c.py": "# from " + BRANCH + "\n"}, "leak")
    repository.head = git(repository.root, "rev-parse", "HEAD")
    with pytest.raises(cold_reader.ColdReaderError, match="names the change's branch"):
        build(repository)


def test_prompt_carries_the_standard_form_and_no_record_of_the_change(repository):
    metadata = cold_reader.load_metadata(build(repository))
    prompt = cold_reader.compose_prompt(metadata, "STANDARD TEXT", "diff body").decode("utf-8")
    for heading in cold_reader.HEADINGS:
        assert heading in prompt
    for kind in cold_reader.FLAG_KINDS:
        assert kind in prompt
    assert "Can tell: yes" in prompt and "STANDARD TEXT" in prompt and "At most 5" in prompt
    assert BRANCH not in prompt and ISSUE_TITLE not in prompt


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
    assert result["covered"] and result["flags"]


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
