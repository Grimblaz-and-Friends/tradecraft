# D-291: Repo-only cells, and one ceiling on the always-on rows in place of two on the files

## The condition

A rule only this repository needs had two lawful homes: `AGENTS.md`, always-on and budgeted, or a file under `docs/` plus a binding line in `AGENTS.md`, which still spends an always-on line. A shipped cell could not hold one — a shipped cell ships to every adopter, and `AGENTS.md` already ruled that repo-specific application stays in this repository's own doctrine. So repo-specific procedure was always-on **by construction** rather than by anyone choosing it, and the outflow's second move in `skills/authoring/references/routing.md` — *a rule that binds only inside one activity moves to that activity's cell* — had no destination for any of it.

That is the structural half of what [#260](https://github.com/Grimblaz-and-Friends/tradecraft/issues/260) filed. **The measurement is [D-261]'s, and it is stated here as that entry states it** rather than as the filing did: every commit that made a governing surface smaller grew this practice's governing prose overall in the same commit — and D-261 also records that an earlier draft claiming the surface rose across *every* commit was re-derived false by three stages of its own review, three commits having reduced the always-on total. The filing's own figures were carried forward into a draft of this entry un-windowed and contradicting D-261 on both halves; a review seat caught it. What survives, and is all this change needs, is that relocation was the only move the instrument had.

## The decision

**Three repo-only cells under `docs/cells/`** — `landing`, `records`, `siting` — carrying the flow, this repository's records and decision log, and where content goes here. `tools/roster.py` gains a second source directory and generates them onto both runtime surfaces. Their descriptions load; their bodies do not; an adopter never loads either, the plugin's roster being built from `skills/`.

**Three cells rather than one** was the owner's, put as a fork the affirmed brief did not reach and ruled on the issue. One cell named for the repository would spend less always-on description and re-create a discipline-shaped unit at the moment stage 2 exists to remove them.

**`AGENTS.md` keeps what must bind before any cell fires**: the charter import and the instruction carrying it to Codex, the ceremony moments, the one-way wall — a session can breach that in its first edit — and a routing line.

**The two per-file ceilings are replaced by a ceiling on each per-runtime row and on the adopter total.** A ceiling on `AGENTS.md` and another on the charter body could not see a move between them: it read as a saving in whichever file shrank while the surface a session loads had not moved. That is the failure D-184 diagnosed in its own predecessor, one level up.

**Not on `repo_total`.** It is the smallest row, so a budget on it leaves the larger runtime unbudgeted — `_always_on`'s own docstring records that nothing renders it alone. Probed: moving a block `AGENTS.md`→`CLAUDE.md` drops the Codex row and `repo_total` and leaves the Claude Code row flat, so under a `repo_total` budget the freed room admits an `AGENTS.md` addition that then grows both rows.

**The headroom is exactly one substantial rule, and the exactness is load-bearing.** The unit is what `AGENTS_BUDGET_CHARS` named and never sized; its one instantiation is the headroom that constant was set with at `81fb1d9`, derivable by measuring `git show 81fb1d9:AGENTS.md` against the ceiling `git show 81fb1d9:tools/lint.py` sets there. A wider margin admits the `AGENTS.md`→`CLAUDE.md` move the row budget exists to refuse; a narrower one refuses the rule admission the ceiling exists to allow. The form the raised constants used — *the next hundred above the body this change measured* — is documented in `tools/lint.py` as a ceiling above a measured body rather than headroom to grow into, and was rejected for that reason: inheriting it would have reproduced the blocking condition under a new name.

**The check reds rather than passing when the figure cannot be derived.** `always_on_note` swallows every exception and returns a string, which is right for a note and wrong for an enforced ceiling. The gate is this file's own presence, not the figure's: a fixture tree writes part of `tools/` without writing `tools/lint.py`, and removing `tools/figures.py` from this repository reaches the branch and reds, which is what [#134] records going wrong when a guard reads its own input's absence as clean.

**Criterion 10 holds under the reading "no ceiling among those #260 raised", not as literally written.** `POINTER_BUDGET_CHARS` survives on `CLAUDE.md`, which *is* a member of the Claude Code row — it bounds a pointer file's shape rather than its share of the surface, and it is what caps an `AGENTS.md`-to-`CLAUDE.md` relocation. Neither approval reached it. Stated here because a later session auditing the criterion will find it.

**Both owner approvals recorded on #260 are discharged.** The raised ceilings are replaced rather than restored, and the temporary-ceiling note in `tools/doctrine_callout.py` goes with them — the two budget pins in `tools/tests/test_lint.py` named that note as the third deletion site.

**The guards follow the material rather than staying with the file it left.** `DOCTRINE_PATHS` gains the repo-only cells, keyed by prefix so a future cell needs no edit: without it a PR rewriting the flow would have stopped reaching the owner at merge while the Release bullet went on describing the wider read — a narrower gate arriving with nothing saying so, and the one regression this change could have shipped invisibly. `check_cell_references`, `check_sideways_deps`, `check_cell_frontmatter`, `check_harness_tokens`, `check_doctrine_citations` and `check_doctrine_references` likewise.

**The cell-reference widening is fenced, and the fence is the wall's own direction.** A repo-only cell may name a shipped cell — that is how it applies a shipped standard without copying it, and no cycle can form through it. A shipped cell naming a repo-only one is a finding: a consumer installs `skills/` and never loads `docs/cells/`. The name form is the one shape `check_zone_wall` cannot see, since that guard matches paths, so a single widened known-set would have opened the wall in the one place nothing else watches. Repo-only naming repo-only stays unlawful: that is the mesh of mutual references the rule exists to prevent, and two cells in one repository build it as easily as two in a plugin.

## Two recorded placements this change reversed, and then restored

Both are rules a draft of this change moved off the always-on surface into a cell, and both had a recorded reason for being where they were. Neither reversal was argued anywhere; a review seat found both.

- **The values ranking.** [D-225] admitted it at the last-resort tier on the ground that *"a session deciding whether work is worth doing has, at that moment, loaded nothing"* — which is the same test this change states for what `AGENTS.md` keeps. It sat, briefly, in a cell whose description names no worth, value or ranking trigger, so nothing could route a session to it at the moment it applies. Restored, with D-225's reason carried onto the surface so the next reader does not have to re-derive it.
- **The CRLF fact.** [D-186] §5 states the placement as a ruling — it sits in `AGENTS.md` *"rather than in a cell"* because the moment it must be found is mid-task — and [D-225]'s own outflow pass then refused this exact move and recorded the refusal so a later audit would not re-derive it. This change made it anyway. Restored.

**Decisions inform rather than bind, so either move was lawful; what was not lawful was making them silently.** The charter's rule is that a prior decision is superseded by *reading* it, and neither was read. That is the failure this section exists to record.

## What this does not decide

Stage 2 converts the roster from discipline-shaped descriptions to moment-shaped entries and is what lowers the adopter total, which this change leaves flat by construction. Stage 3 runs the routing comparison the owner authorised and closes #260. [#255](https://github.com/Grimblaz-and-Friends/tradecraft/issues/255) stays open and contingent on stage 2. Nothing here builds a routing-attribution instrument; [#272](https://github.com/Grimblaz-and-Friends/tradecraft/issues/272)'s answer is stage 3's measurement.

## One thing worth knowing about how this was settled

Six cold seats judged the pre-implementation artifact and the first five returned adverse, every one on a property asserted of the budget that the budget did not have. The repeated failure had one shape — prose quantifying across four quantities with four different memberships — and the repair that worked was replacing the paragraph with a table carrying one row per quantity. That incident is filed as [#290](https://github.com/Grimblaz-and-Friends/tradecraft/issues/290).
