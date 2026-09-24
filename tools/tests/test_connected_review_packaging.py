import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


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


def test_prompts_carry_opposite_burdens_and_all_named_exclusions():
    finder = (ROOT / "skills/connected-review/references/finder.md").read_text(encoding="utf-8")
    checker = (ROOT / "skills/connected-review/references/checker.md").read_text(encoding="utf-8")
    for phrase in ("docstring coverage", "linter", "grammar", "before merge", "does not state"):
        assert phrase in finder
    for phrase in ("optional hardening", "speculation"):
        assert phrase not in finder
    assert "P0/P1" not in finder
    assert "Never create a candidate" in checker
    assert "uncertain, drop" in checker


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
    assert "install `gh`, Python 3.14 and the pinned Claude CLI" in prose
    assert "hosted `prepare` job" in prose and "hosted `report` job" in prose
    assert "permitted non-mechanical second look" in prose
    assert "frozen merged commit on the default branch" in prose
    assert "deliberately leave this copy dormant" in prose
    assert ".github/" not in reference
