#!/usr/bin/env python3
"""Export, run and grade leak-resistant connected-review replays."""
from __future__ import annotations

import argparse
from decimal import Decimal
import functools
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
import connected_review as cr  # noqa: E402
from winio import utf8_stdio  # noqa: E402


class ReplayError(RuntimeError):
    """A replay input or result cannot establish a score."""


EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
KEY_IN_RESULTS = "results contained the API key; nothing was written"


def read_api_key_file(path: Path) -> str:
    """Read one API key from a file, naming only the path when it cannot be used."""
    # A decode error quotes the offending bytes, so no exception text or chain may surface.
    try:
        raw = path.read_bytes()
    except OSError:
        raise ReplayError(f"API key file is unreadable: {path}") from None
    try:
        # The -sig codec drops a leading byte-order mark an editor may have saved.
        key = raw.decode("utf-8-sig").strip()
    except UnicodeDecodeError:
        raise ReplayError(f"API key file is not UTF-8 text: {path}") from None
    if not key:
        raise ReplayError(f"API key file is empty: {path}")
    if any(char.isspace() for char in key):
        raise ReplayError(f"API key file holds more than one line or token: {path}")
    return key


def _credentials(api_key: str | None) -> cr.ReviewCredentials:
    # A file key ignores the environment, so a spent key can never fall back to a token.
    if api_key is not None:
        return cr.ReviewCredentials(api_key, None)
    return cr.review_credentials(os.environ)


def refuse_secret(value: dict[str, Any], secret: str | None) -> None:
    if secret is not None and (
        cr._payload_contains_secret(value, secret)
        or secret in json.dumps(value, ensure_ascii=True, sort_keys=True)
    ):
        raise ReplayError(KEY_IN_RESULTS)


def write_results(path: Path, value: dict[str, Any], secret: str | None) -> None:
    refuse_secret(value, secret)
    write_object(path, value)


