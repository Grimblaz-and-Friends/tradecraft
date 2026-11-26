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
          f"cache/{MARKET}/{GADGET}/2.0.0/.orphaned_at": "orphan-marker",
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
        home.write(f"{WIDGET_V1}/lib/fresh.py", b"FRESH = 1\n")
        return home.path(WIDGET_V1)
    top = home.base / "launcher-checkout"
    # Seeded with the folders an installed version has, so only the files added during the run change.
    home.write("lib/mod.py", b"VALUE = 1\n", top=top)
    home.write("lib/fresh.py", b"FRESH = 1\n", top=top)
    home.compile("lib/mod.py", "lib/__pycache__/mod.cpython-312.pyc", top=top)
    home.write(".in_use/4101", b"{}", top=top)
    return top


def launcher_upkeep(home, top):
    home.compile("lib/fresh.py", "lib/__pycache__/fresh.cpython-312.pyc", top=top)
    home.write(".in_use/7303", b"{}", top=top)
    if top != home.path(WIDGET_V1):
        # The app marks only a version no install entry names, so a marker on the installed one holds (below).
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
                                                 f"{WIDGET_V1}/.in_use/7303": "in-use-marker"}
                                                if where == "installed" else {})}
    own = {Path(entry["path"]).relative_to(launcher).as_posix(): entry["kind"]
           for entry in result["released"] if entry["item"] == "launcher-plugin"}
    expected = {"lib/__pycache__/fresh.cpython-312.pyc": "bytecode", ".in_use/7303": "in-use-marker"}
    if where == "installed":
        expected.update({"lib/__pycache__/util.cpython-312.pyc": "bytecode", ".in_use/5202": "in-use-marker"})
    else:
        expected[".orphaned_at"] = "orphan-marker"
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


@pytest.mark.parametrize("separator, windows", [("/", False), ("/", True), ("\\", True)])
def test_paths_read_alike_with_either_separator_where_both_separate(separator, windows):
    top = separator.join(["", "fixture", "home", ".claude", "plugins"])

    def change(path, kind="added"):
        return {"item": "plugins", "path": top + separator + path.replace("/", separator), "change": kind}

    changes = [change(f"{WIDGET_V1}/lib/__pycache__/x.pyc"), change(f"{WIDGET_V1}/.in_use/9"),
               change("synced/a/.marketplaces.json", "modified"), change("store/q.json", "modified"),
               change("plugin-directory-cache-v3.json", "modified"), change(f"{GADGET_V3}/.orphaned_at"),
               change(f"{WIDGET_V1}/lib/x.pyc"), change(f"data/{WIDGET}/x.json"),
               change(f"cache/{MARKET}/{GADGET}/4.0.0"), change(f"cache/{MARKET}/{GADGET}/4.0.0/p.json")]
    released, _reasons = launch_release.classify(changes, {"plugins": top}, windows=windows)
    assert {index: value["kind"] for index, value in released.items()} == {
        0: "bytecode", 1: "in-use-marker", 2: "synced-marketplaces", 3: "usage-queue", 4: "catalog-cache",
        5: "orphan-marker", 8: "version-folder", 9: "version-folder"}


def test_a_name_with_backslashes_is_one_name_where_backslash_does_not_separate():
    top = "/fixture/home/.claude/plugins"
    decoy = top + "/cache\\acme-market\\widget\\1.0.0"
    edit = top + f"/{WIDGET_V1}/lib/mod.py"
    changes = [{"item": "plugins", "path": decoy, "change": "added"},
               {"item": "plugins", "path": edit, "change": "modified"}]
    released, _reasons = launch_release.classify(changes, {"plugins": top}, windows=False)
    assert released == {}


