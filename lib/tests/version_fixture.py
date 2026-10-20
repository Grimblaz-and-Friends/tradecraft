"""Synthetic public GitHub records for version endpoint tests and consumer use.

No production guard is replaced. The transport records every requested effect.
"""
from __future__ import annotations

import base64
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.parse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import work
from winio import utf8_stdio

REPO = "example/product"
FORK = "contributor/product"
HEAD = "a" * 40
BASE = "c" * 40
ADVANCED = "d" * 40
MERGE_BASE = "b" * 40
PRODUCER = "fixture-holder"
SPEC = {"path": "package.json", "field": "release", "increment": "minor"}
RULES = {"schema_version": 1, "rules": [
    {"include": ["runtime/**", "package.json"], "exclude": ["runtime/tests/**"]},
    {"include": ["runtime/tests/delivery.py"], "exclude": []},
], "version": SPEC}


def blob(content):
    return {"type": "file", "encoding": "base64", "content": base64.b64encode(content).decode()}


def brief(risk="ordinary", lane="mechanical"):
    return ("<!-- tradecraft:affirmed-brief:v1 -->\n"
            "| Decision | Why | Builder |\n|---|---|---|\n"
            "| **1. Compare releases as three integers, so 2.10.0 exceeds 2.9.10.** | Deliver the required version. | Commit a CI test. |\n"
            "| **2. Inspect an isolated matching fixture with an unmoved release through the entrance.** | Exercise its report. | Return the inspect command, revision, result and limitation. |\n"
            "| **3. Make the generated version instruction usable by a fresh builder.** | A reader sets the required field. | Owe a fresh reader who identifies the target and retains a sufficient higher value. |\n"
            f"Review risk: {risk}\nReview lane: {lane}\n")


def fixture_state(*, version="2.9.9", base_version="2.9.9", files=None,
                  risk="ordinary", lane="mechanical", draft=True, pr=True, ref="main", fork=False,
                  merge_base_version=None):
    term = brief(risk, lane)
    texts = [term]
    if lane != "mechanical":
        artifact = "\n" + "\n".join("> " + line for line in term.splitlines()) + (
            "\nThe artifact describes the complete implementation decisions and their executable acceptance criteria.\n"
            "A1: A committed CI test distinguishes 2.10.0 from 2.9.10 numerically.\n"
            "A2: Inspect an isolated matching fixture with an unmoved release through the entrance; record command, revision, result and limitation.\n"
            "A3: A separate fresh reader identifies the target in the generated version instruction and retains a sufficient higher value.\n")
        texts += ["<!-- tradecraft:artifact:v1 status=draft -->" + artifact,
                  "<!-- tradecraft:artifact:v1 status=settled route=would -->\n"
                  "<!-- tradecraft:cold-verdict:v1 verdict=would staffing_status=qualified -->" + artifact,
                  "<!-- tradecraft:holder-reading:v1 result=no-amendment -->"]
    texts += [f"<!-- tradecraft:floor:v1 head={HEAD} status=pass -->",
              f"<!-- tradecraft:use:v1 head={HEAD} status=pass changed=false staffing_status=qualified -->"]
    comments = [{"id": index + 21, "body": text, "user": {"login": PRODUCER},
                 "created_at": f"2026-09-23T12:00:{index:02d}Z",
                 "html_url": f"https://github.com/{REPO}/issues/12#issuecomment-{index + 21}"}
                for index, text in enumerate(texts)]
    inventory = deepcopy(files if files is not None else [{"filename": "runtime/code.py", "status": "modified"}])
    pull = {"number": 7, "state": "open", "draft": draft, "merged_at": None, "mergeable": True,
            "mergeable_state": "clean", "node_id": "PR_fixture", "body": "Closes #12", "changed_files": len(inventory),
            "head": {"sha": HEAD, "ref": "change", "repo": {"full_name": FORK if fork else REPO, "id": 2}},
            # Deliberately historical: the current GET tip, not this SHA, is the basis.
            "base": {"ref": ref, "sha": "b" * 40, "repo": {"full_name": REPO, "id": 1}}}
    state = work.WorkState(REPO, 12, {"number": 12, "state": "open", "body": "",
                           "user": {"login": PRODUCER}}, issue_comments=comments, pr=pull if pr else None,
                           config=work.WorkConfig(marker_producers=frozenset({PRODUCER}), reviewer_label="reviewers"),
                           files=inventory, changed_paths=[item.get("filename", "") for item in inventory if isinstance(item, dict)])
    transport = RecordingGitHub(state, version=version, base_version=base_version,
                                merge_base_version=merge_base_version)
    return state, transport


