"""Classify live review-body findings and their individual conversation answers.

Network-free: review credit and inline disposition policy belong to the caller.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Collection
import re
from typing import Callable


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
    return str((record.get("user") or {}).get("login") or "")


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
    for pattern in (r"<pre\b[^>]*>.*?</pre>", r"<code\b[^>]*>.*?</code>",
                    r"(?<!`)(`+)(?!`).*?(?<!`)\1(?!`)"):
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


def _number(text: str) -> int | None:
    try:
        return int(text)
    except ValueError:
        return None


def _section(label: str, start: int, end: int, content_start: int) -> Section | None:
    label = re.sub(r"<[^>]*>", "", label).strip(" *#>\r\n")
    if re.match(r"P[0-3]\b", label, re.I) or " - " in label or chr(0x2014) in label:
        return None
    if re.search(r"\bprompt\b|\bfix review comments\b", label, re.I):
        return None
    if not re.search(r"\b(?:comments|findings)(?:\s*\([^)]*\))?\s*$", label, re.I):
        return None
    count = re.search(r"\(([0-9]+)\)\s*$", label)
    value = _number(count[1]) if count else None
    return Section(label, value, start, end, content_start,
                   "(" in label and (count is None or value is None))


def _sections(text: str) -> list[Section]:
    """Structural declarations only: details summaries and Markdown headings."""
    sections = []
    stack = []
    for tag in re.finditer(r"<details\b[^>]*>|</details>|<summary\b[^>]*>.*?</summary>",
                           text, re.S | re.I):
        lowered = tag[0].lower()
        if lowered.startswith("<details"):
            stack.append((tag.start(), []))
        elif lowered.startswith("</details"):
            if stack:
                _start, pending = stack.pop()
                for section in pending:
                    section.end = tag.start()
                    sections.append(section)
        elif stack:
            label = re.sub(r"^<summary\b[^>]*>|</summary>$", "", tag[0], flags=re.I)
            section = _section(label, tag.start(), len(text), tag.end())
            if section:
                stack[-1][1].append(section)
    for _start, pending in stack:
        for section in pending:
            section.malformed = True
            sections.append(section)
    headers = list(re.finditer(
        r"(?m)^\s*(?:>\s*)*(?:#{1,6}\s+([^\n]+)|\*\*([^\n]+)\*\*\s*)$", text
    ))
    declared_headers = []
    for header in headers:
        section = _section(header[1] or header[2], header.start(), len(text), header.end())
        if section is None or "actionable comments posted" in section.label.lower():
            continue
        if (header[2] and section.count is None and not section.malformed
                and section.label.lower() not in {"findings", "comments"}):
            continue
        declared_headers.append((header, section))
    for index, (header, section) in enumerate(declared_headers):
        # A quoted outside-diff header owns the following details block.
        later = (declared_headers[index + 1][0].start()
                 if index + 1 < len(declared_headers) else len(text))
        divider = re.search(r"(?m)^\s*(?:>\s*)*---\s*$", text[header.end():later])
        section.end = header.end() + divider.start() if divider else later
        sections.append(section)
    return sorted(sections, key=lambda item: item.start)


def _section_complete(section: Section, text: str, markers: list[tuple[str, int]],
                      inline: set[str] | None = None) -> bool:
    members = {identity for identity, pos in markers if section.start <= pos < section.end}
    if section.malformed:
        return False
    if section.count is not None and inline is None:
        return len(members) == section.count
    if section.count is not None and len(members | inline) != section.count:
        return False
    content = text[section.content_start:section.end]
    plain = re.sub(r"<[^>]*>|(?m:^\s*>\s*)", "", content).strip().lower().rstrip(".")
    if plain in {"none", "no findings", "no findings were found"}:
        return not members and not inline
    # With no count, each structurally declared entry needs an identity.
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
        if section.count is not None:
            return True  # A declared total can be entirely inline.
        return not re.sub(r"<[^>]*>|\s", "", content) and not members
    for index, entry in enumerate(entries):
        start = section.content_start + entry.start()
        end = (section.content_start + entries[index + 1].start()
               if index + 1 < len(entries) else section.end)
        if len({identity for identity, pos in markers if start <= pos < end}) != 1:
            return False
    return len(members) == len(entries)


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
        elif "actionable comments posted" in text.lower() and not declarations:
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
    sections = _sections(text)
    seen = set()
    for section in sections:
        label = re.sub(r"\s*\([^)]*\)\s*$", "", section.label).lower()
        total_inline = inline if login != "coderabbitai[bot]" else None
        if label in seen or not _section_complete(section, text, markers, total_inline):
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
    ignored = set()
    for comment in conversation_comments:
        body = str(comment.get("body") or "")
        if not _bare_disposition(body, inline_disposition):
            continue
        text = live_markup(body)
        links = list(REVIEW_LINK.finditer(text))
        named = set(re.findall(
            r"(?:cr-comment:v1:[A-Za-z0-9_-]+|tradecraft-review-finding:v1:[0-9]+:[0-9]+)",
            text,
        ))
        # One source review and at most one full identity; extra targets cannot bundle.
        if len(links) != 1 or len(named) > 1:
            continue
        link = links[0]
        if link[1].lower() != repo.lower() or int(link[2]) != number:
            continue
        review_id = int(link[3])
        targets = []
        if named:
            identity = min(named)
            canonical = any(label == identity and url == link[0]
                            for label, url in MARKDOWN_LINK.findall(text))
            if canonical:
                targets = [finding for finding in findings.values()
                           if finding.identity == identity
                           and any(source["id"] == review_id for source in finding.sources)]
        else:
            if any(url == link[0] for _label, url in MARKDOWN_LINK.findall(text)):
                targets = [item for item in unidentified if item.review["id"] == review_id]
        if not targets:
            continue
        if author(comment) not in marker_producers:
            ignored.add(author(comment))
            continue
        for target in targets:
            target.answered = True
    return Classification(list(findings.values()), unidentified, sorted(ignored))
