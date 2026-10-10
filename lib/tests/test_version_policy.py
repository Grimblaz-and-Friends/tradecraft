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
