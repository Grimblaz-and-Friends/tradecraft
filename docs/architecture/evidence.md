# Evidence registry — provenance for transcribed claims

ADR-009 §4 mandates citations over copies, and the 2026-08-15 review (finding M28) showed the constitution transcribing its strongest quantitative claims with no attached record. This registry is the repair: every transcribed claim an ADR leans on, with its provenance graded honestly. Grades:

- **repo-verifiable** — checkable from a public repository today; link given.
- **issue-linked** — recorded in a predecessor issue; link given.
- **session-measured** — measured during a recorded working session; the query is given so it can be re-run, but the original run itself is not durably archived.
- **recollection-grade** — carried from the maintainer-side session record of the predecessor; no independently checkable artifact. Claims at this grade must not be load-bearing for new mandates (ADR-009 §3), only illustrative.

| Claim | Used by | Grade | Record |
| --- | --- | --- | --- |
| Predecessor first commit 2025-12-07; ~60 skills (57 measured) | ADR-001, ADR-009 | repo-verifiable | `git log --reverse` and `ls skills/` in [agent-orchestra](https://github.com/Grimblaz/agent-orchestra) |
| Workflow logic in code root-caused 6× to the same never-wired-live failure | ADR-002 | issue-linked | [agent-orchestra#874](https://github.com/Grimblaz/agent-orchestra/issues/874) |
| 15 of 15 sustained findings in newly generalized prose, none in carried-verbatim text | ADR-009 | issue-linked | [agent-orchestra#844](https://github.com/Grimblaz/agent-orchestra/issues/844) review record |
| 324 open / 395 closed issues; ~40% of open untouched 90+ days; open/close rate never net-negative | ADR-006 | session-measured | `gh issue list --repo Grimblaz/agent-orchestra --state open/closed` + age bucketing, measured 2026-08-15 during the backlog-sustainability discussion that produced the filing rule |
| A five-pass review panel sustained a false finding | ADR-006 | recollection-grade | predecessor session record, 2026-08; the panel sustained a "A never provides B to C" claim later disproven by a reference grep |
| Post-fix re-review yields ~1-in-3 additional defects in fresh fixes | ADR-006 | recollection-grade | predecessor session records across three fix cycles (#930, #982, #991-era); consistent but not independently archived |
| Stray zero-byte file dropped by a concurrent agent, nearly committed via broad `git add` | persist-changes SKILL.md | recollection-grade | predecessor session record, 2026-08 (stage-1 parallel review dispatch) |
| `__pycache__` artifacts shipped via broad staging in tradecraft's skeleton commit | ADR exhibits, persist-changes SKILL.md | repo-verifiable | [30fb484](https://github.com/Grimblaz-and-Friends/tradecraft/commit/30fb48482448ded6f45ccd9a2eb6ddb413bdee10), removed in [b98b569](https://github.com/Grimblaz-and-Friends/tradecraft/commit/b98b569) |
| Predecessor shipped-zone relative references to repo-only paths (23 live `../../.github/` instances in 6 skill files) | lint M1 rationale | repo-verifiable | grep in agent-orchestra `skills/` |
| Persona-prompting research both directions | ADR-001 | repo-verifiable | the four papers linked in ADR-001 |
| Full-review stage yields: generalist prosecutors 0 unique sustained findings; defense killed 2 of 4 constitution highs, corrected 12 severities, strengthened 3 findings; judge confirmed defense on all but severity settling; post-fix pass caught 2 defects in fresh fixes | ADR-006 review default | session-measured | 2026-08-15 full review of this repo: 51 raw → 38 merged → 35 sustained / 3 dismissed; rows in ledger.jsonl, fixes in the commit citing them |

Rules going forward: a new ADR claim either links its record inline or adds a row here at the grade it honestly holds; a recollection-grade claim that later gains a record upgrades its row; and per ADR-009 §3, nothing recollection-grade may be the sole support for a mandate.
