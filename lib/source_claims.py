"""Shared source-level marker classification for entrances and cold draft resolution."""
from __future__ import annotations

from dataclasses import dataclass
import re


DISPOSITIONS = (
    "fixed", "fixed - nothing else found it", "fixed in #", "yours - in the release report",
    "declined -", "duplicate of ", "lapsed -",
)

MARKER = re.compile(r"<!--\s*tradecraft:([a-z-]+):v1(?:\s+([^>]*?))?\s*-->", re.I)

ATTRIBUTE = re.compile(r"([a-z_][a-z_0-9]*)=([^\s]+)", re.I)

SETTLEMENT_ROUTES = frozenset({"would", "cap", "discharge", "unobtainable"})

TRAVELS_WITH = {
    "implementing-pr": frozenset({"builder-session"}),
}

POSITIVE_INTEGER = re.compile(r"[1-9][0-9]*\Z")

@dataclass(frozen=True)
class Marker:
    name: str
    attributes: dict[str, str]
    body: str
    author: str
    surface: str = "unknown"
    source_id: str | None = None
    timestamp: str | None = None
    url: str | None = None
    raw_attributes: str = ""
    source_order: int = 0
    occurrence_order: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "attributes": self.attributes,
            "surface": self.surface,
            "source_id": self.source_id,
            "timestamp": self.timestamp,
            "url": self.url,
        }

@dataclass(frozen=True)
class SourceClassification:
    claims: tuple[Marker, ...]
    quotations: tuple[Marker, ...]

def _mask_markdown_quotations(text: str) -> str:
    """Blank Markdown quotation regions while retaining offsets and newlines."""
    masked = list(text)
    offset = 0
    fence: tuple[str, int] | None = None
    for line_with_end in text.splitlines(keepends=True):
        line = line_with_end.rstrip("\r\n")
        quoted = False
        fence_match = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence is not None:
            quoted = True
            closing = re.match(rf"^ {{0,3}}{re.escape(fence[0])}{{{fence[1]},}}\s*$", line)
            if closing is not None:
                fence = None
        elif fence_match is not None:
            token = fence_match.group(1)
            fence = (token[0], len(token))
            quoted = True
        elif re.match(r"^ {0,3}>", line) is not None or re.match(r"^(?: {4}|\t)", line):
            quoted = True
        if quoted:
            for index in range(offset, offset + len(line)):
                masked[index] = " "
        offset += len(line_with_end)
    candidate = "".join(masked)
    opener_pattern = re.compile(r"`+")
    cursor = 0
    while cursor < len(candidate):
        opener = opener_pattern.search(candidate, cursor)
        if opener is None:
            break
        start = opener.start()
        ticks = opener.group(0)
        closing = re.compile(
            rf"(?<!`){re.escape(ticks)}(?!`)"
        ).search(
            candidate, start + len(ticks)
        )
        if closing is None:
            cursor = start + len(ticks)
            continue
        close = closing.start()
        for index in range(start, close + len(ticks)):
            if masked[index] not in "\r\n":
                masked[index] = " "
        cursor = close + len(ticks)
    return "".join(masked)

def _first_content_span(text: str) -> tuple[int, int] | None:
    offset = 0
    for line_with_end in text.splitlines(keepends=True):
        line = line_with_end.rstrip("\r\n")
        if line.strip():
            leading = len(line) - len(line.lstrip())
            trailing = len(line.rstrip())
            return offset + leading, offset + trailing
        offset += len(line_with_end)
    if text.strip():
        leading = len(text) - len(text.lstrip())
        return leading, len(text.rstrip())
    return None

def _first_content_line(text: str) -> str:
    return next((line for line in text.splitlines() if line.strip()), "")

def _block_quoted_line(line: str) -> bool:
    return bool(
        re.match(r"^ {0,3}>", line)
        or re.match(r"^(?: {4}|\t)", line)
        or re.match(r"^ {0,3}(?:`{3,}|~{3,})", line)
    )

def _marker_from_match(match: re.Match[str], text: str, author: str, surface: str,
                       source_id: str | None, timestamp: str | None, url: str | None,
                       source_order: int, occurrence_order: int) -> Marker:
    attributes = {
        key.lower(): value for key, value in ATTRIBUTE.findall(match.group(2) or "")
    }
    return Marker(
        match.group(1).lower(), attributes, text, author, surface,
        source_id, timestamp, url, match.group(2) or "", source_order, occurrence_order,
    )

