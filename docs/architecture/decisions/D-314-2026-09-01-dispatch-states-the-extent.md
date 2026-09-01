# D-314: The dispatch states the job's extent, because the box does not

**Status:** Accepted 2026-09-01 (PR #314)

## Context

`skills/experience-session/SKILL.md` binds the consumer's side of the time-box — *"Expiry without an answer means stop and report what the box bought — never a silent extension"* — and its dispatch guidance says what a job must and must not name. Neither says what a box does **not** do.

[PR #263's second experience session](https://github.com/Grimblaz-and-Friends/tradecraft/pull/263#issuecomment-5472614246) is the incident. Its dispatch set a box of one working pass and separately asked the consumer to work out what the change owed and do it. Under this practice's own standards the answer to the second is a review and an experience session, each buying a further look. The consumer derived that correctly from `AGENTS.md` and the charter, ran it, stopped short of the terminus, and named the shortfall rather than disposing of it — citing `after-the-fix.md`'s rule that the floor *"is never recorded or handed on in place of being run."* The consumer was right and the dispatch was wrong; the dispatcher wrote it up against itself in that same note.

**The incident has two halves and this entry is only one of them.** The material-side half — that the fix-and-look cycle's only real bound is a budget a review's ruling names, so outside a review the flow describes a loop with no exit — is [#274](https://github.com/Grimblaz-and-Friends/tradecraft/issues/274), and is untouched here. [#289](https://github.com/Grimblaz-and-Friends/tradecraft/issues/289) expressly does not rest on it.

## Decision

One paragraph in **"Running one"**, immediately after *"Give the job, not the test"*:

> **State the job's extent, because the box does not.** A job that defers its extent to the material — *work out what this change owes and do it* — is realistic here and unbounded, since this practice's answer to it is a review and a session, each buying a further look; the time-box caps how long a run may take, never how much it takes on, so a consumer holding both resolves toward the job — [one ran well past its box and still stopped short of what it had correctly worked out it owed](https://github.com/Grimblaz-and-Friends/tradecraft/pull/263#issuecomment-5472614246). Name which of the owed steps are in scope, or make working out what is owed the deliverable and doing them out of scope. [D-314]

**Placement is "Running one", not the Time-box bullet.** The defect is written into the job statement, and "Running one" is where a dispatcher composes one. The Time-box bullet makes no scope claim, so it is not the defective text; it also sits under *"The instrument — three pieces, nothing more"*, a heading whose own closing line resists growth. A rule about how to write a dispatch is not a property of the instrument's third piece.

**The rule names two moves rather than asserting only that the box does not bound the job.** That is the whole of what the spike bought, and the reason is below.

## The spike reversed the reasoning, and the premise it was argued from is false

A cold-seat A/B ran **before any of this was asserted** — six seats, three per arm, each handed the cell body inline as its whole world and stopped at the dispatch it would write. The arms differed in exactly this paragraph. [The report](https://github.com/Grimblaz-and-Friends/tradecraft/issues/289#issuecomment-5501042628) carries the docket, the arms, the stop point and the quoted returns.

**The premise as first stated — *a dispatcher holding this cell will pair a box with an unbounded job and not notice* — is false.** Three of three control seats named the contradiction unprompted, in their own words, one of them writing that the pairing "is a contradiction the consumer resolves toward the job."

**What the control arm could not reach was the remedy.** None of the three stated an extent. Two declared a tiebreak — *the box wins, stop and report unfinished* — and one removed the time-box from its dispatch altogether. A tiebreak leaves the consumer holding an unbounded job and a clock, which is the #263 shape by construction rather than by accident: spend the box on a job that cannot be finished, hand back a truncation. Three of three treatment seats instead produced an extent — an in-scope enumeration, an explicit out-of-scope clause naming the recursive steps, and *working out what is owed* promoted from task to deliverable.

So the rule earns its place on **which remedy a dispatcher reaches**, never on whether the clash is visible. A version asserting only that the box does not bound the job is what the control arm already had, and it lands a dispatcher at the tiebreak.

**Two limits are recorded rather than smoothed.** The docket put the two desires in adjacent sentences and asked each seat for its own rationale, which is far more salient than the real case, where job and budget are settled at different moments and no dispatcher writes a rationale — so *3 of 3 noticed* is an upper bound on how visible this is in the wild, and it does not touch the arm difference, both arms having had the identical docket. And the seats received the paragraph with its incident clause unlinked, so that none could follow a URL out to this change's own record; the shipped clause is a link, which adds an evidence pointer and alters no instruction.

**The acceptance criteria are pinned to this wording because of that.** Criteria 1–3 name the completed A/B as their falsifier, which measures nothing unless the built text is the tested text; [the settlement comment](https://github.com/Grimblaz-and-Friends/tradecraft/issues/289#issuecomment-5501106599) states that any other wording of the two moves or the reason clause voids them until the A/B is re-run. A cold seat found that hole in the artifact and it is adopted rather than argued away.

## Rejected

**Stating the rule once for every cold dispatch in the practice**, whose home would be the charter. `skills/spikes/SKILL.md` already carries a sibling — *"Every bound in this cell is yours to impose on the seat, because it cannot infer one"* ([D-307](D-307-2026-09-01-a-commissioned-probe-stops-at-its-datum.md)) — and both rest on the same observation about what a seat handed an ordinary job does. Rejected on three grounds. They are not one standard, so the one-owner rule does not bite: a spike seat must dispatch nothing, stop at its datum, and **not do the job**, where an experience-session consumer is meant to do one, so what the two share is an observation rather than a standard. Routing up would spend an outflow against a near-full always-on surface to buy a sentence neither cell shares. And the evidence is one incident, in an experience-session dispatch; the charter admits an agent-proposed rule on an incident, not beyond one. A cold seat checked this against `skills/authoring/references/cell-structure.md` at `e333441` and both cells, and cleared it.

**A rule prescribing the tiebreak** — *say which of the job and the box wins*. This is what three of three control seats invented unaided, so writing it down buys nothing that is not already there, and it writes down the worse remedy: it holds the overshoot only where the box is hard, and it guarantees a truncated deliverable.

**Banning the deferred-extent job.** It is this repository's most realistic job, and the incident's own consumer produced the finding [#274](https://github.com/Grimblaz-and-Friends/tradecraft/issues/274) records precisely by working out what was owed. A criterion guards the job's survival.

**Placing it in the Time-box bullet**, argued above.

**Making the stated extent a required field of the note.** The cell's own text says a template or field list is *"how it stops being cheap enough to run"*; a criterion guards the instrument at three pieces.

## What this does not fix

**[#274](https://github.com/Grimblaz-and-Friends/tradecraft/issues/274).** Whether the fix-and-look cycle terminates at all outside a chartered review is a property of the material, not of a dispatch. **The rule holds either way**, which is why this did not wait on it: even with a terminus, the owed work is a review plus a session plus the looks those buy, which no single working pass contains.

**And it does not make a dispatcher bound anything it has not thought of.** The paragraph fires on a job whose extent the material sets. A job that is unbounded for some other reason gets nothing from it.

## Cost

One paragraph in a cell body, loaded on demand, on a change whose diff is additive only — `git show b107a79 --stat` and `git show b107a79 -- skills/experience-session/SKILL.md`. **No always-on surface is edited, so no outflow is owed**: the cell's frontmatter `description` is byte-identical to `e333441`, which `python tools/lint.py` corroborates by reporting the same per-runtime always-on rows on this tree as on that one. The body's size against whatever ceiling applies to it is `python tools/figures.py --cell-budget`; this cell has no enforced budget row, which is the condition [#275](https://github.com/Grimblaz-and-Friends/tradecraft/issues/275) reports that flag reads badly for.

The defence of the words is the spike: the paragraph carries two named moves and a reason clause, and the arm without them left three of three dispatchers at a remedy that reproduces the incident.
