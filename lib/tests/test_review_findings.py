import copy
import json
from pathlib import Path
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import review_findings as rf
import work


CR = 'coderabbitai[bot]'
LAB = 'github-actions[bot]'
ID = 'cr-comment:v1:alpha'
URL = 'https://github.com/example/product/pull/7#pullrequestreview-100'
MARKER = f'<!-- {ID} -->'
FIXTURE = (LIB.parent / 'skills' / 'work' / 'references' / 'proof-fixtures'
           / 'v1-review-body-dispositions.json')


def review(body=MARKER, identity=100, login=CR):
    return {'id': identity, 'state': 'COMMENTED', 'user': {'login': login}, 'body': body}


def comment(body, login='holder'):
    return {'id': 200, 'user': {'login': login}, 'body': body}


def classify(reviews=None, inline=(), answers=()):
    return rf.classify('example/product', 7, reviews or [review()], list(inline), list(answers),
                       [CR, LAB, 'review-bot'], ['holder'], work._disposition)


def snapshot(result):
    return {
        'missing_findings': [{'reviewer': finding.reviewer, 'identity': finding.identity,
                              'sources': [source['id'] for source in finding.sources]}
                             for finding in result.missing_findings],
        'missing_reviews': [item.review['id'] for item in result.missing_reviews],
        'unidentified_reviews': [item.review['id'] for item in result.unidentified_reviews],
        'ignored_authors': result.ignored_authors,
    }


SHARED_CASES = (json.loads(FIXTURE.read_bytes())['cases'] if FIXTURE.is_file() else [
    pytest.param(None, marks=pytest.mark.skip(
        reason='shared fixtures are absent from a relocated lib-only copy'), id='lib-only'),
])


@pytest.mark.parametrize('case', SHARED_CASES, ids=lambda c: c['name'] if c else 'lib-only')
def test_shared_live_record_cases(case):
    result = rf.classify(case['repository'], case['pull_request'], case['reviews'],
                         case['inline_comments'], case['conversation_comments'],
                         case['connected_reviewers'], case['marker_producers'], work._disposition)
    assert snapshot(result) == case['expected']


@pytest.mark.parametrize('disposition', [
    'fixed', 'fixed - nothing else found it', 'fixed in #12',
    'yours - in the release report', 'declined - not applicable',
    'duplicate of the earlier comment', 'lapsed - the retired rule',
])
def test_every_existing_disposition_answers_one_finding(disposition):
    result = classify(answers=[comment(f'\n{disposition}; [{ID}]({URL})')])
    assert not result.missing_findings
    assert not result.missing_reviews


@pytest.mark.parametrize('body', [
    f'**fixed** - repaired; [{ID}]({URL})',
    f'`fixed` - repaired; [{ID}]({URL})',
    f'> fixed - repaired; [{ID}]({URL})',
    f'fixedness - repaired; [{ID}]({URL})',
    f'declined; [{ID}]({URL})',
    f'declined - ; [{ID}]({URL})',
    f'duplicate of ; [{ID}]({URL})',
    f'fixed - {ID}',
    f'fixed - [different]({URL})',
    f'fixed - {ID}; [review]({URL})',
    f'fixed - [{ID}extra]({URL})',
    f'fixed - [{ID}]({URL.replace("-100", "-10")})',
    f'fixed - [{ID}]({URL.replace("pull/7", "pull/8")})',
    f'fixed - [{ID}]({URL.replace("example/product", "example/other")})',
    f'fixed - [{ID}]({URL}.extra)',
    f'fixed - [{ID}]({URL}?x=1)',
    f'fixed - [{ID}]({URL}) and [review]({URL.replace("-100", "-101")})',
    f'fixed - [{ID}]({URL}) and [cr-comment:v1:beta]({URL})',
    f'fixed - [{ID}]({URL}) and cr-comment:v1:beta',
    f'fixed - repaired\n```\n[{ID}]({URL})\n```',
])
def test_wrong_opening_identity_or_target_answers_nothing(body):
    assert len(classify(answers=[comment(body)]).missing_findings) == 1


def test_supporting_commit_and_issue_links_do_not_bundle_targets():
    body = f'fixed - repaired in [commit](https://github.com/example/product/commit/abc); '
    body += f'[{ID}]({URL}); [issue](https://github.com/example/product/issues/9)'
    assert not classify(answers=[comment(body)]).missing_findings


