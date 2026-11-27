"""A reread checks the fixes and judges nothing else again, and a reader's flag stands only on what the change wrote.

Design: lib/DESIGN.md#the-cold-reader
"""
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cold_reader  # noqa: E402
import work  # noqa: E402
from test_cold_reader import (BRANCH, Change, accept, commit, covered, git, mode, option,  # noqa: E402
                              recheck, run_stage)

EM = cold_reader.EM_DASH
DOCUMENT = "# Design\n\n## S\n\nIn force: [D1](../decisions/D1.md).\n"
STANDARD = "STANDARD TEXT"
DRIVER = Path(__file__).resolve().parent / "reading_fixture.py"


def flag(location, kind="what-comment", text="the line restates the code"):
    return f"{location} {EM} {kind} {EM} {text}"


def first(*flags, tell="yes"):
    """A first reading's account holding these flag lines."""
    return (f"## Sections\na.py:1-2 {EM} opens with its pointer; the reason is in design/x.md.\n\n"
            "## Flags\n" + ("\n".join(flags) or "none") + "\n\n"
            f"## Why this change was made\nCan tell: {tell}\nThe pointed section says why.\n\n"
            f"## Worth a look\na.py:1 {EM} a pointer done right.\n")


@pytest.fixture
def change(tmp_path, monkeypatch):
    return Change(tmp_path, monkeypatch)


def instructions(change, number=None):
    """The composed instructions of a reading, as the stage composes them from its record and the source."""
    record = change.record(number)
    path = cold_reader.reading_record(Path(record["tree_root"]), change.home)
    diff = path.with_suffix(".diff").read_text("utf-8") if record["diff"] == "inline" else None
    excerpts = cold_reader.reading_excerpts(change.root, record) if record["excerpts"] == "inline" else None
    return cold_reader.compose_prompt(record, STANDARD, diff, excerpts).decode("utf-8")


def assessment(change):
    fixture = change.state()
    work.validate_marker_claims(fixture)
    return work._cold_reading_plan(fixture, change.head)


def placed(change, number=None):
    """Each flag of a reading as the entrance places it: its line, whether it stands, and why not."""
    plan = assessment(change)
    reading = next(item for item in plan["readings"] if item["id"].endswith(f"reading-{number or change.readings}.run.json"))
    entries = plan["assessment"]["placements"][reading["id"]]
    return [(cold_reader.flag_line(item), entry["stands"], entry["reason"]) for item, entry in zip(reading["flags"], entries)]


def marked(text):
    return [int(match) for match in re.findall(r"^> +([0-9]+) \|", text, re.M)]


def shown(text):
    return [int(match) for match in re.findall(r"^[> ] +([0-9]+) \|", text, re.M)]


def base_file(change, name, text):
    """Put a file in the base and bring it into the change, as an older file the change will edit."""
    change.merge_base_change({name: text})


# The change's lines, and the lines gained since a reading.

TEN = "".join(f"line {number}\n" for number in range(1, 11))


def lines_of(tmp_path, before, after):
    root = tmp_path / "lines"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "core.autocrlf", "false")
    base = commit(root, {"f.py": before}, "base")
    head = commit(root, {"f.py": after}, "change")
    return cold_reader.change_lines(root, base, head)["f.py"]


def test_a_removal_counts_the_line_just_before_and_just_after_it_wherever_it_falls(tmp_path):
    # Line 1, line 5 and line 10 removed: the file now holds old lines 2-4 and 6-9.
    kept = "".join(f"line {number}\n" for number in (2, 3, 4, 6, 7, 8, 9))
    assert lines_of(tmp_path, TEN, kept) == [[1, 1], [3, 4], [7, 7]]


def test_an_added_line_counts_and_a_line_shown_only_as_context_does_not(tmp_path):
    edited = TEN.replace("line 5\n", "line five\n")
    assert lines_of(tmp_path, TEN, edited) == [[5, 5]]


@pytest.mark.cold_reading
def test_a_flag_on_an_added_line_stands_and_one_on_an_untouched_line_is_outside_the_change(change):
    base_file(change, "c.py", TEN)
    change.commit({"c.py": TEN.replace("line 5\n", "line five\n").replace("line 9\n", "")})
    # After the edit: line 5 is added, and removing line 9 makes lines 8 and 9 the removal's neighbours.
    account = first(flag("c.py:5"), flag("c.py:2", text="an old line"), flag("c.py:8", text="before the removal"),
                    flag("c.py:9", text="after the removal"), flag("c.py:7", text="two lines from the removal"),
                    flag("c.py:4", text="a context line"))
    change.read(account)
    assert [(stands, reason) for _line, stands, reason in placed(change)] == [
        (True, None), (False, "old-line"), (True, None), (True, None), (False, "old-line"), (False, "old-line")]
    change.post_open(account)
    standing = assessment(change)["assessment"]["flags"]
    assert sorted(item["lines"] for item in standing) == ["5", "8", "9"]


