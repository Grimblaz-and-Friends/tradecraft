"""Public Git history for the entrance and gate's agreed ancestor-use rule."""
from __future__ import annotations

import base64
import re
import urllib.parse

import version_policy


SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


class History:
    def __init__(self, transport, repo, rules):
        self.transport, self.repo = transport, repo
        self.spec = version_policy.declaration(rules)
        self.cache = {}

    def get(self, endpoint, paginate=False):
        if endpoint not in self.cache:
            self.cache[endpoint] = self.transport.get(endpoint, paginate=paginate)
        return self.cache[endpoint]

    def commit(self, revision):
        value = self.get(f"repos/{self.repo}/commits/{revision}?per_page=100", True)
        pages = value if isinstance(value, list) else [value]
        if not pages:
            raise ValueError("complete commit file list is unavailable")
        files = [item for page in pages for item in page["files"]]
        if len(files) >= 3000:
            raise ValueError("complete commit file list is unavailable")
        raw = pages[0].get("parents")
        parents = None
        if isinstance(raw, list) and all(isinstance(item, dict) and isinstance(item.get("sha"), str)
                                        and SHA.fullmatch(item["sha"]) for item in raw):
            revisions = tuple(item["sha"] for item in raw)
            if len(set(revisions)) == len(revisions):
                parents = revisions
        paths = sorted({item[key] for item in files for key in ("filename", "previous_filename")
                        if isinstance(item.get(key), str)})
        return paths, files, parents

    def base_reachable(self, revision, base):
        if revision == base:
            return True
        try:
            comparison = self.get(f"repos/{self.repo}/compare/{revision}...{base}")
            return (comparison.get("status") in {"ahead", "identical"}
                    and comparison.get("merge_base_commit", {}).get("sha") == revision)
        except (KeyError, TypeError, OSError, UnicodeError, ValueError, RuntimeError):
            return False

    def merge_brought_paths(self, parents, base):
        brought = set()
        for parent in parents[1:]:
            if not self.base_reachable(parent, base):
                continue
            comparison = self.get(f"repos/{self.repo}/compare/{parents[0]}...{parent}")
            common = comparison.get("merge_base_commit", {}).get("sha")
            if not isinstance(common, str) or SHA.fullmatch(common) is None:
                raise ValueError("complete merge-side file list is unavailable")
            side = self.get(f"repos/{self.repo}/compare/{common}...{parent}")
            files = side.get("files")
            if not isinstance(files, list) or len(files) >= 300:
                raise ValueError("complete merge-side file list is unavailable")
            brought.update(item[key] for item in files for key in ("filename", "previous_filename")
                           if isinstance(item.get(key), str))
        return brought

    def version_only(self, revision, files, parents):
        if self.spec is None or not parents:
            return False
        path = self.spec["path"]
        matching = [item for item in files if any(isinstance(item.get(key), str)
                    and item[key].replace("\\", "/") == path for key in ("filename", "previous_filename"))]
        if (len(matching) != 1 or matching[0].get("status") != "modified"
                or "previous_filename" in matching[0]):
            return False
        contents = []
        try:
            for commit in (parents[0], revision):
                quoted = urllib.parse.quote(path, safe="/")
                value = self.get(f"repos/{self.repo}/contents/{quoted}?ref={commit}")
                if value.get("encoding") != "base64" or not isinstance(value.get("content"), str):
                    return False
                contents.append(base64.b64decode("".join(value["content"].split()), validate=True))
            return version_policy.only_version(contents[0], contents[1], self.spec)
        except (KeyError, TypeError, OSError, UnicodeError, ValueError, RuntimeError):
            return False


def application(transport, repo, ancestor, head, base, rules, buys, changed_paths):
    graph = History(transport, repo, rules)
    interval = graph.get(f"repos/{repo}/compare/{ancestor}...{head}")
    report = {"applicable": False, "evidence_head": ancestor, "current_head": head,
              "observed_base": base, "intervening_commits": [], "incoming_commits": [],
              "merge_commits": []}
    if (interval.get("status") not in {"ahead", "identical"}
            or interval.get("merge_base_commit", {}).get("sha") != ancestor):
        return {**report, "reason": "use evidence head is not an ancestor"}
    commits = interval.get("commits")
    if (not isinstance(commits, list) or type(interval.get("ahead_by")) is not int
            or interval["ahead_by"] != len(commits)):
        return {**report, "reason": "complete intervening history is unavailable"}
    changed = {path.replace("\\", "/") for path in changed_paths}
    report["changed_paths"] = sorted(changed)
    invalid = []
    for item in commits:
        revision = item.get("sha")
        if not isinstance(revision, str) or SHA.fullmatch(revision) is None:
            return {**report, "reason": "intervening commit has no full revision"}
        paths, files, parents = graph.commit(revision)
        bought = {path for path in paths if buys([path], rules)}
        report["intervening_commits"].append({"sha": revision, "paths": paths})
        if not bought:
            continue
        merge = parents is not None and len(parents) > 1
        if merge:
            brought = set(paths) & graph.merge_brought_paths(parents, base)
            own = bought - brought
            incoming = bought & brought
            report["merge_commits"].append({"sha": revision, "brought_paths": sorted(brought),
                                             "own_paths": sorted(set(paths) - brought)})
        elif graph.base_reachable(revision, base):
            incoming, own = bought, set()
        else:
            incoming, own = set(), bought
        if incoming:
            overlap = {path for path in incoming if path.replace("\\", "/") in changed}
            if (graph.spec and graph.spec["path"] in {path.replace("\\", "/") for path in overlap}
                    and graph.version_only(revision, files, parents)):
                overlap = {path for path in overlap if path.replace("\\", "/") != graph.spec["path"]}
            report["incoming_commits"].append({"sha": revision, "paths": sorted(incoming),
                                               "overlap": sorted(overlap), "origin": "merge" if merge else "base"})
            if overlap:
                invalid.append(f"commit {revision} overlaps use-bought paths: {', '.join(sorted(overlap))}")
        if own:
            invalid.append(f"authored {'merge edit' if merge else 'commit'} {revision} changes use-bought paths: {', '.join(sorted(own))}")
    return {**report, "applicable": not invalid, "carried": not invalid,
            "reason": "; ".join(invalid) if invalid else "authored work buys no new use; base commits and brought merge paths have no use-bought overlap"}
