# D-679 — Cross-change read

**Landed by** [PR #679](https://github.com/Grimblaz-and-Friends/tradecraft/pull/679). Closes [#677](https://github.com/Grimblaz-and-Friends/tradecraft/issues/677). Governed by the [affirmed implementation brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/677#issuecomment-5754095971), the [settled artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/677#issuecomment-5754243244), its first-round [`would` verdict](https://github.com/Grimblaz-and-Friends/tradecraft/issues/677#issuecomment-5754298554), and the [holder's reading](https://github.com/Grimblaz-and-Friends/tradecraft/issues/677#issuecomment-5754298636). The base is `c365cfad374261798c0aed742979e794186108d8`.

## Context

The practice retained a marker timeline, pull-request body and dispatch bundles for each change, but nothing asked the holding session to read those records across landed changes. Markers showed what ran and left skipped, bypassed and stalled stages unrecorded. The evidence on [Organizations of Verra #458](https://github.com/Grimblaz-and-Friends/Organizations-of-Verra/issues/458), [PR #459](https://github.com/Grimblaz-and-Friends/Organizations-of-Verra/pull/459) and [PR #462](https://github.com/Grimblaz-and-Friends/Organizations-of-Verra/pull/462) also showed why likeness to an expected path was the wrong judgment: different paths produced different evidence and cost, and the departing path found product defects a conformity score would obscure. Those records motivated this decision but supplied none of its terms.

## Decision

### Engagement owns the shipped method

The holding session performs the read, writes its note and takes its exits, so `skills/engagement/references/change-paths.md` carries the method behind one indexed trigger. A reference keeps the cadence-only procedure off the engagement body, which every design, artifact, dispatch and handback firing pays to load. A new cell was rejected because the read has no independent actor or job outside engagement.

The charter's release paragraph carries the always-on hook that a pull request records which stages the change skipped, bypassed or stalled at and why, or that the expected path ran without a departure. The engagement reference remains the single owner of the paragraph's form and the read's method. This repository's pull-request form adds one sentence pointing to the `engagement` cell rather than copying that depth, and the plugin version moves to `0.144.0` so an adopter receives the revised cells. The shipped prose does not cite this entry: rationale may remain repository-only, while an adopter must be able to follow the method without this log.

### The cadence is observed rather than automated

The cadence reuses a status read the holder already observes and otherwise fires after five merged changes. It adds no scheduler, hook, workflow, scorer, marker or per-change review. The status observation does not inherit the evaluation reader's exclusions, and this change does not alter that reader's measures, termini or output.

At landing, the repository-specific Phase B binding is:

- `python tools/score_phase_b.py --status`, the command named by `tools/README-phase-b.md` at `c365cfad374261798c0aed742979e794186108d8`;
- `<!-- tradecraft:phase-b-window:v1 opened=2026-09-20T18:50:14Z -->`, the first-read watermark recorded by the authorized [opening comment on #665](https://github.com/Grimblaz-and-Friends/tradecraft/issues/665#issuecomment-5752077642);
- [#665](https://github.com/Grimblaz-and-Friends/tradecraft/issues/665) as the note's destination while that window is open, the same record issue bound by `tools/score_phase_b.py` at the base.

Those are today's repository constants, kept here so the shipped method stays portable and the chain to the local application is one repository-only file. The opening marker supplies the first interval's earlier bound; every later interval uses the cutoff recorded in the previous note. Capturing that cutoff before any repository query keeps a merge arriving during the read for the next interval instead of losing it between queries and note creation. When Phase B ends, its status-read arm and destination cease to apply; the five-merge cadence remains, and the first holder who needs the later destination opens one standing issue. Creating that issue now was rejected because it would be an empty second record beside the active one.

### Evidence and cost decide the comparison

The read compares the actual path, the path the practice expected for that change and the reader's counterfactual by the evidence the actual paths produced and what their records establish they cost. Native dispatch quantities remain separate and unknowns remain unknown. A counterfactual receives no credit for a finding it did not produce, and a difference is not itself a defect.

A conformity score, ranking or required finding count was rejected because it would reward resemblance rather than the product of a path. Reading chat transcripts was rejected because the durable marker, pull-request and dispatch records are the evidence another holder can inspect. Older pull requests are not backfilled; an unrecorded call stays unknown where the allowed evidence cannot establish it.

### The changed behavior buys use

The changed `skills/**` paths match the `runtime-or-user-surface` rule in `lib/use-rules.json` at the base, and the new method changes how a later holding session works. The change therefore buys an experience session in which a fresh holder receives the built cell and real landed records, then performs the read and writes its note without the implementation brief, artifact or expected observations. This tests whether use produces comparison by outcomes and cost and sends each finding to one existing exit, rather than merely whether a reader can paraphrase the rule.

## Cost and rejected alternatives

The added reference increases the prose reached whenever engagement's cross-change trigger fires and, through existing cell edges, the measured reach of cells that already point to engagement. That cost is accepted because placing the procedure in the engagement body would charge every engagement firing, while a new cell would duplicate its actor and reporting boundary.

Also rejected were a second copy of the engagement depth in this repository's landing cell, a product or repository identity in shipped prose, a new cadence mechanism, a change to Phase B, a conformity score, a note template or schema, and a standing issue created before Phase B ends. Each would either duplicate an owner, make portable prose local, or turn a manual read over existing evidence into another process machine.

## Evidence

The pull request body is where the final executable-floor output and fresh-consumer use evidence will be recorded, each pinned to the pull-request revision that ships. This entry cannot name that revision while it is being written because adding it and its index row produces the amended commit.

The implementation surface is re-derived with `git diff --name-only c365cfad374261798c0aed742979e794186108d8 <pull-request-head>` and its content with `git diff c365cfad374261798c0aed742979e794186108d8 <pull-request-head>`. The structural floor is `git diff --check`, `python tools/lint.py`, and `python -m pytest tools/tests skills lib/tests -q -n auto --dist loadfile` on that head. Once run, the behavioral proof will be the fresh-consumer experience note recorded in the pull request body.
