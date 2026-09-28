import ast
import hashlib
import json
from pathlib import Path
import re
import sys


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
    if "/issues/" in endpoint:
        return "issues", access
    if any(part in endpoint for part in ("/contents/", "/tarball/", "/compare/")):
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
        "b7d4b103c9ed31d42258e6f774161bad1f060a42d00c666ac484f800cdbd92a6"
    )


def test_live_reviewer_standard_is_one_high_finder_with_frozen_prompt():
    finder = ROOT / "skills/connected-review/references/finder.md"
    skill = (ROOT / "skills/connected-review/SKILL.md").read_text(encoding="utf-8")
    assert cr.live_reviewer_settings() == {
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
        "preload_budget_bytes": 600000,
        "preload_changed_files": False,
    }
    assert hashlib.sha256(finder.read_bytes()).hexdigest() == (
        "3b13819ec50d747a655c3634a6b663592c052bca8d1f3fa7c0f8ebc8473bf247"
    )
    assert "One fresh read-only finder process runs at `high`" in skill
    assert "historical checker contract retained for replay reproducibility" in skill
    assert "the live workflow never loads it" in skill


def test_canonical_workflow_has_trusted_boundary_and_no_push_trigger():
    workflow = (ROOT / "skills/connected-review/templates/connected-review.yml").read_text(
        encoding="utf-8"
    )
    assert "pull_request_target:" in workflow
    assert "types: [ready_for_review, labeled]" in workflow
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
    assert "if: vars.CONNECTED_REVIEW_ENABLED == 'true'" in workflow
    assert "Run connected review" in workflow
    assert "--finder-prompt" in workflow
    assert "--checker-prompt" not in workflow
    assert "Run finder and checker" not in workflow
    assert (
        "CONNECTED_REVIEW_PRELOAD_CHANGED_FILES: "
        "${{ vars.CONNECTED_REVIEW_PRELOAD_CHANGED_FILES }}"
    ) in workflow


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
            "issues": "write",
            "pull-requests": "read",
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


def test_workflow_template_repository_copy_and_documented_block_are_identical():
    template = (ROOT / "skills/connected-review/templates/connected-review.yml").read_text(
        encoding="utf-8"
    )
    repository_copy = (ROOT / ".github/workflows/connected-review.yml").read_text(
        encoding="utf-8"
    )
    reference = (
        ROOT / "skills/adversarial-review/references/connected-reviewers.md"
    ).read_text(encoding="utf-8")
    section = reference.split(
        "## `connected-review.yml` in the repository's GitHub Actions workflows directory", 1
    )[1]
    documented = section.split("```yaml\n", 1)[1].split("\n```", 1)[0] + "\n"
    assert repository_copy == template
    assert documented == template


def test_repository_copy_is_dormant_until_its_login_is_configured():
    configuration = json.loads((ROOT / ".tradecraft/work.json").read_text(encoding="utf-8"))
    assert "github-actions[bot]" not in configuration["connected_reviewers"]


def test_setup_names_dormant_enablement_and_private_prerequisites():
    reference = (
        ROOT / "skills/adversarial-review/references/connected-reviewers.md"
    ).read_text(encoding="utf-8")
    prose = reference.split(
        "## `connected-review.yml` in the repository's GitHub Actions workflows directory", 1
    )[1].split("```yaml\n", 1)[0]
    assert "repository's GitHub Actions workflows directory" in reference
    assert "Copy this block whole to that directory" in prose
    assert "install `gh`, Python 3.14 and Claude CLI 2.1.280" in prose
    assert "first on the runner's PATH through the runner's `.path` file" in prose
    assert "refuses and names a detected version mismatch" in prose
    assert "hosted `prepare` job" in prose and "hosted `report` job" in prose
    assert "permitted non-mechanical second look" in prose
    assert "reviewed merged commit on the default branch" in prose
    assert "deliberately leave this copy dormant" in prose
    assert "one finder at `high`" in prose
    assert "optional `CONNECTED_REVIEW_PRELOAD_CHANGED_FILES`" in prose
    assert "600,000 raw bytes" in prose
    assert ".github/" not in reference

    live = (ROOT / "tools/connected-review-live-checks.md").read_text(encoding="utf-8")
    assert "first on that runner's PATH with its `.path` file" in live
    assert "refuse and name a detected version mismatch" in live