def test_a_version_folder_matches_the_launchers_root_through_a_linked_plugins_folder():
    top, real = "/home/u/.claude/plugins", "/data/dotfiles/claude/plugins"
    changes = [{"item": "plugins", "path": top + f"/{GADGET_V3}", "change": "removed"},
               {"item": "launcher-plugin", "path": real + f"/{GADGET_V3}/lib/mod.py", "change": "removed"}]
    tops = {"plugins": top, "launcher-plugin": real + f"/{GADGET_V3}"}
    unresolved, _reasons = launch_release.classify(changes, tops, windows=False)
    resolved, _reasons = launch_release.classify(changes, tops, windows=False, real_top=real)
    assert 1 not in unresolved and resolved[1] == {"kind": "version-folder"}


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
    # The update moves the plugin's entry with it; a version removed while an entry names it holds (below).
    home.installed["plugins"][f"{plugin}@{MARKET}"] = [home.entry(plugin, new)]
    home.save_records("installed_plugins.json")


def test_a_version_swap_releases_everything_under_both_folders(home):
    before = home.comparison()
    swap(home)
    result = before.finish(60)
    assert result["findings"] == []
    released = {path: kind for path, kind in kinds(result, home).items() if path.startswith("cache/")}
    assert released and set(released.values()) == {"version-folder"}
    assert {path.split("/")[3] for path in released} == {"3.0.0", "4.0.0"}


def test_a_swap_of_the_launchers_own_version_holds_nothing(home):
    launcher = home.path(GADGET_V3)
    home.write(".in_use/4101", b"{}", top=launcher)
    home.write("lib/m.py", b"M = 1\n", top=launcher)
    home.compile("lib/m.py", "lib/__pycache__/m.cpython-312.pyc", top=launcher)
    before = home.comparison(launcher)
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


def test_a_move_into_another_plugins_new_version_folder_holds(home):
    before = home.comparison()
    home.write(f"cache/{MARKET}/{GADGET}/9.9.9/.claude-plugin/plugin.json", b"{}")
    home.installed["plugins"][f"{WIDGET}@{MARKET}"] = [
        {**home.entry(WIDGET, "9.9.9"), "installPath": str(home.path(f"cache/{MARKET}/{GADGET}/9.9.9"))}]
    home.save_records()
    reason = finding(before.finish(60), home, "installed_plugins.json")["reason"]
    assert f"{WIDGET}@{MARKET}" in reason and "installPath" in reason and "9.9.9" in reason


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
    home.save_records("installed_plugins.json")
    result = before.finish(60)
    assert result["findings"] == []
    assert {rel(home, entry): entry["kind"] for entry in result["released"]} == {
        "installed_plugins.json": "install-record"}


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


def test_an_install_record_turned_into_a_link_holds_and_is_never_read_through(home, tmp_path):
    target = tmp_path / "elsewhere.json"
    target.write_bytes(home.path("installed_plugins.json").read_bytes())
    before = home.comparison()
    home.remove("installed_plugins.json")
    try:
        os.symlink(target, home.path("installed_plugins.json"))
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"this machine can't make a link: {exc}")
    result = before.finish(60)
    assert "installed_plugins.json" in held(result, home)
    readings = launch_release.read_install_records(home.plugins)
    assert "not a regular file" in readings["installed_plugins.json"]["reason"]


def test_an_install_record_that_is_not_a_regular_file_or_nests_too_deep_is_a_reason(home, monkeypatch):
    home.remove("known_marketplaces.json")
    home.path("known_marketplaces.json").mkdir()
    # How deep the parser goes before RecursionError follows the platform's stack, so the error is
    # raised here rather than reached by nesting.
    parse = launch_release.json.loads

    def too_deep(data):
        if data.startswith(b"[[["):
            raise RecursionError("maximum recursion depth exceeded")
        return parse(data)

    monkeypatch.setattr(launch_release.json, "loads", too_deep)
    home.write("installed_plugins.json", b"[[[]]]")
    readings = launch_release.read_install_records(home.plugins)
    assert "not a regular file" in readings["known_marketplaces.json"]["reason"]
    assert readings["installed_plugins.json"]["reason"].startswith("RecursionError")


def test_an_install_record_added_or_removed_holds(home):
    before = home.comparison()
    home.remove("installed_plugins.json")
    assert held(before.finish(60), home) == ["installed_plugins.json"]


# --- A version an install entry still names, removed or marked, holds ----------------

