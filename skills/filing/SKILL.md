---
name: filing
description: How evidence becomes an issue that states decided work or a follow-up's fix. Use when creating or extending an issue, deciding whether a finding earns one, or routing an unfixed finding to its permitted end; not for deciding what work is worth doing, and not for the pre-implementation artifact written when work is picked up.
---

# filing

**Purpose:** make each issue a useful statement of work somebody decided to do, and give every unfixed finding one of three ends. **Audience:** a session creating or extending an issue, or routing a finding it will not fix in the current change. **Success:** every issue carries evidence and its ties, every follow-up states its fix, new instances extend the open issue they support, and no undecided offer is filed for somebody else to triage.

## Where this cell's depth lives

- **Creating or extending an issue, or deciding whether a match covers the evidence in hand** → `references/the-search.md`: the search across open and closed issues, the extension that takes no new number, and the ties a new issue carries.
- **Writing the tie block or reading cause links between existing issues** → `references/naming-a-tie.md`: the tie vocabulary, the sub-issue link, and what a ranking does with them.
- **Writing an issue or deciding whether its evidence earns one** → `references/what-a-filing-carries.md`: the evidence floor and governing-prose bar, what a follow-up states, and what design stays with pickup.
- **Copying the shape of an issue body or an extending comment** → `references/issue-template.md`: the fields to copy whole, the tie block first among them; the other files here are the standard those fields meet.

## Three ends for an unfixed finding

An unfixed finding takes exactly one of these ends:

- **Its own pull request now**, where the fix is mechanical.
- **An issue**, where the owner decided the work or a follow-up states the fix it will make.
- **The release report's ask to the owner, once**, where the decision is theirs. Do not create an issue to carry that ask.

**An issue records work rather than a decision somebody still has to make.** Search first, because new evidence belongs on the open issue it supports rather than in a second number. A repository chooses how it marks and orders the work it decided; this cell owns only what the issue itself carries.
