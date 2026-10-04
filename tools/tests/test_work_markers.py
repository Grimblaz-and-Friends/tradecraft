import re
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lib"))
import work  # noqa: E402


def documented_markers(text):
    return frozenset(re.findall(r"(?m)^## `([a-z-]+)`$", text))


def marker_reference():
    return (ROOT / "skills" / "work" / "references" / "markers.md").read_text(
        encoding="utf-8"
    )


def test_marker_reference_names_every_live_evidence_marker():
    assert work.WORK_EVIDENCE_MARKERS - documented_markers(marker_reference()) == frozenset()


def test_marker_reference_coverage_guard_detects_an_omitted_marker():
    omitted = "affirmed-brief"
    altered = marker_reference().replace(f"## `{omitted}`", f"## `{omitted}-missing`", 1)
    assert work.WORK_EVIDENCE_MARKERS - documented_markers(altered) == {omitted}


@pytest.mark.parametrize(("path", "marker"), [
    ("skills/engagement/references/the-brief.md", "affirmed-brief"),
    ("skills/engagement/references/the-stretch.md", "holder-reading"),
    ("skills/engagement/references/the-artifact.md", "artifact"),
    ("skills/engagement/references/cold-seat.md", "cold-verdict"),
    ("skills/experience-session/references/the-note.md", "use"),
    ("skills/adversarial-review/references/connected-reviewers.md", "connected-reviewer"),
    ("skills/adversarial-review/references/the-record.md", "panel-stage"),
    ("docs/cells/landing/SKILL.md", "implementing-pr"),
])
def test_each_producing_template_carries_its_marker(path, marker):
    text = (ROOT / path).read_text(encoding="utf-8")
    assert f"<!-- tradecraft:{marker}:v1" in text


def test_no_use_is_proof_owned_without_a_producing_marker_template():
    text = (ROOT / "skills/experience-session/references/when-one-fires.md").read_text(encoding="utf-8")
    assert "proof's `use` section" in text
    assert "tradecraft:no-use:" not in text
    assert "no-use" not in work.WORK_EVIDENCE_MARKERS
