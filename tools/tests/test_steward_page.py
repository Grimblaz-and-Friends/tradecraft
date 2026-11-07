# Design: tools/DESIGN.md#the-standing-page
"""Tests for tools/steward_page.py: the standing page in parts, edited entry by entry (#891).

Every GitHub call goes through a recording fake holding one page issue, its
comments, the archive issue and the state of each referenced issue, so each
test states what GitHub held and reads back every write the tool sent. Every
test passes its own state directory; the probe-refusal test is the only one
that resolves the default, and it asserts the refusal. Criterion ids (A1 ...)
are the settled artifact's on #891.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import steward_page as sp  # noqa: E402
import steward_watch as sw  # noqa: E402

PAGE = 683
REPO = sw.LAB_REPO
NOW = datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc)
OLD_BODY = "## The read\n\n- old read\n\n## Rulings a holder applies\n\n- an old ruling\n"


def issue(state="OPEN", reason=None):
    return {"__typename": "Issue", "state": state, "stateReason": reason}


def pull(state="OPEN", merged=False):
    return {"__typename": "PullRequest", "state": state, "merged": merged}


class FakeGitHub:
    """An in-memory GitHub the gh runner reads and writes, recording every call."""

    def __init__(self, body: str = OLD_BODY):
        self.issues = {PAGE: {"number": PAGE, "body": body, "state": "open"}}
        self.comments: dict[int, list[dict]] = {PAGE: []}
        self.states: dict[str, dict] = {}
        self.calls: list[tuple] = []
        self.hooks: list[tuple] = []
        self.store = lambda endpoint, body: body
        self.next_comment = 7_000_000_000
        self.next_issue = 2000

    def __call__(self, args, input_text=None, timeout=60):
        method = args[args.index("--method") + 1]
        endpoint = [a for a in args if a.startswith("repos/") or a == "graphql"][0]
        payload = json.loads(input_text) if input_text else None
        self.calls.append((method, endpoint, payload))
        for hook in list(self.hooks):
            if hook[0](method, endpoint):
                self.hooks.remove(hook)
                hook[1]()
        if endpoint == "graphql":
            return self.graphql(payload["query"])
        tail = endpoint.split("/")[3:]
        if tail == ["issues"] and method == "POST":
            self.next_issue += 1
            made = {"number": self.next_issue, "body": payload["body"], "state": "open",
                    "html_url": f"https://github.com/{REPO}/issues/{self.next_issue}"}
            self.issues[self.next_issue] = made
            self.comments[self.next_issue] = []
            return json.dumps(made)
        if tail[0] == "issues" and len(tail) == 2:
            target = self.issues[int(tail[1])]
            if method == "PATCH":
                if "body" in payload:
                    target["body"] = self.store(endpoint, payload["body"])
                target.update({k: v for k, v in payload.items() if k != "body"})
            return json.dumps(target)
        if tail[0] == "issues" and tail[2] == "comments" and len(tail) == 3:
            number = int(tail[1])
            if method == "GET":
                items = self.comments[number]
                half = len(items) // 2
                return json.dumps(items[:half]) + "\n" + json.dumps(items[half:])
            return json.dumps(self.add_comment(number, self.store(endpoint, payload["body"])))
        if tail[:2] == ["issues", "comments"]:
            found = self.comment(int(tail[2]))
            if method == "PATCH":
                found["body"] = self.store(endpoint, payload["body"])
            return json.dumps(found)
        raise AssertionError(f"unexpected call {args}")

    def add_comment(self, number: int, body: str, login: str = "Grimblaz") -> dict:
        self.next_comment += 1
        made = {"id": self.next_comment, "body": body, "user": {"login": login},
                "created_at": "2026-11-07T11:00:00Z",
                "html_url": f"https://github.com/{REPO}/issues/{number}#issuecomment-{self.next_comment}"}
        self.comments[number].append(made)
        return made

    def comment(self, cid: int) -> dict:
        for items in self.comments.values():
            for item in items:
                if item["id"] == cid:
                    return item
        raise AssertionError(f"no comment {cid}")

    def graphql(self, query: str) -> str:
        data = {}
        for alias, repo, number in re.findall(
                r'(r\d+): repository\(owner: "[^"]+", name: "([^"]+)"\) '
                r"\{ issueOrPullRequest\(number: (\d+)\)", query):
            node = self.states.get(f"{repo}#{number}")
            if node is None:
                raise sw.WatchError("gh api graphql exited 1: Could not resolve to an issue")
            data[alias] = {"issueOrPullRequest": node}
        return json.dumps({"data": data})

    def github(self):
        return sw.GitHub(runner=self)

    def writes(self) -> list[tuple]:
        return [c for c in self.calls if c[0] in ("POST", "PATCH") and c[1] != "graphql"]

    def part_comment(self, name: str) -> dict:
        found = [c for c in self.comments[PAGE]
                 if f"<!-- lab:steward-part:v1 part={name} -->" in c["body"]]
        assert len(found) == 1
        return found[0]

    def part_text(self, name: str) -> str:
        return self.issues[PAGE]["body"] if name == "body" else self.part_comment(name)["body"]

    def set_part(self, name: str, text: str) -> None:
        if name == "body":
            self.issues[PAGE]["body"] = text
        else:
            self.part_comment(name)["body"] = text

    def on_get(self, endpoint_suffix: str, fn) -> None:
        self.hooks.append((lambda m, e: m == "GET" and e.endswith(endpoint_suffix), fn))


class Steward:
    """Runs the tool's commands as the Steward would, against the fake."""

    def __init__(self, lab: FakeGitHub, tmp: Path):
        self.lab = lab
        self.tmp = tmp
        self.state = tmp / "state"
        self.count = 0

    def file(self, text: str) -> str:
        self.count += 1
        path = self.tmp / f"text-{self.count}.txt"
        path.write_bytes(text.encode("utf-8"))
        return str(path)

    def json_file(self, value) -> str:
        return self.file(json.dumps(value))

    def __call__(self, *argv):
        args = sp.build_parser().parse_args([*map(str, argv), "--state-dir", str(self.state)])
        return sp.run(args, github=self.lab.github(), now=NOW)

    def refused(self, *argv, match: str | None = None):
        before = list(self.lab.writes())
        with pytest.raises((sp.PageError, sw.WatchError)) as info:
            self(*argv)
        assert self.lab.writes() == before, "a refused command wrote"
        if match:
            assert match in str(info.value), str(info.value)
        return info.value

    def entries(self, name: str) -> list[dict]:
        return self("show", name)["entries"]

    def ids(self) -> set[str]:
        return {e["id"] for n in sp.PART_ORDER for e in self.entries(n)}

    def accept(self, name: str) -> None:
        self("accept", name, "--sha", self("show", name)["sha256"])

    def add(self, kind: str, text: str, issue: str = "none", *extra) -> str:
        return self("add", "--kind", kind, "--issue", issue, "--text-file", self.file(text),
                    *extra)["added"]


