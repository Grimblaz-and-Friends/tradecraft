**Load this when writing a script that prints, or that writes a file something will later compare, restore or measure.** A session revising prose does not need it.

Text mode is the substrate's sharpest edge, and it takes three rules because it has three surfaces. A text stream encodes to the platform's locale codepage and translates newlines, silently, whichever way the obvious call is written — cp1252 on Windows, *including when the destination is a pipe*, which is what a CI log, an agent harness and a captured command all are. So the failure fires precisely where the output is machine-read.

## The three rules

- **Machine-read output stays ASCII.** No non-ASCII character in a string constant that is not a docstring.
- **A stream is set to UTF-8 with LF endings before anything is written to it.** First statement of the entry point, and the ordering is not incidental: a call after argument parsing is a call that `--help` has already outrun. **It is two properties, and the second is the one that gets dropped** — the encoding is UTF-8, *and* the platform's newline translation is suppressed. The obvious hand-rolled call sets the encoding and leaves the translation in place, which satisfies the sentence and not the rule, so a reader with no helper within reach still owes both halves and not the easy one. **The two properties are the rule; a helper is only how a practice discharges them.** Where this practice's own `winio.utf8_stdio()` is within reach — a script inside this tree, resolving `lib/` against its own directory — reach for it rather than hand-rolling, and neither redefine nor shadow the name: a local no-op with the right name satisfies a call site while setting nothing up. **Outside this tree it is not within reach, and writing both properties yourself is compliance rather than a shortfall** — an installed plugin's copy sits at a version-stamped path that stops resolving at the next release [D-156], so there is no import to reach for. A guard that reads the import binding is a proxy for this and never a substitute: it establishes that a name arrived by an import, not where from and not that what runs sets both.
- **A file that will later be compared, restored or measured is written as bytes** — and **compared line endings aside**. Two questions, two answers: the write is what keeps one tree's bytes the same on every platform, while the comparison has to survive a working copy some other tool rewrote in text mode. A comparison reading raw bytes calls that rewrite a defect, which is the third section below.

## Why the first two are not a choice

They look like alternatives and are not, and mistaking them for a choice is how this bites twice.

A rule about characters can be **guarded exactly**, because "is this byte ASCII" is a fact about the source. But it reaches only what you write, and a guard for it reads **string literals** — so it flags a filename or a regex source alongside a message, and it cannot see a character built at runtime by `chr()`, a format call, or a `__str__`. State that bound where you state the rule: a guard whose message claims to know what reaches a stream is claiming something it never computed, and a session that believes it reasons about the wrong thing.

A stream set to UTF-8 covers what you were **handed** — a path from version control, a filename a consumer chose, a subprocess's stderr — which no literal check can reach. That half fails hardest exactly where it matters most: outside the code page it does not garble, it *raises*, killing the report before the offending name prints, so the message naming the problem is the message that goes missing.

**Guard the second at the call site, not by tracing reachability.** "Did this helper get called on this path" is undecidable from a syntax tree, and that objection is why a helper is sometimes rejected outright. It is the wrong question. The first statement of the entry point is a **position**, and a position is exact. Check the import binding too, for the reason the second rule gives — and state its bound where you state the check: an import establishes that a name arrived by one, not where from and not that the call resolves to it, so a shadowing definition or a same-named helper from elsewhere passes.

## What setting the stream also does

**It pins the line ending as well as the encoding, and that is a decision rather than a side effect.** A text stream's platform default translates a line feed on the way out; suppressing that translation means every caller now emits the same bytes on every platform — which is what a consumer comparing, diffing or hashing a captured stream needs.

Say so where you state the rule. Leave it unsaid and whoever notices their redirected output changed goes hunting their editor and their version-control settings, which is the same wasted search the third rule exists to stop.

## The third rule, and what it is not about

Not encoding at all — and it has now fired, which is where the rule's two halves come from. A guard compared two working-tree files byte for byte and reported every one of them out of step, on a tree version control called clean and a commit whose bytes were untouched — because the harness that created the checkout had rewritten one side in text mode. No conjunction was needed and no other fragility was exposed; reading the comparison as bytes was the whole defect.

So state the two halves apart. **Write as bytes**, always: a text-mode write turns a line feed into a carriage return pair, version control reports the tree clean against a blob that has neither, and a validator asked about the same content can answer differently — so a harness can measure a tree its own commit does not contain. **Compare line endings aside**, wherever version control normalises them on the way in: a difference that cannot survive into a commit is not drift, and treating it as drift reddens a lawful tree. The repair belongs on the comparison; leave the write exact, so the command that regenerates the file still restores the canonical bytes.

## The exemption that has to stay true

Docstrings are exempt from the first rule, because prose read as prose can carry any character its house style likes. That exemption holds only while a docstring stays prose. Handing one to an argument parser as help text — as a description or an epilog — makes it output, and the exemption's premise is then false. Ban the construction rather than reasoning about whether the stream happens to be set up: the ban keeps the exemption honest, which is a warrant that survives changes to how streams are configured.