GADGET_V2 = f"cache/{MARKET}/{GADGET}/2.0.0"
GADGET_FILES = [GADGET_V3, f"{GADGET_V3}/.claude-plugin", f"{GADGET_V3}/.claude-plugin/plugin.json"]
NAMED_BY = f'plugin {GADGET}@{MARKET} entry scope "user" projectPath null'


def unname(home, key=f"{GADGET}@{MARKET}"):
    """A home whose install record no longer names the plugin ``key`` names, before the launch begins."""
    home.installed["plugins"].pop(key)
    home.save_records("installed_plugins.json")


def test_a_removed_version_an_entry_names_holds_saying_so_and_one_none_names_releases(home, tmp_path):
    before = home.comparison()
    release_fixture._installed_removed(home)
    result = before.finish(60)
    assert held(result, home) == GADGET_FILES
    assert "version-folder" not in kinds(result, home).values()
    for entry in result["findings"]:
        assert entry["reason"] == (f"version folder {home.path(GADGET_V3)} removed while installed_plugins.json "
                                   f"still names it: {NAMED_BY}")

    other = Home(tmp_path / "unnamed")
    unname(other)
    before = other.comparison()
    release_fixture._installed_removed(other)
    result = before.finish(60)
    assert result["findings"] == []
    assert kinds(result, other) == dict.fromkeys(GADGET_FILES, "version-folder")


def test_a_removal_of_a_version_the_entry_moved_off_during_the_launch_releases(home):
    before = home.comparison()
    home.installed["plugins"][f"{GADGET}@{MARKET}"] = [home.entry(GADGET, "2.0.0")]
    home.save_records("installed_plugins.json")
    release_fixture._installed_removed(home)
    result = before.finish(60)
    # The entry's own move holds, to a folder no update added; the removal it left behind releases.
    assert held(result, home) == ["installed_plugins.json"]
    assert {path: kind for path, kind in kinds(result, home).items() if path.startswith("cache/")} \
        == dict.fromkeys(GADGET_FILES, "version-folder")


def test_a_removal_holds_where_only_the_second_of_a_keys_entries_names_it(home):
    home.installed["plugins"][f"{GADGET}@{MARKET}"] = [
        {**home.entry(GADGET, "2.0.0"), "scope": "project", "projectPath": "/work/one"}, home.entry(GADGET, "3.0.0")]
    home.save_records("installed_plugins.json")
    before = home.comparison()
    release_fixture._installed_removed(home)
    result = before.finish(60)
    assert held(result, home) == GADGET_FILES
    assert all(entry["reason"].endswith(NAMED_BY) for entry in result["findings"])


@pytest.mark.parametrize("change", ["added", "modified"])
def test_an_orphan_marker_on_a_named_version_holds_and_on_an_unnamed_one_releases(home, change):
    if change == "modified":
        home.write(f"{GADGET_V3}/.orphaned_at", b"1600000000")
        home.write(f"{GADGET_V2}/.orphaned_at", b"1600000000")
    before = home.comparison()
    release_fixture._marked_installed(home)
    home.write(f"{GADGET_V2}/.orphaned_at", b"1700000000")
    result = before.finish(60)
    assert held(result, home) == [f"{GADGET_V3}/.orphaned_at"]
    assert finding(result, home, f"{GADGET_V3}/.orphaned_at")["reason"] == (
        f"orphan marker {change} at the top of {home.path(GADGET_V3)}, which installed_plugins.json still "
        f"names: {NAMED_BY}")
    assert kinds(result, home) == {f"{GADGET_V2}/.orphaned_at": "orphan-marker"}


def test_an_orphan_marker_on_a_new_plugins_first_version_holds_and_on_an_updates_new_folder_releases(home):
    before = home.comparison()
    release_fixture._new_plugin(home)
    home.write(f"cache/{MARKET}/newcomer/1.0.0/.orphaned_at", b"1700000000")
    reason = finding(before.finish(60), home, f"cache/{MARKET}/newcomer/1.0.0/.orphaned_at")["reason"]
    assert f"plugin newcomer@{MARKET} entry" in reason

    before = home.comparison()
    release_fixture._update(home)
    home.write(f"cache/{MARKET}/{WIDGET}/2.0.0/.orphaned_at", b"1700000000")
    result = before.finish(60)
    assert result["findings"] == []
    assert kinds(result, home)[f"cache/{MARKET}/{WIDGET}/2.0.0/.orphaned_at"] == "orphan-marker"


