# A pitch, and a comment extending one

**Loaded when** you are writing the body of a new pitch or a comment extending an open one. Copy the block whole and fill every field; a hint in `<!-- -->` is deleted as its field is filled. What each field must meet is `../references/what-a-filing-carries.md`'s, and what a tie line means is `../references/naming-a-tie.md`'s.

## The issue body

```
<verb> #<N> — <one clause of why>
<!-- the first element of the body; one tie per line, a pair may take more than one verb; a relationship no verb expresses is prose here, flagged as a candidate for the set -->
<!-- or one of: `no siblings on the board`; `its cause is linked (#<N>)` where the cause is the only relationship; `cause #<N>, not linked — <no access | in another repository>` where it could not be set -->

**<the want or defect, in plain terms>**

**Evidence:** <the probe command and its output; or the breached rule's own sentence with its location; on governing prose, also the incident or the run>

**Provenance:** <review | use | owner | session | instrument> — <which review, run, instruction or check, and when>
<!-- review: a seat, defense, terminal stage, judge or external reviewer; use: an experience session, cold seat, consumer, dispatched recipient or A/B run outside a review; owner: their direction or a sitting with them; session: noticed while doing other work; instrument: a script or guard raised it; none fits: the nearest, and why, on this line -->

**Value:** <what buying this is worth, against the live alternatives and their costs>
**Against:** <the strongest case for not buying it>

**Deferred to pickup:** <what discovery must settle; or: nothing>
```

After creation: `python ../scripts/pool.py rate <N> --rating sev:<1-4> --rating urg:<1-4>` — the two proposed ratings, as labels.

## The extending comment

```
**Extends this pitch:** <one clause — what the new evidence shows>

**Evidence:** <the probe command and its output; or the incident or the run>

**Provenance:** <review | use | owner | session | instrument> — <which review, run, instruction or check, and when>

**Value:** <what this changes about the offer; or: nothing — one more instance>
```
