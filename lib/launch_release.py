"""Which changes in the plugins folder a launch comparison releases.

Every session's runtime keeps some files in the plugins folder up at moments no
launch controls, and updates installed plugins whole. A change of one of those
kinds is released: recorded under its kind, never a finding. Only the two
plugin install records are read for their contents, and a changed compiled file for its
header. Nothing here does I/O but ``read_install_records`` and ``release``'s resolving of
the plugins folder's real path and reading of those headers.
Design: lib/DESIGN.md#what-a-launch-comparison-releases
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat

# The runtime keeps files up only in the plugins folder and the launcher's own plugin root; a
# registered checkout is a change's tree, whose every write the comparison exists to catch.
RELEASING_ITEMS = frozenset({"plugins", "launcher-plugin"})
MARKETPLACES = "known_marketplaces.json"
INSTALLED = "installed_plugins.json"
INSTALL_RECORDS = (MARKETPLACES, INSTALLED)
# Only these fields decide which plugin code loads and where its updates come from, so time
# fields, which the app rewrites at every refresh, and every other field are ignored.
MARKETPLACE_FIELDS = ("source", "installLocation")
ENTRY_FIELDS = ("scope", "projectPath", "installPath", "version")
HEADER_BYTES = 16
HASH_BASED, CHECK_SOURCE = 0b01, 0b10
# Flags with no hash bit are checked by time and size, so CHECK_SOURCE alone is checked as no flags are.
CHECKED_FLAGS = frozenset({0, CHECK_SOURCE, HASH_BASED | CHECK_SOURCE})


def _fold(text: str, windows: bool) -> str:
    return text.casefold() if windows else text


def _slashed(path: str, windows: bool) -> str:
    """Separators forward with no trailing one; a backslash separates only on Windows, being part of
    a name elsewhere, so a folder named with backslashes can't pass for a path."""
    return (str(path).replace("\\", "/") if windows else str(path)).rstrip("/")


def _normal(path: str, windows: bool) -> str:
    """The form every path comparison here shares, case folded where the platform folds names."""
    return _fold(_slashed(path, windows), windows)


def _relative(path: str, top: str, windows: bool) -> list[str] | None:
    """The change's path as names below the item's top, or None when it lies elsewhere.

    Compared name by name, because case folding can change a name's length.
    """
    names = _slashed(path, windows).split("/")
    base = _slashed(top, windows).split("/")
    if len(names) <= len(base) or [_fold(name, windows) for name in names[:len(base)]] \
            != [_fold(name, windows) for name in base]:
        return None
    return names[len(base):]


# --- The upkeep files and whole version folders, by kind -----------------------

def _kind(item: str, parts: list[str], entry: str | None, windows: bool) -> str | None:
    """The upkeep kind for one path, first match first.

    ``entry`` is "dir", "file", "link", None where unknown, or "mixed" where the type changed
    between the snapshots, which no type-gated kind releases, because the runtime's upkeep
    never turns a folder into a file or a link.
    """
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
    # The app's sync folder holds account data, never plugin code that loads, so all of it releases.
    if plugins and names[0] == "synced" and (len(names) > 1 or is_dir()):
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
                     entry_of=None, real_top: str | None = None
                     ) -> tuple[list[tuple[str, frozenset[str]]], list[tuple[str, frozenset[str]]]]:
    """The version folders ``cache/<marketplace>/<plugin>/<version>`` added and removed whole.

    Each is its path as the walk recorded it, with its forms: that path and the same folder
    under ``real_top``, the plugins folder's resolved path, because the launcher's own root is
    resolved and may reach the same folder through a link.
    """
    added, removed = [], []
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
        side = added if change["change"] == "added" else removed
        side.append((change["path"], frozenset(_forms(change["path"], top, real_top, windows))))
    return added, removed


def _forms(path: str, top: str | None, real_top: str | None, windows: bool) -> set[str]:
    """``path`` as the plugins folder's top reaches it and as its resolved path does."""
    forms = {_normal(path, windows)}
    for base, other in ((top, real_top), (real_top, top)):
        if base is not None and other is not None:
            parts = _relative(path, base, windows)
            if parts:
                forms.add(_normal(other + "/" + "/".join(parts), windows))
    return forms


