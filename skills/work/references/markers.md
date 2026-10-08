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

- **Exact form:** `<!-- tradecraft:artifact:v1 status=STATUS [route=ROUTE] [draft_comment=COMMENT_ID draft_sha256=SHA256] -->`.
- **Attributes and lawful values:** `status=draft|settled`; a settled artifact requires `route=would|cap|discharge|unobtainable`, while a draft carries no route or draft reference. `draft_comment` and `draft_sha256` appear together: the former is a positive decimal issue-comment id, and the latter is a lowercase hexadecimal sha256.
- **Producer, surface, moment:** the holder, in an issue comment, when the whole draft return arrives and when it takes a lawful settlement route.

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

A new settlement names its draft with `draft_comment` and `draft_sha256`. The digest is computed over the draft comment's whole body as GitHub returns it, with CRLF and CR line endings replaced by LF, then encoded as UTF-8 and hashed with sha256. The cold dispatch states its digest on that basis, so the holder copies it. The entrance freezes the named draft's id, digest and exact input slice in the cold seat's request and run record; the dispatch-records reference in the engagement cell owns that binding.

On `would` and `unobtainable`, post the reference and the route's record without repeating the artifact. The entrance supplies the named draft's whole text and refuses its consumption if the comment is missing or is not the latest lawful draft in the term. On `would`, the same successful bundle that proves the supporting verdict's staffing also proves its judged draft id and digest. A different id refuses even when the bodies hash equally. If the current body differs from the judged digest, the draft was edited after its verdict: restore the judged text, or post a new draft for a fresh cold seat. If that body still matches the judgment but the settlement digest differs, the digest was miscopied: re-settle with the judged digest; no new seat is needed. Editing takes precedence over copying when both differ. On `unobtainable`, only the current-body comparison applies, so a mismatch cannot distinguish editing from copying. Do not use the observed digest to re-settle: restore the settled text, or post a new draft. The original draft marker remains provenance; the settlement makes that text settled.

A supported seat record produced before `0.190.0` without a binding remains usable on the current-body check, and every applicable verdict is reported as **judged digest unrecorded**, including adverse verdicts used by discharge or the cap count. A mismatch under that compatibility rule cannot distinguish editing from copying. Do not use the observed digest to re-settle: restore the judged text, or post a new draft for a fresh cold seat; the miscopy remedy requires a recorded judgment. Missing or malformed modern binding evidence refuses rather than becoming historical compatibility; missing producer provenance does not establish an old record. The completed run's binding must agree with its frozen request and retained input, because today's issue body cannot reconstruct what an old seat received.

On `discharge` and `cap`, post the whole revised artifact with its affirmed brief and name the draft it revises. The entrance supplies that revised text without resolving or checking the named draft, because the draft is not the builder's input.

A settlement without a draft reference remains usable only when it carries a whole artifact recognized by the same affirmed-brief-and-body check as an artifact return. For `would`, this compatibility form requires a pre-change supporting record with its judged digest unrecorded; a bound judgment always requires the reference pair, so a carried revision cannot evade its binding. The entrance then supplies that settlement's own text. If it carries neither a reference nor a whole artifact, the refusal tells the holder to name the draft. This content check preserves correct settlements already posted while refusing a bare pointer or cold return without the quoted brief.

An unsupported route does not settle the phase: its latest claim refuses consumption within the term, but a later affirmed brief revises the last effective settlement and its readings rather than that refusal. A broken source on a supported route remains unusable for revision; an earlier settlement cannot replace it. A settled marker without a route is also invalid. In the current term its diagnostic tells a change in flight to re-post it once with the route the record supports; after a later affirmed brief supersedes that term, the diagnostic records the historical invalid claim and says no re-post is needed.

