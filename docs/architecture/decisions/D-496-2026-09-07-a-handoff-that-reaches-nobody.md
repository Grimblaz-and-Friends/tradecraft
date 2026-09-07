# D-496: The opener finishes the stretch, and a filing names its origin as a key rather than a description

**Status:** Accepted 2026-09-07 (PR #496)

## Context

Two rules the owner affirmed in one conversation on 2026-09-07, filed as [#483](https://github.com/Grimblaz-and-Friends/tradecraft/issues/483) and [#485](https://github.com/Grimblaz-and-Friends/tradecraft/issues/485), both briefs saying one pull request may land both. Each is about a handoff that reached nobody.

[#483](https://github.com/Grimblaz-and-Friends/tradecraft/issues/483): [PR #451](https://github.com/Grimblaz-and-Friends/tradecraft/pull/451) said in its own body that a fresh session would run its experience session and its review from a cold read. Nothing routes a pull request to a session — the pool raises issues, and the ask mark routes to the owner — so no session picked it up, and it merged unreviewed. `gh pr view 451 --json createdAt,mergedAt` gives `2026-09-07T02:55:57Z` and `2026-09-07T20:18:50Z`.

[#485](https://github.com/Grimblaz-and-Friends/tradecraft/issues/485): `tools/trial_intake.py` had to reconstruct each filing's origin from phrases, because no element of a filing stated it. Its run at `2c84f66` left sixteen of that day's twenty-eight bodies unstated, and 193 of the baseline's 268.

## Decision

**1. #483's two halves sit in two cells, and the split follows from who owns what.** #483's brief-comment costed the change as one sentence in the repo-only `landing` cell. The charter routes *what the declining line must say* to the `experience-session` cell, which states it already at `skills/experience-session/SKILL.md`'s *"say so and why"* sentence, so putting the content rule in `docs/cells/landing/SKILL.md` too would be a second copy of a rule that has an owner. **Who runs the stretch** is this repository's own flow and stayed in `landing`; **what the line may not say** joined the sentence that already governs the line. Siting is the session's call under the `engagement` cell's list, and the cost the brief-comment's estimate was protecting — no version bump — is spent either way, since #485 touches the shipped `filing` cell.

**2. The closed list of origins is five, not the four the brief names.** #485's *Deliberately deferred* hands the list to the artifact, to settle against the classifier's classes. The brief names *a review seat, an experience session, a consumer, or you*; `session` and `instrument` are added because two live categories have no lawful answer among those four. #483 is its own exhibit for the first — its body says *"Found by the session that opened the pull request, reading the merged state on 2026-09-07; not owner-directed"*, which is not a review, not use, and not the owner. `tools/ceiling_filing.py` is the second: it opens issues on merge, so without `instrument` this repository's own filer could not obey the rule on the day it landed. **A rule with no lawful answer for a live category is one sessions write around**, and both additions are reported as the session's call rather than put as a fork, since undoing either costs an edit to the rule and to nothing already in the world.

**3. The heading is `**Provenance:**`, and the origin is its first word.** The heading was chosen because bodies here already write it and `tools/trial_intake.py` already looked for it — the cheapest reliable material the `authoring` cell's admission order asks for. **The first-word rule is what makes it a key rather than a description**: three of 356 bodies carried the heading before this change and their first words were `both`, `originated` and `sustained`, none of which any classifier can sort on. The line sites with the evidence, the tie block staying the body's first element, because a required element with no stated place is one every filer sites differently.

**4. The classifier keeps its phrase tiers as a fallback, which is #485's second deferred question.** Every body in the trial's baseline window predates the element. Dropping the tiers would classify the whole baseline `unstated` and empty the comparison the tool exists to make. A stated origin decides first and reports basis `stated`; the tiers run only where none is stated. No phrase pattern is written for `session` or `instrument`, so a pre-element body can never be classified into either — they did not exist to be stated.

**5. The incident's duration is written as two instants, because the figure #483 states is wrong.** #483's body and title say the pull request sat *twelve hours*; it sat 17.4. The artifact inherited the figure verbatim and its first cold seat failed it on that, before it reached `docs/cells/landing/SKILL.md`. The cell now states `2026-09-07T02:55:57Z` and `2026-09-07T20:18:50Z` and derives nothing, so a later reader re-checks with one command and no arithmetic. **The issue is not corrected**: records here are append-only and never maintained, and this entry is the forward surface where the correction lives.

**6. A finding handed to #485 is disposed forward and not backward.** The review of [PR #451](https://github.com/Grimblaz-and-Friends/tradecraft/pull/451) handed #485 a design call: the classifier had no rule for whether a filing's tie block counts as its own provenance text, and three live rows (#342, #363, #400) classify on verbs appearing in tie lines about *other* issues. Reading the stated line first disposes of it for everything filed from here, the element being sited with the evidence rather than in the tie block. It does not reach those three or any other pre-element body, which still classify by phrase — which is what the finding itself anticipated, and its interim guidance stands.

## Rejected

**Putting both halves of #483 in the `landing` cell**, as its brief-comment costed. Rejected under decision 1: it would restate a rule the `experience-session` cell owns, and a second copy is what drifts.

**Keeping the origin list at the brief's four.** Rejected under decision 2: `tools/ceiling_filing.py` would have been unable to obey the rule the same change shipped.

**Dropping the phrase tiers once the element exists.** Rejected under decision 4: it destroys the baseline the trial compares against.

**Editing #483's body to correct the duration, and editing older bodies to carry the element.** Rejected under decision 5 and the artifact's boundary: records here are not maintained, and retro-editing bodies the trial's own evidence cites would disturb that evidence.
