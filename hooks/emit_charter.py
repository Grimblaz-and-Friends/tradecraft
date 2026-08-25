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

    # The runtime reads this stream, not a console, so the console code page is
    # not the encoding that matters -- name it rather than inherit it.
    out = sys.stdout
    if hasattr(out, "reconfigure"):
        out.reconfigure(encoding="utf-8", newline="\n")
        out.write(text)
    else:
        sys.stdout.buffer.write(text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