def _classify_sources(sources: list[tuple]) -> SourceClassification:
    claims: list[Marker] = []
    quotations: list[Marker] = []
    for source_order, source in enumerate(sources):
        text, author = source[:2]
        surface = source[2] if len(source) > 2 else "unknown"
        source_id = source[3] if len(source) > 3 else None
        timestamp = source[4] if len(source) > 4 else None
        url = source[5] if len(source) > 5 else None
        reviewer_reply = bool(source[6]) if len(source) > 6 else False
        masked = _mask_markdown_quotations(text)
        unquoted_spans = {(match.start(), match.end()) for match in MARKER.finditer(masked)}
        occurrences: list[tuple[re.Match[str], Marker]] = []
        for occurrence_order, match in enumerate(MARKER.finditer(text)):
            occurrences.append((match, _marker_from_match(
                match, text, author, surface, source_id, timestamp, url,
                source_order, occurrence_order,
            )))
        first_span = _first_content_span(text)
        opener_index = None
        if first_span is not None:
            for index, (match, _marker) in enumerate(occurrences):
                if (match.start(), match.end()) == first_span and first_span in unquoted_spans:
                    opener_index = index
                    break
        companion_names: frozenset[str] = frozenset()
        asserted_indexes: set[int] = set()
        if opener_index is not None:
            opener = occurrences[opener_index][1]
            if opener.name != "connected-reviewer":
                asserted_indexes.add(opener_index)
                if opener.name == "artifact" and opener.attributes.get("status") == "settled":
                    companion_names = frozenset({"cold-verdict"})
                else:
                    companion_names = TRAVELS_WITH.get(opener.name, frozenset())
        elif reviewer_reply and first_span is not None:
            first_line = _first_content_line(text)
            if not _block_quoted_line(first_line) and _disposition(first_line):
                companion_names = frozenset({"connected-reviewer"})
        for index, (match, marker) in enumerate(occurrences):
            if index in asserted_indexes:
                claims.append(marker)
            elif (match.start(), match.end()) in unquoted_spans and marker.name in companion_names:
                claims.append(marker)
            else:
                quotations.append(marker)
    return SourceClassification(tuple(claims), tuple(quotations))

def markers(sources: list[tuple]) -> list[Marker]:
    return list(_classify_sources(sources).claims)

def _strip_balanced_markdown_wrapper(value: str) -> str:
    stripped = value.strip()
    if not stripped or stripped[0] not in "`*_":
        return stripped
    marker = stripped[0]
    opening = len(stripped) - len(stripped.lstrip(marker))
    closing = len(stripped) - len(stripped.rstrip(marker))
    wrapper = marker * opening
    if wrapper not in {"`", "*", "**", "_", "__"} or closing != opening:
        return stripped
    return stripped[opening:-closing].strip()


def _strip_opening_word_formatting(value: str) -> str:
    stripped = _strip_balanced_markdown_wrapper(value)
    for wrapper in ("**", "__", "*", "_", "`"):
        if not stripped.startswith(wrapper):
            continue
        close = stripped.find(wrapper, len(wrapper))
        if close < 0:
            continue
        word = stripped[len(wrapper):close]
        if re.fullmatch(r"[A-Za-z]+", word) is None:
            continue
        following = stripped[close + len(wrapper):]
        if following and (following[0].isalnum() or following[0] == "_"):
            continue
        return word + following
    return stripped

def _disposition(body: str) -> bool:
    first_line = next((line for line in body.splitlines() if line.strip()), "")
    normalized = (
        _strip_opening_word_formatting(first_line)
        .lower().replace(chr(0x2014), "-").strip()
    )
    for prefix in DISPOSITIONS:
        if not normalized.startswith(prefix):
            continue
        if not prefix[-1].isalnum() or len(normalized) == len(prefix):
            return True
        following = normalized[len(prefix)]
        if not (following.isalnum() or following == "_"):
            return True
    return False


def attribute_error(marker: Marker, contract: dict[str, object] | None) -> str | None:
    if contract is None:
        return None
    tokens = marker.raw_attributes.split()
    parsed: dict[str, str] = {}
    for token in tokens:
        match = ATTRIBUTE.fullmatch(token)
        if match is None:
            return "malformed marker attribute"
        key = match.group(1).lower()
        if key in parsed:
            return f"duplicate marker attribute: {key}"
        parsed[key] = match.group(2)
    required = contract["required"]
    optional = contract["optional"]
    missing = sorted(required - parsed.keys())
    unknown = sorted(parsed.keys() - required - optional)
    if missing:
        return "missing marker attributes: " + ",".join(missing)
    if unknown:
        return "unknown marker attributes: " + ",".join(unknown)
    if parsed != marker.attributes:
        return "marker attributes could not be parsed exactly"
    return None