def build(tmp: Path, parts=sp.COMMENT_PARTS) -> Steward:
    """The move, run on a fake page: archive, the part comments, then the body."""
    lab = FakeGitHub()
    st = Steward(lab, tmp)
    archive = st("init-archive", "--title", "Standing page archive")["archive"]
    st("archive", "--move", "--archive", archive, "--file", st.file(OLD_BODY))
    for name in parts:
        st("create-part", name, "--text-file", st.file(f"## {sp.TITLES[name]}"))
    st.accept("body")
    st("body", "--text-file", st.file("How this page is used: read this body at pickup."),
       "--archive", archive)
    st.archive = archive
    return st


@pytest.fixture
def st(tmp_path):
    return build(tmp_path)


# ---------------------------------------------------------------- row 1: parts


def test_body_index_links_every_part_on_its_page(st):
    """A1: one link per part, each to the comment on this page carrying that part's marker."""
    body = st.lab.part_text("body")
    links = re.findall(r"\]\(https://github\.com/([^)]+)/issues/(\d+)#issuecomment-(\d+)\)", body)
    assert len(links) == 6
    for name, (repo, page, cid) in zip(sp.COMMENT_PARTS, links):
        assert (repo, int(page)) == (REPO, PAGE)
        assert f"<!-- lab:steward-part:v1 part={name} -->" in st.lab.comment(int(cid))["body"]
    assert st("status")["parts"]["body"]["index_current"] is True


def test_index_shows_a_missing_part_and_gains_it_when_created(tmp_path):
    """A1: with five parts the sixth shows as not yet created, then links once created."""
    st = build(tmp_path, parts=sp.COMMENT_PARTS[:-1])
    assert "- Residues (not yet created)" in st.lab.part_text("body")
    assert st("status")["missing"] == ["residues"]
    st("create-part", "residues", "--text-file", st.file("## Residues"))
    cid = st.lab.part_comment("residues")["id"]
    assert f"- [Residues](https://github.com/{REPO}/issues/{PAGE}#issuecomment-{cid})" in \
        st.lab.part_text("body")


def intake_after_everything(st) -> list:
    page = sw.Page(REPO, PAGE, [*st.lab.comments[PAGE],
                                {"id": 1, "body": sw.watermark_body(1, 1, "2026-11-01T00:00:00Z", 9),
                                 "user": {"login": "Grimblaz"}, "created_at": "x"}])
    _, mark = page.watermark()
    triggers = sw.compute_triggers(page, mark, [])
    return [c["id"] for c in page.intake(mark["handled"])], triggers


def test_part_comments_new_and_edited_are_never_intake(st):
    """A2: every part comment classifies as post, after creation and after each edit."""
    assert intake_after_everything(st) == ([], [])
    one = st.add("flight", "first in flight")
    two = st.add("flight", "second in flight")
    st("replace", one, "--text-file", st.file("first, replaced"))
    st("move", two, "--position", "1")
    st("keep", one, "--reason", "still read")
    st("preamble", "traps", "--text-file", st.file("## Traps, restated"))
    st("move", two, "--kind", "trap", "--text-file", st.file("now a trap"))
    st("archive", "--read", "40", "--ids", two)
    for comment in st.lab.comments[PAGE]:
        assert sw.classify_comment(comment)["kind"] == "post"
    assert intake_after_everything(st) == ([], [])


def test_a_part_marker_without_the_post_line_or_from_another_account_is_not_a_part(tmp_path):
    """A2: only a Grimblaz comment opening with the post marker counts as a part."""
    st = build(tmp_path, parts=sp.COMMENT_PARTS[:-1])
    copied = st.lab.add_comment(PAGE, "<!-- lab:steward:v1 kind=post -->\n"
                                "<!-- lab:steward-part:v1 part=residues -->\n", login="someone")
    bare = st.lab.add_comment(PAGE, "<!-- lab:steward-part:v1 part=residues -->\nhello\n")
    status = st("status")
    assert status["missing"] == ["residues"]
    assert copied["id"] in status["not_counted"] and bare["id"] not in status["not_counted"]
    st("create-part", "residues", "--text-file", st.file("## Residues"))


