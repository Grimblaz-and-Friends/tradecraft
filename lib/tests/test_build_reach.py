"""Git-backed reach and account controls for artifact C1-C4."""
from pathlib import Path
import json
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_reach as reach
from work import Marker


def git(root, *args, check=True, input=None):
    streams = {"stdin": subprocess.DEVNULL} if input is None else {"input": input}
    result = subprocess.run(["git", "-C", str(root), *args], **streams,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode:
        raise AssertionError(result.stderr.decode(errors="replace"))
    return result


def revision(root):
    return git(root, "rev-parse", "HEAD").stdout.decode().strip()


def commit(root, files):
    for name, content in files.items():
        path = root / name
        if content is None:
            path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content if isinstance(content, bytes) else content.encode())
    git(root, "add", "--all")
    git(root, "commit", "--allow-empty", "-m", "fixture")
    return revision(root)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-b", "topic")
    for key, value in {"user.name": "fixture", "user.email": "fixture@example.test",
                       "commit.gpgsign": "false", "core.autocrlf": "false"}.items():
        git(root, "config", key, value)
    commit(root, {})
    return root


def reader(head, *, turns=None, recovered=None, supersets=None, stamp="2026-10-06T12:00:00Z"):
    value = {"schema_version": 1, "turns": turns or [], "recovered_ranges": recovered or [],
             "superset_settlements": supersets or []}
    body = f"<!-- tradecraft:reach-reading:v1 head={head} -->\n\n```json\n{json.dumps(value)}\n```\n"
    return Marker("reach-reading", {"head": head}, body, "holder", "issue-comment", "1", stamp)


def account(items, disposition="row-or-criterion", **reference):
    defaults = {"requirement": "Row 1, C2", "generator": "generate index",
                "ruling_source": "issue comment recording owner ruling"}
    field = reach.REFERENCES[disposition]
    return [{"path": item["path"], "disposition": disposition, "basis": "Holder read this contribution.",
             field: reference.get(field, defaults.get(field))} for item in items]


def turn(root, before, after, *, identity="build-1", stage="build", order="2026-10-06T10:00:00Z",
         returned="2026-10-06T11:00:00Z", error=None, pending=False):
    return (order, str(root / (identity + ".run.json")),
            {"dispatch_id": identity, "stage": stage, "root": str(root), "revision_before": before},
            {"completed_at": returned, "revision_after": after, "attempts": [{"launched": True}]}, error, pending)


def evaluate(root, turns, readings=(), *, head=None, base=None, pr=True, run=None):
    head = head or revision(root)
    pull = {"number": 9, "base": {"sha": base or turns[0][2].get("revision_before")},
            "head": {"sha": head}} if pr else None
    return reach.evaluate(turns, readings, head=head, pr=pull,
                          run=run or (lambda args, path: git(path, *args, check=False)),
                          lineage={"root": str(root), "branch": "topic"})


def measure(root, before, after, **kwargs):
    return reach.measure(reach.Git(root, lambda args, path: git(path, *args, check=False)), before, after, **kwargs)


def test_C1_exact_deletions_shrink_equality_growth_moves_binary(repo):
    before = commit(repo, {"empty": b"", "binary": b"\0abc", "binary-mod": b"\0abc",
                           "shrink.md": "a\nb\nc\n", "equal.md": "a\nb\n", "grow.md": "a\nb\n",
                           "move.txt": "contents\n", "Tests/Example.cs": "a\nb\n"})
    after = commit(repo, {"empty": None, "binary": None, "binary-mod": b"\0abcd",
                          "shrink.md": "a\n", "equal.md": "a\nx\n", "grow.md": "a\nx\ny\n",
                          "move.txt": None, "moved.txt": "contents\n", "Tests/Example.cs": "a\n"})
    items = {item["path"]: item for item in measure(repo, before, after)}
    assert set(items) == {"empty", "binary", "shrink.md", "move.txt", "Tests/Example.cs"}
    assert items["empty"]["deleted"] and items["empty"]["removed"] == 0
    assert items["binary"]["deleted"] and items["binary"]["removed"] is None
    assert (items["shrink.md"]["added"], items["shrink.md"]["removed"]) == (0, 2)
    assert items["Tests/Example.cs"]["removed_test"]
    report = evaluate(repo, [turn(repo, before, after)])
    binary, = report["turns"][0]["binary_modifications"]
    assert binary["path"] == "binary-mod" and binary["added"] is None and binary["removed"] is None
    assert measure(repo, after, after) == []


