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
WARNING_SYMBOL = chr(0x26A0) + chr(0xFE0F)
MAJOR_SYMBOL = chr(0x1F7E0)
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


SHARED_CASES = json.loads(FIXTURE.read_bytes())['cases']


@pytest.mark.parametrize('case', SHARED_CASES, ids=lambda c: c['name'])
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
    f'fixed - [{ID}]({URL}) and [cr-comment:v1:beta]({URL})',
    f'fixed - repaired\n```\n[{ID}]({URL})\n```',
])
def test_wrong_opening_identity_or_target_answers_nothing(body):
    assert len(classify(answers=[comment(body)]).missing_findings) == 1


def test_supporting_commit_and_issue_links_do_not_bundle_targets():
    body = f'fixed - repaired in [commit](https://github.com/example/product/commit/abc); '
    body += f'[{ID}]({URL}); [issue](https://github.com/example/product/issues/9)'
    assert not classify(answers=[comment(body)]).missing_findings


def test_non_obligation_review_link_is_supporting_evidence():
    codex = 'chatgpt-codex-connector[bot]'
    body = (f"fixed - as noted in [Codex's review]({URL.replace('-100', '-200')}); "
            f'[{ID}]({URL})')
    result = rf.classify('example/product', 7,
                         [review(), review('Opening note.', identity=200, login=codex)],
                         [], [comment(body)], [CR, codex], ['holder'], work._disposition)
    assert not result.missing_findings and not result.missing_reviews


def test_identity_in_evidence_link_label_does_not_bundle_or_answer_that_identity():
    beta = 'cr-comment:v1:beta'
    body = (f'yours - in the release report; see [my earlier note on {beta}]('
            'https://github.com/example/product/pull/7#issuecomment-556); '
            f'[{ID}]({URL})')
    result = classify([review(), review(f'<!-- {beta} -->', identity=300)],
                      answers=[comment(body)])
    assert [finding.identity for finding in result.missing_findings] == [beta]
    assert not result.missing_reviews


@pytest.mark.parametrize('evidence', [
    '',
    '[release report](https://github.com/example/product/pull/7#issuecomment-555); ',
    '[#9](https://github.com/example/product/issues/9); ',
    '[abc](https://github.com/example/product/commit/abc1234); ',
    'cr-comment:v1:beta; ',
    f'[review]({URL.replace("-100", "-101")}); ',
    '[cr-comment:v1:beta](https://github.com/example/product/pull/8#pullrequestreview-300); ',
])
def test_each_evidence_link_form_preserves_the_canonical_answer(evidence):
    assert not classify(answers=[comment(f'fixed - repaired; {evidence}[{ID}]({URL})')]).missing_findings


@pytest.mark.parametrize('whole_review', [False, True])
def test_two_obligation_source_links_cannot_bundle_answers(whole_review):
    beta = 'cr-comment:v1:beta'
    first = review('1 validated finding(s).', login=LAB) if whole_review else review()
    label = 'unidentified review' if whole_review else ID
    body = f'fixed - repaired; [{label}]({URL}); [{beta}]({URL.replace("-100", "-300")})'
    result = classify([first, review(f'<!-- {beta} -->', identity=300)], answers=[comment(body)])
    assert len(result.missing_findings) == (1 if whole_review else 2)
    assert len(result.missing_reviews) == (1 if whole_review else 0)


@pytest.mark.parametrize('body', [
    'fixed - everything is done',
    f'fixed - [unidentified review]({URL.replace("-100", "-101")})',
    f'fixed - [unidentified review]({URL}.extra)',
])
def test_fallback_requires_one_exact_link(body):
    result = classify([review('1 validated finding(s).', login=LAB)], answers=[comment(body)])
    assert len(result.missing_reviews) == 1


@pytest.mark.parametrize('evidence', [
    f'[another]({URL.replace("-100", "-101")})',
    'cr-comment:v1:beta',
    '[cr-comment:v1:beta](https://github.com/example/product/pull/7#issuecomment-556)',
])
def test_whole_review_answer_ignores_evidence_links_and_identity_text(evidence):
    result = classify([review('1 validated finding(s).', login=LAB)],
                      answers=[comment(f'fixed - addressed; {evidence}; [unidentified review]({URL})')])
    assert not result.missing_reviews
    assert result.unidentified_reviews[0].answered


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


def test_declared_empty_section_cannot_hide_an_inline_finding():
    root = {'id': 10, 'pull_request_review_id': 100, 'user': {'login': 'review-bot'}, 'body': 'finding'}
    assert classify([review('## Findings\nNo findings.', login='review-bot')], [root]).missing_reviews


@pytest.mark.parametrize('opening', [
    'declined - [outside the brief](https://github.com/example/product/issues/9)',
    'duplicate of [the earlier comment](https://github.com/example/product/pull/7#discussion_r10)',
    'lapsed - [the retired rule](https://github.com/example/product/commit/abc)',
])
def test_required_continuation_may_link_its_supporting_evidence(opening):
    assert not classify(answers=[comment(f'{opening}; [{ID}]({URL})')]).missing_findings


