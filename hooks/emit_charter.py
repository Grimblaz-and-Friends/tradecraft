#!/usr/bin/env python3
"""Emit the charter on stdout, for the SessionStart hook.

`cat` was the first shape of this hook and it failed three ways that only a
Windows adopter would ever see. Under `powershell.exe` 5.1 -- the interpreter
Claude Code falls back to when Git Bash is absent, which is the default Windows
state -- `cat` is an alias for `Get-Content`, which reads a BOM-less UTF-8 file
as ANSI: every em dash and curly quote in the charter arrived corrupted. Its
`-Path` is wildcard-interpreted, so a `[` anywhere in the plugin cache path made
the read fail. And it failed at **exit 0 with empty stdout**, which the runtime
contract ("exit 0: stdout is shown to the model") makes indistinguishable from a
hook that deliberately emitted nothing.

This script is the same three fixes: decode explicitly, open by literal path,
and exit non-zero with a reason on stderr when there is nothing to emit. It
prints nothing but the charter, so plain stdout remains the delivery form.

Exit codes: 0 with the charter on stdout; 1 with a reason on stderr otherwise.
"""
from __future__ import annotations

import sys
from pathlib import Path

# lib/ ships beside this hook, so the import resolves in a source checkout
# and an installed plugin alike -- against this file's own directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from winio import utf8_stdio  # noqa: E402

CHARTER = Path(__file__).resolve().parent.parent / "skills" / "charter" / "SKILL.md"


def _body(text: str) -> str:
    """The charter without its frontmatter.

    The charter is a skill cell, so it carries a name and description for the
    runtime's skill index. Those are addressed to the index, not to a session
    reading the rules, so the hook emits what follows them. One file, one owner,
    two doors: the runtime loads the cell when a session asks for it by name,
    and this hook reads out its body at session start for sessions that never
    think to ask.
    """
    if not text.startswith("---"):
        return text
    end = text.find(chr(10) + "---", 3)
    if end == -1:
        return text
    return text[end + 4:].lstrip(chr(10))


def main() -> int:
    utf8_stdio(newline="\n")
    try:
        text = _body(CHARTER.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"charter-not-emitted: no file at {CHARTER}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as exc:
        print(f"charter-not-emitted: {CHARTER} is not valid UTF-8: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"charter-not-emitted: {CHARTER}: {exc}", file=sys.stderr)
        return 1
    if not text.strip():
        print(f"charter-not-emitted: {CHARTER} is empty", file=sys.stderr)
        return 1

    # The runtime reads this stream and compares it byte for byte, not a
    # console -- so this is the one caller that pins the newline rather
    # than leaving the platform translation alone. utf8_stdio ran first,
    # at the top of main(); this branch is only about a stream that had
    # no reconfigure for it to use.
    out = sys.stdout
    if hasattr(out, "reconfigure"):
        out.write(text)
    else:
        sys.stdout.buffer.write(text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
