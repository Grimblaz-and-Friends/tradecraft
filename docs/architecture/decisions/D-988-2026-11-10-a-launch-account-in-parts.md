# D-988 — A launch's account in parts

**Purpose:** record why #957 lets one launch's account run across several `launch-account` comments, why a repeated finding takes its latest naming, and why a comment naming a finding its launch didn't flag counts for nothing as a whole. It also records the calls made inside the brief's rows. **Audience:** a future session changing how the entrance combines launch accounts, the held report's fields, or the account procedure. **Success:** that reader can recover what was chosen over what without the issue.

The owner's [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/957#issuecomment-6773226962) governs. Its pre-implementation artifact was [settled on the would route](https://github.com/Grimblaz-and-Friends/tradecraft/issues/957#issuecomment-6773889772). The lane is ordinary / connected, and no panel was bought. This record supersedes none; it narrows [D-939](D-939-2026-11-03-claude-launch-writes-stay-in-their-tree.md)'s single exact account to the comments that count together.

## The limit that made one comment too small

GitHub accepts an issue comment of up to 262,144 UTF-8 bytes; its refusal message names 65,536 characters, which is not the limit. #957's premise test ([comment 6674635185](https://github.com/Grimblaz-and-Friends/tradecraft/issues/957#issuecomment-6674635185)) measured it; [D-870](D-870-2026-10-06-settlement-sources-and-byte-bound.md)'s earlier probe agrees, and [D-967](D-967-2026-11-07-the-standing-page-in-parts.md) records the same limit. The affirmed brief puts an entry naming a session at about 101 bytes, so a launch with a few thousand findings had no lawful release while each comment was judged alone; `test_an_account_over_one_comments_limit_releases_in_parts` builds such an account.

## What was chosen over what

- **Several comments, over packing several ids into one entry** (option A, bought 2026-11-06, unparked 2026-11-10: "957 - A, unpark it"). Packing keeps a ceiling and changes the marker's form; several comments have no ceiling and leave every account already posted reading as before.
- **A finding named in two counting comments takes the later one, over the bought rule that no id may be named twice** (the owner's ruling, 2026-11-10: "B, later governs"). A long account is written by a script, so a holder fixing a few entries, or a retried post that had landed after all, is the likely repeat. Under the bought rule either would hold the change again, even after a release, and the only way out would be editing or deleting a comment, rewriting the record. The owner was told the case against: two parties shown for one finding, and a careless later comment overriding a careful earlier one, a builder-damage account included. The report's `governing` shows which comment governs each repeat.
- **Within one comment a repeat still voids that comment.** There it is a writing error, not a correction.
- **Later means created, never edited.** Ordering reads each comment's creation time, so an edit can't take governance back.
- **A comment naming any id its launch didn't flag counts for nothing, its other entries included,** over counting the entries that match. Such a comment was most likely written for another launch, so counting part of it would be a guess.

## Calls made inside the rows

- **Which comments a held launch lists as not counting.** Those whose `dispatch` is this launch's, those whose `dispatch` can't be read, and those for another launch that name at least one finding this launch flagged. Row 3 asks for every comment for that launch; a post for another launch naming this one's findings is the misdirected post a holder needs to see, and listing every other launch's accounts would bury what is owed.
- **A local-tree finding the tree has since released still counts as flagged.** The launch did flag it, so a comment that named it while it was owed keeps counting once the tree catches up, rather than being voided whole and leaving its other findings owed.
- **The report's fields.** `findings` stays everything the launch flagged; `owed`, `accounts`, `uncounted` and `governing` (limited to findings named more than once, so a flood doesn't double the report) are added; the single `account` field is dropped from every entry, since nothing outside `lib/work.py` read it. The refusal lists only what is owed, under `owed`, and keeps its reason `launch-findings-unaccounted`.
- **A `names-unflagged` reason lists at most ten ids, sorted, with a count,** because a comment written for another launch's flood could name thousands.
- **No comment-size check in code,** because the entrance reads comments and never posts them. No tool writes or posts an account.

The tests are `lib/tests/test_launch_findings.py` (the split, the limit, each uncounted reason, governing, the edit order and the in-comment repeat) and `lib/tests/test_cloud_build.py::test_only_the_tree_releases_the_local_tree_hold`.
