"""The cold reader's tree, anchors, links and account form at their edges.

Design: lib/DESIGN.md#the-cold-reader
"""
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cold_reader  # noqa: E402
from test_cold_reader import BRANCH, WORK, commit, git  # noqa: E402


def source(tmp_path, base_files, head_files, removed=()):
    root = tmp_path / "source"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "core.autocrlf", "false")
    base = commit(root, base_files, "base")
    for name in removed:
        git(root, "rm", "-q", name)
    # The fixture's commit helper stages everything, so a removal alone still commits.
    return root, base, commit(root, head_files, "change")


def build(tmp_path, root, base, head, name="reading"):
    return cold_reader.build_tree(
        source=root, output=tmp_path / name, work=WORK, producer_version="0.206.0",
        base_tip=base, head=head, covered=None, branch=BRANCH, numbers=[])


def account(flags, sections="a.py:1 {dash} opens the file; the reason is in its comment."):
    dash = cold_reader.EM_DASH
    return ("## Sections\n" + sections.format(dash=dash) + "\n\n## Flags\n" + flags.format(dash=dash)
            + "\n\n## Why this change was made\nCan tell: yes\nThe comment says why.\n\n"
            "## Worth a look\na.py:1 " + dash + " a pointer.\n")


@pytest.mark.parametrize("written", ["none", "`none`", "- none", "* none", "None", "none.",
                                     "- `None.`", "* `none`."])
def test_no_flags_is_accepted_however_it_is_formatted(written):
    text = account(written)
    assert cold_reader.form_errors(text) == []
    assert cold_reader.parse_account(text)["flags"] == []


def test_an_empty_sections_heading_is_refused():
    errors = cold_reader.form_errors(account("none", sections=""))
    assert errors == ["## Sections holds nothing"]


def test_a_deletion_only_change_carries_no_files_and_still_builds(tmp_path):
    root, base, head = source(tmp_path, {"a.py": "A = 1\n", "keep.py": "K = 1\n"}, {}, removed=["a.py"])
    metadata = cold_reader.load_metadata(build(tmp_path, root, base, head))
    assert metadata["change_set"] == {"a.py": "deleted"}
    assert set(metadata["files"]) <= {cold_reader.DIFF_FILE}
    assert not (tmp_path / "reading" / "keep.py").exists()
    assert "-A = 1" in (tmp_path / "reading" / cold_reader.DIFF_FILE).read_text("utf-8")


def test_a_flag_on_a_covered_deleted_file_passes_the_form_and_stands_until_reread(tmp_path):
    root, base, head = source(tmp_path, {"a.py": "A = 1\n", "b.py": "B = 1\n"},
                              {"b.py": "B = 2\n"}, removed=["a.py"])
    metadata = cold_reader.load_metadata(build(tmp_path, root, base, head))
    allowed = cold_reader.flaggable(metadata)
    assert allowed == {"a.py", "b.py"}
    text = account("a.py:1 {dash} missing-reason {dash} the removal gives no reason")
    assert cold_reader.form_errors(text, allowed) == []
    flags = cold_reader.parse_account(text)["flags"]
    present = cold_reader.current(root, base, head)
    first = {"id": 1, "coverage": metadata["coverage"], "account": {"flags": flags, "can_tell": True}}
    judged = cold_reader.assess([first], present)
    assert [flag["path"] for flag in judged["flags"]] == ["a.py"] and judged["owed"] == ["a.py"]
    reread = {"id": 2, "coverage": {"a.py": metadata["coverage"]["a.py"]},
              "account": {"flags": [], "can_tell": True}}
    assert cold_reader.assess([first, reread], present)["flags"] == []


def test_a_numbered_anchor_reaches_the_repeated_heading():
    text = ("# Doc\n\n## Notes\n\n[one](one.md)\n\n## Notes\n\n[two](two.md)\n\n"
            "## Notes\n\n[three](three.md)\n")
    tree = {"one.md": "1", "two.md": "2", "three.md": "3"}
    assert [record["path"] for record in cold_reader._section_records("doc.md", text, "notes-1", tree)] == [
        "two.md"]
    assert [record["path"] for record in cold_reader._section_records("doc.md", text, "notes-2", tree)] == [
        "three.md"]
    assert [record["path"] for record in cold_reader._section_records("doc.md", text, "notes", tree)] == [
        "one.md"]


def test_a_pointer_to_a_numbered_anchor_carries_the_second_sections_links(tmp_path):
    root, base, head = source(tmp_path, {
        "doc.md": "# Doc\n\n## Notes\n\n[one](one.md)\n\n## Notes\n\n[two](two.md)\n",
        "one.md": "# One\n", "two.md": "# Two\n",
    }, {"a.py": "# Design: doc.md#notes-1\n"})
    metadata = cold_reader.load_metadata(build(tmp_path, root, base, head))
    assert sorted(metadata["files"]) == ["a.py", "doc.md", "two.md"]


