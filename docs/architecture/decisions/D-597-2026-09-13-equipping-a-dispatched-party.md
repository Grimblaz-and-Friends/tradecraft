# D-597 — A dispatched party is equipped by the material that assigns it

**Purpose:** preserve why this practice states equipping in prose beside the assignment rather than in a launcher, and what the run that settled it closed off. **Audience:** a future session extending the stretch material, writing an implementer launcher, or re-opening whether the implementer may commit. **Success:** they can tell which claims here rest on a run and which on judgement, and they do not re-derive the launch route from the failure that preceded it.

The owner affirmed [the brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/593#issuecomment-5653959169) after amending it; the [artifact](https://github.com/Grimblaz-and-Friends/tradecraft/issues/593#issuecomment-5654053251) settled in one cold round, `would`, before implementation.

## What the run closed off

[#593](https://github.com/Grimblaz-and-Friends/tradecraft/issues/593) was filed with two candidate remedies — an exception to the rule that the implementer commits, or an unsandboxed implementer — and the [spike](https://github.com/Grimblaz-and-Friends/tradecraft/issues/593#issuecomment-5653831839) retired both before either was designed. On `codex-cli 0.154.0-alpha.6.2`, an agent launched with `--approve-for-me` met the same `.git/index.lock` refusal, escalated, was approved, and committed; a resume of that thread committed again, staging on its first attempt. Both commits were verified from outside the agent. **[D-591](D-591-2026-09-13-one-holding-session-per-change.md) recorded the failure conditioned on approvals being off, and that condition is what the spike answered** — the wall was configuration, not capability, and no rule needed an exception.

Two properties of the route came out of running it and are why the example says what it does. `--approve-for-me` is rejected alongside `--sandbox`, exit 2 before the model runs, so the natural way to write the line down — naming the sandbox you mean to keep — is the way that does not start. And a dispatch instructing the implementer to stop rather than work around a failure suppresses the escalation, because the escalation is something the agent requests after a refusal: the spike's own first arm carried that instruction and produced no commit. **A usable flag does not make an assignment performable if the dispatch closes the route the flag opens**, which is the general claim this change is about, observed in miniature.

## Why prose beside the assignment, and not a launcher

The charter admits the cheapest reliable material first and builds a script only for a concept prose already states in one sentence. That sentence did not exist before this change, so a launcher could not have been built for it in the right order. Extending `lib/dispatch_seat.py` was rejected on three further grounds: it is one-shot and read-only by design while the implementer is resumed across turns; the model and effort a launcher would have to choose are [#592](https://github.com/Grimblaz-and-Friends/tradecraft/issues/592)'s open question; and automating the launch buys none of what the incident cost, which was a session not knowing what to supply.

The obligation is stated where the job is handed over rather than in a catalogue of runtimes, because what a party needs is a fact about the assignment and the catalogue would be stale the week it was written.

## Scope, and what was deliberately not done

The rule is general and shown once. The owner affirmed that breadth against the narrower option of writing only the implementer's own start-up, taking the wider rule at the narrower one's evidential bar: two faces on the record, one of them already patched. The judging-seat face stays where `skills/adversarial-review/references/dispatch.md` already handles it, by carrying executable probe evidence and execution gaps to a seat with no shell; a reverse pointer from `skills/engagement/references/the-stretch.md` was refused because that file is already routed to from there and the authoring standard forbids the ring.

The worked example names Codex by vendor. That was the holding session's call, reported in the brief and uncontested, and it follows the vendor naming the same file already carries in its default staffing sentence.

## What this entry does not claim

No complete resume invocation is published, because none was executed in the form it would take; the spike demonstrates that a resumed thread commits, not a line to copy. Enabling the approval route does not guarantee a request is granted — a rejection or an unavailable route remains an inability the implementer reports. And at the time of writing, the built prose's own acceptance criteria had been exercised by nothing but the change that wrote them: the first implementer to commit its own work here was this change's, which is evidence the route works and not evidence the wording teaches it.
