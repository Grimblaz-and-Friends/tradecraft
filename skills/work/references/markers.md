# Work evidence markers

**Loaded when** recording evidence that the state-driven entrance will read, or interpreting why it selected a stage. A marker is an HTML comment on the surface named below; attribute values contain no whitespace, and a reason uses a hyphenated slug. It advances the entrance only when its issue body or comment author is named by the repository's marker-producer configuration, because an untrusted commenter cannot stand in for the party each contract names.

The entrance validates every claim against the contract below before using it: the surface and authorized producer, exact required and optional attribute names, lawful values and formats, required accompanying prose, and any identity that must be unique all have to hold. It reports malformed, wrong-surface, unauthorized, ambiguous and unverifiable claims instead of advancing on them, because a typed marker cannot establish more than its source proves.

For a marker produced by a dispatched stage, the latest matching successful bundle for the same work and stage, completed no later than the marker, is the source of truth. `builder-session` agrees with the build bundle's observed session; `floor` agrees with the floor bundle's revision and successful return; and `cold-verdict` and `use` take staffing, fallback and same-vendor facts from the seat run record. An absent or ambiguous bundle, or marker text disagreeing with it, does not satisfy the claim. Intrinsic holder-authored markers with no dispatched producer remain governed by their own contract here.

## `affirmed-brief`

- **Exact form:** `<!-- tradecraft:affirmed-brief:v1 -->`.
- **Attributes and lawful values:** none. Its comment contains exactly one lawful `Review risk` and `Review lane` pair.
- **Producer, surface, moment:** the holder, in the issue comment carrying the affirmed implementation brief, immediately after affirmation is recorded.

```text
<!-- tradecraft:affirmed-brief:v1 -->
```

## `artifact`

- **Exact form:** `<!-- tradecraft:artifact:v1 status=STATUS -->`.
- **Attributes and lawful values:** `status=draft|settled`.
- **Producer, surface, moment:** the holder, in the issue comment carrying the artifact return, when the draft arrives and again when it takes a lawful settlement route.

```text
<!-- tradecraft:artifact:v1 status=draft -->
```

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

- **Exact form:** `<!-- tradecraft:builder-session:v1 session=SESSION -->`.
- **Attributes and lawful values:** `session` is the UUID-shaped session identity printed by the implementer launcher.
- **Producer, surface, moment:** the holder, in a comment on the issue, when the build return and launcher output arrive.

```text
<!-- tradecraft:builder-session:v1 session=01234567-89ab-cdef-0123-456789abcdef -->
```

## `model-override`

- **Exact form:** `<!-- tradecraft:model-override:v1 [ROLE=VENDOR:MODEL:EFFORT ...] -->`, where each bracketed role attribute is optional and may appear at most once.
- **Attributes and lawful values:** the lawful role attributes are `implementer`, `ordinary_seat`, `cold_seat`, `terminal_seat`, and `use_consumer`, corresponding to the roles `implementer`, `ordinary-seat`, `cold-seat`, `terminal-seat`, and `use-consumer`. Each present value is one complete `VENDOR:MODEL:EFFORT` triple; `VENDOR` is `codex` or `claude`, and `MODEL` and `EFFORT` are nonempty values containing no whitespace or colon. Unknown or duplicate attributes and malformed triples are invalid.
- **Whole-line precedence:** the latest lawful line is the entire current override choice and replaces every earlier line rather than merging with it. A role absent from that line uses the selected launcher's standing default. A lawful line with no role attributes restores every role to its standing default.
- **Producer, surface, moment:** a configured marker producer, in an issue comment on the work, after the owner gives the choice and before a launch it is to govern. Absence of a role on the latest lawful line means the named launcher's standing default, not an inferred choice from prose.

The motivating choice, with ordinary seats at `high` and cold, terminal, and use seats at `max`, is one line:

```text
<!-- tradecraft:model-override:v1 ordinary_seat=claude:claude-opus-5-5:high cold_seat=claude:claude-opus-5-5:max terminal_seat=claude:claude-opus-5-5:max use_consumer=claude:claude-opus-5-5:max -->
```

A later bare line returns every role to its standing default:

```text
<!-- tradecraft:model-override:v1 -->
```

## `floor`

- **Exact form:** `<!-- tradecraft:floor:v1 head=SHA status=STATUS -->`.
- **Attributes and lawful values:** `head` is the tested pull-request head SHA; `status=pass`.
- **Producer, surface, moment:** the builder returning the floor stage to the holder, in the issue or pull-request comment carrying the exact command output, after the floor passes at that head.

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

## `no-use`

- **Exact form:** `<!-- tradecraft:no-use:v1 head=SHA -->` followed in the same comment by `Use: not required` and its reason.
- **Attributes and lawful values:** `head` is the pull-request head SHA whose changed paths were classified.
- **Producer, surface, moment:** the proof command, in its pull-request proof comment, after the path rules conclude no use was bought and before the pull request is marked ready. The legacy holder-authored form remains accepted for the compatibility release.

```text
<!-- tradecraft:no-use:v1 head=0123456789abcdef0123456789abcdef01234567 -->
```

## `proof`

- **Exact form:** `<!-- tradecraft:proof:v1 head=SHA -->` followed by the fenced version-one JSON object and its readable rendering.
- **Attributes and lawful values:** `head` is the full pull-request head the object describes and equals `identity.head` inside the object.
- **Producer, surface, moment:** the holder through `run proof`, in the command-owned pull-request comment, after any evidence update whose current state should be presented to the gate.

```text
<!-- tradecraft:proof:v1 head=0123456789abcdef0123456789abcdef01234567 -->
```

The object and publication contract are `proof.md`. For one compatibility release, the entrance continues to accept the marker family above as input and the proof comment also carries a generated `no-use` carrier when no use was bought.

## `connected-reviewer`

- **Exact form:** `<!-- tradecraft:connected-reviewer:v1 name=NAME status=STATUS -->`.
- **Attributes and lawful values:** `name` is the reviewer's nonempty integration identifier; `status=complete`.
- **Producer, surface, moment:** the builder, in the final disposition reply on the pull request, once that connected review has run and every comment from it is dispositioned.

```text
<!-- tradecraft:connected-reviewer:v1 name=review-bot status=complete -->
```

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
