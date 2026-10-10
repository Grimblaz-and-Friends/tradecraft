"""Declared JSON version fields shared by use classification and catch-up."""
from __future__ import annotations

import json
from decimal import Decimal
import re


def declaration(policy: dict) -> dict | None:
    value = policy.get("version")
    if value is None and "version" not in policy:
        return None
    if not isinstance(value, dict) or set(value) != {"path", "field", "increment"}:
        raise ValueError("version declaration requires path, field and increment")
    path, field = value["path"], value["field"]
    if (not isinstance(path, str) or not path.strip() or "\\" in path or re.match(r"^[A-Za-z]:", path)
            or any(ord(char) < 32 or 127 <= ord(char) < 160 for char in path)
            or any(part in {"", ".", ".."} for part in path.split("/"))):
        raise ValueError("version file must be a repository-relative path")
    if not isinstance(field, str) or not field.strip():
        raise ValueError("version field must name a top-level JSON member")
    if not isinstance(value["increment"], str) or value["increment"] not in {"major", "minor", "patch"}:
        raise ValueError("version increment must be major, minor or patch")
    return value


def json_object(content: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("version JSON contains a duplicate member")
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError(f"invalid JSON numeric constant: {value}")
    value = json.loads(content.decode("utf-8"), object_pairs_hook=pairs,
                       parse_float=Decimal, parse_constant=invalid_constant)
    if not isinstance(value, dict):
        raise ValueError("declared version file must contain a JSON object")
    return value


def document(content: bytes, spec: dict) -> dict:
    value = json_object(content)
    if (not isinstance(value.get(spec["field"]), str)
            or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value[spec["field"]]) is None):
        raise ValueError("declared version must be a top-level string with three integer parts")
    return value


def parts(version: str) -> tuple[int, int, int]:
    """Compare the declared grammar numerically, including multi-digit parts."""
    if not isinstance(version, str) or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) is None:
        raise ValueError("declared version must be a string with three integer parts")
    major, minor, patch = map(int, version.split("."))
    return major, minor, patch


def json_equal(left, right) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(json_equal(value, right[key]) for key, value in left.items())
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(json_equal(a, b) for a, b in zip(left, right))
    return left == right


def only_version(before: bytes, after: bytes, spec: dict) -> bool:
    left, right = json_object(before), json_object(after)
    left.pop(spec["field"], None)
    right.pop(spec["field"], None)
    return json_equal(left, right)


def increment(content: bytes, spec: dict) -> str:
    parts = [int(part) for part in document(content, spec)[spec["field"]].split(".")]
    selected = ("major", "minor", "patch").index(spec["increment"])
    parts[selected] += 1
    parts[selected + 1:] = [0] * (2 - selected)
    return ".".join(map(str, parts))


def replace_field(content: bytes, spec: dict, version: str) -> bytes:
    """Keep all bytes outside the top-level member's string token."""
    document(content, spec)
    text = content.decode("utf-8")
    decoder = json.JSONDecoder()
    position = text.index("{") + 1
    while True:
        while text[position].isspace() or text[position] == ",":
            position += 1
        key, end = decoder.raw_decode(text, position)
        position = end
        while text[position].isspace() or text[position] == ":":
            position += 1
        start = position
        _, position = decoder.raw_decode(text, position)
        if key == spec["field"]:
            return (text[:start] + json.dumps(version) + text[position:]).encode("utf-8")
