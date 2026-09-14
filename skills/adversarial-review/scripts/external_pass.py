#!/usr/bin/env python3
"""Collect and replay the complete external-review evidence on one pull request."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from typing import Any

# Shared code lives in lib/, which ships beside this cell, so the import
# resolves in a source checkout and an installed plugin alike -- against this
# file's own directory, never the working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from winio import utf8_stdio  # noqa: E402


SCHEMA = "tradecraft.external-pass.v1"
PAGE_SIZE = 100
MAX_PAGES = 1000
SOURCES = (
    {"label": "issue_comments", "path": "issues/{pr}/comments"},
    {"label": "review_comments", "path": "pulls/{pr}/comments"},
    {"label": "reviews", "path": "pulls/{pr}/reviews"},
)


class ExternalPassError(Exception):
    """A refusal whose one-line diagnostic tells the holder what to retry."""


def canonical_json(value: Any) -> bytes:
    """One stable JSON representation for source comparison and bundle bytes."""
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def source_endpoint(repository: str, pull_request: int, source: dict[str, str]) -> str:
    """The REST collection named by one source label."""
    return f"repos/{repository}/{source['path'].format(pr=pull_request)}"


def gh_api(endpoint: str) -> str:
    """Read one REST page with every subprocess stream deliberately named."""
    try:
        result = subprocess.run(
            ["gh", "api", "--method", "GET", endpoint],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        raise ExternalPassError("gh is not on PATH") from None
    except OSError as exc:
        raise ExternalPassError(f"could not start gh: {exc}") from None
    if result.returncode:
        detail = result.stderr.strip().replace("\n", " ")
        raise ExternalPassError(f"gh api failed for {endpoint}: {detail[:400]}")
    return result.stdout


def stable_id(item: Any, label: str, page: int, position: int) -> str | int:
    """Return the only identity comparison can safely use for a raw object."""
    if not isinstance(item, dict):
        raise ExternalPassError(
            f"{label} page {page} item {position} is not a JSON object"
        )
    identifier = item.get("id")
    if isinstance(identifier, bool) or not isinstance(identifier, (str, int)):
        raise ExternalPassError(
            f"{label} page {page} item {position} has no stable id"
        )
    if isinstance(identifier, str) and not identifier:
        raise ExternalPassError(
            f"{label} page {page} item {position} has no stable id"
        )
    return identifier


def drain_collection(label: str, endpoint: str) -> dict[str, Any]:
    """Drain one REST collection until its terminal short page proves completion."""
    objects: list[dict[str, Any]] = []
    page_lengths: list[int] = []
    identifiers: set[str | int] = set()
    for page in range(1, MAX_PAGES + 1):
        page_endpoint = f"{endpoint}?per_page={PAGE_SIZE}&page={page}"
        try:
            raw = gh_api(page_endpoint)
        except ExternalPassError as exc:
            raise ExternalPassError(f"{label} page {page}: {exc}") from None
        try:
            items = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ExternalPassError(
                f"{label} page {page} returned malformed JSON: {exc.msg}"
            ) from None
        if not isinstance(items, list):
            raise ExternalPassError(f"{label} page {page} returned JSON that is not a list")
        page_lengths.append(len(items))
        for position, item in enumerate(items, start=1):
            identifier = stable_id(item, label, page, position)
            if identifier in identifiers:
                raise ExternalPassError(
                    f"{label} repeats id {identifier!s} before its terminal page"
                )
            identifiers.add(identifier)
            objects.append(item)
        if len(items) < PAGE_SIZE:
            return {
                "endpoint": endpoint,
                "completeness": {
                    "page_size": PAGE_SIZE,
                    "page_lengths": page_lengths,
                    "terminal_page": page,
                },
                "objects": objects,
            }
    raise ExternalPassError(
        f"{label} reached safety ceiling of {MAX_PAGES} full pages before a terminal page"
    )


def drain_sources(repository: str, pull_request: int) -> dict[str, dict[str, Any]]:
    """Drain every collection in the source-defined order."""
    return {
        source["label"]: drain_collection(
            source["label"], source_endpoint(repository, pull_request, source),
        )
        for source in SOURCES
    }


def ids_by_source(objects: list[dict[str, Any]], label: str) -> list[str | int]:
    """Read stored identifiers with the same admission rail as a live collection."""
    identifiers = [stable_id(item, label, 0, position)
                   for position, item in enumerate(objects, start=1)]
    if len(identifiers) != len(set(identifiers)):
        raise ExternalPassError(f"{label} repeats an id in stored bundle content")
    return identifiers


def source_difference(
        before: list[dict[str, Any]], after: list[dict[str, Any]], label: str) -> str | None:
    """Describe source movement by identity without hiding a changed raw object."""
    before_ids = ids_by_source(before, label)
    after_ids = ids_by_source(after, label)
    if before_ids == after_ids and canonical_json(before) == canonical_json(after):
        return None
    before_by_id = dict(zip(before_ids, before, strict=True))
    after_by_id = dict(zip(after_ids, after, strict=True))
    added = [identifier for identifier in after_ids if identifier not in before_by_id]
    removed = [identifier for identifier in before_ids if identifier not in after_by_id]
    changed = [
        identifier for identifier in after_ids
        if identifier in before_by_id
        and canonical_json(before_by_id[identifier]) != canonical_json(after_by_id[identifier])
    ]
    moved = [
        identifier for identifier in after_ids
        if identifier in before_by_id and not added and not removed
        and before_ids.index(identifier) != after_ids.index(identifier)
    ]
    parts = []
    for name, identifiers in (
            ("added", added), ("removed", removed), ("changed", changed), ("moved", moved)):
        if identifiers:
            parts.append(f"{name}: {', '.join(str(identifier) for identifier in identifiers)}")
    return "; ".join(parts) or "canonical source content differs"


def collect_stable_sources(repository: str, pull_request: int) -> dict[str, dict[str, Any]]:
    """Read every source twice and refuse a receipt if either full drain moved."""
    first = drain_sources(repository, pull_request)
    second = drain_sources(repository, pull_request)
    for source in SOURCES:
        label = source["label"]
        difference = source_difference(first[label]["objects"], second[label]["objects"], label)
        if difference:
            raise ExternalPassError(
                f"{label} was unstable between complete drains: {difference}; run collect again"
            )
    return first


def bundle_for(repository: str, pull_request: int, sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build the deterministic receipt only after every source has passed."""
    return {
        "schema": SCHEMA,
        "repository": repository,
        "pull_request": pull_request,
        "sources": {source["label"]: sources[source["label"]] for source in SOURCES},
    }


