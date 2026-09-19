# Naming a tie

**Loaded when** you are writing the tie block of a new issue or an extending comment, or setting or reading the cause link between two issues. The block's form is `../references/issue-template.md`'s; this file is what its lines mean.

**A tie name earns its place by changing what a ranking does with the pair.** That is what keeps the set closed, and the test any addition to it must pass.

| tie | what it asserts | what a ranking does with it |
| --- | --- | --- |
| **same-subject #N** | same file, paragraph, or mechanism | consider one PR for both |
| **same-class #N** | different subject, same defect shape | one remedy may serve both |
| **the sub-issue link**, cause as parent | this produced that — the symptom is what the cause was observed doing, and fixing the cause may discharge it or leave it standing | rank the cause above the symptoms a ranking holds and work them as one group led by it; do not schedule a symptom on its own while its cause is open |
| **sequenced-after #N** / **blocks #N** | this cannot start until that lands / that cannot start until this does | order the pair, do not bundle it |
| **supersedes #N** / **superseded-by #N** | this replaces that, or that replaces this, in whole or in part | close or rescope the replaced one |

Each paired relationship **written as a verb** is written in both directions; `blocks` exists because a filing that unblocks an existing issue would otherwise have to edit that issue to record the order.

**The cause relationship is not a verb at all: it is GitHub's sub-issue link, the cause as parent, the parent carrying a `cause` label.** The link means a task split into parts everywhere else, and the label is the only thing saying this one means causation — **an unlabelled parent is invisible to everything downstream**, which is a silent failure rather than a loud one.

The repository creates the `cause` label before using it. The link is a mutation over the two issues' node ids:

```bash
gh api graphql -f query='mutation{addSubIssue(input:{issueId:"<cause id>",
  subIssueId:"<symptom id>"}){subIssue{number parent{number}}}}'
#   node ids: gh issue view <N> --json id
#   parent label: gh issue edit <cause N> --add-label cause; create the label first if the repository lacks it
#   no gh subcommand sets the link as of gh 2.80.0; check gh issue create --help for --parent first, an absence claim about a tool being only as old as the version it was checked against
#   re-parenting: removeSubIssue first, the second addSubIssue being refused while the first link stands
```

A causal relationship you believe but cannot set — the cause in another repository, or no access — goes in the tie block as flagged prose that **says which it is**: nobody will ever link it, so the prose is the record; or it is waiting on access, so the prose comes out when the link goes in. Nothing else tells them apart afterwards, and neither is a candidate for the tie set — causation has a home already.

**A pass that creates more than one issue is not done until each of them names the others.** The numbers do not exist until creation, so the first issue's tie block is completed inside the same pass, by editing its body (`gh issue edit`) — a tie in a comment lands where nobody ranking the work will reach it.

**The same five relationships apply whether the tied issue is open or closed; there is no separate closed-issue vocabulary.**

**The ties are the first element of the issue body, before any heading or prose**, because consistent placement is what lets a session ranking the work find them without reading every body — [#33](https://github.com/Grimblaz-and-Friends/tradecraft/issues/33) named [#20](https://github.com/Grimblaz-and-Friends/tradecraft/issues/20) and [#52](https://github.com/Grimblaz-and-Friends/tradecraft/issues/52) named #35, both truthfully, and both in a closing line nobody ranking the work would reach.

Where the search turned up nothing that earns a tie, the block says so as a fact about the searched issue set, because that is what a ranking uses.
