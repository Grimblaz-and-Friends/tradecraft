"""Tests for tools/trial_intake.py: classification in both polarities, the
ambiguity refusal, the window split, and the CLI on a fixture file."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import trial_intake as ti  # noqa: E402


REVIEW_BODY = """same-subject #1 -- closed

> **In plain terms:** something.

**Warrant:** surfaced by the `claims-vs-evidence` seat of PR #173's review, sustained at the terminal stage.

## The want
"""

USE_BODY = """> **In plain terms:** something.

## Why it will get picked up

A cold consumer hit this on the first real use of the new permission and told us. Value 2.
"""

OWNER_BODY = """> **In plain terms:** something.

## Why it will get picked up

Owner-directed, 2026-09-05, after a design sitting. Value 3 by number.
"""

AMBIGUOUS_BODY = """> **In plain terms:** something.

**Warrant:** surfaced by the `authority` seat of PR #300's review, which cited the experience session that first met it.
"""

UNSTATED_BODY = """> **In plain terms:** something.

## The want

A thing. Nothing here says where it came from.
"""

# A body whose *evidence* carries a strong review phrase, but whose own
# provenance section names use. The provenance section must win.
LAYERED_BODY = """> **In plain terms:** something.

## The evidence

The owner ruled on 2026-09-05 that no marker is carried. The claim was sustained by the terminal stage of PR #415's review, whose judge's corpus probe put reciprocity at 7 pairs.

## Why it will get picked up

Filed from PR #437's second experience session, which met it on the fixed tree.
"""

# A body that *discusses* every mechanism the weak tier names -- the judge, the
# cold seat, the terminal stage, the experience session, the A/B run, the
# design sitting -- with no provenance section and no verb of provenance.
# Topic is not origin. PR #451's review found the first version of this
# control drawn from outside the defect's class: it omitted the two literals
# that were actually misplaced, so the defect shipped green.
TOPICAL_BODY = """> **In plain terms:** the cold seat and the judge disagree about a word.

## The evidence

`references/cold-seat.md` says the seat applies the bar; `arbitration.md` says the judge rules at the terminal stage. A cold consumer would read the two apart, and an experience session or an A/B run would show it. The design sitting on 2026-09-05 used the word both ways.

## The want

One owner for the word.
"""

# Provenance stated under the heading forms the corpus actually uses.
HEADED_PROVENANCE_BODY = """> **In plain terms:** something.

## The evidence

The claim was sustained by the terminal stage of PR #415's review.

## Provenance

Found by the second experience session PR #376's fix batch bought, on the fixed tree.

## Why this will get picked up

Value 2 by number.
"""

MIGHT_VARIANT_BODY = """> **In plain terms:** something.

## Why it might get picked up, and why it might not