def read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReplayError(f"cannot read JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise ReplayError(f"expected a JSON object: {path}")
    return value


def write_object(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(bytes.fromhex(file_digest(path)))
    return digest.hexdigest()


def validate_source_manifest(value: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    if set(value) != {"schema_version", "repository", "cases"}:
        raise ReplayError("source manifest may contain only schema_version, repository and cases")
    if value.get("schema_version") != 1:
        raise ReplayError("source manifest schema_version must be 1")
    repository = value.get("repository")
    if not isinstance(repository, str) or not repository.count("/") == 1:
        raise ReplayError("source manifest repository is invalid")
    cases = value.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ReplayError("source manifest has no cases")
    seen = set()
    validated = []
    for case in cases:
        if not isinstance(case, dict) or set(case) != {"id", "number", "head", "base"}:
            raise ReplayError("each source case must contain only id, number, head and base")
        identifier = case.get("id")
        number = case.get("number")
        head = case.get("head")
        base = case.get("base")
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise ReplayError("source case IDs must be nonempty and unique")
        if not isinstance(number, int) or number <= 0:
            raise ReplayError(f"case {identifier} has an invalid pull request number")
        if not all(isinstance(sha, str) and len(sha) == 40
                   and all(char in "0123456789abcdef" for char in sha)
                   for sha in (head, base)):
            raise ReplayError(f"case {identifier} has an invalid revision")
        seen.add(identifier)
        validated.append({
            "id": identifier,
            "number": str(number),
            "head": head,
            "base": base,
        })
    return repository, validated


def export_replay(source: Path, output: Path) -> dict[str, Any]:
    repository, cases = validate_source_manifest(read_object(source))
    if output.exists():
        raise ReplayError(f"export destination already exists: {output}")
    output.mkdir(parents=True)
    exported = []
    for case in cases:
        case_root = output / "cases" / case["id"]
        snapshot = case_root / "snapshot"
        archive = cr.gh_bytes(f"repos/{repository}/tarball/{case['head']}")
        cr.extract_snapshot(archive, snapshot)
        input_dir = case_root / "input"
        input_dir.mkdir()
        diff_path = input_dir / "pull-request.diff"
        rules_path = input_dir / "repository-rules.md"
        diff_path.write_bytes(cr.gh_bytes(
            f"repos/{repository}/compare/{case['base']}...{case['head']}",
            accept="application/vnd.github.v3.diff",
        ))
        rules_path.write_bytes(cr.repository_review_rules(repository, case["base"]).encode("utf-8"))
        attributes_path = input_dir / "base-attributes.json"
        write_object(attributes_path, cr.base_attribute_material(
            repository, case["base"], cr.coverage_paths(diff_path.read_text(encoding="utf-8", errors="replace")),
        ))
        exported.append({
            **case,
            "snapshot": f"cases/{case['id']}/snapshot",
            "diff": f"cases/{case['id']}/input/pull-request.diff",
            "rules": f"cases/{case['id']}/input/repository-rules.md",
            "snapshot_sha256": tree_digest(snapshot),
            "diff_sha256": file_digest(diff_path),
            "rules_sha256": file_digest(rules_path),
            "base_attributes": f"cases/{case['id']}/input/base-attributes.json",
            "base_attributes_sha256": file_digest(attributes_path),
        })
    manifest = {
        "schema_version": 2,
        "repository": repository,
        "cases": exported,
    }
    write_object(output / "manifest.json", manifest)
    return manifest


def validate_export(root: Path, *, require_policy: bool = False) -> dict[str, Any]:
    manifest = read_object(root / "manifest.json")
    if set(manifest) != {"schema_version", "repository", "cases"}:
        raise ReplayError("export manifest contains an unrecognized field")
    if manifest.get("schema_version") not in {1, 2} or not isinstance(manifest.get("cases"), list):
        raise ReplayError("export manifest is malformed")
    if require_policy and manifest["schema_version"] == 1:
        source = {
            "schema_version": 1, "repository": manifest["repository"],
            "cases": [{"id": row["id"], "number": int(row["number"]),
                       "base": row["base"], "head": row["head"]} for row in manifest["cases"]],
        }
        raise ReplayError(
            "older export lacks captured base attributes; re-export into a new directory "
            "with `python tools/connected_review_replay.py export --manifest SOURCE.json --output NEW_DIRECTORY`; "
            "write this original source manifest to SOURCE.json: " + json.dumps(source, ensure_ascii=True, sort_keys=True)
        )
    for case in manifest["cases"]:
        if not isinstance(case, dict):
            raise ReplayError("export case is malformed")
        expected = {
            "id", "number", "head", "base", "snapshot", "diff", "rules",
            "snapshot_sha256", "diff_sha256", "rules_sha256",
        }
        if manifest["schema_version"] == 2:
            expected |= {"base_attributes", "base_attributes_sha256"}
        if set(case) != expected:
            raise ReplayError("export case contains an unrecognized field")
        snapshot = root / case["snapshot"]
        diff = root / case["diff"]
        rules = root / case["rules"]
        if (
            tree_digest(snapshot) != case["snapshot_sha256"]
            or file_digest(diff) != case["diff_sha256"]
            or file_digest(rules) != case["rules_sha256"]
        ):
            raise ReplayError(f"export case {case['id']} no longer matches its manifest")
        if manifest["schema_version"] == 2:
            attributes = root / case["base_attributes"]
            if file_digest(attributes) != case["base_attributes_sha256"]:
                raise ReplayError(f"export case {case['id']} base attributes no longer match its manifest")
            try:
                cr.validate_attribute_material(read_object(attributes), case["base"])
            except cr.ReviewError as exc:
                raise ReplayError(str(exc)) from exc
    return manifest


# The padded known-defect ladder (#902, row 6) grows one case to a rung's size with
# inert added files, so the finder's ceiling can be measured on a defect it should find.
LIVE_FINDER_PROMPT = ROOT / "skills" / "connected-review" / "references" / "finder.md"
REVIEWER_WORKFLOW = ROOT / ".github" / "workflows" / "connected-review-shared.yml"
PADDING_DIRECTORY = "replay-padding"
PADDING_FILE_BYTES = 64 * 1024
PADDING_WINDOW_BYTES = 1_000
DEFAULT_PAD_SEED = "tradecraft-902-ladder-v1"
CASE_TEMPORARY_PREFIX = "connected-review-replay-case-"
PADDING_VOCABULARY = (
    "account", "address", "amount", "archive", "attempt", "balance", "batch", "binding",
    "boundary", "branch", "buffer", "bundle", "cache", "calendar", "capacity", "catalog",
    "channel", "checkpoint", "client", "column", "comment", "config", "counter", "cursor",
    "customer", "dataset", "deadline", "default", "delivery", "detail", "device", "digest",
    "document", "domain", "draft", "entry", "estimate", "event", "export", "feature",
    "field", "filter", "folder", "format", "fragment", "gateway", "group", "handler",
    "header", "history", "import", "index", "input", "inventory", "invoice", "item",
    "journal", "label", "layer", "ledger", "limit", "listing", "locale", "marker",
    "measure", "member", "message", "metric", "module", "notice", "number", "offset",
    "option", "order", "output", "owner", "package", "page", "parcel", "payload",
    "period", "policy", "portal", "preview", "profile", "project", "quota", "range",
    "reader", "receipt", "record", "region", "release", "report", "request", "result",
    "revision", "route", "schedule", "schema", "section", "segment", "session", "setting",
    "shipment", "signal", "source", "status", "storage", "summary", "supplier", "table",
    "target", "template", "ticket", "timeline", "token", "topic", "total", "tracker",
    "update", "upload", "value", "vendor", "version", "window", "worker", "zone",
)


class PaddingRefused(ReplayError):
    """Padding cannot place a case at its rung, so no model launches."""


def _padding_choice(seed: str, file_index: int, counter: int, size: int) -> int:
    # A hash, not `random`, keeps the bytes identical across Python versions.
    digest = hashlib.sha256(f"{seed}:{file_index}:{counter}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % size


@functools.lru_cache(maxsize=256)
def padding_lines(seed: str, file_index: int) -> tuple[str, ...]:
    """One padding file: a docstring, comments and literal constants, with no behaviour to report."""
    lines = ['"""Replay padding: literal constants and comments only; nothing here runs."""', ""]
    total = sum(len(line) + 1 for line in lines)
    counter = 0
    constant = 0

    def draw(size: int) -> int:
        nonlocal counter
        counter += 1
        return _padding_choice(seed, file_index, counter, size)

    def words(count: int) -> list[str]:
        return [PADDING_VOCABULARY[draw(len(PADDING_VOCABULARY))] for _ in range(count)]

    while True:
        kind = draw(3)
        if kind == 0:
            line = "# " + " ".join(words(6 + draw(7))).capitalize() + "."
        else:
            constant += 1
            name = "_".join(words(3)).upper() + f"_{constant}"
            value = '"' + " ".join(words(3 + draw(6))) + '"' if kind == 1 else str(draw(1_000_000))
            line = f"{name} = {value}"
        if total + len(line) + 1 > PADDING_FILE_BYTES:
            return tuple(lines)
        lines.append(line)
        total += len(line) + 1


def padding_path(file_index: int) -> str:
    return f"{PADDING_DIRECTORY}/padding_{file_index:03d}.py"


def padding_content(lines: tuple[str, ...]) -> bytes:
    return ("\n".join(lines) + "\n").encode("utf-8")


def padding_section(path: str, lines: tuple[str, ...]) -> str:
    """A standard new-file diff section for one padding file."""
    content = padding_content(lines)
    blob = hashlib.sha1(b"blob %d\x00" % len(content) + content).hexdigest()[:7]
    count = "" if len(lines) == 1 else f",{len(lines)}"
    return (
        f"diff --git a/{path} b/{path}\nnew file mode 100644\nindex 0000000..{blob}\n"
        f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1{count} @@\n"
        + "".join(f"+{line}\n" for line in lines)
    )


def _padding_files(seed: str, files: int, last_lines: int | None = None) -> list[tuple[str, tuple[str, ...]]]:
    chosen = [(padding_path(index), padding_lines(seed, index)) for index in range(1, files + 1)]
    if chosen and last_lines is not None:
        path, lines = chosen[-1]
        chosen[-1] = (path, lines[:last_lines])
    return [(path, lines) for path, lines in chosen if lines]


def padded_diff(diff: str, files: list[tuple[str, tuple[str, ...]]]) -> str:
    """Put the first half of the padding before the case's sections and the rest after them."""
    # The case's own sections, and so its defect, sit mid-prompt whatever their paths.
    if diff and not diff.endswith("\n"):
        diff += "\n"
    sections = re.split(r"(?m)(?=^diff --git )", diff)
    preamble = sections.pop(0) if sections and not sections[0].startswith("diff --git ") else ""
    padding = [padding_section(path, lines) for path, lines in files]
    before = (len(padding) + 1) // 2
    return preamble + "".join(padding[:before]) + "".join(sections) + "".join(padding[before:])


def refuse_padding_collision(diff: str, snapshot: Path) -> None:
    taken = [
        path for path in cr.coverage_paths(diff)
        if path == PADDING_DIRECTORY or path.startswith(PADDING_DIRECTORY + "/")
    ]
    if taken or (snapshot / PADDING_DIRECTORY).exists():
        where = "diff" if taken else "snapshot"
        raise PaddingRefused(f"padding path is already in the case's {where}: {PADDING_DIRECTORY}")


def measure_finder_input(
    diff: str, attributes: dict[str, Any], finder_text: str, snapshot: Path, rules: str,
) -> int:
    """The reviewer's own size: the largest composed finder input, through live selection."""
    selected, exclusions, _lines = cr.select_coverage(diff, attributes)
    for entry in exclusions:
        if entry["path"].startswith(PADDING_DIRECTORY + "/"):
            raise PaddingRefused(
                f"padding path {entry['path']} is excluded from coverage as {entry['reason']}"
            )
    return cr.largest_input_bytes(cr.finder_prompts(finder_text, snapshot, selected, rules, None, exclusions))


def pad_case(
    diff: str,
    attributes: dict[str, Any],
    finder_text: str,
    snapshot: Path,
    rules: str,
    target: int,
    seed: str,
) -> tuple[str, dict[str, Any], list[tuple[str, tuple[str, ...]]]]:
    """Pad a raw diff until its largest finder input lies in [target - window, target]."""
    def measure(files: list[tuple[str, tuple[str, ...]]]) -> tuple[str, int]:
        candidate = padded_diff(diff, files)
        return candidate, measure_finder_input(candidate, attributes, finder_text, snapshot, rules)

    padded, natural = measure([])
    if natural > target:
        raise PaddingRefused(f"case is larger than the rung: {natural} > {target} UTF-8 bytes")
    low = target - PADDING_WINDOW_BYTES
    chosen: list[tuple[str, tuple[str, ...]]] = []
    measured = natural
    if natural < low:
        # Whole files first: the fewest whose composed size reaches the rung.
        each = len(padding_section(padding_path(1), padding_lines(seed, 1)).encode("utf-8"))
        files = max(1, -(-(target - natural) // each))
        sizes: dict[int, int] = {}

        def whole(count: int) -> int:
            if count not in sizes:
                sizes[count] = natural if count == 0 else measure(_padding_files(seed, count))[1]
            return sizes[count]

        while whole(files) < target:
            files += 1
        while files > 1 and whole(files - 1) >= target:
            files -= 1
        # Then the last file's line count: the most lines that keep the size within the rung.
        lowest, highest = 0, len(padding_lines(seed, files))
        while lowest < highest:
            middle = (lowest + highest + 1) // 2
            if measure(_padding_files(seed, files, middle))[1] <= target:
                lowest = middle
            else:
                highest = middle - 1
        chosen = _padding_files(seed, files, lowest)
        padded, measured = measure(chosen)
        if not low <= measured <= target:
            raise PaddingRefused(
                f"rung {target} cannot be reached within {PADDING_WINDOW_BYTES} UTF-8 bytes; nearest is {measured}"
            )
    record = {
        "target_bytes": target,
        "seed": seed,
        "files": len(chosen),
        "lines": sum(len(lines) for _path, lines in chosen),
        "measured_bytes": measured,
        "padded_diff_sha256": hashlib.sha256(padded.encode("utf-8")).hexdigest(),
    }
    return padded, record, chosen


def write_padding(snapshot: Path, files: list[tuple[str, tuple[str, ...]]]) -> None:
    for path, lines in files:
        target = snapshot.joinpath(*path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(padding_content(lines))


def parse_rungs(value: str) -> list[int]:
    try:
        rungs = [int(item) for item in value.split(",")]
    except ValueError:
        raise ReplayError(f"rungs must be comma-separated byte counts: {value}") from None
    if not rungs or any(rung <= 0 for rung in rungs) or rungs != sorted(set(rungs)):
        raise ReplayError("rungs must be positive and strictly ascending")
    return rungs


def single_case(manifest: dict[str, Any]) -> dict[str, Any]:
    if len(manifest["cases"]) != 1:
        raise ReplayError("a ladder export holds exactly one case")
    return manifest["cases"][0]


def ladder_plan(
    export_root: Path, rungs: list[int], seed: str = DEFAULT_PAD_SEED,
    finder_prompt: Path | None = None,
) -> list[dict[str, Any]]:
    """Compose and measure the natural size and every rung; launches no model and needs no credential."""
    manifest = validate_export(export_root, require_policy=True)
    case = single_case(manifest)
    finder_text = (finder_prompt or LIVE_FINDER_PROMPT).read_text(encoding="utf-8")
    diff = (export_root / case["diff"]).read_text(encoding="utf-8", errors="replace")
    rules = (export_root / case["rules"]).read_text(encoding="utf-8", errors="replace")
    attributes = read_object(export_root / case["base_attributes"])
    refuse_padding_collision(diff, export_root / case["snapshot"])
    # A replay case's own snapshot path, whose length the prompt's size depends on.
    with tempfile.TemporaryDirectory(prefix=CASE_TEMPORARY_PREFIX) as temporary:
        snapshot = Path(temporary) / "case" / "snapshot"
        rows: list[dict[str, Any]] = [{
            "rung": "natural",
            "measured_bytes": measure_finder_input(diff, attributes, finder_text, snapshot, rules),
            "files": 0,
            "lines": 0,
            "padded_diff_sha256": hashlib.sha256(diff.encode("utf-8")).hexdigest(),
        }]
        for rung in rungs:
            _padded, record, _files = pad_case(diff, attributes, finder_text, snapshot, rules, rung, seed)
            rows.append({"rung": rung, **{
                key: record[key] for key in ("measured_bytes", "files", "lines", "padded_diff_sha256")
            }})
    return rows


def harness_digest() -> str:
    digest = hashlib.sha256()
    for name, path in (
        ("runtime", Path(cr.__file__)),
        ("replay", Path(__file__)),
    ):
        digest.update(name.encode("ascii"))
        digest.update(bytes.fromhex(file_digest(path)))
    return digest.hexdigest()


def reviewer_record(
    finder_prompt: Path,
    checker_prompt: Path | None,
    version: str,
    revision: str,
    *,
    single_pass: bool = False,
    finder_effort: str | None = None,
    checker_effort: str | None = None,
    preload_changed_files: bool = False,
    preload_budget_bytes: int = cr.DEFAULT_PRELOAD_BUDGET_BYTES,
    summarise_deleted_files: bool = False,
    summary_threshold_bytes: int | None = None,
    pad_to_bytes: int | None = None,
    pad_seed: str | None = None,
) -> dict[str, Any]:
    settings = cr.reviewer_settings(
        version,
        preload_changed_files=preload_changed_files,
        preload_budget_bytes=preload_budget_bytes,
    )
    record = {
        "revision": revision,
        **settings,
        "settings_sha256": hashlib.sha256(cr._json_bytes(settings)).hexdigest(),
        "finder_prompt_sha256": file_digest(finder_prompt),
        "harness_sha256": harness_digest(),
    }
    if checker_prompt is not None:
        record["checker_prompt_sha256"] = file_digest(checker_prompt)
    if (
        single_pass
        or finder_effort is not None
        or checker_effort is not None
        or preload_changed_files
        or summarise_deleted_files
        or pad_to_bytes is not None
    ):
        record.update({
            "pass_structure": "single-pass" if single_pass else "finder-checker",
            "finder_effort": finder_effort or cr.FINDER_EFFORT,
            "checker_effort": None if single_pass else checker_effort or cr.CHECKER_EFFORT,
            "overrides": {
                **({"single_pass": True} if single_pass else {}),
                **({"finder_effort": finder_effort} if finder_effort is not None else {}),
                **({"checker_effort": checker_effort} if checker_effort is not None else {}),
                **({"preload_changed_files": True} if preload_changed_files else {}),
                **({
                    "summarise_deleted_files": True,
                    "summary_threshold_bytes": _summary_threshold(summary_threshold_bytes),
                } if summarise_deleted_files else {}),
                **({
                    "pad_to_bytes": pad_to_bytes, "pad_seed": pad_seed or DEFAULT_PAD_SEED,
                } if pad_to_bytes is not None else {}),
            },
        })
    return record


def _resume_cases(
    resume: Path,
    manifest: dict[str, Any],
    current_reviewer: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[str], dict[str, str]]:
    previous = read_object(resume)
    expected_manifest = [
        {"case_id": case["id"], "head": case["head"], "base": case["base"]}
        for case in manifest["cases"]
    ]
    if (
        previous.get("repository") != manifest["repository"]
        or previous.get("manifest_cases") != expected_manifest
    ):
        raise ReplayError("resume results do not match the exported manifest")
    stored_reviewer = previous.get("reviewer")
    if not isinstance(stored_reviewer, dict):
        raise ReplayError("resume results have no reviewer identity")
    identity_fields = (
        set(current_reviewer) | set(stored_reviewer)
    ) - {"harness_sha256"}
    mismatched = [
        key for key in identity_fields
        if stored_reviewer.get(key) != current_reviewer.get(key)
    ]
    if mismatched:
        raise ReplayError(
            "resume reviewer identity differs: " + ", ".join(sorted(mismatched))
        )
    expected_sources = {case["id"]: case["base_attributes_sha256"] for case in manifest["cases"]}
    if previous.get("base_attribute_sources") != expected_sources:
        raise ReplayError("resume base attribute source hashes differ; re-export original revisions into a new directory and start a new results file")
    old_harness = stored_reviewer.get("harness_sha256")
    if (
        not isinstance(old_harness, str)
        or len(old_harness) != 64
        or any(char not in "0123456789abcdef" for char in old_harness)
    ):
        raise ReplayError("resume results have no harness hash")
    rows = previous.get("cases")
    if not isinstance(rows, list):
        raise ReplayError("resume results have no case records")
    manifest_by_id = {case["id"]: case for case in manifest["cases"]}
    previous_by_id = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ReplayError("resume results contain a malformed case record")
        identifier = row.get("case_id")
        expected = manifest_by_id.get(identifier)
        if (
            expected is None
            or identifier in previous_by_id
            or row.get("head") != expected["head"]
            or row.get("base") != expected["base"]
        ):
            raise ReplayError("resume results contain a mismatched case record")
        previous_by_id[identifier] = row
    previous_harnesses = previous.get("case_harness_sha256", {})
    if not isinstance(previous_harnesses, dict):
        raise ReplayError("resume case harness record is malformed")
    completed = {
        identifier: row for identifier, row in previous_by_id.items()
        if row.get("status") == "completed"
    }
    case_harnesses = {}
    for identifier in completed:
        value = previous_harnesses.get(identifier, old_harness)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)
        ):
            raise ReplayError(f"resume case {identifier} has no harness hash")
        case_harnesses[identifier] = value
    resumed = [
        case["id"] for case in manifest["cases"] if case["id"] not in completed
    ]
    return completed, resumed, case_harnesses


def _summary_threshold(value: int | None) -> int:
    return cr.MAX_FINDER_PROMPT_BYTES if value is None else value


def _validate_run_options(
    checker_prompt: Path | None,
    single_pass: bool,
    finder_effort: str | None,
    checker_effort: str | None,
    summarise_deleted_files: bool = False,
    summary_threshold_bytes: int | None = None,
    pad_to_bytes: int | None = None,
    pad_seed: str | None = None,
    preload_changed_files: bool = False,
) -> None:
    if pad_seed is not None and pad_to_bytes is None:
        raise ReplayError("--pad-seed requires --pad-to-bytes")
    if pad_to_bytes is not None:
        if pad_to_bytes <= 0:
            raise ReplayError("--pad-to-bytes must be positive")
        # A ladder rung measures the live reviewer, which neither summarises below the rung nor preloads.
        if summarise_deleted_files:
            raise ReplayError("--pad-to-bytes cannot be used with --summarise-deleted-files")
        if preload_changed_files:
            raise ReplayError("--pad-to-bytes cannot be used with --preload-changed-files")
    if summary_threshold_bytes is not None and not summarise_deleted_files:
        raise ReplayError("--summary-threshold-bytes requires --summarise-deleted-files")
    if summary_threshold_bytes is not None and summary_threshold_bytes < 0:
        raise ReplayError("--summary-threshold-bytes cannot be negative")
    if finder_effort is not None and finder_effort not in EFFORT_LEVELS:
        raise ReplayError(f"unsupported finder effort: {finder_effort}")
    if checker_effort is not None and checker_effort not in EFFORT_LEVELS:
        raise ReplayError(f"unsupported checker effort: {checker_effort}")
    if single_pass and checker_effort is not None:
        raise ReplayError("--checker-effort cannot be used with --single-pass")
    if not single_pass and checker_prompt is None:
        raise ReplayError("--checker-prompt is required unless --single-pass is used")


def _run_finders_at_effort(
    executable: str | list[str],
    run_root: Path,
    snapshot: Path,
    instructions: str,
    diff: str,
    rules: str,
    lines: dict[tuple[str, str], set[int]],
    credentials: cr.ReviewCredentials,
    effort: str,
    preloaded_changed_files: dict[str, Any] | None,
    exclusions: list[dict[str, str]] | None = None,
    *,
    summarised: list[dict[str, Any]] | None = None,
    readable: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, list[dict[str, Any]]]]:
    return cr.run_finders(
        executable, run_root, snapshot, instructions, diff, rules, lines, credentials, preloaded_changed_files,
        effort=effort, exclusions=exclusions, summarised=summarised, readable=readable,
    )


def _run_finders_for_replay(
    executable: str | list[str],
    run_root: Path,
    snapshot: Path,
    instructions: str,
    diff: str,
    rules: str,
    lines: dict[tuple[str, str], set[int]],
    credentials: cr.ReviewCredentials,
    effort: str | None,
    preloaded_changed_files: dict[str, Any] | None,
    exclusions: list[dict[str, str]] | None = None,
    *,
    summarised: list[dict[str, Any]] | None = None,
    readable: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, list[dict[str, Any]]]]:
    if effort is None:
        return cr.run_finders(
            executable, run_root, snapshot, instructions, diff, rules, lines, credentials,
            preloaded_changed_files, exclusions=exclusions, summarised=summarised, readable=readable,
        )
    return _run_finders_at_effort(
        executable, run_root, snapshot, instructions, diff, rules, lines, credentials, effort,
        preloaded_changed_files, exclusions, summarised=summarised, readable=readable,
    )


def _run_checkers_at_effort(
    executable: str | list[str],
    run_root: Path,
    snapshot: Path,
    instructions: str,
    diff: str,
    rules: str,
    candidates: list[dict[str, Any]],
    lines: dict[tuple[str, str], set[int]],
    credentials: cr.ReviewCredentials,
    effort: str,
    preloaded_changed_files: dict[str, Any] | None,
    exclusions: list[dict[str, str]] | None = None,
    *,
    summarised: list[dict[str, Any]] | None = None,
    readable: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, list[dict[str, Any]]]]:
    return cr.run_checkers(
        executable, run_root, snapshot, instructions, diff, rules, candidates, lines, credentials, preloaded_changed_files,
        effort=effort, exclusions=exclusions, summarised=summarised, readable=readable,
    )


def _run_checkers_for_replay(
    executable: str | list[str],
    run_root: Path,
    snapshot: Path,
    instructions: str,
    diff: str,
    rules: str,
    candidates: list[dict[str, Any]],
    lines: dict[tuple[str, str], set[int]],
    credentials: cr.ReviewCredentials,
    effort: str | None,
    preloaded_changed_files: dict[str, Any] | None,
    exclusions: list[dict[str, str]] | None = None,
    *,
    summarised: list[dict[str, Any]] | None = None,
    readable: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, list[dict[str, Any]]]]:
    if effort is None:
        return cr.run_checkers(
            executable, run_root, snapshot, instructions, diff, rules,
            candidates, lines, credentials, preloaded_changed_files, exclusions=exclusions,
            summarised=summarised, readable=readable,
        )
    return _run_checkers_at_effort(
        executable, run_root, snapshot, instructions, diff, rules,
        candidates, lines, credentials, effort, preloaded_changed_files, exclusions,
        summarised=summarised, readable=readable,
    )


def run_replay(
    export_root: Path,
    output: Path,
    finder_prompt: Path,
    checker_prompt: Path | None,
    executable: str | list[str],
    version: str,
    revision: str,
    resume: Path | None = None,
    *,
    single_pass: bool = False,
    finder_effort: str | None = None,
    checker_effort: str | None = None,
    preload_changed_files: bool = False,
    preload_budget_bytes: int = cr.DEFAULT_PRELOAD_BUDGET_BYTES,
    summarise_deleted_files: bool = False,
    summary_threshold_bytes: int | None = None,
    api_key: str | None = None,
    pad_to_bytes: int | None = None,
    pad_seed: str | None = None,
) -> dict[str, Any]:
    _validate_run_options(
        checker_prompt, single_pass, finder_effort, checker_effort,
        summarise_deleted_files, summary_threshold_bytes,
        pad_to_bytes, pad_seed, preload_changed_files,
    )
    manifest = validate_export(export_root, require_policy=True)
    finder_text = finder_prompt.read_text(encoding="utf-8")
    checker_text = (
        checker_prompt.read_text(encoding="utf-8") if checker_prompt is not None else None
    )
    current_reviewer = reviewer_record(
        finder_prompt, checker_prompt, version, revision,
        single_pass=single_pass,
        finder_effort=finder_effort,
        checker_effort=checker_effort,
        preload_changed_files=preload_changed_files,
        preload_budget_bytes=preload_budget_bytes,
        summarise_deleted_files=summarise_deleted_files,
        summary_threshold_bytes=summary_threshold_bytes,
        pad_to_bytes=pad_to_bytes,
        pad_seed=pad_seed,
    )
    completed: dict[str, dict[str, Any]] = {}
    resumed_cases: list[str] = []
    case_harnesses: dict[str, str] = {}
    if resume is not None:
        if output.resolve() == resume.resolve() or output.exists():
            raise ReplayError("resume output must be a new results file")
        completed, resumed_cases, case_harnesses = _resume_cases(
            resume, manifest, current_reviewer,
        )
    pending = [case for case in manifest["cases"] if case["id"] not in completed]
    if pending:
        try:
            _credentials(api_key)
        except cr.ReviewError as exc:
            raise ReplayError(str(exc)) from exc
        cr.verify_managed_settings()
        cr.verify_claude_version(executable, version)
    order = {case["id"]: index for index, case in enumerate(manifest["cases"])}
    record = {
        "schema_version": 1,
        "repository": manifest["repository"],
        "manifest_cases": [
            {"case_id": case["id"], "head": case["head"], "base": case["base"]}
            for case in manifest["cases"]
        ],
        "reviewer": current_reviewer,
        "base_attribute_sources": {case["id"]: case["base_attributes_sha256"] for case in manifest["cases"]},
        "resumed_cases": resumed_cases,
        "case_harness_sha256": case_harnesses,
        "credential_source": "environment" if api_key is None else "api-key-file",
        "complete": False,
        "cases": list(completed.values()),
    }
    record["cases"].sort(key=lambda row: order[row["case_id"]])
    record["complete"] = (
        len(record["cases"]) == len(record["manifest_cases"])
        and all(case.get("status") == "completed" for case in record["cases"])
    )
    write_results(output, record, api_key)
    for case in pending:
        case_result: dict[str, Any] = {
            "case_id": case["id"], "head": case["head"], "base": case["base"],
        }
        # Each case starts on the key, as each live review does.
        credentials = _credentials(api_key)
        try:
            with tempfile.TemporaryDirectory(prefix=CASE_TEMPORARY_PREFIX) as temporary:
                temporary_root = Path(temporary)
                case_root = temporary_root / "case"
                snapshot = case_root / "snapshot"
                input_dir = case_root / "input"
                prohibited = temporary_root / "prohibited"
                prohibited.mkdir()
                canaries = {
                    "answer-key": "answer-key material must be unreachable",
                    "pull-request-thread": "pull-request discussion must be unreachable",
                    "later-commit": "later repository bytes must be unreachable",
                }
                canary_record = {}
                for name, content in canaries.items():
                    path = prohibited / f"{name}.txt"
                    path.write_bytes(content.encode("ascii"))
                    canary_record[name] = {
                        "path": str(path), "sha256": file_digest(path),
                    }
                shutil.copytree(export_root / case["snapshot"], snapshot)
                input_dir.mkdir()
                diff_path = input_dir / "pull-request.diff"
                rules_path = input_dir / "repository-rules.md"
                shutil.copyfile(export_root / case["diff"], diff_path)
                shutil.copyfile(export_root / case["rules"], rules_path)
                diff_text = diff_path.read_text(encoding="utf-8", errors="replace")
                rules_text = rules_path.read_text(encoding="utf-8", errors="replace")
                attributes = read_object(export_root / case["base_attributes"])
                if pad_to_bytes is not None:
                    # Padding joins the raw diff, so live selection and line anchors see it.
                    refuse_padding_collision(diff_text, snapshot)
                    diff_text, case_result["padding"], padding_files = pad_case(
                        diff_text, attributes, finder_text, snapshot, rules_text,
                        pad_to_bytes, pad_seed or DEFAULT_PAD_SEED,
                    )
                    write_padding(snapshot, padding_files)
                diff_text, exclusions, lines = cr.select_coverage(diff_text, attributes)
                case_result["excluded_files"] = exclusions
                preloaded = (
                    cr.preload_changed_file_data(
                        snapshot, diff_text, preload_budget_bytes,
                    )
                    if preload_changed_files else None
                )
                prompts = cr.finder_prompts(
                    finder_text, snapshot, diff_text, rules_text, preloaded, exclusions,
                )
                summarised = None
                readable = None
                if (
                    summarise_deleted_files
                    and cr.largest_input_bytes(prompts) > _summary_threshold(summary_threshold_bytes)
                ):
                    # The live reviewer's over-budget summary, at this run's threshold;
                    # replay still refuses no size.
                    summarised_diff, entries = cr.summarise_deleted_files(diff_text)
                    if entries:
                        summarised = entries
                        readable = case_root / cr.DELETED_FOLDER_NAME
                        cr.write_deleted_files(
                            diff_path.read_bytes().decode("utf-8", errors="surrogateescape"), entries, readable,
                        )
                        case_result["summarised_deleted_files"] = cr.summary_exclusions(entries)
                        case_result["finder_input_utf8_bytes_before_summary"] = {
                            name: len(cr.pass_input_bytes(prompt)) for name, prompt in prompts
                        }
                        diff_text = summarised_diff
                        if preload_changed_files:
                            preloaded = cr.preload_changed_file_data(
                                snapshot, diff_text, preload_budget_bytes,
                            )
                        prompts = cr.finder_prompts(
                            finder_text, snapshot, diff_text, rules_text, preloaded, exclusions,
                            summarised=summarised, readable=readable,
                        )
                case_result["finder_input_utf8_bytes"] = {
                    name: len(cr.pass_input_bytes(prompt)) for name, prompt in prompts
                }
                candidates, finder_usage, finder_trace = _run_finders_for_replay(
                    executable, case_root, snapshot, finder_text, diff_text,
                    rules_text, lines, credentials, finder_effort, preloaded, exclusions,
                    summarised=summarised, readable=readable,
                )
                if single_pass:
                    survivors = cr.deduplicate_root_causes(candidates)
                    checker_usage = None
                    checker_trace = None
                else:
                    assert checker_text is not None
                    survivors, checker_usage, checker_trace = _run_checkers_for_replay(
                        executable, case_root, snapshot, checker_text, diff_text,
                        rules_text, candidates, lines, credentials, checker_effort,
                        preloaded, exclusions, summarised=summarised, readable=readable,
                    )
                finder_leaks = []
                for name, trace in finder_trace.items():
                    finder_leaks.extend(_outside_trace_reads(
                        trace, snapshot, input_dir, case_root / f"finder-{name}", readable,
                    ))
                checker_leaks = []
                if checker_trace is not None:
                    for name, trace in checker_trace.items():
                        checker_leaks.extend(_outside_trace_reads(
                            trace, snapshot, input_dir, case_root / f"checker-{name}", readable,
                        ))
                leaks = sorted(set(finder_leaks + checker_leaks))
                completed_result = {
                    "status": "invalid-leak" if leaks else "completed",
                    "survivors": survivors,
                    "finder_usage": finder_usage,
                    "finder_trace": finder_trace,
                    "outside_reads": leaks,
                    "canaries": canary_record,
                }
                if checker_usage is not None and checker_trace is not None:
                    completed_result.update({
                        "checker_usage": checker_usage,
                        "checker_trace": checker_trace,
                    })
                case_result.update(completed_result)
        except PaddingRefused:
            raise
        except (ReplayError, cr.ReviewError, OSError) as exc:
            case_result.update({"status": "error", "error": str(exc)})
        case_result["credential"] = credentials.record
        record["cases"].append(case_result)
        record["cases"].sort(key=lambda row: order[row["case_id"]])
        record["case_harness_sha256"][case["id"]] = current_reviewer["harness_sha256"]
        record["complete"] = (
            len(record["cases"]) == len(record["manifest_cases"])
            and all(case.get("status") == "completed" for case in record["cases"])
        )
        write_results(output, record, api_key)
    return record


DEFECT_KEY_FIELDS = frozenset({
    "repository", "number", "head", "base", "source", "anchors", "root_cause", "wrong_result",
})
MATCH_FIELDS = frozenset({"run", "survivor_id", "root_cause_same", "wrong_result_same", "reason"})
BILLING_PREFIX = "Claude API key budget spent ("
COUNTED_CLASSES = frozenset({"finished", "not-finished"})


def _sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(char in "0123456789abcdef" for char in value)


def validate_defect_key(value: dict[str, Any]) -> dict[str, Any]:
    """The defect a ladder run must find, fixed before the first paid run."""
    if set(value) != DEFECT_KEY_FIELDS:
        raise ReplayError("defect key must contain exactly: " + ", ".join(sorted(DEFECT_KEY_FIELDS)))
    repository = value["repository"]
    if not isinstance(repository, str) or repository.count("/") != 1:
        raise ReplayError("defect key repository is invalid")
    if not isinstance(value["number"], int) or isinstance(value["number"], bool) or value["number"] <= 0:
        raise ReplayError("defect key number is invalid")
    if not _sha(value["head"]) or not _sha(value["base"]):
        raise ReplayError("defect key head and base must be full revisions")
    source = value["source"]
    if (
        not isinstance(source, dict) or set(source) != {"comment_url", "fixing_commit"}
        or not all(isinstance(item, str) and item.strip() for item in source.values())
    ):
        raise ReplayError("defect key source must name comment_url and fixing_commit")
    anchors = value["anchors"]
    if not isinstance(anchors, list) or not anchors:
        raise ReplayError("defect key has no anchors")
    for anchor in anchors:
        if (
            not isinstance(anchor, dict) or set(anchor) != {"path", "side", "line_start", "line_end"}
            or not isinstance(anchor["path"], str) or not anchor["path"]
            or anchor["side"] not in {"LEFT", "RIGHT"}
            or not all(isinstance(anchor[key], int) and not isinstance(anchor[key], bool)
                       for key in ("line_start", "line_end"))
            or not 1 <= anchor["line_start"] <= anchor["line_end"]
        ):
            raise ReplayError("defect key anchor must be {path, side, line_start, line_end} with a valid range")
    for key in ("root_cause", "wrong_result"):
        if not isinstance(value[key], str) or not value[key].strip():
            raise ReplayError(f"defect key {key} must be one nonempty sentence")
    return value


def anchor_matches(survivor: dict[str, Any], anchors: list[dict[str, Any]]) -> bool:
    """Condition (a): the tool's half of the match rule, on path, side and line alone."""
    line = survivor.get("line")
    return isinstance(line, int) and any(
        survivor.get("path") == anchor["path"] and survivor.get("side") == anchor["side"]
        and anchor["line_start"] <= line <= anchor["line_end"]
        for anchor in anchors
    )


def read_matches(path: Path | None) -> dict[tuple[str, str], dict[str, Any]]:
    """Condition (b): the recorded judgment of each anchored survivor against the key's two sentences."""
    if path is None:
        return {}
    value = read_object(path)
    rows = value.get("matches")
    if set(value) != {"matches"} or not isinstance(rows, list):
        raise ReplayError("match records must be an object holding only a matches list")
    matches: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if (
            not isinstance(row, dict) or set(row) != MATCH_FIELDS
            or not isinstance(row["run"], str) or not isinstance(row["survivor_id"], str)
            or not isinstance(row["root_cause_same"], bool) or not isinstance(row["wrong_result_same"], bool)
            or not isinstance(row["reason"], str) or not row["reason"].strip()
        ):
            raise ReplayError("each match record must be {run, survivor_id, root_cause_same, wrong_result_same, reason}")
        identity = (row["run"], row["survivor_id"])
        if identity in matches:
            raise ReplayError(f"match record is repeated: {identity[0]} {identity[1]}")
        matches[identity] = row
    return matches


def anchored_survivors(case_result: dict[str, Any], anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        survivor for survivor in case_result.get("survivors", [])
        if isinstance(survivor, dict) and anchor_matches(survivor, anchors)
    ]


def run_found(
    run: str, case_result: dict[str, Any], anchors: list[dict[str, Any]],
    matches: dict[tuple[str, str], dict[str, Any]],
) -> bool | None:
    """Whether a finished run found the defect; None while an anchored survivor has no match record."""
    found = False
    for survivor in anchored_survivors(case_result, anchors):
        row = matches.get((run, str(survivor.get("id"))))
        if row is None:
            return None
        found = found or (row["root_cause_same"] and row["wrong_result_same"])
    return found


def check_match_records(
    matches: dict[tuple[str, str], dict[str, Any]],
    finished: dict[str, dict[str, Any]],
    anchors: list[dict[str, Any]],
) -> None:
    """Refuse a record that names no finished run's survivor, or one outside every anchor."""
    for run, survivor_id in matches:
        case_result = finished.get(run)
        if case_result is None:
            raise ReplayError(f"match record names no finished run: {run}")
        survivor = next(
            (row for row in case_result.get("survivors", []) if str(row.get("id")) == survivor_id), None,
        )
        if survivor is None:
            raise ReplayError(f"match record names no survivor of {run}: {survivor_id}")
        if not anchor_matches(survivor, anchors):
            raise ReplayError(f"match record names a survivor outside every anchor: {run} {survivor_id}")


def classify(case_result: dict[str, Any]) -> str:
    """Sort one run's outcome so that billing can never read as a size failing."""
    status = case_result.get("status")
    if status == "completed":
        return "finished"
    error = str(case_result.get("error", ""))
    lowered = error.lower()
    if error.startswith(BILLING_PREFIX):
        return "void-billing"
    if "prompt is too long" in lowered or "command timed out" in lowered:
        return "not-finished"
    if "rate limit reached" in lowered or "authentication failed" in lowered or status == "invalid-leak":
        return "void-infrastructure"
    # Never counted on its own: the holder re-runs it, and a second one caps the rung.
    return "unrecognised"


def decide(rungs: list[tuple[int, bool]]) -> str:
    """Row 7's rule: the largest rung with no failed rung at or below it."""
    if not rungs or not rungs[0][1]:
        return "lowest-failed"
    largest = rungs[0][0]
    for rung, passed in rungs:
        if not passed:
            break
        largest = rung
    # A pass above a failure is not a safe line, so the loop stops at the first failure.
    return f"moves-to:{largest}" if largest > cr.MAX_FINDER_PROMPT_BYTES else "stays"


LADDER_FINDER_EFFORT = "high"
DEFAULT_RUNGS = (600_000, 1_200_000, 1_800_000, 2_400_000, 3_000_000)
LIVE_MATCH_SETTINGS = (
    "model", "finder_effort", "pass_structure", "finder_passes", "finder_candidates_per_pass",
)
RUN_FILE = re.compile(r"^(?P<label>natural|\d+)-r(?P<run>[12])-a(?P<attempt>\d+)$")


def workflow_cli_pin(workflow: Path | None = None) -> str:
    """The Claude CLI version the live reviewer's workflow installs."""
    text = (workflow or REVIEWER_WORKFLOW).read_text(encoding="utf-8")
    match = re.search(r"(?m)^\s*CLAUDE_CLI_VERSION:\s*[\"']?([^\"'\s#]+)", text)
    if match is None:
        raise ReplayError("the reviewer workflow pins no CLAUDE_CLI_VERSION")
    return match.group(1)


def live_reference() -> dict[str, Any]:
    """What the live reviewer runs, recomputed from this tree."""
    pin = workflow_cli_pin()
    live = cr.live_reviewer_settings(pin)
    return {
        "claude_cli_version": pin,
        **{name: live[name] for name in LIVE_MATCH_SETTINGS},
        "finder_prompt_sha256": file_digest(LIVE_FINDER_PROMPT),
    }


def _differences(recorded: dict[str, Any], current: dict[str, Any]) -> list[str]:
    return [
        f"{name}: ladder {json.dumps(recorded.get(name), sort_keys=True)}, "
        f"live {json.dumps(current.get(name), sort_keys=True)}"
        for name in sorted(current) if recorded.get(name) != current.get(name)
    ]


def tree_revision() -> str:
    try:
        return cr._decode(cr._run(["git", "-C", str(ROOT), "rev-parse", "HEAD"]).stdout).strip()
    except cr.ReviewError as exc:
        raise ReplayError(f"cannot name this tree's revision; pass --revision: {exc}") from exc


def live_match(executable: str | list[str], revision: str) -> dict[str, Any]:
    """Refuse before spending unless the ladder's runs are the live reviewer's."""
    reference = live_reference()
    record = reviewer_record(
        LIVE_FINDER_PROMPT, None, reference["claude_cli_version"], revision,
        single_pass=True, finder_effort=LADDER_FINDER_EFFORT,
    )
    replayed = {name: record.get(name) for name in reference}
    differences = _differences(replayed, reference)
    if differences:
        raise ReplayError("the ladder would not run the live reviewer: " + "; ".join(differences))
    try:
        cr.verify_claude_version(executable, reference["claude_cli_version"])
    except cr.ReviewError as exc:
        raise ReplayError(str(exc)) from exc
    return {**replayed, "harness_sha256": record["harness_sha256"]}


def ladder_verify(output_dir: Path) -> list[str]:
    """Each difference between the ladder's recorded live match and this tree's live reviewer."""
    recorded = read_object(output_dir / "ladder.json").get("live_match")
    if not isinstance(recorded, dict):
        raise ReplayError("ladder record has no live_match")
    return _differences(recorded, live_reference())


def _run_attempts(runs_dir: Path) -> list[dict[str, Any]]:
    """Every attempt on disk; one interrupted before its case finished counts as no attempt."""
    attempts = []
    for path in sorted(runs_dir.glob("*.json")) if runs_dir.is_dir() else []:
        match = RUN_FILE.match(path.stem)
        if match is None:
            raise ReplayError(f"unrecognised file among the ladder's runs: {path.name}")
        cases = read_object(path).get("cases")
        case_result = cases[0] if isinstance(cases, list) and cases else None
        attempts.append({
            "id": path.stem,
            "label": match["label"],
            "run": int(match["run"]),
            "attempt": int(match["attempt"]),
            "path": path,
            "case": case_result,
            "class": None if case_result is None else classify(case_result),
        })
    return sorted(attempts, key=lambda row: (row["label"], row["run"], row["attempt"]))


def _rung_runs(attempts: list[dict[str, Any]], label: str) -> dict[str, Any]:
    """A rung's two runs: each counted attempt, and whether a second unrecognised resolved the rung."""
    own = [row for row in attempts if row["label"] == label and row["class"] is not None]
    counted = {
        run: next((row for row in own if row["run"] == run and row["class"] in COUNTED_CLASSES), None)
        for run in (1, 2)
    }
    return {
        "attempts": own,
        "counted": counted,
        "voids": sum(row["class"].startswith("void-") for row in own),
        "unrecognised": [row for row in own if row["class"] == "unrecognised"],
    }


def _ladder_identity(
    export_root: Path, case: dict[str, Any], defect: dict[str, Any], rungs: list[int], seed: str,
    revision: str, plan: list[dict[str, Any]], match: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "repository": defect["repository"],
        "case": {name: case[name] for name in ("id", "number", "head", "base")},
        "export_manifest_sha256": file_digest(export_root / "manifest.json"),
        "defect": defect,
        "rungs": rungs,
        "pad_seed": seed,
        "revision": revision,
        "credential_source": "api-key-file",
        "plan": plan,
        "live_match": match,
    }


def _awaiting(label: str, rung: dict[str, Any], anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"run": row["id"], "survivor_id": str(survivor.get("id")),
         "root_cause": survivor.get("root_cause"), "wrong_result": survivor.get("wrong_result")}
        for row in rung["counted"].values() if row is not None and row["class"] == "finished"
        for survivor in anchored_survivors(row["case"], anchors)
    ]


