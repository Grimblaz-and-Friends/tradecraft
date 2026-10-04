"""E10: validate the actual declaration, expanded names and event schedules."""
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def flow_values(text, pattern):
    """Parse these workflows' unquoted YAML flow arrays, refusing another shape."""
    matches = re.findall(pattern, text, re.M)
    assert len(matches) == 1
    values = matches[0].split(",")
    assert all(re.fullmatch(r"[\w-]+", value.strip()) for value in values)
    return [value.strip() for value in values]


def test_actual_declaration_and_body_edit_schedule():
    policy = json.loads((ROOT / ".github/change-proof.json").read_bytes())
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    body = (ROOT / ".github/workflows/ask-declaration.yml").read_text(encoding="utf-8")
    ci_jobs = re.findall(r"^  ([\w-]+):$", ci.split("\njobs:\n", 1)[1], re.M)
    body_jobs = re.findall(r"^  ([\w-]+):$", body.split("\njobs:\n", 1)[1], re.M)
    assert ci_jobs == ["lint-and-test"]
    assert body_jobs == ["ask-declaration"]
    matrix = flow_values(ci, r"^        os: \[([^\]]+)\]$")
    assert matrix == ["ubuntu-latest", "windows-latest"]
    assert not re.search(r"^    name:", ci, re.M)  # Actions' default expanded name.
    assert not re.search(r"^    name:", body, re.M)
    pairs = {(item["workflow"], item["job"]) for item in policy["floor"]["jobs"]}
    assert pairs == {(".github/workflows/ci.yml", f"lint-and-test ({os})") for os in matrix} | {
        (".github/workflows/ask-declaration.yml", "ask-declaration")}
    assert len(policy["floor"]["jobs"]) == len(pairs)
    suite_events = flow_values(ci, r"^    types: \[([^\]]+)\]$")
    body_events = flow_values(body, r"^    types: \[([^\]]+)\]$")
    assert "edited" not in suite_events and "edited" in body_events
    for event in ["opened", "reopened", "synchronize"]:
        assert event in suite_events and event in body_events
    assert "ready_for_review" in body_events
    assert "  push:" not in body
    assert "  push:\n    branches: [main]" in ci
    for retained in ["if: github.event_name == 'pull_request'", "pull-requests: read",
                     "persist-credentials: false", "GH_TOKEN: ${{ github.token }}",
                     "PR_NUMBER: ${{ github.event.pull_request.number }}",
                     'python tools/check_ask_declaration.py --pr "$PR_NUMBER"']:
        assert retained in body
