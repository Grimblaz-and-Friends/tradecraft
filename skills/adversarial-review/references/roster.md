# Staffing the panel — the roster, the seats, and the tier each gets

**Loaded when** you are choosing who sits on a review — the panel's seats, the defense, the judge, a post-fix look — or deciding what model tier staffs them. A recipient carrying out a brief it was handed does not need it.

## The roster — five names, four or five seated

Three seats stand; the fourth is chosen by the artifact's shape, and where the artifact is both shapes — the common case here — both shape seats sit and the panel is five. Seats differ or they are waste: a seat is added for a lens or vantage the panel lacks, never for a second pass at one it has. A **vantage** is where a seat reads from — cold, briefed, or as the consumer; a **lens** is what it is told to look for. What a dispatch prompt could have said is a lens, not a vantage.

- **`cold-read`** — fresh vantage, no lens brief: forms its own view of the artifact before this review's findings exist for it. A brief aims attention, and aimed attention has a shadow; this seat is what falls in it.
- **`wiring-falsifier`** — scripts and contracts: does the code enforce what the prose claims, does anything call it, can each guard actually fail? Probe by execution, not reading.
- **`operational`** — walk the artifact as its consumer: a fresh executor following the text, reporting where it under-determines or misleads action.
- **The fourth seat, by shape:** **`claims-vs-evidence`** on substantially new prose — verify every load-bearing claim, number, and quotation against its cited source; also the default when no shape fits. **`revision-diff`** on amendments to governing prose — report every load-bearing sentence whose *meaning* changed without the change being recorded (in the decision entry where one exists, else the PR body), including the sentence whose characters never changed while a term it turns on was redefined elsewhere in the change; the unit of comparison is the governing claim, not the diff hunk, so its read scope is the whole change. When the artifact is both shapes, both seats sit and the panel is five. A needed lens the roster lacks — `security` on a write path or trust boundary, `position` when the artifact builds on an unreviewed design (review the earlier artifact first; position beats depth) — takes the shape slot or widens the panel by declared risk, named in the report.

**The width is measured, and on this repository's own record.** Across the 25 panel-lane reviews in `tradecraft` dated 2026-08-26 or later that booked a sustained high — the window opening where reports began naming each high's finders — 81 panel-originated sustained highs were recovered, **55 of them carrying attribution** and 50 of those naming a primary finder. Retention of those highs by the panels this roster actually staffs:

| the panel | of the 55 attributed | of the 50 naming a primary |
| --- | --- | --- |
| the three standing seats alone | 76% | 64% |
| four — the standing seats and `claims-vs-evidence` | 91% | 84% |
| four — the standing seats and `revision-diff` | 87% | 80% |
| five — both shape seats sitting | 100% | 100% |

Both columns are given because they bracket, and neither is the answer alone: the first cannot tell a high one seat found from one all five found, the second cannot see a co-finder at all and drops the five attributed highs that name no primary. **These are the panels this roster permits, not best-available subsets** — the recomputation also orders seats by hindsight, and every interior point of that ordering describes a panel this roster does not staff, so its curve is not comparable to the table above.

**What the fifth chair buys is the second shape seat, and it is not marginal:** `claims-vs-evidence` and `revision-diff` are the sole finders of 12 of the 20 sole-found highs in the corpus, the two strongest records on it. Whether that is worth a dispatch is a worth-it judgement and not a measurement.

**What the figures cannot settle**, which matters as much as what they say: 26 of the 81 panel highs name no finder anywhere, all but one because six whole reviews published no attribution at all. Over all 81, a four-seat panel therefore lands between 59% and 94%, depending on whether the unattributed resemble the attributed. [The recomputation](https://github.com/Grimblaz-and-Friends/tradecraft/issues/138#issuecomment-5519548671) carries the corpus, the per-seat table, the sensitivity bound and the re-run recipe; it discharges the trigger [D-185] set, and [D-336] records what it settled.

**The predecessor's figure is retired rather than carried here** — a single pass keeping 12% of sustained yield ([the mining record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/1)). It measured yield across every severity, a different quantity from the highs-only retention above, so the two cannot be set beside each other. Nothing refuted that figure: [a local spike](https://github.com/Grimblaz-and-Friends/tradecraft/issues/138#issuecomment-5389959332) separately put one cold pass on this practice's own artifacts at close to the same 12%.

**The cold boundary, operationally**: a dispatch read cold carries the assignment and none of the review's history: no prior findings, no self-review, no conversation context, and not the PR's comment thread, which carries another party's findings within seconds of the PR opening. A cold seat is therefore always a fresh dispatch with context inheritance disabled, never the session that authored or discussed the artifact — and the rule reaching every other role, that defense and judge are never the artifact's author and the judge never a finder, is in the dispatch contract (`../references/dispatch.md`). **A session note is not among the things withheld**, and carrying it spends that vantage rather than preserving it: a note names the sentences use actually broke on, so a seat reads it already pointed. It travels in the assignment (`../references/dispatch.md`) because real-use evidence is worth that price, not because it costs nothing.

**Two more things are carried rather than withheld, at that same price and argued the same way.** A finding an earlier review **recorded** against this artifact travels in the assignment: the disposition exists to be met again, and a seat that never sees it cannot meet it. And a post-fix look is given the merged finding list, without which it cannot locate each sustained high's territory — which is its floor (`../references/after-the-fix.md`), and which it reads as input and never as a subject. Both spend a little of the cold vantage. Both are worth it for the reason the note is: withholding them leaves an obligation nobody can discharge, and a rule nobody can discharge is not a boundary but a dead letter.

## Staffing

Every seat runs at the strongest model tier the runtime's budget bears. Where the top tier is scarce, concentrate it where open-ended perception lives — the `cold-read` — and where single dispatches carry the most leverage — the judge. Terminal stages run at least the seats' reasoning effort. Each launch names its model and reasoning effort explicitly; a runtime default is not review evidence. The report records which model and runtime staffed each seat, so per-runtime evidence can accumulate; how that value is spelled is the record's (`../references/the-record.md`), and one spelling per runtime is what makes it a query.
