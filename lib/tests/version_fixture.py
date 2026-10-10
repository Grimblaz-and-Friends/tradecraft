"""Synthetic public GitHub records for version endpoint tests and consumer use.

No production guard is replaced. The transport records every requested effect.
"""
from __future__ import annotations

import base64
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import work
from winio import utf8_stdio

REPO = "example/product"
FORK = "contributor/product"
HEAD = "a" * 40
BASE = "c" * 40
ADVANCED = "d" * 40
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
                  risk="ordinary", lane="mechanical", draft=True, pr=True, ref="main", fork=False):
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
            "node_id": "PR_fixture", "body": "Closes #12", "changed_files": len(inventory),
            "head": {"sha": HEAD, "ref": "change", "repo": {"full_name": FORK if fork else REPO, "id": 2}},
            # Deliberately historical: the current GET tip, not this SHA, is the basis.
            "base": {"ref": ref, "sha": "b" * 40, "repo": {"full_name": REPO, "id": 1}}}
    state = work.WorkState(REPO, 12, {"number": 12, "state": "open", "body": "",
                           "user": {"login": PRODUCER}}, issue_comments=comments, pr=pull if pr else None,
                           config=work.WorkConfig(marker_producers=frozenset({PRODUCER}), reviewer_label="reviewers"),
                           files=inventory, changed_paths=[item.get("filename", "") for item in inventory if isinstance(item, dict)])
    transport = RecordingGitHub(state, version=version, base_version=base_version)
    return state, transport


class RecordingGitHub:
    def __init__(self, state, *, version="2.9.9", base_version="2.9.9"):
        self.state = state
        self.version = json.dumps({SPEC["field"]: version}).encode()
        self.base_version = json.dumps({SPEC["field"]: base_version}).encode()
        self.base_sha = BASE
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
            head = self.state.pr["head"]
            if endpoint.startswith(f"repos/{head['repo']['full_name']}/contents/") and f"ref={head['sha']}" in endpoint:
                return blob(self.version)
            raise work.WorkError(f"unexpected version source: {endpoint}")
        if "/compare/" in endpoint:
            return {"behind_by": 0}
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
    transport.version = base64.b64decode(data["version"])
    transport.labels = set(data["labels"])
    transport.comments = data["comments"]
    transport.calls = data["calls"]
    transport.effects = data["effects"]
    return transport


def gh_main():
    """A deterministic gh executable; no network request is possible here."""
    utf8_stdio()
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
    path = Path(os.environ["TRADECRAFT_VERSION_FIXTURE"])
    transport = _load_fixture(path)
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
    _save_fixture(path, transport)
    print(json.dumps(value, ensure_ascii=True))


def setup_consumer(root, scenario):
    """Build an isolated adopting checkout and a recording gh on both CI OSes."""
    if root.exists():
        raise ValueError("consumer setup needs a new directory")
    files = [{"filename": "README.md" if scenario == "unrelated" else "runtime/code.py", "status": "modified"}]
    _, transport = fixture_state(files=files, version="2.10.0" if scenario == "repaired" else "2.9.9")
    adopted_repository(root)
    fixture_path = root / ".tradecraft" / "github-fixture.json"
    _save_fixture(fixture_path, transport)
    bin_path = root / ".tradecraft" / "bin"
    bin_path.mkdir()
    if os.name == "nt":
        # pip ships the same console launcher used by installed Python tools.
        from pip._vendor.distlib.scripts import ScriptMaker
        maker = ScriptMaker(None, str(bin_path))
        maker.executable = sys.executable
        maker.variants = {""}
        maker.make("gh = version_fixture:gh_main")
    else:
        launcher = bin_path / "gh"
        launcher.write_bytes((f"#!{sys.executable}\nfrom version_fixture import gh_main\ngh_main()\n").encode())
        launcher.chmod(0o755)
    return fixture_path


def run_consumer(root, stage=None):
    environment = os.environ.copy()
    environment["TRADECRAFT_VERSION_FIXTURE"] = str(root / ".tradecraft" / "github-fixture.json")
    environment["PATH"] = str(root / ".tradecraft" / "bin") + os.pathsep + environment.get("PATH", "")
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parent) + os.pathsep + environment.get("PYTHONPATH", "")
    arguments = ["run", stage] if stage else []
    return subprocess.run([sys.executable, str(Path(work.__file__).resolve()), *arguments,
                           "--repo", REPO, "--issue", "12", "--root", str(root)],
                          env=environment, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def main(argv=None):
    utf8_stdio()
    parser = argparse.ArgumentParser(description="Set up and run isolated version entrance consumer fixtures.")
    parser.add_argument("command", choices=["setup", "inspect", "ready-reviewers", "proof", "effects", "prompts"])
    parser.add_argument("root", type=Path)
    parser.add_argument("--scenario", choices=["blocked", "repaired", "unrelated"], default="blocked")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.command == "setup":
        setup_consumer(root, args.scenario)
        print(json.dumps({"root": str(root), "scenario": args.scenario}, ensure_ascii=True))
        return 0
    if args.command == "effects":
        transport = _load_fixture(root / ".tradecraft" / "github-fixture.json")
        print(json.dumps({"effects": transport.effects}, ensure_ascii=True, indent=2))
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
    result = run_consumer(root, None if args.command == "inspect" else args.command)
    sys.stdout.buffer.write(result.stdout)
    sys.stderr.buffer.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
