# Reading the pool and buying work

**Loaded when** reading, rating, shortlisting or framing pooled work, or closing quiet pitches.

**A shortlist helps a session choose what to sell when there is room.** It buys nothing and requires no assessment. Bring the strongest few to the owner in the argued form the cell names, and frame what they pick. The two ratings are advisory labels; they do not accrue from instances or decay with age. Unrated and clashing ratings are shown as such. The policy orders the proposals, then the configured tie-break keys, then the issue number. Its `recent` key reads the issue's `updatedAt`, including activity caused by label writes, and the shortlist states what separated the pair at its cut.

Every path below resolves against this file's directory. Global `--repo OWNER/REPO` and `--policy PATH` go **before the subcommand**. Use both when working on another repository: `--repo` changes the GitHub destination, while the policy otherwise resolves from the local checkout. Every command prints its resolved policy.

```bash
python ../scripts/pool.py labels --dry-run
python ../scripts/pool.py labels
python ../scripts/pool.py list
python ../scripts/pool.py show 123
python ../scripts/pool.py rate 123 --rating sev:3 --rating urg:2
python ../scripts/pool.py shortlist
python ../scripts/pool.py frame 123
python ../scripts/pool.py unframe 123
python ../scripts/pool.py fade --dry-run
python ../scripts/pool.py fade
```

**The fade closes a quiet pitch, not a rating.** After one full `fade.quiet_days` window without activity, an open unframed issue is due regardless of its ratings. The shipped policy sets the window to 30 days and `fade.closes` to true. `fade` closes it as not planned with a reason, preserving its body and comments; `--dry-run` previews without writing. A false `fade.closes` also previews without closing. The command rereads each candidate before closing, skipping anything now framed, closed or recently touched. Unknown or future activity supplies no closing clock. `list` and `show` expose the activity and eligibility the command uses.

**Nothing schedules the fade for an adopter.** Run it where the repository performs its refresh; the command is explicit so a read never spends a purchase or closes a pitch. A close does not reopen automatically. Search the closed history before pitching a recurrence, and sell it on the new evidence.

`../scripts/pool-policy.json` holds the default vocabulary, ordering, shortlist size and quiet window. A `pool-policy.json` at the repository root replaces it whole. Retired assessment, accrual and push fields in an older override are ignored, and old issue labels are left intact; a legacy `symptoms` tie-break produces a migration message and no longer orders anything. `cause` still provisions the label used by existing board groups. The old cycle, assessment and push commands are removed rather than aliased to another action.
