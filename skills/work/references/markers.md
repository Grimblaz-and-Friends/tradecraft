# Work evidence markers

**Loaded when** recording evidence that the state-driven entrance will read, or interpreting why it selected a stage. A marker is an HTML comment on the surface named below; attribute values contain no whitespace, and a reason uses a hyphenated slug. It advances the entrance only when its issue body or comment author is named by the repository's marker-producer configuration, because an untrusted commenter cannot stand in for the party each contract names.

The entrance validates every claim against the contract below before using it: the surface and authorized producer, exact required and optional attribute names, lawful values and formats, required accompanying prose, and any identity that must be unique all have to hold. It reports malformed, wrong-surface, unauthorized, ambiguous and unverifiable claims instead of advancing on them, because a typed marker cannot establish more than its source proves.

For a marker produced by a dispatched stage, the latest matching successful bundle for the same work and stage, completed no later than the marker, is the source of truth. `builder-session` agrees with the build bundle's observed session; `floor` agrees with the floor bundle's revision and successful return; and `cold-verdict` and `use` take staffing, fallback and same-vendor facts from the seat run record. An absent or ambiguous bundle, or marker text disagreeing with it, does not satisfy the claim. Intrinsic holder-authored markers with no dispatched producer remain governed by their own contract here.

## How a source makes a claim

Before interpreting a source, the entrance sets aside marker text inside inline code, fenced or indented code blocks, and blockquotes. Those occurrences are quotations and never assert a claim.

A source's first line of content is its first nonblank line. An ordinary issue body, issue comment, pull-request body or pull-request comment opens with a marker only when that first line is an unquoted marker. The source asserts that marker kind and the unquoted marker kinds its contract lists as travelling with it; every other marker in that source is a quotation. A heading or prose before the first marker therefore makes every marker in that source a quotation. The entrance reports every marker it sets aside with its kind and source, so a holder can locate a real co-claim that the contract does not carry.

A reviewer-thread reply instead opens with a disposition when its first line of content begins with a lawful disposition word after permitted inline formatting around the opening word is removed. The `connected-reviewer` marker travels with that disposition and counts anywhere unquoted in the reply. It counts nowhere else: the disposition remains first and the marker remains appended to the reply.

| Opening claim | Claims that travel with it |
|---|---|
| `artifact` with `status=settled` | `cold-verdict` |
| `implementing-pr` | `builder-session` |
| lawful disposition opening a reviewer-thread reply | `connected-reviewer` |

A `cold-verdict` beside an artifact with `status=draft` is therefore a quotation. A marker kind absent from the applicable row does not acquire meaning merely by appearing in the same source. A source opening with neither an unquoted marker nor a reviewer-thread disposition asserts no marker claims.

## `affirmed-brief`

- **Exact form:** `<!-- tradecraft:affirmed-brief:v1 -->`.
- **Attributes and lawful values:** none. Its comment contains exactly one lawful `Review risk` and `Review lane` pair.
- **Producer, surface, moment:** the holder, in the issue comment carrying the affirmed implementation brief, immediately after affirmation is recorded.

```text
<!-- tradecraft:affirmed-brief:v1 -->
```

## `artifact`

- **Exact form:** `<!-- tradecraft:artifact:v1 status=STATUS [route=ROUTE] -->`.
- **Attributes and lawful values:** `status=draft|settled`; a settled artifact requires `route=would|cap|discharge|unobtainable`, while a draft carries no route.
- **Producer, surface, moment:** the holder, in the issue comment carrying the artifact return, when the draft arrives and again when it takes a lawful settlement route.

```text
<!-- tradecraft:artifact:v1 status=draft -->
```

### Artifact terms and settlement routes

An artifact term begins at the latest affirmed brief or amendment, so only later artifact claims belong to it. A cold verdict qualifies only after the artifact draft it judges. Only a qualifying verdict for the latest draft can support `would` or `discharge`; a newer draft ends that power but retains each qualifying `would-not` in the term's cap count. Only an amended brief starts a new term and restarts the count.

A settled artifact follows the draft it settles and the verdicts supporting its route. Every settlement requires a draft in its current term; `unobtainable` means no qualifying verdict judges that draft, not that the draft is absent. A qualifying verdict carried in the settlement's own source is ordered immediately before the settlement and can support it. The routes mean:

- `would` requires the latest qualifying verdict for the latest draft to be `would`.
- `cap` requires two qualifying `would-not` verdicts in the term, across any drafts, and no qualifying `would` for the latest draft.
- `discharge` requires a qualifying `not-settleable` verdict for the latest draft.
- `unobtainable` requires no qualifying verdict for the latest draft.