class RecordingGitHub:
    def __init__(self, state, *, version="2.9.9", base_version="2.9.9", merge_base_version=None):
        self.state = state
        self.version = json.dumps({SPEC["field"]: version}).encode()
        self.base_version = json.dumps({SPEC["field"]: base_version}).encode()
        # The merge base the PR's three-dot file list is taken against.
        self.merge_base_version = json.dumps({SPEC["field"]: merge_base_version or base_version}).encode()
        self.base_sha = BASE
        self.merge_base_sha = MERGE_BASE
        self.labels = set()
        self.calls = []
        self.effects = []
        self.comments = []
        self.overrides = {}
        self.before_get = None
        self.after_effect = None
        corpus_path = Path(__file__).resolve().parents[2] / "skills" / "work" / "references" / "proof-fixtures" / "v1-ci-floor.json"
        self.floor_case = json.loads(corpus_path.read_bytes())["cases"][0]

    def get(self, endpoint, *, paginate=False):
        self.calls.append(("GET", endpoint, paginate))
        if self.before_get:
            self.before_get(endpoint)
        if endpoint in self.overrides:
            value = self.overrides[endpoint]
            if isinstance(value, Exception):
                raise value
            return deepcopy(value)
        prefix = f"repos/{REPO}"
        if endpoint == "user":
            return {"login": PRODUCER}
        if endpoint == prefix:
            return {"id": 1, "full_name": REPO, "default_branch": "main"}
        if "/git/ref/heads/" in endpoint:
            return {"object": {"sha": self.base_sha}}
        if "/contents/" in endpoint:
            if f"ref={self.base_sha}" in endpoint:
                return blob(json.dumps(self.floor_case["base_policy"]["content"]).encode()
                            if "/change-proof.json?" in endpoint else self.base_version)
            if f"ref={self.merge_base_sha}" in endpoint and endpoint.startswith(f"{prefix}/contents/"):
                return blob(self.merge_base_version)
            head = self.state.pr["head"]
            if endpoint.startswith(f"repos/{head['repo']['full_name']}/contents/") and f"ref={head['sha']}" in endpoint:
                return blob(self.version)
            raise work.WorkError(f"unexpected version source: {endpoint}")
        if "/compare/" in endpoint:
            return {"behind_by": 0, "merge_base_commit": {"sha": self.merge_base_sha}}
        if "/rules/branches/" in endpoint:
            return []
        if "/protection" in endpoint:
            return {}
        if endpoint == f"{prefix}/issues/12":
            return deepcopy(self.state.issue)
        if endpoint == f"{prefix}/issues/12/comments":
            return deepcopy(self.state.issue_comments)
        if "/pulls?" in endpoint:
            return [deepcopy(self.state.pr)] if self.state.pr else []
        if endpoint == f"{prefix}/pulls/7":
            return deepcopy(self.state.pr)
        if endpoint == f"{prefix}/pulls/7/files":
            assert paginate, "complete PR inventory must use pagination"
            return deepcopy(self.state.files)
        if endpoint == f"{prefix}/issues/7":
            return {"labels": [{"name": name} for name in sorted(self.labels)]}
        if endpoint == f"{prefix}/issues/7/comments":
            return deepcopy(self.comments)
        if "/actions/runs?" in endpoint:
            return deepcopy(self.floor_case["workflow_runs"][0])
        if endpoint.endswith("/actions/runs/91"):
            return deepcopy(self.floor_case["runs"][0]["record"])
        if "/actions/runs/91/jobs?" in endpoint:
            return deepcopy(self.floor_case["jobs"][0]["pages"][0])
        if "/check-runs?filter=all" in endpoint:
            return deepcopy(self.floor_case["check_runs"][0])
        if "/check-runs?" in endpoint:
            return {"check_runs": [], "total_count": 0}
        if endpoint.endswith(("/reviews", "/pulls/7/comments")):
            return []
        if "/issues/comments/" in endpoint:
            return deepcopy(next(item for item in self.comments if str(item["id"]) == endpoint.rsplit("/", 1)[-1]))
        raise work.WorkError(f"unexpected fixture GET: {endpoint}")

    def post(self, endpoint, payload):
        self.effects.append(("POST", endpoint, deepcopy(payload)))
        if endpoint.endswith("/labels"):
            self.labels.update(payload["labels"])
            result = [{"name": name} for name in sorted(self.labels)]
        elif endpoint.endswith("/comments"):
            result = {"id": 91 + len(self.comments), "body": payload["body"], "user": {"login": PRODUCER},
                      "html_url": f"https://github.com/{REPO}/issues/7#issuecomment-91"}
            self.comments.append(result)
        elif endpoint.endswith("/rerun"):
            result = {}
        else:
            raise work.WorkError(f"unexpected fixture POST: {endpoint}")
        if self.after_effect:
            self.after_effect(endpoint)
        return deepcopy(result)

    def patch(self, endpoint, payload):
        self.effects.append(("PATCH", endpoint, deepcopy(payload)))
        comment = next(item for item in self.comments if str(item["id"]) == endpoint.rsplit("/", 1)[-1])
        comment.update(payload)
        return deepcopy(comment)

    def graphql(self, query, variables):
        self.effects.append(("GRAPHQL", query, variables))
        self.state.pr["draft"] = False
        return {"data": {"markPullRequestReadyForReview": {"pullRequest": {"isDraft": False}}}}


