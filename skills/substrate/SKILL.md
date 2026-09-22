---
name: substrate
description: How this practice writes code that behaves consistently across platforms and runtimes — calling contracts, tests, text output, standard streams, and child-process streams. Use when writing or revising a script, test, hook or guard, when choosing a repository substrate, or when code prints, writes a comparable file, resolves a path, or launches another program; not for prose standards, content placement, review, or committing.
---

# substrate

**Purpose:** make code written under this practice behave the same for every consumer on every supported platform and runtime. **Audience:** a session writing or revising a script, test, hook or guard. **Success:** the implementation fits its repository's substrate, its proof travels with it, its output survives capture, and its launches have explicit boundaries.

## Where this cell's depth lives

- **A script prints, or writes a file something will later compare, restore or measure** → `references/text-mode.md`: the text-mode rules and what each guard can establish.
- **A script launches another program** → `references/subprocess-streams.md`: why a launch redirects nothing or names all three streams.

## The standards

- **Choose one substrate for a repository and harden it**, because one substrate means one set of idioms and failure modes to learn.
- **Tests ride beside the code they prove**, so the proof reaches every consumer of that code.
- **Probe guard-shaped code in both polarities and include a negative control from the probe's own class**, because a guard that blocks lawful work or a probe that never could have changed its answer proves nothing.
- **A calling contract names no harness token**, because a token one runtime substitutes and another reads literally binds only one of them.
- **Machine-read output stays ASCII**, because platform text encodings can garble a diagnostic at the moment it is captured.
- **A command-line parser receives an explicit description rather than a module docstring**, because help text can be written before the program configures its streams.
- **A script configures standard output and error before any other entry-point work**, because even argument parsing can write and exit first.
- **A launch redirects nothing, or names standard input, output and error together**, because an unnamed Windows stream can resolve through a closed process handle.
- **Comparable files are written as bytes, and text streams explicitly choose UTF-8 with newline translation suppressed**, because text mode silently changes bytes across platforms.
- **Resolve a relative path from the file that names it**, because working directories differ between source checkouts and installed copies.
- **A change to the shape of a durable record owes the records already written a migration or a recovery route**, because a guard that can only report that a record is old strands exactly the work it was protecting.