@pytest.mark.parametrize("name", ["a/TEST/a.py", "tests/a", "__tests__/a", "spec/x", "Specs/x",
                                   "test_alpha.py", "test-alpha", "test.alpha", "alpha_test.py",
                                   "alpha_spec.rb", "alpha.test.tsx", "alpha.spec.js", "TestAlpha.cs",
                                   "AlphaTest.java", "AlphaTests.cs", "AlphaSpec.rb", "AlphaSpecs.cs"])
def test_C1_test_paths(name):
    assert reach.test_path(name)


@pytest.mark.parametrize("name", ["contest.md", "latest.json", "testing/x", "specimen.py", "Testament.md",
                                   "alpha-testimony.md", "a/TestData.json", "alpha_test_data.py"])
def test_C1_test_path_boundaries(name):
    # TestData is conventionally Test*, unlike Testament (no camel boundary).
    assert reach.test_path(name) == (name == "a/TestData.json")


DOC = "title\nchoice: common\ncontext\nreason one\nreason two\nreason three\nend\n"


def merge_fixture(root, *, result="title\nchoice: resolved\ncontext\nend\n", deletion=False):
    initial = commit(root, {"doc.md": DOC, "base-only.md": "one\ntwo\nthree\n", "deleted-by-base": "a\nb\n"})
    git(root, "checkout", "-b", "base")
    base = commit(root, {"doc.md": DOC.replace("common", "other"), "base-only.md": "one\n", "deleted-by-base": None})
    git(root, "checkout", "topic")
    branch = commit(root, {"doc.md": DOC.replace("common", "branch")})
    git(root, "merge", "--no-commit", "base", check=False)
    merged = commit(root, {"doc.md": None if deletion else result})
    return initial, branch, base, merged


def test_C2_resolution_only_counts_all_parent_columns(repo):
    _, branch, base, merged = merge_fixture(repo)
    items = measure(repo, branch, merged)
    assert [item["path"] for item in items] == ["doc.md"]
    assert (items[0]["added"], items[0]["removed"]) == (1, 3)
    assert items[0]["contributions"] == [{"basis": "combined-all-parent-columns", "head": merged,
                                            "parents": [branch, base]}]


def test_C2_deletion_relative_to_every_parent(repo):
    _, branch, _, merged = merge_fixture(repo, deletion=True)
    items = measure(repo, branch, merged)
    assert len(items) == 1 and items[0]["deleted"]
    # The choice lines differ by parent; shared removed lines count once.
    assert (items[0]["added"], items[0]["removed"]) == (0, 6)


@pytest.mark.parametrize("choice", ["other", "branch"])
def test_C2_existing_parent_result_has_no_authored_reach(repo, choice):
    _, branch, _, merged = merge_fixture(repo, result=DOC.replace("common", choice))
    assert measure(repo, branch, merged) == []


def test_C2_clean_merge_excludes_independent_parent_shrink(repo):
    before = commit(repo, {"doc": "a\nb\nc\n", "base": "a\nb\nc\n"})
    git(repo, "checkout", "-b", "base")
    commit(repo, {"base": "a\n"})
    git(repo, "checkout", "topic")
    branch = commit(repo, {"doc": "a\n"})
    git(repo, "merge", "--no-ff", "base", "-m", "clean")
    assert measure(repo, branch, revision(repo)) == []
    assert {item["path"] for item in measure(repo, before, revision(repo))} == {"doc"}