def run_ladder(
    export_root: Path,
    defect_path: Path,
    api_key: str,
    executable: str | list[str],
    output_dir: Path,
    rungs: list[int],
    revision: str,
    *,
    seed: str = DEFAULT_PAD_SEED,
    matches_path: Path | None = None,
) -> dict[str, Any]:
    """Run the qualifying runs and then every rung twice, resuming from what the output holds."""
    manifest = validate_export(export_root, require_policy=True)
    case = single_case(manifest)
    defect = validate_defect_key(read_object(defect_path))
    if (
        defect["repository"] != manifest["repository"] or str(defect["number"]) != case["number"]
        or defect["head"] != case["head"] or defect["base"] != case["base"]
    ):
        raise ReplayError("defect key names another case than the export holds")
    anchors = defect["anchors"]
    # Nothing is spent until every rung composes and the runs would be the live reviewer's.
    plan = ladder_plan(export_root, rungs, seed)
    match = live_match(executable, revision)
    identity = _ladder_identity(export_root, case, defect, rungs, seed, revision, plan, match)
    ladder_path = output_dir / "ladder.json"
    if ladder_path.exists():
        stored = read_object(ladder_path)
        changed = sorted(name for name in identity if stored.get(name) != identity[name])
        if changed:
            raise ReplayError("ladder output belongs to another ladder or tree: " + ", ".join(changed))
    else:
        write_results(ladder_path, identity, api_key)
    matches = read_matches(matches_path)
    runs_dir = output_dir / "runs"
    pin = match["claude_cli_version"]
    for label, target in [("natural", None), *((str(rung), rung) for rung in rungs)]:
        for run in (1, 2):
            while True:
                rung = _rung_runs(_run_attempts(runs_dir), label)
                if rung["counted"][run] is not None or len(rung["unrecognised"]) >= 2:
                    break
                attempt = 1 + max(
                    (row["attempt"] for row in _run_attempts(runs_dir)
                     if row["label"] == label and row["run"] == run),
                    default=0,
                )
                run_id = f"{label}-r{run}-a{attempt}"
                record = run_replay(
                    export_root, runs_dir / f"{run_id}.json", LIVE_FINDER_PROMPT, None, executable, pin, revision,
                    single_pass=True, finder_effort=LADDER_FINDER_EFFORT, api_key=api_key,
                    pad_to_bytes=target, pad_seed=None if target is None else seed,
                )
                result_class = classify(record["cases"][0])
                rung = _rung_runs(_run_attempts(runs_dir), label)
                halt = {"status": "halted", "run": run_id, "class": result_class,
                        "error": record["cases"][0].get("error")}
                if result_class == "void-billing":
                    return {**halt, "reason": "a billing refusal is void; re-run after the credit renews"}
                if result_class == "void-infrastructure" and rung["voids"] >= 2:
                    return {**halt, "reason": "a second void at one rung halts the ladder for the holder"}
                if result_class == "unrecognised" and len(rung["unrecognised"]) < 2:
                    return {**halt, "reason": "an unrecognised outcome is re-run once after the owner confirms credit"}
        if label == "natural":
            rung = _rung_runs(_run_attempts(runs_dir), label)
            found = [
                False if row is None or row["class"] != "finished"
                else run_found(row["id"], row["case"], anchors, matches)
                for row in rung["counted"].values()
            ]
            if False in found:
                return {"status": "case-not-qualified", "found": found}
            if None in found:
                return {"status": "awaiting-matches", "survivors": _awaiting(label, rung, anchors)}
    return {"status": "complete", "output_dir": str(output_dir)}


