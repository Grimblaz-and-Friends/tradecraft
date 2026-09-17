# D-644 — The filing cell is swept under the prose principle

**Purpose:** record what the `filing` sweep keeps, moves and leaves unwritten, including the ownership calls and control results that explain its shape. **Audience:** a session revising filing, search, tie or pool behavior. **Success:** every removed passage has its class and destination, the template and contradiction decisions can be recovered, and no frozen figure depends on a moving checkout.

**Landed by** [PR #644](https://github.com/Grimblaz-and-Friends/tradecraft/pull/644). Closes [#633](https://github.com/Grimblaz-and-Friends/tradecraft/issues/633), governed by [#571's affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/571#issuecomment-5627498365) and its [2026-09-14 amendment](https://github.com/Grimblaz-and-Friends/tradecraft/issues/571#issuecomment-5674412155). Evidence is pinned to base `c679fd520ee690e524c12658639cb1a3813af587` and built text `8b2f6ff52e4cb30945ac7ff9152a8e70dff4a793` unless another source is named.

## What was decided

The `filing` cell is swept under [D-575]'s principle: governing prose keeps concepts with their reasons and the choices a model cannot safely resolve alone; output fields move to a template; command facts sit with the commands; existing script messages say rules at the mistake; incidents and migrations live in entries; copies leave the cell that does not own them. The description, the script, its policy and its tests do not change. The body ceiling follows the smaller body, and the plugin advances to `0.132.0`.

The amendment to #571 is the authority for running this sweep. [D-575]:9 records the carve-out exactly as the original brief stated it and informs this change rather than binding it. The carve-out was spent when #572 landed as [PR #590](https://github.com/Grimblaz-and-Friends/tradecraft/pull/590), and the owner's amendment — *"amend the brief; the carve-out is spent now that 572 landed"* — lifted it. The artifact did not lift the carve-out by its own reading.

### One template, including its first field

`skills/filing/references/pitch-template.md` is the one template for both a new issue body and a comment extending an open pitch. The tie line is the issue body's first field, not a second template. The prose keeps the standard each field meets; the template carries the fields, placeholders and copy-time hints once, where a session copies them.

The three fenced command blocks stay in place. The two search commands and the cause-link mutation gain their runtime facts as adjacent `#` comments. The ten pool invocations remain verbatim because `skills/filing/tests/test_pool.py:928-951` reads `skills/filing/references/the-pool.md`, parses lines matching `^python \.\./scripts/pool\.py (.+)$`, and requires at least nine.

### Five contradictions resolved inside the cell

1. **The `cause` label had two creation paths and two descriptions.** `naming-a-tie.md` instructed `gh label create cause --description "Observed cause of the issues linked under it"`; the shipped policy gives the fuller meaning and `pool.py labels` creates it. The prose command leaves. The script's path and description survive.
2. **The fade was stated in both the body and `the-pool.md`.** The body keeps the owner's quiet-pitch concept; the depth file keeps the quiet-window concept; the script and policy say the operating cases.
3. **Closed work not reopening was stated in both `the-search.md` and `the-pool.md`.** The search file owns it. The pool copy leaves unwritten.
4. **The compliance concept was split between `naming-a-tie.md` and `what-a-filing-carries.md`.** The body-standard file now states it once, with [D-128].
5. **Cause instructions claimed to serve only existing numbered groups while the search allowed a distinct new pitch and tie.** The over-narrow migration sentence leaves for [D-590]; the instructions serve lawful new links too.

The findings' §1.2 contradiction is separate from those five. On this cell's side, the governing-prose filing bar admits an incident or a run, while the charter admits an incident or the owner's approval. The clause claiming the filing bar was the charter's bar leaves; each surface states its own grounds. The pointer defining what is not an incident remains. The charter side belongs to #629 because that change's artifact explicitly declined to settle it.

## Every passage changed or removed

Line numbers below are the artifact's base lines at `6376ccb`; the later base did not change `skills/filing`. “Sharpen” means the concept remains and the named case, duplication or armour leaves unwritten. A mixed class names every destination used by the row. Every `pool.py` citation is to `skills/filing/scripts/pool.py`.

| base site | passage that moves or leaves | class | destination or surviving reason |
| --- | --- | --- | --- |
| `SKILL.md`, after 15 | new depth-index entry | to template | indexes `skills/filing/references/pitch-template.md`; this is an addition, not a deletion |
| `SKILL.md:19` | “The search and the filing's evidence bar live in this cell's depth.” | sharpen | cut unwritten; the depth index already says where depth lives |
| `SKILL.md:21` | “A session's own filing enters that pool.” | sharpen | cut unwritten; the surrounding membership and framing concepts decide it |
| `SKILL.md:23` | “retaining its text and the reason it closed” | sharpen + to script message | `pool.py:890-894`, whose close comment supplies the reason while GitHub retains the body |
| `SKILL.md:25` | why a naming-file-relative path works in source and installed plugin | sharpen + to another cell | the `substrate` cell's `SKILL.md:22`; the path rule stays here and no pointer is added |
| `the-search.md:5` | looser command to search pool, board and closed issues | cut | unwritten; line 7 states every state and the whole set precisely |
| `the-search.md:9` | summary of how the two surfaces differ | sharpen | replaced by a lead to the comments beside the commands |
| `the-search.md:11-14` | the two search invocations as copyable material | to template | kept in place as a fenced command template with adjacent runtime comments |
| `the-search.md:16` | `--state all`, default-limit facts, and closed-history narration | to template + cut | command facts move beside each command; the third sentence is unwritten because lines 7 and 28 carry the concepts |
| `the-search.md:18` | phrase-versus-AND mechanics, term boundary and #20 exhibit | sharpen + to template + to entry | mechanics move beside commands; boundary joins line 20; exhibit is recorded below |
| `the-search.md:20` | `check_version_bump` near-miss exhibit | sharpen + to entry | the one-term concept and `post-fix terminus` example stay; the near miss is recorded below |
| `the-search.md:22` | “the issue that decided the filing that found this” | sharpen | cut unwritten as narration beside the retained example |
| `the-search.md:30` | existing-numbered-issue migration sentence | sharpen + to entry | [D-590]:13 already records preservation of existing cause links |
| `the-search.md:32` | extending-comment fields and the rating-label case | sharpen + to template | fields move to the template; the impossible comment-label case is unwritten |
| `naming-a-tie.md:3` | location of the tie block's form | sharpen | adds the template pointer while this file remains the meaning of the fields |
| `naming-a-tie.md:5` | existing-groups-only migration and duplicate extension rule | to entry | [D-590] carries the migration; the search file owns extension; nothing survives here |
| `naming-a-tie.md:19` | reciprocal-link and one-parent explanations | sharpen + to entry | [D-429]:23,41 already carry them; the labelled-parent concept stays |
| `naming-a-tie.md:21` | `gh` runtime facts and label-existence rule | sharpen + to template + to script message | runtime facts move beside the mutation; `pool.py:729-738` and `:762-790` own label specification and creation |
| `naming-a-tie.md:24` | direct `gh label create cause` command | to script message | `pool.py:729-738` and `:762-790`; the script is the sole creation path |
| `naming-a-tie.md:26` | copied mutation and its operating facts | to template | mutation remains in place; node-id, version and re-parenting facts become adjacent comments |
| `naming-a-tie.md:29` | re-parenting instruction | to template | adjacent comment on the mutation |
| `naming-a-tie.md:33` | symptom-with-only-cause output case | to template | tie-block hint `its cause is linked (#<N>)` |
| `naming-a-tie.md:35` | distinction from the edit that `blocks` avoids | sharpen | cut unwritten as armour; the create-pass rule and reason stay |
| `naming-a-tie.md:37` | closed-target consequences for the five relationships | sharpen | cut unwritten as cases reached by the one-vocabulary and closed-history concepts |
| `naming-a-tie.md:39` | tie syntax and variants | sharpen + to template | field forms move; placement, its reason and one example stay |
| `naming-a-tie.md:41` | no-tie form, coined-phrase case and duplicate compliance rule | sharpen + to template | form moves; coined-phrase case is unwritten; compliance consolidates in `what-a-filing-carries.md` with [D-128] |
| `what-a-filing-carries.md:3` | location of the output fields | sharpen | adds the template pointer while this file remains their standard |
| `what-a-filing-carries.md:5` | complete creation-field list | to template | issue-body block in `pitch-template.md` |
| `what-a-filing-carries.md:7` | argued-form mechanics and duplicate extension pointer | sharpen + to another cell | mechanics belong to `engagement`; the index and template make the last pointer redundant |
| `what-a-filing-carries.md:11` | charter-equivalence clause and finding-fate sentence | sharpen + to another cell | false equivalence is unwritten; finding fate belongs to `skills/adversarial-review/references/arbitration.md:21`, with no circular pointer |
| `what-a-filing-carries.md:13` | ratings copy, door enumeration and restatement of the general bar | sharpen + to entry | cases leave; [D-544] carries the mechanism history; the evidence-keyed carve-out and reason stay |
| `what-a-filing-carries.md:15` | four-item fallback list and final restatement | sharpen | cut unwritten; demonstration, fallback concept and reasons stay |
| `what-a-filing-carries.md:19` | provenance heading, origins, placement and no-search form | sharpen + to template + to entry | fields move to the template; concepts stay with [D-128] and [D-496] |
| `the-pool.md:5` | shortlist procedure, ratings cases and ordering mechanics | sharpen + to script message | `pool.py:656-657`, `:660-709`, `:616-620`, `:528-540` and `:2-7`; read/buys-nothing, cut explanation and label-write activity stay |
| `the-pool.md:7` | global-flag order and policy-print rule | sharpen + to script message | `pool.py:919-922` and `:962-967`; path anchor and local-policy-resolution concept stay |
| `the-pool.md:22` | fade operating cases | sharpen + to script message | `pool.py:934-935`, `:873-874`, `:867`, `:883`, `:888`, `:622-623`, `:868`, plus the policy's `_fade`; quiet-pitch and quiet-window concepts stay |
| `the-pool.md:24` | close/reopen/search recurrence copy | sharpen | cut unwritten; `the-search.md:28` owns it |
| `the-pool.md:26` | policy migration and retired-command cases | sharpen + to script message + to entry | policy `_note`; `pool.py:227-228`, `:712-723`; argparse as pinned by `skills/filing/tests/test_fade.py:143`; [D-590]:19 carries the migration |

No passage moves to a new guard. No script, policy or test changes: every cited message already existed.

## Exhibits and observed controls

The phrase-versus-AND comments are backed by the artifact's probe: `gh search issues "manifest exemption wider"` returned nothing while `gh issue list --search "manifest exemption wider"` returned #20. The near-miss exhibit is that searching `check_version_bump` returned none of the issues whose titles begin with `check_version_bump.py`. These are evidence in this entry, not more prose examples.

The base control `20260917T012453Z-633-criterion-7-base` met criterion 7's control: a fresh seat at `c679fd5` returned both `python skills/filing/scripts/pool.py labels` and `gh label create cause --description "Observed cause of the issues linked under it"`. The contradiction existed in use, not only on inspection, and the script path is the one retained.

The base control `20260917T012450Z-633-criterion-6-base` falsified criterion 6 by the criterion's own terms. A fresh seat at `c679fd5` produced an issue body already carrying all four named features in the same positions: a first tie or no-tie line, keyed provenance, evidence with the probe and output, and value with a case against. The criterion did not discriminate. The template is justified by the other half of the artifact's item 3: it states the fields once where a session copies them instead of four times across prose.

## Eight ownership calls

1. The naming-file-relative calling contract remains here as this cell's application; its reason belongs to `substrate`, with no pointer added.
2. One `pitch-template.md` carries both issue body and extending comment; the tie line is its first field; all three command blocks stay in place, including the pool block pinned by `skills/filing/tests/test_pool.py:928-951`.
3. The `cause` label has one creation path, the shipped script's `labels` command; the direct `gh label create` path leaves.
4. The finding-fate sentence belongs to `adversarial-review` and leaves without a pointer because that cell already points to `filing` and the reverse edge would form a circle.
5. The compliance concept is one sentence in the body-standard file, cited to [D-128].
6. The closed provenance vocabulary ships in the template because its only code consumer, `tools/trial_intake.py:78`, is repo-only and is not delivered to adopters.
7. The frontmatter description remains verbatim, so no roster regeneration is needed.
8. The two `gh` surface facts remain as comments beside the commands: `--state all` is rejected by `gh search issues`, and each surface defaults `--limit` to 30.

Three cross-cell copies remain for the sweeps that own them. `docs/cells/board/SKILL.md:35` and `docs/cells/board/references/refreshing-it.md:17` retain “strongest few” for the board sweep tracked by #614. `skills/engagement/references/the-ask.md:31` retains its `--limit` prose for the engagement sweep tracked by #577. `skills/adversarial-review/references/arbitration.md:21` retains the filing-standard copy for the adversarial-review sweep. This change does not cut another cell's copy.

## Citations and findings moved under #590

This sweep adds [D-544] to the measurement-only carve-out, [D-128] to the compliance concept, [D-496] to the keyed provenance concept, and [D-590] to the pool policy and migration boundary.

The findings written against pre-#590 lines are resolved against the current cell rather than silently inherited. The old `the-search.md:26-32` five-outcome passage, including “Record it under its cause,” is gone; those lines now carry extension, closed match, ties at birth and the extending comment. The governing-prose bar formerly cited at `what-a-filing-carries.md:15` is now line 11, while current line 15 is demonstration; provenance formerly cited at line 23 is now line 19. In `naming-a-tie.md`, the old citations at lines 19, 27, 33 and 37 now correspond to current lines 21, 29, 35 and 39. The old `SKILL.md:27` mandatory-two-ratings premise is gone; ratings are advisory and applied after creation. `the-search.md:7`, `:16`, `:20` and `what-a-filing-carries.md:5` remain the sites the findings named. Whether a spike report is a pitch belongs to the `spikes` cell and is not decided here.

## Figures, with both trees pinned

These commands derive the figures; their outputs are deliberately not frozen here.

```bash
git worktree add --detach ../tc-633-base c679fd520ee690e524c12658639cb1a3813af587
git worktree add --detach ../tc-633-built 8b2f6ff52e4cb30945ac7ff9152a8e70dff4a793
(cd ../tc-633-base && find skills -name "*.md" -exec cat {} + | wc -c)
(cd ../tc-633-built && find skills -name "*.md" -exec cat {} + | wc -c)
(cd ../tc-633-base && python -c "import sys; sys.path.insert(0,'tools'); import lint; from pathlib import Path; print(len(lint._frontmatterless(Path('skills/filing/SKILL.md').read_text(encoding='utf-8'))))")
(cd ../tc-633-built && python -c "import sys; sys.path.insert(0,'tools'); import lint; from pathlib import Path; print(len(lint._frontmatterless(Path('skills/filing/SKILL.md').read_text(encoding='utf-8'))))")
git diff --stat c679fd520ee690e524c12658639cb1a3813af587 8b2f6ff52e4cb30945ac7ff9152a8e70dff4a793
git diff --quiet c679fd520ee690e524c12658639cb1a3813af587 8b2f6ff52e4cb30945ac7ff9152a8e70dff4a793 -- skills/filing/scripts skills/filing/tests scripts/pool-policy.json
```

[D-128]: D-128-2026-08-23-filing-cell.md
[D-429]: D-429-2026-09-05-the-cause-relationship-becomes-a-link.md
[D-496]: D-496-2026-09-07-a-handoff-that-reaches-nobody.md
[D-544]: D-544-2026-09-09-the-ceiling-reading-goes-to-the-refresh-note.md
[D-575]: D-575-2026-09-11-a-rule-is-a-guard-a-script-an-exhibit-or-unwritten.md
[D-590]: D-590-2026-09-12-work-is-bought.md
