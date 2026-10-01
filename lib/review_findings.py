"""Classify live review-body findings and their individual conversation answers.

Network-free: review credit and inline disposition policy belong to the caller.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Collection
import re
from typing import Callable
import unicodedata


SUBMITTED = frozenset({"COMMENTED", "APPROVED", "CHANGES_REQUESTED", "DISMISSED"})
FAMILIES = {
    "github-actions[bot]": "tradecraft-review-finding:v1:",
    "coderabbitai[bot]": "cr-comment:v1:",
}
IDENTITY = re.compile(
    r"(?:tradecraft-review-finding:v1:[1-9][0-9]*:[1-9][0-9]*"
    r"|cr-comment:v1:[A-Za-z0-9_-]+)\Z"
)
REVIEW_LINK = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/"
    r"([1-9][0-9]*)#pullrequestreview-([1-9][0-9]*)(?![A-Za-z0-9_/#?=-])"
)
MARKDOWN_LINK = re.compile(r"\[([^\]\n]+)\]\((https://github\.com/[^\s)]+)\)")


def author(record: dict) -> str:
    return str((record.get("user") or {}).get("login") or "").lower()


def review_url(repo: str, number: int, review: dict) -> str:
    return f"https://github.com/{repo}/pull/{number}#pullrequestreview-{review['id']}"


def live_markup(body: str) -> str:
    """Remove code examples, preserving offsets for section accounting."""
    lines = []
    fence = None
    for line in body.splitlines(keepends=True):
        unquoted = re.sub(r"^\s*(?:>\s*)*", "", line)
        marker = re.match(r"(`{3,}|~{3,})", unquoted)
        if fence:
            lines.append(re.sub(r"[^\r\n]", " ", line))
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = None
        elif marker:
            fence = marker[1]
            lines.append(re.sub(r"[^\r\n]", " ", line))
        else:
            lines.append(re.sub(r"[^\r\n]", " ", line)
                         if re.match(r"^(?: {4}|\t)", line) else line)
    text = "".join(lines)
    paragraph_break = r"\r?\n[ \t]*(?:>[ \t]*)*\r?\n"
    inline_code = rf"(?<!`)(`+)(?!`)(?:(?!{paragraph_break}).)*?(?<!`)\1(?!`)"
    for pattern in (r"<pre\b[^>]*>.*?</pre>", r"<code\b[^>]*>.*?</code>", inline_code):
        text = re.sub(pattern, lambda m: re.sub(r"[^\r\n]", " ", m[0]), text,
                      flags=re.S | re.I)
    return text


def identities(text: str, login: str) -> tuple[list[tuple[str, int]], bool]:
    family = FAMILIES.get(login)
    if family is None:
        return [], False
    found = []
    malformed = False
    pattern = r"<!--\s*" + re.escape(family) + r"[^\n<>]*(?:-->|$)"
    for match in re.finditer(pattern, text, re.M):
        value = match[0].removeprefix("<!--").removesuffix("-->").strip()
        if match[0].endswith("-->") and IDENTITY.fullmatch(value):
            found.append((value, match.start()))
        else:
            malformed = True
    return found, malformed


@dataclass
class BodyFinding:
    reviewer: str
    identity: str
    sources: list[dict] = field(default_factory=list)
    answered: bool = False


@dataclass
class UnidentifiedReview:
    review: dict
    reasons: list[str]
    answered: bool = False


@dataclass
class Classification:
    findings: list[BodyFinding]
    unidentified_reviews: list[UnidentifiedReview]
    ignored_authors: list[str]

    @property
    def missing_findings(self) -> list[BodyFinding]:
        return [item for item in self.findings if not item.answered]

    @property
    def missing_reviews(self) -> list[UnidentifiedReview]:
        return [item for item in self.unidentified_reviews if not item.answered]


@dataclass
class Section:
    label: str
    count: int | None
    start: int
    end: int
    content_start: int
    malformed: bool = False
    depth: int = 0
    details_section: bool = False


def _number(text: str) -> int | None:
    try:
        return int(text)
    except ValueError:
        return None


def _section(label: str, start: int, end: int, content_start: int,
             login: str) -> Section | None:
    label = re.sub(r"<[^>]*>", "", label)
    label = re.sub(r"(?m)^[ \t]*(?:>[ \t]*)*", "", label)
    label = re.sub(r"\s+", " ", label).strip()
    if login == "coderabbitai[bot]":
        offset = 0
        while offset < len(label) and (
                unicodedata.category(label[offset])[0] in {"S", "M"}
                or label[offset] == chr(0x200D) or label[offset].isspace()):
            offset += 1
        label = label[offset:]
        if ("findings" in label.lower()
                or not re.fullmatch(r".+ comments \([0-9]+\)", label, re.I)):
            return None
    elif login == "github-actions[bot]" or not label.lower().startswith("findings"):
        return None
    count = re.search(r"\(([0-9]+)\)\s*$", label)
    value = _number(count[1]) if count else None
    return Section(label, value, start, end, content_start,
                   "(" in label and (count is None or value is None))


def _sections(text: str, login: str) -> list[Section]:
    """Apply producer title shapes and boundaries at their details nesting depth."""
    sections = []
    stack = []
    details_ranges = []
    for tag in re.finditer(r"<details\b[^>]*>|</details>|<summary\b[^>]*>.*?</summary>",
                           text, re.S | re.I):
        lowered = tag[0].lower()
        if lowered.startswith("<details"):
            stack.append((tag.start(), []))
        elif lowered.startswith("</details"):
            if stack:
                start, pending = stack.pop()
                details_ranges.append((start, tag.start()))
                for section in pending:
                    section.end = tag.start()
                    sections.append(section)
        elif stack:
            label = re.sub(r"^<summary\b[^>]*>|</summary>$", "", tag[0], flags=re.I)
            section = _section(label, stack[-1][0], len(text), tag.end(), login)
            if section:
                section.depth = len(stack) - 1
                section.details_section = True
                stack[-1][1].append(section)
    for start, pending in stack:
        details_ranges.append((start, len(text)))
        for section in pending:
            section.malformed = True
            sections.append(section)

    def depth_at(position: int) -> int:
        return sum(start < position < end for start, end in details_ranges)

    header_pattern = (
        r"(?m)^[ \t]*(?:>[ \t]*)*\*\*((?:(?!\*\*)[\s\S])+?)\*\*[ \t]*\r?$"
        if login == "coderabbitai[bot]" else
        r"(?m)^[ \t]*(?:>[ \t]*)*#{1,6}[ \t]+([^\r\n]+)\r?$"
    )
    for header in re.finditer(header_pattern, text):
        section = _section(header[1], header.start(), len(text), header.end(), login)
        if section:
            section.depth = depth_at(header.start())
            sections.append(section)
    sections.sort(key=lambda item: item.start)
    dividers = [(match.start(), depth_at(match.start())) for match in re.finditer(
        r"(?m)^[ \t]*(?:>[ \t]*)*---[ \t]*\r?$", text,
    )]
    declared = []
    for section in sections:
        content_depth = section.depth + int(section.details_section)
        boundaries = [pos for pos, depth in dividers
                      if pos >= section.content_start and depth == content_depth]
        section.end = min([section.end, *boundaries])
        if any(parent.content_start <= section.start < parent.end
               and section.depth > parent.depth for parent in declared):
            continue  # Nested candidate titles belong to the enclosing finding content.
        for parent in declared:
            if section.start > parent.start:
                parent.end = min(parent.end, section.start)
        declared.append(section)
    return declared


def _section_complete(section: Section, text: str, markers: list[tuple[str, int]],
                      inline: set[str] | None = None) -> bool:
    members = {identity for identity, pos in markers if section.start <= pos < section.end}
    if section.malformed:
        return False
    content = text[section.content_start:section.end]
    plain = re.sub(r"<[^>]*>|(?m:^\s*>\s*)", "", content).strip().lower().rstrip(".")
    empty = not plain or plain in {"none", "no findings", "no findings were found"}
    if empty:
        if section.count is not None:
            return len(members | (inline or set())) == section.count
        return not members and not inline
    if section.count is not None and len(members) != section.count:
        return False
    # Non-empty body content must identify its own entries; inline roots cannot pay for it.
    entries = []
    depth = 0
    for entry in re.finditer(
        r"(?m)^\s*(?:>\s*)*(?:[-*+]\s+|[0-9]+[.)]\s+|#{2,6}\s+|\*\*P[0-3]\b)"
        r"|<details\b[^>]*>|</details>", content, re.I
    ):
        if entry[0].lower().startswith("</details"):
            depth = max(depth - 1, 0)
        elif entry[0].lower().startswith("<details"):
            if depth == 0:
                entries.append(entry)
            depth += 1
        elif depth == 0:
            entries.append(entry)
    if not entries:
        return inline is None and len(members) == 1
    credited = set()
    for index, entry in enumerate(entries):
        start = section.content_start + entry.start()
        end = (section.content_start + entries[index + 1].start()
               if index + 1 < len(entries) else section.end)
        entry_members = {identity for identity, pos in markers if start <= pos < end}
        # CodeRabbit may group several identified entries beneath one file details block.
        file_group = inline is None and entry[0].lower().startswith("<details")
        if (not entry_members or (not file_group and len(entry_members) != 1)
                or credited & entry_members):
            return False
        credited.update(entry_members)
    return credited == members


def _accounting(text: str, login: str, roots: list[dict],
                markers: list[tuple[str, int]], malformed: bool) -> list[str]:
    reasons = ["malformed finding identity"] if malformed else []
    inline = set()
    for root in roots:
        root_markers, bad = identities(live_markup(str(root.get("body") or "")), login)
        if bad or len({value for value, _pos in root_markers}) > 1:
            reasons.append("malformed or conflicting inline identities")
        inline.update(value for value, _pos in root_markers)
        if not root_markers:
            inline.add(f"inline:{root['id']}")
    if login == "github-actions[bot]":
        declarations = re.findall(r"(?m)^\s*([0-9]+) validated finding\(s\)\.\s*$", text)
        count = len(inline | {value for value, _pos in markers})
        if len(declarations) > 1 or (declarations and _number(declarations[0]) != count):
            reasons.append("declared total does not account for inline and body findings")
        elif re.search(r"(?m)^\s*\S+ validated finding\(s\)", text) and not declarations:
            reasons.append("malformed findings declaration")
        attempt = re.search(r"<!-- connected-review-attempt:([1-9][0-9]*) -->\s*\Z", text)
        if attempt and any(value.split(":")[2] != attempt[1] for value, _pos in markers):
            reasons.append("body finding identity conflicts with review attempt")
    elif login == "coderabbitai[bot]":
        declarations = re.findall(
            r"(?im)^\s*(?:\*\*)?Actionable comments posted:\s*([0-9]+)(?:\*\*)?\s*$", text
        )
        if (len(declarations) > 1
                or (declarations and _number(declarations[0]) != len(inline))):
            reasons.append("actionable declaration does not account for inline findings")
        elif re.search(r"(?im)^[ \t]*(?:\*\*)?Actionable comments posted:", text) and not declarations:
            reasons.append("malformed actionable declaration")
    else:
        declarations = re.findall(
            r"(?im)^\s*(?:\*\*)?(?:Findings:\s*([0-9]+)|([0-9]+) findings?\.?)"
            r"(?:\*\*)?\s*$", text
        )
        declarations = [left or right for left, right in declarations]
        if (len(declarations) > 1 or (declarations and _number(declarations[0])
                                     != len(inline | {value for value, _pos in markers}))):
            reasons.append("declared total does not account for inline and body findings")
        elif re.search(r"(?im)^\s*(?:\*\*)?Findings:", text) and not declarations:
            reasons.append("malformed findings declaration")
    sections = _sections(text, login)
    scoped_markers = {id(section): [] for section in sections}
    for marker in markers:
        containing = [section for section in sections
                      if section.content_start <= marker[1] < section.end]
        if containing:
            innermost = max(containing, key=lambda section: (section.start, -section.end))
            scoped_markers[id(innermost)].append(marker)
    seen = set()
    for section in sections:
        label = re.sub(r"\s*\([^)]*\)\s*$", "", section.label).lower()
        total_inline = inline if login != "coderabbitai[bot]" else None
        if label in seen or not _section_complete(
                section, text, scoped_markers[id(section)], total_inline):
            reasons.append(f"unaccounted findings section: {section.label}")
        seen.add(label)
    return sorted(set(reasons))


def _bare_disposition(body: str, inline_disposition: Callable[[str], bool]) -> bool:
    first = next((line.strip() for line in body.splitlines() if line.strip()), "")
    if not re.match(r"(?:fixed|yours|declined|duplicate|lapsed)\b", first, re.I):
        return False
    if not inline_disposition(body):
        return False
    # Continuations keep their existing meaning; a delimiter alone is no answer.
    continuation = MARKDOWN_LINK.sub(
        lambda match: "" if REVIEW_LINK.fullmatch(match[2]) else match[0], first
    )
    normalized = continuation.lower().replace(chr(0x2014), "-")
    if normalized.startswith(("declined -", "lapsed -")):
        return bool(normalized.partition("-")[2].strip(" ;:.,-"))
    if normalized.startswith("duplicate of "):
        return bool(normalized[len("duplicate of "):].strip(" ;:.,-"))
    return True


def classify(repo: str, number: int, reviews: list[dict], inline_comments: list[dict],
             conversation_comments: list[dict], connected_reviewers: Collection[str],
             marker_producers: Collection[str], inline_disposition: Callable[[str], bool]
             ) -> Classification:
    """Keep per-review accounting and per-reviewer/PR answer obligations separate."""
    def belongs(row: dict) -> bool:
        url = row.get("html_url")
        if not url:
            return True  # The caller fetched these rows from this PR's endpoint.
        return bool(re.fullmatch(
            r"https://github\.com/" + re.escape(repo) + r"/pull/" + str(number)
            + r"#discussion_r[1-9][0-9]*", str(url), re.I
        ))

    roots = [row for row in inline_comments if isinstance(row.get("id"), int)
             and row.get("in_reply_to_id") is None and author(row) in connected_reviewers
             and belongs(row)]
    answered_identities = set()
    for root in roots:
        if any(reply.get("in_reply_to_id") == root["id"]
               and author(reply) in marker_producers
               and belongs(reply)
               and inline_disposition(str(reply.get("body") or ""))
               for reply in inline_comments):
            markers, bad = identities(live_markup(str(root.get("body") or "")), author(root))
            if not bad and len({value for value, _pos in markers}) == 1:
                answered_identities.add((author(root), markers[0][0]))
    findings = {}
    unidentified = []
    for review in reviews:
        login = author(review)
        if (login not in connected_reviewers or not isinstance(review.get("id"), int)
                or str(review.get("state") or "").upper() not in SUBMITTED):
            continue
        text = live_markup(str(review.get("body") or ""))
        markers, malformed = identities(text, login)
        own_roots = [row for row in roots if row.get("pull_request_review_id") == review["id"]
                     and author(row) == login]
        reasons = _accounting(text, login, own_roots, markers, malformed)
        if reasons:
            unidentified.append(UnidentifiedReview(review, reasons))
        for identity, _pos in markers:
            key = (login, identity)
            finding = findings.setdefault(key, BodyFinding(login, identity))
            if review not in finding.sources:
                finding.sources.append(review)
            finding.answered = key in answered_identities
    # Source membership stays fixed while answers discharge obligations.
    source_ids = {source["id"] for finding in findings.values() for source in finding.sources}
    source_ids.update(item.review["id"] for item in unidentified)
    ignored = set()
    for comment in conversation_comments:
        body = str(comment.get("body") or "")
        if not _bare_disposition(body, inline_disposition):
            continue
        text = live_markup(body)
        links = [link for link in REVIEW_LINK.finditer(text)
                 if link[1].lower() == repo.lower() and int(link[2]) == number
                 and int(link[3]) in source_ids]
        # Only obligation-source links are targets; other links and prose are evidence.
        if len(links) != 1:
            continue
        link = links[0]
        review_id = int(link[3])
        label = next((label for label, url in MARKDOWN_LINK.findall(text) if url == link[0]), None)
        targets = []
        if label is not None and IDENTITY.fullmatch(label):
            targets = [finding for finding in findings.values()
                       if finding.identity == label
                       and any(source["id"] == review_id for source in finding.sources)]
        elif label is not None:
            targets = [item for item in unidentified if item.review["id"] == review_id]
        if not targets:
            continue
        if author(comment) not in marker_producers:
            ignored.add(author(comment))
            continue
        for target in targets:
            target.answered = True
    return Classification(list(findings.values()), unidentified, sorted(ignored))
