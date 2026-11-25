"""Which changes in the plugins folder a launch comparison releases.

Every session's runtime keeps some files in the plugins folder up at moments no
launch controls, and updates installed plugins whole. A change of one of those
kinds is released: recorded under its kind, never a finding. Only the two
plugin install records are read for their contents. Nothing here does I/O but
``read_install_records``.
Design: lib/DESIGN.md#what-a-launch-comparison-releases
"""
from __future__ import annotations

import json
import os
from pathlib import Path

RELEASING_ITEMS = frozenset({"plugins", "launcher-plugin"})
MARKETPLACES = "known_marketplaces.json"
INSTALLED = "installed_plugins.json"
INSTALL_RECORDS = (MARKETPLACES, INSTALLED)
# Only these fields decide which plugin code loads and where its updates come from, so time
# fields, which the app rewrites at every refresh, and every other field are ignored.
MARKETPLACE_FIELDS = ("source", "installLocation")
ENTRY_FIELDS = ("scope", "projectPath", "installPath", "version")


def _fold(text: str, windows: bool) -> str:
    return text.casefold() if windows else text


def _normal(path: str, windows: bool) -> str:
    """Slashes forward with no trailing one, and case folded where the platform folds it."""
    return _fold(str(path).replace("\\", "/").rstrip("/"), windows)


def _relative(path: str, top: str, windows: bool) -> list[str] | None:
    """The change's path as names below the item's top, or None when it lies elsewhere.

    Compared name by name, because case folding can change a name's length.
    """
    names = str(path).replace("\\", "/").rstrip("/").split("/")
    base = str(top).replace("\\", "/").rstrip("/").split("/")
    if len(names) <= len(base) or [_fold(name, windows) for name in names[:len(base)]]             != [_fold(name, windows) for name in base]:
        return None
    return names[len(base):]


# --- The upkeep files and whole version folders, by kind -----------------------

def _kind(item: str, parts: list[str], entry: str | None, windows: bool) -> str | None:
    """The upkeep kind for one path, first match first; ``entry`` is "dir", "file", "link" or unknown."""
    names = [_fold(name, windows) for name in parts]
    last, parent = names[-1], names[-2] if len(names) > 1 else None
    plugins = item == "plugins"

    def is_dir():
        return entry in {None, "dir"}

    def is_file():
        return entry in {None, "file"}

    # Python checks a .pyc in __pycache__ against its source and rebuilds it; one elsewhere can load
    # with no source to check, so it holds.
    if (last == "__pycache__" and is_dir()) or (
            parent == "__pycache__" and last.endswith(".pyc") and is_file()):
        return "bytecode"
    if plugins and names[0] == "synced":
        return "synced-marketplaces"
    if (last == ".in_use" and is_dir()) or (parent == ".in_use" and is_file()) or (
            last == ".last_inuse_sweep" and is_file()):
        return "in-use-marker"
    if last == ".orphaned_at" and is_file():
        return "orphan-marker"
    if plugins and names[0] == "store" and (
            (len(names) == 1 and is_dir()) or (len(names) == 2 and last.endswith(".json") and is_file())):
        return "usage-queue"
    # By prefix, so a renamed catalog version (``-v2``, ``-v3``) still releases.
    if plugins and len(names) == 1 and last.startswith("plugin-directory-cache") and last.endswith(".json") \
            and is_file():
        return "catalog-cache"
    return None


def _version_folders(changes: list[dict], tops: dict[str, str], windows: bool,
                     entry_of=None) -> tuple[set[str], set[str]]:
    """The version folders ``cache/<marketplace>/<plugin>/<version>`` added and removed whole."""
    added, removed = set(), set()
    top = tops.get("plugins")
    if top is None:
        return added, removed
    for change in changes:
        if change["item"] != "plugins" or change["change"] not in {"added", "removed"}:
            continue
        parts = _relative(change["path"], top, windows)
        if parts is None or len(parts) != 4 or _fold(parts[0], windows) != "cache":
            continue
        if entry_of is not None and entry_of(change) not in {None, "dir"}:
            continue
        (added if change["change"] == "added" else removed).add(_normal(change["path"], windows))
    return added, removed


def _inside(path: str, folders: set[str], windows: bool) -> bool:
    folded = _normal(path, windows)
    parts = folded.split("/")
    return any("/".join(parts[:count]) in folders for count in range(len(parts), 0, -1))


# --- The install records, by what they say -----------------------------------

def read_install_records(top: Path) -> dict[str, dict]:
    """Each install record at the plugins folder's top, parsed, or why it couldn't be."""
    readings = {}
    for name in INSTALL_RECORDS:
        try:
            readings[name] = {"value": json.loads(Path(top, name).read_bytes())}
        except FileNotFoundError:
            readings[name] = {"reason": "absent"}
        except (OSError, UnicodeError, ValueError) as exc:
            readings[name] = {"reason": f"{type(exc).__name__}: {exc}"}
    return readings


