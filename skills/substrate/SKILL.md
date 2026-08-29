---
name: substrate
description: How this practice writes the code it ships and runs — one substrate, tests that travel with the script they prove, guards probed in both polarities, a calling contract portable across runtimes and installs, and text mode's silent damage to output and line endings. Use when writing or revising a script, test, hook or guard, when choosing a language for new code, or when a script prints, writes a file, or finds a file it needs; not for how prose is written or where a rule belongs, not for reviewing finished code, and not for committing and pushing it.
---

# substrate

**Purpose:** make the code this practice ships and runs behave the same for every consumer, on every platform, in every runtime. **Audience:** any session writing or revising a script, test, hook or guard — in this repo or a repo that adopts the practice, whose own substrate is its own choice and not this one's to set. **Success:** a script written under these standards runs the same from a source checkout as from an installed plugin, its output survives being captured, and whatever proves it travels with it.

## The standards

- **Stdlib-first Python** here, because one substrate is one set of idioms to harden. The pick is this practice's own; what carries over is that a practice has one.
- **Tests ride beside the script they cover**, so what proves the code travels with it to every consumer.
- **Guard-shaped code is probed in both polarities** — the unlawful case caught, the lawful case left alone — since a guard blocking lawful work fails as hard as one passing unlawful work.
- **The calling contract names no harness token**, because one runtime substitutes it and another does not, so a contract carrying one binds in the first and is dead in the second. [D-156]
- **A path resolved against the directory of the file naming it** works in a source repository and in an installed plugin alike.
- **A launch redirects nothing, or names all three streams** — redirect one and leave another unnamed, and on Windows that one resolves through a std-handle table which can still name a closed handle: an intermittent `WinError 6` that is not the command's. `references/subprocess-streams.md` carries the mechanism, the compliant forms, and the wrappers that have none. [D-232]

## Text mode

**Text-mode defaults take rules of their own** — output stays ASCII, streams are set up before anything is written, and a file to be compared later is handled as bytes. `references/text-mode.md` carries them, their bounds, and the shipped helper that discharges the stream half; load it when writing a script that prints or writes files. [D-186]