def test_C2_edits_before_and_after_merge_accumulate_without_base_shrink(repo):
    initial = commit(repo, {"doc.md": DOC, "own": "a\nb\nc\nd\n", "incoming": "a\nb\nc\n"})
    git(repo, "checkout", "-b", "base")
    commit(repo, {"doc.md": DOC.replace("common", "other"), "incoming": "a\n"})
    git(repo, "checkout", "topic")
    first = commit(repo, {"doc.md": DOC.replace("common", "branch"), "own": "a\nb\nc\n"})
    git(repo, "merge", "--no-commit", "base", check=False)
    merged = commit(repo, {"doc.md": "title\nchoice: resolved\ncontext\nend\n"})
    after = commit(repo, {"own": "a\n"})
    items = {item["path"]: item for item in measure(repo, initial, after)}
    assert set(items) == {"doc.md", "own"}
    assert (items["doc.md"]["added"], items["doc.md"]["removed"]) == (2, 4)
    assert (items["own"]["added"], items["own"]["removed"]) == (0, 3)
    assert [piece["after"] for piece in items["own"]["contributions"]] == [first, after]
    assert items["doc.md"]["contributions"][1]["head"] == merged


def test_C2_patch_content_resembling_headers_and_unterminated_lines(repo):
    content = "title\nchoice: common\ndiff --combined fake\n@@@ -1 -1 +1 @@@\n--- content\n+++ content\nend"
    commit(repo, {"doc": content})
    git(repo, "checkout", "-b", "base")
    commit(repo, {"doc": content.replace("common", "other")})
    git(repo, "checkout", "topic")
    before = commit(repo, {"doc": content.replace("common", "branch")})
    git(repo, "merge", "--no-commit", "base", check=False)
    after = commit(repo, {"doc": "title\nchoice: resolved\nend"})
    item, = measure(repo, before, after)
    assert (item["added"], item["removed"]) == (1, 4)


@pytest.mark.parametrize("disposition", list(reach.REFERENCES))
def test_C4_each_lawful_disposition_and_later_restore(repo, disposition):
    before = commit(repo, {"tests/a": "a\nb\nc\n"})
    after = commit(repo, {"tests/a": "a\n"})
    restored = commit(repo, {"tests/a": "a\nb\nc\n"})
    turns = [turn(repo, before, after), turn(repo, after, restored, identity="build-2",
              order="2026-10-06T11:05:00Z", returned="2026-10-06T11:30:00Z")]
    reading = reader(after, turns=[{"dispatch_id": "build-1", "items": account(measure(repo, before, after), disposition,
                          restored_by={"dispatch_id": "build-2", "head": restored})}])
    report = evaluate(repo, turns, [reading])
    assert report["state"] == "clear", report
    assert report["turns"][0]["reading_source"] and report["turns"][1]["items"] == []
    assert evaluate(repo, turns)["state"] == "reading-required"


@pytest.mark.parametrize("cause", ["missing-before", "invalid-after", "unavailable-before", "ancestry",
                                    "incompatible-before", "missing-after", "attribution", "ordering", "incomplete", "missing-id", "unsupported-merge"])
