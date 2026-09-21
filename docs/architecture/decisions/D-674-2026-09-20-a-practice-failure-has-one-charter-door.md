# D-674 — A practice failure has one charter door

**Landed by** [PR #674](https://github.com/Grimblaz-and-Friends/tradecraft/pull/674). Closes [#673](https://github.com/Grimblaz-and-Friends/tradecraft/issues/673). Governed by the [affirmed implementation brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/673#issuecomment-5752995440), the [settled artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/673#issuecomment-5753087113), and its qualified first-round [`would` verdict](https://github.com/Grimblaz-and-Friends/tradecraft/issues/673#issuecomment-5753122893). The base is `72c4e30a10fc539a6867bccdd698275c189cabff`.

## Context

The product incident on #673 records a session working in an adopting repository being sent toward a practice file the product should not carry, then asking the owner what to do. The owner relayed the failure to the holding session, and it became [#672](https://github.com/Grimblaz-and-Friends/tradecraft/issues/672) two hops later. The same issue records two further failures filed against a shared gate in a form the reporting session invented. Those incidents are evidence for the missing route, not terms of this decision.

The practice already had an admissible product-incident record, but only the holder-facing `work` cell exposed it. The charter — the one practice text every adopting session receives before acting — said nothing about a failure of the practice itself. That left the owner as the relay or the reporting session to invent a destination and form.

## Decision

### The charter is the one door

One paragraph goes in `skills/charter/SKILL.md` under **Content and evidence**, immediately before its existing final paragraph. That section already owns where durable evidence belongs, while the new instruction has to bind before a more specific cell can be relied upon to load. The paragraph is the operative rule; this entry records why it has that shape and is not a second source for it. The shipped paragraph therefore carries no citation to this repo-only entry.

A new numbered section was rejected. `tools/check_codex_compat.py` at the base derives compatibility evidence from the existing numbered sequence, and `tools/tests/test_codex_compat.py::test_charter_evidence_rejects_a_seventh_numbered_concept` pins the rejecting polarity. Placing the paragraph inside the existing section also preserves the final prose paragraph used as the compatibility tail.

### The installation names the destination

The practice repository is resolved from the installed plugin's `homepage`, whose source at the base is `.claude-plugin/plugin.json`. The shipped instruction therefore needs no product name, repository owner, login, or repository URL that could diverge from the installation carrying it.

### The existing marker supplies the form

The paragraph routes the reporting session to the `product-incident` record in the `work` cell's marker reference. `skills/work/SKILL.md` at the base routes a reader to `skills/work/references/markers.md`, and that reference owns the exact record and its lawful producer, surface, and moment. The charter does not copy the marker syntax: copying it would create a second operative form that could drift.

The filing also carries the command run and the output seen. For an adopting repository on the practice repository's product list, the record makes the incident admissible to the existing entrance; command and output make the failure rerunnable rather than merely described. No entrance behavior, product list, marker syntax, or producer rule changes in this decision.

An adopting repository absent from that list files the same record in the same place. At the base, `skills/work/references/markers.md` makes list membership a lawful value and `lib/work.py` counts incident evidence only for configured product repositories, so the entrance does not count that filing as the incident practice work requires until the owner lists the repository; until then, it is a report the holder reads and the owner rules on. Widening admission, whether by listing the repository or by adding an admission path for outside adopters, is the owner's decision and outside this change.

### Filing does not stall the product work

After filing, the session continues by whatever route the owner allows rather than waiting for the practice to be fixed. The owner remains responsible only for a route that is genuinely theirs; they do not relay the failure. This keeps a defect in the practice from stopping the product work the practice exists to serve.

## Meaning change and cost

Before this change, the charter had no instruction for a failure of the practice itself. After it, the charter supplies one filing door and a continuation rule. No existing charter sentence is redefined, removed, or moved, and its purpose, audience, and success statement remain the review bar for the enlarged page.

The cost is permanent always-on reading weight: every adopting session receives the added paragraph. That cost is accepted because the charter is the only shared practice surface already in hand at the moment the failure occurs, and the recorded incidents show the alternative spending the owner's attention or producing an improvised report. The retired size-ceiling and admissions machinery is not restored.

## Rejected alternatives

- **A mirror in each product repository:** duplicates the rule on surfaces that can drift and still leaves the shared practice without its own door.
- **A change to the entrance, product list, record, or producer rules:** the existing marker is already the admissible form; this change exposes it to the reader who lacked it.
- **Notification, delivery, or a message channel between sessions:** filing is the door; transport is a different mechanism the implementation brief excludes.
- **Opinion or satisfaction feedback:** the filing carries a reproducible failure, not a survey response.
- **Waiting for the practice's fix:** makes the process defect block the product work it is meant to support.
- **Another numbered charter section:** breaks the compatibility shape where an existing evidence section already fits.
- **A hard-coded repository identity or copied marker syntax:** duplicates information the installation and the owning reference already provide.

## Evidence

The pull request body carries the final executable-floor output and the fresh-consumer use evidence, each pinned to the pull request head that will ship. This entry cannot name that revision while it is being written because adding it and its index row is what produces the amended commit.

The implementation surface is re-derived with `git diff --name-only 72c4e30a10fc539a6867bccdd698275c189cabff <pull-request-head>` and its content with `git diff 72c4e30a10fc539a6867bccdd698275c189cabff <pull-request-head>`. The structural floor is `python tools/lint.py` and `python -m pytest tools/tests skills lib/tests -q -n auto --dist loadfile` on that head. The behavioral proof is the use note linked from the pull request body, run by a fresh consumer without this change's history or another route supplying the destination or form.