@pytest.mark.parametrize("named", [True, False])
def test_the_launchers_own_version_removed_holds_in_its_item_while_an_entry_names_it(home, named):
    launcher = home.path(GADGET_V3)
    if not named:
        unname(home)
    before = home.comparison(launcher)
    release_fixture._installed_removed(home)
    result = before.finish(60)
    own = sorted(Path(entry["path"]).relative_to(launcher).as_posix()
                 for entry in result["findings"] if entry["item"] == "launcher-plugin")
    if named:
        assert own == [".claude-plugin", ".claude-plugin/plugin.json"]
        assert all(entry["reason"].endswith(NAMED_BY) for entry in result["findings"])
    else:
        assert result["findings"] == []


def test_an_install_record_unreadable_after_the_launch_holds_a_removal_and_says_why(home):
    before = home.comparison()
    home.remove(GADGET_V2)
    home.write("installed_plugins.json", b"{not json")
    result = before.finish(60)
    # Its in-use markers keep their own kind.
    assert held(result, home) == sorted([GADGET_V2, f"{GADGET_V2}/.claude-plugin",
                                         f"{GADGET_V2}/.claude-plugin/plugin.json", "installed_plugins.json"])
    reason = finding(result, home, GADGET_V2)["reason"]
    assert f"version folder {home.path(GADGET_V2)} removed and installed_plugins.json could not be read after" \
        in reason


def readings(plugins):
    return {"installed_plugins.json": {"value": {"version": 2, "plugins": plugins}},
            "known_marketplaces.json": {"value": {}}}


@pytest.mark.parametrize("separator, windows", [("/", False), ("/", True), ("\\", True)])
def test_a_named_version_is_matched_alike_with_either_separator_where_both_separate(separator, windows):
    top = separator.join(["", "fixture", "home", ".claude", "plugins"])

    def change(path, kind):
        return {"item": "plugins", "path": top + separator + path.replace("/", separator), "change": kind}

    changes = [change(GADGET_V3, "removed"), change(f"{GADGET_V3}/plugin.json", "removed"),
               change(f"{WIDGET_V1}/.orphaned_at", "added"), change(f"{GADGET_V2}/.orphaned_at", "added")]
    # The record names its paths with forward slashes, in another case where the platform folds case.
    path = "/fixture/home/.claude/plugins/" + (GADGET_V3.upper() if windows else GADGET_V3)
    widget = "/fixture/home/.claude/plugins/" + WIDGET_V1
    records = readings({}), readings({f"{GADGET}@{MARKET}": [{"scope": "user", "installPath": path}],
                                      f"{WIDGET}@{MARKET}": [{"scope": "user", "installPath": widget}]})
    released, reasons = launch_release.classify(changes, {"plugins": top}, records=records, windows=windows)
    assert released == {3: {"kind": "orphan-marker"}} and sorted(reasons) == [0, 1, 2]
    unnamed = readings({}), readings({})
    released, reasons = launch_release.classify(changes, {"plugins": top}, records=unnamed, windows=windows)
    assert sorted(released) == [0, 1, 2, 3] and reasons == {}


# --- A compiled file Python won't check against its source holds -------------------

UTIL_PYC = f"{WIDGET_V1}/lib/__pycache__/util.cpython-312.pyc"


@pytest.mark.parametrize("mode, holds", [("UNCHECKED_HASH", True), ("TIMESTAMP", False), ("CHECKED_HASH", False)])
def test_only_a_compiled_file_python_wont_check_holds(home, mode, holds):
    before = home.comparison()
    home.compile(f"{WIDGET_V1}/lib/util.py", UTIL_PYC, mode)
    result = before.finish(60)
    if holds:
        assert held(result, home) == [UTIL_PYC]
        assert "Python loads it without checking it against its source" in finding(result, home, UTIL_PYC)["reason"]
    else:
        assert result["findings"] == [] and kinds(result, home) == {UTIL_PYC: "bytecode"}