def test_C3_every_named_uncertainty_clears_via_superset(repo, cause):
    before = commit(repo, {"doc": "a\nb\nc\n"})
    after = commit(repo, {"doc": "a\n"})
    row = turn(repo, before, after)
    request, record = row[2], row[3]
    if cause == "missing-before":
        request.pop("revision_before")
    elif cause == "invalid-after":
        record["revision_after"] = "not-a-sha"
    elif cause == "unavailable-before":
        request["revision_before"] = "f" * 40
    elif cause == "incompatible-before":
        request["revision_before"] = git(repo, "rev-parse", before + ":doc").stdout.decode().strip()
    elif cause == "missing-after":
        record.pop("revision_after")
    elif cause == "ancestry":
        request["revision_before"], record["revision_after"] = after, before
    elif cause == "attribution":
        row = (*row[:4], "missing target attribution", False)
    elif cause == "ordering":
        row = ("unknown", *row[1:])
    elif cause == "incomplete":
        record.pop("attempts")
    elif cause == "missing-id":
        request.pop("dispatch_id")
    elif cause == "unsupported-merge":
        record["recovery_error"] = "unsupported turn merge output"
    report = evaluate(repo, [row], base=before)
    entry, = report["turns"]
    assert report["state"] == "unmeasurable"
    assert entry["uncertainty"] and entry["superset"]["items"]
    fallback = entry["superset"]
    settlement = {key: fallback[key] for key in ("pull_request", "base", "merge_base", "head", "basis")}
    settlement.update(turn_reference=entry["turn_reference"], reason=entry["uncertainty"], items=account(fallback["items"]))
    settled = evaluate(repo, [row], [reader(after, supersets=[settlement])], base=before)
    assert settled["state"] == "clear", settled
    assert settled["turns"][0]["uncertainty"] == entry["uncertainty"]
    assert settled["turns"][0]["basis"] == "pr-superset"
    partial = {**settlement, "items": []}
    assert evaluate(repo, [row], [reader(after, supersets=[partial])], base=before)["state"] == "unmeasurable"


def test_C3_true_range_recovery_and_empty_range(repo):
    before = commit(repo, {"a": "a\nb\n"})
    after = commit(repo, {"a": "a\n"})
    for end in (before, after):
        row = turn(repo, None, end)
        rows = [row]
        if end == before:
            # The previous proved return independently establishes the empty
            # turn's start; a bare recovered before=after is not evidence.
            rows.insert(0, turn(repo, before, before, identity="build-0", order="2026-10-06T09:00:00Z",
                                returned="2026-10-06T09:30:00Z"))
        reading = reader(end, recovered=[{"dispatch_id": "build-1", "before": before, "after": end,
                                          "basis": "retained native contemporaneous revisions"}],
                         turns=[{"dispatch_id": "build-1", "items": account(measure(repo, before, end))}] if end != before else [])
        report = evaluate(repo, rows, [reading], head=end, base=before)
        assert report["state"] == "clear", report


def test_C3_empty_superset_needs_explicit_settlement_and_pre_pr_route(repo):
    head = revision(repo)
    row = turn(repo, None, head)
    no_pr = evaluate(repo, [row], pr=False)
    assert "open the draft" in no_pr["turns"][0]["superset_error"]
    report = evaluate(repo, [row], base=head)
    assert report["state"] == "unmeasurable" and report["turns"][0]["superset"]["items"] == []
    fallback = report["turns"][0]["superset"]
    settlement = {**fallback, "turn_reference": "build-1", "reason": "no endpoint"}
    assert evaluate(repo, [row], [reader(head, supersets=[settlement])], base=head)["state"] == "clear"


def test_C3_superset_union_retains_growth_and_restoration_and_excludes_base(repo):
    before = commit(repo, {"a": "a\nb\nc\n", "incoming": "a\nb\nc\n"})
    git(repo, "checkout", "-b", "base")
    base = commit(repo, {"incoming": "a\n"})
    git(repo, "checkout", "topic")
    shrink = commit(repo, {"a": "a\n"})
    commit(repo, {"a": "a\nb\nc\nd\ne\nf\n"})
    git(repo, "merge", "--no-ff", "base", "-m", "fixture merge")
    after = revision(repo)
    ordinary = measure(repo, before, after)
    conservative = measure(repo, before, after, conservative=True)
    assert ordinary == []
    assert {item["path"] for item in conservative} == {"a"}
    assert {item["path"] for item in measure(repo, before, shrink)} <= {item["path"] for item in conservative}
    assert reach.superset(reach.Git(repo, lambda args, path: git(path, *args, check=False)),
                          {"number": 9, "base": {"sha": base}, "head": {"sha": after}})["items"] == conservative


