# What the refresh note owes its reader

**Loaded when** you are writing a refresh note, or reading one to see what it should have carried.

The note is posted as a project status update, dated and kept, and read back with `notes`. It is what the owner actually reads, so it carries what a board cannot. **Its material comes from two places and neither alone is enough:** `sync` reports what arrived and what was archived, `apply` reports what moved and what was relabelled. `apply`'s diff cannot see membership — it refuses any plan whose membership differs from the board — so a note written from it alone will call a refresh unchanged that added and closed issues.

- **The deltas** — what moved, what arrived, what closed, each with its one-line reason. Not a restatement of the board. **A refresh that changed nothing says so**, in one line.
- **The watch-items** — what the board as a whole is trending toward, which no single item shows. Rate of arrival against rate of closure, and any single item whose settling would reshape everything behind it.
- **The assessments** — the answers the cycle (`../references/refreshing-it.md`) produced, and which it left.
- **The drift look**, below.
- **The reach line** — the charter's row from `python tools/lint.py`'s pointer-reach block, beside the figure the last note to carry one gave and that note's date. It covers the charter and the shipped cells it reaches, so repo-only prose here can grow without moving it. [D-522]
- **The ceiling line** — the same command's `cell bodies over where they stood` line, copied whole: every cell body past where it stood when its ratchet was set, and by how much. **It is a reading and nothing files from it.** `none` is a result like any other and is carried too, an absent line being indistinguishable from a refresh that did not look. [D-544]

Reasons, not conclusions alone: the note is read cold days later by someone reconstructing why the board looks like this. **A figure in a note carries the command that derives it** — the note is kept and never edited, so a number standing alone cannot be re-checked by the reader who needs it most.

## The drift look

`docs/values.md` asks for a periodic look at what actually shipped — *"if it's all short-horizon and measurable, the drift is happening regardless of how each call felt"* — and nothing else performs it. Every refresh note carries an observation over recently closed work, derived rather than recalled:

```
gh issue list --repo Grimblaz-and-Friends/tradecraft --state closed --limit 40 \
  --json number,title,closedAt,stateReason --jq '[.[]|select(.stateReason=="COMPLETED")]'
gh issue list --repo Grimblaz-and-Friends/tradecraft --state all --limit 400 \
  --search 'created:>=YYYY-MM-DD' --json number --jq length
```

`stateReason` is not optional: without it the set includes work closed `NOT_PLANNED`, so the look forms its observation partly over things that were declined rather than shipped. The second command supplies the arrival half of the watch-items; substitute a date and say in the note which window you used.

**State an observation, not a list.** A list of closed issue numbers is material for the look, not the look — a reader given one can say only that a single instance is not drift, which is the wall this exists to get past. Name what the shipped mix is weighted toward, and whether prevention, tooling and craft are represented in it or only the measurable.
