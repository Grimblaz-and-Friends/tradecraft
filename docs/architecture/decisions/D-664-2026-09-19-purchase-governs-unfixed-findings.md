# D-664 — Purchase governs unfixed findings; repairs stop at the existing rule's scope

**Status:** Accepted 2026-09-19 (PR #664)

This change closes [#660](https://github.com/Grimblaz-and-Friends/tradecraft/issues/660). It is governed by the [implementation brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/660#issuecomment-5743143704), its [amendment](https://github.com/Grimblaz-and-Friends/tradecraft/issues/660#issuecomment-5743242253), and the [settled artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/660#issuecomment-5743317226). The built tree is pinned at `f8836fd` over base `4ea42fd`.

## Context

The second experience session on PR #654 obeyed the amended filing rule and filed nothing, but gave *no board* rather than *no purchase* as its reason. The holder made four related routing errors while landing that same amendment. The text had the invariant below the list of ends, mixed a session's two ends with the owner's three named answers, left four live references to the retired count, preserved the withdrawn mechanical exception in its owning cell, and stated the doctrine's mechanical exemption beyond the convergence gate it belongs to.

The owner's push on 2026-09-19 settled both the answer vocabulary and the breadth of this repair: *“Are do it and buy it later really different? There seem to just be 2 splits to me, and timing depends on when I actually start the issue.”* He chose the repairs-only shape from the three offered shapes.

## Decision

### 1. The owner's answer is bought or not bought, not a scheduling vocabulary

*Do it* and *buy it for later* both produce an issue; they differ only in when the owner starts it. That timing belongs to the repository's ordering, which the unchanged closing sentence of `skills/filing/SKILL.md` at `f8836fd` already disclaims: a repository chooses how it marks and orders decided work, while this cell owns what the issue carries. The old three-word vocabulary in `skills/filing/SKILL.md` at `4ea42fd` therefore smuggled scheduling into a cell that says scheduling is not its subject.

The surviving distinction is the product of the answer. `skills/filing/SKILL.md` at `f8836fd` now says that bought work creates an issue carrying what the ask knew and is picked up fresh rather than continued by the session that raised it; not-bought work creates nothing and is declined on the work. **Rejected:** retaining *do it*, *buy it for later*, and *drop it*, because the first two name timing rather than different outcomes and leave the first answer's product unstated.

### 2. No general rule is added

This incident needs repairs, not a third statement of the general rule. `skills/charter/SKILL.md` at `f8836fd` already says that a concept reaches an unanticipated case while a rule reaches only the case it names. `skills/authoring/references/revising.md` at `f8836fd` already names the amendment defect: a sentence left verbatim while a term it turns on is redefined. The charter also forbids a second copy of what a cell can hold.

**Rejected:** a proximity clause in `authoring` requiring a rule's reason to travel to every point of use; a required clause in the release report's ask explaining why a finding is not fixed now; and adding holder misrouting to the close-out scored by #652. The owner chose shape A, repairs only. No new instrument or obligation lands, and recurrence rather than this one incident is what could supply the evidence for a further rule.

### 3. The mechanical exemption's scope is repaired; its definition is not

`AGENTS.md` at `f8836fd` now says mechanical work *owes neither*, resolving against the implementation brief and artifact named immediately before it. It no longer says mechanical work *proceeds straight to a PR*, which let the convergence exemption be carried through the ready gate. `skills/experience-session/references/when-one-fires.md` at `f8836fd` now agrees with the citing cells: mechanical work buys no session and still owes the line saying none ran.

This decides the exemption's scope and does not decide what counts as mechanical. That definition remains [#563](https://github.com/Grimblaz-and-Friends/tradecraft/issues/563)'s subject; the owner dropped [#655](https://github.com/Grimblaz-and-Friends/tradecraft/issues/655) on 2026-09-19. **Rejected:** treating a scope correction as the definition's resolution, or using this change to revive the dropped work.

### 4. Append-only records keep the retired count

The historical references remain in `docs/architecture/decisions/D-545-2026-09-09-a-review-disposes-its-own-findings.md` at `f8836fd`, the D-545 and D-654 rows of `docs/architecture/decisions/README.md` at `f8836fd`, and `docs/settling.jsonl` at `f8836fd`. Each records what was decided or reported when appended. `git grep -n "three ends" f8836fd` re-derives the surviving population without turning it into a frozen count.

The records cell forbids maintaining an appended record, so a stale present-tense rule elsewhere is corrected while these historical statements stay byte-for-byte. **Rejected:** making the log agree with today's rule by rewriting what the earlier decisions said.

### 5. The holder built, and rerunning the build did not restore the artifact stage

The holding session wrote the pre-implementation artifact and applied the seven edits. That violated `skills/engagement/references/the-stretch.md` at `f8836fd`, which says the holder edits no file in the implementation tree and takes no judging seat, and `skills/engagement/references/dispatch-records.md` at `f8836fd`, which makes Codex the standing implementer. It also made both cold seats the same vendor as the builder whose artifact they judged, contrary to the other-vendor requirement in `skills/engagement/references/the-stretch.md` at `f8836fd`.

The build was reverted and run again through `lib/dispatch_implementer.py` at `f8836fd`, producing the built commit this entry pins. The artifact was not re-authored, so the artifact stage's cross-vendor property is lost for this change. Nothing in the floor, artifact check, or dispatch records detected the departure; the owner did, by asking why Codex had stopped being used. The incident is filed as [#663](https://github.com/Grimblaz-and-Friends/tradecraft/issues/663).

**Rejected:** treating the Codex rebuild as though it retroactively repaired who authored and judged the artifact, or omitting the departure because the final implementation commit came through the correct launcher. The rerun repaired the build stage only.

### 6. Two false artifact claims are retracted and changed no implementation

An earlier artifact draft named the D-654 entry as carrying the retired count. It does not; the hit is the D-654 row in `docs/architecture/decisions/README.md` at `f8836fd`. The draft also predicted that the post-fix grep for *buy it for later* would return append-only records, but no record contains that retired vocabulary, so the grep returns nothing. Both claims are retracted in the PR body. Neither selected or altered an edit, and neither changes the built result.

**Rejected:** silently carrying either claim into this frozen entry, and widening the implementation to repair a consequence neither claim produced.

## Settlement cost and findings

Settlement cost two Claude `opus` cold-seat rounds; the PR body records reasoning effort as unavailable because the native Agent tool exposes no effort parameter. Round one returned `would not` on four points, all verified against the tree before repair: the missed printed sentence in `tools/board.py` at `4ea42fd`; a falsifier scoped to Markdown and therefore unable to see it; R1's builder obligation having no acceptance criterion while the draft recast the owner's warrant sentence; and a mechanical-site figure transcribed from a truncated run, with one of its falsifiers also omitting a live site. Round two returned `would` against the repaired artifact.

The missed Python sentence is the durable lesson from that round: an enumeration asserted over the tree cannot be bounded to the extensions its author first expects. That lesson produced no new rule here; the unscoped falsifier in the settled artifact carries it for this change.

## Evidence and re-derivation

- The implementation surface is `git diff --name-only 4ea42fd f8836fd`; its content is `git diff 4ea42fd f8836fd`.
- The historical count references are `git grep -n "three ends" f8836fd`.
- The retired answer vocabulary's post-fix reach is `git grep -n -E "do it|buy it for later|drop it" f8836fd`.
- `python tools/lint.py`, whose script is `tools/lint.py` at `f8836fd`, checks this entry's repository references and the decision index.