def test_C3_missing_objects_and_read_capability_name_repair_then_clear(repo):
    before = commit(repo, {"a": "a\nb\n"})
    head = commit(repo, {"a": "a\n"})
    row = turn(repo, None, head)
    def broken(args, root):
        return subprocess.CompletedProcess(args, 128, b"", b"missing object/read unavailable")
    report = evaluate(repo, [row], base=before, run=broken)
    assert "restore required Git objects/read capability" in report["turns"][0]["superset_error"]
    fallback = evaluate(repo, [row], base=before)["turns"][0]["superset"]
    reading = reader(head, supersets=[{**fallback, "turn_reference": "build-1", "reason": "endpoint lost",
                                     "items": account(fallback["items"])}])
    assert evaluate(repo, [row], [reading], base=before, run=broken)["state"] == "unmeasurable"
    assert evaluate(repo, [row], [reading], base=before)["state"] == "clear"


@pytest.mark.parametrize("mutation", ["partial", "duplicate-path", "duplicate-turn", "unknown-disposition",
                                      "empty-basis", "wrong-reference", "extra-path", "false-restore",
                                      "before-return", "wrong-head"])
def test_C4_invalid_accounts_discharge_nothing(repo, mutation):
    before = commit(repo, {"a": "a\nb\n", "b": "a\nb\n"})
    head = commit(repo, {"a": "a\n", "b": "a\n"})
    items = account(measure(repo, before, head))
    turns = [{"dispatch_id": "build-1", "items": items}]
    stamp = "2026-10-06T12:00:00Z"
    marker_head = head
    if mutation == "partial":
        items.pop()
    elif mutation == "duplicate-path":
        items.append(items[0])
    elif mutation == "duplicate-turn":
        turns.append(turns[0])
    elif mutation == "unknown-disposition":
        items[0]["disposition"] = "reject"
    elif mutation == "empty-basis":
        items[0]["basis"] = " "
    elif mutation == "wrong-reference":
        items[0]["generator"] = "irrelevant field"
    elif mutation == "extra-path":
        items.append({**items[0], "path": "extra"})
    elif mutation == "false-restore":
        items[0] = account([items[0]], "restored", restored_by={"dispatch_id": "build-1", "head": head})[0]
    elif mutation == "before-return":
        stamp = "2026-10-06T10:00:00Z"
    else:
        marker_head = before
    report = evaluate(repo, [turn(repo, before, head)], [reader(marker_head, turns=turns, stamp=stamp)])
    assert report["state"] == "reading-required" and report["diagnostics"], report


def test_C3_no_launch_live_and_launched_failure_inventory(repo):
    before = commit(repo, {"a": "a\nb\n"})
    after = commit(repo, {"a": "a\n"})
    failed = turn(repo, before, after)
    failed[3]["outcome"] = "error"
    assert evaluate(repo, [failed])["state"] == "reading-required"
    unlaunched = turn(repo, before, after)
    unlaunched[3]["attempts"] = [{"launched": False}]
    assert evaluate(repo, [unlaunched])["state"] == "not-due"
    live = turn(repo, before, after, pending=True)
    report = evaluate(repo, [live])
    assert report["state"] == "pending" and report["turns"][0]["items"]
    reading = reader(after, turns=[{"dispatch_id": "build-1", "items": account(measure(repo, before, after))}])
    assert evaluate(repo, [live], [reading])["state"] == "pending"


def test_C4_flag_free_later_turn_retains_same_path_obligations(repo):
    before = commit(repo, {"a": "a\nb\nc\n"})
    first = commit(repo, {"a": "a\nb\n"})
    second = commit(repo, {"a": "a\n"})
    third = commit(repo, {"unrelated": "new\n"})
    turns = [turn(repo, before, first), turn(repo, first, second, identity="build-2",
                 order="2026-10-06T11:01:00Z", returned="2026-10-06T11:05:00Z"),
             turn(repo, second, third, identity="build-3", order="2026-10-06T11:10:00Z",
                  returned="2026-10-06T11:15:00Z")]
    reading = reader(first, turns=[{"dispatch_id": "build-1", "items": account(measure(repo, before, first))}])
    report = evaluate(repo, turns, [reading])
    assert [entry["state"] for entry in report["turns"]] == ["clear", "reading-required", "clear"]
    both = reader(second, turns=[{"dispatch_id": row[2]["dispatch_id"], "items": account(measure(repo, row[2]["revision_before"], row[3]["revision_after"]))} for row in turns[:2]])
    assert evaluate(repo, turns, [both])["state"] == "clear"


