# The search before an issue

**Loaded when** creating or extending an issue, or deciding whether a match covers the evidence in hand.

**The search is not done until it has been run against the subject's identifier, every name the mechanism goes by, and the defect in the repository's own words — over issues in every state, across the whole set rather than a first page.** All three parts are load-bearing.

**Run it as commands,** substituting your own repository; the two surfaces differ, and the comments beside each say how:

```
gh search issues "post-fix" --repo OWNER/REPO --limit 1000
#   every state is the absence of a --state flag here, and --state all is rejected outright
#   a quoted argument is one phrase
gh issue list --repo OWNER/REPO --state all --limit 1000 --search "post-fix"
#   --state all is valid only here, and is what reaches closed issues
#   a quoted argument's words are ANDed
#   --limit on both: the default is 30 and a short read says nothing about what it left behind
```

**One term per query, because the failure runs both ways.** A name containing a space is a term; a lifted sentence is not — take its distinctive word. A near-miss on the string returns nothing, and adding a word narrows hard on either surface: `post-fix terminus` returns a small fraction of what `post-fix` alone does. Neither result says which happened to it.

**A mechanism usually answers to three names** — its key, the term the prose uses for it, the file that records it — and one can be the only one that reaches what you need. In this practice's own issue set `post-fix`, `prosecution look` and `reviews.jsonl` name one mechanism; only `reviews.jsonl` returns [#126](https://github.com/Grimblaz-and-Friends/tradecraft/issues/126). Running one of the three looks exactly like running the search.

**The defect's own words are the repository's, not yours.** The other two are printed on the artifact in front of you; this one guesses what somebody else called the same thing. Lift it from the material — the rule being breached, the term a decision entry used — rather than coining it, because a coined phrase is queried against a set that could never have contained it.

**Extend an open issue when the new evidence supports the work it states.** Read its comments as well as its body, because the work can be clarified there. An instance of that cause is evidence on the issue, not a symptom issue and not a promise that every instance must later be fixed or re-filed. Distinct work that the host does not cover takes its own issue and a tie.

**A closed match is history, not an open destination.** Read why it closed, then file a recurrence on its own evidence and name the relationship. No command reopens it merely because it was met again.

**New issues name their ties at birth.** Where the evidence in hand shares one observed cause, state that work as one issue carrying the evidence together; shared location or origin alone does not make one cause.

**An extending comment meets the same floor as an issue** (`../references/what-a-filing-carries.md`), inherits its host's incident-or-run admission, and takes the host as its tie. It may argue that the new evidence changes the work's value. Its shape is `../references/issue-template.md`'s.
