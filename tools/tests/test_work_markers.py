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


def test_marker_reference_names_every_marker_the_entrance_reads():
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
    ("skills/experience-session/references/when-one-fires.md", "no-use"),
    ("skills/adversarial-review/references/connected-reviewers.md", "connected-reviewer"),
    ("skills/adversarial-review/references/the-record.md", "panel-stage"),
    ("docs/cells/landing/SKILL.md", "implementing-pr"),
])
def test_each_producing_template_carries_its_marker(path, marker):
    text = (ROOT / path).read_text(encoding="utf-8")
    assert f"<!-- tradecraft:{marker}:v1" in text