def test_C2_octopus_columns_binary_deletion_and_exact_quoted_paths(repo):
    name = "space and caf" + chr(0xe9) + ".md"
    initial = commit(repo, {name: DOC, "binary": b"\0common"})
    parents = []
    for index in range(3):
        git(repo, "checkout", "-B", "side-" + str(index), initial)
        parents.append(commit(repo, {name: DOC.replace("common", str(index))}))
    commit(repo, {name: "title\nchoice: new\ncontext\nend\n", "binary": None})
    tree = git(repo, "rev-parse", "HEAD^{tree}").stdout.decode().strip()
    args = ["commit-tree", tree]
    for parent in parents:
        args += ["-p", parent]
    merged = git(repo, *args, input=b"octopus fixture\n").stdout.decode().strip()
    items = {item["path"]: item for item in measure(repo, parents[0], merged)}
    assert set(items) == {name, "binary"}
    assert items["binary"]["deleted"] and items["binary"]["binary"]
    assert (items[name]["added"], items[name]["removed"]) == (1, 3)
    assert items[name]["contributions"][0]["parents"] == parents


def test_C3_ambiguous_order_requires_each_named_superset_account(repo):
    before = commit(repo, {"a": "a\nb\nc\n"})
    first = commit(repo, {"a": "a\nb\n"})
    second = commit(repo, {"a": "a\n"})
    rows = [turn(repo, before, first), turn(repo, first, second, identity="build-2")]
    report = evaluate(repo, rows, base=before)
    assert report["state"] == "unmeasurable"
    settlements = [{**entry["superset"], "turn_reference": entry["turn_reference"],
                    "reason": entry["uncertainty"], "items": account(entry["superset"]["items"])} for entry in report["turns"]]
    assert evaluate(repo, rows, [reader(second, supersets=settlements[:1])], base=before)["state"] == "unmeasurable"
    assert evaluate(repo, rows, [reader(second, supersets=settlements)], base=before)["state"] == "clear"


def test_C3_in_flight_account_survives_descendants_and_rebase_needs_new_account(repo):
    base = commit(repo, {"a": "a\nb\nc\n"})
    old_head = commit(repo, {"a": "a\n"})
    old_turn = turn(repo, None, old_head)
    entry = evaluate(repo, [old_turn], base=base)["turns"][0]
    reading = reader(old_head, supersets=[{**entry["superset"], "turn_reference": "build-1",
                     "reason": entry["uncertainty"], "items": account(entry["superset"]["items"])}])
    descendant = commit(repo, {"new": "new\n"})
    next_turn = turn(repo, old_head, descendant, identity="build-2", order="2026-10-06T13:00:00Z",
                     returned="2026-10-06T14:00:00Z")
    assert evaluate(repo, [old_turn, next_turn], [reading], base=base)["state"] == "clear"
    git(repo, "checkout", "-B", "replacement", base)
    head = commit(repo, {"a": "replacement\n"})
    report = evaluate(repo, [old_turn], [reading], base=base)
    assert report["state"] == "unmeasurable" and report["diagnostics"]
    entry = report["turns"][0]
    renewed = reader(head, supersets=[{**entry["superset"], "turn_reference": "build-1", "reason": entry["uncertainty"],
                     "items": account(entry["superset"]["items"])}])
    assert evaluate(repo, [old_turn], [reading, renewed], base=base)["state"] == "clear"


