# D-812 — Checked persistence for named staging and catch-up merges

**Purpose:** preserve the reasons and boundaries behind #774's staging, merge and recovery change. **Audience:** a future session revising persistence or the holder's catch-up dispatch. **Success:** that session can supersede these choices without silently inheriting staged work, losing merge ancestry or confusing checked content with publication.

Recorded in [PR #812](https://github.com/Grimblaz-and-Friends/tradecraft/pull/812), implementing [#774](https://github.com/Grimblaz-and-Friends/tradecraft/issues/774), under its [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/774#issuecomment-5922480637) and the settled artifact supplied to the build. The catch-up below carries the implementation evidence at `426c280cfaa55400e6a39e36065752c8f1526422`; the release identifier is `0.166.0` in `.claude-plugin/plugin.json` at that commit.

## Decisions and meaning changes

The owner ruled that naming pre-staged paths is sufficient and that persistence lands a catch-up merge itself. These supersede D-627's inherited pre-loaded-index refusal and D-800's sole-parent identity condition; D-800's whole-tree comparison, hook boundary, expected-old ref update and index preservation remain.

- Outside a merge, inherited staged paths must belong to the named literal files or directories. The refusal names every omission; naming or unstaging those omissions supplies two working remedies. Named paths are re-staged from current working content, with already staged absent paths retaining their deletion. This answers the false remedy encountered by Organizations of Verra's builder.
- An in-progress merge owns its staged tree and needs no path list. Further named paths add checked working changes; unrelated working files remain outside the commit. Unresolved entries refuse before staging. An ancestry-only merge still needs a commit.
- Identity uses the recorded start followed by the ordered merge heads, a unique reflog action and the preceding-event consistency check. The take-back's immutable first-parent proof and atomic expected-old branch update prevent another actor's head from being undone. Working files remain for revalidation. A taken-back merge needs preparation and restart because Git has cleared its merge state; a plain retry loses ancestry.
- A pre-existing unpushed merge receives classification before an ordinary path requirement, staging or nothing-to-commit. The actual selected remote tip establishes publication; an unavailable object is fetched rather than inferring publication from tracking refs. The external unpushed one-parent case is unchanged.
- A schema-versioned atomic UTF-8 receipt in Git's common directory retains local evidence only after exact identity, whole-tree comparison and the branch/head guard. Its immutable commit/tree/start/ordered parents and original branch reflog evidence must agree. Missing, malformed, unsupported, duplicate or inconsistent evidence grants no ownership. Commit shape and a token prefix alone are insufficient. Linked worktrees share the receipt while identity remains tied to the original recorded branch event through Git's backend-independent reflog interface.
- A proved earlier checked merge after push failure receives the existing-commit publication route. Pending staging and working changes survive; this invocation stages, commits and pushes nothing. An external or unidentifiable merge instead receives truthful preservation/back-out/`--no-commit --no-ff` advice. Receipt retention failure stops before push and retains the equal-tree commit; it does not undo checked content.
- The cell's description and scope now cover catch-up landing and the existing protected-branch route. D-627's protected-branch steps remain, with exact remote-head verification of the same checked commit; its universal second-run-stages-nothing claim is superseded. Engagement carries only the holder's dispatch responsibility and points to persistence for mechanics.
- Both content remedies retain hooks. Acceptance validates the formatter's output under unchanged policy. Byte-exact restoration first requires the product holder to reconcile the conflicting path's hook policy. Restoring against unchanged conflicting policy repeats mismatch. These prerequisites make D-800's offered restore route executable without a bypass.

Fresh starts and restarts include `--no-ff` as well as `--no-commit`, because a fast-forward otherwise finishes outside the script. There is no new catch-up scheduling rule, branch creation, push-only flag, automatic retry, rebase or integration decision.

## Demonstrators and limits

Evidence pin: `skills/persist-changes/scripts/persist.py`, `skills/persist-changes/SKILL.md`, `skills/engagement/references/the-stretch.md` and `skills/persist-changes/tests/test_persist.py` to `426c280cfaa55400e6a39e36065752c8f1526422`. The returned refusal-remedy inventory maps every advertised alternative to an executing test. Relevant test families include named staging/current bytes/deletions, omitted-path remedies and directory boundaries; clean/conflicted/fast-forward-eligible/ancestry-only merges; both active-hook merge recovery routes including additions/deletions; receipt uncertainty and copied-evidence controls; rejected push and later checked-merge routing; linked-worktree/reftable evidence; and concurrent descendant/ref/index/lock preservation.

Reproduce focused validation with `python -m pytest skills/persist-changes/tests/test_persist.py -q` at that head, and lint with `python tools/lint.py`. Both passed on the finished catch-up bytes before landing. The original build return at implementation commit `29bb5cb43345cc952b3a6215aa9f476ab7f9fe81` records the repository floor (`python tools/lint.py` and `python -m pytest tools/tests skills lib/tests -q`) and isolated guard-deletion evidence. The repair dispatch required focused tests and lint before each landing and expressly excluded a new full-floor run. No suite count is frozen here.

## First repository catch-up through the new route

The holder dispatched the builder to fetch and start `git merge --no-commit --no-ff origin/main` on `tradecraft/774-7e1f46392feb`. The recorded start was `29bb5cb43345cc952b3a6215aa9f476ab7f9fe81`; the fetched target was `8887b7513b9249b60c1e7b803f068e44fcd6765d`, carrying #807, #805 and #806. Only `.claude-plugin/plugin.json` conflicted, and the builder resolved its version to the holder-prescribed `0.166.0`. The test file merged automatically, retaining #807's `maintenance.auto false` settings on origin and clone and its assertion alongside #774's tests. No other conflict required a resolution.

After staging the resolution and passing focused tests and lint, the builder invoked its branch's own script without a path list:

```text
python skills/persist-changes/scripts/persist.py -m "Catch up with main while preserving checked merge landing (#774)" --expect-branch tradecraft/774-7e1f46392feb
```

Its output line was:

```text
persisted: 426c280cfaa5 -> origin/tradecraft/774-7e1f46392feb (19 file(s))
```

Commit `426c280cfaa55400e6a39e36065752c8f1526422` has the recorded start and target as its ordered parents and tree `2ab440dec3fadd3dbb98d93f07686fc4e1120cfd`. The retained schema-v1 checked-merge receipt agrees with that commit, tree and parent vector. A read-back with `git ls-remote origin refs/heads/tradecraft/774-7e1f46392feb` returned the same full commit ID; the worktree was clean and merge state was absent. This run landed the catch-up through the new route without a refusal, path enumeration or a hand-made commit or push. It does not establish the mismatch or rejected-push recovery routes beyond the pinned test evidence.

The builder ran on Windows. Linux execution, later consumer use, connected review, proof and release are not established by this entry. The holder owns those stages; `.github/workflows/ci.yml` at `426c280cfaa55400e6a39e36065752c8f1526422` declares the Ubuntu/Windows suite matrix rather than proving that either remote leg has run.
