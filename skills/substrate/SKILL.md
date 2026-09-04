---
name: substrate
description: How this practice writes the code it ships and runs — one substrate, tests that travel with the script they prove, guards probed in both polarities, a calling contract portable across runtimes and installs, text mode's silent damage to output and line endings, and the streams a launch must name. Use when writing or revising a script, test, hook or guard, when judging whether a probe answers the question it is credited with, when choosing a language for new code, or when a script prints, writes a file, finds a file it needs, or launches another program; not for how prose is written or where a rule belongs, not for how a review reaches its findings, and not for committing and pushing it.
---

# substrate

**Purpose:** make the code this practice ships and runs behave the same for every consumer, on every platform, in every runtime. **Audience:** any session writing or revising a script, test, hook or guard, in this repo or a repo that adopts the practice. **Success:** a script written under these standards runs the same from a source checkout as from an installed plugin, its output survives being captured, and whatever proves it travels with it.

## The standards

- **One substrate, chosen once and hardened**, because one substrate is one set of idioms to harden. Which one is the adopting repository's own call, made in its doctrine.
- **Tests ride beside the script they cover**, so what proves the code travels with it to every consumer.
- **Guard-shaped code is probed in both polarities** — the unlawful case caught, the lawful case left alone — since a guard blocking lawful work fails as hard as one passing unlawful work. **A probe must also be shown to answer the question it is credited with** — by a negative control drawn from the probe's own class, demonstrating it would have reported differently had the answer been different; a control outside that class can pass while the probe stays masked. A probe that reports a result it never took is *trusted*, which argument at least is not: [a size-preserving mutation masked by stale bytecode reported SURVIVES for a guard it never broke](https://github.com/Grimblaz-and-Friends/tradecraft/issues/142), and a defense published the false result.
- **The calling contract names no harness token**, because one runtime substitutes it and another does not, so a contract carrying one binds in the first and is dead in the second. [D-156]
- **A path resolved against the directory of the file naming it** works in a source repository and in an installed plugin alike.
- **A launch redirects nothing, or names all three streams** — redirect one and leave another unnamed, and on Windows that one resolves through a std-handle table which can still name a closed handle: an intermittent `WinError 6` that is not the command's. `references/subprocess-streams.md` carries the mechanism, the compliant forms, and the wrappers that have none. [D-232]

## Text mode

**Text-mode defaults take rules of their own** — output stays ASCII, streams are set up before anything is written, and a file to be compared later is handled as bytes. `references/text-mode.md` carries them, their bounds, and the two properties the stream half turns on — which a shipped helper discharges here and a reader outside this tree writes for themselves; load it when writing a script that prints or writes files. [D-186]
