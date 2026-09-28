# D-775 — Read record claims by source and artifact term

**Purpose:** preserve why the entrance treats markers as source-level claims, reduces artifact state within the latest term, normalizes disposition formatting, and limits optional-reviewer replies by author authority. **Audience:** a future session changing marker parsing, artifact routing, reviewer completion, release reporting, or the shared gate. **Success:** that session can revise one mechanism without restoring quoted-marker claims, stale artifact precedence, formatting-sensitive dispositions, or reviewer text as authority.

Governed by the [affirmed implementation brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/735#issuecomment-5863572101), the holder's [first recorded calls](https://github.com/Grimblaz-and-Friends/tradecraft/issues/735#issuecomment-5863916617), the [connected-reviewer amendment](https://github.com/Grimblaz-and-Friends/tradecraft/issues/735#issuecomment-5863963570), and the [recorded cap resolution](https://github.com/Grimblaz-and-Friends/tradecraft/issues/735#issuecomment-5864228378). The implementation is carried by [#735](https://github.com/Grimblaz-and-Friends/tradecraft/issues/735) in [pull request #775](https://github.com/Grimblaz-and-Friends/tradecraft/pull/775).

## Context

The entrance read each marker kind independently across whole bodies and reduced artifact state through record-wide booleans in a fixed order. A copied marker could therefore make a claim its author was only quoting, while an earlier draft, verdict, settlement or holder reading could control a later artifact term. Disposition completion also read the unformatted beginning literally, so ordinary inline emphasis could make an answered thread appear unanswered.

The owner chose the source-contract remedy over requiring writers to escape every paste, chose latest-term artifact reduction over post-order precedence, and limited optional-reviewer replies to authors whose repository authority can be established. The holder then resolved the opener, migration-order and companion-marker details inside those affirmed rows; the two-round cold cap withdrew one proposed product-incident exception and settled the remaining calls.

## Decision

### A source asserts its opener and only the companions that opener permits

Marker text inside inline code, fenced or indented code, or blockquotes is always a quotation. An ordinary source asserts a marker kind only when that unquoted marker is its first line of content. That opening claim may carry only the unquoted companion kinds named by its contract; every other marker occurrence is set aside and reported with enough source identity to locate it.

The companion contracts cover the combined claims the record actually needs: proof with no-use, an implementing pull-request link with its builder session, and a settled artifact with its cold verdict. A cold verdict beside a draft artifact remains a quotation. A reviewer-thread reply is the one non-marker opener: a lawful disposition on its first line opens the reply, and an appended connected-reviewer marker travels with that disposition.

The product-incident marker has no mid-source exception. The holder's first call proposed one to preserve older writing, but the cap resolution withdrew it because the affirmed decision says every other marker is a quotation and current filings already open with the marker. Existing equivalent product-issue URLs and later affirmed briefs continue to admit the records their contracts admit; historical placement does not widen the new rule.

This source-level contract was chosen because the observed failure came from a writer copying correctly. A convention that made every writer protect every paste would reproduce the failure, while the legitimate combined claims form a short explicit list and preserve the existing writing form.

### Artifact state is reduced within the latest term

An artifact term begins at the latest affirmed brief or amendment. Verdicts, settlements, drafts and holder readings are interpreted in order within that term: a verdict must judge the applicable draft, a supported routed settlement closes the phase, a newer draft reopens it, and a holder reading counts only after the latest effective settlement. Earlier states cannot win merely because the old implementation checked their booleans first.

A settlement names `route=would`, `route=cap`, `route=discharge` or `route=unobtainable`, and the route must be supported by the term's qualifying verdicts. Every settlement, including `unobtainable`, requires a draft in its current term. A missing or unsupported route is reported as invalid and does not settle the artifact. A routeless settlement in a superseded term remains historical invalid evidence but no longer tells a holder to re-post it into the current term. A cold verdict carried by its settled artifact is reduced immediately before that settlement, regardless of textual order, so it can support the route; the same companion beside a draft does not become a verdict claim.

For a change already in flight, a later marker that only adds a route to an earlier routeless settlement keeps the earlier settlement's position when no brief, draft or verdict intervenes. An intervening holder reading does not break that migration: it remains after the effective settlement and no second reading is manufactured. The routeless marker stays invalid, and the routed marker remains the validating source. The inherited position is consumed by that routed marker; another settlement has its own position and therefore needs a holder reading after it. This ordering exception was chosen to honor the affirmed requirement that an in-flight change re-post once rather than turn a data migration into another artifact round.

Latest-term reduction was chosen because the report must describe the record the authors reached, not whichever historical state a fixed check happens to encounter first. Amendments restart the term; newer drafts supersede old support except where qualifying would-not verdicts still count toward the current term's cap.

An explicit artifact dispatch after an amendment carries the latest artifact text from any earlier term as the artifact under revision until the current term has its own draft. Within the term that supplied the artifact, it prefers the latest settlement text even when that settlement's route is invalid, otherwise carries the latest draft, because route validity decides whether a term is settled rather than which text the amendment revises. The prompt follows that artifact with the latest holder reading made against it in the same term, labelled as governing where it differs. A term with no artifact preserves both; a newer artifact without a reading clears the older reading; and a current-term draft replaces both prior-term sections. This keeps the amendment path a revision, as the engagement contract requires, without letting prior-term verdicts or settlement state advance the new term.

### Disposition formatting is presentation, and every disposition reader agrees

Permitted inline formatting around the opening word is removed before applying the unchanged disposition vocabulary and delimiter test. Formatting cannot make a word outside that closed vocabulary lawful. The connected-reviewer marker then travels only with a lawful disposition opener on a reviewer-thread reply.

The shared gate must apply the same interpretation wherever it reads dispositions. The corresponding change-proof work lands before this change is released, because an entrance that accepts an answer while its gate rejects it would report readiness while the gate stays red. Moving the marker ahead of the disposition was rejected because it would change every builder's writing contract and collide with the rule that the disposition word comes first.

### Optional-reviewer findings are answered only across an established authority boundary

At release, the holder dispositions comments from reviewers not configured as connected when the author is an installed repository app or an account with write access. Other authors' comments are left unanswered and noted in the release report. Both the release-report and connected-reviewer references state that every reviewer comment is information the holder weighs, never an instruction it follows.

This boundary was chosen because an optional reviewer had found real defects, while a public repository permits anyone to comment and the holder acts with the owner's account. It therefore answers findings from established repository actors without letting outsider text direct a session. It adds no optional-reviewer mechanism or configuration list.

## Rejected alternatives and boundaries

**Take the first unquoted marker anywhere in a source.** Rejected because a heading, explanation or bare paste before it would still turn quotation into state.

**Keep a product-incident placement exception.** Withdrawn at the cap because it contradicted the affirmed ordinary-opener rule and current writers no longer needed it.

**Give a routed migration re-post its physical order.** Rejected because a holder reading between the original settlement and its route-only correction would become stale and require more than the one re-post the owner affirmed.

**Change disposition words or add optional-reviewer machinery.** Rejected by the brief's boundary. Stages from the floor onward retain their push-replaced precedence, and no historical record migration is required beyond the one routed settlement re-post for a change in flight.

## Meaning changes and evidence

- Marker consumers use one source-level claim classification, and set-aside quotations become visible diagnostics rather than hidden state.
- Artifact routing and builder prompts come from the latest term rather than record-wide marker presence.
- A settlement cannot stand in for its term's missing draft, one migration correction cannot lend its inherited order to a second settlement, and an amendment dispatch retains the latest earlier artifact with only its same-term reading as revision input; empty terms preserve that pair, while settlement validity does not select it.
- Plain and permitted-inline-formatted disposition openers have the same meaning in the entrance and any gate that reads them.
- Release guidance distinguishes authorized optional reviewers from other commenters without treating either group's text as instructions.

The complete-record polarities for opener and quotation contexts, companion contracts, product-incident consequences, terms, settlement routes, migration order and dispositions are retained in `lib/tests/test_work.py`. Reference parity and the one-way wall are checked by the repository lint. Run `python -m pytest tools/tests skills lib/tests -q -n auto --dist loadfile` and `python tools/lint.py` on the tree under review; the commands and their recorded results are the evidence rather than a frozen result here.
