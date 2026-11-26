"""A plugins folder changed during a stand-in launch, and what the practice makes of it.

Each scenario builds a fixture home in a temporary folder, takes a launch comparison's
real before-snapshot, makes its changes, takes the real after-snapshot and compares
(`launch_bound.Comparison`). It prints the comparison as a launch's run record carries
it, then whether the entrance reads that launch as clear or held, through the
entrance's own launch-findings reading. `--list` names the scenarios. Nothing outside
the temporary folder is read or written, and the folder is removed afterwards.
It ships beside the tests so a holder or a use session can see what a situation
records and how the entrance reads it, without waiting for a live launch to meet it.
Run under `python -B`, so importing the tree writes no bytecode into it for a launch's comparison
to see. Paths under the temporary folder print as `<fixture>`.
Design: lib/DESIGN.md#what-a-launch-comparison-releases
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import py_compile
import shutil
import sys
import tempfile

LIB = Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

import launch_bound  # noqa: E402

HOLDER = "01234567-89ab-cdef-0123-456789abcdef"
OWN = "c" * 32
PRODUCER = "holder-fixture"
WORK = "example/product#12"
MARKET, WIDGET, GADGET = "acme-market", "widget", "gadget"


class Home:
    """A home whose plugins folder has one marketplace, two installed plugins and one retired version,
    which two sessions' in-use markers still name.

    It names no real path, repository or marketplace, so what holds in it holds on any adopter's machine.
    """

    def __init__(self, base: Path):
        self.base = Path(base).resolve()
        self.home = self.base / "home"
        self.plugins = self.home / ".claude" / "plugins"
        self.store = self.home / ".tradecraft" / "dispatches"
        self.own = self.base / "own"
        self.clock = 1_700_000_000
        for path in (self.store, self.own / ".git", self.base / "records", self.base / "launcher"):
            path.mkdir(parents=True, exist_ok=True)
        self.own_request = self.base / "records" / "own.md.request.json"
        self.own_request.write_bytes(b"{}")
        widget = f"cache/{MARKET}/{WIDGET}/1.0.0"
        for rel, data in {
                f"{widget}/.claude-plugin/plugin.json": b'{"name": "widget"}',
                f"{widget}/lib/mod.py": b"VALUE = 1\n",
                f"{widget}/lib/util.py": b"HELPER = 1\n",
                f"{widget}/.in_use/4101": b'{"pid": 4101}',
                f"cache/{MARKET}/{GADGET}/3.0.0/.claude-plugin/plugin.json": b'{"name": "gadget"}',
                f"cache/{MARKET}/{GADGET}/2.0.0/.claude-plugin/plugin.json": b'{"name": "gadget"}',
                f"cache/{MARKET}/{GADGET}/2.0.0/.in_use/6101": b'{"pid": 6101}',
                f"cache/{MARKET}/{GADGET}/2.0.0/.in_use/6102": b'{"pid": 6102}',
                f"marketplaces/{MARKET}/.claude-plugin/marketplace.json": b'{"plugins": []}',
                f"marketplaces/{MARKET}/README.md": b"# acme\n",
                "synced/account-1/.marketplaces.json": b"[]",
                "store/usage-queue.json": b'{"usage-rows-queued": []}',
                "plugin-directory-cache-v2.json": b'{"listings": []}',
                ".last_inuse_sweep": b"2026-11-01T00:00:00.000Z",
                f"data/{WIDGET}/state.json": b"{}"}.items():
            self.write(rel, data)
        self.compile(f"{widget}/lib/mod.py", f"{widget}/lib/__pycache__/mod.cpython-312.pyc")
        self.marketplaces = {MARKET: {"source": {"source": "github", "repo": "acme/market"},
                                      "installLocation": str(self.plugins / "marketplaces" / MARKET),
                                      "lastUpdated": "2026-11-01T00:00:00.000Z"}}
        self.installed = {"version": 2, "plugins": {
            f"{WIDGET}@{MARKET}": [self.entry(WIDGET, "1.0.0")],
            f"{GADGET}@{MARKET}": [self.entry(GADGET, "3.0.0")]}}
        self.save_records()

    def entry(self, plugin: str, version: str) -> dict:
        return {"scope": "user", "installPath": str(self.plugins / "cache" / MARKET / plugin / version),
                "version": version, "installedAt": "2026-10-01T00:00:00.000Z",
                "lastUpdated": "2026-11-01T00:00:00.000Z"}

    def path(self, rel: str) -> Path:
        return self.plugins / rel

    def write(self, rel: str, data: bytes, *, top: Path | None = None) -> Path:
        """Write a file and move its time on, so the walk sees the change whatever the clock's grain."""
        path = (top or self.plugins) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.clock += 10
        os.utime(path, ns=(self.clock * 10**9, self.clock * 10**9))
        return path

    def compile(self, source: str, compiled: str, mode: str = "TIMESTAMP", *, top: Path | None = None) -> Path:
        """Compile a source into a compiled file with Python's own compiler, in the mode named.

        ``TIMESTAMP`` is how an import compiles; ``CHECKED_HASH`` and ``UNCHECKED_HASH`` are what a
        compile step asking for them writes. The mode is always named, so the environment can't choose it.
        """
        path = (top or self.plugins) / compiled
        path.parent.mkdir(parents=True, exist_ok=True)
        py_compile.compile(str((top or self.plugins) / source), cfile=str(path), doraise=True,
                           invalidation_mode=py_compile.PycInvalidationMode[mode])
        self.clock += 10
        os.utime(path, ns=(self.clock * 10**9, self.clock * 10**9))
        return path

    def remove(self, rel: str) -> None:
        path = self.path(rel)
        shutil.rmtree(path) if path.is_dir() else path.unlink()

    def save_records(self, *names: str) -> None:
        """Rewrite the named install records, or both, as the app does when it changes one."""
        values = {"known_marketplaces.json": self.marketplaces, "installed_plugins.json": self.installed}
        for name in names or tuple(values):
            self.write(name, json.dumps(values[name], indent=2).encode("utf-8"))

    def comparison(self, launcher: Path | None = None) -> launch_bound.Comparison:
        value = launch_bound.Comparison(
            root=self.own, env={}, launcher_plugin=launcher or self.base / "launcher",
            own_output=self.own_request.with_name("own.md"), own_request=self.own_request,
            holder_session_id=HOLDER, dispatch_id=OWN, home=self.home, store=self.store)
        value.take_before(60)
        return value

    def bundle(self, comparison: dict) -> None:
        """The launch's request and run records, as the launcher leaves them once it stops.

        The launch opens at the comparison's before-snapshot and completes at its after-snapshot,
        so a change's timing reads against the launch as it would on a real run.
        """
        request = {"schema_version": 2, "dispatch_id": OWN, "work": WORK, "stage": "build",
                   "launched_at": comparison.get("before_at") or comparison["after_at"],
                   "requested": {"vendor": "claude"},
                   "write_bound": {"file_tools": None, "memory": None, "comparison": {"coverage": []},
                                   "shell": launch_bound.SHELL}}
        run = {"schema_version": 2, "dispatch_id": OWN, "lifecycle": "completed",
               "completed_at": comparison["after_at"], "outcome": "success",
               "attempts": [{"vendor": "claude", "launched": True}], "launch_comparison": comparison}
        (self.store / "launch.md.request.json").write_text(json.dumps(request), encoding="utf-8")
        (self.store / "launch.md.run.json").write_text(json.dumps(run), encoding="utf-8")


