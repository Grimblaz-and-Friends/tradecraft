import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def test_canonical_workflow_has_trusted_boundary_and_no_push_trigger():
    workflow = (ROOT / "skills/connected-review/templates/connected-review.yml").read_text(
        encoding="utf-8"
    )
    assert "pull_request_target:" in workflow
    assert "types: [ready_for_review, labeled]" in workflow
    assert "synchronize" not in workflow
    assert "push:" not in workflow
    assert "cancel-in-progress: false" in workflow
    assert "persist-credentials: false" in workflow
    assert "CLAUDE_CODE_OAUTH_TOKEN" in workflow
    report = workflow.split("  report:\n", 1)[1]
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in report
    assert "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09" in workflow
    assert "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1" in workflow
    pin = re.search(r"TRADECRAFT_REVIEWER_REF: ([0-9a-f]{40})", workflow)
    assert pin is not None
    assert "REPLACE_WITH_REVIEWED_COMMIT" not in workflow


def test_prompts_carry_opposite_burdens_and_all_named_exclusions():
    finder = (ROOT / "skills/connected-review/references/finder.md").read_text(encoding="utf-8")
    checker = (ROOT / "skills/connected-review/references/checker.md").read_text(encoding="utf-8")
    for phrase in ("docstring coverage", "linter", "grammar", "before merge", "does not state"):
        assert phrase in finder
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
    section = reference.split("## `connected-review.yml`", 1)[1]
    documented = section.split("```yaml\n", 1)[1].split("\n```", 1)[0] + "\n"
    assert repository_copy == template
    assert documented == template


def test_repository_copy_is_dormant_until_its_login_is_configured():
    configuration = json.loads((ROOT / ".tradecraft/work.json").read_text(encoding="utf-8"))
    assert "github-actions[bot]" not in configuration["connected_reviewers"]