def test_a_ruling_lands_in_the_body(st):
    """A3: the kind decides the part, and a ruling's part is the body."""
    rid = st.add("ruling", "Holders run the floor before review.")
    assert [e["id"] for e in st.entries("body")] == [rid]
    assert rid in st.lab.part_text("body")


def test_a_ruling_cannot_leave_the_body_and_nothing_else_enters_it(st):
    """A3: no move takes a ruling out of the body, or another kind into it."""
    rid = st.add("ruling", "Holders run the floor before review.")
    fid = st.add("flight", "in flight")
    st.refused("move", rid, "--kind", "steward-ruling", "--text-file", st.file("x"),
               match="stays in the body")
    st.refused("move", fid, "--kind", "ruling", "--text-file", st.file("x"),
               match="stays in the body")


def test_a_hand_placed_ruling_in_a_comment_part_is_a_fault(st):
    """A3: status names the misplaced ruling, and every write refuses until it is repaired."""
    text = st.lab.part_text("steward").rstrip("\n") + (
        "\n\n- smuggled <!-- lab:steward-entry:v1 id=0badcafe kind=ruling issue=none -->\n")
    st.lab.set_part("steward", text)
    st.accept("steward")
    assert any("ruling" in f and "0badcafe" in f for f in st("status")["faults"])
    st.refused("add", "--kind", "flight", "--issue", "none", "--text-file", st.file("x"),
               match="faults")


def test_body_then_load_body_lists_each_ruling(st):
    """A3: after body and load body, status counts the body's rulings by id."""
    loaded = st("load", "body", "--file", st.json_file([
        {"kind": "ruling", "issue": "none", "text": f"Ruling {n} applies." } for n in range(3)]))
    body = st("status")["parts"]["body"]
    assert body["ruling_count"] == 3
    assert body["rulings"] == loaded["ids"]


@pytest.mark.parametrize("command", ["add", "replace", "move"])
def test_a_ready_entry_is_one_line(st, command):
    """A4: add, replace and move each refuse two lines for a ready entry."""
    rid = st.add("ready", "tradecraft#1: a defect. After #2.")
    fid = st.add("flight", "in flight")
    two = st.file("line one\nline two")
    argv = {"add": ("add", "--kind", "ready", "--issue", "none", "--text-file", two),
            "replace": ("replace", rid, "--text-file", two),
            "move": ("move", fid, "--kind", "ready", "--text-file", two)}[command]
    st.refused(*argv, match="one line")


def test_keep_leaves_a_ready_entry_on_one_line(st):
    """A4: the kept reason joins a ready entry's one line."""
    rid = st.add("ready", "tradecraft#1: a defect. After #2.", "tradecraft#1")
    st("keep", rid, "--reason", "its follow-up is still open")
    (line,) = [l for l in st.lab.part_text("ready").split("\n") if rid in l]
    assert "Kept after its issue closed: its follow-up is still open <!--" in line
    assert len([l for l in st.lab.part_text("ready").split("\n") if l.startswith("1. ")]) == 1


def hand_edit(st, name: str, text: str) -> None:
    st.lab.set_part(name, text)
    st.accept(name)


@pytest.mark.parametrize("fault,match", [
    ("unmarked", "no entry marker"),
    ("duplicate-id", "appears in"),
    ("duplicate-part", "carried by two comments"),
    ("outside-repo", "lab's repositories"),
])
def test_a_fault_is_named_and_nothing_written(st, fault, match):
    """A5: each fault is reported by name, and a writing command writes nothing."""
    fid = st.add("flight", "in flight")
    flight = st.lab.part_text("flight").rstrip("\n")
    if fault == "unmarked":
        hand_edit(st, "flight", flight + "\n- a hand-added bullet\n")
    elif fault == "duplicate-id":
        st.add("trap", "a trap")
        traps = st.lab.part_text("traps").rstrip("\n")
        hand_edit(st, "traps", traps + f"\n- copy <!-- lab:steward-entry:v1 id={fid} kind=trap issue=none -->\n")
    elif fault == "duplicate-part":
        st.lab.add_comment(PAGE, "<!-- lab:steward:v1 kind=post -->\n"
                           "<!-- lab:steward-part:v1 part=flight -->\n")
    else:
        hand_edit(st, "flight", flight + "\n- x <!-- lab:steward-entry:v1 id=0000abcd kind=flight issue=Elsewhere#3 -->\n")
    assert any(match in f for f in st("status")["faults"])
    st.refused("add", "--kind", "trap", "--issue", "none", "--text-file", st.file("x"), match="faults")
    st.refused("keep", fid, "--reason", "r", match="faults")


def test_an_issue_outside_the_lab_is_refused(st):
    """A5: a repository outside the lab's six never reaches the page."""
    st.refused("add", "--kind", "flight", "--issue", "Elsewhere#3", "--text-file", st.file("x"),
               match="lab's repositories")


WRITING = [
    ("add", "--kind", "flight", "--issue", "none", "--text-file", "F"),
    ("replace", "deadbeef", "--text-file", "F"),
    ("move", "deadbeef", "--position", "1"),
    ("keep", "deadbeef", "--reason", "r"),
    ("preamble", "flight", "--text-file", "F"),
    ("create-part", "flight", "--text-file", "F"),
    ("load", "flight", "--file", "F"),
    ("body", "--text-file", "F", "--archive", "5"),
    ("archive", "--read", "3", "--closed"),
    ("archive", "--move", "--archive", "5", "--file", "F"),
    ("accept", "flight", "--sha", "0"),
    ("init-archive", "--title", "t"),
]


