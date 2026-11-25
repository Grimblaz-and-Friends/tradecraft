"""What a launch comparison releases in the plugins folder, and what still holds.

Design: lib/DESIGN.md#what-a-launch-comparison-releases
"""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(LIB / "tests"))
import launch_bound
import launch_release
import release_fixture
from release_fixture import GADGET, MARKET, WIDGET, Home

WIDGET_V1 = f"cache/{MARKET}/{WIDGET}/1.0.0"
GADGET_V3 = f"cache/{MARKET}/{GADGET}/3.0.0"
UPKEEP = {"synced/account-1/.marketplaces.json": "synced-marketplaces",
          f"{WIDGET_V1}/.in_use/5202": "in-use-marker",
          f"{GADGET_V3}/.orphaned_at": "orphan-marker",
          f"{WIDGET_V1}/lib/__pycache__/util.cpython-312.pyc": "bytecode",
          "store/usage-queue.json": "usage-queue",
          "plugin-directory-cache-v2.json": "catalog-cache",
          ".last_inuse_sweep": "in-use-marker"}


@pytest.fixture
def home(tmp_path):
    return Home(tmp_path / "fixture")


def rel(home, entry):
    """A recorded path relative to the plugins folder, with forward slashes."""
    path = Path(entry["path"])
    try:
        return path.relative_to(home.plugins).as_posix()
    except ValueError:
        return path.as_posix()


def held(result, home):
    return sorted(rel(home, finding) for finding in result["findings"])


def kinds(result, home, item="plugins"):
    return {rel(home, entry): entry["kind"] for entry in result["released"] if entry["item"] == item}


# --- The upkeep kinds release; one more file, or a sourceless .pyc, holds -----------

def launcher_at(home, where):
    """The launcher's plugin root: an installed version that stays, or a checkout outside the plugins folder."""
    if where == "installed":
        return home.path(WIDGET_V1)
    top = home.base / "launcher-checkout"
    home.write("lib/__pycache__/mod.cpython-312.pyc", b"\x00pyc", top=top)
    home.write(".in_use/4101", b"{}", top=top)
    return top


def launcher_upkeep(home, top):
    home.write("lib/__pycache__/fresh.cpython-312.pyc", b"\x00pyc", top=top)
    home.write(".in_use/7303", b"{}", top=top)
    home.write(".orphaned_at", b"1700000000", top=top)


@pytest.mark.parametrize("where", ["installed", "checkout"])
def test_upkeep_alone_holds_nothing_and_is_listed_by_kind_in_both_items(home, where):
    launcher = launcher_at(home, where)
    before = home.comparison(launcher)
    release_fixture._upkeep(home)
    launcher_upkeep(home, launcher)
    result = before.finish(60)
    assert result["status"] == "clean" and result["findings"] == []
    assert kinds(result, home) == {**UPKEEP, **({f"{WIDGET_V1}/lib/__pycache__/fresh.cpython-312.pyc": "bytecode",
                                                 f"{WIDGET_V1}/.in_use/7303": "in-use-marker",
                                                 f"{WIDGET_V1}/.orphaned_at": "orphan-marker"}
                                                if where == "installed" else {})}
    own = {Path(entry["path"]).relative_to(launcher).as_posix(): entry["kind"]
           for entry in result["released"] if entry["item"] == "launcher-plugin"}
    expected = {"lib/__pycache__/fresh.cpython-312.pyc": "bytecode", ".in_use/7303": "in-use-marker",
                ".orphaned_at": "orphan-marker"}
    if where == "installed":
        expected.update({"lib/__pycache__/util.cpython-312.pyc": "bytecode", ".in_use/5202": "in-use-marker"})
    assert own == expected
    for entry in result["released"]:
        assert entry["id"] == launch_bound._finding_id(entry["item"], entry["path"], entry["change"])


def test_one_more_file_elsewhere_in_the_plugins_folder_is_the_one_finding(home):
    before = home.comparison()
    release_fixture._upkeep(home)
    home.write(f"data/{WIDGET}/added.json", b"{}")
    result = before.finish(60)
    assert held(result, home) == [f"data/{WIDGET}/added.json"]
    assert set(kinds(result, home).values()) == set(UPKEEP.values())


def test_a_compiled_file_outside_pycache_is_the_one_finding(home):
    before = home.comparison()
    release_fixture._upkeep(home)
    release_fixture._sourceless(home)
    result = before.finish(60)
    assert held(result, home) == [f"{WIDGET_V1}/lib/helper.pyc"]


