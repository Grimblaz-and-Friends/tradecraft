# D-570 — The `experience-session` cell sheds three subjects, and the disqualifier is read against moments rather than trigger clauses

**Landed by** [PR #570](https://github.com/Grimblaz-and-Friends/tradecraft/pull/570), closing [#515](https://github.com/Grimblaz-and-Friends/tradecraft/issues/515). Brief affirmed 2026-09-09 at [issue #476 comment](https://github.com/Grimblaz-and-Friends/tradecraft/issues/476#issuecomment-5609749676), covering the whole set of nine; artifact settled at [issue #515 comment](https://github.com/Grimblaz-and-Friends/tradecraft/issues/515#issuecomment-5627094346). **Evidence at two endpoints, and each figure says which.** What the tree held before this change is read at `686a3bc`; every figure describing the tree this change produces is derived at this branch, as `len()` over decoded UTF-8.

## What was decided

`skills/experience-session/SKILL.md` at `686a3bc` was **12,151** characters below its frontmatter against a ceiling of `11_802`, with two depth files already beside it. Three of its six sections each serve one moment of use and nothing else, and each becomes one file under `skills/experience-session/references/`:

| new file | source at `686a3bc` | characters, heading included |
| --- | --- | --- |
| `skills/experience-session/references/running-one.md` | `## Running one`, L51–L67 | 5,274 |
| `skills/experience-session/references/the-note.md` | `## What a note carries`, L31–L41, plus L69 | 2,290 |
| `skills/experience-session/references/when-one-fires.md` | `## When one fires`, L43–L49 | 1,872 |

The body keeps the purpose header, a five-entry depth index, `## The instrument — three pieces, nothing more` and `## What it is for, and where it stops`. **3,575 characters**, and `tools/lint.py`'s ceiling for this body is rebaselined to it, as that map's own comment requires of a cell that sheds depth.

## The disqualifier is read against moments of use, not against the description's trigger clauses, and that is the call

`skills/authoring/references/cell-structure.md` states the test as *what one trigger among several needs belongs in `references/`*, and reads it as a disqualifier — *a cell is too big when a session loads prose it had no use for*. **Those two phrasings come apart in this cell, and the second is the one that governs.** This description carries two `Use when` clauses — a change has been built, and a review's fix batch has rewritten what the material instructs — and **both open the whole arc**: decide, run, write up. Read against the clauses alone, nothing in this cell is one-trigger prose and the body is unsplittable; read against the moments a session is actually at, three subjects fall out cleanly, because **no session is at more than one of those moments at a time.**

**The first moment is the one that pays for the split.** The charter's Release bullet sends every non-mechanical change to it — *"or one line saying why none happened; the `experience-session` cell carries both, and what that line must say"* — and most changes stop there, having bought no run. At `686a3bc` that arrival loaded the whole dispatch procedure and the whole of what a note carries. It now loads neither.

This is recorded because the next session finishing a split under #476 will meet a cell whose description's clauses do not partition its body, and the answer is not that the cell is already correct.

## Three smaller calls

- **L69 leaves `## Running one` for the note's file.** It is the one departure from moving whole sections: it says where the note lands and by when, which a session composing a dispatch has no use for and a session writing one up needs. The section it leaves is otherwise moved entire.
- **L55 stays with the dispatch, not with the note.** *"The note is written by the session that chartered it, from the consumer's own account of the run"* reads as note-authorship, and its operative half is a dispatch-time instruction — ask the consumer for an ordinary report, never for a session note, because a cold consumer told there is a session is no longer cold. A session that opened only `the-note.md` would have already blown the coldness by then, so it stays where the dispatcher reads it.
- **The body gains no inline pointer to the three new files.** `cell-structure.md` makes the index the authority — *"Inline pointers stay lawful wherever a paragraph wants one; what they stop being is the record"* — and neither remaining section has a paragraph that wants one. An inline pointer here would be a new sentence written to host it, which is prose this change is otherwise not adding.

## What was rejected

- **Keeping `## What a note carries` in the body and shedding only the two larger sections.** It is the shape that leaves the body nearest its siblings in size, and it fails the disqualifier for the highest-frequency arrival: a session asking whether a finished change owes a run would still load 1,964 characters about writing up a run it has not had.
- **Splitting `skills/experience-session/references/isolation.md`.** At 9,228 bytes it is the largest file in the cell, larger than the body it sits under. Whether depth should itself be split is [#457](https://github.com/Grimblaz-and-Friends/tradecraft/issues/457)'s question and is outside the brief's scope; the lint prices a cell's `SKILL.md` and not its depth.

## Nothing is cut, and the accounting

Of the non-blank lines below the frontmatter at `686a3bc`, every one appears verbatim in exactly one of the four files, with **five exceptions and no line found twice**. **Two are pointer repairs the move makes obligatory**: a pointer written as `references/` plus a filename resolves against its own file's directory, so from inside `references/` it lands a level too deep and `tools/lint.py` reports it; L65 and L67 gain the `../` prefix. **Three are headings that become file titles** — `## Running one` keeps its words; `## When one fires` becomes `# When a session fires`; `## What a note carries` becomes `# The session note`, wider than the heading it replaces because that file also holds L69.

**Two lines change that no source line moved, both in `skills/experience-session/references/running-instance.md`.** `:17` credited *"the cell, under what a note carries"* with the run-record rule, naming a section of the body by its heading — and this change is what removes that heading. And `:3`'s bare `` `isolation.md` `` gains the `../references/` prefix, so that every sibling pointer in this cell is written in the one form `tools/lint.py` reads: a review probe renamed a depth file and found the bare spellings silently unreported where the path form raises `reference-pointer` and exits 1. `skills/experience-session/references/isolation.md:3`'s *"the isolation rule it serves is in the cell whose run it is"* is a cell-level credit and survives the rule moving within the cell, so it is left alone.

## Cost

The cell's own prose grows **24,147 → 26,117** characters by the lint's reach measure, **+1,970** — three titles, three load conditions, three index entries, five sibling pointers written in the guarded form, and the routing and trigger repairs the review ordered, against no deletion. Every cell that points at `experience-session` carries the increase in its reach row. What the split buys is not what the cell weighs but what a session loads on a given firing, which is the same trade [D-263](D-263-2026-08-30-the-isolation-procedure-sheds-and-states-its-conditions.md) recorded for this cell's first shed, and recorded honestly: that shed left both the body and the cell total larger than they began. This one does not — the body falls 12,151 to 3,611 — and the total still rises.

## What the record cannot say for itself

`docs/recorded-findings.jsonl` carries 20 entries naming this cell. **Six cite a body line** — lines 13, 14, 42, 54 and 56 — and **fourteen name `skills/experience-session/SKILL.md` in their `artifact` field, twelve of them for text this change moves out of it**, into `skills/experience-session/references/when-one-fires.md`, `skills/experience-session/references/running-one.md` and `skills/experience-session/references/the-note.md`. The body renumbers from 69 lines to 32, so every citation above 32 resolves past the file's end.

**The line citations were already stale at `686a3bc`, and this change is not what broke them** — there, `:14`, `:42`, `:54` and `:56` are blank lines and `:13` is the `running-instance.md` depth-index entry, where the entry citing it is about the Time-box bullet's unit list. **What this change does break is the file half of those twelve `artifact` locators**, which is the locator the next review's dispatch hands a seat; the two that stay correct are the entry about the Time-box bullet, still in the body, and the one about the description, which is untouched. The same goes for four frozen decision entries that locate rules in this cell by heading name — D-132, D-173, D-263 and D-314 — the three headings having become file titles as recorded above. Nothing maintains either record, so this is the only surface where it can be said.

**That count is the third this change produced, and the two before it were wrong** — four, then five, then six — because the class depends on **how a citation is spelled** and there are three spellings: `experience-session/SKILL.md:N`, a bare `:N` in prose, and `Line N` in words. Each pass used a grep shape that saw one or two of the three, and a bare-colon sweep also admits another file's `:N` as a false positive. **A class named by the grep that found it understates itself**; the enumeration that holds was read entry by entry.

**No recorded entry's stated ground is falsified by this change**: the nearest, entry 108, gives *"prose on a cell already in net growth"*, and the cell's own prose still grows.

## The cold seat, and the one thing left unrepaired

One round, verdict `would`, settled on the first with no revision. The seat reconstructed all six files of the cell byte-exactly from the artifact and the base tree on its first attempt, and re-ran four of the five criteria against the tree independently.

It reported two observations, neither a ground, and **one is a real ambiguity in a judged criterion**. Criterion 3's arm 2 — *"pointing it at a sibling that does not exist"* — is **true read as the `../references/` path form** (a `reference-pointer` finding, exit 1) and **false read as a bare filename** (`lint: 0 finding(s)`, exit 0), because `RELATIVE_MD_REF` matches only the path form. **It was left as settled rather than repaired**: repairing a claim the verdict turned on is a fresh draft under the `engagement` cell's narrowing and buys a fresh dispatch, and the seat's own ground was that the artifact's Boundary settles the reading and that this is a check arm rather than a build instruction. The true behaviour of both readings is recorded in the pull request body and here, which is what the repair would have bought.