@pytest.mark.parametrize("argv", WRITING, ids=[" ".join(a[:2]) for a in WRITING])
def test_a_probe_page_is_refused_against_the_default_state_directory(tmp_path, monkeypatch, argv):
    """A6: a page other than 683 never runs against the live Steward's state."""
    monkeypatch.delenv(sw.STATE_ENV, raising=False)
    lab = FakeGitHub()
    path = tmp_path / "f.txt"
    path.write_bytes(b"x")
    args = sp.build_parser().parse_args([*(str(path) if a == "F" else a for a in argv),
                                         "--page", "999"])
    with pytest.raises(sw.WatchError, match="default state directory"):
        sp.run(args, github=lab.github(), now=NOW)
    assert lab.calls == []


# ---------------------------------------------------------------- row 2: limit


BIG = "x" * 25_000


def make_over(st, name: str, entries: bool = True) -> list[str]:
    """Two entries in the part, then a preamble that puts it over, with a reason shown."""
    kind = next(k for k, p in sp.KIND_PART.items() if p == name)
    ids = [st.add(kind, f"{name} entry {n}") for n in range(2)] if entries else []
    st("preamble", name, "--text-file", st.file(BIG), "--over-reason", "the move left it long")
    assert sp.size(st.lab.part_text(name)) > sp.LIMIT
    return ids


def shrinking_commands(st, name: str, ids: list[str]) -> dict:
    kind = next(k for k, p in sp.KIND_PART.items() if p == name)
    return {
        "add": ("add", "--kind", kind, "--issue", "none", "--text-file", st.file("short")),
        "replace": ("replace", ids[0], "--text-file", st.file("s")),
        "move": ("move", ids[1], "--position", "1"),
        "keep": ("keep", ids[0], "--reason", "r"),
        "preamble": ("preamble", name, "--text-file", st.file(BIG[:-10])),
        "archive": ("archive", "--read", "9", "--ids", ids[0]),
    }


@pytest.mark.parametrize("name", sp.PART_ORDER)
@pytest.mark.parametrize("command", ["add", "replace", "move", "keep", "preamble", "archive"])
def test_an_edit_leaving_a_part_over_with_no_reason_writes_nothing(st, name, command):
    """A7: on every part, the body included, even while a reason shows and the edit shrinks it."""
    ids = make_over(st, name)
    st.refused(*shrinking_commands(st, name, ids)[command], match="over its 20,000-byte limit")


@pytest.mark.parametrize("name", sp.PART_ORDER)
def test_load_into_an_over_part_with_no_reason_writes_nothing(st, name):
    """A7: load is held to the limit like every other write."""
    make_over(st, name, entries=False)
    kind = next(k for k, p in sp.KIND_PART.items() if p == name)
    st.refused("load", name, "--file", st.json_file([{"kind": kind, "issue": "none", "text": "t"}]),
               match="over its 20,000-byte limit")


@pytest.mark.parametrize("name", sp.COMMENT_PARTS)
def test_create_part_over_the_limit_with_no_reason_writes_nothing(tmp_path, name):
    """A7: a new part is held to the limit before it is posted."""
    st = build(tmp_path, parts=[n for n in sp.COMMENT_PARTS if n != name])
    st.refused("create-part", name, "--text-file", st.file(BIG), match="over its 20,000-byte limit")


def test_body_over_the_limit_with_no_reason_writes_nothing(tmp_path):
    """A7: the move's body command is held to the limit too."""
    lab = FakeGitHub()
    st = Steward(lab, tmp_path)
    archive = st("init-archive", "--title", "a")["archive"]
    st.accept("body")
    st.refused("body", "--text-file", st.file(BIG), "--archive", archive,
               match="over its 20,000-byte limit")


def test_create_part_refuses_when_the_new_index_would_put_the_body_over(tmp_path):
    """A7: the index a create-part regenerates counts against the body's limit."""
    st = build(tmp_path, parts=sp.COMMENT_PARTS[:-1])
    head = sp.size(st.lab.part_text("body"))
    st("preamble", "body", "--text-file",
       st.file("How this page is used: read this body at pickup.\n\n" + "y" * (sp.LIMIT - head - 60)))
    assert sp.size(st.lab.part_text("body")) <= sp.LIMIT
    st.refused("create-part", "residues", "--text-file", st.file("## Residues"),
               match="body part would be")


def test_growing_a_part_over_with_no_reason_and_same_with_none_shown_write_nothing(st):
    """A7: growing past the limit needs a reason, and `same` needs one already shown."""
    st.refused("add", "--kind", "flight", "--issue", "none", "--text-file", st.file(BIG),
               match="over its 20,000-byte limit")
    st.refused("add", "--kind", "flight", "--issue", "none", "--text-file", st.file(BIG),
               "--over-reason", "same", match="shows no reason")
    fid = st.add("flight", "short")
    st.refused("keep", fid, "--reason", "r" * 25_000, match="over its 20,000-byte limit")