def test_an_upkeep_name_in_the_wrong_place_holds(home):
    before = home.comparison()
    home.write("store/sub/x.json", b"{}")
    home.write(f"cache/{MARKET}/synced/x.json", b"{}")
    result = before.finish(60)
    assert {"store/sub/x.json", f"cache/{MARKET}/synced/x.json"} <= set(held(result, home))
    assert result["released"] == []


def test_a_file_where_the_synced_folder_belongs_holds(home):
    home.remove("synced")
    before = home.comparison()
    home.write("synced", b"not a folder")
    result = before.finish(60)
    assert held(result, home) == ["synced"] and result["released"] == []


@pytest.mark.parametrize("separator", ["/", "\\"])
def test_paths_read_alike_with_either_separator(separator):
    top = separator.join(["", "fixture", "home", ".claude", "plugins"])

    def change(path, kind="added"):
        return {"item": "plugins", "path": top + separator + path.replace("/", separator), "change": kind}

    changes = [change(f"{WIDGET_V1}/lib/__pycache__/x.pyc"), change(f"{WIDGET_V1}/.in_use/9"),
               change("synced/a/.marketplaces.json", "modified"), change("store/q.json", "modified"),
               change("plugin-directory-cache-v3.json", "modified"), change(f"{GADGET_V3}/.orphaned_at"),
               change(f"{WIDGET_V1}/lib/x.pyc"), change(f"data/{WIDGET}/x.json"),
               change(f"cache/{MARKET}/{GADGET}/4.0.0"), change(f"cache/{MARKET}/{GADGET}/4.0.0/p.json")]
    released, _reasons = launch_release.classify(changes, {"plugins": top}, windows=False)
    assert {index: value["kind"] for index, value in released.items()} == {
        0: "bytecode", 1: "in-use-marker", 2: "synced-marketplaces", 3: "usage-queue", 4: "catalog-cache",
        5: "orphan-marker", 8: "version-folder", 9: "version-folder"}


def test_a_home_whose_folded_name_changes_length_still_releases():
    # The sharp s folds to "ss", one character longer, so a cut at the folded top's length would misread.
    top = "C:\\Users\\Stra" + chr(0xDF) + "e\\.claude\\plugins"
    changes = [{"item": "plugins", "path": top + "\\synced\\a.json", "change": "added"},
               {"item": "plugins", "path": top + "\\store\\q.json", "change": "modified"}]
    released, _reasons = launch_release.classify(changes, {"plugins": top}, windows=True)
    assert {index: value["kind"] for index, value in released.items()} == {
        0: "synced-marketplaces", 1: "usage-queue"}


def test_released_changes_never_wait_on_the_store(home, monkeypatch):
    before = home.comparison()
    release_fixture._upkeep(home)

    def refused(*_args, **_kwargs):
        raise AssertionError("the store was read for a released change")

    monkeypatch.setattr(launch_bound, "overlapping_runs", refused)
    assert before.finish(60)["status"] == "clean"


# --- A whole version folder releases; an edit inside one, or a new plugin, holds ---------

def swap(home, plugin=GADGET, old="3.0.0", new="4.0.0"):
    home.write(f"cache/{MARKET}/{plugin}/{new}/.claude-plugin/plugin.json", b"{}")
    home.write(f"cache/{MARKET}/{plugin}/{new}/skills/a/SKILL.md", b"# a\n")
    home.remove(f"cache/{MARKET}/{plugin}/{old}")


def test_a_version_swap_releases_everything_under_both_folders(home):
    before = home.comparison()
    swap(home)
    result = before.finish(60)
    assert result["findings"] == []
    released = kinds(result, home)
    assert released and set(released.values()) == {"version-folder"}
    assert {path.split("/")[3] for path in released} == {"3.0.0", "4.0.0"}


def test_a_swap_of_the_launchers_own_version_holds_nothing(home):
    launcher = home.path(GADGET_V3)
    home.write(".in_use/4101", b"{}", top=launcher)
    home.write("lib/__pycache__/m.cpython-312.pyc", b"\x00", top=launcher)
    before = home.comparison(launcher)
    home.write(".in_use/5202", b"{}", top=launcher)
    home.write("lib/__pycache__/n.cpython-312.pyc", b"\x00", top=launcher)
    swap(home)
    result = before.finish(60)
    assert result["findings"] == []
    own = [entry for entry in result["released"] if entry["item"] == "launcher-plugin"]
    assert own and {entry["change"] for entry in own} == {"removed"}


def test_a_file_changed_inside_a_version_that_stayed_holds(home):
    before = home.comparison()
    home.write(f"{GADGET_V3}/.claude-plugin/plugin.json", b'{"name": "edited"}')
    assert held(before.finish(60), home) == [f"{GADGET_V3}/.claude-plugin/plugin.json"]


