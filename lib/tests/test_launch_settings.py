import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import launch_settings as settings


def entry(role="implementer", vendor="codex"):
    return {"id": f"ruling-{role}-{vendor}", "role": role, "vendor": vendor,
            "replaces": {"model": "old", "effort": "old-effort"},
            "model": "ruled", "effort": "ruled-effort", "source": "issuecomment-123"}


def write(path, entries):
    path.write_bytes(json.dumps({"schema_version": 1, "entries": entries}).encode())


def resolve(bridge, role="implementer", vendor="codex", model="old", effort="old-effort", **kwargs):
    return settings.resolve(role, vendor, model, effort, "model default", "effort default",
                            bridge=bridge, **kwargs)


@pytest.mark.parametrize("role", settings.ROLES)
@pytest.mark.parametrize("vendor", settings.VENDORS)
def test_ruling_is_scoped_and_provenance_survives_file_removal(tmp_path, role, vendor):
    path = tmp_path / "model-rulings.json"
    ruled = entry(role, vendor)
    write(path, [ruled])
    bridge = settings.read_bridge(path)
    selected = resolve(bridge, role, vendor)
    path.unlink()
    assert (selected.model, selected.effort) == ("ruled", "ruled-effort")
    provenance = json.loads(selected.model_source.removeprefix("model ruling "))
    assert provenance == {"path": str(path.resolve()), **ruled}
    assert selected.effort_source == selected.model_source
    other = "claude" if vendor == "codex" else "codex"
    assert resolve(bridge, role, other).model == "old"
    other_role = "cold_seat" if role == "implementer" else "implementer"
    assert resolve(bridge, other_role, vendor).model == "old"


@pytest.mark.parametrize(("model", "effort"), [
    ("new", "old-effort"), ("old", "new-effort"), ("new", "new-effort"),
    ("ruled", "ruled-effort"),
])
def test_exact_pair_lapse_is_visible_and_leaves_file_intact(tmp_path, model, effort):
    path = tmp_path / "rulings.json"
    write(path, [entry()])
    original = path.read_bytes()
    selected = resolve(settings.read_bridge(path), model=model, effort=effort)
    assert (selected.model, selected.effort) == (model, effort)
    assert selected.bridge["disposition"] == "lapsed"
    assert selected.bridge["running"] == {"model": model, "effort": effort}
    assert selected.bridge["replaces"] == entry()["replaces"]
    assert selected.model_source == "model default"
    assert path.read_bytes() == original


def test_explicit_field_equal_to_default_keeps_its_source(tmp_path):
    path = tmp_path / "rulings.json"
    write(path, [entry()])
    selected = resolve(settings.read_bridge(path), explicit_model="old",
                       explicit_model_source="direct --model")
    assert selected.model == "old"
    assert selected.model_source == "direct --model"
    assert selected.effort == "ruled-effort"
    assert "ruling-implementer-codex" in selected.effort_source


def test_absent_empty_and_next_read(tmp_path):
    path = tmp_path / "missing" / "rulings.json"
    assert resolve(settings.read_bridge(path)).model == "old"
    assert not path.parent.exists()
    path.parent.mkdir()
    write(path, [])
    assert resolve(settings.read_bridge(path)).model == "old"
    write(path, [entry()])
    assert resolve(settings.read_bridge(path)).model == "ruled"
    changed = {**entry(), "model": "second-ruling"}
    write(path, [changed])
    assert resolve(settings.read_bridge(path)).model == "second-ruling"


@pytest.mark.parametrize("raw", [
    b"{", b"\xff", b'[]', b'{"schema_version":2,"entries":[]}',
    b'{"schema_version":true,"entries":[]}',
    b'{"schema_version":1,"schema_version":1,"entries":[]}',
    b'{"schema_version":1,"entries":{},"unknown":0}',
])
def test_invalid_wire_shape_names_path(tmp_path, raw):
    path = tmp_path / "rulings.json"
    path.write_bytes(raw)
    with pytest.raises(settings.SettingsError, match="rulings.json"):
        settings.read_bridge(path)


@pytest.mark.parametrize("change", [
    {"role": "cold-seat"}, {"vendor": "other"}, {"id": " "}, {"source": ""},
    {"model": "bad:model"}, {"effort": "two words"}, {"unknown": "x"},
    {"replaces": {"model": "old"}}, {"replaces": {"model": "old", "effort": " "}},
])
def test_invalid_entry_is_refused(tmp_path, change):
    path = tmp_path / "rulings.json"
    write(path, [{**entry(), **change}])
    with pytest.raises(settings.SettingsError):
        settings.read_bridge(path)


@pytest.mark.parametrize("second", [entry(), {**entry(), "id": "another"},
                                    {**entry("cold_seat"), "id": entry()["id"]}])
def test_duplicate_identity_or_scope_refused(tmp_path, second):
    path = tmp_path / "rulings.json"
    write(path, [entry(), second])
    with pytest.raises(settings.SettingsError, match="duplicate entry"):
        settings.read_bridge(path)


def test_unreadable_file_is_not_absence(tmp_path, monkeypatch):
    def denied(_self):
        raise PermissionError("denied")
    monkeypatch.setattr(Path, "read_bytes", denied)
    with pytest.raises(settings.SettingsError, match="cannot read.*rulings.json.*denied"):
        settings.read_bridge(tmp_path / "rulings.json")


def test_print_flushes_before_return(monkeypatch):
    class Stream:
        def __init__(self):
            self.output = ""
            self.flushed = None
        def write(self, value):
            self.output += value
        def flush(self):
            self.flushed = self.output
    stream = Stream()
    monkeypatch.setattr(sys, "stdout", stream)
    settings.print_plan({"model": "ruled"}, label="fixture")
    assert stream.flushed == stream.output
    assert '"model": "ruled"' in stream.output