def _within(path: str, folders: dict[str, str], windows: bool) -> str | None:
    """The value of the folder in ``folders`` that ``path`` is at or under, or None."""
    parts = _normal(path, windows).split("/")
    for count in range(len(parts), 0, -1):
        found = folders.get("/".join(parts[:count]))
        if found is not None:
            return found
    return None


def _inside(path: str, folders: set[str], windows: bool) -> bool:
    return _within(path, dict.fromkeys(folders, ""), windows) is not None


def _parent(path: str, windows: bool) -> str:
    """The folder ``path`` is in, as the walk recorded it."""
    path = path.rstrip("/\\" if windows else "/")
    cut = max(path.rfind("/"), path.rfind("\\") if windows else -1)
    return path[:cut] if cut > 0 else path


# --- What the app's own upkeep never makes ------------------------------------

def _named(reading: dict | None, top: str | None, real_top: str | None, windows: bool
           ) -> tuple[dict[str, str] | None, str | None]:
    """Each path an entry of ``installed_plugins.json`` after the launch installs from, with that
    entry, or why that reading can't say.

    The app retires a version only once no entry names it, so a named version removed or marked
    for retirement is never its work.
    """
    plugins, fault = _plugins(reading, "after")
    if fault:
        return None, fault
    named: dict[str, str] = {}
    for key in sorted(plugins):
        for entry in plugins[key]:
            path = entry.get("installPath")
            if isinstance(path, str) and path:
                for form in _forms(path, top, real_top, windows):
                    named.setdefault(form, f"plugin {key} entry scope {_text(entry.get('scope'))} "
                                           f"projectPath {_text(entry.get('projectPath'))}")
    return named, None


def _header(header_of, change: dict) -> str | None:
    """Why a compiled file added or changed in a ``__pycache__`` folder holds, or None when it releases.

    An import writes only a file Python checks against its source; one built to skip that check
    loads whatever its source says, so it holds.
    """
    try:
        header = header_of(change)
    except FileNotFoundError:
        return None  # Gone since the walk, so nothing is left to load, as with a compiled file removed.
    except (OSError, ValueError) as exc:
        return f"compiled file's header could not be read: {type(exc).__name__}: {exc}"
    if len(header) < HEADER_BYTES:
        return (f"compiled file's header could not be read: {len(header)} bytes, fewer than the "
                f"{HEADER_BYTES} a header takes")
    flags = int.from_bytes(header[4:8], "little")
    if flags == HASH_BASED:
        return ("compiled file's header marks it unchecked (flags 1): Python loads it without checking "
                "it against its source")
    if flags not in CHECKED_FLAGS:
        # Python compiles the source again rather than load it, but it is none of the kinds Python checks.
        return f"compiled file's header carries flags {flags}, which Python refuses"
    return None


# --- The install records, by what they say -----------------------------------

def _regular_bytes(path: Path, limit: int = -1) -> bytes:
    """A regular file's bytes, or its first ``limit``; a link, a pipe or any other entry is refused,
    never followed or waited on.

    A link would let an install record's contents change behind an entry the walk sees as
    unchanged, or point a compiled file's read at another file than the one walked; a pipe would
    stall either read past the allowance.
    """
    if not stat.S_ISREG(os.lstat(path).st_mode):
        raise ValueError("not a regular file")
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError("not a regular file")
        return handle.read(limit)


def read_install_records(top: Path) -> dict[str, dict]:
    """Each install record at the plugins folder's top, parsed, or why it couldn't be."""
    readings = {}
    for name in INSTALL_RECORDS:
        try:
            readings[name] = {"value": json.loads(_regular_bytes(Path(top, name)))}
        except FileNotFoundError:
            readings[name] = {"reason": "absent"}
        except (OSError, RecursionError, UnicodeError, ValueError) as exc:
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


def _pair(gone: list[dict], came: list[dict]) -> list[tuple[dict, dict]]:
    """Each entry that left matched with the one that replaced it, taking both out of their lists.

    Pairing lets an update read as one entry's move, which can release, and lets a held change
    name the field that moved. A plugin is installed once per scope and project, so those two
    identify an entry; an entry pairs only where it and its match are the only ones with that
    scope and project, since several can't be told apart. Failing that, when one entry left and
    one came, they are one entry whose scope or project moved.
    """
    def identity(entry):
        return entry.get("scope"), entry.get("projectPath")

    pairs = []
    for entry in list(gone):
        same = [other for other in came if identity(other) == identity(entry)]
        if len(same) == 1 and sum(identity(other) == identity(entry) for other in gone) == 1:
            pairs.append((entry, same[0]))
            gone.remove(entry)
            came.remove(same[0])
    if len(gone) == 1 and len(came) == 1:
        pairs.append((gone.pop(), came.pop()))
    return pairs