def test_a_plugins_own_folder_appearing_holds(home):
    before = home.comparison()
    home.write(f"cache/{MARKET}/newcomer/1.0.0/.claude-plugin/plugin.json", b"{}")
    result = before.finish(60)
    assert held(result, home) == [f"cache/{MARKET}/newcomer"]
    assert set(kinds(result, home).values()) == {"version-folder"}


def test_a_marketplaces_own_folder_appearing_holds(home):
    before = home.comparison()
    home.write("cache/other-market/thing/1.0.0/plugin.json", b"{}")
    assert held(before.finish(60), home) == ["cache/other-market", "cache/other-market/thing"]


# --- The install records, by what they say --------------------------------------

def finding(result, home, name):
    return next(entry for entry in result["findings"] if rel(home, entry) == name)


def test_a_refresh_time_alone_releases_and_a_source_change_holds(home):
    before = home.comparison()
    home.marketplaces[MARKET]["lastUpdated"] = "2026-11-03T05:30:00.000Z"
    home.save_records()
    result = before.finish(60)
    assert result["findings"] == []
    assert [entry["basis"] for entry in result["released"] if rel(home, entry) == "known_marketplaces.json"] \
        == ["no listed field changed"]

    before = home.comparison()
    release_fixture._source(home)
    reason = finding(before.finish(60), home, "known_marketplaces.json")["reason"]
    assert MARKET in reason and "source" in reason
    assert "acme/market" in reason and "someone-else/market" in reason


def test_a_move_to_a_version_folder_added_in_the_launch_releases(home):
    before = home.comparison()
    release_fixture._update(home)
    result = before.finish(60)
    assert result["findings"] == []
    basis = next(entry["basis"] for entry in result["released"] if rel(home, entry) == "installed_plugins.json")
    assert basis == "update to " + str(home.path(f"cache/{MARKET}/{WIDGET}/2.0.0"))


def test_a_move_to_a_path_no_update_added_holds_naming_both_paths(home):
    before = home.comparison()
    release_fixture._repoint(home)
    reason = finding(before.finish(60), home, "installed_plugins.json")["reason"]
    assert f"{WIDGET}@{MARKET}" in reason and "installPath" in reason
    assert json.dumps(str(home.path(WIDGET_V1))) in reason
    assert json.dumps(str(home.base / "elsewhere" / WIDGET)) in reason


@pytest.mark.parametrize("field", ["scope", "projectPath"])
def test_a_scope_or_project_change_holds_naming_the_field(home, field):
    before = home.comparison()
    home.installed["plugins"][f"{GADGET}@{MARKET}"][0][field] = "local" if field == "scope" else "/elsewhere"
    home.save_records()
    reason = finding(before.finish(60), home, "installed_plugins.json")["reason"]
    assert f"{GADGET}@{MARKET}" in reason and f" {field} " in reason


def test_a_plugin_key_added_holds_naming_it(home):
    before = home.comparison()
    home.installed["plugins"][f"newcomer@{MARKET}"] = [home.entry("newcomer", "1.0.0")]
    home.save_records()
    assert f"plugin newcomer@{MARKET} added" in finding(before.finish(60), home, "installed_plugins.json")["reason"]


@pytest.mark.parametrize("change", ["top-level version", "unnamed field", "time fields"])
def test_fields_outside_the_compared_ones_release(home, change):
    before = home.comparison()
    if change == "top-level version":
        home.installed["version"] = 3
    elif change == "unnamed field":
        home.installed["plugins"][f"{WIDGET}@{MARKET}"][0]["gitCommitSha"] = "f" * 40
    else:
        home.installed["plugins"][f"{WIDGET}@{MARKET}"][0]["lastUpdated"] = "2026-11-03T05:31:00.000Z"
    home.save_records()
    result = before.finish(60)
    assert result["findings"] == []
    assert {rel(home, entry): entry["kind"] for entry in result["released"]} == {
        "installed_plugins.json": "install-record", "known_marketplaces.json": "install-record"}


@pytest.mark.parametrize("refreshed", [True, False])
def test_a_marketplace_clone_change_releases_only_with_its_refresh(home, refreshed):
    before = home.comparison()
    if refreshed:
        release_fixture._refresh(home)
    else:
        home.write(f"marketplaces/{MARKET}/README.md", b"# changed\n")
    result = before.finish(60)
    clone = [entry for entry in result["released"] + result["findings"]
             if rel(home, entry).startswith("marketplaces/")]
    assert clone
    if refreshed:
        assert result["findings"] == [] and {entry.get("kind") for entry in clone} == {"marketplace-refresh"}
    else:
        assert held(result, home) == [f"marketplaces/{MARKET}/README.md"]


