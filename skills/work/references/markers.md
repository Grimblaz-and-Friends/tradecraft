# Work evidence markers

**Loaded when** recording evidence that the state-driven entrance will read, or interpreting why it selected a stage. A marker is an HTML comment on the surface named below; attribute values contain no whitespace, and a reason uses a hyphenated slug.

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
- **Producer, surface, moment:** the holder, in an issue or pull-request comment, after the path rules conclude no use was bought and before the pull request is marked ready.

```text
<!-- tradecraft:no-use:v1 head=0123456789abcdef0123456789abcdef01234567 -->
```

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
