**Load this when writing a script that prints, or that writes a file something will later compare, restore or measure.** A session revising prose does not need it.

Text mode is the substrate's sharpest edge, and it takes three rules because it has three surfaces. A text stream encodes to the platform's locale codepage and translates newlines, silently, whichever way the obvious call is written — cp1252 on Windows, *including when the destination is a pipe*, which is what a CI log, an agent harness and a captured command all are. So the failure fires precisely where the output is machine-read.

## The three rules

- **Machine-read output stays ASCII.** No non-ASCII character in a string constant that is not a docstring.
- **A stream is set to UTF-8 with LF endings before anything is written to it.** First statement of the entry point, and the ordering is not incidental: a call after argument parsing is a call that `--help` has already outrun.
- **A file that will later be compared, restored or measured is written and read as bytes**, with byte-identity asserted on restore.

## Why the first two are not a choice

They look like alternatives and are not, and mistaking them for a choice is how this bites twice.

A rule about characters can be **guarded exactly**, because "is this byte ASCII" is a fact about the source. But it reaches only what you write, and a guard for it reads **string literals** — so it flags a filename or a regex source alongside a message, and it cannot see a character built at runtime by `chr()`, a format call, or a `__str__`. State that bound where you state the rule: a guard whose message claims to know what reaches a stream is claiming something it never computed, and a session that believes it reasons about the wrong thing.

A stream set to UTF-8 covers what you were **handed** — a path from version control, a filename a consumer chose, a subprocess's stderr — which no literal check can reach. That half fails hardest exactly where it matters most: outside the code page it does not garble, it *raises*, killing the report before the offending name prints, so the message naming the problem is the message that goes missing.

**Guard the second at the call site, not by tracing reachability.** "Did this helper get called on this path" is undecidable from a syntax tree, and that objection is why a helper is sometimes rejected outright. It is the wrong question. The first statement of the entry point is a **position**, and a position is exact. Check the import binding too, or a local no-op with the right name satisfies the guard while setting nothing up.

## What setting the stream also does

**It pins the line ending as well as the encoding, and that is a decision rather than a side effect.** A text stream's platform default translates a line feed on the way out; suppressing that translation means every caller now emits the same bytes on every platform — which is what a consumer comparing, diffing or hashing a captured stream needs.

Say so where you state the rule. Leave it unsaid and whoever notices their redirected output changed goes hunting their editor and their version-control settings, which is the same wasted search the third rule exists to stop.

## The third rule, and what it is not about

Not encoding at all. A text-mode write turns a line feed into a carriage return pair, version control reports the tree clean against a blob that has neither, and a validator asked about the same content can answer differently — so a harness can measure a tree that its own commit does not contain.

Its warrant is narrower than it first looks and is worth stating narrowly: a validator flipping on line endings usually needs a conjunction, some other fragility that the changed bytes expose. Preventive against a mutation seat that introduces one — which is what mutation testing does to prose — rather than a response to a defect already firing.

## The exemption that has to stay true

Docstrings are exempt from the first rule, because prose read as prose can carry any character its house style likes. That exemption holds only while a docstring stays prose. Handing one to an argument parser as help text — as a description or an epilog — makes it output, and the exemption's premise is then false. Ban the construction rather than reasoning about whether the stream happens to be set up: the ban keeps the exemption honest, which is a warrant that survives changes to how streams are configured.
