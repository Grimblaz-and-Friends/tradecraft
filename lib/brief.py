#!/usr/bin/env python3
"""Check the mechanically decidable elements of an implementation brief."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

from winio import utf8_stdio

LANES = (
    ("ordinary", "connected"),
    ("ordinary", "mechanical"),
    ("elevated", "routine-panel"),
    ("critical", "substantial-panel"),
)
ELEMENTS = (
    "Shape",
    "Readers",
    "decision block",
    "Not this",
    "Review risk / Review lane pair",
)


def review_lane(text: str) -> tuple[str, str] | None:
    """Return the single lawful risk/lane pair, or None."""
    risks = re.findall(r"(?im)^Review risk:\s*(ordinary|elevated|critical)\s*$", text)
    lanes = re.findall(
        r"(?im)^Review lane:\s*(connected|mechanical|routine-panel|substantial-panel)\s*$",
        text,
    )
    if len(risks) != 1 or len(lanes) != 1:
        return None
    pair = risks[0].lower(), lanes[0].lower()
    return pair if pair in LANES else None


def _draft_review_lane(text: str) -> tuple[str, str] | None:
    risk_rows = re.findall(r"(?im)^Review risk:[^\r\n]*\r?$", text)
    lane_rows = re.findall(r"(?im)^Review lane:[^\r\n]*\r?$", text)
    if len(risk_rows) != 1 or len(lane_rows) != 1:
        return None
    return review_lane(text)


def _without_fenced_regions(text: str) -> str:
    outside: list[str] = []
    fence: tuple[str, int] | None = None
    for line in text.splitlines():
        if fence is not None:
            character, width = fence
            closing = rf"^[ \t]{{0,3}}{re.escape(character)}{{{width},}}[ \t]*$"
            if re.fullmatch(closing, line):
                fence = None
            outside.append("")
            continue

        opening = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})", line)
        if opening is None:
            outside.append(line)
            continue
        token = opening.group(1)
        fence = token[0], len(token)
        outside.append("")
    return "\n".join(outside)


def _has_label(text: str, label: str) -> bool:
    escaped = re.escape(label)
    heading = re.compile(rf"^#{{1,6}}\s+{escaped}(?:[.:])?\s*#*\s*$", re.I)
    inline = re.compile(
        rf"^(?:(?:\*\*|__){escaped}[.:](?:\*\*|__)"
        rf"|(?:\*\*|__){escaped}(?:\*\*|__)[.:]"
        rf"|{escaped}[.:])(?:\s+.*)?$",
        re.I,
    )
    return any(heading.fullmatch(line.strip()) or inline.fullmatch(line.strip())
               for line in text.splitlines())


def _pipe_decision_header(line: str) -> bool:
    cells = {
        re.sub(r"[*_`]", "", cell).strip().casefold() for cell in _pipe_cells(line)
    }
    return {"decision", "why"}.issubset(cells)


def _pipe_cells(line: str) -> tuple[str, ...]:
    if "|" not in line:
        return ()
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return tuple(cell.strip() for cell in stripped.split("|"))


def _has_pipe_decision_table(lines: list[str], index: int) -> bool:
    header = _pipe_cells(lines[index])
    if not _pipe_decision_header(lines[index]) or index + 2 >= len(lines):
        return False
    delimiter = _pipe_cells(lines[index + 1])
    if len(delimiter) != len(header) or not all(
        re.fullmatch(r":?-{3,}:?", cell) for cell in delimiter
    ):
        return False
    data = _pipe_cells(lines[index + 2])
    return bool(data) and any(data)


ROW_HEADING = re.compile(r"^(#{1,6})\s+Row\s+([1-9][0-9]*)(?:\s+.*)?$", re.I)
BOLD_ROW = re.compile(r"^\*\*(?:R([1-9][0-9]*)|([1-9][0-9]*))\.\s+\S.*?\*\*(?:\s|$)", re.I)
HEADING = re.compile(r"^(#{1,6})\s")


def _has_decision_block(text: str) -> bool:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if (_has_pipe_decision_table(lines, index) or ROW_HEADING.fullmatch(stripped)
                or BOLD_ROW.match(stripped)):
            return True
    return False


def _row_text(lines: list[str]) -> str:
    while lines and not lines[-1].strip():
        lines = lines[:-1]
    return "\n".join(lines)


def rows(text: str) -> list[tuple[int, str]]:
    """Each decision row's number and whole text, in order, from the forms `_has_decision_block` recognises.

    Rows are found outside fenced regions, but a row's text is the brief's own lines, so a fence
    inside a row stays in it. A pipe table's rows are numbered in order from 1 and read as their
    cells joined with ` | `. Design: lib/DESIGN.md#the-builder-route
    """
    original = text.splitlines()
    # The fence-free copy keeps one line per line, so an index into it is an index into the brief.
    outside = _without_fenced_regions(text).splitlines()
    outside += [""] * (len(original) - len(outside))
    found: list[tuple[int, str]] = []
    table_rows = 0
    index = 0
    while index < len(outside):
        stripped = outside[index].strip()
        heading, bold = ROW_HEADING.fullmatch(stripped), BOLD_ROW.match(stripped)
        if _has_pipe_decision_table(outside, index):
            index += 2  # The header and its delimiter carry no row.
            while index < len(outside) and _pipe_cells(outside[index]) and any(_pipe_cells(outside[index])):
                table_rows += 1
                found.append((table_rows, " | ".join(_pipe_cells(outside[index]))))
                index += 1
            continue
        if heading:
            level, end = len(heading.group(1)), index + 1
            # A heading row runs to the next heading of its own level or higher.
            while end < len(outside) and not (
                    (match := HEADING.match(outside[end].strip())) and len(match.group(1)) <= level):
                end += 1
            found.append((int(heading.group(2)), _row_text(original[index:end])))
            index = end
            continue
        if bold:
            end = index + 1
            while end < len(outside) and not (BOLD_ROW.match(outside[end].strip())
                                              or _has_label(outside[end], "Not this")):
                end += 1
            found.append((int(bold.group(1) or bold.group(2)), _row_text(original[index:end])))
            index = end
            continue
        index += 1
    return found


def missing_elements(text: str) -> tuple[str, ...]:
    """Return absent or invalid elements in stable form order."""
    outside_fences = _without_fenced_regions(text)
    missing: list[str] = []
    if not _has_label(outside_fences, "Shape"):
        missing.append(ELEMENTS[0])
    if not _has_label(outside_fences, "Readers"):
        missing.append(ELEMENTS[1])
    if not _has_decision_block(outside_fences):
        missing.append(ELEMENTS[2])
    if not _has_label(outside_fences, "Not this"):
        missing.append(ELEMENTS[3])
    # The form permits this pair inside a fence. A quoted example can therefore satisfy
    # it once the four real elements exist; distinguishing quotation is content judgment.
    if _draft_review_lane(text) is None:
        missing.append(ELEMENTS[4])
    return tuple(missing)


def _display_path(path: Path) -> str:
    return str(path).encode("ascii", errors="backslashreplace").decode("ascii")


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        description="Check required implementation-brief elements without judging content."
    )
    cli.add_argument("--check", required=True, type=Path, metavar="FILE")
    return cli


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    args = parser().parse_args(argv)
    displayed = _display_path(args.check)
    try:
        text = args.check.read_text(encoding="utf-8")
    except UnicodeError:
        print(f"brief check: {displayed} is not valid UTF-8.", file=sys.stderr)
        return 1
    except OSError:
        print(f"brief check: could not read {displayed}.", file=sys.stderr)
        return 1

    missing = missing_elements(text)
    if missing:
        for element in missing:
            print(f"brief check: missing or invalid {element}.", file=sys.stderr)
        return 1

    print(
        "brief check: required elements present; content, reasons, and reader cells "
        "were not checked."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
