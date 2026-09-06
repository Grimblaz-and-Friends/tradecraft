# D-441: The pool moves on its own — a derived fade, a derived accrual, and an assessment gate

**Status:** Accepted 2026-09-06 (PR #441)

## Context

[#434](https://github.com/Grimblaz-and-Friends/tradecraft/issues/434), stage two of three under one affirmed brief. The brief is [on that issue](https://github.com/Grimblaz-and-Friends/tradecraft/issues/434#issuecomment-5561062728), amended [there](https://github.com/Grimblaz-and-Friends/tradecraft/issues/434#issuecomment-5561376807); this stage's settled artifact is [there too](https://github.com/Grimblaz-and-Friends/tradecraft/issues/434#issuecomment-5562301545). Stage one is [D-438](D-438-2026-09-06-a-filing-lands-in-a-pool.md), which landed the pool itself. What this entry records is the reading, not the brief.

**What the tree held at the base.** At `e0d2675`, stage one's tip: `skills/filing/scripts/pool.py` with membership as the absence of the framed label, two ratings as policy-named labels, `writable_labels` and the single write chokepoint, `read_pool` and `sort_key` over the labelled pair; `tools/board.py` reading the framed label from that policy while holding `CAUSE_LABEL = "cause"` as its own constant; and `causal_parents` there as a paged GraphQL read over `parent` plus that label.

**The artifact took two rounds.** A first cold seat returned `would not` on three points, all of them places the reading built *less* than the brief agreed: the fade's rail made unconditional where the brief made it conditional, the amendment's first moment given an advisory line and no mechanism, and the held-findings record answered with a pointer rather than by joining the pool. All three are repaired below and a fresh seat returned `would`. That history is recorded because each repair is a decision in its own right.

## Decision

**1. The fade is derived at read time and never written, and the reason is mechanical rather than stylistic.** Writing a decayed rating updates the issue, and *the issue was updated* is precisely the signal quiet is read from. A written fade therefore resets its own clock on every item it touches: an item decays once and then never again, while presenting exactly as one being actively kept alive. So effective urgency is the labelled band less one per `fade.quiet_days` of no activity, floored at the axis minimum, read from GitHub's own `updatedAt`. Nothing is stored and no run has to have happened, so a repository that never runs `cycle` still sees a faded order.

**Severity has no decay term at all**, which is how the brief's *severity never does* becomes structural rather than a rule someone must remember. **What this costs is stated rather than solved:** any comment resets the quiet clock, including one recording a finding under its cause, so a busy cause never reaches the floor however long nobody picks it up.

**2. The close at the floor is a real write, behind a switch that ships off.** The first draft made criterion 7 read *nothing closes, whatever the policy says*, which converted the brief's *until a repository turns that on* — a condition on when — into a licence never to build it. The cold seat named that and it was right. `fade.closes` is false by default; where a repository sets it true, `cycle` closes each floored item as `not planned`, leaving the body and every comment so the evidence is kept and the next symptom reopens it. Nothing is deleted and no rating is rewritten.

**3. Accrual is derived on both axes, and differently on each.** Effective severity is the greater of a cause's own and the highest among its open symptoms — a cause is at least as bad as the worst thing it produces. Effective urgency is its own raised one band per `accrual.symptoms_per_band` open symptoms, capped at the axis maximum — a thing that keeps happening climbs. Neither is written back.

**A symptom contributes its labelled band and nothing derived**, so accrual cannot feed accrual: a chain of causes would otherwise climb without limit and for no reason anybody wrote down. In `read_pool` that property is *additionally* held by call order, symptoms being collected before any effective pair is computed — which is why the pin sits on `_bare` rather than on the chain. A mutation of the call site leaves the suite green; a mutation of `_bare` reddens it. The pin was moved on that evidence.

**4. The shipped script grows its own causation read rather than importing the board's.** A repository's board transport is repo-only and this script ships, so the import is barred one way. What is shared instead is the label's *name*, which moves out of a repo-only constant and into the policy where every other label name this practice writes already lives — so the duplication that remains is a query, not a vocabulary. **The wall guard caught two breaches in this change's own prose**, both in comments explaining the wall while naming a repo-only path; they are reworded.

**5. Assessment is a gate on the shortlist, not a note beside it.** The amendment has the pool work out the causes behind the highest-rated unassessed things *before* a session brings the owner a few, so that what it brings are causes. An advisory line does not do that — a session reads it and raises the symptoms anyway — so `shortlist` refuses while any of the top `assessment.before_shortlist` items is unassessed, names exactly which and the command that answers for each, and takes `--unassessed` as the stated escape. **The gate looks at least as deep as `--count` asks**, so that flag cannot outrun it. At ship every item is unassessed and the refusal fires on the first run, which is the amendment's intent rather than a failure of it: `list`, `show`, `rate`, `frame`, `unframe` and `cycle` all work meanwhile.

**Two states and no third.** An issue asked and found to be its own cause carries the assessed label; one never asked carries nothing, exactly as an issue in the pool carries nothing. Where the answer is that it *has* a cause, the record is the sub-issue link the `filing` cell already governs, and duplicating that here would give one relationship two representations that could disagree.

**6. A `record` ruling files into the pool, and the append stays.** The brief has the held-findings record join the pool *rather than staying a separate list nothing reads*, and a pointer to an existing route does not do that. So the ruling now files one issue, rated low — real, evidenced, not yet worth acting on is the pool's own state, and once it is a pool item the ranking, the fade and the shortlist all reach it. `docs/recorded-findings.jsonl` keeps its append: records are append-only, the row is the review's own accounting, and the next review's dispatch fetches it. **No row is migrated.**

**The filing bar has to admit it, and that is said out loud.** A `record` ruling is most often about governing prose, which `skills/filing/SKILL.md` refuses to file without an incident or a run. Left unstated the shipped material would hold two rules that contradict for the ordinary case — the cold seat named this as the artifact's weakest seam. The carve-out is narrow: what admits it is that a stage which is not the builder has already judged it real and evidenced.

**7. The evidence-rot check closes nothing, and that is a measurement rather than caution.** The artifact called the path half exact — a path resolves or it does not. Run over this repository's own pool it produced eight hits, and most were filings naming a path *deliberately*: one they propose should exist, or one whose moving is what the filing is about. Skipping fenced blocks, placeholder segments and partial matches took eight to two. A close on that predicate would discard live filings, so it reports. `fade.closes` does not reach it, and the only close the fade performs is at the floor, where quiet is measured rather than inferred from a pattern.

**8. A policy written before this stage is refused with a message naming what to add, not silently defaulted.** The no-merge rule is [D-438]'s decision 5 — an override states the whole policy — so defaulting the new blocks would hand a repository numbers it never wrote. `load_policy` names `cause`, `assessed`, `accrual`, `fade` and `assessment` in the refusal. **`fade.closes` must be stated rather than inferred**, since it alone decides whether anything closes.

## What was rejected

- **Writing the decayed rating**, which is the obvious design and is self-defeating; decision 1.
- **A `null` threshold or a defaulted policy block**, on [D-438] decision 11's own ground: a field no command reads is a promise in a second place, and a silent default is worse than a refusal that names the migration.
- **Importing the board's causation read into the shipped script** — the wall, one way.
- **Closing on the rot check**, decision 7.
- **Refusing `shortlist` outright with no escape**, which would make the pool's one route to the board unavailable at exactly the moment it ships.

## Meaning changes named

- `skills/adversarial-review/references/arbitration.md` and `skills/adversarial-review/references/the-record.md`: a `record` ruling now files into a pool where one exists, and the entry's role narrows to accounting. Both are shipped.
- `docs/cells/records/SKILL.md`: the local statement of where a ruling goes. Repo-only, and flagged for the owner's review by `ci.yml` as a repo-only cell is.
- `skills/filing/SKILL.md`: the pool paragraph gains the accrual, the fade and the assessment; and the governing-prose bar gains its one exception, decision 6.
- `docs/cells/board/SKILL.md`: the two commands that read what moves between refreshes.
- No always-on document and no cell description is touched, which is the affirmed brief's exclusion and is stage one's reading of it, unchanged.