An unsupported route does not settle the phase. A settled marker without a route is also invalid. In the current term its diagnostic tells a change in flight to re-post it once with the route the record supports; after a later affirmed brief supersedes that term, the diagnostic records the historical invalid claim and says no re-post is needed.

That route-only re-post retains the earlier routeless settlement's place in the term when no affirmed brief, amendment, artifact draft or cold verdict intervenes. A holder reading may intervene: the old marker remains invalid and reported, the new marker supplies the route and source, and the earlier position decides whether that reading follows the settlement. The latest eligible routeless marker supplies the position when more than one exists. That inherited position is spent by the first routed settlement that uses it, so a later settlement takes its own position and requires a later holder reading.

A holder reading counts only after the latest effective settlement. A newer draft reopens the phase; a later supported settlement closes it again.

## `cold-verdict`

- **Exact form:** `<!-- tradecraft:cold-verdict:v1 verdict=VERDICT staffing_status=STATUS [same_vendor_reason=REASON] -->`.
- **Attributes and lawful values:** `verdict=would|would-not|not-settleable`; `staffing_status=qualified|degraded`; `same_vendor_reason` is a nonempty slug present only when a degraded same-vendor result is accepted for this stage.
- **Producer, surface, moment:** the holder, in the issue comment carrying the cold seat's whole return, when that return arrives.

```text
<!-- tradecraft:cold-verdict:v1 verdict=would staffing_status=qualified -->
```

## `holder-reading`

- **Exact form:** `<!-- tradecraft:holder-reading:v1 result=RESULT -->`.
- **Attributes and lawful values:** `result=no-amendment|amended`.
- **Producer, surface, moment:** the holder, in the issue comment carrying the whole-change reading, after a qualifying cold verdict and before the first build.

```text
<!-- tradecraft:holder-reading:v1 result=no-amendment -->
```

## `builder-session`

- **Exact form:** `<!-- tradecraft:builder-session:v1 session=SESSION [vendor=VENDOR] -->`.
- **Attributes and lawful values:** `session` is the UUID-shaped session identity printed by the implementer launcher; optional `vendor` is `codex` or `claude`. A matching dispatch bundle proves the vendor and must agree with a present attribute. Without a bundle, a vendor-qualified marker is the recovery route after the holder verifies the original runtime record; a UUID alone proves no vendor.
- **Producer, surface, moment:** the holder, in a comment on the issue, when the build return and launcher output arrive.

```text
<!-- tradecraft:builder-session:v1 session=01234567-89ab-cdef-0123-456789abcdef -->
```

## `model-override`

- **Exact form:** `<!-- tradecraft:model-override:v1 [ROLE=VENDOR:MODEL:EFFORT ...] -->`, where each bracketed role attribute is optional and may appear at most once.
- **Attributes and lawful values:** the lawful role attributes are `artifact_author`, `implementer`, `ordinary_seat`, `cold_seat`, `terminal_seat`, and `use_consumer`, corresponding to the artifact author, builder, and judging roles. Each present value is one complete `VENDOR:MODEL:EFFORT` triple; `VENDOR` is `codex` or `claude`, and `MODEL` and `EFFORT` are nonempty values containing no whitespace or colon. Unknown or duplicate attributes and malformed triples are invalid.
- **Whole-line precedence:** the latest lawful line is the entire current override choice and replaces every earlier line rather than merging with it. A missing implementer role uses the machine vendor and that role's profile; a missing judging role uses default resolution, including an applicable machine-local ruling bridge. A lawful line with no role attributes clears all earlier entries.
- **Producer, surface, moment:** a configured marker producer, in an issue comment on the work, after the owner gives the choice and before a launch it is to govern. Absence of a role on the latest lawful line means default resolution under `launch-settings.md`, not an inferred choice from prose.

An example choice, ordinary seats at `high`, cold and terminal seats at `xhigh` and use consumers at `max`, is one line:

```text
<!-- tradecraft:model-override:v1 ordinary_seat=claude:claude-opus-5-5:high cold_seat=claude:claude-opus-5-5:xhigh terminal_seat=claude:claude-opus-5-5:xhigh use_consumer=claude:claude-opus-5-5:max -->
```

A later bare line returns every role to default resolution:

```text
<!-- tradecraft:model-override:v1 -->
```

## `floor`