def _text(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _marketplaces(reading: dict | None, side: str) -> tuple[dict | None, str | None]:
    if not isinstance(reading, dict) or "value" not in reading:
        return None, f"{MARKETPLACES} could not be read {side}: " + str((reading or {}).get("reason")
                                                                        or "no reading was taken")
    value = reading["value"]
    if not isinstance(value, dict) or not all(isinstance(entry, dict) for entry in value.values()):
        return None, f"{MARKETPLACES} could not be read {side}: not an object of marketplaces"
    return value, None


def _plugins(reading: dict | None, side: str) -> tuple[dict | None, str | None]:
    if not isinstance(reading, dict) or "value" not in reading:
        return None, f"{INSTALLED} could not be read {side}: " + str((reading or {}).get("reason")
                                                                     or "no reading was taken")
    value = reading["value"]
    plugins = value.get("plugins") if isinstance(value, dict) else None
    if not isinstance(plugins, dict) or not all(
            isinstance(entries, list) and all(isinstance(entry, dict) for entry in entries)
            for entries in plugins.values()):
        return None, f"{INSTALLED} could not be read {side}: no object of plugin entry lists"
    return plugins, None


def _marketplace_differences(before: dict, after: dict) -> list[str]:
    differences = []
    for name in sorted(set(before) | set(after)):
        if name not in after:
            differences.append(f"marketplace {name} removed")
        elif name not in before:
            differences.append(f"marketplace {name} added")
        else:
            for field in MARKETPLACE_FIELDS:
                old, new = before[name].get(field), after[name].get(field)
                if _text(old) != _text(new):
                    differences.append(f"marketplace {name} {field} {_text(old)} -> {_text(new)}")
    return differences


def _entry(value: dict) -> tuple:
    return tuple(_text(value.get(field)) for field in ENTRY_FIELDS)


def _plugin_differences(before: dict, after: dict, added_folders: set[str], windows: bool
                        ) -> tuple[list[str], list[str]]:
    """Each listed difference, and the new install paths when every one is an update to an added folder."""
    differences, updates, releasable = [], [], True
    for key in sorted(set(before) | set(after)):
        if key not in after:
            differences.append(f"plugin {key} removed")
            releasable = False
            continue
        if key not in before:
            differences.append(f"plugin {key} added")
            releasable = False
            continue
        old = {_entry(entry): entry for entry in before[key]}
        new = {_entry(entry): entry for entry in after[key]}
        gone = [old[entry] for entry in sorted(set(old) - set(new))]
        came = [new[entry] for entry in sorted(set(new) - set(old))]
        pairs = []
        for entry in list(gone):
            # Paired, so an update reads as one entry's move and a held change names the field that moved:
            # by scope and project, or, when one entry left and one came, those two.
            same = [other for other in came if (other.get("scope"), other.get("projectPath"))
                    == (entry.get("scope"), entry.get("projectPath"))]
            if len(same) == 1 and sum((other.get("scope"), other.get("projectPath"))
                                      == (entry.get("scope"), entry.get("projectPath")) for other in gone) == 1:
                pairs.append((entry, same[0]))
                gone.remove(entry)
                came.remove(same[0])
        if len(gone) == 1 and len(came) == 1:
            pairs.append((gone.pop(), came.pop()))
        for entry in gone:
            differences.append(f"plugin {key} entry removed {_text({f: entry.get(f) for f in ENTRY_FIELDS})}")
            releasable = False
        for entry in came:
            differences.append(f"plugin {key} entry added {_text({f: entry.get(f) for f in ENTRY_FIELDS})}")
            releasable = False
        for old_entry, new_entry in pairs:
            changed = [field for field in ENTRY_FIELDS if _text(old_entry.get(field)) != _text(new_entry.get(field))]
            where = (f"plugin {key} entry scope {_text(old_entry.get('scope'))} "
                     f"projectPath {_text(old_entry.get('projectPath'))}")
            differences += [f"{where} {field} {_text(old_entry.get(field))} -> {_text(new_entry.get(field))}"
                            for field in changed]
            path = new_entry.get("installPath")
            if set(changed) != {"version", "installPath"} or not isinstance(path, str) \
                    or _normal(path, windows) not in added_folders:
                releasable = False
            else:
                updates.append(path)
    return differences, (updates if releasable else [])


def _install_record(name: str, before: dict | None, after: dict | None, added_folders: set[str],
                    windows: bool) -> tuple[str | None, str]:
    """``(basis, "")`` when a modified install record is released, else ``(None, reason)``."""
    read = _marketplaces if name == MARKETPLACES else _plugins
    first, fault = read((before or {}).get(name), "before")
    second, later = read((after or {}).get(name), "after")
    if fault or later:
        return None, "; ".join(value for value in (fault, later) if value)
    if name == MARKETPLACES:
        differences = _marketplace_differences(first, second)
        if not differences:
            return "no listed field changed", ""
        return None, f"{name}: " + "; ".join(differences)
    differences, updates = _plugin_differences(first, second, added_folders, windows)
    if not differences:
        return "no listed field changed", ""
    if updates:
        return "update to " + ", ".join(sorted(set(updates))), ""
    return None, f"{name}: " + "; ".join(differences)


def _refreshed(name: str, before: dict | None, after: dict | None, windows: bool) -> bool:
    """Whether marketplace ``name``'s refresh time moved between two readings that both parsed."""
    first, fault = _marketplaces((before or {}).get(MARKETPLACES), "before")
    second, later = _marketplaces((after or {}).get(MARKETPLACES), "after")
    if fault or later:
        return False
    old = next((value for key, value in first.items() if _fold(key, windows) == _fold(name, windows)), None)
    new = next((value for key, value in second.items() if _fold(key, windows) == _fold(name, windows)), None)
    return old is not None and new is not None and _text(old.get("lastUpdated")) != _text(new.get("lastUpdated"))


# --- The two callers ------------------------------------------------------------

def classify(changes: list[dict], tops: dict[str, str], *, records: tuple[dict, dict] | None = None,
             entry_of=None, windows: bool = os.name == "nt", check=None
             ) -> tuple[dict[int, dict], dict[int, str]]:
    """Each released change's kind and basis by index, and a reason for each held install-record change.

    ``changes`` are ``{"item", "path", "change"}`` with absolute paths, and ``tops`` each
    item's top. ``records`` are the install records' readings before and after; without
    them an install record or a marketplace clone holds. ``entry_of(change)`` names a
    change's entry type where it is known.
    """
    released: dict[int, dict] = {}
    reasons: dict[int, str] = {}
    added, removed = _version_folders(changes, tops, windows, entry_of)
    whole = added | removed
    before, after = records if records is not None else (None, None)
    for index, change in enumerate(changes):
        if check is not None:
            check()
        item = change["item"]
        if item not in RELEASING_ITEMS or change["change"] not in {"added", "removed", "modified"} \
                or tops.get(item) is None:
            continue
        parts = _relative(change["path"], tops[item], windows)
        if not parts:
            continue
        kind = _kind(item, parts, entry_of(change) if entry_of is not None else None, windows)
        if kind is None and whole and _inside(change["path"], whole, windows):
            kind = "version-folder"
        if kind is not None:
            released[index] = {"kind": kind}
            continue
        if item != "plugins":
            continue
        name = _fold(parts[0], windows)
        if len(parts) == 1 and name in {_fold(record, windows) for record in INSTALL_RECORDS} \
                and change["change"] == "modified":
            record = MARKETPLACES if name == _fold(MARKETPLACES, windows) else INSTALLED
            if records is None:
                continue
            basis, reason = _install_record(record, before, after, added, windows)
            if basis is not None:
                released[index] = {"kind": "install-record", "basis": basis}
            else:
                reasons[index] = reason
        elif name == "marketplaces" and len(parts) >= 2 and records is not None \
                and _refreshed(parts[1], before, after, windows):
            released[index] = {"kind": "marketplace-refresh",
                               "basis": f"marketplace {parts[1]} lastUpdated moved"}
    return released, reasons


def release(plan: list[dict], changes: list[dict], before: dict, after: dict, *,
            windows: bool = os.name == "nt", check=None) -> tuple[dict[int, dict], dict[int, str]]:
    """``classify`` over one live comparison: its plan's tops, its snapshots' entries and install records."""
    tops = {item["item"]: item["path"] for item in plan if item["item"] in RELEASING_ITEMS}
    records = ((before.get("plugins") or {}).get("install_records"),
               (after.get("plugins") or {}).get("install_records"))

    def entry_of(change):
        top = tops.get(change["item"])
        parts = _relative(change["path"], top, windows) if top else None
        if not parts:
            return None
        key = "/".join(parts)
        kinds = set()
        for state in (before.get(change["item"]) or {}, after.get(change["item"]) or {}):
            value = (state.get("entries") or {}).get(key)
            if isinstance(value, tuple) and value:
                kinds.add(value[0])
        return kinds.pop() if len(kinds) == 1 else (None if not kinds else "mixed")

    return classify(changes, tops, records=records, entry_of=entry_of, windows=windows, check=check)


def classify_recorded(findings: list[dict], coverage: list[dict], *, windows: bool = os.name == "nt"
                      ) -> dict[int, dict]:
    """Which of one recorded launch's findings the rules release, read from its record alone.

    For measuring the rules against finished records, as a replay across recorded launches
    does; neither the comparison nor the entrance calls it, and no record is reread to
    release its hold. The record keeps no install record's contents, so those and
    marketplace clones hold, and no entry type, so names alone decide.
    """
    tops = {entry["item"]: entry["path"] for entry in coverage
            if isinstance(entry, dict) and entry.get("item") in RELEASING_ITEMS and entry.get("path")}
    changes = [{"item": str(finding.get("item") or ""), "path": str(finding.get("path") or ""),
                "change": finding.get("change")} for finding in findings]
    released, _reasons = classify(changes, tops, windows=windows)
    return released
