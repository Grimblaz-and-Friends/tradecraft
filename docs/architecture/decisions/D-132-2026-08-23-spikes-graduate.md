# D-132: Spikes graduate to their own cell, and the trigger is keyed to what a session can consult

**Status:** Accepted 2026-08-23 (PR #132)

## Context

[D-80](D-80-2026-08-19-spikes.md) landed spikes as a reference file with an artifact-keyed trigger, and declined depth explicitly on the ground that the practice had **zero runs**. [D-104](D-104-2026-08-22-engagement-cell.md) moved the file to `engagement` unchanged and recorded a graduation condition at `:36`, so a later session would not have to re-derive it: *"if the trigger broadens past the artifact — a spike serving a review finding, an implementation question, a doctrine proposal — it clears the independent-trigger bar and becomes its own cell."*

Both conditions moved. The [#115 spike](https://github.com/Grimblaz-and-Friends/tradecraft/issues/115#issuecomment-5384143581) is the first recorded run, and it served material outside the trigger's letter: a disputed issue thesis, a review-routed finding's exhibit, and a candidate rule wording — falsifying the first, non-reproducing the second, withdrawing the third on its own evidence. It also demonstrated the reframe this entry rests on: **governing prose is a mechanism whose executor is a reader**, so a wording no cold session has worked under is, in the existing trigger's own words, a mechanism nobody has executed.

Both frozen entries are superseded by being read, per the decisions rule. Nothing in either is edited.

## Decision

**A fifth cell, `skills/spikes/`.** The trigger binds no surface: it fires on a load-bearing premise wherever asserted — an artifact's claim, a review thesis still disputed after a round, a candidate rule wording, a question arising while building.

**Its own cell rather than a broadened reference where it sat, and the argument is mechanical rather than aesthetic.** The broadening exists for sessions that are not writing an artifact. `tools/lint.py` forbids one skill referencing another skill by path, so `adversarial-review` cannot point a disputing seat at `engagement/references/spikes.md` — the file is unreachable, not merely unlikely to be read, for exactly the surfaces the broadening serves. Left in place, the change would have been lawful and inert. A top-level cell is discoverable from its own frontmatter description, which is the only handle a review seat has. `engagement` keeps one sentence naming the move and restating none of the trigger's conditions, since a restatement is the drift `authoring` forbids and the failure the plain brief's own duplication already cost this repo once. It names the move without naming the cell, following `filing`'s precedent for the pre-implementation artifact.

**The name is the owner's, taken 2026-08-23:** `spikes`, the word the record already uses. The live alternative was a plainer name (`premise-testing`), rejected for costing the vocabulary every issue and two decision entries carry.

### The four wording changes the spike forced

Each is recorded with the seat result behind it, because none is in the issue and a later session would otherwise read them as drafting preference. The run is [reported on #124](https://github.com/Grimblaz-and-Friends/tradecraft/issues/124#issuecomment-5387189398): ten cold seats, five arms, a docket of nine situations, arms differing only in the trigger paragraphs.

- **`a mechanism nobody has executed` → `behavior no run you can consult has exercised`. This is a meaning change and also a correction.** A cold seat read the shipped words as *nobody, anywhere*, and observed that no session can evaluate that. [D-80:15] had already settled it the other way in as many words — *"the predicate is keyed to what the session can consult, not to what anyone has ever done"* — so the prose and its own recorded reason have disagreed since the day both landed. No review found it across four days; the first cold seat asked to *apply* the sentence did.
- **`material you cannot survey, not material you have not surveyed`.** Every seat in the two unbroadened arms independently named `no enumeration you can consult covers` the file's most under-determined clause and split it the same two ways — material you cannot survey, versus material for which no pre-made index exists. Under the second, every exhaustiveness claim over shipped material fires a spike.
- **The consume exemption**, keyed to nothing resting on the answer. The broadening as the issue words it fired on a thirty-second regex check in both seats that saw it, both calling the ceremony oversized — the counter-bureaucracy [#122](https://github.com/Grimblaz-and-Friends/tradecraft/issues/122) names as failure mode one. **The first fix was wrong and is recorded as such:** keyed to cheapness, the exemption swallows the paradigm case, since a session can always just go build the guard. Rekeying it to the handoff separates the trivial check from the acceptance criterion that rests on the same kind of fact.
- **The reframe defers to the load-bearing condition** instead of asserting an identity. *A wording no cold session has ever worked under* is true of every newly drafted sentence, so read literally the reframe fires on all prose changes — which contradicts the file's own *"a phase that always fires has stopped being a decision."* Both seats that saw it reached that reading unprompted.

Two smaller changes ride with them: the exclusion leads with its arbitration test and carries a tiebreaker (*what a reader will do under the wording is a spike; where the wording belongs is not*), after seats split on a placement dispute and one confirmed the sentence was what decided it; and `Running one` loses its own artifact-keying, which the broadening had otherwise stranded.

**Provenance compressed** to the rule's reason clause plus a link, offsetting the section's growth per `authoring`'s state-the-rule-link-the-evidence standard. The reason survives; the migration's two paragraphs of history do not.

### The index, declined

**A spike commits nothing — no branch, no pull request — so a tracked index could only be appended to by the one instrument forbidden to write anything**, or by giving spikes the process the file says they need none of. That is the whole argument, and it is why the want behind the index is met differently: the report opens `# Spike report — <premise>`, so every run is findable by one search of the board, with no file to maintain. The want was real — D-80 declined depth for zero runs, and that fact was undetectable for four days.

### The seam, and what is left untested

The boundary between an answer you consume and an answer something you write rests on is the least crisp joint in the trigger; four seats across two arms said so, and one moved back to *cannot tell* on the trivial-check case at the last round. It is an under-determination at the edge, not an over-fire — no seat in the last three arms ran ceremony on a trivial check. **The falsifier, so a later session settles it from one real occurrence rather than a sixth docket: a session that spends a spike's ceremony on a question nothing it writes rests on.** A sixth arm was declined rather than run, because five rounds of rewriting one paragraph on apparatus-facing evidence is the self-referential defect supply #122 warns against.

The docket is nine constructed situations; every seat was handed the trigger and asked to apply it, which measures how a wording sorts situations against each other and inflates the absolute rate at which any trigger fires, equally in both arms. No absolute firing rate is claimed anywhere.

## Rejected

- **Broadening the trigger where the file sat.** The cheapest change and the one the issue left open. It fails on reachability, above: the lint makes the file unreachable from the surfaces the broadening serves, so the change would ship and never fire.
- **A spike index.** Above.
- **The issue's own wording of the broadening**, verbatim. It fires on trivial implementation checks, in both seats that received it.
- **A clause in `A spike commits nothing` for the prose case.** A seat observed that section reads as code-and-worktrees only and says nothing about a spike producing no tree. Declined as armor: *nothing committed, no branch, no pull request* is satisfied trivially by a cold-seat run, and the clause would defend against a reader who does not err.
- **A sixth arm** to close the consume boundary. Above.

## Evidence

[#124](https://github.com/Grimblaz-and-Friends/tradecraft/issues/124) — the spike report at [comment 5387189398](https://github.com/Grimblaz-and-Friends/tradecraft/issues/124#issuecomment-5387189398), the affirmed artifact at [comment 5387189939](https://github.com/Grimblaz-and-Friends/tradecraft/issues/124#issuecomment-5387189939), and the affirmation at [comment 5387246260](https://github.com/Grimblaz-and-Friends/tradecraft/issues/124#issuecomment-5387246260). The first recorded run is [#115's report](https://github.com/Grimblaz-and-Friends/tradecraft/issues/115#issuecomment-5384143581). The anchor design is [#122](https://github.com/Grimblaz-and-Friends/tradecraft/issues/122).