A supported settlement of the same text keeps the earliest eligible settlement's place in its term until a lawful affirmed brief, lawful artifact draft or qualifying cold verdict intervenes, because a restatement decides nothing new. A companion verdict in a later settlement creates that barrier too. Quotations, unauthorized or invalid claims, unqualified verdicts, readings and ordinary comments do not. A referenced `would` or `unobtainable` settlement has the applicable draft id and judged digest as its identity, or its accepted historical digest when unrecorded. A compatibility settlement without a reference that supplies its own whole artifact has that carried text as its identity, as do `discharge` and `cap`. Carried identity is the exact text from the recognized brief to the end of the settlement, excluding only transport before the artifact; whitespace and Unicode differences create another identity. Text after the quoted brief is carried text the builder receives, so a re-post adds notes above the artifact, never below it. Draft and carried-revision identities remain distinct.

An earlier supported settlement, an otherwise supported claim missing only its route or both draft reference and whole artifact, or a bound `would` refused only for a miscopied digest may establish that place. A bound `would` claim missing its reference pair is also a form omission when it carries whole text: it may anchor only the matching judged draft and remains refused for consumption. Form omissions may coexist, but an unrelated semantic failure cannot anchor: missing or wrong comments, malformed references, unsupported routes, edited drafts, unexplained historical mismatches, ambiguous judgment evidence and incomplete revisions do not. A claim missing its route may anchor the unambiguous applicable draft on a supported draft route, as well as any identifiable whole carried text; it has not selected text for consumption. A draft pointer without a reference can infer only the unambiguous draft and judgment applicable then; a bare revised-artifact pointer has no carried-text identity. The current settlement must itself be supported and carry or name usable text; an earlier claim supplies order only, never replacement text or an excuse for a broken source. Earlier refused claims stay invalid and reported. Repeated corrections never spend the anchor, and returning from carried text A to B to identical A uses A's earliest eligible place.

A holder reading counts strictly after that effective place, in record order, including identical reposts of every lawful result. Newest differing direction governs; reposts remain distinct delivery identities. The latest physical settlement still selects and validates the artifact. A newer draft reopens the phase; a later supported settlement closes it again.

## `cold-verdict`

- **Exact form:** `<!-- tradecraft:cold-verdict:v1 verdict=VERDICT staffing_status=STATUS [same_vendor_reason=REASON] -->`.
- **Attributes and lawful values:** `verdict=would|would-not|not-settleable`; `staffing_status=qualified|degraded`; `same_vendor_reason` is a nonempty slug present only when a degraded same-vendor result is accepted for this stage.
- **Producer, surface, moment:** the holder, in the issue comment carrying the cold seat's whole return, when that return arrives. The entrance selects the latest successful cold-seat bundle completed no later than the marker whose retained source return appears in that comment, considering both historical and modern records. It normalizes CRLF and CR to LF and strips trailing whitespace on each line for comparison. A selected record produced before `0.190.0` without a binding is reported as judged digest unrecorded. Unposted seats do not affect content pairing. Only when no return matches, a latest candidate produced before `0.190.0` retains time-based selection under historical compatibility; a modern latest candidate refuses and asks for the seat's whole return with the marker, naming that bundle. Equal completion times among matching bundles remain ambiguous.

```text
<!-- tradecraft:cold-verdict:v1 verdict=would staffing_status=qualified -->
```

## `holder-reading`

- **Exact form:** `<!-- tradecraft:holder-reading:v1 result=RESULT -->`.
- **Attributes and lawful values:** `result=no-amendment|amended`.
- **Producer, surface, moment:** the holder, in an issue comment carrying the whole-change reading after a qualifying cold verdict and before the first build, or, after that reading, in an issue comment carrying a later direction to the builder on the settled artifact with `result=amended`, because both record the holder's calls without a new verdict.

```text
<!-- tradecraft:holder-reading:v1 result=no-amendment -->
```

## `reach-reading`

- **Exact form:** `<!-- tradecraft:reach-reading:v1 head=FULL_COMMIT_SHA -->`.
- **Attributes:** only `head`, a full 40- or 64-digit hexadecimal commit identity.
- **Producer, surface, moment:** an authorized marker producer acting as holder, in an issue comment after the covered builder returns and before readiness, proof or release reporting. The marker claims the first content line and carries no `holder-reading` companion. It supplies reach evidence only, never whole-change reading, artifact settlement or amended-term delivery.
- **Payload:** exactly one fenced `json` object with integer `schema_version: 1`, required `turns`, and an optional `superset_settlements` list. Unknown fields and duplicate JSON keys are invalid.