@pytest.mark.parametrize('body', [
    'fixed - everything is done',
    f'fixed - [unidentified review]({URL.replace("-100", "-101")})',
    f'fixed - [unidentified review]({URL}.extra)',
    f'fixed - [unidentified review]({URL}) and [another]({URL.replace("-100", "-101")})',
])
def test_fallback_requires_one_exact_link(body):
    result = classify([review('1 validated finding(s).', login=LAB)], answers=[comment(body)])
    assert len(result.missing_reviews) == 1


def test_whole_review_answer_stays_classified_and_cannot_replace_inline_reply():
    root = {'id': 10, 'pull_request_review_id': 100, 'user': {'login': LAB}, 'body': 'finding'}
    result = classify([review('2 validated finding(s).', login=LAB)], [root],
                      [comment(f'fixed - repaired; [unidentified review]({URL})')])
    assert len(result.unidentified_reviews) == 1
    assert not result.missing_reviews
    state = work.WorkState('example/product', 9, {}, pr={'number': 7}, reviews=[],
                           review_comments=[root], config=work.WorkConfig(
                               connected_reviewers=(LAB,), marker_producers=('holder',)))
    assert work._undisposed_threads(state)[0] == [10]


@pytest.mark.parametrize('code', [
    f'```html\n{MARKER}\n```', f'~~~\n{MARKER}\n~~~',
    f'> ```\n> {MARKER}\n> ```', f'``{MARKER}``',
    f'<pre>{MARKER}</pre>', f'<code>{MARKER}</code>',
    f'    {MARKER}',
    f'```html\n{MARKER}',
])
def test_marker_examples_have_no_accounting_credit(code):
    result = classify([review(f'<details><summary>Other comments (1)</summary>\n{code}\n</details>')])
    assert not result.findings
    assert len(result.missing_reviews) == 1


@pytest.mark.parametrize('declaration', [
    '**Actionable comments posted: 2**', '**Actionable comments posted: unknown**',
    '**Actionable comments posted: 0**\n**Actionable comments posted: 0**',
    '<details><summary>Nitpick comments (unknown)</summary>\n</details>',
    '<details><summary>Nitpick comments (1)</summary>\n</details>',
])
def test_bad_declarations_are_never_complete(declaration):
    assert classify([review(declaration)]).missing_reviews


def test_inline_and_body_identity_union_is_local_to_each_review():
    identity = 'tradecraft-review-finding:v1:91:1'
    marker = f'<!-- {identity} -->'
    root = {'id': 10, 'pull_request_review_id': 100, 'user': {'login': LAB}, 'body': marker}
    result = classify([review(f'1 validated finding(s).\n{marker}', login=LAB)], [root])
    assert not result.missing_reviews
    assert len(result.missing_findings) == 1
    different = copy.deepcopy(root)
    different['pull_request_review_id'] = 101
    result = classify([review('1 validated finding(s).', login=LAB)], [different])
    assert result.missing_reviews


def test_multiple_inline_identities_cannot_grant_an_exemption():
    root = {'id': 10, 'pull_request_review_id': 100, 'user': {'login': CR},
            'body': MARKER + '\n<!-- cr-comment:v1:beta -->'}
    reply = {'id': 11, 'in_reply_to_id': 10, 'user': {'login': 'holder'}, 'body': 'fixed'}
    result = classify([review(MARKER)], [root, reply])
    assert result.missing_findings and result.missing_reviews


def test_another_pr_thread_cannot_exempt_this_prs_finding():
    root = {'id': 10, 'pull_request_review_id': 100, 'user': {'login': CR}, 'body': MARKER,
            'html_url': 'https://github.com/example/product/pull/8#discussion_r10'}
    reply = {'id': 11, 'in_reply_to_id': 10, 'user': {'login': 'holder'}, 'body': 'fixed'}
    assert classify(inline=[root, reply]).missing_findings


def test_another_pr_reply_cannot_exempt_this_prs_finding():
    root = {'id': 10, 'pull_request_review_id': 100, 'user': {'login': CR}, 'body': MARKER}
    reply = {'id': 11, 'in_reply_to_id': 10, 'user': {'login': 'holder'}, 'body': 'fixed',
             'html_url': 'https://github.com/example/product/pull/8#discussion_r11'}
    assert classify(inline=[root, reply]).missing_findings