def rate_card(rates_path: Path) -> dict[str, Any]:
    """The live model's current list-price card."""
    rows = read_object(rates_path).get("rates")
    card = next((
        row for row in rows or []
        if isinstance(row, dict) and row.get("vendor") == "claude"
        and row.get("model") == cr.DEFAULT_MODEL and row.get("effective_to") is None
    ), None)
    if card is None:
        raise ReplayError(f"rates name no current card for {cr.DEFAULT_MODEL}")
    return card


def usage_tokens(case_result: dict[str, Any] | None) -> dict[str, int] | None:
    usage = ((case_result or {}).get("finder_usage") or {}).get("coverage")
    if not isinstance(usage, dict) or not any(key.endswith("_tokens") for key in usage):
        return None
    return {
        "input": int(usage.get("input_tokens") or 0),
        "cache_creation": int(usage.get("cache_creation_input_tokens") or 0),
        "cache_read": int(usage.get("cache_read_input_tokens") or 0),
        "output": int(usage.get("output_tokens") or 0),
    }


def usage_cost(case_result: dict[str, Any] | None, card: dict[str, Any]) -> tuple[Decimal | None, str | None]:
    """A run's cost at list, and whether cache writes were priced by duration or the legacy rate."""
    tokens = usage_tokens(case_result)
    if tokens is None:
        return None, None
    usage = case_result["finder_usage"]["coverage"]
    rates = {name: Decimal(str(value)) for name, value in card["classes"].items()}
    cost = (
        tokens["input"] * rates["input"] + tokens["cache_read"] * rates["cache_read"]
        + tokens["output"] * rates["output"]
    )
    durations = usage.get("cache_creation")
    if isinstance(durations, dict) and (
        "ephemeral_5m_input_tokens" in durations or "ephemeral_1h_input_tokens" in durations
    ):
        cost += int(durations.get("ephemeral_5m_input_tokens") or 0) * rates["cache_write_5m"]
        cost += int(durations.get("ephemeral_1h_input_tokens") or 0) * rates["cache_write_1h"]
        basis = "duration"
    else:
        cost += tokens["cache_creation"] * rates["cache_creation"]
        basis = "legacy"
    return cost / Decimal(card["per_tokens"]), basis