```json
{
  "schema_version": 1,
  "turns": [
    {
      "dispatch_id": "the-reported-turn",
      "items": [
        {
          "path": "the/exact/flagged/path",
          "disposition": "row-or-criterion",
          "requirement": "Row 1, criterion C2",
          "basis": "Row 1, criterion C2 requires this move."
        }
      ]
    }
  ],
  "superset_settlements": []
}
```

Each item has only `path`, `disposition`, nonempty `basis` and the disposition's reference field: `requirement` for `row-or-criterion`, `generator` for `generator`, `restored_by` for `restored`, `ruling_source` for `owner-ruling`, or `added_by` for `own-turn`. String references are nonempty. `restored_by` contains exactly `dispatch_id` and full `head` of a later returned turn in the same selected lineage; the reading follows that restoration too. `added_by` is the dispatch ID of an earlier returned, measured builder turn in this PR's selected lineage that added lines to the exact path, using the same authored measurement. A later, foreign, unknown or unmeasurable turn, or one with no authored additions to that path, is rejected. The holder accounts for which lines were removed; the entrance proves positive path-level additions, not line-level provenance. Every ordinary turn entry covers all its flags. Unknown turns/paths, partial coverage, duplicate paths/turns, unknown dispositions and another disposition's fields are rejected.

Each superset settlement contains exactly `turn_reference`, nonempty `reason`, `basis: "pr-superset"`, positive integer `pull_request`, full `base`, `merge_base` and `head`, and `items`. Each reference names an entrance-reported unmeasurable entry. One reading may explicitly name all such entries, each with complete coverage of the same conservative PR superset. Bounds are computed through the holder checkout from the actual PR base, merge base and account head; `head` matches the marker. The account uses the PR's current head. A first-parent ancestor account survives only with no later unmeasurable return: the entrance checks uncertain returns against the reading's timestamp and requires the entire first-parent suffix after the account head to be covered by later measured turns. Later/undated uncertainty or unexplained intervening commits requires a current-head account. Missing objects never invent a return bound. Paths absent from the PR merge base never become flags or conservative candidates; the holder owes no item account for PR-created files. Every conservative candidate needs a lawful disposition, and an empty proved superset still needs explicit settlement. Superset coverage clears reach while retaining the original uncertainty, without requiring the failed original range or attribution to pass again. There is no `recovered_ranges` field; it is rejected as an unknown field.

Only the latest actual turn with a live launcher or recipient, unresolved spawn or unproved cleanup stays pending under recovery. Other incomplete or failed turns are measured from available recorded endpoints or named unmeasurable. Foreign-host liveness alone does not make reach pending. Registry state and recorded worktree paths do not decide PR reach.

The head binds the covered flags; initial adoption may cover historical turns at the proved current head. Ordinary coverage is checked against the merge-base path set at that reading head. Subsequent descendant progress retains a complete account even when catch-up removes some or all of that turn's current flags; it cannot make an originally partial or forged account valid. Newly flagged turns owe new accounts. A superseding rebase/amendment requires a new current-head account. Quoted, forged, unauthorized, wrong-surface, malformed or stale claims discharge nothing. The procedure, including reading the builder's returned recommendations even without flags and restoring missing superset evidence, is `reach.md`.

## `builder-session`

- **Exact form:** `<!-- tradecraft:builder-session:v1 session=SESSION [vendor=VENDOR] -->`.
- **Attributes and lawful values:** `session` is the UUID-shaped session identity printed by the implementer launcher; optional `vendor` is `codex` or `claude`. A matching dispatch bundle proves the vendor and must agree with a present attribute. Without a bundle, a vendor-qualified marker is the recovery route after the holder verifies the original runtime record; a UUID alone proves no vendor.
- **Producer, surface, moment:** the holder, in a comment on the issue, when the build return and launcher output arrive.

Reach correlates this claim across the issue's retained native records before scoping it to the selected implementation lineage. A proved sibling or other-lineage session is not this PR's missing turn. An authorized session with no retained attribution anywhere remains visible as its own uncertainty; a later return cannot account for an earlier marker.

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