def test_reference_links_in_a_pointed_section_are_carried():
    text = ("# Doc\n\n## S\n\nSee [full][Guide], [Collapsed][], [shortcut] and [missing].\n\n"
            "## Other\n\n[other][o]\n\n[guide]: notes/guide.md\n[collapsed]: <notes/collapsed.md> \"t\"\n"
            "[SHORTCUT]: ../top.md#part\n[o]: notes/other.md\n")
    tree = {"design/notes/guide.md": "g", "design/notes/collapsed.md": "c", "top.md": "t",
            "design/notes/other.md": "o"}
    records = cold_reader._section_records("design/doc.md", text, "s", tree)
    assert sorted(record["path"] for record in records) == [
        "design/notes/collapsed.md", "design/notes/guide.md", "top.md"]


def test_a_pointer_written_with_a_leading_dot_slash_resolves_like_one_without(tmp_path):
    root, base, head = source(tmp_path, {
        "design/x.md": "# X\n\n## S\n\n[d](../decisions/D1.md)\n", "decisions/D1.md": "# D1\n",
        "lib/notes.md": "# Notes\n\n## Here\n\n[g](guide.md)\n", "lib/guide.md": "# Guide\n",
    }, {"a.py": "# Design: ./design/x.md#s\n", "lib/b.py": "# Design: ./notes.md#here\n"})
    metadata = cold_reader.load_metadata(build(tmp_path, root, base, head))
    dependency = metadata["coverage"]["a.py"]["dependencies"][0]
    assert dependency["path"] == "design/x.md" and dependency["records"][0]["path"] == "decisions/D1.md"
    assert metadata["coverage"]["lib/b.py"]["dependencies"][0]["path"] == "lib/notes.md"
    assert sorted(metadata["files"]) == ["a.py", "decisions/D1.md", "design/x.md", "lib/b.py",
                                        "lib/guide.md", "lib/notes.md"]


def test_a_renamed_and_edited_file_shows_its_removed_lines(tmp_path):
    body = "".join(f"LINE_{number} = {number}\n" for number in range(20))
    root = tmp_path / "source"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "core.autocrlf", "false")
    base = commit(root, {"old.py": body}, "base")
    git(root, "mv", "old.py", "new.py")
    head = commit(root, {"new.py": body.replace("LINE_3 = 3\n", "LINE_3 = 33\n")}, "rename")
    metadata = cold_reader.load_metadata(build(tmp_path, root, base, head))
    assert metadata["change_set"] == {"new.py": metadata["files"]["new.py"]["oid"]}
    diff = cold_reader.recipient_tree.metadata_path(tmp_path / "reading").with_suffix(".diff")
    text = diff.read_text("utf-8")
    assert "rename from old.py" in text and "-LINE_3 = 3\n" in text and "+LINE_3 = 33\n" in text


def test_a_committed_root_change_diff_is_refused_when_the_diff_travels_as_a_file(tmp_path, monkeypatch):
    root, base, head = source(tmp_path, {"a.py": "A = 1\n"},
                              {"a.py": "A = 2\n", cold_reader.DIFF_FILE: "not the diff\n"})
    monkeypatch.setattr(cold_reader, "INLINE_DIFF_CHARACTERS", 0)
    with pytest.raises(cold_reader.ColdReaderError, match=cold_reader.DIFF_FILE):
        build(tmp_path, root, base, head)
    assert not (tmp_path / "reading").exists()
    assert not cold_reader.recipient_tree.metadata_path(tmp_path / "reading").exists()


def test_a_repository_whose_git_converts_line_endings_still_builds_its_reading_tree(tmp_path):
    root, base, head = source(tmp_path, {"README.md": "# Readme\n"},
                              {"a.py": "A = 1\nB = 2\n", "notes.md": "# Notes\nline\n"})
    # No attributes, and a machine setting that converts line endings on checkout and archive.
    git(root, "config", "core.autocrlf", "true")
    metadata = cold_reader.load_metadata(build(tmp_path, root, base, head))
    assert (tmp_path / "reading" / "a.py").read_bytes() == b"A = 1\nB = 2\n"
    assert sorted(metadata["files"]) == ["a.py", "notes.md"]


def test_a_change_holding_a_symlink_is_refused_naming_it_rather_than_escaping_the_stage(tmp_path):
    root, base, _head = source(tmp_path, {"README.md": "# Readme\n"}, {"a.py": "A = 1\n"})
    # Staged by mode, so the test needs no symlink support from the platform.
    target = subprocess.run(["git", "-C", str(root), "hash-object", "-w", "--stdin"], input=b"a.py",
                            capture_output=True, check=True).stdout.decode("ascii").strip()
    git(root, "update-index", "--add", "--cacheinfo", f"120000,{target},link.py")
    git(root, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com", "commit", "-q", "-m", "link")
    head = git(root, "rev-parse", "HEAD")
    with pytest.raises(cold_reader.ColdReaderError, match="link.py"):
        build(tmp_path, root, base, head)
    assert not (tmp_path / "reading").exists()