@pytest.mark.parametrize('route', ['body', 'whole-review', 'inline-exemption'])
def test_mixed_case_logins_preserve_authorized_answers_and_exemptions(route):
    body = MARKER if route != 'whole-review' else '**Actionable comments posted: 1**'
    reviews = [review(body, login='CodeRabbitAI[bot]')]
    inline, answers = [], []
    if route == 'inline-exemption':
        inline = [
            {'id': 10, 'pull_request_review_id': 100,
             'user': {'login': 'CodeRabbitAI[bot]'}, 'body': MARKER},
            {'id': 11, 'in_reply_to_id': 10,
             'user': {'login': 'Grimblaz'}, 'body': '**fixed** - repaired'},
        ]
    else:
        label = ID if route == 'body' else 'unidentified review'
        answers = [comment(f'fixed - repaired; [{label}]({URL})', login='Grimblaz')]
    result = rf.classify('example/product', 7, reviews, inline, answers,
                         [CR], ['grimblaz'], work._disposition)
    assert not result.missing_findings and not result.missing_reviews
    assert not result.ignored_authors
    if route == 'whole-review':
        assert result.unidentified_reviews[0].answered
    else:
        assert result.findings[0].reviewer == CR and result.findings[0].answered


def test_next_summary_ends_bold_section_before_its_identity_can_mask_a_deficit():
    body = ('> **Outside diff range comments (1)**\n'
            '> <details><summary><em>Major</em> real.py:40</summary>\n'
            '> Fix the off-diff bug.\n> </details>\n'
            '<details><summary>Nitpick comments (1)</summary>\n'
            '<!-- cr-comment:v1:beta -->\n</details>')
    result = classify([review(body)])
    assert [item.identity for item in result.findings] == ['cr-comment:v1:beta']
    assert result.unidentified_reviews[0].reasons == [
        'unaccounted findings section: Outside diff range comments (1)',
    ]


def test_counted_prose_section_cannot_spend_an_inline_root_as_its_body_identity():
    root = {'id': 10, 'pull_request_review_id': 100,
            'user': {'login': 'review-bot'}, 'body': 'inline finding'}
    body = '## Findings (1)\nThe loader drops the last row; fix the bounds check.'
    result = classify([review(body, login='review-bot')], [root])
    assert not result.findings
    assert result.unidentified_reviews[0].reasons == [
        'unaccounted findings section: Findings (1)',
    ]


def test_inline_code_paragraph_boundary_preserves_live_declarations_and_identities():
    body = ('**Actionable comments posted: 0**\n\nA lone ` backtick in prose.\n\n'
            '<details><summary>Outside diff range comments (1)</summary>\n'
            '`app.py` line 3: fix\n' + MARKER + '\n`done`\n</details>')
    result = classify([review(body)])
    assert [item.identity for item in result.missing_findings] == [ID]
    assert not result.unidentified_reviews


@pytest.mark.parametrize('title', [
    'Security Findings', 'Security Findings and Attack Paths',
    'Security Findings comments (1)', 'Other comments (unknown)', 'Other comments (two places)',
    'Prefix **Other comments (1)**',
])
def test_coderabbit_requires_a_whole_structural_counted_comments_title(title):
    for body in (f'<details><summary>{title}</summary>\n- something risky\n</details>',
                 f'**{title}**\n- something risky', f'## {title}\n- something risky'):
        assert not classify([review(body)]).unidentified_reviews


@pytest.mark.parametrize('title', [
    'Other comments (1)', WARNING_SYMBOL + ' Other comments (1)',
    WARNING_SYMBOL + ' Other\ncomments (1)',
])
def test_coderabbit_summary_and_bold_titles_support_symbols_and_line_wrapping(title):
    for body in (f'<details><summary>{title}</summary>\n{MARKER}\n</details>',
                 '> **' + title.replace('\n', '\n> ') + '**\n' + MARKER):
        result = classify([review(body)])
        assert len(result.missing_findings) == 1 and not result.unidentified_reviews
        assert classify([review(body.replace(MARKER, 'No identity supplied.'))]).missing_reviews


def test_inner_finding_details_and_nondeclaration_summaries_do_not_end_a_section():
    body = (f'> **{WARNING_SYMBOL} Outside diff range comments (1)**\n'
            f'> <details><summary><em>{MAJOR_SYMBOL} Major</em> real.py:40</summary>\n'
            '> <details><summary>Proposed fix</summary>\n> example\n> </details>\n'
            '> ' + MARKER + '\n> </details>')
    result = classify([review(body)])
    assert len(result.missing_findings) == 1 and not result.unidentified_reviews


def test_nested_summary_candidate_is_content_of_the_declared_parent():
    body = ('<details><summary>Other comments (1)</summary>\n'
            '<details><summary>Nitpick comments (1)</summary>\n' + MARKER
            + '\n</details>\n</details>')
    result = classify([review(body)])
    assert not result.unidentified_reviews
    assert [finding.identity for finding in result.missing_findings] == [ID]


