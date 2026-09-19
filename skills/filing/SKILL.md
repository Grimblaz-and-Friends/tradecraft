---
name: filing
description: How evidence becomes an issue stating work the owner bought. Use when creating or extending an issue, deciding whether a finding earns one, or routing an unfixed finding to one of its two ends; not for deciding what work is worth doing, and not for the pre-implementation artifact written when work is picked up.
---

# filing

**Purpose:** make each issue a useful statement of work the owner bought, and give every unfixed finding one of two ends. **Audience:** a session creating or extending an issue, or routing a finding it will not fix in the current change. **Success:** every issue carries evidence and its ties, every open issue is work the owner bought, new instances extend the open issue they support, and nothing an agent proposed is filed for somebody else to triage.

## Where this cell's depth lives

- **Creating or extending an issue, or deciding whether a match covers the evidence in hand** → `references/the-search.md`: the search across open and closed issues, the extension that takes no new number, and the ties a new issue carries.
- **Writing the tie block or reading cause links between existing issues** → `references/naming-a-tie.md`: the tie vocabulary, the sub-issue link, and what a ranking does with them.
- **Writing an issue or deciding whether its evidence earns one** → `references/what-a-filing-carries.md`: the evidence floor and governing-prose bar, what a follow-up states, and what design stays with pickup.
- **Copying the shape of an issue body or an extending comment** → `references/issue-template.md`: the fields to copy whole, the tie block first among them; the other files here are the standard those fields meet.

## Two ends for an unfixed finding

An unfixed finding takes exactly one of these ends:

- **Fixed now** — in the current change where it caused the finding, otherwise in one immediate follow-up pull request carrying the rest together, which keeps the cost one pass rather than one per finding.
- **The release report's ask to the owner, once**, carrying the fix and its cost, so their answer is *do it*, *buy it for later*, or *drop it*.

**No issue is created for work the owner has not bought.** *Buy it for later* creates one; *drop it* creates nothing and is a decline recorded on the work. **Deferred attention is attention, taken twice** — once to pick the item up, once to agree its brief — so a queue of agent-proposed work costs what asking costs, paid later by someone who did not choose to pay it.

**An issue records work rather than a decision somebody still has to make.** Search first, because new evidence belongs on the open issue it supports rather than in a second number. A repository chooses how it marks and orders the work it decided; this cell owns only what the issue itself carries.