def _own_folder(key: str, path: str, windows: bool) -> bool:
    """Whether ``path`` is a version folder of the plugin ``key`` names (``<plugin>@<marketplace>``).

    An update moves a plugin to its own new version; an entry moved into another plugin's
    folder changes what that plugin loads, so it holds.
    """
    plugin, _, marketplace = key.rpartition("@")
    names = _normal(path, windows).split("/")
    return len(names) >= 3 and names[-3:-1] == [_fold(marketplace, windows), _fold(plugin, windows)]


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
        pairs = _pair(gone, came)
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
                    or _normal(path, windows) not in added_folders or not _own_folder(key, path, windows):
                releasable = False
            else:
                updates.append(path)
    return differences, (updates if releasable else [])


def _install_record(name: str, before: dict | None, after: dict | None, added_folders: set[str],
                    windows: bool) -> tuple[str | None, str, list[str]]:
    """``(basis, "", updated install paths)`` when a modified install record is released, else
    ``(None, reason, [])``."""
    read = _marketplaces if name == MARKETPLACES else _plugins
    first, fault = read((before or {}).get(name), "before")
    second, later = read((after or {}).get(name), "after")
    if fault or later:
        return None, "; ".join(value for value in (fault, later) if value), []
    if name == MARKETPLACES:
        differences = _marketplace_differences(first, second)
        if not differences:
            return "no listed field changed", "", []
        return None, f"{name}: " + "; ".join(differences), []
    differences, updates = _plugin_differences(first, second, added_folders, windows)
    if not differences:
        return "no listed field changed", "", []
    if updates:
        return "update to " + ", ".join(sorted(set(updates))), "", updates
    return None, f"{name}: " + "; ".join(differences), []


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

def _record(change: dict, top: str | None, windows: bool) -> str | None:
    """The install record a modified change in the plugins folder is, or None."""
    if change["item"] != "plugins" or change["change"] != "modified" or top is None:
        return None
    parts = _relative(change["path"], top, windows)
    if not parts or len(parts) != 1:
        return None
    return next((record for record in INSTALL_RECORDS if _fold(record, windows) == _fold(parts[0], windows)), None)


def _version_shaped(path: str, top: str | None, real_top: str | None, windows: bool) -> bool:
    for base in (top, real_top):
        parts = _relative(path, base, windows) if base is not None else None
        if parts and len(parts) == 4 and _fold(parts[0], windows) == "cache":
            return True
    return False


def _marker(change: dict, named: dict[str, str] | None, fault: str | None, top: str | None,
            real_top: str | None, windows: bool) -> str | None:
    """Why an orphan marker added or changed at the top of a version an entry names holds, or None.

    The app marks a version for retirement only once no entry names it.
    """
    parent = _parent(change["path"], windows)
    if fault:
        if not _version_shaped(parent, top, real_top, windows):
            return None
        return (f"orphan marker {change['change']} at the top of version folder {parent} and {fault}, "
                "so nothing shows that no entry names it")
    entry = next((named[form] for form in sorted(_forms(parent, top, real_top, windows)) if form in named), None)
    if entry is None:
        return None
    return f"orphan marker {change['change']} at the top of {parent}, which {INSTALLED} still names: {entry}"