def entrance(home: Home, comparison: dict, accounts: tuple[dict, ...] = ()) -> dict:
    """The entrance's reading of this one launch, through its own launch-findings evaluation."""
    import work
    home.bundle(comparison)
    # An account counts only once posted after the launch completed.
    posted = (datetime.fromisoformat(comparison["after_at"]) + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    comments = [{"body": f"<!-- tradecraft:launch-account:v1 dispatch={OWN} -->\n\n```json\n"
                         + json.dumps({"schema_version": 1, "findings": list(accounts)}) + "\n```\n",
                 "user": {"login": PRODUCER}, "created_at": posted}] if accounts else []
    state = work.WorkState("example/product", 12,
                           {"number": 12, "state": "open", "body": "", "labels": [],
                            "user": {"login": PRODUCER}},
                           issue_comments=comments,
                           config=work.WorkConfig(marker_producers=frozenset({PRODUCER})))
    state.record_root = home.store
    work.validate_marker_claims(state)
    report = work._evaluate_launch_findings(state)
    bundle = report["bundles"][0]
    return {"status": report["status"], "state": bundle["state"],
            "owed": [finding["id"] for finding in bundle.get("owed") or []]}


# --- The scenarios ----------------------------------------------------------------

def _upkeep(home: Home) -> None:
    widget = f"cache/{MARKET}/{WIDGET}/1.0.0"
    home.write("synced/account-1/.marketplaces.json", b'[{"name": "acme-market"}]')
    home.write(f"{widget}/.in_use/5202", b'{"pid": 5202}')
    home.write(f"cache/{MARKET}/{GADGET}/2.0.0/.orphaned_at", b"1700000000")
    home.compile(f"{widget}/lib/util.py", f"{widget}/lib/__pycache__/util.cpython-312.pyc")
    home.write("store/usage-queue.json", b'{"usage-rows-queued": [1]}')
    home.write("plugin-directory-cache-v2.json", b'{"listings": [1]}')
    home.write(".last_inuse_sweep", b"2026-11-03T05:30:00.000Z")


def _update(home: Home, plugin: str = WIDGET, old: str = "1.0.0", new: str = "2.0.0") -> None:
    home.write(f"cache/{MARKET}/{plugin}/{new}/.claude-plugin/plugin.json", b'{"name": "%s"}' % plugin.encode())
    home.write(f"cache/{MARKET}/{plugin}/{new}/lib/mod.py", b"VALUE = 2\n")
    home.remove(f"cache/{MARKET}/{plugin}/{old}")
    home.installed["plugins"][f"{plugin}@{MARKET}"] = [
        {**home.entry(plugin, new), "lastUpdated": "2026-11-03T05:31:00.000Z"}]
    home.save_records("installed_plugins.json")
    _refresh(home)


def _refresh(home: Home) -> None:
    home.marketplaces[MARKET]["lastUpdated"] = "2026-11-03T05:30:00.000Z"
    home.save_records("known_marketplaces.json")
    home.write(f"marketplaces/{MARKET}/.claude-plugin/marketplace.json", b'{"plugins": ["widget"]}')


def _stray_edit(home: Home) -> None:
    _upkeep(home)
    home.write(f"cache/{MARKET}/{WIDGET}/1.0.0/lib/mod.py", b"VALUE = 'edited in place'\n")


def _repoint(home: Home) -> None:
    home.installed["plugins"][f"{WIDGET}@{MARKET}"] = [
        {**home.entry(WIDGET, "1.0.0"), "installPath": str(home.base / "elsewhere" / WIDGET)}]
    home.save_records("installed_plugins.json")


def _source(home: Home) -> None:
    home.marketplaces[MARKET]["source"] = {"source": "github", "repo": "someone-else/market"}
    home.save_records("known_marketplaces.json")


def _sourceless(home: Home) -> None:
    home.write(f"cache/{MARKET}/{WIDGET}/1.0.0/lib/helper.pyc", b"\x00pyc")


def _installed_removed(home: Home) -> None:
    home.remove(f"cache/{MARKET}/{GADGET}/3.0.0")


def _retired_removed(home: Home) -> None:
    home.remove(f"cache/{MARKET}/{GADGET}/2.0.0")


def _marked_installed(home: Home) -> None:
    home.write(f"cache/{MARKET}/{GADGET}/3.0.0/.orphaned_at", b"1700000000")


def _unchecked_bytecode(home: Home) -> None:
    widget = f"cache/{MARKET}/{WIDGET}/1.0.0"
    home.compile(f"{widget}/lib/util.py", f"{widget}/lib/__pycache__/util.cpython-312.pyc", "UNCHECKED_HASH")


def _data_write(home: Home) -> None:
    home.write(f"data/{WIDGET}/state.json", b'{"runs": 1}')


def _new_plugin(home: Home) -> None:
    home.write(f"cache/{MARKET}/newcomer/1.0.0/.claude-plugin/plugin.json", b'{"name": "newcomer"}')
    home.installed["plugins"][f"newcomer@{MARKET}"] = [home.entry("newcomer", "1.0.0")]
    home.save_records("installed_plugins.json")


SCENARIOS = {
    "upkeep": ("the synced marketplace list, an in-use marker, an orphan marker, a compiled file in "
               "__pycache__, the usage queue, the catalog cache and the last-sweep stamp rewritten", _upkeep),
    "update": ("an installed plugin's new version folder added and its old one removed, "
               "installed_plugins.json moved to it, and the marketplace refreshed", _update),
    "refresh": ("only the marketplace's refresh time moved in known_marketplaces.json, "
                "and its clone changed", _refresh),
    "stray-edit": ("upkeep, plus one file edited inside an installed version that stayed", _stray_edit),
    "repoint": ("installed_plugins.json points a plugin at a path no update in the run added", _repoint),
    "source": ("a marketplace's source changed in known_marketplaces.json", _source),
    "sourceless": ("a compiled file written beside a plugin's modules, outside __pycache__", _sourceless),
    "new-plugin": ("a plugin's folder appears with its first version, and installed_plugins.json "
                   "gains its key", _new_plugin),
    "recorded-before": ("a run record in the form written before released changes were recorded, "
                        "with upkeep findings and no account", _upkeep),
    "installed-removed": ("an installed version folder removed while installed_plugins.json still "
                          "points at it", _installed_removed),
    "data-write": ("a file in a plugin's own data folder rewritten", _data_write),
    "retired-removed": ("an old version folder no entry in installed_plugins.json points at removed, "
                        "with two in-use markers in it", _retired_removed),
    "marked-installed": ("an orphan marker written at the top of a version folder installed_plugins.json "
                         "still points at", _marked_installed),
    "unchecked-bytecode": ("a module of an installed plugin compiled into its __pycache__ folder in the "
                           "mode Python loads without checking it against its source", _unchecked_bytecode),
}


def recorded_before(comparison: dict) -> dict:
    """The comparison as a launcher recorded it before released changes existed: every one a finding."""
    findings = [{key: entry[key] for key in ("id", "item", "path", "change")} | {"reason": None}
                for entry in comparison["released"]] + list(comparison["findings"])
    old = {key: value for key, value in comparison.items() if key != "released"}
    return {**old, "status": "findings" if findings else "clean",
            "findings": sorted(findings, key=lambda value: value["id"])}


def run(name: str, base: Path) -> dict:
    """One scenario's comparison record, the entrance's reading of it, and its fixture home."""
    home = Home(base)
    comparison = home.comparison()
    SCENARIOS[name][1](home)
    result = comparison.finish(60)
    if name == "recorded-before":
        result = recorded_before(result)
    return {"comparison": result, "entrance": entrance(home, result), "home": home}


def _shown(value: object, base: Path) -> str:
    text = json.dumps(value, indent=2, ensure_ascii=True)
    for form in {str(base), str(base).replace("\\", "/")}:
        # A path inside a reason is escaped twice: once in the reason, once in the record.
        text = text.replace(json.dumps(json.dumps(form)[1:-1])[1:-1], "<fixture>")
        text = text.replace(json.dumps(form)[1:-1], "<fixture>")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("scenario", nargs="?", choices=sorted(SCENARIOS))
    parser.add_argument("--list", action="store_true", help="name every scenario and what it changes")
    arguments = parser.parse_args(argv)
    if arguments.list or not arguments.scenario:
        for name, (what, _make) in SCENARIOS.items():
            print(f"{name}: {what}")
        return 0
    with tempfile.TemporaryDirectory(prefix="release-fixture-") as folder:
        base = Path(folder).resolve()
        result = run(arguments.scenario, base)
        print(f"Scenario {arguments.scenario}: {SCENARIOS[arguments.scenario][0]}.")
        print("\nThe run record's launch_comparison:")
        print(_shown(result["comparison"], base))
        reading = result["entrance"]
        print("\nThe entrance reads this launch as: " + (
            "clear; nothing is owed" if reading["status"] == "clear"
            else f"held ({reading['state']}); a launch-account is owed for " + ", ".join(reading["owed"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