def _money(value: Decimal | None) -> str | None:
    return None if value is None else str(value.quantize(Decimal("0.0001")))


def _run_row(row: dict[str, Any], found: bool | None, card: dict[str, Any]) -> dict[str, Any]:
    cost, basis = usage_cost(row["case"], card)
    return {
        "run": row["id"],
        "class": row["class"],
        "found": found,
        "tokens": usage_tokens(row["case"]),
        "cost_usd": _money(cost),
        "cost_basis": basis,
        "error": None if row["class"] == "finished" else row["case"].get("error"),
    }


def _measured(case_result: dict[str, Any] | None) -> int | None:
    sizes = (case_result or {}).get("finder_input_utf8_bytes")
    return max(sizes.values()) if isinstance(sizes, dict) and sizes else None


def _per_byte(tokens: float, size: int) -> str:
    return f"{tokens / size:.4f}"


def ladder_summary(
    output_dir: Path, matches_path: Path, rates_path: Path,
    references: list[tuple[str, Path]] | None = None,
) -> dict[str, Any]:
    """The results summary: each size's runs, their classes, tokens and cost, and row 7's decision."""
    ladder = read_object(output_dir / "ladder.json")
    anchors = ladder["defect"]["anchors"]
    matches = read_matches(matches_path)
    attempts = _run_attempts(output_dir / "runs")
    check_match_records(matches, {
        row["id"]: row["case"] for row in attempts if row["class"] == "finished"
    }, anchors)
    card = rate_card(rates_path)
    planned = {str(row["rung"]): row["measured_bytes"] for row in ladder["plan"]}
    rows = []
    total = Decimal(0)
    for label in ["natural", *(str(rung) for rung in ladder["rungs"])]:
        rung = _rung_runs(attempts, label)
        runs = []
        for row in rung["counted"].values():
            if row is None:
                continue
            found = run_found(row["id"], row["case"], anchors, matches) if row["class"] == "finished" else False
            if found is None:
                raise ReplayError(f"an anchored survivor of {row['id']} has no match record")
            runs.append(_run_row(row, found, card))
        if len(rung["unrecognised"]) >= 2:
            outcome = "not-passed"
        elif len(runs) < 2:
            outcome = "incomplete"
        else:
            outcome = "passed" if all(run["class"] == "finished" and run["found"] for run in runs) else "failed"
        counted_ids = {run["run"] for run in runs}
        uncounted = [_run_row(row, None, card) for row in rung["attempts"] if row["id"] not in counted_ids]
        for item in runs + uncounted:
            total += Decimal(item["cost_usd"] or 0)
        measured = next((_measured(row["case"]) for row in rung["counted"].values() if row is not None), None)
        rows.append({
            "label": label,
            "measured_bytes": measured if measured is not None else planned.get(label),
            "outcome": outcome,
            "runs": runs,
            "uncounted": uncounted,
        })
    qualified = rows[0]["outcome"] == "passed"
    rung_rows = rows[1:]
    if not qualified:
        decision = "case-not-qualified" if rows[0]["outcome"] in {"failed", "not-passed"} else "incomplete"
    elif any(row["outcome"] == "incomplete" for row in rung_rows):
        decision = "incomplete"
    else:
        decision = decide([(int(row["label"]), row["outcome"] == "passed") for row in rung_rows])
    reference_rows = []
    for label, path in references or []:
        record = read_object(path)
        case_result = (record.get("cases") or [None])[0]
        if not isinstance(case_result, dict):
            raise ReplayError(f"reference results hold no case: {path}")
        # Only sizes, outcome, tokens and cost: a private case's survivors are never quoted.
        cost, basis = usage_cost(case_result, card)
        total += cost or Decimal(0)
        reference_rows.append({
            "label": label,
            "measured_bytes": _measured(case_result),
            "class": classify(case_result),
            "tokens": usage_tokens(case_result),
            "cost_usd": _money(cost),
            "cost_basis": basis,
            "results_sha256": file_digest(path),
        })
    density = []
    finished = []
    for row in rung_rows:
        writes = [run["tokens"]["cache_creation"] for run in row["runs"]
                  if run["class"] == "finished" and run["tokens"] is not None]
        if writes and row["measured_bytes"]:
            finished.append((row["label"], row["measured_bytes"], sum(writes) / len(writes)))
    for index, (label, size, writes) in enumerate(finished):
        entry = {"label": label, "cache_creation_per_byte": _per_byte(writes, size)}
        if index:
            previous_label, previous_size, previous_writes = finished[index - 1]
            entry["since"] = previous_label
            entry["marginal_cache_creation_per_byte"] = _per_byte(writes - previous_writes, size - previous_size)
        density.append(entry)
    for row in reference_rows:
        if row["tokens"] is not None and row["measured_bytes"]:
            density.append({
                "label": row["label"],
                "cache_creation_per_byte": _per_byte(row["tokens"]["cache_creation"], row["measured_bytes"]),
            })
    summary = {
        "schema_version": 1,
        "repository": ladder["repository"],
        "case": ladder["case"],
        "rows": rows,
        "references": reference_rows,
        "padding_density": density,
        "decision": decision,
        "total_cost_usd": _money(total),
        "rate_card": {"model": card["model"], "effective_from": card.get("effective_from")},
        "live_match": ladder["live_match"],
        "digests": {
            "runs": {row["id"]: file_digest(row["path"]) for row in attempts},
            "export_manifest_sha256": ladder["export_manifest_sha256"],
            "harness_sha256": ladder["live_match"]["harness_sha256"],
            "revision": ladder["revision"],
        },
    }
    write_object(output_dir / "summary.json", summary)
    return summary