@pytest.mark.cold_reading
def test_a_flag_names_an_added_line_by_its_number_or_its_hunk_but_not_by_its_context_alone(change):
    base_file(change, "c.py", TEN)
    change.commit({"c.py": TEN.replace("line 5\n", "line five\n")})
    change.read(first(flag("c.py:5"), flag("c.py:2-8", text="the hunk"), flag("c.py:2-4,6-8", text="the context")))
    assert [stands for _line, stands, _reason in placed(change)] == [True, True, False]


@pytest.mark.cold_reading
def test_a_document_gap_on_an_untouched_pointed_document_stands_in_a_first_reading_only(change):
    change.reviewed(first(flag("design/x.md:5", "in-force-missing", "no decision for A"),
                          flag("design/x.md", "dead-end-pointer", "the section names nothing for B"),
                          flag("design/x.md:3", "what-comment", "an old heading")))
    assert [(stands, reason) for _line, stands, reason in placed(change)] == [
        (True, None), (True, None), (False, "old-line")]
    change.commit({"a.py": "# Design: design/x.md#s (decision D1)\nA = 1\n"})
    change.read(recheck([("F1", "answered"), ("F2", "answered")],
                        flags="\n".join((flag("design/x.md:5", "in-force-missing", "still no decision for A"),
                                         flag("a.py:1", "dead-end-pointer", "the pointer names a decision the "
                                              "section does not list")))))
    assert [(stands, reason) for _line, stands, reason in placed(change)] == [(False, "not-reached"), (True, None)]


# What a reread is ordered and shown.

LONG = "".join(f"VALUE_{number:03d} = {number}\n" for number in range(1, 301))


@pytest.mark.cold_reading
def test_a_fix_to_three_lines_of_a_long_file_orders_a_check_of_those_lines_and_the_standing_flags_alone(change):
    change.commit({"long.py": "# Design: design/x.md#s\n" + LONG})
    account = first(flag("long.py:21", text="VALUE_020 restates its number"),
                    flag("long.py:251", "missing-reason", "nothing says why 250 is kept"),
                    flag("a.py:2", "history", "a name that remembers a past run"))
    change.read(account)
    change.review(change.post_open(account, "Holder's private note.\n\n" + accept("a.py:2", "fine here", "history")))
    fixed = LONG.replace("VALUE_150 = 150\n", "VALUE_150 = 1500\n").replace(
        "VALUE_151 = 151\n", "VALUE_151 = 1510\n").replace("VALUE_152 = 152\n", "VALUE_152 = 1520\n")
    change.commit({"long.py": "# Design: design/x.md#s\n" + fixed})
    decision = change.decide()
    assert (covered(decision), mode(decision)) == (["long.py"], "fix-check")
    change.read(recheck([("F1", "answered"), ("F2", "answered")]))
    text = instructions(change)
    assert marked(text) == [151, 152, 153] and shown(text) == list(range(148, 157))
    rows = re.findall(r"^[> ] +[0-9]+ \| (.*)$", text, re.M)
    assert [row.split(" = ")[0] for row in rows] == [f"VALUE_{number:03d}" for number in range(147, 156)]
    assert "F1. `long.py:21`" in text and "F2. `long.py:251`" in text and "F3." not in text
    for earlier in ("opens with its pointer", "a pointer done right", "a name that remembers", "fine here",
                    "Holder's private note", "The pointed section says why"):
        assert earlier not in text
    assert {"a.py", "b.py", "long.py"} <= set(change.record()["files"])


@pytest.mark.cold_reading
@pytest.mark.parametrize("pointing", [4, 8])
def test_a_fix_to_a_document_many_files_point_into_checks_its_fixed_lines_alone(change, pointing):
    files = {f"p{number}.py": f"# Design: design/x.md#s\nP = {number}\n" for number in range(pointing)}
    change.commit({**files, "design/x.md": DOCUMENT + "Why P: one module per period.\n"})
    account = first(flag("design/x.md:6", "missing-reason", "why one module per period is not said"),
                    flag("p0.py:2", "changeable-number", "P's value has no reason"))
    change.reviewed(account)
    change.commit({"design/x.md": DOCUMENT + "Why P: one module per period.\nPeriods close monthly.\n"})
    decision = change.decide()
    assert (covered(decision), mode(decision)) == (["design/x.md"], "fix-check")
    change.read(recheck([("F1", "answered"), ("F2", "answered")]))
    record = change.record()
    assert record["lines"]["design/x.md"]["judged"] == [[7, 7]] and marked(instructions(change)) == [7]
    assert [item["path"] for item in record["earlier_flags"]] == ["design/x.md", "p0.py"]


