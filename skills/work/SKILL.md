---
name: work
description: The single state-driven entrance for a product change. Use when the owner names an issue to work on or continue; use its stage commands only when a power user deliberately wants one stage. Not for deciding whether work is worth doing, changing an affirmed brief, choosing vendor defaults, merging, or answering an owner ask.
---

# work

**Purpose:** turn one issue number into the next stage its GitHub evidence calls for. **Audience:** the holder continuing an affirmed product change, and a power user running one named stage. **Success:** the issue and its linked pull request are read without mutation, exactly one next stage is selected, and no recipient is instructed to continue into another stage.

## Where this cell's depth lives

- **Recording or reading evidence that advances the entrance** → `references/markers.md`: each marker's exact form, lawful values, producer, surface and moment.

For the ordinary entrance, run:

```text
python <plugin-root>/lib/work.py --repo OWNER/REPO --issue N --root PATH
```

In this repository, `<plugin-root>` is the repository checkout root. For an adopter, `<plugin-root>` is the installed plugin directory containing `lib/work.py`. For the ordinary entrance, `--root` is the repository checkout that receives implementation-worktree registrations and supplies `.tradecraft/product-repos.json` and `lib/use-rules.json`.

The script reads issue, pull-request, check, review and comment state with GitHub REST GET requests. A pull request becomes the implementing one only through its own standalone closing reference or the issue's explicit marker, and multiple candidates are refused. On practice-facing work, it applies the repository's own product list where one is configured and refuses dispatch until the issue names an incident from that list, because the practice is a means to better product work rather than its own product. With no configured list, that check does not apply and the decision reason says so.

An affirmed-brief marker counts only with exactly one lawful `Review risk` and `Review lane` pair. Changed paths are matched against the repository's schema-versioned JSON use rules; a bought use needs a current-head note, and the other branch needs its explicit no-use line. These are guards read by the entrance rather than choices it makes.

Power users may put one of `artifact`, `cold-seat`, `build`, `floor`, `use`, `review-disposition` or `release-report` before the options. That runs only the named stage and exits. Every builder prompt names one stage and tells the recipient to return rather than start another.

The entrance consumes the affirmed brief and recorded evidence; it never decides whether work is worth doing, what the change is for, the brief's terms, a vendor or model default, whether to merge, or an owner ask. `ambiguous-pr` returns to the holder, who names the implementing pull request on the issue with the `implementing-pr` marker or opens the one that should exist. Holder-reading, ready/reviewer setup, waiting, panel coordination and terminal states also return to the holder without an unattended recipient.

Before a fresh build dispatch, the entrance atomically registers the canonical implementation root in the machine-local worktree registry. A holder runtime loading project `PreToolUse` hooks refuses writes below every active root; another runtime records `holder_write_guard=unavailable`, with revision and status snapshots providing detection only, because detection is not equivalent enforcement.