@pytest.mark.parametrize("side", ["before", "after"])
@pytest.mark.parametrize("record", ["known_marketplaces.json", "installed_plugins.json"])
def test_an_unparsable_reading_holds_and_says_which(home, side, record):
    if side == "before":
        home.write(record, b"{not json")
    before = home.comparison()
    if side == "before":
        home.save_records()
    else:
        home.write(record, b"{not json")
    result = before.finish(60)
    reason = finding(result, home, record)["reason"]
    assert f"{record} could not be read {side}" in reason


def test_an_install_record_added_or_removed_holds(home):
    before = home.comparison()
    home.remove("installed_plugins.json")
    assert held(before.finish(60), home) == ["installed_plugins.json"]


# --- The run record and the entrance ------------------------------------

def test_released_changes_ride_the_run_record_and_the_entrance_reads_clear(home):
    before = home.comparison()
    release_fixture._upkeep(home)
    result = before.finish(60)
    assert kinds(result, home) == UPKEEP
    assert release_fixture.entrance(home, result) == {"status": "clear", "state": "clear", "owed": []}
    stored = json.loads((home.store / "launch.md.run.json").read_bytes())["launch_comparison"]
    assert stored["released"] == result["released"]


def test_a_record_from_before_still_holds_every_finding_until_an_account_counts(home):
    before = home.comparison()
    release_fixture._upkeep(home)
    old = release_fixture.recorded_before(before.finish(60))
    assert "released" not in old and len(old["findings"]) == len(UPKEEP)
    reading = release_fixture.entrance(home, old)
    assert reading["status"] == "held" and sorted(reading["owed"]) == sorted(f["id"] for f in old["findings"])
    account = tuple({"id": f["id"], "party": "plugin-update", "basis": "the runtime's upkeep"}
                    for f in old["findings"])
    assert release_fixture.entrance(home, old, account)["status"] == "clear"


# --- The use session's fixture driver -------------------------------------------

EXPECTED = {"upkeep": [], "update": [], "refresh": [],
            "stray-edit": [f"{WIDGET_V1}/lib/mod.py"], "repoint": ["installed_plugins.json"],
            "source": ["known_marketplaces.json"], "sourceless": [f"{WIDGET_V1}/lib/helper.pyc"],
            "new-plugin": [f"cache/{MARKET}/newcomer", "installed_plugins.json"],
            "recorded-before": sorted(UPKEEP)}


@pytest.mark.parametrize("name", sorted(release_fixture.SCENARIOS))
def test_each_scenario_agrees_with_the_comparison_and_the_entrance(tmp_path, name):
    result = release_fixture.run(name, tmp_path)
    home = Home.__new__(Home)
    home.plugins = (tmp_path / "home" / ".claude" / "plugins").resolve()
    assert held(result["comparison"], home) == EXPECTED[name]
    assert result["entrance"]["status"] == ("held" if EXPECTED[name] else "clear")
    assert len(result["entrance"]["owed"]) == len(EXPECTED[name])


def test_the_driver_lists_and_runs_a_scenario_from_the_command_line(tmp_path):
    script = LIB / "tests" / "release_fixture.py"
    env = {**os.environ, "TMPDIR": str(tmp_path), "TEMP": str(tmp_path), "TMP": str(tmp_path)}
    listed = subprocess.run([sys.executable, "-B", str(script), "--list"], capture_output=True, check=True,
                            stdin=subprocess.DEVNULL, env=env)
    assert [line.split(":")[0] for line in listed.stdout.decode("utf-8").splitlines()] == \
        list(release_fixture.SCENARIOS)
    shown = subprocess.run([sys.executable, "-B", str(script), "repoint"], capture_output=True, check=True,
                           stdin=subprocess.DEVNULL, env=env).stdout.decode("utf-8")
    assert '"released"' in shown and "The entrance reads this launch as: held" in shown
    assert str(tmp_path) not in shown and list(tmp_path.glob("release-fixture-*")) == []


def test_a_finished_records_findings_classify_by_name_with_install_records_holding(home):
    before = home.comparison()
    release_fixture._upkeep(home)
    release_fixture._update(home)
    old = release_fixture.recorded_before(before.finish(60))
    released = launch_release.classify_recorded(old["findings"], old["coverage"])
    kept = sorted(rel(home, finding) for index, finding in enumerate(old["findings"]) if index not in released)
    assert kept == sorted(["installed_plugins.json", "known_marketplaces.json",
                           f"marketplaces/{MARKET}/.claude-plugin/marketplace.json"])
