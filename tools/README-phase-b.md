# Phase B close reader

`score_phase_b.py` is the repo-only reader for the Phase B window recorded on
tradecraft issue #665. Its product repository configuration names
`Grimblaz-and-Friends/Organizations-of-Verra` and
`Grimblaz-and-Friends/Daemon`; neither product needs a local checkout or a
lab-specific file.

Run `python tools/score_phase_b.py --status` for exactly the qualifying-change
count and whole calendar days elapsed. Run
`python tools/score_phase_b.py --final` only at a terminus. Final mode exits
nonzero without a partial table until the first of 28 calendar days after the
opening instant or 20 qualifying merged product pull requests. At a terminus
it orders rows by merge time, repository, and pull-request number, never by a
measure.

All GitHub traffic is authenticated REST GET traffic through `gh api`. The
reader follows each response's `Link` header. `--now ISO_TIMESTAMP` and
`--transport FIXTURE.json` are deterministic test hooks; a fixture is a
schema-version-1 object whose `responses` maps an exact endpoint to a `body`
and optional `headers` object.

## Record markers

These are HTML comments in GitHub issue bodies or issue comments. Attribute
values contain no whitespace. A record is in the window when its GitHub
record was created from the opening through the closing instant, inclusive.

- `<!-- tradecraft:phase-b-window:v1 opened=TIMESTAMP -->` appears on #665.
  The timestamp is an aware ISO-8601 instant.
- `<!-- tradecraft:change-followup:v1 source_pr=NUMBER -->` appears on an
  issue. The distinct issue counts once for that qualifying product pull
  request.
- `<!-- tradecraft:escaped-defect:v1 found_by=use source_pr=NUMBER -->`
  appears on an issue created strictly after that qualifying pull request
  merged. The distinct issue counts once.
- `<!-- tradecraft:owner-ask:v1 pr=NUMBER -->` makes its issue body or issue
  comment one ask record for that qualifying pull request.

The fourth measure comes from the `change-cost:v1` report produced at read
time by `lib/change_cost.py`, keyed by product repository and pull-request
number. Its raw usage, dated rate-card price, and bill or plan status are
separate table columns. An absent quantity is `unknown`, never zero. The other
three measures are counts and may lawfully be zero. If the read-time cost
report itself cannot be completed, each of its three columns remains unknown
rather than erasing the product-change rows.

The final output has one change table and one close-record table linking #652,
#360, and #653. It makes no comparative decision about repositories, changes,
vendors, or stages.
