# D-602 — The affirmed agreement is the implementation brief, and only it

**Purpose:** preserve why this practice renamed the agreement rather than the artifact, why four existing rules were narrowed instead of deleted, and what the owner ruled about the settling record's key. **Audience:** a future session revising the brief material, tempted to rename the pre-implementation artifact, or wondering why one subtype carries exceptions the generic form does not. **Success:** they can tell which of these choices were the owner's and which the session's, and they do not re-open a question he closed.

The owner affirmed [the implementation brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/596#issuecomment-5654982480); the [artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/596#issuecomment-5656476338) settled in one cold round, `would`, before implementation.

## The session's opening reading was wrong, and the owner rejected it

The issue was filed as a naming collision and this session's first recommendation was to rename the **pre-implementation artifact** to carry the owner's word, on the ground that `artifact` already meant two things in shipped prose. The owner rejected it outright, in conversation on 2026-09-13 — *"I'm not trying to touch the artifact at all with this change"* — and supplied the reading the change was built on: the plain-terms text he receives everywhere is a communication obligation rather than a brief, and the single document affirmed before a build is the thing that deserves the name. **A later session tempted by the rename this change did not make should know it was proposed, argued and refused**, and that `artifact`'s other collisions are untouched by design.

The material's own sentence is what made the confusion possible and is worth preserving as the diagnosis: `skills/engagement/SKILL.md:27` at `ed69ada` read *"Affirmed, it binds; describing, it is accountable"* — one word covering a form owed on every owner-facing surface and an agreement that governs a build, with only the form's standards written down.

## Why four rules were narrowed rather than deleted

The content disqualifier on implementation detail, the blanket *what it is not* prohibition, the scoring pass over one undifferentiated list, and the opener announcing a brief that applies a prior ruling were each written when one document wore both jobs. Every one of them, applied to an implementation brief, strips the terms of the build that the new standard requires — on [#593](https://github.com/Grimblaz-and-Friends/tradecraft/issues/593) the detail disqualifier is what a session used to talk itself out of stating anything concrete, and its scoring pass then passed the result. **Each keeps its generic arm intact**, because the plain brief's own failure mode is unchanged: it is still not a summary and still not a home for detail.

**The line between what an implementation brief carries and what it excludes is the fork test, never a what-versus-how reading.** That axis was drafted first and the owner broke it in one question, in that same conversation — *"How and what get murky in some places; what if I'm asking you to build a database?"* Engine, schema and location are all *how*, and some of them are his. So the rule reaches whose decision it is: a choice the session owns stays out while it is the session's, and becomes a term the moment he rules on it.

**Fidelity is owned by the standard rather than delegated.** `skills/engagement/references/the-ask.md` scopes its three habits to an *ask*, and `the-brief.md` states that the recorded form has none — so the exact-words habit does not reach the surface where an implementation brief's fidelity matters most. Pointing at it would have inherited that gap. This was found by the discarded draft of the artifact, not by the one built from.

## The settling record's key

The rename reaching `docs/settling.jsonl`'s `brief` key was carried to the owner as a fork rather than closed by the builder, because it touches an append-only record and a guard. He ruled **option A** — *"yes, go with A as recommended"* — so rows after the pinned positional boundary require `implementation_brief` and every existing row keeps `brief`, untouched. The grandfathering is positional rather than by date, copying `check_review_index`, whose own comment records why a date cutoff failed.

**The case for option B is recorded because it was real and may return**: a schema field is an identifier rather than prose, renaming one for vocabulary is arguably a category error, and A buys a permanent two-key split that every later writer must learn. What decided it was the affirmed text — *"takes that name everywhere our files mean it"* — and that key means the agreement.

## Scope, and what was deliberately not done

No rename of generic, lens, review or handback briefs, and none of the verb. No edit to any existing settling row, frozen decision, review record or recorded finding for vocabulary. No move of acceptance criteria, falsifiers, the boundary statement or cold-seat mechanics into the implementation brief — that would rebuild the artifact under a new name, which is the owner's exclusion breached from the other side. The `artifact` / build-output collision open on [#273](https://github.com/Grimblaz-and-Friends/tradecraft/issues/273) is untouched.

The always-on statement is the owner's own sentence, kept verbatim and never reworded, with its depth routed to the `engagement` cell rather than stated in the charter — the charter holding only what must bind before any cell loads.