def rewrite_flags(path, flags):
    data = bytearray(path.read_bytes())
    data[4:8] = flags.to_bytes(4, "little")
    path.write_bytes(bytes(data))


@pytest.mark.parametrize("flags, reason", [(2, None), (4, "carries flags 4, which Python refuses")])
def test_a_flags_word_python_checks_releases_and_one_it_refuses_holds(home, flags, reason):
    before = home.comparison()
    rewrite_flags(home.compile(f"{WIDGET_V1}/lib/util.py", UTIL_PYC), flags)
    result = before.finish(60)
    if reason is None:
        assert result["findings"] == [] and kinds(result, home) == {UTIL_PYC: "bytecode"}
    else:
        assert held(result, home) == [UTIL_PYC] and reason in finding(result, home, UTIL_PYC)["reason"]


def test_a_compiled_file_too_short_for_a_header_holds_and_one_removed_releases(home):
    before = home.comparison()
    home.write(UTIL_PYC, b"\x00" * 8)
    home.remove(f"{WIDGET_V1}/lib/__pycache__/mod.cpython-312.pyc")
    result = before.finish(60)
    assert held(result, home) == [UTIL_PYC]
    assert finding(result, home, UTIL_PYC)["reason"] == (
        "compiled file's header could not be read: 8 bytes, fewer than the 16 a header takes")
    assert kinds(result, home) == {f"{WIDGET_V1}/lib/__pycache__/mod.cpython-312.pyc": "bytecode"}


@pytest.mark.parametrize("mode, holds", [("UNCHECKED_HASH", True), ("TIMESTAMP", False), ("CHECKED_HASH", False)])
def test_the_launchers_own_compiled_files_read_alike(home, mode, holds):
    launcher = launcher_at(home, "checkout")
    before = home.comparison(launcher)
    home.compile("lib/fresh.py", "lib/__pycache__/fresh.cpython-312.pyc", mode, top=launcher)
    result = before.finish(60)
    own = [entry for entry in result["findings"] + result["released"] if entry["item"] == "launcher-plugin"]
    assert len(own) == 1 and (own[0] in result["findings"]) == holds


def test_an_unchecked_compiled_file_releases_only_inside_an_updates_new_folder(home):
    before = home.comparison()
    release_fixture._update(home)
    new = f"cache/{MARKET}/{WIDGET}/2.0.0/lib/__pycache__/mod.cpython-312.pyc"
    home.compile(f"cache/{MARKET}/{WIDGET}/2.0.0/lib/mod.py", new, "UNCHECKED_HASH")
    result = before.finish(60)
    assert result["findings"] == [] and kinds(result, home)[new] == "bytecode"

    before = home.comparison()
    release_fixture._new_plugin(home)
    home.write(f"cache/{MARKET}/newcomer/1.0.0/lib/x.py", b"X = 1\n")
    first = f"cache/{MARKET}/newcomer/1.0.0/lib/__pycache__/x.cpython-312.pyc"
    home.compile(f"cache/{MARKET}/newcomer/1.0.0/lib/x.py", first, "UNCHECKED_HASH")
    assert first in held(before.finish(60), home)

    before = home.comparison()
    home.write(f"cache/{MARKET}/{GADGET}/4.0.0/lib/x.py", b"X = 1\n")
    stray = f"cache/{MARKET}/{GADGET}/4.0.0/lib/__pycache__/x.cpython-312.pyc"
    home.compile(f"cache/{MARKET}/{GADGET}/4.0.0/lib/x.py", stray, "UNCHECKED_HASH")
    assert held(before.finish(60), home) == [stray]


def test_a_header_gone_by_its_read_releases_and_one_that_fails_holds():
    top = "/fixture/home/.claude/plugins"
    changes = [{"item": "plugins", "path": top + f"/{WIDGET_V1}/lib/__pycache__/{name}.pyc", "change": "added"}
               for name in ("gone", "locked")]

    def header_of(change):
        if "gone" in change["path"]:
            raise FileNotFoundError("gone")
        raise PermissionError("denied")

    released, reasons = launch_release.classify(changes, {"plugins": top}, windows=False, header_of=header_of)
    assert released == {0: {"kind": "bytecode"}}
    assert reasons == {1: "compiled file's header could not be read: PermissionError: denied"}