def summary_table(summary: dict[str, Any]) -> str:
    """The summary as a Markdown table for the results comment."""
    def cell(value: Any) -> str:
        return "-" if value is None else str(value)

    lines = [
        "| Size | Bytes | Run | Class | Found | Input | Cache write | Cache read | Output | Cost (USD) |",
        "|---|---:|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in summary["rows"]:
        for run in row["runs"] + row["uncounted"]:
            tokens = run["tokens"] or {}
            counted = "" if run in row["runs"] else " (uncounted)"
            lines.append(
                f"| {row['label']} | {cell(row['measured_bytes'])} | {run['run']}{counted} | {run['class']} "
                f"| {cell(run['found'])} | {cell(tokens.get('input'))} | {cell(tokens.get('cache_creation'))} "
                f"| {cell(tokens.get('cache_read'))} | {cell(tokens.get('output'))} | {cell(run['cost_usd'])} |"
            )
    for row in summary["references"]:
        tokens = row["tokens"] or {}
        lines.append(
            f"| {row['label']} | {cell(row['measured_bytes'])} | as merged | {row['class']} | - "
            f"| {cell(tokens.get('input'))} | {cell(tokens.get('cache_creation'))} "
            f"| {cell(tokens.get('cache_read'))} | {cell(tokens.get('output'))} | {cell(row['cost_usd'])} |"
        )
    lines.append("")
    lines.append("Rung outcomes: " + ", ".join(f"{row['label']} {row['outcome']}" for row in summary["rows"]) + ".")
    for row in summary["rows"]:
        for run in row["runs"] + row["uncounted"]:
            if run["class"] == "unrecognised":
                lines.append(f"Unrecognised outcome of {run['run']}: {run['error']}")
    lines.append("Padding density (cache-creation tokens per byte): " + "; ".join(
        f"{entry['label']} {entry['cache_creation_per_byte']}"
        + (f" (marginal since {entry['since']}: {entry['marginal_cache_creation_per_byte']})"
           if "since" in entry else "")
        for entry in summary["padding_density"]
    ) + ".")
    lines.append(f"Total cost at list: ${summary['total_cost_usd']} ({summary['rate_card']['model']}).")
    lines.append(f"Decision: {summary['decision']}.")
    return "\n".join(lines) + "\n"


def _is_pass_tool_result(path: Path, pass_root: Path) -> bool:
    projects = (pass_root / "profile" / "claude" / "projects").resolve()
    try:
        relative = path.relative_to(projects)
    except ValueError:
        return False
    parts = relative.parts
    return len(parts) >= 4 and parts[2] == "tool-results" and path.is_file()


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _outside_trace_reads(
    trace: list[dict[str, Any]],
    snapshot: Path,
    inputs: Path,
    pass_root: Path,
    readable: Path | None = None,
) -> list[str]:
    outside = []
    # A case's summary folder is in bounds only for the case that summarised.
    allowed = (snapshot.resolve(), inputs.resolve(), *(() if readable is None else (readable.resolve(),)))
    for event in trace:
        tool = event.get("tool")
        event_input = event.get("input")
        if tool not in {"Read", "Glob", "Grep"} or not isinstance(event_input, dict):
            continue
        for key in ("file_path", "path"):
            raw = event_input.get(key)
            if not isinstance(raw, str) or not raw:
                continue
            path = Path(raw)
            resolved = (
                path.resolve()
                if path.is_absolute()
                else (pass_root / "work" / path).resolve()
            )
            if any(_within(resolved, root) for root in allowed):
                continue
            if _is_pass_tool_result(resolved, pass_root):
                continue
            outside.append(str(resolved))
    return sorted(set(outside))


def _unscorable(results: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "repository": results.get("repository"),
        "status": "unscorable",
        "pass": False,
        "reason": reason,
        "reviewer": results.get("reviewer"),
    }


def grade_replay(results_path: Path, key_path: Path, decisions_path: Path) -> dict[str, Any]:
    results = read_object(results_path)
    key = read_object(key_path)
    decisions = read_object(decisions_path)
    if results.get("repository") != key.get("repository"):
        raise ReplayError("answer key belongs to another repository")
    profile = key.get("profile")
    if profile == "change-proof":
        return _unscorable(results, "change-proof has no owner-set replay bar")
    if profile not in {"tradecraft", "product"}:
        return _unscorable(results, "answer key has no recognized repository profile")
    manifest_cases = results.get("manifest_cases")
    result_cases = results.get("cases")
    if not isinstance(manifest_cases, list) or not isinstance(result_cases, list):
        return _unscorable(results, "results do not carry the frozen manifest population")
    expected = {
        (case.get("case_id"), case.get("head"), case.get("base"))
        for case in manifest_cases if isinstance(case, dict)
    }
    observed = {
        (case.get("case_id"), case.get("head"), case.get("base"))
        for case in result_cases if isinstance(case, dict)
    }
    if len(expected) != len(manifest_cases) or expected != observed or len(observed) != len(result_cases):
        return _unscorable(results, "results do not cover every frozen manifest case exactly once")
    if not results.get("complete") or any(case.get("status") != "completed" for case in result_cases):
        return _unscorable(results, "one or more frozen cases errored, leaked, or did not finish")
    survivors = {
        (case.get("case_id"), row.get("id")): row
        for case in result_cases if isinstance(case, dict)
        for row in case.get("survivors", []) if isinstance(row, dict)
    }
    rows = decisions.get("classifications")
    if not isinstance(rows, list):
        raise ReplayError("grading decisions have no classifications")
    classified = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ReplayError("grading classification is malformed")
        identity = (row.get("case_id"), row.get("candidate_id"))
        if identity not in survivors or identity in classified:
            raise ReplayError("grading classification is unknown or repeated")
        if not isinstance(row.get("noise"), bool) or not isinstance(row.get("reason"), str):
            raise ReplayError("grading classification lacks noise or reason")
        defect = row.get("defect_id")
        if defect is not None and not isinstance(defect, str):
            raise ReplayError("grading defect_id must be a string or null")
        classified[identity] = row
    if set(classified) != set(survivors):
        raise ReplayError("every survivor must be classified exactly once")
    defect_rows = key.get("defects")
    if not isinstance(defect_rows, list):
        raise ReplayError("answer key has no defects")
    defects = {}
    for row in defect_rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ReplayError("answer-key defect is malformed")
        categories = row.get("categories")
        if not isinstance(categories, list) or not all(
            category in ("fixed", "unique", "harmful") for category in categories
        ):
            raise ReplayError("answer-key defect has an invalid category")
        defects[row["id"]] = frozenset(categories)
    matched = set()
    noise = 0
    for row in classified.values():
        if row["noise"]:
            noise += 1
        defect = row.get("defect_id")
        if defect is not None:
            if defect not in defects:
                raise ReplayError(f"classification names unknown defect {defect}")
            matched.add(defect)
    counts = {
        category: sum(category in defects[identifier] for identifier in matched)
        for category in ("fixed", "unique", "harmful")
    }
    thresholds = key.get("thresholds")
    if not isinstance(thresholds, dict):
        return _unscorable(results, "answer key has no thresholds")
    fixed_total = sum("fixed" in categories for categories in defects.values())
    unique_total = sum("unique" in categories for categories in defects.values())
    harmful_total = sum("harmful" in categories for categories in defects.values())
    noise_limit = thresholds.get("maximum_noise_fraction")
    if not isinstance(noise_limit, dict) or set(noise_limit) != {"numerator", "denominator"}:
        return _unscorable(results, "noise threshold must be an exact fraction")
    if not all(isinstance(noise_limit.get(key), int) for key in ("numerator", "denominator")):
        return _unscorable(results, "noise threshold is not numeric")
    if noise_limit["numerator"] < 0 or noise_limit["denominator"] <= 0:
        return _unscorable(results, "noise threshold is not a valid fraction")
    checks = {}
    if profile == "tradecraft":
        required = {"minimum_fixed", "minimum_unique", "maximum_harmful", "maximum_noise_fraction"}
        if set(thresholds) != required:
            return _unscorable(results, "tradecraft answer key does not carry every affirmed bar")
        if (
            thresholds.get("minimum_fixed") != 12
            or thresholds.get("minimum_unique") != 7
            or thresholds.get("maximum_harmful") != 0
            or noise_limit != {"numerator": 1, "denominator": 20}
            or fixed_total != 17
            or unique_total != 10
            or harmful_total != 4
        ):
            return _unscorable(results, "tradecraft answer key does not match the affirmed population and bars")
        checks["fixed"] = counts["fixed"] >= thresholds["minimum_fixed"]
        checks["unique"] = counts["unique"] >= thresholds["minimum_unique"]
        checks["harmful"] = counts["harmful"] <= thresholds["maximum_harmful"]
    else:
        required = {"minimum_recall_fraction", "maximum_noise_fraction"}
        recall = thresholds.get("minimum_recall_fraction")
        if (
            set(thresholds) != required
            or recall != {"numerator": 7, "denominator": 10}
            or fixed_total <= 0
        ):
            return _unscorable(results, "product answer key does not carry its affirmed recall and Greptile noise bars")
        checks["recall"] = (
            counts["fixed"] * recall["denominator"]
            >= fixed_total * recall["numerator"]
        )
    total = len(survivors)
    checks["noise"] = total == 0 or (
        noise * noise_limit["denominator"]
        <= total * noise_limit["numerator"]
    )
    return {
        "schema_version": 1,
        "repository": results["repository"],
        "status": "scored",
        "pass": bool(checks) and all(checks.values()),
        "checks": checks,
        "caught": counts,
        "noise": {"count": noise, "survivors": total},
        "classified": len(classified),
        "reviewer": results.get("reviewer"),
    }


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description="Export, run or grade a connected-review replay")
    commands = cli.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--manifest", required=True, type=Path)
    export.add_argument("--output", required=True, type=Path)
    run = commands.add_parser("run")
    run.add_argument("--export", required=True, type=Path)
    run.add_argument("--output", required=True, type=Path)
    run.add_argument("--finder-prompt", required=True, type=Path)
    run.add_argument("--checker-prompt", required=True, type=Path)
    run.add_argument("--claude")
    run.add_argument("--claude-version", default=cr.DEFAULT_CLAUDE_VERSION)
    run.add_argument("--revision", required=True)
    run.add_argument("--resume", type=Path)
    run.add_argument("--single-pass", action="store_true")
    run.add_argument("--finder-effort", choices=EFFORT_LEVELS)
    run.add_argument("--checker-effort", choices=EFFORT_LEVELS)
    run.add_argument("--preload-changed-files", action="store_true")
    run.add_argument("--summarise-deleted-files", action="store_true")
    run.add_argument("--summary-threshold-bytes", type=int)
    run.add_argument("--api-key-file", type=Path)
    run.add_argument("--pad-to-bytes", type=int)
    run.add_argument("--pad-seed")
    plan = commands.add_parser("ladder-plan")
    plan.add_argument("--export", required=True, type=Path)
    plan.add_argument("--rungs", required=True)
    plan.add_argument("--pad-seed", default=DEFAULT_PAD_SEED)
    ladder = commands.add_parser("ladder")
    ladder.add_argument("--export", required=True, type=Path)
    ladder.add_argument("--defect", required=True, type=Path)
    ladder.add_argument("--api-key-file", required=True, type=Path)
    ladder.add_argument("--claude")
    ladder.add_argument("--output-dir", required=True, type=Path)
    ladder.add_argument("--rungs", default=",".join(str(rung) for rung in DEFAULT_RUNGS))
    ladder.add_argument("--pad-seed", default=DEFAULT_PAD_SEED)
    ladder.add_argument("--matches", type=Path)
    ladder.add_argument("--revision")
    verify = commands.add_parser("ladder-verify")
    verify.add_argument("--output-dir", required=True, type=Path)
    summary = commands.add_parser("ladder-summary")
    summary.add_argument("--output-dir", required=True, type=Path)
    summary.add_argument("--matches", required=True, type=Path)
    summary.add_argument("--rates", default=ROOT / "lib" / "rates.json", type=Path)
    summary.add_argument("--reference", action="append", default=[], metavar="LABEL=RESULTS")
    grade = commands.add_parser("grade")
    grade.add_argument("--results", required=True, type=Path)
    grade.add_argument("--answer-key", required=True, type=Path)
    grade.add_argument("--decisions", required=True, type=Path)
    grade.add_argument("--output", required=True, type=Path)
    return cli