@pytest.mark.cold_reading
def test_a_merge_from_the_base_that_alters_a_pointed_document_orders_no_reading(change):
    change.reviewed(first())
    change.merge_base_change({"design/x.md": DOCUMENT + "A base edit.\n"})
    assert change.decide().reason == "cold-reading-close"


@pytest.mark.cold_reading
def test_lines_a_merge_from_the_base_brings_are_never_marked_and_a_flag_on_one_is_outside(change):
    base_file(change, "c.py", "C1\nC2\nC3\n")
    change.commit({"c.py": "C1\nC2 changed\nC3\n"})
    change.reviewed(first())
    change.merge_base_change({"c.py": "C1\nC2\nC3\nC4\nC5\n"})
    change.commit({"c.py": "NEW1\nNEW2\nC1\nC2 changed\nC3\nC4\nC5\n"})
    decision = change.decide()
    assert (covered(decision), mode(decision)) == (["c.py"], "fix-check")
    change.read(recheck(flags="\n".join((flag("c.py:1", text="a new line"), flag("c.py:6", text="a merged line")))))
    assert marked(instructions(change)) == [1, 2]
    assert [(stands, reason) for _line, stands, reason in placed(change)] == [(True, None), (False, "old-line")]


@pytest.mark.cold_reading
def test_a_line_that_becomes_the_changes_by_keeping_its_side_in_a_merge_is_read(change):
    base_file(change, "c.py", "C1\nC2\nC3\nC4\nC5\n")
    change.commit({"c.py": "C1\nC2 changed\nC3\nC4\nC5\n"})
    change.reviewed(first())
    blob = git(change.root, "rev-parse", "HEAD:c.py")
    kept = change.head
    git(change.root, "checkout", "-q", "main")
    change.base = commit(change.root, {"c.py": "C1\nC2\nC3\nC4 base\nC5\n"}, "base edits line 4")
    git(change.root, "checkout", "-q", "feature")
    git(change.root, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "merge", "-q", "--no-commit", "main")
    git(change.root, "checkout", kept, "--", "c.py")
    git(change.root, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-q", "-m", "keep the change's side")
    change.head = git(change.root, "rev-parse", "HEAD")
    assert git(change.root, "rev-parse", "HEAD:c.py") == blob
    decision = change.decide()
    assert (decision.stage, covered(decision), mode(decision)) == ("cold-reader", ["c.py"], "fix-check")
    change.read(recheck())
    assert marked(instructions(change)) == [4]


# What clears a flag, and what a reread's verdicts do.

@pytest.mark.cold_reading
def test_a_new_flag_on_an_already_read_line_is_outside_the_change_and_routes_nothing(change):
    change.reviewed(first(flag("a.py:1")))
    change.commit({"a.py": "# Design: design/x.md#s\nA = 1\nA2 = 2\n"})
    gained = flag("a.py:3", "changeable-number", "2 has no reason")
    old = flag("a.py:2", "changeable-number", "1 has no reason")
    change.read(recheck([("F1", "answered")], flags="\n".join((gained, old))))
    assert [(stands, reason) for _line, stands, reason in placed(change)] == [(True, None), (False, "old-line")]
    change.post_open(recheck([("F1", "answered")], flags="\n".join((gained, old))))
    fixture = change.state()
    work.validate_marker_claims(fixture)
    row = work._cold_reading_measures(fixture)["readings"][-1]
    assert row["routed"] == [gained] and row["outside"] == [{"flag": old, "reason": "old-line"}]
    assert [item["lines"] for item in assessment(change)["assessment"]["flags"]] == ["3"]


@pytest.mark.cold_reading
def test_a_reading_whose_only_new_flag_is_outside_the_change_closes_without_a_builder_turn(change):
    change.reviewed(first(flag("a.py:1")))
    change.commit({"a.py": "# Design: design/x.md#s\nA = 1\nA2 = 2\n"})
    returned = recheck([("F1", "answered")], flags=flag("a.py:2", "changeable-number", "1 has no reason"))
    change.read(returned)
    change.post_open(returned)
    assert change.decide().reason == "cold-reading-close"


@pytest.mark.cold_reading
@pytest.mark.parametrize("why", [False, True])
def test_an_accepted_flag_reaches_no_later_reading_and_its_restatement_is_outside(change, why):
    ordinary = flag("a.py:1", "what-comment", "the pointer line restates the file")
    document = flag("design/x.md:5", "in-force-missing", "D1 does not say why A is one")
    account = first(ordinary, document, tell="no" if why else "yes")
    change.read(account)
    change.review(change.post_open(account, accept("a.py:1", "a pointer is meant to") + "\n"
                                   + accept("design/x.md:5", "D1 is the base's", "in-force-missing")))
    change.commit({"a.py": "# Design: design/x.md#s\nA = 2\n"})
    assert mode(change.decide()) == ("why-check" if why else "fix-check")
    change.read(recheck(flags="\n".join((ordinary, document)), tell="yes" if why else None))
    text = instructions(change)
    assert change.record()["earlier_flags"] == []
    assert "restates the file" not in text and "D1 does not say" not in text
    assert [(stands, reason) for _line, stands, reason in placed(change)] == [
        (False, "old-line"), (False, "not-reached")]


@pytest.mark.cold_reading
def test_answered_clears_an_earlier_flag_and_not_answered_stands_as_the_rereads_own_to_accept(change):
    change.reviewed(first(flag("a.py:1"), flag("b.py:2", "changeable-number", "B's value has no reason")))
    change.commit({"a.py": "# Design: design/x.md#s\n# A is one so the count starts at the first item.\nA = 1\n"})
    returned = recheck([("F1", "answered"), ("F2", "not-answered")])
    change.read(returned)
    change.post_open(returned, accept("b.py:2", "B is the product's default", "changeable-number"))
    assert change.decide().reason == "cold-reading-close"
    fixture = change.state()
    work.validate_marker_claims(fixture)
    row = work._cold_reading_measures(fixture)["readings"][-1]
    assert [(item["verdict"], item["why"]) for item in row["checked"]] == [
        ("answered", "as the code now stands"), ("not-answered", "as the code now stands")]
    assert row["accepted"] == [{"flag": flag("b.py:2", "changeable-number", "B's value has no reason"),
                                "reason": "B is the product's default"}]


@pytest.mark.cold_reading
def test_a_fix_check_is_ordered_after_every_fix_with_no_count_of_rounds(change):
    change.reviewed(first(flag("a.py:2", "changeable-number", "1 has no reason")))
    for round_number in range(2, 6):
        change.commit({"a.py": "# Design: design/x.md#s\n" + "".join(f"A{n} = {n}\n" for n in range(round_number))})
        decision = change.decide()
        assert (decision.stage, mode(decision)) == ("cold-reader", "fix-check"), round_number
        earlier = [(item["id"], "answered") for item in change.order()["earlier_flags"]]
        change.reviewed(recheck(earlier, flags=flag(f"a.py:{round_number + 1}", "changeable-number", "no reason")))


@pytest.mark.cold_reading
def test_a_standing_flag_with_no_commit_since_orders_a_fix_check_of_no_path_that_still_launches(
        change, monkeypatch, capsys):
    change.reviewed(first(flag("a.py:1")))
    decision = change.decide()
    assert (covered(decision), mode(decision)) == ([], "fix-check")
    code, command, _decision, report = run_stage(change, monkeypatch, capsys, recheck([("F1", "answered")]))
    assert code == 0 and (report["mode"], report["covered"], report["form"]) == ("fix-check", [], "pass")
    prompt = Path(option(command, "--dispatch")).read_text("utf-8")
    assert "no line is marked: judge only the earlier flags" in prompt and marked(prompt) == []
    assert Path(option(command, "--root")).is_dir()


@pytest.mark.cold_reading
def test_a_why_check_reads_the_whole_change_but_its_flags_stay_on_the_lines_gained_since(change):
    change.reviewed(first(tell="no"))
    change.commit({"a.py": "# Design: design/x.md#s\nA = 2\n"})
    decision = change.decide()
    assert (decision.reason, covered(decision), mode(decision)) == (
        "cold-reading-why-owed", ["a.py", "b.py"], "why-check")
    returned = recheck(tell="yes", flags="\n".join((
        flag("a.py:1", "what-comment", "an already-read line"),
        flag("design/x.md:5", "dead-end-pointer", "a gap in the pointed document"),
        flag("a.py:2", "changeable-number", "2 has no reason"))))
    change.read(returned)
    assert [(stands, reason) for _line, stands, reason in placed(change)] == [
        (False, "old-line"), (False, "not-reached"), (True, None)]
    assert "## The diff of the whole change" in instructions(change)
    assert assessment(change)["assessment"]["standing_no"] is False


@pytest.mark.cold_reading
def test_a_fix_check_never_clears_a_cannot_tell(change):
    change.reviewed(first(tell="no"))
    change.commit({"a.py": "# Design: design/x.md#s\nA = 2\n"})
    change.reviewed(recheck(), order={"mode": "fix-check", "covered": ["a.py"], "judged": {"a.py": [[2, 2]]}})
    assert change.decide().reason == "cold-reading-why-owed"


@pytest.mark.cold_reading
def test_the_release_report_lists_each_rereads_verdicts_new_flags_and_the_flags_outside_the_change(change):
    change.reviewed(first(flag("a.py:1"), flag("b.py:5", text="past the file's end")))
    change.commit({"a.py": "# Design: design/x.md#s\nA = 1\nA2 = 2\n"})
    new = flag("a.py:3", "changeable-number", "2 has no reason")
    change.reviewed(recheck([("F1", "answered")], flags=new))
    change.commit({"a.py": "# Design: design/x.md#s\nA = 1\n# Two, the second shelf.\nA2 = 2\n"})
    change.reviewed(recheck([("F1", "answered")], flags=flag("a.py:2", "history", "an old line")))
    fixture = change.state()
    work.validate_marker_claims(fixture)
    rows = work._cold_reading_measures(fixture)["readings"]
    assert [row["mode"] for row in rows] == ["first", "fix-check", "fix-check"]
    assert rows[0]["outside"] == [{"flag": flag("b.py:5", text="past the file's end"), "reason": "old-line"}]
    assert rows[1]["checked"] == [{"flag": f"F1. `a.py:1` {EM} what-comment {EM} the line restates the code",
                                   "verdict": "answered", "why": "as the code now stands"}]
    assert rows[1]["flags"] == [new] and rows[2]["flags"] == []
    assert rows[2]["outside"] == [{"flag": flag("a.py:2", "history", "an old line"), "reason": "old-line"}]
    for row in rows:
        listed = {item["flag"] for item in row["outside"]}
        assert not listed & (set(row["flags"]) | set(row["routed"]) | {item["flag"] for item in row["accepted"]})


@pytest.mark.cold_reading
def test_an_acceptance_of_a_flag_outside_the_change_is_harmless_and_one_naming_no_flag_still_fails(change):
    account = first(flag("design/x.md:3", "what-comment", "an old heading"))
    change.read(account)
    change.post_open(account, accept("design/x.md:3", "old text"))
    decision = change.decide()
    assert (decision.reason, decision.invalid) == ("cold-reading-close", [])
    change.post_open(account, accept("design/x.md:4", "names nothing"))
    assert change.decide().invalid


# What each reading is told, and that it is what the entrance holds.

@pytest.mark.cold_reading
def test_a_rereads_rule_on_what_may_be_flagged_is_the_rule_the_entrance_holds(change):
    base_file(change, "c.py", TEN)
    change.commit({"c.py": TEN.replace("line 5\n", "line five\n")})
    change.read(first())
    record = change.record()
    diff = cold_reader.reading_record(Path(record["tree_root"]), change.home).with_suffix(".diff").read_text("utf-8")
    added, number, path = {}, 0, None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[len("+++ b/"):]
        elif line.startswith("@@"):
            number = int(re.match(r"@@ -[0-9,]+ \+([0-9]+)", line).group(1))
        elif line.startswith("+"):
            added.setdefault(path, []).append(number)
            number += 1
        elif line.startswith(" "):
            number += 1
    for name, numbers in added.items():
        assert cold_reader.numbers_of(record["lines"][name]["judged"]) == set(numbers), name
    change.post_open(first())
    change.commit({"c.py": TEN.replace("line 5\n", "line five\n").replace("line 7\n", "line seven\n")})
    change.read(recheck())
    text = instructions(change)
    assert "Only a marked line may be flagged, whatever the flag's kind." in text
    assert set(marked(text)) == cold_reader.numbers_of(change.record()["lines"]["c.py"]["judged"]) == {7}


# Version 1 records, written before readings had modes.

def as_version_one(change, number=None):
    """Rewrite a reading's record as a version 1 record: no mode, no sealed lines."""
    path = cold_reader.reading_record(change.trees / f"reading-{number or change.readings}", change.home)
    value = json.loads(path.read_bytes())
    for key in ("mode", "lines", "excerpts", "since", "earlier_flags", "gained_unknown", "metadata_sha256"):
        value.pop(key, None)
    value["schema_version"] = 1
    value["metadata_sha256"] = cold_reader._digest(value)
    path.write_bytes(json.dumps(value, indent=2, sort_keys=True).encode("ascii") + b"\n")
    return value


@pytest.mark.cold_reading
@pytest.mark.parametrize(("account", "expected"), [
    (first(), ("cold-reading-close", None)),
    (first(flag("a.py:1")), ("cold-reading-flag-reread", "cold-reader")),
    (first(tell="no"), ("cold-reading-why-owed", "cold-reader")),
])
def test_a_store_of_version_one_readings_gives_the_decision_it_gave_before(change, account, expected):
    change.reviewed(account)
    as_version_one(change)
    decision = change.decide()
    assert decision.reason == expected[0] and (expected[1] is None or decision.stage == expected[1])


@pytest.mark.cold_reading
def test_a_change_in_flight_whose_latest_reading_is_version_one_is_ordered_a_fix_check(change):
    base_file(change, "c.py", "C1\nC2\nC3\nC4\nC5\n")
    change.commit({"c.py": "C1\nC2 changed\nC3\nC4\nC5\n"})
    change.reviewed(first(flag("c.py:2", text="the written line"), flag("c.py:4", text="an old line"),
                          flag("c.py", "missing-reason", "no lines named")))
    as_version_one(change)
    standing = assessment(change)["assessment"]["flags"]
    assert [(item["lines"], item["kind"]) for item in standing] == [("2", "what-comment"), (None, "missing-reason")]
    change.commit({"c.py": "C1\nC2 changed\nC3 too\nC4\nC5\n"})
    order = change.order()
    assert order["mode"] == "fix-check" and order["judged"] == {"c.py": [[3, 3]]}
    assert [item["lines"] for item in order["earlier_flags"]] == ["2", None]


@pytest.mark.cold_reading
def test_a_version_one_reading_whose_head_is_gone_keeps_its_flags_and_has_its_files_read_again(change):
    change.reviewed(first(flag("a.py:9", text="a line the change never wrote")))
    path = cold_reader.reading_record(change.trees / "reading-1", change.home)
    value = as_version_one(change)
    value.pop("metadata_sha256")
    value["head"] = "f" * 40
    value["metadata_sha256"] = cold_reader._digest(value)
    path.write_bytes(json.dumps(value, indent=2, sort_keys=True).encode("ascii") + b"\n")
    request = change.store / "reading-1.request.json"
    request.write_text(json.dumps({**json.loads(request.read_text("utf-8")), "lineage_branch": BRANCH,
                                   "lineage_pull_request": change.state().pr["number"]}), encoding="utf-8")
    plan = assessment(change)["assessment"]
    assert [item["lines"] for item in plan["flags"]] == ["9"]
    change.commit({"a.py": "# Design: design/x.md#s\nA = 2\n"})
    order = change.order()
    assert order["judged"] == {"a.py": [[1, 2]]} and order["gained_unknown"] == ["a.py"]


# A builder's reread is recomposed from its sealed record.

@pytest.mark.cold_reading
@pytest.mark.parametrize("why", [False, True])
def test_a_builders_reread_is_recomposed_from_its_record_and_the_source(change, monkeypatch, capsys, why):
    change.reviewed(first(flag("a.py:1"), tell="no" if why else "yes"))
    change.commit({"a.py": "# Design: design/x.md#s\nA = 2\n"})
    returned = recheck([("F1", "answered")], tell="yes" if why else None)
    _code, command, _decision, report = run_stage(change, monkeypatch, capsys, returned)
    assert report["mode"] == ("why-check" if why else "fix-check")
    root = Path(option(command, "--root"))
    launched = Path(option(command, "--dispatch")).read_bytes()
    state = SimpleNamespace(holder_root=change.root)
    composed, head, problem = work._recompose_reading(state, root, change.home)
    assert (problem, head) == ("", change.head) and composed == launched
    record = cold_reader.reading_record(root, change.home)
    for suffix in (".diff", ".excerpts"):
        record.with_suffix(suffix).write_text("> 1 | all is well\n", encoding="utf-8")
    assert work._recompose_reading(state, root, change.home)[0] == launched


# The use session's driver.

def driver(*words, cwd=None):
    return subprocess.run([sys.executable, "-B", str(DRIVER), *map(str, words)], capture_output=True,
                          stdin=subprocess.DEVNULL, timeout=300, cwd=cwd, encoding="utf-8")


def tree_status():
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=DRIVER.parents[2],
                          capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout


def printed(result):
    found = dict(line.split(": ", 1) for line in result.stdout.splitlines() if ": " in line)
    return Path(found["reading tree"]), Path(found["instructions"])


def test_the_driver_names_its_situations():
    assert driver("--list").stdout.split() == ["first", "reread", "shared-document"]


@pytest.mark.parametrize("situation", ["first", "reread", "shared-document"])
def test_each_situation_prints_its_reading_tree_and_instructions_and_writes_nothing_in_the_tree(situation, tmp_path):
    before = tree_status()
    result = driver(situation, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    tree, written = printed(result)
    assert tree.is_dir() and (tree / ".git").exists() and written.is_file()
    assert not tree.is_relative_to(DRIVER.parents[2]) and tree_status() == before


def test_the_drivers_isolation_refuses_every_socket(tmp_path):
    probe = ("import sys, socket; sys.path.insert(0, sys.argv[1]); import reading_fixture as f; "
             "f._isolate(__import__('pathlib').Path(sys.argv[2]))\n"
             "try:\n    socket.create_connection(('example.com', 443))\nexcept OSError as e:\n    print('refused', e)")
    (tmp_path / "probe").mkdir()
    result = subprocess.run([sys.executable, "-B", "-c", probe, str(DRIVER.parent), str(tmp_path / "probe")],
                            capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
    assert result.stdout.startswith("refused"), result.stderr
    # The probe ran in its own process, so this one's sockets are untouched.
    assert socket.create_connection.__module__ == "socket"


def judged(situation, account, tmp_path):
    assert driver(situation, cwd=tmp_path).returncode == 0
    path = tmp_path / f"{situation}-account.md"
    path.write_text(account, encoding="utf-8")
    return driver("judge", situation, path, cwd=tmp_path)


def test_judge_prints_what_the_entrance_makes_of_a_first_readings_account(tmp_path):
    account = (f"## Sections\nshop/pricing.py:1-11 {EM} prices a basket.\n\n## Flags\n"
               f"shop/pricing.py:6 {EM} changeable-number {EM} 0.17 has no reason\n"
               f"shop/inventory.py:10 {EM} what-comment {EM} the comment restates the line\n\n"
               f"## Why this change was made\nCan tell: yes\nThe docstrings say why.\n\n"
               f"## Worth a look\nshop/inventory.py:19 {EM} a reason.\n")
    result = judged("first", account, tmp_path)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    for part in ("form check: passes", "earlier flags: none", "flags that stand:",
                 f"shop/pricing.py:6 {EM} changeable-number", "(old-line)", "next: "):
        assert part in out, out
    assert out.index("shop/inventory.py:10") > out.index("flags outside the change")


def test_the_reread_situations_later_commit_settles_one_point_and_leaves_the_other(tmp_path):
    account = (f"## Earlier flags\nF1 {EM} not-answered {EM} the number still has no reason\n"
               f"F2 {EM} answered {EM} the comment gives the terms\n\n## Flags\nnone\n")
    result = judged("reread", account, tmp_path)
    assert result.returncode == 0, result.stderr
    assert "verdict: not-answered" in result.stdout and "verdict: answered" in result.stdout
    assert "(carried: not answered)" in result.stdout
    product = Path(printed(driver("reread", cwd=tmp_path))[0]).parents[1] / "product"
    changed = subprocess.run(["git", "diff", "HEAD~1", "HEAD"], cwd=product, capture_output=True, text=True,
                             stdin=subprocess.DEVNULL).stdout
    # The point of the second flag, the rounding, is answered in the code; the first's number is left as it was.
    assert "+    # Rounded down" in changed and "LOYALTY_DISCOUNT = 0.17" not in "".join(
        line for line in changed.splitlines() if line.startswith(("+", "-")))


def test_judge_refuses_an_account_in_the_wrong_form_and_says_why(tmp_path):
    result = judged("shared-document", "## Flags\nnone\n", tmp_path)
    assert result.returncode == 1 and "form check: refused" in result.stdout
    assert "missing heading ## Earlier flags" in result.stdout


def test_a_reread_report_read_without_its_record_counts_each_new_flag_and_each_not_answered_one():
    import readiness
    returned = recheck([("F1", "answered"), ("F2", "not-answered")], flags=flag("a.py:3", "history", "a past run"))
    assert readiness.report_findings("cold-reader", returned) == [
        {"finding": "F1", "text": flag("a.py:3", "history", "a past run")},
        {"finding": "F2", "text": f"F2 {EM} not-answered"}]
    assert readiness.report_findings("cold-reader", recheck([("F1", "answered")], tell="no")) == [
        {"finding": "F1", "text": "Can tell: no"}]


def _bundle(store, name, request, run=None, files=None):
    output = store / name / "result.md"
    output.parent.mkdir(parents=True)
    work.records.write_json(work.records.sidecar(output, ".request.json"), {
        "schema_version": 2, "work": "o/r#5", "launched_at": "2026-11-22T00:00:00+00:00", **request})
    work.records.write_json(work.records.sidecar(output, ".run.json"),
                            {"schema_version": 2, "dispatch_id": request["dispatch_id"], **(run or {})})
    for suffix, content in (files or {}).items():
        work.records.sidecar(output, suffix).write_bytes(content)


@pytest.mark.cold_reading
@pytest.mark.parametrize("reread", [False, True])
def test_a_builders_record_owes_no_entry_for_a_flag_outside_the_change(change, monkeypatch, reread):
    import hashlib
    import readiness
    base_file(change, "c.py", TEN)
    change.commit({"c.py": TEN.replace("line 5\n", "line five\n")})
    written, old = flag("c.py:5", text="the written line"), flag("c.py:2", text="an old line")
    returned = first(written, old, tell="no")
    if reread:
        change.reviewed(first(flag("c.py:5", "missing-reason", "five has no reason")))
        change.commit({"c.py": TEN.replace("line 5\n", "line five\n").replace("line 7\n", "line seven\n")})
        written, old = flag("c.py:7", text="the written line"), flag("c.py:5", text="an already-read line")
        returned = recheck([("F1", "not-answered")], flags="\n".join((written, old)))
    change.read(returned)
    root = Path(change.record()["tree_root"])
    recompose = work._recompose_reading
    recomposed = recompose(SimpleNamespace(holder_root=change.root), root, change.home)[0]
    composed = b"the composed reading"
    monkeypatch.setattr(work, "_recompose_reading", lambda state, tree, home: (composed, change.head, ""))
    monkeypatch.setattr(work, "_records_home", lambda _state: change.home)
    store = change.tmp / "builder-store"
    _bundle(store, "stretch", {"dispatch_id": "a" * 32, "stage": "stretch"})
    _bundle(store, "reading", {"dispatch_id": "c" * 32, "stage": "cold-reader", "root": str(root),
                               "launched_by": {"dispatch_id": "a" * 32}},
            {"outcome": "success", "staffing_status": "degraded"},
            {".dispatch.bin": composed, ".source.bin": returned.encode("utf-8")})
    body = (f"<!-- tradecraft:check-report:v1 stage=cold-reader dispatch={'c' * 32} head={change.head} "
            f"dispatch_sha256={hashlib.sha256(composed).hexdigest()} tree=held staffing_status=degraded "
            "outcome=success -->\n\n" + returned)
    state = SimpleNamespace(repo="o/r", issue_number=5, record_root=store, holder_root=change.root,
                            config=work.WorkConfig(marker_producers=frozenset({"producer"})),
                            issue_comments=[{"id": 77, "body": body, "user": {"login": "producer"}}])
    report = work.builder_checks(state)["check_reports"][0]
    assert report["counts"] is True, report["invalid"]
    standing = [written, "c.py:5 " + EM + " missing-reason " + EM + " five has no reason"] if reread else [
        written, "Can tell: no"]
    assert report["findings"] == [f"F{number}" for number in range(1, len(standing) + 1)]
    assert [item["text"] for item in readiness.report_findings(
        "cold-reader", returned, change.record(), change.root)] == standing
    assert report["outside"] == [{"flag": old, "reason": "old-line"}]
    record = {"findings": [{"report": 77, "finding": finding, "disposition": "declined", "reason": "judged"}
                           for finding in report["findings"]]}
    reconciled = readiness.reconcile(record, [{"report": 77, "named": True, "findings": report["findings"]}],
                                     lambda commit: True)
    assert reconciled["unreconciled"] == []
    # A record rewritten in the store to judge no line can't move a flag outside the change: its lines are
    # recomputed from the source first, and where they differ every listed flag stays a finding.
    path = cold_reader.reading_record(root, change.home)
    value = json.loads(path.read_bytes())
    value.pop("metadata_sha256")
    for entry in value["lines"].values():
        entry["judged"] = []
    value["metadata_sha256"] = cold_reader._digest(value)
    path.write_bytes(json.dumps(value, indent=2, sort_keys=True).encode("ascii") + b"\n")
    if reread:
        # A reread's judged lines are the excerpts its dispatch carries, so the rewrite stops it recomposing.
        assert recompose(SimpleNamespace(holder_root=change.root), root, change.home)[0] != recomposed
    else:
        rewritten = work.builder_checks(state)["check_reports"][0]
        assert "outside" not in rewritten and len(rewritten["findings"]) > len(report["findings"])
