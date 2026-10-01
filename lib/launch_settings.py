"""Resolve defaulted launch fields against a sourced machine-local ruling."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re

ROLES = ("artifact_author", "implementer", "ordinary_seat", "cold_seat",
         "terminal_seat", "use_consumer")
VENDORS = ("codex", "claude")
VALUE = re.compile(r"[^\s:]+\Z")


class SettingsError(ValueError):
    """A present ruling file cannot be interpreted unambiguously."""


@dataclass(frozen=True)
class Bridge:
    path: Path
    entries: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True)
class LaunchSettings:
    model: str
    effort: str
    model_source: str
    effort_source: str
    baseline: dict[str, str] = field(default_factory=dict, compare=False)
    bridge: dict[str, object] | None = field(default=None, compare=False)

    def as_dict(self, vendor: str, vendor_source: str) -> dict[str, object]:
        return {
            "vendor": vendor, "model": self.model, "effort": self.effort,
            "sources": {"vendor": vendor_source, "model": self.model_source,
                        "effort": self.effort_source},
            "baseline": self.baseline, "bridge": self.bridge,
        }


def default_path() -> Path:
    return Path.home() / ".tradecraft" / "model-rulings.json"


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SettingsError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _fields(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise SettingsError(f"{label} requires exactly these fields: {', '.join(expected)}")


def _string(value, label, *, setting=False):
    if not isinstance(value, str) or not value.strip():
        raise SettingsError(f"{label} must be a nonempty string")
    if setting and VALUE.fullmatch(value) is None:
        raise SettingsError(f"{label} must contain no whitespace or colon")


def read_bridge(path: Path | None = None) -> Bridge:
    selected = (path or default_path()).expanduser().resolve()
    try:
        raw = selected.read_bytes()
    except FileNotFoundError:
        return Bridge(selected)
    except OSError as exc:
        raise SettingsError(f"cannot read model rulings {selected}: {exc}") from exc
    try:
        value = json.loads(raw, object_pairs_hook=_object)
        _fields(value, ("schema_version", "entries"), "model rulings")
        if type(value["schema_version"]) is not int or value["schema_version"] != 1:
            raise SettingsError("unsupported schema_version (expected 1)")
        if not isinstance(value["entries"], list):
            raise SettingsError("entries must be a list")
        ids, keys = set(), set()
        for entry in value["entries"]:
            _fields(entry, ("id", "role", "vendor", "replaces", "model", "effort", "source"), "entry")
            for name in ("id", "role", "vendor", "model", "effort", "source"):
                _string(entry[name], name, setting=name in {"model", "effort"})
            if entry["role"] not in ROLES or entry["vendor"] not in VENDORS:
                raise SettingsError("entry has unknown role or vendor")
            _fields(entry["replaces"], ("model", "effort"), "replaces")
            for name in ("model", "effort"):
                _string(entry["replaces"][name], f"replaces.{name}", setting=True)
            key = (entry["role"], entry["vendor"])
            if entry["id"] in ids or key in keys:
                raise SettingsError("duplicate entry ID or role/vendor pair")
            ids.add(entry["id"])
            keys.add(key)
        return Bridge(selected, tuple(value["entries"]))
    except (UnicodeError, ValueError) as exc:
        raise SettingsError(f"invalid model rulings {selected}: {exc}") from exc


def resolve(role: str, vendor: str, model: str, effort: str,
            model_source: str, effort_source: str, *, bridge: Bridge,
            explicit_model: str | None = None, explicit_effort: str | None = None,
            explicit_model_source: str | None = None,
            explicit_effort_source: str | None = None) -> LaunchSettings:
    if role not in ROLES or vendor not in VENDORS:
        raise SettingsError(f"unknown launch role/vendor: {role}/{vendor}")
    baseline = {"model": model, "effort": effort}
    entry = next((item for item in bridge.entries
                  if item["role"] == role and item["vendor"] == vendor), None)
    disposition = None
    if entry is not None:
        applicable = entry["replaces"] == baseline
        disposition = {**entry, "path": str(bridge.path), "running": baseline,
                       "disposition": "applicable" if applicable else "lapsed"}
        if applicable:
            source = "model ruling " + json.dumps({
                "path": str(bridge.path), **entry,
            }, ensure_ascii=True, sort_keys=True)
            model, effort = entry["model"], entry["effort"]
            model_source = effort_source = source
    if explicit_model is not None:
        model, model_source = explicit_model, explicit_model_source
    if explicit_effort is not None:
        effort, effort_source = explicit_effort, explicit_effort_source
    return LaunchSettings(model, effort, model_source, effort_source, baseline, disposition)


def print_plan(plan: dict[str, object], *, label: str) -> None:
    print(f"{label}: launch_settings " + json.dumps(plan, ensure_ascii=True, sort_keys=True), flush=True)
