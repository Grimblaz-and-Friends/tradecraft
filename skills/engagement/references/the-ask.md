# Putting a decision to the owner

**Loaded when** you are putting a decision to the owner — composing the argued form it arrives in, or handing work back to them after time away — or putting one where they are not in the room to read it: writing the ask block, marking what carries it, or reading what waits.

**What is theirs arrives argued:** the live options, each with its pros and cons, then the recommendation among them — above the brief, which sits last, immediately before the ask it briefs. Where exactly one option is live, say so and say what was rejected and why — the reasoning is what makes that case informative, and a fabricated second option under-informs worse than none, because it presents a search that did not happen.

**Four habits qualify every ask.** A question carries the session's guess; a recommendation carries its strongest case against; the text the owner settles is kept exact under the rule below; and an explanation or proposal arrives built on a real case where that is reasonable. Where a real case is not reasonable to build, say why and describe it instead.

A guess lets the owner correct rather than compose, and the strongest case against the recommendation keeps an argued choice from becoming advocacy for one. [The case against a recommendation travels with it](https://github.com/Grimblaz-and-Friends/tradecraft/issues/402). The real case gives them the instance they can judge on sight rather than an abstraction they have to imagine.

**The text the owner settles is kept exact.** For an implementation brief, the affirmed item and the one-time record of each row-changing push are governed by `../references/the-brief.md`; none of the item's words need to have been typed by the owner. For another ask, record the ruling in their own words or in the one restatement they approved, and keep that text exact thereafter. [D-414]

**An ask is anything a session needs from the owner that the session may not settle** — an implementation brief put for affirmation, an argued ask ruled at release, or a handback after time away. The occasions are not a closed list; what makes something an ask is that **the matter is not the session's to close**, whether or not the work waits on the answer. **Waiting is not the test and never was**: an argued ask ruled at release has the work proceeding on the recommendation, and it is an ask.

**An ask the owner is not in the room for is put by posting an ask block and marking what carries it.** The block is a comment on the issue or pull request the ask concerns, and carries three lines:

- **What is being asked** — the decision, in one sentence.
- **Where the work stands** — enough that the question makes sense without the owner reconstructing the work first.
- **What an answer unblocks** — what proceeds once it is answered and what does not, so the owner sees which answer frees the most work.

**The mark is a label on what carries the block — `awaiting-owner`, unless the adopting repository's own doctrine names another.** **Create it before the first ask**; applying a label that does not exist is refused.

**An ask that is not marked is not put, and nothing that later happens to what carries it rules on it.** A question written into a pull request body and marked nowhere is not answered by the merge; it was never asked.

**An ask put to the owner in conversation is put, and carries no mark**, the conversation being the engagement surface. The mark is for an ask they are not in the room for.

**One query is the whole of what waits, and it is scoped to the repository.** Unscoped, the label is a common one and the search returns other people's work.

```bash
gh search issues --repo <owner>/<repo> --label <the mark> --state open --include-prs --limit 100
```

**An empty result and a wrong label name are the same output** — no rows, exit zero — so a query that has never returned anything is worth checking against the repository's label set before it is read as *nothing waits*. **The limit is not decoration**: the default is thirty and a truncated page is indistinguishable from a complete one, so a result that comes back at whatever limit was asked for is a short read rather than the whole of what waits.

**The mark comes off when the ask is answered**, by the session that reads the answer. A closed issue or a merged pull request leaves the set on its own, so nothing has to be swept.

**Where the owner cannot be reached at all, the waiting rule (`../references/waiting.md`) governs**, and it decides whether the ask block and its mark above apply — read it before putting an ask into an absence rather than after.