The judge routed it here at the terminal stage; the fix is cheap.
"""


def test_review_provenance_classifies_as_review_and_not_use():
    cls, phrases, basis = ti.classify(REVIEW_BODY)
    assert cls == "review"
    assert basis == "provenance"
    assert any("surfaced by" in p for p in phrases)
    assert not any("experience" in p.lower() for p in phrases)


def test_use_provenance_classifies_as_use_and_not_review():
    cls, phrases, basis = ti.classify(USE_BODY)
    assert cls == "use"
    assert basis == "provenance"
    assert any("consumer hit" in p.lower() for p in phrases)


def test_owner_provenance_classifies_as_owner():
    cls, phrases, _ = ti.classify(OWNER_BODY)
    assert cls == "owner"
    assert "Owner-directed" in phrases and "design sitting" in phrases


def test_two_sources_in_the_provenance_refuse_to_classify():
    cls, phrases, _ = ti.classify(AMBIGUOUS_BODY)
    assert cls == "ambiguous"
    assert any(p.startswith("review:") for p in phrases)
    assert any(p.startswith("use:") for p in phrases)


def test_no_phrase_anywhere_is_unstated_not_a_guess():
    cls, phrases, basis = ti.classify(UNSTATED_BODY)
    assert cls == "unstated"
    assert phrases == []
    assert basis == "body"


def test_provenance_section_outranks_phrases_in_the_evidence():
    # Negative control for the fallback: the whole body would be ambiguous
    # (owner + review + use); the provenance section alone says use.
    cls, phrases, basis = ti.classify(LAYERED_BODY)
    assert cls == "use"
    assert basis == "provenance"
    whole = ti.classify_whole(LAYERED_BODY)
    assert whole[0] == "ambiguous", "the control must differ, or the section rule proves nothing"


def _every_weak_literal_is_in(body: str) -> None:
    # The control is only a control if it carries the words the tiers are about.
    for name, pattern in ti.WEAK_PATTERNS.items():
        assert pattern.search(body), f"control body lacks a weak {name} phrase"


def test_a_body_that_discusses_the_mechanisms_is_not_classified_by_topic():
    # Negative control for the tiers: every mechanism phrase the weak tier
    # names appears, none as a verb of provenance, and there is no provenance
    # section. This must be unstated, not review, use or owner.
    _every_weak_literal_is_in(TOPICAL_BODY)
    cls, phrases, basis = ti.classify(TOPICAL_BODY)
    assert cls == "unstated", (cls, phrases)
    assert basis == "body"


def test_no_strong_phrase_is_a_mechanism_noun():
    # The two nouns PR #451's review found in STRONG, and the words the weak
    # tier owns: none may match in the anywhere tier.
    for word in ("A/B run", "design sitting", "the judge", "terminal stage", "cold seat",
                 "experience session", "cold consumer"):
        for name, pattern in ti.STRONG_PATTERNS.items():
            assert not pattern.search(word), f"{word!r} matches STRONG {name}"


def test_weak_words_decide_inside_a_provenance_section_and_only_there():
    # Second half of the control, decided by a WEAK phrase: 'the judge' and
    # 'terminal stage' with no verb of provenance. It must classify with the
    # section, and stop classifying when the weak tier is emptied, which is
    # what shows the weak tier is the tier deciding it.
    sectioned = TOPICAL_BODY + "\n## Why it will get picked up\n\nThe judge at the terminal stage.\n"
    cls, phrases, basis = ti.classify(sectioned)
    assert (cls, basis) == ("review", "provenance")
    assert sorted(p.lower() for p in phrases) == ["terminal stage", "the judge"]
    saved = dict(ti.WEAK_PATTERNS)
    try:
        ti.WEAK_PATTERNS.clear()
        assert ti.classify(sectioned)[0] == "unstated", "the weak tier was not what decided it"
    finally:
        ti.WEAK_PATTERNS.update(saved)
    saved_strong = dict(ti.STRONG_PATTERNS)
    try:
        ti.STRONG_PATTERNS.clear()
        assert ti.classify(sectioned)[0] == "review", "clearing STRONG must not touch a weak-decided row"
    finally:
        ti.STRONG_PATTERNS.update(saved_strong)


def test_a_provenance_heading_is_read_and_outranks_the_evidence():
    # '## Provenance' names use; '## The evidence' carries a strong review
    # phrase. The heading section decides, and only its own words count.
    cls, phrases, basis = ti.classify(HEADED_PROVENANCE_BODY)
    assert (cls, basis) == ("use", "provenance"), (cls, phrases, basis)
    assert not any("sustained by" in p for p in phrases)


def test_the_might_and_this_heading_variants_are_recognised():
    cls, phrases, basis = ti.classify(MIGHT_VARIANT_BODY)
    assert (cls, basis) == ("review", "provenance"), (cls, phrases, basis)
    section = ti.provenance_text(MIGHT_VARIANT_BODY)
    assert "The judge routed it here" in section
    headed = ti.provenance_text(HEADED_PROVENANCE_BODY)
    assert "Found by the second experience session" in headed      # '## Provenance'
    assert "Value 2 by number" in headed                             # '## Why this will get picked up'
    assert "sustained by the terminal stage" not in headed           # '## The evidence' is not provenance


def test_a_section_runs_to_the_next_heading_and_no_further():
    body = "## Provenance\n\nsurfaced by a seat.\n\n## The want\n\nA consumer hit this.\n"
    section = ti.provenance_text(body)
    assert "surfaced by" in section and "consumer hit" not in section


def test_a_naive_instant_is_utc_not_local():
    assert ti.parse_when("2026-09-25") == ti.parse_when("2026-09-25T00:00:00Z")
    assert ti.parse_when("2026-09-25T00:00:00") == ti.parse_when("2026-09-25T00:00:00+00:00")
    # Negative control: an explicit non-zero offset still moves the instant.
    assert ti.parse_when("2026-09-25T00:00:00+04:00") != ti.parse_when("2026-09-25T00:00:00Z")
    assert ti.parse_when("2026-09-25T00:00:00+04:00").hour == 20


def test_duplicate_rows_from_a_paginated_search_count_once():
    a = _issue(358, "2026-09-04T02:37:27Z", USE_BODY)
    rows = ti.dedupe([a, dict(a), _issue(359, "2026-09-04T03:00:00Z", USE_BODY)])
    assert [r["number"] for r in rows] == [358, 359]


def test_a_capped_fetch_warns_on_stderr(monkeypatch, capsys: pytest.CaptureFixture[str]):
    capped = json.dumps([_issue(n, "2026-09-05T00:00:00Z", USE_BODY) for n in range(ti.FETCH_LIMIT)])
    monkeypatch.setattr(ti, "gh", lambda args: capped)
    ti.fetch_issues(None, ti.parse_when("2026-08-14T00:00:00Z"))
    assert "GitHub's cap" in capsys.readouterr().err
    # Negative control: one under the cap warns of nothing.
    under = json.dumps([_issue(n, "2026-09-05T00:00:00Z", USE_BODY) for n in range(ti.FETCH_LIMIT - 1)])
    monkeypatch.setattr(ti, "gh", lambda args: under)
    ti.fetch_issues(None, ti.parse_when("2026-08-14T00:00:00Z"))
    assert capsys.readouterr().err == ""


def test_the_text_run_carries_the_caveat_and_a_pinned_corpus_is_byte_identical(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    dump = tmp_path / "issues.json"
    dump.write_text(json.dumps([_issue(40, "2026-09-05T00:00:00Z", USE_BODY)]), encoding="utf-8")
    args = ["--from-file", str(dump), "--until", "2026-09-06T00:00:00Z", "--rows"]
    assert ti.main(args) == 0
    first = capsys.readouterr().out
    assert "bodies get edited" in first and "--from-file" in first
    assert ti.main(args) == 0
    assert capsys.readouterr().out == first


def test_empty_body_is_unstated():
    assert ti.classify("")[0] == "unstated"
    assert ti.classify(None)[0] == "unstated"  # type: ignore[arg-type]


def _issue(number: int, created: str, body: str) -> dict:
    return {"number": number, "title": f"t{number}", "createdAt": created, "state": "OPEN", "body": body}


def test_windows_split_on_the_opened_instant_and_count_per_day():
    opened = ti.parse_when("2026-09-04T22:34:00Z")
    start = opened - ti.timedelta(weeks=1)
    end = opened + ti.timedelta(days=2)
    issues = [
        _issue(1, "2026-09-01T00:00:00Z", USE_BODY),         # baseline
        _issue(2, "2026-09-04T22:33:59Z", REVIEW_BODY),      # baseline, one second before
        _issue(3, "2026-09-04T22:34:00Z", REVIEW_BODY),      # trial, the instant itself
        _issue(4, "2026-09-05T12:00:00Z", OWNER_BODY),       # trial
        _issue(5, "2026-09-07T00:00:00Z", USE_BODY),         # after the end: excluded
        _issue(6, "2026-08-01T00:00:00Z", USE_BODY),         # before the start: excluded
    ]
    base = ti.window_rows(issues, start, opened)
    trial = ti.window_rows(issues, opened, end)
    assert [r["number"] for r in base] == [1, 2]
    assert [r["number"] for r in trial] == [3, 4]
    s = ti.summarize(trial, opened, end)
    assert s["total"] == 2 and s["days"] == 2.0
    assert s["counts"]["review"] == 1 and s["counts"]["owner"] == 1
    assert s["per_day"]["review"] == 0.5


def test_cli_reads_a_fixture_file_and_reports_both_windows(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    dump = tmp_path / "issues.json"
    dump.write_text(json.dumps([
        _issue(10, "2026-08-20T00:00:00Z", REVIEW_BODY),
        _issue(11, "2026-09-05T00:00:00Z", USE_BODY),
        _issue(12, "2026-09-05T01:00:00Z", AMBIGUOUS_BODY),
    ]), encoding="utf-8")
    rc = ti.main(["--from-file", str(dump), "--until", "2026-09-06T00:00:00Z", "--rows"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "== baseline:" in out and "== trial:" in out
    assert "#10" in out and "review" in out
    assert "#12" in out and "ambiguous" in out
    assert "1 ambiguous and 0 unstated rows need a reader" in out
    assert out.isascii()


def test_cli_json_is_machine_readable(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    dump = tmp_path / "issues.json"
    dump.write_text(json.dumps([_issue(20, "2026-09-05T00:00:00Z", OWNER_BODY)]), encoding="utf-8")
    rc = ti.main(["--from-file", str(dump), "--until", "2026-09-06T00:00:00Z", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["trial"]["summary"]["counts"]["owner"] == 1
    assert set(data["trial"]["rows"][0]["phrases"]) == {"Owner-directed", "design sitting"}


def test_only_filter_limits_the_rows_and_not_the_counts(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    dump = tmp_path / "issues.json"
    dump.write_text(json.dumps([
        _issue(30, "2026-09-05T00:00:00Z", USE_BODY),
        _issue(31, "2026-09-05T01:00:00Z", UNSTATED_BODY),
    ]), encoding="utf-8")
    rc = ti.main(["--from-file", str(dump), "--until", "2026-09-06T00:00:00Z", "--rows", "--only", "unstated"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "#31" in out and "#30" not in out
    assert "use            1" in out  # the summary still counts every row


def test_a_failing_cli_returns_2_and_names_the_command(monkeypatch, capsys: pytest.CaptureFixture[str]):
    def boom(args):
        raise ti.IntakeError("gh issue list failed: no gh")
    monkeypatch.setattr(ti, "gh", boom)
    rc = ti.main(["--until", "2026-09-06T00:00:00Z"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "trial_intake: gh issue list failed" in err