def classify(changes: list[dict], tops: dict[str, str], *, records: tuple[dict, dict] | None = None,
             entry_of=None, windows: bool = os.name == "nt", check=None, real_top: str | None = None,
             header_of=None) -> tuple[dict[int, dict], dict[int, str]]:
    """Each released change's kind and basis by index, and a reason for each held change the rules read.

    ``changes`` are ``{"item", "path", "change"}`` with absolute paths, and ``tops`` each
    item's top. ``records`` are the install records' readings before and after; without
    them an install record or a marketplace clone holds, and a removed version folder or an
    orphan marker is judged by its name alone. ``entry_of(change)`` names a change's entry
    type where it is known. ``header_of(change)`` reads a compiled file's first bytes; without
    it a compiled file in a ``__pycache__`` folder is judged by its name alone.
    """
    released: dict[int, dict] = {}
    reasons: dict[int, str] = {}
    added, removed = _version_folders(changes, tops, windows, entry_of, real_top)
    added_paths = {form for _path, forms in added for form in forms}
    before, after = records if records is not None else (None, None)
    top = tops.get("plugins")
    # The install records first, because an update's new folder is exempt from the rules below.
    decided: dict[int, tuple[str | None, str]] = {}
    updated: set[str] = set()
    for index, change in enumerate(changes):
        record = _record(change, top, windows)
        if record is None or records is None:
            continue
        if entry_of is not None and entry_of(change) != "file":
            # A record turned into a link or anything else holds, whatever it reads as.
            decided[index] = (None, f"{record} is not a regular file before and after")
            continue
        basis, reason, moved = _install_record(record, before, after, added_paths, windows)
        decided[index] = (basis, reason)
        updated |= {_normal(path, windows) for path in moved}
    # Later sessions load an update's new folder whole, whatever the launch put in it, so holding part of it
    # would stop nothing; everything in it releases as the update does.
    new_folders = {form for _path, forms in added if forms & updated for form in forms}
    named, fault = _named((after or {}).get(INSTALLED), top, real_top, windows) if records is not None \
        else ({}, None)
    # The app retires a version only once no entry names it, so a named version removed holds; where the
    # after-reading failed, nothing shows that no entry names it.
    whole, held = set(added_paths), {}
    for path, forms in removed:
        entry = next((named[form] for form in sorted(forms) if form in named), None) if named else None
        if fault:
            held.update(dict.fromkeys(forms, f"version folder {path} removed and {fault}, "
                                             "so nothing shows that no entry names it"))
        elif entry is not None:
            held.update(dict.fromkeys(forms, f"version folder {path} removed while {INSTALLED} still names it: "
                                             f"{entry}"))
        else:
            whole |= forms
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
        reason = None
        if kind is None:
            reason = _within(change["path"], held, windows)
            if reason is None and whole and _inside(change["path"], whole, windows):
                kind = "version-folder"
        # A marker or a compiled file removed takes nothing from what loads, so neither is checked.
        elif change["change"] != "removed" and not _inside(change["path"], new_folders, windows):
            if kind == "orphan-marker" and records is not None:
                reason = _marker(change, named, fault, top, real_top, windows)
            elif kind == "bytecode" and header_of is not None and _fold(parts[-1], windows).endswith(".pyc"):
                reason = _header(header_of, change)
                if check is not None:
                    check()  # The only read here, and a slow disk can spend the allowance on it.
        if reason is not None:
            reasons[index] = reason
            continue
        if kind is not None:
            released[index] = {"kind": kind}
            continue
        if item != "plugins":
            continue
        name = _fold(parts[0], windows)
        if _record(change, top, windows) is not None:
            if index not in decided:
                continue
            basis, reason = decided[index]
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

    def header_of(change):
        return _regular_bytes(Path(change["path"]), HEADER_BYTES)

    real_top = os.path.realpath(tops["plugins"]) if "plugins" in tops else None
    return classify(changes, tops, records=records, entry_of=entry_of, windows=windows, check=check,
                    real_top=real_top, header_of=header_of)


def classify_recorded(findings: list[dict], coverage: list[dict], *, windows: bool = os.name == "nt"
                      ) -> dict[int, dict]:
    """Which of one recorded launch's findings the rules release, read from its record alone.

    For measuring the rules against finished records, as a replay across recorded launches
    does; neither the comparison nor the entrance calls it, and no record is reread to
    release its hold. The record keeps no install record's contents, so those and
    marketplace clones hold, and a removed version folder or an orphan marker releases by its
    name whether or not an entry names it; it keeps no entry type or compiled file, so names
    alone decide.
    """
    tops = {entry["item"]: entry["path"] for entry in coverage
            if isinstance(entry, dict) and entry.get("item") in RELEASING_ITEMS and entry.get("path")}
    changes = [{"item": str(finding.get("item") or ""), "path": str(finding.get("path") or ""),
                "change": finding.get("change")} for finding in findings]
    released, _reasons = classify(changes, tops, windows=windows)
    return released