def main(argv: Iterable[str] | None = None) -> int:
    utf8_stdio()
    args = parser().parse_args(argv)
    secret = None
    try:
        if args.command == "export":
            result = export_replay(args.manifest, args.output)
        elif args.command == "run":
            if args.api_key_file is not None:
                secret = read_api_key_file(args.api_key_file)
            executable = cr.resolve_command("claude", args.claude)
            result = run_replay(
                args.export, args.output, args.finder_prompt, args.checker_prompt,
                executable, args.claude_version, args.revision, args.resume,
                single_pass=args.single_pass,
                finder_effort=args.finder_effort,
                checker_effort=args.checker_effort,
                preload_changed_files=args.preload_changed_files,
                summarise_deleted_files=args.summarise_deleted_files,
                summary_threshold_bytes=args.summary_threshold_bytes,
                api_key=secret,
                pad_to_bytes=args.pad_to_bytes,
                pad_seed=args.pad_seed,
            )
        elif args.command == "ladder-plan":
            result = {"rungs": ladder_plan(args.export, parse_rungs(args.rungs), args.pad_seed)}
        elif args.command == "ladder":
            secret = read_api_key_file(args.api_key_file)
            result = run_ladder(
                args.export, args.defect, secret, cr.resolve_command("claude", args.claude),
                args.output_dir, parse_rungs(args.rungs), args.revision or tree_revision(),
                seed=args.pad_seed, matches_path=args.matches,
            )
        elif args.command == "ladder-verify":
            differences = ladder_verify(args.output_dir)
            print(json.dumps({
                "status": "differs" if differences else "verified", "differences": differences,
            }, ensure_ascii=True, sort_keys=True))
            return 1 if differences else 0
        elif args.command == "ladder-summary":
            references = []
            for item in args.reference:
                label, separator, path = item.partition("=")
                if not separator or not label or not path:
                    raise ReplayError(f"--reference must be LABEL=RESULTS: {item}")
                references.append((label, Path(path)))
            summary = ladder_summary(args.output_dir, args.matches, args.rates, references)
            print(summary_table(summary), end="")
            return 0
        else:
            result = grade_replay(args.results, args.answer_key, args.decisions)
            write_object(args.output, result)
        refuse_secret(result, secret)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0
    except (ReplayError, cr.ReviewError, cr.CliError, OSError) as exc:
        print(json.dumps({"status": "failed", "cause": str(exc)}, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
