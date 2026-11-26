"""A proof names a use or floor source only by a comment opening with a marker the entrance declares for it."""
import json
from pathlib import Path
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import work  # noqa: E402
import test_work as support  # noqa: E402


def held(body, identity=41, kind="issue-comment"):
    state = support.state(support.AFFIRMED, pr=True)
    comment = {"id": identity, "body": body, "user": {"login": support.PRODUCER}}
    (state.issue_comments if kind == "issue-comment" else state.pr_comments).append(comment)
    return state, {"kind": kind, "id": identity}


@pytest.mark.parametrize("evidence, body", [
    ("use", f"<!-- tradecraft:use:v1 head={support.SHA} status=pass changed=false staffing_status=qualified -->"),
    ("use", f"<!-- tradecraft:check-report:v1 stage=use head={support.SHA} -->"),
    ("use", "<!-- tradecraft:affirmed-brief:v1 -->\nReview risk: ordinary\nReview lane: mechanical\n"),
    ("floor", f"<!-- tradecraft:floor:v1 head={support.SHA} status=pass -->"),
])
def test_a_source_opening_with_a_declared_marker_is_named(evidence, body):
    state, source = held(body)
    work._refuse_unlisted_source(state, evidence, source)


@pytest.mark.parametrize("evidence, body, opening", [
    ("use", "<!-- tradecraft:cold-verdict:v1 verdict=would -->", "a cold-verdict marker"),
    ("use", f"<!-- tradecraft:floor:v1 head={support.SHA} status=pass -->", "a floor marker"),
    ("floor", f"<!-- tradecraft:use:v1 head={support.SHA} status=pass changed=false staffing_status=qualified -->",
     "a use marker"),
    ("floor", "The floor passed.", "no marker"),
])
def test_a_source_opening_with_any_other_marker_is_refused(evidence, body, opening):
    state, source = held(body, kind="pull-request-comment")
    with pytest.raises(work.WorkError, match=f"pull-request-comment #41 as its {evidence} source, which opens "
                                             f"with {opening}; a {evidence} source opens with "):
        work._refuse_unlisted_source(state, evidence, source)


def test_a_source_the_state_holds_no_comment_for_is_left_to_the_gate():
    state, _source = held("<!-- tradecraft:cold-verdict:v1 verdict=would -->")
    work._refuse_unlisted_source(state, "use", {"kind": "issue-comment", "id": 99})
    work._refuse_unlisted_source(state, "use", {"kind": "issue", "id": None})
    work._refuse_unlisted_source(state, "floor", None)


def test_the_shared_counting_use_report_is_the_body_the_entrance_writes():
    """The shared case the gate is tested on is the report this entrance posts, so the two read one form."""
    shared = json.loads((LIB.parent / "skills" / "work" / "references" / "proof-fixtures"
                         / "v1-builder-use-report.json").read_bytes())
    counting = next(case for case in shared["cases"] if case["expected"]["result"] == "counts")
    marker, _, returned = counting["comment"]["body"].partition("\n\n")
    attributes = dict(part.split("=", 1) for part in marker.removeprefix("<!-- ").removesuffix(" -->").split()[1:])
    frame = {"dispatch_id": attributes["dispatch"], "dispatch_sha256": attributes["dispatch_sha256"],
             "staffing_status": attributes["staffing_status"], "same_vendor_reason": attributes["same_vendor_reason"],
             "outcome": attributes["outcome"], "return": returned.encode("utf-8")}
    assert attributes["head"] == shared["evidence_head"]
    assert work.check_report_body(stage="use", frame=frame, head=attributes["head"], tree=attributes["tree"],
                                  criterion=None) == counting["comment"]["body"]
