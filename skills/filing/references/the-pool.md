# Reading the pool and buying work

**Loaded when** reading, rating, shortlisting or framing pooled work, or closing quiet pitches.

**A shortlist is a read that helps choose what to sell; it buys nothing.** What separated the last item raised from the first not raised is printed with it. Every label write is activity on the issue, so rating a pitch restarts its quiet window.

Every path below resolves against this file's directory. The policy resolves from the checkout you stand in and not from `--repo`, so a write against another repository carries this one's vocabulary unless `--policy` names its own.

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

**The fade closes a quiet pitch, not a rating.** One full quiet window without activity makes an open unframed pitch due whatever its ratings.

**Nothing schedules the fade for an adopter.** Run it where the repository performs its refresh; the command is explicit so a read never spends a purchase or closes a pitch.

`../scripts/pool-policy.json` holds the vocabulary, ordering, shortlist size and quiet window, and a `pool-policy.json` at the repository root replaces it whole. [D-590]
