# The search before a filing, and its five outcomes

**Loaded when** you are about to create an issue, deciding whether what you hold belongs on one that is already open, or landing a change that fixes a cause carrying findings recorded under it.

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

Five outcomes, each lawful:

- **Extend** an **open** issue — a comment, not a new number. A closed match is a tie, never a home. **Extend only where a ruling that closes the host would dispose of your defect too** — read its comments as well as its body, since an issue is re-scoped where it is discussed. Otherwise it is a tie, and extending buries your defect under a disposal that never reaches it.
- **Record it under its cause** — where the cause is already an open issue, framed or in the pool, and what you hold is one of the instances it was observed producing, the finding lands as a comment on that cause and takes no number of its own. **The extend rule above does not govern it**, and what stands in for that rule is what answers the same burial: not that a ruling closing the cause disposes of the finding, but that **a change fixing a cause disposes of every finding recorded under it — clearing it, or filing it then as its own issue: a finding the fix left standing is one that now needs a fix of its own, and the fix having left it standing is the evidence for that, so the bar a filing about governing prose meets (`../references/what-a-filing-carries.md`) does not run on it.** A finding already carrying a number is tied `caused-by` its cause rather than moved onto it. **A finding takes a number of its own while its cause is still open only where it needs fixing now, and that call is the owner's.**
- **File new with named ties** — the relationship goes on the record at birth instead of being reconstructed at ranking time.
- **File one issue carrying the batch** — where the defects in hand share one cause you can point at, they land as one number rather than several cross-tied ones: each defect with its own evidence, the shared probes stated once, pickup dispositioning them item by item. **The test is a cause you observed, never a fix you would have to design** — what one change would take is remedy design, which this cell leaves to pickup — **and not the surface either**: a shared file neither decides it nor is required. **Where the symptoms already carry numbers, the cause takes its own and the ties (`../references/naming-a-tie.md`) group them**; one number is for what is in your hands at once. [#94](https://github.com/Grimblaz-and-Friends/tradecraft/issues/94) and [#95](https://github.com/Grimblaz-and-Friends/tradecraft/issues/95) are the cost of not taking it — two lawful filings against one sentence, merged into a single PR later, whose pairing had to be reconstructed at ranking time. [#151](https://github.com/Grimblaz-and-Friends/tradecraft/issues/151) and [#152](https://github.com/Grimblaz-and-Friends/tradecraft/issues/152) show the form a batch takes and are not an exhibit for the test: each was warranted by one opening of one cell, which is the surface.
- **File standalone** — nothing turned up that earns a tie.

[#233](https://github.com/Grimblaz-and-Friends/tradecraft/issues/233), [#234](https://github.com/Grimblaz-and-Friends/tradecraft/issues/234) and [#235](https://github.com/Grimblaz-and-Friends/tradecraft/issues/235) came out of one review, each naming the others. #233 and #234 share one cause, line-ending handling every guard passes; #235 named a third file and was closed without a change of its own, its subject discharged by a pull request already in flight. A shared file would have split the pair and grouped nothing.

An extending comment carries the creation list and meets the same evidence standard, and so does a finding recorded under its cause — **except the ratings, which neither carries, having no number of its own to put a label on: the host's stand, and the cause's**, and **except that bar (`../references/what-a-filing-carries.md`), which neither owes: an extending comment inherits its host's, and a recorded finding its cause's**, one filing carrying the incident or the run being what puts them all on the board. The tie is the issue the comment lands on.
