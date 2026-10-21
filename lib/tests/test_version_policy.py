import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import version_policy


@pytest.mark.parametrize("part,target", [("major", "3.0.0"), ("minor", "2.10.0"), ("patch", "2.9.10")])
def test_declared_increment_and_numeric_comparison(part, target):
    spec = {"path": "package.json", "field": "release", "increment": part}
    assert version_policy.increment(b'{"release":"2.9.9"}', spec) == target
    assert version_policy.parts("2.9.10") < version_policy.parts("2.10.0")
    assert version_policy.parts("3.0.0") > version_policy.parts("2.10.0")


@pytest.mark.parametrize("value", [None, {}, {"path": "package.json", "field": "release", "increment": "minor", "target": "2.10.0"}])
def test_present_declaration_retains_exact_schema(value):
    with pytest.raises(ValueError):
        version_policy.declaration({"version": value})
    assert version_policy.declaration({}) is None


@pytest.mark.parametrize("content", [b'[]', b'{"release":1}', b'{"release":null}', b'{}',
    b'{"release":"2.9"}', b'{"release":"2.9.9-beta"}', b'{"release":"2.9.9","release":"3.0.0"}',
    b'{"release":"2.9.9","nested":{"x":1,"x":2}}', b'{"release":"2.9.9","x":NaN}'])
def test_invalid_declared_json_cannot_supply_a_version(content):
    with pytest.raises(ValueError):
        version_policy.document(content, {"field": "release"})


def test_replacement_preserves_catch_up_bytes_and_other_members():
    content = b'{\r\n  "release" : "2.9.9", "other": {"value": 1}\r\n}\r\n'
    spec = {"path": "package.json", "field": "release", "increment": "minor"}
    replaced = version_policy.replace_field(content, spec, version_policy.increment(content, spec))
    assert replaced == content.replace(b'"2.9.9"', b'"2.10.0"')
    assert version_policy.only_version(content, replaced, spec)
    assert json.loads(replaced)["other"] == {"value": 1}


OWING_SPEC = {"path": "package.json", "field": "release", "increment": "minor"}


def owing(records, field_only=lambda: True):
    calls = []
    def judged():
        calls.append(True)
        return field_only()
    paths, confined = version_policy.owing(
        records, OWING_SPEC, lambda path: path.startswith("runtime/") or path == "package.json", judged)
    return paths, confined, len(calls)


def record(filename, status="modified", previous=None):
    return {"filename": filename, "status": status, "previous_filename": previous}


def test_owing_keeps_removals_and_both_rename_names():
    paths, confined, calls = owing([record("runtime/gone.py", "removed"),
                                    record("notes/moved.py", "renamed", "runtime/old.py"),
                                    record("README.md")])
    assert (paths, confined, calls) == (["runtime/gone.py", "runtime/old.py"], False, 0)


def test_field_only_declared_change_owes_nothing_and_another_member_still_owes():
    assert owing([record("package.json"), record("README.md")]) == ([], True, 1)
    assert owing([record("package.json")], field_only=lambda: False) == (["package.json"], False, 1)


@pytest.mark.parametrize("records", [
    [record("package.json", "added")],
    [record("package.json", "removed")],
    [record("package.json", "changed")],
    [record("package.json", "renamed", "old.json")],
    [record("new.json", "renamed", "package.json")],
    [record("package.json"), record("other.json", "renamed", "package.json")],
])
def test_only_one_ordinary_modification_can_be_field_only(records):
    paths, confined, calls = owing(records)
    assert "package.json" in paths and confined is False and calls == 0


def test_unmatched_or_undeclared_file_never_consults_field_only():
    assert version_policy.owing([record("package.json")], OWING_SPEC, lambda path: False,
                                lambda: pytest.fail("consulted")) == ([], False)
    assert version_policy.owing([record("package.json")], None, lambda path: True,
                                lambda: pytest.fail("consulted")) == (["package.json"], False)
