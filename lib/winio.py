"""Stream setup for the half of the encoding problem a lint cannot reach.

The practice's emitted-ASCII rule reads string *literals*, so it protects what
a repository writes. It cannot protect what a repository is handed: a path from
`git`, a filename a consumer chose, a subprocess's stderr. On Windows those
reach `print` through a stream encoded to the locale codepage, and the result
is one of two failures -- a mojibaked byte a UTF-8 reader cannot decode, or,
for anything outside cp1252, a `UnicodeEncodeError` that kills the report
mid-list so the offending path never prints at all.

The two halves are complementary and were once mistaken for alternatives. The
rule is exact about literals; this is exact about the stream. Neither reaches
the other's surface.

A guard on the call site is what keeps this honest -- reading where the call
sits rather than tracing what reaches a stream, so "did every script call
this" is answered exactly rather than approximately.
"""
from __future__ import annotations

import sys


def utf8_stdio(newline: str = "") -> None:
    """Make stdout and stderr carry UTF-8 with LF, whatever the platform default.

    Called first in `main()`, before any output and before argparse can exit.
    `errors="replace"` rather than strict: a guard that dies encoding its own
    failure message has converted a legible failure into a traceback, which is
    strictly worse than a substituted character.

    `newline=""` leaves the stream's own newline translation alone -- writing
    `\n` and getting `\r\n` harms no reader of a stream, and suppressing it
    here would change what every existing caller emits for no stated benefit.

    Idempotent, and safe where a stream has been replaced by something without
    `reconfigure` (pytest's capture, a redirect to `io.StringIO`).
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace", newline=newline)
        except (ValueError, OSError):
            # A detached or already-closed stream cannot be reconfigured, and
            # failing to set up output is not a reason to fail the run.
            pass