# --- Changes a launch can make that still release ----------------------------------

def test_an_update_the_launch_makes_releases_with_the_update_named(home):
    before = home.comparison()
    release_fixture._update(home)
    result = before.finish(60)
    assert result["findings"] == []
    released = kinds(result, home)
    assert {path for path, kind in released.items() if kind == "version-folder"} >= {
        f"cache/{MARKET}/{WIDGET}/2.0.0", f"cache/{MARKET}/{WIDGET}/2.0.0/lib/mod.py", WIDGET_V1}
    basis = next(entry["basis"] for entry in result["released"] if rel(home, entry) == "installed_plugins.json")
    assert basis == "update to " + str(home.path(f"cache/{MARKET}/{WIDGET}/2.0.0"))


def test_a_retired_version_removed_with_its_in_use_markers_releases(home):
    before = home.comparison()
    release_fixture._retired_removed(home)
    result = before.finish(60)
    assert result["findings"] == []
    assert {path: kind for path, kind in kinds(result, home).items() if "/.in_use" in path} == {
        f"{GADGET_V2}/.in_use": "in-use-marker", f"{GADGET_V2}/.in_use/6101": "in-use-marker",
        f"{GADGET_V2}/.in_use/6102": "in-use-marker"}
    assert kinds(result, home)[GADGET_V2] == "version-folder"


def test_a_compiled_file_given_its_sources_time_and_size_releases_whatever_it_runs(home):
    source = home.path(f"{WIDGET_V1}/lib/util.py")
    other = home.base / "other.py"
    other.write_bytes(b"import os\nos.environ['PLANTED'] = '1'\n")
    before = home.comparison()
    path = home.compile(str(other), UTIL_PYC)
    data = bytearray(path.read_bytes())
    status = source.stat()
    data[8:16] = (int(status.st_mtime) & 0xFFFFFFFF).to_bytes(4, "little") + \
        (status.st_size & 0xFFFFFFFF).to_bytes(4, "little")
    path.write_bytes(bytes(data))
    result = before.finish(60)
    assert result["findings"] == [] and kinds(result, home) == {UTIL_PYC: "bytecode"}


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
            "recorded-before": sorted(UPKEEP),
            "installed-removed": [GADGET_V3, f"{GADGET_V3}/.claude-plugin", f"{GADGET_V3}/.claude-plugin/plugin.json"],
            "data-write": [f"data/{WIDGET}/state.json"], "retired-removed": [],
            "marked-installed": [f"{GADGET_V3}/.orphaned_at"],
            "unchecked-bytecode": [f"{WIDGET_V1}/lib/__pycache__/util.cpython-312.pyc"]}


@pytest.mark.parametrize("name", sorted(release_fixture.SCENARIOS))
def test_each_scenario_agrees_with_the_comparison_and_the_entrance(tmp_path, name):
    result = release_fixture.run(name, tmp_path)
    assert held(result["comparison"], result["home"]) == EXPECTED[name]
    assert result["entrance"]["status"] == ("held" if EXPECTED[name] else "clear")
    assert len(result["entrance"]["owed"]) == len(EXPECTED[name])


@pytest.mark.parametrize("name, says", [
    ("installed-removed", "removed while installed_plugins.json still names it: " + NAMED_BY),
    ("marked-installed", "which installed_plugins.json still names: " + NAMED_BY),
    ("unchecked-bytecode", "Python loads it without checking it against its source")])
def test_each_new_hold_reaches_the_entrance_with_its_reason(tmp_path, name, says):
    result = release_fixture.run(name, tmp_path)
    findings = result["comparison"]["findings"]
    assert findings and all(says in entry["reason"] for entry in findings)
    assert result["entrance"]["state"] == "account-required"
    assert sorted(result["entrance"]["owed"]) == sorted(entry["id"] for entry in findings)


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
