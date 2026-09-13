# The search before a pitch

**Loaded when** creating or extending a pitch, or deciding whether a match covers the evidence in hand.

Before creating an issue, search every issue in the repository — the pool, the board and what is closed.

**The search is not done until it has been run against the subject's identifier, every name the mechanism goes by, and the defect in the repository's own words — over issues in every state, across the whole set rather than a first page.** All three parts are load-bearing.

**Run it as commands,** substituting your own repository. The two surfaces differ on all-states and on multi-word queries, so pick one deliberately:

```
gh search issues "post-fix" --repo OWNER/REPO --limit 1000
gh issue list --repo OWNER/REPO --state all --limit 1000 --search "post-fix"
```

`--state all` is valid on `gh issue list` and rejected outright by `gh search issues`, where every state is the **absence** of the flag. Left at its default of thirty, either surface returns a first page with no warning there was more. A closed issue records what was already decided, already tried, or left behind when its parent closed.

**A quoted argument is one term, and the surfaces read it differently:** `gh search issues` sends it as a phrase, `gh issue list --search` ANDs its words. A name containing a space is a term; a lifted sentence is not — take its distinctive word. `gh search issues "manifest exemption wider"` returns nothing where the other surface returns [#20](https://github.com/Grimblaz-and-Friends/tradecraft/issues/20), whose title carries all three words but not adjacently.

**One term per query, because the failure runs both ways.** A near-miss on the string returns nothing: on this practice's own board, `check_version_bump` returns none of the issues whose titles *begin* with `check_version_bump.py`. Adding a word narrows hard on either surface: `post-fix terminus` returns a small fraction of what `post-fix` alone does. Neither result says which happened to it.

**A mechanism usually answers to three names** — its key, the term the prose uses for it, the file that records it — and one can be the only one that reaches what you need. On this practice's own board `post-fix`, `prosecution look` and `reviews.jsonl` name one mechanism; only `reviews.jsonl` returns [#126](https://github.com/Grimblaz-and-Friends/tradecraft/issues/126), the issue that decided the filing that found this. Running one of the three looks exactly like running the search.

**The defect's own words are the repository's, not yours.** The other two are printed on the artifact in front of you; this one guesses what somebody else called the same thing. Lift it from the material — the rule being breached, the term a decision entry used — rather than coining it, because a coined phrase is queried against a set that could never have contained it.

**Extend an open pitch when the new evidence supports the work it offers.** Read its comments as well as its body, because the offer can change there. An instance of that cause is evidence on the pitch, not a symptom issue and not a promise that every instance must later be fixed or re-filed. A distinct offer that the host does not cover takes its own pitch and a tie.

**A closed match is history, not an open destination.** Read why it closed, then pitch a recurrence on its own evidence and name the relationship. No command reopens it merely because it was met again.

**New pitches name their ties at birth.** Where the evidence in hand shares one observed cause, sell that work as one pitch carrying the evidence together; shared location or origin alone does not make one cause. Existing issues keep their numbers and cause links, which the tie vocabulary describes.

An extending comment meets the evidence floor of `../references/what-a-filing-carries.md`. It inherits its host's incident-or-run admission, takes the host as its tie, and need not carry rating labels of its own. The comment can argue why new evidence changes the offer's value; it does not silently overwrite the filer's ratings.