def test_the_limit_is_twenty_thousand_bytes_of_the_text_written(st):
    """A7: 20,000 bytes is allowed and 20,001 refused, counted in UTF-8 bytes."""
    overhead = sp.size(sp.render(_traps_with(""), []))  # header, separators, newline

    def text_of(total: int) -> str:
        body = total - overhead - 2  # the blank line between header and preamble
        return chr(0xE9) * (body // 2) + "a" * (body % 2)

    st("preamble", "traps", "--text-file", st.file(text_of(sp.LIMIT)))
    assert sp.size(st.lab.part_text("traps")) == sp.LIMIT
    st.refused("preamble", "traps", "--text-file", st.file(text_of(sp.LIMIT + 1)),
               match="over its 20,000-byte limit")


def _traps_with(preamble: str) -> sp.Part:
    part = sp.Part("traps")
    part.preamble = [preamble] if preamble else []
    return part


def test_every_writing_command_takes_an_over_reason():
    """A7: every command that writes a part accepts --over-reason."""
    parser = sp.build_parser()
    for name in ("create-part", "load", "preamble", "body", "add", "replace", "move", "keep",
                 "archive"):
        sub = parser._subparsers._group_actions[0].choices[name]
        assert any("--over-reason" in a.option_strings for a in sub._actions), name


def over_shown(text: str) -> tuple[int, str] | None:
    lines = text.split("\n")
    if sp.OVER_MARKER not in lines:
        return None
    line = lines[lines.index(sp.OVER_MARKER) + 1]
    match = re.fullmatch(r"> \*\*Over its 20,000-byte limit at ([\d,]+) bytes:\*\* (.+)", line)
    return int(match.group(1).replace(",", "")), match.group(2)


@pytest.mark.parametrize("name", sp.PART_ORDER)
def test_a_reason_shows_in_the_part_and_leaves_once_back_under(st, name):
    """A8: the block carries the reason and the true size; same keeps it; under removes it."""
    make_over(st, name, entries=False)
    text = st.lab.part_text(name)
    assert over_shown(text) == (sp.size(text), "the move left it long")
    status = st("status")["parts"][name]
    assert (status["over"], status["over_reason"]) == (True, "the move left it long")
    st("preamble", name, "--text-file", st.file(BIG[:-1000]), "--over-reason", "same")
    text = st.lab.part_text(name)
    assert over_shown(text) == (sp.size(text), "the move left it long")
    st("preamble", name, "--text-file", st.file("short again"))
    assert over_shown(st.lab.part_text(name)) is None
    assert st("status")["parts"][name]["over_reason"] is None


# ---------------------------------------------------------------- row 3: tool


def stale_commands(st, fid: str, gid: str) -> list[tuple]:
    return [
        ("add", "--kind", "flight", "--issue", "none", "--text-file", st.file("x")),
        ("replace", fid, "--text-file", st.file("y")),
        ("move", gid, "--position", "1"),
        ("move", fid, "--kind", "trap", "--text-file", st.file("z")),
        ("keep", fid, "--reason", "r"),
        ("preamble", "flight", "--text-file", st.file("p")),
        ("archive", "--read", "4", "--ids", fid),
    ]


def test_a_stale_saved_copy_writes_nothing_and_shows_the_difference(st):
    """A9: with the live part changed by another hand, every writing command refuses with a diff."""
    fid, gid = st.add("flight", "first"), st.add("flight", "second")
    live = st.lab.part_text("flight")
    st.lab.set_part("flight", live.replace("second", "second, edited by hand"))
    for argv in stale_commands(st, fid, gid):
        error = st.refused(*argv, match="differs from the saved copy")
        assert "+" in error.detail["diff"] and "second, edited by hand" in error.detail["diff"]
        assert error.detail["live_sha256"] == sp.sha256(st.lab.part_text("flight"))
    error = st.refused("load", "flight", "--file", st.json_file([]))  # load refuses a part with entries
    assert "already holds entries" in str(error)


def test_a_part_changed_mid_archive_stops_the_run_at_that_part(st):
    """A9: the re-read before each write catches a change after the first read; later parts wait."""
    ids = {name: st.add(kind, f"{name} entry")
           for name, kind in (("ready", "ready"), ("flight", "flight"), ("traps", "trap"))}
    flight_id = st.lab.part_comment("flight")["id"]

    def tamper():
        comment = st.lab.part_comment("flight")
        comment["body"] = comment["body"].replace("## In flight", "## In flight, by hand")

    st.lab.on_get(f"issues/comments/{flight_id}", tamper)
    with pytest.raises(sp.PageError, match="differs from the saved copy") as info:
        st("archive", "--read", "7", "--ids", *ids.values())
    assert info.value.detail["stopped_at"] == "flight"
    assert ids["ready"] not in st.lab.part_text("ready")
    assert ids["flight"] in st.lab.part_text("flight") and ids["traps"] in st.lab.part_text("traps")
    posts = len(st.lab.writes())
    st.accept("flight")
    st("archive", "--read", "7", "--ids", ids["flight"], ids["traps"])
    archive_writes = [c for c in st.lab.writes()[posts:] if f"issues/{st.archive}" in c[1]
                      or c[1].endswith(str(_archive_comment(st, 7)["id"]))]
    assert archive_writes == [], "entries already in the read's comment were posted again"
    assert ids["flight"] not in st.lab.part_text("flight")
    assert ids["traps"] not in st.lab.part_text("traps")


def _archive_comment(st, read: int) -> dict:
    (found,) = [c for c in st.lab.comments[st.archive]
                if c["body"].startswith(f"<!-- lab:steward-archive:v1 read={read} -->")]
    return found


def test_no_saved_copy_writes_nothing_until_the_live_part_is_accepted(st):
    """A10: a replacement Steward sees the live part, and only its shown SHA is accepted."""
    for path in (st.state / f"page-{PAGE}").iterdir():
        path.unlink()
    error = st.refused("add", "--kind", "flight", "--issue", "none", "--text-file", st.file("x"),
                       match="no saved copy")
    assert error.detail["live"] == st.lab.part_text("flight")
    shown = error.detail["live_sha256"]
    st.lab.set_part("flight", st.lab.part_text("flight") + "changed meanwhile\n")
    st.refused("accept", "flight", "--sha", shown, match="no longer")
    st.accept("flight")
    st.add("flight", "x")


def test_status_and_show_never_create_a_saved_copy(tmp_path):
    """A10: reading the page leaves the state directory untouched."""
    st = build(tmp_path)
    fresh = Steward(st.lab, tmp_path / "fresh")
    fresh("status")
    for name in sp.PART_ORDER:
        fresh("show", name)
    assert not (tmp_path / "fresh" / "state").exists()
    assert {p["copy"] for p in fresh("status")["parts"].values()} == {"no-copy"}


def numbers(st) -> list[str]:
    return [l.split(".", 1)[0] for l in st.lab.part_text("ready").split("\n") if re.match(r"\d+\. ", l)]


def test_the_ready_list_is_numbered_in_order_after_every_change(st):
    """A11: from a misnumbered list, add, move within, move out and archive each renumber 1..n."""
    a, b, c = (st.add("ready", f"tradecraft#{n}: defect {n}.") for n in (1, 2, 3))
    text = st.lab.part_text("ready")
    for wrong, line in zip(("3", "3", "7"), [l for l in text.split("\n") if re.match(r"\d+\. ", l)]):
        text = text.replace(line, wrong + line[1:])
    hand_edit(st, "ready", text)
    assert numbers(st) == ["3", "3", "7"]
    d = st.add("ready", "tradecraft#4: defect 4.", "none", "--position", "2")
    assert numbers(st) == ["1", "2", "3", "4"]
    assert [e["id"] for e in st.entries("ready")] == [a, d, b, c]
    st("move", c, "--position", "1")
    assert numbers(st) == ["1", "2", "3", "4"]
    st("move", a, "--kind", "flight", "--text-file", st.file("now in flight"))
    assert numbers(st) == ["1", "2", "3"]
    st("archive", "--read", "8", "--ids", d)
    assert numbers(st) == ["1", "2"]
    assert [e["id"] for e in st.entries("ready")] == [c, b]


def test_the_closed_lists_name_exactly_the_closed_references(st):
    """A12: over two repositories and more than 50 references, in every state GitHub reports."""
    lab = st.lab
    states = {"open": issue(), "completed": issue("CLOSED", "COMPLETED"),
              "not-planned": issue("CLOSED", "NOT_PLANNED"), "no-reason": issue("CLOSED", None),
              "merged": pull("MERGED", True), "unmerged": pull("CLOSED", False),
              "pr-open": pull()}
    expected = {}
    flight, rulings = [], []
    number = 100
    for repo in ("tradecraft", "Daemon"):
        for label, node in states.items():
            for _ in range(4):
                number += 1
                ref = f"{repo}#{number}"
                lab.states[ref] = node
                flight.append({"kind": "flight", "issue": ref, "text": f"{label} {ref}"})
                rulings.append({"kind": "ruling", "issue": ref, "text": f"ruling {label} {ref}"})
                expected[ref] = label
    flight.append({"kind": "flight", "issue": "none", "text": "no issue"})
    st("load", "flight", "--file", st.json_file(flight), "--over-reason", "a test of many entries")
    st("load", "body", "--file", st.json_file(rulings), "--over-reason", "a test of many entries")
    kept_ref = "tradecraft#101"  # open
    kept = [e for e in st.entries("flight") if e["issue"] == "tradecraft#102"][0]["id"]
    st("keep", kept, "--reason", "still read", "--over-reason", "same")
    status = st("status")
    assert len([c for c in lab.calls if c[1] == "graphql"]) >= 2
    closed = {(r["kind"], r["issue"]) for r in status["closed"]}
    unlanded = {(r["kind"], r["issue"]) for r in status["closed_without_landing"]}
    for ref, label in expected.items():
        is_closed = label not in ("open", "pr-open")
        landed = label in ("completed", "merged")
        if ref == "tradecraft#102":
            assert ("flight", ref) not in closed
        else:
            assert (("flight", ref) in closed) == is_closed, ref
        assert (("ruling", ref) in closed) == (is_closed and landed), ref
        assert (("ruling", ref) in unlanded) == (is_closed and not landed), ref
    assert [r["id"] for r in status["kept"]] == [kept]
    assert all(r["issue"] != "none" for r in status["closed"])
    assert kept_ref not in {r["issue"] for r in status["closed"]}
    assert status["unresolved"] == []


def test_an_unresolvable_reference_is_an_error_never_open(st):
    """A12: a reference GitHub cannot resolve is reported, and the rest still resolve."""
    st.lab.states["tradecraft#890"] = issue("CLOSED", "COMPLETED")
    st.add("flight", "known", "tradecraft#890")
    st.add("flight", "unknown", "tradecraft#99999")
    status = st("status")
    assert [u["issue"] for u in status["unresolved"]] == ["tradecraft#99999"]
    assert "Could not resolve" in status["unresolved"][0]["error"]
    assert [r["issue"] for r in status["closed"]] == ["tradecraft#890"]


def test_no_marker_starts_a_list_item_or_shares_a_line_with_other_text(st):
    """A13: each marker is on its own line or ends an entry's first line."""
    st.add("ruling", "A **bold** ruling.", "none")
    st.add("ready", "**tradecraft#5**: a defect.", "none")
    fid = st.add("flight", "multi\nline\n\n  - nested")
    st("keep", fid, "--reason", "why")
    make_over(st, "traps", entries=True)
    for name in sp.PART_ORDER:
        for line in st.lab.part_text(name).split("\n"):
            if "<!--" not in line:
                continue
            assert not re.match(r"\s*(?:[-*+]|\d+[.)])\s*<!--", line), line
            whole = line.startswith("<!--") and line.endswith("-->") and line.count("<!--") == 1
            assert whole or sp.ENTRY_LINE.fullmatch(line), line


@pytest.mark.parametrize("char", ["\x1b", "\x00"])
def test_control_characters_are_refused(st, char):
    """A14: text carrying a control character never reaches the page."""
    st.refused("add", "--kind", "flight", "--issue", "none", "--text-file", st.file(f"a{char}b"),
               match="control character")
    st.refused("keep", st.add("flight", "x"), "--reason", f"a{char}b", match="control character")


def test_a_byte_order_mark_is_refused(st):
    """A14: a BOM in a text file is refused."""
    st.refused("add", "--kind", "flight", "--issue", "none", "--text-file", st.file(sw.BOM + "a"),
               match="byte-order mark")


def test_a_write_read_back_differently_leaves_the_copy_so_the_next_edit_is_stale(st):
    """A14: the copy moves only on a confirmed write."""
    st.lab.store = lambda endpoint, body: body + "GitHub changed this\n"
    with pytest.raises(sp.PageError, match="read back differently"):
        st.add("flight", "x")
    st.lab.store = lambda endpoint, body: body
    st.refused("add", "--kind", "flight", "--issue", "none", "--text-file", st.file("y"),
               match="differs from the saved copy")


def test_every_command_on_its_happy_path(st):
    """A14: each page edit the Steward makes is a command."""
    st.lab.states["tradecraft#890"] = issue("CLOSED", "COMPLETED")
    rid = st.add("ruling", "A ruling.")
    sid = st.add("owner-wait", "Waits on the owner.")
    fid = st.add("flight", "In flight.", "tradecraft#890")
    gid = st.add("flight", "Also in flight.", "none", "--after", fid)
    st("replace", rid, "--text-file", st.file("A ruling, restated."))
    st("replace", rid, "--issue", "tradecraft#890")
    st("move", gid, "--position", "1")
    st("move", sid, "--kind", "owed", "--text-file", st.file("Owed by the Steward."))
    st("keep", gid, "--reason", "still read")
    st("replace", gid, "--clear-kept")
    st("preamble", "body", "--text-file", st.file("How this page is used, restated."))
    assert "restated" in st.lab.part_text("body") and sp.INDEX_BEGIN in st.lab.part_text("body")
    result = st("archive", "--read", "41", "--closed")
    assert set(result["archived"]) == {fid, rid}
    entries = {e["id"]: e for n in sp.PART_ORDER for e in st.entries(n)}
    assert set(entries) == {sid, gid}
    assert entries[sid]["kind"] == "owed" and entries[gid]["kept"] is False
    assert st("status")["faults"] == []


def test_create_part_is_refused_for_an_existing_part_and_body_once_marked(st):
    """A14: create-part and body each refuse to overwrite what exists."""
    st.refused("create-part", "flight", "--text-file", st.file("x"), match="already exists")
    st.refused("body", "--text-file", st.file("x"), "--archive", st.archive,
               match="already carries the page marker")
    st.refused("init-archive", "--title", "again", match="already names archive")


# ---------------------------------------------------------------- row 4: archive


def test_the_archive_posts_before_any_part_is_written_and_holds_each_entry_word_for_word(st):
    """A15: the archive comment comes first, and every removed entry is in it exactly."""
    st.lab.states["tradecraft#890"] = issue("CLOSED", "COMPLETED")
    ids = [st.add("flight", "landed\n  with a second line", "tradecraft#890"),
           st.add("ready", "tradecraft#890: landed.", "tradecraft#890"),
           st.add("ruling", "a ruling whose change landed", "tradecraft#890")]
    texts = {e: _entry_text(st, e) for e in ids}
    start = len(st.lab.writes())
    st("archive", "--read", "42", "--closed")
    order = st.lab.writes()[start:]
    assert f"issues/{st.archive}/comments" in order[0][1]
    archive = _archive_comment(st, 42)["body"]
    for eid, text in texts.items():
        assert text in archive
        assert eid not in st.lab.part_text(sp.KIND_PART[_kind_of(text)])


def _entry_text(st, eid: str) -> str:
    for name in sp.PART_ORDER:
        part = sp.parse_part(name, st.lab.part_text(name), sp.lab_short_names())
        for entry in part.entries:
            if entry.id == eid:
                return entry.text
    raise AssertionError(eid)


def _kind_of(text: str) -> str:
    return sp.ENTRY_MARKER.search(text).group("kind")


def test_a_stale_part_refuses_the_archive_before_anything_is_posted(st):
    """A15: the first read stale-checks every affected part."""
    fid = st.add("flight", "x")
    st.lab.set_part("flight", st.lab.part_text("flight") + "hand\n")
    st.refused("archive", "--read", "43", "--ids", fid, match="differs from the saved copy")
    assert st.lab.comments[st.archive][1:] == []


def test_an_archive_read_back_missing_an_entry_removes_nothing(st):
    """A15: nothing leaves the page unless the archive comment holds it."""
    fid, gid = st.add("flight", "kept on GitHub"), st.add("flight", "dropped by GitHub")
    st.lab.store = lambda endpoint, body: (body.replace(_entry_text(st, gid), "")
                                           if f"issues/{st.archive}/" in endpoint else body)
    with pytest.raises(sp.PageError, match="removed from the page"):
        st("archive", "--read", "44", "--ids", fid, gid)
    assert {fid, gid} <= {e["id"] for e in st.entries("flight")}


def test_a_second_run_for_a_read_appends_to_its_one_comment(st):
    """A15: one comment per read, appended to and never duplicated."""
    fid = st.add("flight", "first")
    st("archive", "--read", "45", "--ids", fid)
    first = _archive_comment(st, 45)["body"]
    gid = st.add("trap", "second")
    st("archive", "--read", "45", "--ids", gid)
    after = _archive_comment(st, 45)["body"]
    assert after.startswith(first.rstrip("\n")) and f"id={gid}" in after
    assert len([c for c in st.lab.comments[st.archive] if "read=45" in c["body"]]) == 1


def test_no_other_command_removes_an_entry(st):
    """A15: only archive reduces the set of entry ids."""
    a, b = st.add("flight", "a"), st.add("flight", "b")
    seen = st.ids()
    for argv in (("replace", a, "--text-file", st.file("a2")), ("move", b, "--position", "1"),
                 ("move", a, "--kind", "trap", "--text-file", st.file("a3")),
                 ("keep", b, "--reason", "r"), ("preamble", "flight", "--text-file", st.file("p")),
                 ("preamble", "body", "--text-file", st.file("p"))):
        st(*argv)
        assert seen <= st.ids()


def test_a_ruling_closed_without_landing_refuses_the_read_until_kept_or_repointed(st):
    """A16: the run names the ruling; after keep or replace --issue it completes."""
    lab = st.lab
    lab.states.update({"tradecraft#501": issue("CLOSED", "NOT_PLANNED"),
                       "tradecraft#502": pull("CLOSED", False),
                       "tradecraft#503": issue(), "tradecraft#504": issue("CLOSED", "COMPLETED")})
    r1 = st.add("ruling", "carried by a declined issue", "tradecraft#501")
    r2 = st.add("ruling", "carried by an unmerged pull request", "tradecraft#502")
    landed = st.add("flight", "landed", "tradecraft#504")
    error = st.refused("archive", "--read", "46", "--closed", match="closed without landing")
    assert {r["id"] for r in error.detail["closed_without_landing"]} == {r1, r2}
    st("keep", r1, "--reason", "its follow-up carries it")
    st("replace", r2, "--issue", "tradecraft#503")
    st("archive", "--read", "46", "--closed")
    status = st("status")
    assert status["closed"] == [] and status["closed_without_landing"] == []
    assert [r["id"] for r in status["kept"]] == [r1]
    assert landed not in {e["id"] for e in st.entries("flight")}
    assert "Kept after its issue closed: its follow-up carries it" in st.lab.part_text("body")


def test_after_closed_every_closed_entry_left_is_kept_and_says_why(st):
    """A16: closed entries go, kept ones stay with their reasons, open ones stay."""
    st.lab.states.update({"tradecraft#601": issue("CLOSED", "COMPLETED"),
                          "Daemon#602": pull("MERGED", True), "tradecraft#603": issue()})
    gone = [st.add("flight", "closed", "tradecraft#601"), st.add("trap", "merged", "Daemon#602")]
    kept = st.add("ruling", "kept ruling", "tradecraft#601")
    st("keep", kept, "--reason", "still applies until #700")
    opened = st.add("flight", "open", "tradecraft#603")
    st("archive", "--read", "47", "--closed")
    left = st.ids()
    assert not set(gone) & left and {kept, opened} <= left
    status = st("status")
    assert status["closed"] == [] and [r["reason"] for r in status["kept"]] == ["still applies until #700"]


def test_closed_leaves_issueless_entries_and_ids_archives_them(st):
    """A17: a ruling with no carrying change leaves only when named."""
    rid = st.add("ruling", "no carrying change")
    text = _entry_text(st, rid)
    st("archive", "--read", "48", "--closed")
    assert rid in st.ids()
    st("archive", "--read", "48", "--ids", rid)
    assert rid not in st.ids()
    assert text in _archive_comment(st, 48)["body"]


def test_the_move_archive_posts_the_file_whole_and_only_once(st):
    """C13: the move's archive comment holds the old page, and a second move is refused."""
    (move,) = [c for c in st.lab.comments[st.archive] if "event=move" in c["body"]]
    assert OLD_BODY.strip("\n") in move["body"]
    st.refused("archive", "--move", "--archive", st.archive, "--file", st.file("again"),
               match="already holds the move")


def test_parse_and_render_round_trip(st):
    """C5, C7: the tool reads back exactly what it writes."""
    st.add("flight", "one\n  two")
    make_over(st, "flight", entries=False)
    for name in sp.PART_ORDER:
        text = st.lab.part_text(name)
        page = sp.Page(PAGE, st.lab.part_text("body"), st.lab.comments[PAGE], sp.lab_short_names())
        part = page.body if name == "body" else page.parts[name]
        over = sp.over_line(sp.size(text), part.over_reason) if part.over_reason else None
        assert sp.render(part, page.index(), over) == text