def write_new_bundle(path: Path, bundle: dict[str, Any]) -> bytes:
    """Publish complete canonical bytes atomically without replacing a receipt."""
    if os.path.lexists(path):
        raise ExternalPassError(f"output already exists: {path}")
    if not path.parent.is_dir():
        raise ExternalPassError(f"output directory does not exist: {path.parent}")
    data = canonical_json(bundle) + b"\n"
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as temporary:
            temporary_name = temporary.name
            temporary.write(data)
        os.replace(temporary_name, path)
    except OSError as exc:
        if temporary_name:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError:
                pass
        raise ExternalPassError(f"could not install bundle at {path}: {exc}") from None
    return data


def replay_command(path: Path) -> str:
    """Print the documented relative invocation in the active host's shell syntax."""
    arguments = ["python", "../scripts/external_pass.py", "verify", str(path)]
    if os.name == "nt":
        return subprocess.list2cmdline(arguments)
    return shlex.join(arguments)


def print_receipt(path: Path, data: bytes, sources: dict[str, dict[str, Any]]) -> None:
    """Print the legible cross-check and the command that replays its sources."""
    print(f"external-pass: bundle: {path}")
    print(f"external-pass: sha256: {hashlib.sha256(data).hexdigest()}")
    total = 0
    for source in SOURCES:
        label = source["label"]
        count = len(sources[label]["objects"])
        total += count
        print(f"external-pass: {label}: {count}")
    print(f"external-pass: total: {total}")
    print(f"external-pass: verify: {replay_command(path)}")