@pytest.mark.parametrize("mismatch", ["head", "base", "merge_base", "pull_request", "reason", "unknown-turn", "duplicate"])
def test_C4_superset_exact_bounds_contract(repo, mismatch):
    base = commit(repo, {"a": "a\nb\n"})
    head = commit(repo, {"a": "a\n"})
    row = turn(repo, None, head)
    entry = evaluate(repo, [row], base=base)["turns"][0]
    account_entry = {**entry["superset"], "turn_reference": "build-1", "reason": "range lost",
                     "items": account(entry["superset"]["items"])}
    settlements = [account_entry]
    if mismatch in {"head", "base", "merge_base"}:
        account_entry[mismatch] = "f" * 40
    elif mismatch == "pull_request":
        account_entry["pull_request"] = 100
    elif mismatch == "reason":
        account_entry["reason"] = " "
    elif mismatch == "unknown-turn":
        account_entry["turn_reference"] = "unknown"
    else:
        settlements.append(account_entry)
    assert evaluate(repo, [row], [reader(head, supersets=settlements)], base=base)["state"] == "unmeasurable"


def test_C4_payload_duplicate_keys_nonstring_disposition_and_extra_fences(repo):
    head = revision(repo)
    good = reader(head).body
    for bad in [good.replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1'),
                good + '\n```json\n{}\n```',
                good.replace('"turns": []', '"turns": [{"dispatch_id": "x", "items": [{"path": "a", "disposition": {}, "basis": "x"}]}]')]:
        with pytest.raises(reach.ReachError):
            reach.payload(bad)


def test_C4_restore_reference_needs_proved_selected_lineage(repo):
    before = commit(repo, {"a": "a\nb\n"})
    shrunk = commit(repo, {"a": "a\n"})
    restored = commit(repo, {"a": "a\nb\n"})
    first = turn(repo, before, shrunk)
    later = turn(repo, shrunk, restored, identity="build-2", order="2026-10-06T11:01:00Z",
                 returned="2026-10-06T11:30:00Z", error="unproved target branch/root")
    reading = reader(restored, turns=[{"dispatch_id": "build-1", "items": account(measure(repo, before, shrunk),
                 "restored", restored_by={"dispatch_id": "build-2", "head": restored})}])
    report = evaluate(repo, [first, later], [reading])
    assert report["turns"][0]["state"] == "reading-required" and report["diagnostics"]


@pytest.mark.parametrize("missing", ["before", "after"])
@pytest.mark.parametrize("older", ["base", "intermediate"])
def test_repair_872_superset_cannot_end_before_the_unmeasurable_turn(repo, missing, older):
    base = commit(repo, {"a": "a\nb\nc\n"})
    intermediate = commit(repo, {"new": "new\n"})
    head = commit(repo, {"a": "a\n"})
    row = turn(repo, base, head)
    (row[2] if missing == "before" else row[3]).pop("revision_" + missing)
    old_head = base if older == "base" else intermediate
    fallback = reach.superset(reach.Git(repo, lambda args, root: git(root, *args, check=False)),
                              {"number": 9, "base": {"sha": base}, "head": {"sha": old_head}})
    stale = reader(old_head, supersets=[{**fallback, "turn_reference": "build-1", "reason": "lost range",
                                         "items": account(fallback["items"])}])
    report = evaluate(repo, [row], [stale], base=base)
    assert report["state"] == "unmeasurable" and report["diagnostics"], report
    fallback = report["turns"][0]["superset"]
    current = reader(head, supersets=[{**fallback, "turn_reference": "build-1", "reason": "lost range",
                                      "items": account(fallback["items"])}])
    assert evaluate(repo, [row], [stale, current], base=base)["state"] == "clear"


