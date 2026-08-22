# D-104: The engagement cell, and the plain brief

**Status:** Accepted 2026-08-22 (PR #104)

## Context

[D-74](D-74-2026-08-19-constitutional-reset.md) chartered `authoring` in one sentence: *"a new `authoring` skill carrying the purpose/audience/success header standard and content routing."* Two items. It has since absorbed the boundary statement and the spikes pointer, both by gravity — the pre-implementation artifact is a document, and `authoring` was the only cell that talked about documents.

The doctrine routes methodology to *the skill that governs it*, and ceremony survives at two moments. Release is a CI mechanism plus one rule. **Convergence had no skill at all**: its methodology was one doctrine bullet plus those two scraps.

Four open issues made that visible at once — [#83](https://github.com/Grimblaz-and-Friends/tradecraft/issues/83) (what to pick up next), [#84](https://github.com/Grimblaz-and-Friends/tradecraft/issues/84) (this one), [#85](https://github.com/Grimblaz-and-Friends/tradecraft/issues/85) (convergence is interactive, ends at a handoff), [#86](https://github.com/Grimblaz-and-Friends/tradecraft/issues/86) (decision rights). None is about writing a document; none is about reviewing one. All four were pointed at doctrine lines, because no cell would take them.

The mechanism that sent them there: the admission ladder reads *"a platform or CI mechanism, then skill prose, then a doctrine line"*, where "skill prose" silently means **a skill that already exists**. Nothing anywhere prompts "is there a cell for this at all?" — so a homeless requirement walks past skills onto a budgeted file. `authoring`'s own routing line compounded it by phrasing the test as a restriction: a piece becomes its own skill *"only when"* it has an independent trigger.

The owner named the second half directly during convergence: he should not have to push to get the question asked.

## Decision

**A fourth cell, `engagement`**, for how a session and the owner work together. It clears `authoring`'s own independent-trigger test — putting a decision to the owner, converging on what to build, and handing work back each fire with no document being written and no review running.

**`engagement` owns the pre-implementation artifact whole.** The precedent that settled it: `adversarial-review` owns its own final report outright, and `authoring` does not co-own that report's prose. An artifact is the same kind of object — an issue comment binding one implementation, then history, not governing prose that later sessions obey. The skill that owns the process owns the work object the process produces. `authoring` accordingly drops the artifact from its frontmatter trigger and its body, and its purpose header narrows to governing documents.

**The doctrine gains two things**: the admission ladder's missing rung (a new cell where no existing one fits, with the burden on cramming rather than creating — restated in `authoring`'s routing line so both read the same way), and the plain brief named once with its four touchpoints. Admitted on both paths available under [D-77](D-77-2026-08-19-owner-approval-admission-path.md): an incident from real work, and the owner's specific approval.

**The plain brief.** A blockquote opening with a bold `**In plain terms:**` lead-in, at the top of every surface the owner enters, with nothing above it but a title. Plain English, no term he would have to look up. What earns a place: what this is, why it matters, what he is being asked. What is disqualified: anything that would only matter once he had already decided.

- **Length is not a count.** The bar is readable-in-one-pass; longer is lawful with a reason. The disqualifier carries the concision property that a word limit would carry badly — a limit rejects a good six-sentence brief for being seven.
- **Accountable, not authoritative.** The brief must be true of what sits beneath it, and what sits beneath it is what is agreed. A brief that misrepresents its body is a defect found in that body's review, never a second contract.

**Spikes** move to `engagement/references/spikes.md` unchanged, because everything the file says today is artifact-triggered — its stated audience is *"any session writing a pre-implementation artifact"* and its report goes on the work's issue. **Graduation condition, recorded so a later session need not re-derive it:** if the trigger broadens past the artifact — a spike serving a review finding, an implementation question, a doctrine proposal — it clears the independent-trigger bar and becomes its own cell.

## The evidence that set the brief's form

#84 recorded the predecessor's artifacts as opening with one concise statement that was both readable in one pass *and* enough to decide from. A census of the predecessor's plan artifacts — 183 carrying the `## Plan:` heading, drawn from all 299 issues GitHub reports as carrying a `plan-issue` marker — found **three objects, not one**:

- **The plan TL;DR** — plain unadorned prose under an H2, 142 of 183 (78%), median 97 words and 4 sentences, prescribed as `{TL;DR - what, how, why. (30-200 words)}` with 93% compliance. Distinguished from the body by **position, not markup**. Not a decision surface.
- **The approval card** — `Change:` / `No change:` / `Trade-off:` / `Areas:`, specified as a consent surface that "must stand on its own so the user can approve from the dialog alone." **Conversational only**; zero occurrences in any persisted comment.
- **The affirmed what-statement** — a separate record posted *before* the plan, blockquoted in 19 of 21 sampled, usually a bold one-sentence headline then supporting detail, 90–365 words. **This was the thing affirmed.**

The form adopted here takes the what-statement's shape rather than the TL;DR's, because the plain brief's job is decidability. It also matches what the owner already writes unprompted in the bodies of #84, #85, #86 and #89 — the decision surface, reproduced by the person it is for.

The predecessor bound its what-statement and did not bind its TL;DR. The single-form, accountable-not-authoritative reading was taken instead so that one form serves four touchpoints without a second binding object that can drift from the surface beneath it.

## Rejected

- **Filing the cell as a new issue and leaving #84 as the plain brief alone.** Rejected by the owner: #84 is the issue the work rides on, #85 and #86 already point at it as the companion issue, and a second number would split one convergence. The issue was retitled and its body left unedited as the record of the original want.
- **Both `authoring` and `engagement` governing the artifact**, split by whether a piece is a component of the artifact or a standard its prose is held to. Coherent, and it survived one round of argument, but it leaves a seam to be judged on every future addition — which is exactly how `authoring` acquired the boundary statement. The owner's reading — `authoring` is the formal-documents skill — plus the `adversarial-review`-owns-its-report precedent settled it the other way.
- **Restating the brief's form in each touchpoint's own prose.** Zero doctrine cost and cells stay pure, but it produces three restatements of one standard that can drift, and it cannot reach the two touchpoints that live in chat, which no skill owns.
- **Naming the touchpoints only in the cell that defines the form.** Cheapest, and it fails: a session writing a review report never loads `engagement`, so the requirement would not fire where it is needed.
- **A word-count bound on the brief** (the predecessor's 30–200 band). Rejected by the owner in favour of the disqualifier test.
- **Standing spikes up as its own cell now, or broadening its trigger to any load-bearing premise.** Both are coherent and one may yet be right, but each is a second decision riding in a PR that already creates a cell and amends the doctrine, and [D-80](D-80-2026-08-19-spikes.md) was three days old. Deferred to the graduation condition above.

## Evidence

[#84](https://github.com/Grimblaz-and-Friends/tradecraft/issues/84) (the artifact at comment 5380975104 and its affirmation at 5380976787), successor to #26 and #27. The census above was run against [agent-orchestra](https://github.com/Grimblaz/agent-orchestra) as reference material, per the doctrine's predecessor rule — the lesson pulled, no artifact imported.