def required_bundle(path: Path) -> tuple[dict[str, Any], bytes]:
    """Read enough receipt structure to replay its exact repository and PR."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ExternalPassError(f"cannot read bundle {path}: {exc}") from None
    try:
        bundle = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExternalPassError(f"bundle {path} is not valid UTF-8 JSON: {exc}") from None
    if not isinstance(bundle, dict) or bundle.get("schema") != SCHEMA:
        raise ExternalPassError(f"bundle {path} does not use schema {SCHEMA}")
    repository = bundle.get("repository")
    pull_request = bundle.get("pull_request")
    sources = bundle.get("sources")
    if not isinstance(repository, str) or not repository or not isinstance(pull_request, int) \
            or isinstance(pull_request, bool) or pull_request < 1 or not isinstance(sources, dict):
        raise ExternalPassError(f"bundle {path} lacks a valid repository, pull request, or sources")
    for source in SOURCES:
        label = source["label"]
        saved = sources.get(label)
        if not isinstance(saved, dict) or not isinstance(saved.get("objects"), list):
            raise ExternalPassError(f"bundle {path} lacks objects for {label}")
        if saved.get("endpoint") != source_endpoint(repository, pull_request, source):
            raise ExternalPassError(f"bundle {path} has the wrong endpoint for {label}")
        proof = saved.get("completeness")
        if not isinstance(proof, dict) or not isinstance(proof.get("page_size"), int) \
                or not isinstance(proof.get("page_lengths"), list) \
                or not isinstance(proof.get("terminal_page"), int):
            raise ExternalPassError(f"bundle {path} lacks completeness proof for {label}")
        ids_by_source(saved["objects"], label)
    return bundle, raw


def collect(repository: str, pull_request: int, output: Path) -> None:
    """Collect stable sources, then install and receipt their one immutable bundle."""
    if os.path.lexists(output):
        raise ExternalPassError(f"output already exists: {output}")
    sources = collect_stable_sources(repository, pull_request)
    data = write_new_bundle(output, bundle_for(repository, pull_request, sources))
    print_receipt(output, data, sources)


def verify(path: Path) -> None:
    """Re-read the receipt's sources and report equality or source drift."""
    bundle, raw = required_bundle(path)
    try:
        current = collect_stable_sources(bundle["repository"], bundle["pull_request"])
    except ExternalPassError as exc:
        raise ExternalPassError(f"source failure while verifying {path}: {exc}") from None
    for source in SOURCES:
        label = source["label"]
        difference = source_difference(bundle["sources"][label]["objects"], current[label]["objects"], label)
        if difference:
            raise ExternalPassError(f"source drift in {label}: {difference}")
    print(f"external-pass: verified {path} sha256: {hashlib.sha256(raw).hexdigest()}")


def build_parser() -> argparse.ArgumentParser:
    """Build the two-operation public interface."""
    parser = argparse.ArgumentParser(prog="external-pass")
    commands = parser.add_subparsers(dest="command", required=True)
    collect_parser = commands.add_parser("collect")
    collect_parser.add_argument("--repo", required=True, metavar="OWNER/REPO")
    collect_parser.add_argument("--pr", required=True, type=int, metavar="PR_NUMBER")
    collect_parser.add_argument("--output", required=True, type=Path, metavar="BUNDLE.json")
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("bundle", type=Path, metavar="BUNDLE.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "collect":
            if args.pr < 1:
                raise ExternalPassError("--pr must be at least 1")
            collect(args.repo, args.pr, args.output)
        else:
            verify(args.bundle)
    except ExternalPassError as exc:
        print(f"external-pass: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