@pytest.mark.parametrize("mutation", ["empty", "narrowed", "later-after", "later-before"])
def test_repair_872_recovery_preserves_recorded_endpoints_and_cannot_invent_empty_range(repo, mutation):
    base = commit(repo, {"a": "a\nb\nc\n"})
    middle = commit(repo, {"a": "a\nb\n"})
    after = commit(repo, {"a": "a\n"})
    head = commit(repo, {"new": "new\n"})
    row = turn(repo, base, after)
    recovered_before, recovered_after = base, after
    if mutation == "later-before":
        row[3].pop("revision_after")
        recovered_before, recovered_after = middle, after
    else:
        row[2].pop("revision_before")
        if mutation == "empty":
            recovered_before = after
        elif mutation == "narrowed":
            recovered_after = middle
        else:
            recovered_after = head
    measured = measure(repo, recovered_before, recovered_after)
    reading = reader(head, recovered=[{"dispatch_id": "build-1", "before": recovered_before,
                                       "after": recovered_after, "basis": "claimed native revisions"}],
                     turns=[{"dispatch_id": "build-1", "items": account(measured)}] if measured else [])
    report = evaluate(repo, [row], [reading], base=base)
    assert report["state"] == "unmeasurable" and report["diagnostics"], report


def test_repair_872_recovered_range_respects_neighboring_turn_order(repo):
    base = commit(repo, {"a": "a\nb\nc\n"})
    previous = commit(repo, {"new": "new\n"})
    after = commit(repo, {"a": "a\n"})
    rows = [turn(repo, base, previous, identity="build-0", order="2026-10-06T09:00:00Z",
                 returned="2026-10-06T09:30:00Z"), turn(repo, None, after)]
    reading = reader(after, recovered=[{"dispatch_id": "build-1", "before": base, "after": after,
                                        "basis": "claimed revisions overlapping the previous turn"}],
                     turns=[{"dispatch_id": "build-1", "items": account(measure(repo, base, after))}])
    report = evaluate(repo, rows, [reading], base=base)
    assert report["state"] == "unmeasurable" and report["diagnostics"], report
    correct = reader(after, recovered=[{"dispatch_id": "build-1", "before": previous, "after": after,
                                        "basis": "native launch and return revisions"}],
                     turns=[{"dispatch_id": "build-1", "items": account(measure(repo, previous, after))}])
    assert evaluate(repo, rows, [reading, correct], base=base)["state"] == "clear"


def test_repair_872_recovered_after_cannot_cross_the_next_launch(repo):
    base = commit(repo, {"a": "a\nb\nc\nd\n"})
    middle = commit(repo, {"a": "a\nb\nc\n"})
    head = commit(repo, {"a": "a\nb\n"})
    rows = [turn(repo, base, None), turn(repo, middle, head, identity="build-2",
            order="2026-10-06T11:10:00Z", returned="2026-10-06T11:30:00Z")]
    later_account = {"dispatch_id": "build-2", "items": account(measure(repo, middle, head))}
    reading = reader(head, recovered=[{"dispatch_id": "build-1", "before": base, "after": head,
                                       "basis": "claimed range crossing the next launch"}],
        turns=[{"dispatch_id": "build-1", "items": account(measure(repo, base, head))}, later_account])
    report = evaluate(repo, rows, [reading], base=base)
    assert report["state"] == "unmeasurable" and report["diagnostics"], report
    correct = reader(head, recovered=[{"dispatch_id": "build-1", "before": base, "after": middle,
                                       "basis": "retained launch and stop revisions"}],
        turns=[{"dispatch_id": "build-1", "items": account(measure(repo, base, middle))}, later_account])
    assert evaluate(repo, rows, [reading, correct], base=base)["state"] == "clear"


def test_repair_872_missing_return_superset_survives_a_proved_descendant_launch(repo):
    base = commit(repo, {"a": "a\nb\nc\n"})
    returned_head = commit(repo, {"a": "a\n"})
    row = turn(repo, base, None)
    entry = evaluate(repo, [row], head=returned_head, base=base)["turns"][0]
    reading = reader(returned_head, supersets=[{**entry["superset"], "turn_reference": "build-1",
        "reason": "return endpoint lost", "items": account(entry["superset"]["items"])}])
    descendant = commit(repo, {"new": "new\n"})
    later = turn(repo, returned_head, descendant, identity="build-2", order="2026-10-06T13:00:00Z",
                 returned="2026-10-06T14:00:00Z")
    assert evaluate(repo, [row, later], [reading], base=base)["state"] == "clear"
