# D-104: The engagement cell, and the plain brief

**Status:** Accepted 2026-08-22 (PR #104)

## Context

[D-74](D-74-2026-08-19-constitutional-reset.md) chartered `authoring` in one sentence: *"a new `authoring` skill carrying the purpose/audience/success header standard and content routing."* Two items. It has since absorbed the boundary statement and the spikes pointer, both by gravity — the pre-implementation artifact is a document, and `authoring` was the only cell that talked about documents.

The doctrine routes methodology to *the skill that governs it*, and ceremony survives at two moments. Release is a CI mechanism plus one rule. **Convergence had no skill at all**: its methodology was one doctrine bullet plus those two scraps.

Four open issues made that visible at once — [#83](https://github.com/Grimblaz-and-Friends/tradecraft/issues/83) (what to pick up next), [#84](https://github.com/Grimblaz-and-Friends/tradecraft/issues/84) (this one), [#85](https://github.com/Grimblaz-and-Friends/tradecraft/issues/85) (convergence is interactive, ends at a handoff), [#86](https://github.com/Grimblaz-and-Friends/tradecraft/issues/86) (decision rights). None is about writing a document; none is about reviewing one. Their stated homes vary: #85 and #86 point at doctrine lines, each naming skill prose only as a fallback; #83 leaves the choice open between the doctrine, a skill, and plain practice; and #84 points at `authoring` — a cell that does not fit it. That last one is the diagnosis in miniature. The only issue of the four to name a cell named the wrong one, because no cell fitted, and nothing prompted the question of whether one should exist.

The mechanism that sent them there: the admission ladder reads *"a platform or CI mechanism, then skill prose, then a doctrine line"*, where "skill prose" silently means **a skill that already exists**. Nothing anywhere prompts "is there a cell for this at all?" — so a homeless requirement walks past skills onto a budgeted file. `authoring`'s own routing line compounded it by phrasing the test as a restriction: a piece becomes its own skill *"only when"* it has an independent trigger.

The owner named the second half directly during convergence: he should not have to push to get the question asked.

## Decision

**A fourth cell, `engagement`**, for how a session and the owner work together. It clears `authoring`'s own independent-trigger test — putting a decision to the owner, converging on what to build, and handing work back each fire with no document being written and no review running.

**`engagement` owns the pre-implementation artifact whole.** The precedent that settled it: `adversarial-review` owns its own final report outright, and `authoring` does not co-own that report's prose. An artifact is the same kind of object — an issue comment binding one implementation, then history, not governing prose that later sessions obey. The skill that owns the process owns the work object the process produces. `authoring` accordingly drops the artifact from its frontmatter trigger and its body, and its purpose header narrows to governing documents.

**The doctrine gains two things**: the admission ladder's missing rung (a new cell where no existing one fits, with the burden on cramming rather than creating — restated in `authoring`'s routing line as three disjoint cases — independent trigger, its own cell; not independent but a cell already serves it, that cell's `references/`; no cell serves it at all, a new cell — so both encode the same test), and the plain brief named once with its four touchpoints. Admitted on both paths available under [D-77](D-77-2026-08-19-owner-approval-admission-path.md): an incident from real work, and the owner's specific approval.

**Where the doctrine stops and the cell starts.** The doctrine carries that a brief is owed, where it is owed, and where its form lives; the cell carries the form. This was settled during this change's own review, on an incident inside it: the brief's element list had been duplicated into the doctrine line and had already drifted — two elements against the cell's three — before landing. `authoring`'s routing forbids exactly that (*"never duplicated prose that can drift"*), so the doctrine's copy was deleted rather than patched, and every later remedy that would have added form detail to the doctrine was priced out against this line.

**The plain brief.** A blockquote opening with a bold `**In plain terms:**` lead-in, at the top of every surface the owner enters, with nothing above it but a title. Plain English, no term he would have to look up. What earns a place: what this is, why it matters, what he is being asked. What is disqualified: anything that would only matter once he had already decided.

- **Length is not a count.** The bar is readable-in-one-pass; longer is lawful with a reason. The disqualifier carries the concision property that a word limit would carry badly — a limit rejects a good six-sentence brief for being seven.
- **Accountable, not authoritative.** The brief must be true of what sits beneath it, and what sits beneath it is what is agreed. A brief that misrepresents its body is a defect found in that body's review, never a second contract.

**One meaning change rode along with the relocations, named here rather than left silent:** `authoring`'s boundary-statement paragraph was conditional (*"Where a repo's pre-implementation artifact **also** carries a boundary statement"*) and lands in `engagement` as a component of the artifact's contents, which makes it required of every repo that installs the plugin. The reason clause travelled intact; the conditional did not, and the widening is intended now that a cell owns the artifact outright.

**The form's first instance does not conform to it, and that is recorded rather than repaired.** The affirmed artifact carries acceptance criterion 9 — *"This artifact's own opening is a conforming plain brief"* — and its opening fails the form twice: an italic provenance line sits between the title and the brief, against *"nothing above it but a title"*, and the brief names three issue numbers, which the disqualifier sends below. The artifact freezes on affirmation, so the criterion ships unmet. Editing it would rewrite an affirmed handoff contract and breach the artifact's own boundary statement; relaxing the rule to fit a non-conforming instance is the move the evidence standards forbid. The rule stands, and the working exemplar is this change's own pull-request body, written after the rule and conforming on both counts.

**Spikes** move to `engagement/references/spikes.md` unchanged, because everything the file says today is artifact-triggered — its stated audience is *"any session writing a pre-implementation artifact"* and its report goes on the work's issue. **Graduation condition, recorded so a later session need not re-derive it:** if the trigger broadens past the artifact — a spike serving a review finding, an implementation question, a doctrine proposal — it clears the independent-trigger bar and becomes its own cell.

## The evidence that set the brief's form

#84 recorded the predecessor's artifacts as opening with one concise statement that was both readable in one pass *and* enough to decide from. A census of the predecessor's plan artifacts found **three objects, not one**.

**Method**, recorded so a later session reconciles rather than guesses: the population is issue comments whose first four lines carry a `<!-- plan-issue-N -->` marker — 192 comments across 189 issues; an artifact is such a comment that also carries a `## Plan:` heading — 181; its opening is the first non-blank block after that heading that is neither an HTML comment nor a `---` fence. The census was re-derived four times during this change's review. The medians reproduce exactly under every extraction; the population counts move by a few percent with the width of the marker scan; and any *adorned-versus-unadorned* split is classifier-sensitive — 81% of openings begin with a plain character, 46% if bold anywhere disqualifies — which is why no such figure is load-bearing below.

- **The plan TL;DR** — plain prose under an H2, median 97 words and 4 sentences, prescribed as `{TL;DR - what, how, why. Reference key decisions. (30-200 words)}`, with 173 of 181 (96%) inside that band. Distinguished from the body by **position, not markup**. Not a decision surface — and its instruction to reference key decisions is content the plain brief's disqualifier sends below the fold, which is further evidence the two are different objects.
- **The approval card** — `Change:` / `No change:` / `Trade-off:` / `Areas:`, specified as a consent surface that "must stand on its own so the user can approve from the dialog alone." **Conversational only**; zero occurrences in any persisted comment.
- **The affirmed what-statement** — a separate record posted *before* the plan, blockquoted in 19 of 21 sampled, usually a bold one-sentence headline then supporting detail, 90–365 words. **This was the thing affirmed.**

The form adopted here takes the what-statement's shape rather than the TL;DR's, because the plain brief's job is decidability. It also matches the form carried in the bodies of #84, #85, #86 and #89 — though those were session-filed, three of them within three seconds, so they are the form the owner has affirmed rather than independent evidence that he authors it. #83, filed the same morning, carries no brief at all.

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
