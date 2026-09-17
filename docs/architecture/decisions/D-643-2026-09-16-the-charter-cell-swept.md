# D-643 — The charter cell swept: the routing map stays and six clauses leave

**Landed by** [PR #643](https://github.com/Grimblaz-and-Friends/tradecraft/pull/643). Closes [#629](https://github.com/Grimblaz-and-Friends/tradecraft/issues/629). Governed by the implementation brief affirmed on [#571](https://github.com/Grimblaz-and-Friends/tradecraft/issues/571#issuecomment-5627498365) on 2026-09-10, which commissions each cell's sweep as its own reviewed change without a fresh affirmation; [D-575] landed the charter principle. Evidence pinned at `e9a5ca389367f828e369fd5dc260a92260b2b74c`, over base `c679fd520ee690e524c12658639cb1a3813af587`, unless another pin is stated.

## What was decided

The `charter` cell keeps every concept and every owner-stated sentence it carried. Of its 22 passages, 17 stay and five are sharpened; no passage leaves whole. Six sentences or clauses leave from inside those five sharpened passages: two go to the cells that own them, three are cut as unwritten or restated, and one old framing is rewritten to the `authoring` cell's existing framing. The description is unchanged.

This cell is different from every other sweep because every adopting session reads it before any cell fires, while an adopter receives neither this repository's `tools/` nor its repo-only cells. A rule can therefore leave this page for a guard or script message only when that mechanism ships to the same reader. Nothing in this sweep does. The available moves were to the shipped cell that already owns the rule, to an entry, or to unwritten judgment; no new guard, script, template, or citation was added.

## Every clause that left, with the artifact's class

The settled artifact classes each containing passage as **sharpen**. The final column records the sentence- or clause-level move the same row gives it. For deleted text, the locator names the surviving line of its hunk at the evidence pin; the pinned diff in *Figures* supplies the removed wording. That diff is the complete source check, and no deletion falls outside this table.

| passage | artifact row class | clause-level move |
| --- | --- | --- |
| `skills/charter/SKILL.md:27` — *"one that altered how a later session must work or what someone using the result can do"* | sharpen | **To another cell.** The trigger belongs to the `experience-session` cell, whose description states it at `skills/experience-session/SKILL.md:3` and whose depth states the operative test at `skills/experience-session/references/when-one-fires.md:5`. The charter keeps the merge-time anchor and both outcomes: use the result, or write the declining line. |
| `skills/charter/SKILL.md:37` — *"this section states where content goes, not how to decide a hard case"* | sharpen | **Cut, unwritten.** It described the section's scope against a misreading; the pointer beside it already sends the hard case to the `authoring` cell. |
| `skills/charter/SKILL.md:38` — *"A binding always-on rule → the adopting repository's own doctrine"* | sharpen | **Rewritten to the existing framing.** `skills/authoring/references/routing.md:10` says the always-on home is for what must hold before any context loads and names both the shipped charter and an adopting repository's root doctrine. |
| `skills/charter/SKILL.md:38` — *"This charter is the practice's own always-on surface"* | sharpen | **Cut, restated.** The rewritten arrow names *this charter* as one of the two always-on surfaces. |
| `skills/charter/SKILL.md:42` — *"What belongs here is what must hold before any context loads"* | sharpen | **Cut, restated.** The rewritten arrow at `skills/charter/SKILL.md:38` now states that framing once. |
| `skills/charter/SKILL.md:50` — *"When to load each is its own description's to say, and every description loads in every session beside its name — so the condition is stated where it is already read, and not a second time here"* | sharpen | **To another cell.** `skills/authoring/references/cell-structure.md:5` owns the rule that a roster names cells and does not copy their load conditions; this repository's `check_charter_roster` says the same thing at the editing mistake. The charter keeps the roster and its reason. |

## Ownership calls

**1. The routing map stays in the charter.** The four arrows at `skills/charter/SKILL.md:37-40` are the compressed map an adopter needs before loading a cell; `skills/authoring/references/routing.md:9-12` carries the fuller method and reasons. The refused alternative was to cut all four arrows and leave only the pointer to the `authoring` cell. [D-388]'s owner requirement and [D-376]'s warning against compressed copies argued for that cut; against it, and deciding, three arrows name homes that are not cells an adopter can load, and the drift [D-575] identified is repaired by making the two framings one. If a later reader takes the refused alternative, `docs/cells/siting/SKILL.md:12` must change with it, because its statement that the charter carries the routing map would no longer be true.

**2. The roster's load-condition rule is the `authoring` cell's.** `skills/authoring/references/cell-structure.md:5` already owns it, and `check_charter_roster` is this repository's editing-time material. The charter keeps the roster and its completeness sentence; it drops the second copy of how roster entries are written.

**3. The experience-session trigger is that cell's.** Its always-loaded description at `skills/experience-session/SKILL.md:3` owns when it fires, and `skills/experience-session/references/when-one-fires.md:5` owns the full test. The charter keeps what only it supplied: the before-merge anchor and the two outcomes.

**4. Precedence between the two always-on surfaces stays in the charter.** No cell can own a rule that must settle a conflict before any cell loads. *Doctrine* here means the adopting repository's **root doctrine**, the word introduced at `skills/authoring/references/routing.md:10`; in this repository that file is `AGENTS.md`. The separate wording *"made in its doctrine"* at `skills/substrate/SKILL.md:17` belongs to the substrate sweep, not this one.

**5. The out-of-review decline stays at `skills/charter/SKILL.md:33`.** It fires when no review cell has loaded. The copy quoted by the findings existed at `skills/adversarial-review/references/arbitration.md:15` at `bd71c4f`; it is absent now. Current `skills/adversarial-review/references/arbitration.md:19` is a different rule, requiring an independent ruling for a lapse outside review. The role-separation rule at `skills/adversarial-review/references/arbitration.md:27` at `bd71c4f` also belonged to #572's rewrite. If that programme gives the review cell both the general decline rule and a route to readers outside a review, the charter line becomes the copy to remove; this change does not pretend that route already exists.

**6. *Ask the cheap question* is not the fabricated gate.** `skills/charter/SKILL.md:20` rejects a question where no fork exists; `skills/charter/SKILL.md:26` addresses doubt over whether a change decides something and therefore owes the owner's affirmation gate. That doubt is a genuine fork the owner lives with, because their affirmation and the whole convergence path turn on it. The current test is at `skills/engagement/SKILL.md:42`, and its tell — nothing turns on the answer — is at `skills/engagement/SKILL.md:44`. The apparent conflict is resolved by reading those tests, not by adding a reconciling clause.

**7. The charter emits no template and takes no decision citation.** It is read rather than copied from, and an adopter cannot resolve this repository's decision log. The decisions cited in this entry record this repository's reasoning; none was added to the shipped charter.

## Copies left to their owning sweeps

These sites are not charter material to cut in this change. They are named so the next owning sweep does not re-find them as omissions:

- `docs/cells/landing/SKILL.md:17` carries the repository's flow through the experience session and its post-fix repetition.
- `skills/adversarial-review/references/after-the-fix.md:21` carries the fixed-tree experience session.
- `skills/adversarial-review/references/the-record.md:19` records whether a session note was carried, and `skills/adversarial-review/references/the-record.md:21` records the experience session a fix batch bought or the declining line.
- `docs/cells/records/references/what-a-review-records.md:9` excludes experience sessions from the review's dispatch-cost population.
- `skills/adversarial-review/references/arbitration.md:19` carries the current lapse-ruling sentence; the role-separation sentence formerly at `skills/adversarial-review/references/arbitration.md:27` is pinned above to `bd71c4f` for #572.
- `skills/substrate/SKILL.md:17` carries that cell's unresolved use of *doctrine*.

## The Authority sentence stayed verbatim

The cold seat found one omission in the artifact's provenance search. The search below finds `docs/architecture/decisions/D-74-2026-08-19-constitutional-reset.md:13` in addition to the entries the artifact listed. D-74 is the doctrine ancestor of the Authority sentence — it says the owner's decisions outrank doctrine and a session argues rather than refuses — but it quotes no owner words, so it does not disturb the artifact's verbatim keep.

```
Get-ChildItem docs/architecture/decisions/D-*.md | Select-String -Pattern 'outrank' -CaseSensitive:$false
```

## Admissions, settling, and related work

**No bank row was owed.** The conditional in the artifact resolved on the built tree: `python tools/lint.py` at `e9a5ca389367f828e369fd5dc260a92260b2b74c` prints no `admission-stale` finding, so the existing admission stands and `docs/admissions.jsonl` is unchanged. A bank row on the artifact's older probe would have recorded a state this built tree never reached.

**No settling row is appended.** The implementation brief is #571's, affirmed once for all ten sweeps, and its existing row is found with `Select-String -SimpleMatch '"issue": 571' docs/settling.jsonl`. A second row would record the same affirmation twice. The cold check belongs to this pull request and this entry instead.

Read from GitHub on 2026-09-16 with `gh api repos/Grimblaz-and-Friends/tradecraft/issues/<N> --jq '{number,state,title,body}'`: [#390](https://github.com/Grimblaz-and-Friends/tradecraft/issues/390) is closed; it concerned the `authoring` cell's overloaded cell-structure bullet. [#557](https://github.com/Grimblaz-and-Friends/tradecraft/issues/557) is open and concerns the `adversarial-review` lane gate. [#89](https://github.com/Grimblaz-and-Friends/tradecraft/issues/89) is open and concerns the runnable command and agent surface. None is this cell's work.

## Figures

Commands only, with both endpoints pinned. The two worktrees make the tree read by commands without a revision flag explicit:

```
git worktree add --detach <base-path> c679fd520ee690e524c12658639cb1a3813af587
git worktree add --detach <tip-path> e9a5ca389367f828e369fd5dc260a92260b2b74c
```

- **The charter diff:** `git diff --unified=0 c679fd520ee690e524c12658639cb1a3813af587 e9a5ca389367f828e369fd5dc260a92260b2b74c -- skills/charter/SKILL.md`; its stat is `git diff --stat c679fd520ee690e524c12658639cb1a3813af587 e9a5ca389367f828e369fd5dc260a92260b2b74c -- skills/charter/SKILL.md`.
- **The charter body and always-on rows:** `(cd <base-path> && python tools/lint.py)` and `(cd <tip-path> && python tools/lint.py)`.
- **Shipped prose:** `(cd <base-path> && find skills -name "*.md" -exec cat {} + | wc -c)` and `(cd <tip-path> && find skills -name "*.md" -exec cat {} + | wc -c)`.
- **The plugin version:** `git show c679fd520ee690e524c12658639cb1a3813af587:.claude-plugin/plugin.json` and `git show e9a5ca389367f828e369fd5dc260a92260b2b74c:.claude-plugin/plugin.json`.
- **The no-bank branch:** `(cd <tip-path> && python tools/lint.py)` and `git diff --exit-code c679fd520ee690e524c12658639cb1a3813af587 e9a5ca389367f828e369fd5dc260a92260b2b74c -- docs/admissions.jsonl`.

[D-575] [D-74] [D-388] [D-376] [D-524] [D-306] [D-156] [D-590] [D-602]
