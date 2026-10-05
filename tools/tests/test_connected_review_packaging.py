import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))
import connected_review as cr  # noqa: E402


def _render_endpoint(node, assignments):
    if isinstance(node, ast.Name) and node.id in assignments:
        return _render_endpoint(assignments[node.id], assignments)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            value.value if isinstance(value, ast.Constant) else "{}"
            for value in node.values
        )
    raise AssertionError(f"unrecognized GitHub endpoint expression: {ast.dump(node)}")


def _runtime_api_calls(entrypoint):
    source = (ROOT / "lib/connected_review.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    pending = [entrypoint]
    visited = set()
    calls = set()
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        function = functions[name]
        assignments = {
            target.id: node.value
            for node in ast.walk(function)
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        for node in ast.walk(function):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            called = node.func.id
            if called in {"gh_json", "gh_bytes"}:
                endpoint = _render_endpoint(node.args[0], assignments)
                method = "GET"
                for keyword in node.keywords:
                    if keyword.arg == "method":
                        assert isinstance(keyword.value, ast.Constant)
                        method = keyword.value.value
                calls.add((method, endpoint))
            elif called in functions:
                pending.append(called)
    return calls


def _permission_for_api_call(method, endpoint):
    access = "write" if method != "GET" else "read"
    if "/actions/" in endpoint:
        return "actions", access
    if re.fullmatch(r"repos/\{\}/issues/\{\}/comments", endpoint):
        # The reporter's target is always a pull request. Permission-probe run
        # https://github.com/Grimblaz-and-Friends/reviewer-sandbox-private/actions/runs/36466795215
        # proved that its workflow token needs pull-requests: write to POST here.
        return "pull-requests", access
    if any(part in endpoint for part in ("/contents/", "/tarball/", "/compare/", "/git/trees/", "/git/blobs/")):
        assert access == "read"
        return "contents", "read"
    if "/pulls/" in endpoint:
        return "pull-requests", access
    raise AssertionError(f"unmapped GitHub API call: {method} {endpoint}")


def _job_permissions(workflow, job):
    body = workflow.split(f"  {job}:\n", 1)[1]
    match = re.search(r"\n  [a-z][a-z-]*:\n", body)
    if match:
        body = body[:match.start()]
    block = body.split("    permissions:\n", 1)[1].split("    outputs:", 1)[0]
    block = block.split("    steps:", 1)[0]
    return dict(
        re.fullmatch(r"      ([a-z-]+): (read|write)\n?", line).groups()
        for line in block.splitlines(keepends=True)
        if line.strip()
    )


def _required_permissions(calls, job_body):
    levels = {"read": 0, "write": 1}
    required = {}
    for method, endpoint in calls:
        permission, access = _permission_for_api_call(method, endpoint)
        if permission not in required or levels[access] > levels[required[permission]]:
            required[permission] = access
    if "actions/checkout@" in job_body:
        required.setdefault("contents", "read")
    return required


def test_measured_two_pass_replay_defaults_and_prompt_hashes_remain_reproducible():
    finder = ROOT / "skills/connected-review/references/finder.md"
    checker = ROOT / "skills/connected-review/references/checker.md"
    settings = cr.reviewer_settings()
    assert settings == {
        **cr.coverage_settings(),
        "checker_candidates_per_batch": 25,
        "checker_effort": "xhigh",
        "claude_cli_version": "2.1.280",
        "finder_candidates_per_pass": 50,
        "finder_effort": "xhigh",
        "finder_passes": [
            {
                "name": "coverage",
                "focus": (
                    "Trace each change through callers, consumers, tests, documented "
                    "contracts, and analogous paths, then probe each changed branch or guard "
                    "with unconsidered inputs and state transitions. Seek contradictions with "
                    "unchanged behavior, bypasses, lost state, refused valid cases, and wrong "
                    "records or results."
                ),
            },
        ],
        "max_candidates": 50,
        "model": "claude-opus-5-5",
        "preload_budget_bytes": 600000,
        "preload_changed_files": False,
    }
    assert hashlib.sha256(finder.read_bytes()).hexdigest() == (
        "3b13819ec50d747a655c3634a6b663592c052bca8d1f3fa7c0f8ebc8473bf247"
    )
    assert hashlib.sha256(checker.read_bytes()).hexdigest() == (
        "c7c352d97e6b971ffff6343d113cbc299dd2a3c6c72363b6debee28e665a3f83"
    )
    assert hashlib.sha256(cr._json_bytes(settings)).hexdigest() == (
        "7b101cc3a5661e80b8f347b6e2aff358280daf40bcf5987bd1b39da4d30370c8"
    )


def test_live_reviewer_standard_is_one_high_finder_with_frozen_prompt():
    finder = ROOT / "skills/connected-review/references/finder.md"
    skill = (ROOT / "skills/connected-review/SKILL.md").read_text(encoding="utf-8")
    assert cr.live_reviewer_settings() == {
        **cr.coverage_settings(),
        "checker_effort": None,
        "claude_cli_version": "2.1.280",
        "finder_candidates_per_pass": 50,
        "finder_effort": "high",
        "finder_passes": [
            {
                "name": "coverage",
                "focus": (
                    "Trace each change through callers, consumers, tests, documented "
                    "contracts, and analogous paths, then probe each changed branch or guard "
                    "with unconsidered inputs and state transitions. Seek contradictions with "
                    "unchanged behavior, bypasses, lost state, refused valid cases, and wrong "
                    "records or results."
                ),
            },
        ],
        "max_candidates": 50,
        "model": "claude-opus-5-5",
        "pass_structure": "single-pass",
    }
    assert hashlib.sha256(finder.read_bytes()).hexdigest() == (
        "3b13819ec50d747a655c3634a6b663592c052bca8d1f3fa7c0f8ebc8473bf247"
    )
    assert "One fresh read-only finder process runs at `high`" in skill
    assert "historical checker contract retained for replay reproducibility" in skill
    assert "the live workflow never loads it" in skill
    assert "replay preload" in skill
    assert "MAX_FINDER_PROMPT_BYTES" in skill


def test_canonical_workflow_has_trusted_boundary_and_no_push_trigger():
    workflow = (ROOT / "skills/connected-review/templates/connected-review.yml").read_text(
        encoding="utf-8"
    )
    assert "pull_request_target:" in workflow
    assert "types: [ready_for_review, labeled]" in workflow
    assert "workflow_dispatch:" not in workflow
    assert "synchronize" not in workflow
    assert "push:" not in workflow
    assert workflow.count("concurrency:") == 1
    review = workflow.split("  review:\n", 1)[1].split("  report:\n", 1)[0]
    assert "concurrency:" in review
    assert "group: connected-review-${{ github.repository }}-${{ needs.prepare.outputs.number }}" in review
    assert "cancel-in-progress: false" in review
    assert "persist-credentials: false" in workflow
    assert "CLAUDE_CODE_OAUTH_TOKEN" in workflow
    report = workflow.split("  report:\n", 1)[1]
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in report
    assert "needs.prepare.result != 'success'" in report
    assert "PREPARE_RESULT: ${{ needs.prepare.result }}" in report
    assert "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09" in workflow
    assert "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1" in workflow
    assert workflow.count(
        "TRADECRAFT_REVIEWER_REF: SET_BY_ENABLEMENT_TO_FROZEN_MERGED_COMMIT"
    ) == 1
    assert workflow.count("REVIEW_OWNER_LOGIN: Grimblaz") == 1
    assert "CONNECTED_REVIEW_ENABLED" not in workflow
    assert "CONNECTED_REVIEW_PRELOAD_CHANGED_FILES" not in workflow
    assert "${{ vars." not in workflow
    assert set(re.findall(r"secrets\.([A-Z0-9_]+)", workflow)) == {
        "CLAUDE_CODE_OAUTH_TOKEN",
    }
    lint = (ROOT / "tools/lint.py").read_text(encoding="utf-8")
    assert "connected-review.yml" not in lint
    assert "github-actions[bot]" not in lint
    assert "Run connected review" in workflow
    assert "--finder-prompt" in workflow
    assert "--checker-prompt" not in workflow
    assert "Run finder and checker" not in workflow
    assert "CONNECTED_REVIEW_VISIBILITY: ${{ needs.prepare.outputs.visibility }}" in workflow
    assert 'DISABLE_AUTOUPDATER: "1"' in workflow


def test_workflow_permissions_exactly_cover_each_job_api_call_graph():
    workflow = (ROOT / "skills/connected-review/templates/connected-review.yml").read_text(
        encoding="utf-8"
    )
    entrypoints = {
        "prepare": "eligibility",
        "review": "execute_review",
        "report": "report_skip",
    }
    expected_calls = {
        "prepare": {
            ("GET", "repos/{}/contents/{}?ref={}"),
            ("GET", "repos/{}/pulls/{}"),
            ("GET", "repos/{}/pulls/{}/reviews"),
        },
        "review": {
            ("GET", "repos/{}/compare/{}...{}"),
            ("GET", "repos/{}/contents/{}?ref={}"),
            ("GET", "repos/{}/pulls/{}"),
            ("GET", "repos/{}/pulls/{}/reviews"),
            ("GET", "repos/{}/tarball/{}"),
            ("GET", "repos/{}/git/trees/{}?recursive=1"),
            ("GET", "repos/{}/git/trees/{}"),
            ("GET", "repos/{}/git/blobs/{}"),
            ("GET", "repos/{}/issues/{}/comments"),
            ("POST", "repos/{}/issues/{}/comments"),
            ("POST", "repos/{}/pulls/{}/reviews"),
        },
        "report": {
            ("GET", "repos/{}/actions/runs/{}/jobs"),
            ("GET", "repos/{}/contents/{}?ref={}"),
            ("GET", "repos/{}/issues/{}/comments"),
            ("GET", "repos/{}/pulls/{}"),
            ("GET", "repos/{}/pulls/{}/reviews"),
            ("POST", "repos/{}/issues/{}/comments"),
        },
    }
    expected_permissions = {
        "prepare": {"contents": "read", "pull-requests": "read"},
        "review": {"contents": "read", "pull-requests": "write"},
        "report": {
            "actions": "read",
            "contents": "read",
            "pull-requests": "write",
        },
    }
    for job, entrypoint in entrypoints.items():
        calls = _runtime_api_calls(entrypoint)
        assert calls == expected_calls[job]
        body = workflow.split(f"  {job}:\n", 1)[1]
        required = _required_permissions(calls, body)
        assert required == expected_permissions[job]
        assert _job_permissions(workflow, job) == required


def test_cli_pin_supports_the_pinned_model_and_matches_setup_surfaces():
    runtime = (ROOT / "lib/connected_review.py").read_text(encoding="utf-8")
    matched = re.search(r'DEFAULT_CLAUDE_VERSION = "(\d+)\.(\d+)\.(\d+)"', runtime)
    assert matched is not None
    version = tuple(int(part) for part in matched.groups())
    assert version >= (2, 1, 280)
    assert "2.1.280 is the first version verified to support DEFAULT_MODEL" in runtime
    rendered = ".".join(str(part) for part in version)
    workflow = (ROOT / "skills/connected-review/templates/connected-review.yml").read_text(
        encoding="utf-8"
    )
    assert f"CLAUDE_CLI_VERSION: {rendered}" in workflow
    assert f"@anthropic-ai/claude-code@{rendered}" in workflow
    setup = (
        ROOT / "skills/adversarial-review/references/connected-reviewers.md"
    ).read_text(encoding="utf-8")
    live = (ROOT / "tools/connected-review-live-checks.md").read_text(encoding="utf-8")
    assert f"Claude CLI {rendered}" in setup
    assert f"Claude CLI {rendered}" in live


def test_finder_prompt_stays_frozen_and_historical_checker_remains_replayable():
    finder = (ROOT / "skills/connected-review/references/finder.md").read_text(encoding="utf-8")
    checker = (ROOT / "skills/connected-review/references/checker.md").read_text(encoding="utf-8")
    for phrase in ("docstring coverage", "linter", "grammar", "before merge", "does not state"):
        assert phrase in finder
    for phrase in ("optional hardening", "speculation"):
        assert phrase not in finder
    assert "P0/P1" not in finder
    assert "root cause" in finder
    assert "coverage sweep across all hunks" in finder
    assert "proof targets" in finder
    assert "Never create a candidate" in checker
    assert "uncertain after the trace, drop" in checker
    assert "trace its stated execution path" in checker
    assert "not present in the snapshot or diff" in checker
    assert "Keep at most one candidate for one root cause" in checker


def test_workflow_template_matches_documentation():
    template = (ROOT / "skills/connected-review/templates/connected-review.yml").read_text(
        encoding="utf-8"
    )
    reference = (
        ROOT / "skills/adversarial-review/references/connected-reviewers.md"
    ).read_text(encoding="utf-8")
    section = reference.split(
        "## `connected-review.yml` in the repository's GitHub Actions workflows directory", 1
    )[1]
    documented = section.split("```yaml\n", 1)[1].split("\n```", 1)[0] + "\n"
    assert documented == template


def lab_workflow():
    return (ROOT / ".github/workflows/connected-review-shared.yml").read_text(encoding="utf-8")


def lab_job(job):
    body = lab_workflow().split(f"  {job}:\n", 1)[1]
    return re.split(r"\n  [a-z][a-z-]*:\n", body, maxsplit=1)[0]


def lab_python_steps(job):
    return [textwrap.dedent(script).rstrip() + "\n" for script in re.findall(
        r"        run: \|\n(.*?)(?=      - name:|\Z)", lab_job(job), re.S,
    )]


def run_workflow_script(script, tmp_path, variables):
    return subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, env={**os.environ, **variables},
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        encoding="utf-8", errors="replace", check=False,
    )


def test_lab_stub_and_downstream_example_call_one_release_control():
    stub = (ROOT / ".github/workflows/connected-review.yml").read_text(encoding="utf-8")
    assert stub == (
        "name: connected-review\n\non:\n  pull_request_target:\n"
        "    types: [ready_for_review, labeled]\n\njobs:\n  connected-review:\n"
        "    permissions:\n      actions: read\n      contents: read\n"
        "      pull-requests: write\n"
        "    uses: Grimblaz-and-Friends/tradecraft/.github/workflows/connected-review-shared.yml@main\n"
        "    secrets:\n"
        "      CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}\n"
    )
    procedure = (ROOT / "docs/cells/steward/references/connected-review-releases.md").read_text(encoding="utf-8")
    documented = procedure.split("```yaml\n", 1)[1].split("\n```", 1)[0] + "\n"
    assert documented == stub.replace("@main", "@reviewer-stable")
    steward = (ROOT / "docs/cells/steward/SKILL.md").read_text(encoding="utf-8")
    assert "`references/connected-review-releases.md`" in steward


def test_shared_workflow_preserves_security_and_runtime_boundaries():
    workflow = lab_workflow()
    trigger = workflow.split("on:\n", 1)[1].split("\nenv:", 1)[0]
    assert trigger == (
        "  workflow_call:\n    secrets:\n      CLAUDE_CODE_OAUTH_TOKEN:\n"
        "        required: true\n"
    )
    assert "inputs:" not in workflow
    assert workflow.count("CLAUDE_CLI_VERSION: 2.1.280") == 1
    assert workflow.count("2.1.280") == 1
    assert 'npm install --global @anthropic-ai/claude-code@"$CLAUDE_CLI_VERSION"' in workflow
    assert "TRADECRAFT_REVIEWER_REF" not in workflow
    assert "reviewer-stable" not in workflow and "@main" not in workflow
    assert "github.workflow_sha" not in workflow and "github.sha" not in workflow
    assert workflow.count("concurrency:") == 1
    review = lab_job("review")
    assert "runs-on: ${{ needs.prepare.outputs.visibility == 'private' && 'self-hosted' || 'ubuntu-latest' }}" in review
    assert "timeout-minutes: 120" in review
    assert "group: connected-review-${{ github.repository }}-${{ needs.prepare.outputs.number }}" in review
    assert "cancel-in-progress: false" in review
    assert "--finder-prompt" in review and "--checker-prompt" not in review
    assert 'DISABLE_AUTOUPDATER: "1"' in review
    assert review.count("needs.prepare.outputs.visibility == 'public'") == 2
    for job, entrypoint in (("prepare", "eligibility"), ("review", "execute_review"), ("report", "report_skip")):
        body = lab_job(job)
        assert _job_permissions(workflow, job) == _required_permissions(_runtime_api_calls(entrypoint), body)
        assert "persist-credentials: false" in body
        assert "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09" in body
        assert "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1" in body
        assert body.index("job.workflow_sha") < body.index("actions/checkout@")
        assert body.index("Verify trusted reviewer checkout") < body.index("lib/connected_review.py")
        if job != "review":
            assert "runs-on: ubuntu-latest" in body
            assert "secrets." not in body
        else:
            before, finder = body.split("      - name: Run connected review\n")
            assert "secrets." not in before
            assert finder.count("secrets.CLAUDE_CODE_OAUTH_TOKEN") == 1
    assert "always() &&" in lab_job("report")
    assert "needs.prepare.result != 'success'" in lab_job("report")
    assert "reviewer_sha: ${{ steps.identity.outputs.reviewer_sha }}" in lab_job("prepare")
    assert "ref: ${{ needs.prepare.outputs.reviewer_sha }}" in review
    for job in ("prepare", "report"):
        assert "ref: ${{ steps.identity.outputs.reviewer_sha }}" in lab_job(job)
    for job, revision in (("review", "needs.prepare.outputs.reviewer_sha"), ("report", "steps.identity.outputs.reviewer_sha")):
        assert lab_job(job).count("CONNECTED_REVIEW_REVIEWER_SHA: ${{ " + revision + " }}") == 2


@pytest.mark.parametrize("job", ["prepare", "review", "report"])
@pytest.mark.parametrize("patch,accepted", [
    ({}, True),
    ({"WORKFLOW_REPOSITORY": "example/product"}, False),
    ({"WORKFLOW_FILE_PATH": ".github/workflows/connected-review.yml"}, False),
    ({"WORKFLOW_SHA": ""}, False),
    ({"WORKFLOW_SHA": "c" * 39}, False),
    ({"WORKFLOW_SHA": "main"}, False),
])
def test_called_identity_is_the_workflow_commit_not_the_caller(job, patch, accepted, tmp_path):
    revision = "c" * 40
    output = tmp_path / "output"
    variables = {
        "WORKFLOW_REPOSITORY": "Grimblaz-and-Friends/tradecraft",
        "WORKFLOW_FILE_PATH": ".github/workflows/connected-review-shared.yml",
        "WORKFLOW_SHA": revision, "CAPTURED_REVIEWER_SHA": revision,
        "GITHUB_SHA": "a" * 40, "GITHUB_WORKFLOW_SHA": "a" * 40,
        "GITHUB_OUTPUT": str(output), **patch,
    }
    result = run_workflow_script(lab_python_steps(job)[0], tmp_path, variables)
    assert (result.returncode == 0) == accepted, result.stderr
    if accepted:
        assert output.read_bytes() == f"reviewer_sha={revision}\n".encode()
    else:
        assert not output.exists()


@pytest.mark.parametrize("job", ["review", "report"])
def test_later_jobs_reject_a_changed_workflow_commit(job, tmp_path):
    output = tmp_path / "output"
    result = run_workflow_script(lab_python_steps(job)[0], tmp_path, {
        "WORKFLOW_REPOSITORY": "Grimblaz-and-Friends/tradecraft",
        "WORKFLOW_FILE_PATH": ".github/workflows/connected-review-shared.yml",
        "WORKFLOW_SHA": "d" * 40, "CAPTURED_REVIEWER_SHA": "c" * 40,
        "GITHUB_OUTPUT": str(output),
    })
    assert result.returncode != 0 and "disagrees with preparation" in result.stderr
    assert not output.exists()


def test_report_recovers_immutable_identity_after_prepare_failure_but_review_requires_it(tmp_path):
    variables = {
        "WORKFLOW_REPOSITORY": "Grimblaz-and-Friends/tradecraft",
        "WORKFLOW_FILE_PATH": ".github/workflows/connected-review-shared.yml",
        "WORKFLOW_SHA": "c" * 40, "CAPTURED_REVIEWER_SHA": "",
        "GITHUB_OUTPUT": str(tmp_path / "output"),
    }
    review = run_workflow_script(lab_python_steps("review")[0], tmp_path, variables)
    assert review.returncode != 0 and "no reviewer commit" in review.stderr
    report = run_workflow_script(lab_python_steps("report")[0], tmp_path, variables)
    assert report.returncode == 0, report.stderr
    assert (tmp_path / "output").read_bytes() == b"reviewer_sha=" + b"c" * 40 + b"\n"


def test_mutable_ref_movement_does_not_change_captured_execution_identity(tmp_path):
    revision = "c" * 40
    output = tmp_path / "output"
    variables = {
        "WORKFLOW_REPOSITORY": "Grimblaz-and-Friends/tradecraft",
        "WORKFLOW_FILE_PATH": ".github/workflows/connected-review-shared.yml",
        "WORKFLOW_SHA": revision, "GITHUB_OUTPUT": str(output),
    }
    assert run_workflow_script(lab_python_steps("prepare")[0], tmp_path, variables).returncode == 0
    captured = output.read_text().strip().split("=", 1)[1]
    for job in ("review", "report"):
        result = run_workflow_script(lab_python_steps(job)[0], tmp_path, {
            **variables, "CAPTURED_REVIEWER_SHA": captured,
            "TRADECRAFT_REVIEWER_REF": "d" * 40, "GITHUB_SHA": "a" * 40,
        })
        assert result.returncode == 0, result.stderr
    assert output.read_bytes() == (f"reviewer_sha={revision}\n" * 3).encode()


@pytest.mark.parametrize("job", ["prepare", "review", "report"])
@pytest.mark.parametrize("matches", [True, False])
def test_each_job_verifies_checkout_head_before_runtime(job, matches, tmp_path):
    # Exercise the actual inline script with Git's HEAD response controlled.
    script = (
        "from unittest.mock import patch\nimport subprocess\n"
        "with patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, "
        + repr("c" * 40 + "\n") + ", '')):\n"
        + textwrap.indent(lab_python_steps(job)[1], "    ")
    )
    result = run_workflow_script(script, tmp_path, {
        "CONNECTED_REVIEW_REVIEWER_SHA": ("c" if matches else "d") * 40,
    })
    assert (result.returncode == 0) == matches, result.stderr
    if not matches:
        assert "checkout does not match" in result.stderr


def test_no_shipped_consumer_names_lab_release_controls():
    for directory in ("skills", "lib", "commands", "agents", "hooks", ".claude-plugin"):
        for path in (ROOT / directory).rglob("*"):
            if path.is_file() and path.suffix in {".py", ".md", ".yml", ".json"}:
                text = path.read_text(encoding="utf-8")
                assert "connected-review-shared.yml" not in text, path
                assert "reviewer-stable" not in text, path


def test_setup_names_login_only_enablement_and_private_prerequisites():
    reference = (
        ROOT / "skills/adversarial-review/references/connected-reviewers.md"
    ).read_text(encoding="utf-8")
    prose = reference.split(
        "## `connected-review.yml` in the repository's GitHub Actions workflows directory", 1
    )[1].split("```yaml\n", 1)[0]
    assert "repository's GitHub Actions workflows directory" in reference
    assert (
        "copy the one workflow file, set the one secret, and, on a private "
        "repository, install the runner"
    ) in prose
    assert "`claude setup-token` as the owner" in prose
    assert "long-lived token" in prose
    assert "on the repository or organization" in prose
    assert "`REVIEW_OWNER_LOGIN` names the one account" in prose
    assert "already names the lab owner, `Grimblaz`" in prose
    assert "any other author is refused without a notice" in prose
    assert "`gh`, `git`, Python 3.14, Node and npm" in prose
    assert "`gh`, `git`, Python 3.14, Node and npm" in (ROOT / "skills/connected-review/SKILL.md").read_text(encoding="utf-8")
    assert "run the runner as the account whose PATH holds them" in prose
    assert "runner installed as a service runs under a service account" in prose
    assert "for example from a logon task" in prose
    assert "install the tools for all users" in prose
    assert "`RUNNER_TOOL_CACHE` a stable writable location" in prose
    assert "cache's `claude-cli` directory" in prose
    assert "never installs or executes pull-request content" in prose
    assert "rather than falling back to another CLI" in prose
    assert "`.path`" not in prose
    assert "hosted `prepare` job" in prose and "hosted `report` job" in prose
    assert "permitted non-mechanical second look" in prose
    assert "`TRADECRAFT_REVIEWER_REF` to a commit on tradecraft's default branch" in prose
    assert "normally the merge commit of the change that shipped it" in prose
    assert (
        "gh api repos/Grimblaz-and-Friends/tradecraft/compare/<sha>...main "
        "--jq .status"
    ) in prose
    assert "`identical` or `ahead` means it is on `main`" in prose
    assert "base branch's `.tradecraft/work.json`" in prose
    assert "`github-actions[bot]` is missing from `connected_reviewers`" in prose
    assert "placeholder ref below is not runnable" in prose
    assert "do not install the template unchanged" in prose
    assert "installed with a real ref" in prose
    assert "is dormant" in prose
    assert "only activation switch" in prose
    assert "label named by `reviewer_label` in `.tradecraft/work.json`" in prose
    assert "default is `reviewers`" in prose
    assert "label trigger fires only when that label is added" in prose
    assert "gh run rerun <run-id> --failed" in prose
    assert "review job deliberately remains failed" in prose
    assert "successful over-budget preflight skip" in prose
    assert "`connected-review` cell's input-policy contract" in prose
    assert "A separate workflow dispatch is not offered" in prose
    assert "default branch and cannot repair" in prose
    assert "one finder at `high`" in prose
    assert "CONNECTED_REVIEW_ENABLED" not in prose
    assert "CONNECTED_REVIEW_PRELOAD_CHANGED_FILES" not in prose
    assert "preload" not in prose.casefold()
    assert ".github/" not in reference

    live = (ROOT / "tools/connected-review-live-checks.md").read_text(encoding="utf-8")
    assert "`gh`, `git`, Python 3.14, Node and npm" in live
    assert "`RUNNER_TOOL_CACHE` a stable writable location" in live
    assert "under its `claude-cli` directory" in live
    assert "disables the auto-updater" in live
    assert "executes nothing from the pull request" in live
    assert "CONNECTED_REVIEW_ENABLED" not in live
    assert "`.path`" not in live