def adopted_repository(root, rules=RULES):
    root.mkdir(parents=True, exist_ok=True)
    (root / ".github").mkdir()
    (root / ".tradecraft").mkdir()
    (root / ".github" / "change-proof.json").write_bytes(json.dumps(rules).encode() + b"\n")
    (root / ".tradecraft" / "work.json").write_bytes(json.dumps({"schema_version": 1,
        "product_repositories": [], "connected_reviewers": [], "marker_producers": [PRODUCER],
        "reviewer_label": "reviewers"}).encode() + b"\n")
    for command in (["init"], ["add", "/".join((".github", "change-proof.json")), ".tradecraft/work.json"],
                    ["-c", "user.name=fixture", "-c", "user.email=fixture@example.com", "commit", "-m", "Synthetic adopting policy"]):
        subprocess.run(["git", "-C", str(root), *command], stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return root / ".github" / "change-proof.json"


def _save_fixture(path, transport):
    state = transport.state
    payload = {"issue": state.issue, "issue_comments": state.issue_comments,
               "pr": state.pr, "files": state.files,
               "base_sha": transport.base_sha,
               "base_version": base64.b64encode(transport.base_version).decode(),
               "merge_base_sha": transport.merge_base_sha,
               "merge_base_version": base64.b64encode(transport.merge_base_version).decode(),
               "version": base64.b64encode(transport.version).decode(),
               "labels": sorted(transport.labels), "comments": transport.comments,
               "calls": transport.calls, "effects": transport.effects}
    path.write_bytes((json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n").encode())


def _load_fixture(path):
    data = json.loads(path.read_bytes())
    state = work.WorkState(REPO, 12, data["issue"], issue_comments=data["issue_comments"],
                           pr=data["pr"], files=data["files"])
    transport = RecordingGitHub(state)
    transport.base_sha = data["base_sha"]
    transport.base_version = base64.b64decode(data["base_version"])
    transport.merge_base_sha = data.get("merge_base_sha", MERGE_BASE)
    transport.merge_base_version = base64.b64decode(data.get("merge_base_version", data["base_version"]))
    transport.version = base64.b64decode(data["version"])
    transport.labels = set(data["labels"])
    transport.comments = data["comments"]
    transport.calls = data["calls"]
    transport.effects = data["effects"]
    return transport


class GitHubNotFound(Exception):
    """A stand-in 404, reported the way the gh executable reports one."""


def _gh_serve(transport, save):
    """Answer one `gh api` invocation from transport; no network request is possible here."""
    arguments = sys.argv[1:]
    if not arguments or arguments[0] != "api":
        raise SystemExit("fixture gh supports api only")
    arguments = arguments[1:]
    method = "GET"
    if "--method" in arguments:
        index = arguments.index("--method")
        method = arguments[index + 1]
        del arguments[index:index + 2]
    endpoint = arguments[0]
    try:
        if method == "GET":
            value = transport.get(endpoint, paginate="--paginate" in arguments)
            if "--slurp" in arguments:
                value = [value]
        else:
            payload = json.loads(sys.stdin.buffer.read())
            if endpoint == "graphql":
                value = transport.graphql(payload["query"], payload["variables"])
            elif method == "POST":
                value = transport.post(endpoint, payload)
            elif method == "PATCH":
                value = transport.patch(endpoint, payload)
            else:
                raise SystemExit("unsupported fixture method")
    except GitHubNotFound:
        save(transport)
        sys.stderr.write("gh: Not Found (HTTP 404)\n")
        raise SystemExit(1)
    save(transport)
    print(json.dumps(value, ensure_ascii=True))


def gh_main():
    """A deterministic gh executable over a stored record; no network request is possible here."""
    utf8_stdio()
    path = Path(os.environ["TRADECRAFT_VERSION_FIXTURE"])
    _gh_serve(_load_fixture(path), lambda transport: _save_fixture(path, transport))


def _install_gh(bin_path, entry):
    """Put a `gh` console launcher for entry on the consumer's PATH, on both CI OSes."""
    bin_path.mkdir()
    if os.name == "nt":
        # pip ships the same console launcher used by installed Python tools.
        from pip._vendor.distlib.scripts import ScriptMaker
        maker = ScriptMaker(None, str(bin_path))
        maker.executable = sys.executable
        maker.variants = {""}
        maker.make(f"gh = version_fixture:{entry}")
    else:
        launcher = bin_path / "gh"
        launcher.write_bytes((f"#!{sys.executable}\nfrom version_fixture import {entry}\n{entry}()\n").encode())
        launcher.chmod(0o755)


def setup_consumer(root, scenario):
    """Build an isolated adopting checkout and a recording gh on both CI OSes."""
    if root.exists():
        raise ValueError("consumer setup needs a new directory")
    if scenario == "catch-up":
        return setup_catch_up(root)
    files = [{"filename": "README.md" if scenario == "unrelated" else "runtime/code.py", "status": "modified"}]
    _, transport = fixture_state(files=files, version="2.10.0" if scenario == "repaired" else "2.9.9")
    adopted_repository(root)
    fixture_path = root / ".tradecraft" / "github-fixture.json"
    _save_fixture(fixture_path, transport)
    _install_gh(root / ".tradecraft" / "bin", "gh_main")
    return fixture_path


# The catch-up scenario: real local repositories behind a stand-in gh that
# answers from them as they stand at each call, so a commit the consumer pushes
# is what the next read sees. Everything lives under one new root:
#   origin.git      a throwaway bare origin
#   holder/         the adopting holder checkout on main
#   implementation/ the change branch, a worktree of holder/, registered by adopt
#   home/           USERPROFILE and HOME for every command the scenario names
#   github.json     the stand-in's issue, comments, labels and recorded effects
#   bin/            the stand-in gh
CATCH_UP_SPEC = {"path": "version.json", "field": "version", "increment": "minor"}
CATCH_UP_RULES = {"schema_version": 1, "rules": RULES["rules"], "version": CATCH_UP_SPEC}
CATCH_UP_BRANCH = "tradecraft/12-0123456789ab"
CATCH_UP_HOLDER_SESSION = "catch-up-fixture-holder"
CATCH_UP_LAB_PATH = "notes/change.md"
CATCH_UP_MARKER = "catch-up-scenario.json"
BUILDER_SESSION = "01234567-89ab-cdef-0123-456789abcdef"
PULL = 7


def catch_up_layout(root):
    root = Path(root)
    return {"origin": root / "origin.git", "holder": root / "holder",
            "implementation": root / "implementation", "home": root / "home",
            "state": root / "github.json", "bin": root / "bin"}


def _git(cwd, *arguments, check=True):
    result = subprocess.run(["git", "-C", str(cwd), *arguments], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode:
        raise RuntimeError(f"git {' '.join(arguments)}: {result.stderr.decode(errors='replace').strip()}")
    return result


def _git_text(cwd, *arguments):
    return _git(cwd, *arguments).stdout.decode("utf-8").strip()


def _write(root, path, content):
    target = Path(root) / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content.encode("utf-8"))


def _version_document(value):
    return json.dumps({"version": value, "name": "fixture"}, indent=2) + "\n"


class LiveGitHub:
    """Public GitHub records derived, at each call, from the scenario's bare origin."""

    def __init__(self, root):
        self.layout = catch_up_layout(root)
        self.origin = self.layout["origin"]
        self.data = json.loads(self.layout["state"].read_bytes())

    def save(self):
        self.layout["state"].write_bytes(
            (json.dumps(self.data, ensure_ascii=True, sort_keys=True, indent=1) + "\n").encode())

    def _revision(self, name):
        result = _git(self.origin, "rev-parse", "--verify", "--quiet", name, check=False)
        if result.returncode:
            raise GitHubNotFound(name)
        return result.stdout.decode().strip()

    def _files(self, left, right):
        files = []
        lines = _git_text(self.origin, "diff", "--name-status", "-M", left, right).splitlines()
        for line in lines:
            fields = line.split("\t")
            item = {"filename": fields[-1], "status": "renamed" if fields[0].startswith("R")
                    else {"A": "added", "D": "removed"}.get(fields[0], "modified")}
            if fields[0].startswith("R"):
                item["previous_filename"] = fields[1]
            files.append(item)
        return files

    def _compare(self, left, right):
        left, right = self._revision(left), self._revision(right)
        common = _git_text(self.origin, "merge-base", left, right)
        commits = _git_text(self.origin, "rev-list", "--reverse", f"{left}..{right}").splitlines()
        behind = int(_git_text(self.origin, "rev-list", "--count", f"{right}..{left}"))
        status = ("identical" if left == right else "ahead" if common == left
                  else "behind" if common == right else "diverged")
        return {"status": status, "ahead_by": len(commits), "behind_by": behind,
                "merge_base_commit": {"sha": common}, "commits": [{"sha": sha} for sha in commits],
                "files": self._files(common, right)}

    def pull(self):
        head = self._revision(f"refs/heads/{CATCH_UP_BRANCH}")
        base = self._revision("refs/heads/main")
        comparison = self._compare(base, head)
        mergeable = _git(self.origin, "merge-tree", "--write-tree", "--no-messages", base, head,
                         check=False).returncode == 0
        return {"number": PULL, "state": "open", "draft": self.data["draft"], "merged_at": None,
                "mergeable": mergeable,
                "mergeable_state": "dirty" if not mergeable else "behind" if comparison["behind_by"] else "clean",
                "node_id": "PR_catch_up_fixture", "body": "Closes #12",
                "changed_files": len(comparison["files"]),
                "head": {"sha": head, "ref": CATCH_UP_BRANCH, "repo": {"full_name": REPO, "id": 1}},
                "base": {"ref": "main", "sha": base, "repo": {"full_name": REPO, "id": 1}}}

    def get(self, endpoint, *, paginate=False):
        prefix = f"repos/{REPO}"
        if endpoint == "user":
            return {"login": PRODUCER}
        if endpoint == prefix:
            return {"id": 1, "full_name": REPO, "default_branch": "main"}
        if not endpoint.startswith(prefix + "/"):
            raise SystemExit(f"unexpected fixture GET: {endpoint}")
        suffix = endpoint[len(prefix) + 1:]
        if suffix.startswith("git/ref/heads/"):
            ref = urllib.parse.unquote(suffix.removeprefix("git/ref/heads/"))
            return {"object": {"sha": self._revision(f"refs/heads/{ref}")}}
        if suffix.startswith("compare/"):
            left, right = suffix.removeprefix("compare/").split("...")
            return self._compare(left, right)
        if suffix.startswith("commits/") and "/check-runs" in suffix:
            return {"check_runs": [], "total_count": 0}
        if suffix.startswith("commits/"):
            revision = self._revision(suffix.split("/", 1)[1].split("?")[0])
            parents = _git_text(self.origin, "show", "-s", "--format=%P", revision).split()
            return {"sha": revision, "parents": [{"sha": sha} for sha in parents],
                    "files": self._files(parents[0], revision) if parents else []}
        if suffix.startswith("contents/"):
            path, revision = suffix.removeprefix("contents/").split("?ref=")
            path = urllib.parse.unquote(path)
            result = _git(self.origin, "cat-file", "blob", f"{revision}:{path}", check=False)
            if result.returncode:
                raise GitHubNotFound(endpoint)
            return blob(result.stdout)
        if suffix.startswith("git/trees/"):
            revision = suffix.removeprefix("git/trees/").split("?")[0]
            entries = []
            for line in _git_text(self.origin, "ls-tree", revision).splitlines():
                identity, name = line.split("\t")
                mode, kind, sha = identity.split()
                entries.append({"path": name, "mode": mode, "type": kind, "sha": sha})
            return {"sha": revision, "truncated": False, "tree": entries}
        if suffix.startswith("git/blobs/"):
            content = _git(self.origin, "cat-file", "blob", suffix.rsplit("/", 1)[-1]).stdout
            return {"encoding": "base64", "content": base64.b64encode(content).decode()}
        if suffix.startswith("rules/branches/"):
            return []
        if suffix.startswith("branches/") and suffix.endswith("/protection"):
            # A strict base: a pull request behind main must catch up before it merges.
            return {"required_status_checks": {"strict": True, "contexts": []}}
        if suffix == "issues/12":
            return deepcopy(self.data["issue"])
        if suffix == "issues/12/comments":
            return deepcopy(self.data["issue_comments"])
        if suffix.startswith("pulls?"):
            return [self.pull()]
        if suffix == f"pulls/{PULL}":
            return self.pull()
        if suffix == f"pulls/{PULL}/files":
            pull = self.pull()
            return self._compare(pull["base"]["sha"], pull["head"]["sha"])["files"]
        if suffix in {f"pulls/{PULL}/reviews", f"pulls/{PULL}/comments"}:
            return []
        if suffix == f"issues/{PULL}":
            return {"labels": [{"name": name} for name in sorted(self.data["labels"])]}
        if suffix == f"issues/{PULL}/comments":
            return deepcopy(self.data["pull_comments"])
        if suffix.startswith("issues/comments/"):
            identity = int(suffix.rsplit("/", 1)[-1])
            return deepcopy(next(item for item in self.data["pull_comments"] if item["id"] == identity))
        if suffix.startswith("actions/runs"):
            return {"total_count": 0, "workflow_runs": []}
        raise SystemExit(f"unexpected fixture GET: {endpoint}")

    def post(self, endpoint, payload):
        self.data["effects"].append(["POST", endpoint, payload])
        if endpoint.endswith(f"/issues/{PULL}/labels"):
            self.data["labels"] = sorted(set(self.data["labels"]) | set(payload["labels"]))
            return [{"name": name} for name in self.data["labels"]]
        if endpoint.endswith(f"/issues/{PULL}/comments"):
            comment = {"id": 900 + len(self.data["pull_comments"]), "body": payload["body"],
                       "user": {"login": PRODUCER}, "created_at": "2026-10-20T12:00:00Z",
                       "html_url": f"https://github.com/{REPO}/pull/{PULL}#issuecomment-900"}
            self.data["pull_comments"].append(comment)
            return deepcopy(comment)
        if endpoint.endswith("/rerun"):
            return {}
        raise SystemExit(f"unexpected fixture POST: {endpoint}")

    def patch(self, endpoint, payload):
        self.data["effects"].append(["PATCH", endpoint, payload])
        identity = int(endpoint.rsplit("/", 1)[-1])
        comment = next(item for item in self.data["pull_comments"] if item["id"] == identity)
        comment.update(payload)
        return deepcopy(comment)

    def graphql(self, query, variables):
        self.data["effects"].append(["GRAPHQL", query, variables])
        self.data["draft"] = False
        return {"data": {"markPullRequestReadyForReview": {"pullRequest": {"isDraft": False}}}}


def gh_live_main():
    """A gh executable answering from the catch-up scenario's local repositories."""
    utf8_stdio()
    transport = LiveGitHub(Path(os.environ["TRADECRAFT_CATCH_UP_FIXTURE"]))
    _gh_serve(transport, lambda served: served.save())


def consumer_environment(root):
    """Confine a consumer command to the scenario: its gh, and a home inside the root."""
    root = Path(root)
    live = (root / CATCH_UP_MARKER).exists()
    home = catch_up_layout(root)["home"] if live else root / ".tradecraft" / "home"
    home.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["USERPROFILE"] = environment["HOME"] = str(home)
    environment.pop("HOMEDRIVE", None)
    environment.pop("HOMEPATH", None)
    if live:
        environment["TRADECRAFT_CATCH_UP_FIXTURE"] = str(root)
        bin_path = catch_up_layout(root)["bin"]
    else:
        environment["TRADECRAFT_VERSION_FIXTURE"] = str(root / ".tradecraft" / "github-fixture.json")
        bin_path = root / ".tradecraft" / "bin"
    environment["PATH"] = str(bin_path) + os.pathsep + environment.get("PATH", "")
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parent) + os.pathsep + environment.get("PYTHONPATH", "")
    return environment


def run_consumer(root, stage=None, extra=(), command=None):
    """Run the built entrance as a consumer would; extra carries a stage's own arguments."""
    root = Path(root)
    holder = catch_up_layout(root)["holder"] if (root / CATCH_UP_MARKER).exists() else root
    arguments = [command] if command else ["run", stage] if stage else []
    return subprocess.run([sys.executable, str(Path(work.__file__).resolve()), *arguments,
                           "--repo", REPO, "--issue", "12", "--root", str(holder), *extra],
                          env=consumer_environment(root), stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _builder_turn(root, transport):
    """Record the completed first build that produced the change branch.

    The scenario starts after a builder has returned, so the entrance's
    governing-terms comparison finds a delivered turn rather than an unproved one.
    """
    layout = catch_up_layout(root)
    state = work.read_state(transport, REPO, 12, work.WorkConfig(
        marker_producers=frozenset({PRODUCER}), reviewer_label="reviewers"))
    work.validate_marker_claims(state)
    folder = layout["home"] / ".tradecraft" / "dispatches" / "fixture-build"
    folder.mkdir(parents=True)
    prompt = b"Build the affirmed change on the registered branch.\n"
    context = b"One bounded stage.\n"
    (folder / "result.md.dispatch.bin").write_bytes(prompt)
    (folder / "result.md.context.bin").write_bytes(context)
    effective = hashlib.sha256(context + b"\n\n" + prompt).hexdigest()
    request = {"schema_version": 2, "dispatch_id": "fixture-build", "work": f"{REPO}#12", "stage": "build",
               "producer_version": work.records.producer_version(),
               "root": str(layout["implementation"].resolve()), "lineage_branch": CATCH_UP_BRANCH,
               "lineage_pull_request": PULL, "launched_at": "2026-10-20T11:00:30Z",
               "input": str(folder / "result.md.dispatch.bin"),
               "context": {"path": str(folder / "result.md.context.bin")},
               "effective_input_sha256": effective,
               "prompt_composition": {
                   "origin": "entrance", "composed_at": "2026-10-20T11:00:00Z",
                   "dispatch_sha256": hashlib.sha256(prompt).hexdigest(),
                   "effective_input_sha256": effective,
                   "sources": [work._governing_identity(marker) for marker in work._governing_sources(state)]},
               "requested": {"vendor": "codex", "session_id": BUILDER_SESSION, "continuity": "fresh"}}
    run = {"schema_version": 2, "dispatch_id": "fixture-build", "actual_vendor": "codex",
           "completed_at": "2026-10-20T11:30:00Z", "outcome": "success", "lifecycle": "completed",
           "revision_after": state.pr["head"]["sha"],
           "attempts": [{"launched": True, "elapsed_seconds": 1, "observed": {"session_id": BUILDER_SESSION}}]}
    (folder / "result.md.request.json").write_bytes(work.records.json_bytes(request))
    (folder / "result.md.run.json").write_bytes(work.records.json_bytes(run))


def setup_catch_up(root):
    """Build the catch-up scenario: a lab-only change whose base has since moved its version."""
    root = Path(root)
    layout = catch_up_layout(root)
    root.mkdir(parents=True)
    _git(root, "init", "--bare", "--initial-branch=main", str(layout["origin"]))
    holder, implementation = layout["holder"], layout["implementation"]
    holder.mkdir()
    _git(holder, "init", "--initial-branch=main")
    for key, value in (("user.name", "Fixture Holder"), ("user.email", "fixture@example.test"),
                       ("core.autocrlf", "false"), ("commit.gpgsign", "false")):
        _git(holder, "config", key, value)
    _write(holder, "/".join((".github", "change-proof.json")), json.dumps(CATCH_UP_RULES, indent=2) + "\n")
    _write(holder, ".tradecraft/work.json", json.dumps({
        "schema_version": 1, "product_repositories": [], "connected_reviewers": [],
        "marker_producers": [PRODUCER], "reviewer_label": "reviewers"}, indent=2) + "\n")
    _write(holder, "version.json", _version_document("1.3.0"))
    _write(holder, "runtime/code.py", "VALUE = 1\n")
    _write(holder, CATCH_UP_LAB_PATH, "Notes before the change.\n")
    _git(holder, "add", "--", ".")
    _git(holder, "commit", "-m", "Merge base: version 1.3.0")
    _git(holder, "remote", "add", "origin", str(layout["origin"]))
    _git(holder, "push", "-u", "origin", "main")
    # The change branch starts at the merge base and touches only a path no use rule matches.
    _git(holder, "worktree", "add", "-b", CATCH_UP_BRANCH, str(implementation), "main")
    _write(implementation, CATCH_UP_LAB_PATH, "Notes the change rewrote.\n")
    _git(implementation, "commit", "-am", "Rewrite the notes")
    _git(implementation, "push", "-u", "origin", CATCH_UP_BRANCH)
    # Main moves on: the base bumps the declared version.
    _write(holder, "version.json", _version_document("1.4.0"))
    _git(holder, "commit", "-am", "Base moves the version to 1.4.0")
    _git(holder, "push", "origin", "main")
    comments = [
        {"id": 31, "body": brief(), "user": {"login": PRODUCER}, "created_at": "2026-10-20T10:00:00Z",
         "html_url": f"https://github.com/{REPO}/issues/12#issuecomment-31"},
        {"id": 32, "body": f"<!-- tradecraft:implementing-pr:v1 number={PULL} -->",
         "user": {"login": PRODUCER}, "created_at": "2026-10-20T10:00:01Z",
         "html_url": f"https://github.com/{REPO}/issues/12#issuecomment-32"},
    ]
    layout["state"].write_bytes((json.dumps({
        "issue": {"number": 12, "state": "open", "body": "", "user": {"login": PRODUCER}},
        "issue_comments": comments, "pull_comments": [], "labels": [], "draft": True, "effects": [],
    }, indent=1) + "\n").encode())
    (root / CATCH_UP_MARKER).write_bytes((json.dumps({
        "holder_session_id": CATCH_UP_HOLDER_SESSION, "branch": CATCH_UP_BRANCH}) + "\n").encode())
    _install_gh(layout["bin"], "gh_live_main")
    adopted = run_consumer(root, command="adopt", extra=(
        "--implementation-root", str(implementation), "--holder-session-id", CATCH_UP_HOLDER_SESSION))
    if adopted.returncode:
        raise RuntimeError("adopt failed: " + adopted.stderr.decode(errors="replace") + adopted.stdout.decode(errors="replace"))
    _builder_turn(root, LiveGitHub(root))
    return root


def main(argv=None):
    utf8_stdio()
    parser = argparse.ArgumentParser(description="Set up and run isolated version entrance consumer fixtures.")
    parser.add_argument("command", choices=["setup", "inspect", "catch-up", "ready-reviewers", "proof",
                                            "effects", "prompts"])
    parser.add_argument("root", type=Path)
    parser.add_argument("--scenario", choices=["blocked", "repaired", "unrelated", "catch-up"], default="blocked")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.command == "setup":
        setup_consumer(root, args.scenario)
        report = {"root": str(root), "scenario": args.scenario}
        if args.scenario == "catch-up":
            layout = catch_up_layout(root)
            report.update(holder=str(layout["holder"]), implementation=str(layout["implementation"]),
                          home=str(layout["home"]), branch=CATCH_UP_BRANCH,
                          holder_session_id=CATCH_UP_HOLDER_SESSION)
        print(json.dumps(report, ensure_ascii=True))
        return 0
    if args.command == "effects":
        if (root / CATCH_UP_MARKER).exists():
            effects = LiveGitHub(root).data["effects"]
        else:
            effects = _load_fixture(root / ".tradecraft" / "github-fixture.json").effects
        print(json.dumps({"effects": effects}, ensure_ascii=True, indent=2))
        return 0
    if args.command == "prompts":
        for lane in ("mechanical", "connected"):
            state, transport = fixture_state(lane=lane, pr=False)
            instruction = work._compose_version_instruction(state, transport, RULES, "synthetic policy")
            prompt = work._stage_prompt(state, work.Decision("build", True, "fresh", "fixture"),
                                       version_instruction=instruction)
            (root / (lane + "-prompt.txt")).write_bytes(prompt)
        print("Generated mechanical-prompt.txt and connected-prompt.txt in the named root.")
        return 0
    extra = ()
    if args.command == "catch-up":
        if not (root / CATCH_UP_MARKER).exists():
            raise SystemExit("catch-up needs a root set up with --scenario catch-up")
        extra = ("--holder-session-id", CATCH_UP_HOLDER_SESSION)
    result = run_consumer(root, None if args.command == "inspect" else args.command, extra)
    sys.stdout.buffer.write(result.stdout)
    sys.stderr.buffer.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
