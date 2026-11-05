# D-951 — A padded known-defect ladder measures the finder's ceiling, and the budget stays at 600,000 bytes

**Purpose:** trace instalment 2 of #902. The replay gains a credential file and a padded known-defect ladder that measures the largest finder input at which the live reviewer still finishes and still finds a defect it caught at a normal size. That ladder left `MAX_FINDER_PROMPT_BYTES` at 600,000. **Audience:** a future session that re-measures the budget after a model or CLI change, changes the replay's ladder, or proposes raising the budget. **Success:** that reader can recover:
- why the key comes from a file and ignores the environment;
- how the padding is built and sized;
- how a run is judged and classified;
- what was measured, at what cost;
- why the budget did not move;

and can re-run the measurement without re-deriving its rules.

**The governing record.** The owner's [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/902#issuecomment-6606454720) governs, through rows 5 to 7. Its instalment-2 artifact was [settled on the cap route](https://github.com/Grimblaz-and-Friends/tradecraft/issues/902#issuecomment-6623606293), with one cold round of its own (#928). The holder's readings governed the build:
- [6623618186](https://github.com/Grimblaz-and-Friends/tradecraft/issues/902#issuecomment-6623618186) set the floor at CI;
- [6624134487](https://github.com/Grimblaz-and-Friends/tradecraft/issues/902#issuecomment-6624134487) accepted the first build and the builder's seven calls listed below;
- [6649671441](https://github.com/Grimblaz-and-Friends/tradecraft/issues/902#issuecomment-6649671441) applied the `stays` branch;
- [6649843583](https://github.com/Grimblaz-and-Friends/tradecraft/issues/902#issuecomment-6649843583) added the section on the case's second defect;
- [6650342631](https://github.com/Grimblaz-and-Friends/tradecraft/issues/902#issuecomment-6650342631) added the per-run token table and corrected the limits' description of the case.

The lane is ordinary / connected. The brief names a budget set too high as the panel risk, and no panel was bought.

**The key comes from a file, and the file ignores the environment.** `run --api-key-file PATH` and `ladder --api-key-file PATH` read one key from a file the owner saved outside every repository, so no key is pasted into a session or printed. The 2026-10-12 attempt failed on a pasted token broken by line wrapping.
- **Where the key goes:** it builds `ReviewCredentials(key, None)`, so it reaches the child process only through its environment, as the live reviewer's key does.
- **Why the environment is ignored:** both credential variables are ignored, so a spent key ends the run as a billing refusal instead of switching quietly to the subscription token. A switch would let an exhausted credit look like a finished run.
- **Unusable files:** a file that is unreadable, not UTF-8 text, empty, or holds more than one token stops the run before any launch. The message names only the path, with exception chaining suppressed, because a decode error quotes the bytes it failed on.
- **The last line of defence:** every results file the replay writes, and everything it prints, is refused if it contains the key's text.

**The padding.**
- **Content:** a case is grown with new files named `padding_NNN.py`, in a `replay-padding` folder of the replay's copied snapshot, of up to 64 KiB each. They hold only a docstring, comments and literal constants, so there is no behaviour for the finder to report. Their words are drawn from a fixed vocabulary by `sha256(seed:file:counter)`, so the bytes don't depend on `random` or the Python version. The seed defaults to `tradecraft-902-ladder-v1`.
- **Where it goes in:** the padding enters the raw diff before `select_coverage`, and its files are written into the replay's copied snapshot. So it passes the same lockfile and generated-file selection a real pull request would, and it can be read there without counting as a leak. Half the files go before the case's own sections and half after, so the defect sits mid-prompt whatever its paths. Mid-prompt is the conservative position for recall.
- **Sizing:** each rung N is sized in the reviewer's own measure, the largest composed finder input. Whole files are added first, then the last file's line count is binary-searched until the size lies in [N − 1,000, N].
- **Refusals before any launch:**
  - a padding path the case already uses;
  - a padding path the base attributes would exclude;
  - a case larger than the rung;
  - padding combined with `--summarise-deleted-files` or `--preload-changed-files`, because the live reviewer does neither below the budget.
- **Rehearsal:** `ladder-plan` composes and measures every rung without a credential or a model, so the next re-measurement can be rehearsed for free.

**The match rule.** Before any paid run, the holder fixes a defect key: anchors of path, side and a line range around the original lab finding, plus one-sentence `root_cause` and `wrong_result` taken from that finding. A run finds the defect when one of its survivors meets two conditions:
- **(a)**, which the tool computes: the survivor falls inside an anchor;
- **(b)**, which the holder records in a matches file: the survivor names the same root cause and the same wrong result.

A survivor outside every anchor never matches. `ladder-summary` refuses to run while an anchored survivor has no record, and refuses a record for a survivor outside the anchors.

**Classification.** Each run is sorted in this order:

| Outcome | Class | Effect |
|---|---|---|
| Completed | `finished` | Then found or not found, under the match rule. |
| An error starting `Claude API key budget spent (` | `void-billing` | Never counted. The driver halts, and the holder re-runs after the credit renews. |
| "Prompt is too long", or a timeout | `not-finished` | Counted as a failure. |
| A rate limit, an authentication failure, or an out-of-bounds read | `void-infrastructure` | Re-run once automatically. |
| Anything else | `unrecognised` | The driver halts. The holder re-runs it once, after the owner confirms the Console shows credit. A second one at the rung marks it not passed. |

A second void of any kind at one rung halts the ladder. The billing class is checked first, so an exhausted credit can never read as a size failing. An unrecognised outcome can only hold the budget down, never raise it.

**The rule for the budget.**
- A rung passes only when both runs finish and both find the defect, so one pass and one miss is a failure.
- The case qualifies only if both runs at its natural size find the defect.
- The decision is the largest rung with no failed rung at or below it:
  - `moves-to:N` when that rung is above the current budget;
  - `stays` when it is not;
  - `lowest-failed` when the lowest rung fails, which goes to the owner.

**The runs are the live reviewer's.**
- **Before spending:** `ladder` refuses unless the CLI reports the version `connected-review-shared.yml` pins, the replay's model, effort, pass structure, passes and candidates equal `live_reviewer_settings()`, and the finder prompt's digest equals the shipped `finder.md`. It records this as `live_match`, with the harness digest.
- **At release:** `ladder-verify` recomputes the same values from whatever tree it runs in and names each difference. The holder runs it at the head the release report names.
- **Not checked:** the model the stream reports is not captured (the artifact's C4), because capturing it would change the live reviewer's posted usage.

**What was measured.** The case was #883 at its lab-reviewed head `b59802e`, base `b63cd76`, run from tradecraft `dcce863`.
- Its defect key was posted before any paid run. That defect: a clean merge whose result is not valid declared-version JSON is raised as a plain error instead of a version conflict, so catch-up fails and the builder never gets the merge.
- Each size ran twice on Claude CLI 2.1.280, `claude-opus-5-5`, finder effort `high`, single pass.
- No run was void or unrecognised.
- The [results comment](https://github.com/Grimblaz-and-Friends/tradecraft/issues/902#issuecomment-6649666401) holds every judgment, the matches file's digest, and every raw file's digest. The raw output stays outside the repository.

| Size | Measured bytes | Run 1 | Run 2 | Outcome | Cost at list |
|---|---:|---|---|---|---:|
| natural | 91,406 | found | found | qualified | $3.07 |
| 600,000 | 599,952 | found | found | passed | $5.65 |
| 800,000 | 799,984 | not found | not found | failed | $7.49 |
| 1,000,000 | 999,968 | found | not found | failed | $9.70 |
| 1,200,000 | 1,199,963 | not found | not found | failed | $9.89 |
| 1,800,000 | 1,799,970 | not found | not found | failed | $17.03 |
| 2,400,000 | 2,399,998 | Prompt is too long | Prompt is too long | failed | none reported |
| 3,000,000 | 2,999,964 | Prompt is too long | Prompt is too long | failed | none reported |
| Verra #557, as it really was | 701,521 | finished | — | cost only | $5.06 |
| Daemon #107, as it really was | 1,531,290 | finished | — | cost only | $8.37 |

Each run's `finder_usage.coverage` tokens, as `ladder-summary` printed them, with every cache write at the 5-minute duration ([correction](https://github.com/Grimblaz-and-Friends/tradecraft/issues/902#issuecomment-6650336484) to the results comment):

| Size | Bytes | Run | Class | Found | Input | Cache write | Cache read | Output | Cost (USD) |
|---|---:|---|---|---|---:|---:|---:|---:|---:|
| natural | 91406 | natural-r1-a1 | finished | True | 62 | 125302 | 2702266 | 32017 | 1.8076 |
| natural | 91406 | natural-r2-a1 | finished | True | 34 | 111074 | 1367511 | 21614 | 1.2613 |
| 600000 | 599952 | 600000-r1-a1 | finished | True | 24 | 315128 | 3319806 | 13090 | 2.5015 |
| 600000 | 599952 | 600000-r2-a1 | finished | True | 38 | 331669 | 5580364 | 18503 | 3.1446 |
| 800000 | 799984 | 800000-r1-a1 | finished | False | 36 | 430334 | 6938407 | 20634 | 3.9522 |
| 800000 | 799984 | 800000-r2-a1 | finished | False | 34 | 405043 | 6320038 | 12199 | 3.5333 |
| 1000000 | 999968 | 1000000-r1-a1 | finished | True | 44 | 528885 | 10497683 | 30760 | 5.3593 |
| 1000000 | 999968 | 1000000-r2-a1 | finished | False | 32 | 505683 | 7343712 | 17360 | 4.3445 |
| 1200000 | 1199963 | 1200000-r1-a1 | finished | False | 28 | 608504 | 7588658 | 23644 | 5.0332 |
| 1200000 | 1199963 | 1200000-r2-a1 | finished | False | 28 | 600200 | 7565473 | 17316 | 4.8605 |
| 1800000 | 1799970 | 1800000-r1-a1 | finished | False | 54 | 897779 | 22677771 | 21996 | 9.4646 |
| 1800000 | 1799970 | 1800000-r2-a1 | finished | False | 34 | 882425 | 13833235 | 19176 | 7.5624 |
| 2400000 | 2399998 | 2400000-r1-a1 | not-finished | False | - | - | - | - | - |
| 2400000 | 2399998 | 2400000-r2-a1 | not-finished | False | - | - | - | - | - |
| 3000000 | 2999964 | 3000000-r1-a1 | not-finished | False | - | - | - | - | - |
| 3000000 | 2999964 | 3000000-r2-a1 | not-finished | False | - | - | - | - | - |
| #557 | 701521 | as merged | finished | - | 70 | 379133 | 11853413 | 39566 | 5.0579 |
| #107 | 1531290 | as merged | finished | - | 56 | 753386 | 19747828 | 32550 | 8.3677 |

- **Total: $66.25 at list.** That splits into $35.64 for the planned ladder, $17.19 for the refinement and $13.43 for the two cost replays.
- **Pricing:** every run is priced on the `claude-opus-5-5` card in `lib/rates.json`, with cache writes at the 5-minute rate the usage reported. A run ending "Prompt is too long" reported no usage, so it carries no cost.
- **Padding density** (cache-creation tokens per byte): 0.539 at 600,000, falling to 0.495 at 1,800,000. #557 sat at 0.540 and #107 at 0.492, so the padding loads the model about as a real large pull request does.
- **The cost replays' sizes** sit 17 bytes above their recorded skip sizes. The prompt embeds the temporary snapshot path, whose length differs between runs.

**The decision: `stays`.** 600,000 passed and 800,000, the first size above it, failed, so `MAX_FINDER_PROMPT_BYTES` stays at 600,000. That is not `lowest-failed`, so no owner ruling was owed. Nothing in `lib/` changed, and no version bump was owed.

**Two ceilings on this case.**
- **Recall:** the reviewer still finds the known defect at 600 KB, and does not reliably find it from 800 KB. At 1,000,000 one run found it and one missed. From 800 KB up, misses usually reported a different issue in the same code, in place of the known defect.
- **Context:** the prompt exceeds the model's 1M-token context between 1.8 and 2.4 MB. At 2.4 MB it was about 1,116,899 tokens.

So a finished review above 600 KB can miss what the same reviewer catches at a normal size, and the gate cannot tell. That is the brief's panel risk, which the measurement prevents here.

**The evidence's limits.**
- It is one case, scored on one known defect, and that case held a second real defect (see "A second defect in the case, and the owner's ruling" below).
- Each size ran twice, which cannot separate a real drop from run-to-run variation. The rule treats one pass and one miss as a failure for that reason.
- Condition (b) is a holder judgment, made against two sentences fixed before the runs.
- The padding is unrelated content, which may load the finder differently from a large pull request whose content is related. The density figures above suggest it does not differ much.

A re-measurement after a model or CLI change should try more than one case before the budget moves up.

**A second defect in the case, and the owner's ruling.**
- **The second defect.** #883 at `b59802e` held a second real P1 defect in the same function, now #953. The composed merge obligation drops a field-only version conflict from the builder's list and discards the classifier's merged bytes, so a builder can revert the base's change to another member. The Steward filed it after a two-arm probe confirmed it was still present at `5dad8cb`. The original lab review of #883 did not report it.
- **The counts.** From 800 KB to 1.8 MB, five of the eight runs reported #953: `800000-r2`, `1000000-r1`, `1200000-r1`, `1200000-r2` and `1800000-r1`. The known defect was found in 4 of 4 runs at 600 KB and below, and in 1 of 8 above. So the drop tracks size, not a random choice between two equal defects.
- **A looser rule gives the same decision.** Even counting any real defect as found, `800000-r1` returned no findings at all, so 800,000 still fails, and row 7 stops at the first failure.
- **The owner's challenge.** The owner asked whether the second defect confounded the test, and whether the reviewer works up to 2 MB. 2 MB was never run: 1.8 MB finished, and 2.4 MB exceeded the context at about 1,116,899 tokens.
- **His ruling.** After that answer, he ruled "Land 600,000" ([record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/902#issuecomment-6649839222)).
- **For whoever measures again:**
  - before any run, screen each case for other real defects in the anchored code, or score a set of known defects fixed in advance;
  - use more than one case and more than two runs per size;
  - expect the hard context limit between 1.8 and 2.4 MB.

**What this supersedes.** [D-841](D-841-2026-10-03-connected-review-input.md) set 600,000 by rounding down the larger input that one past review had completed. That single-run basis is superseded: the figure now rests on this measurement, which found it to be the largest size at which this case's defect is still found in both runs. The value is unchanged. Everything else in D-841, and D-943's over-budget summary, stands.

**Departures.**
- **The refinement.** The settled artifact's C2 fixed the sizes at 0.6 MB steps. Once those had run and given `stays` with a gap between 0.6 and 1.2 MB, the owner answered "Refine" ([record](https://github.com/Grimblaz-and-Friends/tradecraft/issues/902#issuecomment-6649397934)), adding 800,000 and 1,000,000.
  - They were added after the planned results were seen, and ran last rather than in ascending order.
  - They ran in a second output folder seeded with copies of the 12 finished runs, which the driver never re-runs, so one summary covers every size.
  - Row 7's rule applied to them unchanged, and no affirmed row moved.
- **The builder's calls,** accepted by the holder as inside the rows:
  - `ladder` pauses with `awaiting-matches` after the qualifying runs until condition (b) is recorded;
  - `ladder` takes `--revision` (default this tree's HEAD), and `ladder-summary` takes `--reference LABEL=RESULTS` for the cost replays;
  - void and unrecognised counts are per rung;
  - padding refuses preload as well as the summary;
  - the collision check refuses the whole `replay-padding` folder;
  - `stays` is decided by the current budget;
  - the padding record and the ladder record each gain a field (measured bytes, and the plan).

**Demonstrators.** Implementation demonstrators are pinned to `dcce8638c18d31d907b34af272f9c8df4c37f554`, the revision the ladder ran from. In `tools/connected_review_replay.py`, they are:
- `read_api_key_file`, `refuse_secret`, `padding_lines`, `pad_case` and `ladder_plan`;
- `validate_defect_key`, `run_found`, `classify` and `decide`;
- `live_match`, `run_ladder`, `ladder_verify` and `ladder_summary`.

They are tested by the #902 instalment-2 block in `tools/tests/test_connected_review_replay.py` at that revision. The holder's procedure is in `tools/connected-review-live-checks.md`, under "Size ladder".
