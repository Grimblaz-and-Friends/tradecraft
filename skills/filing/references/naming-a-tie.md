# Naming a tie

**Loaded when** you are writing the tie block of a new issue or an extending comment, or setting or reading the cause link between two issues.

**A tie name earns its place by changing what a ranking does with the pair.** That is what keeps the set closed, and the test any addition to it must pass.

| tie | what it asserts | what a ranking does with it |
| --- | --- | --- |
| **same-subject #N** | same file, paragraph, or mechanism | consider one PR for both |
| **same-class #N** | different subject, same defect shape | one remedy may serve both |
| **the sub-issue link**, cause as parent | this produced that — the symptom is what the cause was observed doing, and fixing the cause may discharge it or leave it standing | rank the cause above the symptoms a ranking holds and work them as one group led by it; do not schedule a symptom on its own while its cause is open |
| **sequenced-after #N** / **blocks #N** | this cannot start until that lands / that cannot start until this does | order the pair, do not bundle it |
| **supersedes #N** / **superseded-by #N** | this replaces that, or that replaces this, in whole or in part | close or rescope the replaced one |

Each paired relationship **written as a verb** is written in both directions; `blocks` exists because a filing that unblocks an existing issue would otherwise have to edit that issue to record the order.

**The cause relationship is not a verb at all: it is GitHub's sub-issue link, the cause as parent, the parent carrying a `cause` label.** [D-429] The link means a task split into parts everywhere else, and the label is the only thing saying this one means causation — **an unlabelled parent is invisible to everything downstream**, which is a silent failure rather than a loud one. One link is carried by both issues, so a session opening a symptom sees its cause and a session opening the cause sees every symptom, whichever was filed first and without either body saying so. **GitHub refuses a second parent**, so a symptom carries one cause and the question of what two would mean cannot be asserted.

**No `gh` subcommand set the link as of 2.80.0**, so it is a mutation over the two issues' node ids, which `gh issue view <N> --json id` returns — check your own `gh issue create --help` for a `--parent` flag first, since an absence claim about a tool is only as old as the version it was checked against. The label is an ordinary one and `--label` puts it on, but it has to exist in the repository before it will:

```bash
gh label create cause --description "Observed cause of the issues linked under it"
gh api graphql -f query='mutation{addSubIssue(input:{issueId:"<cause id>",
  subIssueId:"<symptom id>"}){subIssue{number parent{number}}}}'
```

**Re-parenting takes `removeSubIssue` first**, the second `addSubIssue` being refused while the first link stands.

A causal relationship you believe but cannot set — the cause in another repository, or no access — goes in the tie block as flagged prose that **says which it is**: nobody will ever link it, so the prose is the record; or it is waiting on access, so the prose comes out when the link goes in. Nothing else tells them apart afterwards, and neither is a candidate for the tie set — causation has a home already.

**A symptom whose only relationship is its cause writes no tie line at all**, the link being the record — and its block does not then claim *no siblings on the board*, which would be false of an issue that has a parent. Say that its cause is linked.

**A pass that creates more than one issue is not done until each of them names the others.** The numbers do not exist until creation, so the first filing's tie block is completed inside the same pass, by editing its body (`gh issue edit`) — a tie in a comment lands where nobody ranking the board will reach it. That is not the edit `blocks` avoids: that one mutates an issue a ranking may already have read; this one closes a filing nobody has seen yet.

**The same five relationships apply whether the tied issue is open or closed; there is no separate closed-issue vocabulary.** What shifts is the ranking consequence — against a closed target it is that the issue is read, not that anything is scheduled — and, on the ordering row, the assertion itself: `sequenced-after` is already satisfied and `blocks` does not hold.

Write the ties as the **first element of the issue body, before any heading or prose**, one per line as `<verb> #N — <one clause of why>`. One pair may carry more than one verb, one per line; a relationship none of the five expresses is carried in the same block in prose and flagged as a candidate for the set. Consistent placement is what lets a session ranking the board find ties without reading every body — [#33](https://github.com/Grimblaz-and-Friends/tradecraft/issues/33) named [#20](https://github.com/Grimblaz-and-Friends/tradecraft/issues/20) and [#52](https://github.com/Grimblaz-and-Friends/tradecraft/issues/52) named #35, both truthfully, and both in a closing line nobody ranking the board would reach.

Where the search turned up nothing that earns a tie, the block says so **as a fact about the board** — *no siblings on the board* — because that is what a ranking uses. Where one limb could only be run on a phrase you coined, its zero is a fact about the phrase rather than the board, and the block claims the narrower thing. **Do not state that the search was performed.** The ties are its artifact, and a compliance sentence nobody can check buys nothing.