@pytest.mark.parametrize('content', ['', 'None.', 'No findings.', 'No findings were found.'])
def test_empty_counted_findings_section_can_account_for_its_inline_root(content):
    root = {'id': 10, 'pull_request_review_id': 100,
            'user': {'login': 'review-bot'}, 'body': 'inline finding'}
    body = '## Findings (1)\n' + content
    assert not classify([review(body, login='review-bot')], [root]).unidentified_reviews


@pytest.mark.parametrize('title', ['Outside diff findings (1)', 'Other comments (1)'])
def test_other_reviewers_declare_only_titles_starting_with_findings(title):
    assert not classify([review(f'## {title}\n- prose', login='review-bot')]).unidentified_reviews


@pytest.mark.parametrize('blank', ['\n\n', '\n \t\n', '\n> \n', '\r\n\r\n'])
def test_inline_code_cannot_cross_a_blank_line(blank):
    text = 'An unmatched ` backtick.' + blank + MARKER + '\n`paired`'
    assert MARKER in rf.live_markup(text)


def test_unmatched_backticks_blank_nothing_but_valid_multiline_spans_still_do():
    assert MARKER in rf.live_markup('A lone `\n' + MARKER)
    assert MARKER not in rf.live_markup('`an example\n' + MARKER + '`')


def test_actionable_declaration_words_in_prose_do_not_declare_a_count():
    assert not classify([review('The label Actionable comments posted: N describes the UI.')]).unidentified_reviews


def test_counted_comments_section_cannot_hide_an_entry_without_an_identity():
    body = '<details><summary>Other comments (1)</summary>\n- First\n' + MARKER + '\n- Second\n</details>'
    assert classify([review(body)]).unidentified_reviews


def test_counted_comments_section_with_zero_identities_cannot_hide_prose():
    assert classify([review('<details><summary>Other comments (0)</summary>\n'
                            'An unaccounted body entry.\n</details>')]).unidentified_reviews


def test_correct_bold_and_summary_sections_need_no_divider():
    body = ('> **Outside diff range comments (1)**\n'
            '> <details><summary><em>Major</em> real.py:40</summary>\n> ' + MARKER
            + '\n> </details>\n'
            '<details><summary>Nitpick comments (1)</summary>\n'
            '<!-- cr-comment:v1:beta -->\n</details>')
    result = classify([review(body)])
    assert len(result.findings) == 2 and not result.unidentified_reviews


def test_coderabbit_file_group_can_hold_distinct_identified_entries():
    body = ('<details><summary>Nitpick comments (2)</summary>\n'
            '<details><summary>app.py (2)</summary>\n' + MARKER
            + '\n<!-- cr-comment:v1:beta -->\n</details>\n</details>')
    result = classify([review(body)])
    assert len(result.findings) == 2 and not result.unidentified_reviews


@pytest.mark.parametrize('content', [
    '- First supporting point\n- Second supporting point',
    f'<details><summary>{chr(0x1F9E9)} Analysis chain</summary>\n'
    '- Supporting analysis\n---\nMore analysis.\n</details>',
    '**Update stale code comments (two places)**',
    '**Remove two stale comments (2)**',
    '<details><summary>Other comments (2)</summary>\nSupporting text.\n</details>',
], ids=['prose-bullets', 'analysis-divider', 'bold-two-places', 'bold-digit-count', 'nested-summary'])
def test_finding_content_uses_only_the_declared_sections_depth(content):
    body = ('<details><summary>Nitpick comments (1)</summary>\n'
            '<details><summary>app.py (1)</summary>\n' + content + '\n' + MARKER
            + '\n</details>\n</details>')
    result = classify([review(body)], answers=[comment(f'fixed - repaired; [{ID}]({URL})')])
    assert len(result.findings) == 1 and result.findings[0].answered
    assert not result.unidentified_reviews


@pytest.mark.parametrize('summary', [False, True])
def test_divider_at_the_declared_sections_own_depth_still_ends_it(summary):
    body = ('<details><summary>Nitpick comments (1)</summary>\n' if summary
            else '> **Outside diff range comments (1)**\n')
    body += '<details><summary>app.py (1)</summary>\nNo identity here.\n</details>\n---\n' + MARKER
    if summary:
        body += '\n</details>'
    result = classify([review(body)])
    assert len(result.unidentified_reviews) == 1
    assert [finding.identity for finding in result.missing_findings] == [ID]


def test_divider_ends_bold_section_before_a_later_nested_declaration():
    body = ('**Other comments (0)**\nNone.\n---\n'
            '<details><summary>Wrapper</summary>\n'
            '<details><summary>Nitpick comments (1)</summary>\n' + MARKER
            + '\n</details>\n</details>')
    assert not classify([review(body)]).unidentified_reviews


@pytest.mark.parametrize('whole_review', [False, True])
def test_answer_repository_names_compare_case_insensitively(whole_review):
    source = review('1 validated finding(s).', login=LAB) if whole_review else review()
    label = 'unidentified review' if whole_review else ID
    url = URL.replace('example/product', 'Example/Product')
    result = classify([source], answers=[comment(f'fixed - repaired; [{label}]({url})')])
    assert not result.missing_findings and not result.missing_reviews