def test_generic_numeric_declaration_accounts_for_its_inline_roots():
    root = {'id': 10, 'pull_request_review_id': 100, 'user': {'login': 'review-bot'}, 'body': 'finding'}
    assert not classify([review('1 finding.', login='review-bot')], [root]).missing_reviews
    assert classify([review('2 findings.', login='review-bot')], [root]).missing_reviews


def test_conflicting_lab_attempt_does_not_establish_completeness():
    result = classify([review('1 validated finding(s).\n'
        '<!-- tradecraft-review-finding:v1:90:1 -->\n<!-- connected-review-attempt:91 -->', login=LAB)])
    assert result.missing_reviews
    assert result.missing_findings[0].identity == 'tradecraft-review-finding:v1:90:1'


def test_known_identity_producer_must_still_be_configured():
    result = rf.classify('example/product', 7, [review()], [], [], [], ['holder'], work._disposition)
    assert not result.findings and not result.unidentified_reviews


def test_authorized_inline_reply_must_be_a_lawful_disposition():
    root = {'id': 10, 'pull_request_review_id': 100, 'user': {'login': CR}, 'body': MARKER}
    reply = {'id': 11, 'in_reply_to_id': 10, 'user': {'login': 'holder'}, 'body': 'I saw this.'}
    assert classify(inline=[root, reply]).missing_findings


def test_finding_titles_and_bold_summary_prose_are_not_section_declarations():
    assert not classify([review('**Some comments**\nReview summary.')]).unidentified_reviews
    result = classify([review('1 validated finding(s).\n'
        '**P1 - Reader skips comments**\n<!-- tradecraft-review-finding:v1:91:1 -->', login=LAB)])
    assert not result.unidentified_reviews
    assert len(result.findings) == 1


def test_bold_finding_title_cannot_end_a_declared_outside_diff_section():
    body = '**Outside diff range comments (1)**\n<details><summary>app.py</summary>\n'
    body += '**Fix the comments**\n' + MARKER + '\n</details>'
    result = classify([review(body)])
    assert len(result.findings) == 1 and not result.unidentified_reviews


def test_generic_section_total_can_be_entirely_inline_but_cannot_hide_body_entries():
    root = {'id': 10, 'pull_request_review_id': 100, 'user': {'login': 'review-bot'}, 'body': 'finding'}
    result = classify([review('## Findings (1)', login='review-bot')], [root])
    assert not result.unidentified_reviews
    result = classify([review('## Findings (1)\n- An unidentified body finding', login='review-bot')], [root])
    assert result.unidentified_reviews


def test_dismissing_a_submitted_review_does_not_answer_its_findings():
    result = classify([{**review(), 'state': 'DISMISSED'}])
    assert len(result.missing_findings) == 1


@pytest.mark.parametrize('login, body', [
    (CR, '**Actionable comments posted: {count}**'),
    (CR, '<details><summary>Nitpick comments ({count})</summary></details>'),
    (LAB, '{count} validated finding(s).'),
    ('review-bot', 'Findings: {count}'),
])
def test_oversized_numeric_declaration_is_unidentified_instead_of_a_parse_error(login, body):
    assert classify([review(body.format(count='9' * 5000), login=login)]).missing_reviews


@pytest.mark.parametrize('statement', ['None.', 'No findings.', 'No findings were found.'])
def test_explicitly_empty_findings_section_needs_no_whole_review_answer(statement):
    assert not classify([review('## Findings\n' + statement, login='review-bot')]).unidentified_reviews


def test_declared_empty_section_cannot_hide_a_real_identity_or_inline_finding():
    assert classify([review('## Findings\nNo findings.\n' + MARKER)]).missing_reviews
    root = {'id': 10, 'pull_request_review_id': 100, 'user': {'login': 'review-bot'}, 'body': 'finding'}
    assert classify([review('## Findings\nNo findings.', login='review-bot')], [root]).missing_reviews


@pytest.mark.parametrize('opening', [
    'declined - [outside the brief](https://github.com/example/product/issues/9)',
    'duplicate of [the earlier comment](https://github.com/example/product/pull/7#discussion_r10)',
    'lapsed - [the retired rule](https://github.com/example/product/commit/abc)',
])
def test_required_continuation_may_link_its_supporting_evidence(opening):
    assert not classify(answers=[comment(f'{opening}; [{ID}]({URL})')]).missing_findings