- **Exact form:** `<!-- tradecraft:floor:v1 head=SHA status=STATUS -->`.
- **Attributes and lawful values:** `head` is the tested pull-request head SHA; `status=pass`.
- **Producer, surface, moment:** the builder returning the floor stage to the holder, in the issue or pull-request comment carrying the exact command output, after the command passes at the actual tested head. The builder returns this line and result; the holder posts them without reconstructing the marker.

```text
<!-- tradecraft:floor:v1 head=0123456789abcdef0123456789abcdef01234567 status=pass -->
```

## `use`

- **Exact form:** `<!-- tradecraft:use:v1 head=SHA status=STATUS changed=CHANGED staffing_status=STAFFING_STATUS [same_vendor_reason=REASON] -->`.
- **Attributes and lawful values:** `head` is the used pull-request head SHA; `status=pass`; `changed=true|false`; `staffing_status=qualified|degraded`; `same_vendor_reason` follows the same degraded-stage rule as `cold-verdict`.
- **Producer, surface, moment:** the holder, in the issue or pull-request comment carrying the consumer's session note, when the run finishes against that head.

```text
<!-- tradecraft:use:v1 head=0123456789abcdef0123456789abcdef01234567 status=pass changed=false staffing_status=qualified -->
```

## `proof`

- **Exact form:** `<!-- tradecraft:proof:v1 head=SHA -->` followed by the fenced version-one JSON object and its readable rendering.
- **Attributes and lawful values:** `head` is the full pull-request head the object describes and equals `identity.head` inside the object.
- **Producer, surface, moment:** the holder through `run proof`, in the command-owned pull-request comment, after any evidence update whose current state should be presented to the gate.

```text
<!-- tradecraft:proof:v1 head=0123456789abcdef0123456789abcdef01234567 -->
```

The object and publication contract are `proof.md`. The gate evaluates only an authorized current-head proof document; its `use` section is the sole no-use carrier. Standalone historical markers cannot replace that document.

## `connected-reviewer`

- **Exact form:** `<!-- tradecraft:connected-reviewer:v1 name=NAME status=STATUS -->`.
- **Attributes and lawful values:** `name` is the reviewer's nonempty integration identifier; `status=complete`.
- **Producer, surface, moment:** the builder, in the final disposition reply on the pull request, once that connected review has run and every comment from it is dispositioned.

```text
<!-- tradecraft:connected-reviewer:v1 name=review-bot status=complete -->
```

The connected-reviewer reference maintains the lawful disposition words as a closed vocabulary. For matching, the entrance removes permitted inline formatting around the reply's opening word and then applies the same word-and-delimiter test as an unformatted disposition. Formatting never makes a word outside that vocabulary lawful. A gate that reads dispositions must apply the same rule, or the entrance and gate disagree about whether the reply is complete.

Body-finding and unidentified-review answers instead open with the bare disposition word in an individual pull-request conversation comment. Their exact identity and source-link contract belongs to the connected-reviewer reference. Finding identities are reviewer data, not stage markers; conversation answers gain no stage-marker authority from this rule.

## `panel-stage`

- **Exact form:** `<!-- tradecraft:panel-stage:v1 stage=STAGE status=STATUS -->`.
- **Attributes and lawful values:** `stage=cold-pass|revision-diff|four-seat-panel|defense|judge|floor-fixes`; `status=complete`.
- **Producer, surface, moment:** the holder, in the issue comment carrying that stage's return or disposition, as each bought panel stage completes.

```text
<!-- tradecraft:panel-stage:v1 stage=defense status=complete -->
```

## `product-incident`

- **Exact form:** `<!-- tradecraft:product-incident:v1 repo=OWNER/REPOSITORY issue=NUMBER -->`.
- **Attributes and lawful values:** `repo` is an entry in the repository-owned product list, compared case-insensitively; `issue` is a positive integer.
- **Producer, surface, moment:** the issue author or holder, in the issue body or a later issue comment, when naming the product incident that the work answers; a full issue URL is the equivalent evidence.

```text
<!-- tradecraft:product-incident:v1 repo=acme/product-app issue=91 -->
```

## `implementing-pr`

- **Exact form:** `<!-- tradecraft:implementing-pr:v1 number=NUMBER -->`.
- **Attributes and lawful values:** `number` is the positive integer number of the pull request that implements this issue.
- **Producer, surface, moment:** the holder, in a comment on the implemented issue, immediately after opening the implementing pull request as a draft.

```text
<!-- tradecraft:implementing-pr:v1 number=91 -->
```
