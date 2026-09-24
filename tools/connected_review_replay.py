#!/usr/bin/env python3
"""Export, run and grade leak-resistant connected-review replays."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
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
        exported.append({
            **case,
            "snapshot": f"cases/{case['id']}/snapshot",
            "diff": f"cases/{case['id']}/input/pull-request.diff",
            "rules": f"cases/{case['id']}/input/repository-rules.md",
            "snapshot_sha256": tree_digest(snapshot),
            "diff_sha256": file_digest(diff_path),
            "rules_sha256": file_digest(rules_path),
        })
    manifest = {
        "schema_version": 1,
        "repository": repository,
        "cases": exported,
    }
    write_object(output / "manifest.json", manifest)
    return manifest


def validate_export(root: Path) -> dict[str, Any]:
    manifest = read_object(root / "manifest.json")
    if set(manifest) != {"schema_version", "repository", "cases"}:
        raise ReplayError("export manifest contains an unrecognized field")
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("cases"), list):
        raise ReplayError("export manifest is malformed")
    for case in manifest["cases"]:
        if not isinstance(case, dict):
            raise ReplayError("export case is malformed")
        expected = {
            "id", "number", "head", "base", "snapshot", "diff", "rules",
            "snapshot_sha256", "diff_sha256", "rules_sha256",
        }
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
    return manifest


def run_replay(
    export_root: Path,
    output: Path,
    finder_prompt: Path,
    checker_prompt: Path,
    executable: str | list[str],
    version: str,
    revision: str,
) -> dict[str, Any]:
    manifest = validate_export(export_root)
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if not token:
        raise ReplayError("CLAUDE_CODE_OAUTH_TOKEN is unavailable")
    cr.verify_managed_settings()
    cr.verify_claude_version(executable, version)
    finder_text = finder_prompt.read_text(encoding="utf-8")
    checker_text = checker_prompt.read_text(encoding="utf-8")
    settings = cr.reviewer_settings(version)
    record = {
        "schema_version": 1,
        "repository": manifest["repository"],
        "manifest_cases": [
            {"case_id": case["id"], "head": case["head"], "base": case["base"]}
            for case in manifest["cases"]
        ],
        "reviewer": {
            "revision": revision,
            **settings,
            "settings_sha256": hashlib.sha256(cr._json_bytes(settings)).hexdigest(),
            "finder_prompt_sha256": file_digest(finder_prompt),
            "checker_prompt_sha256": file_digest(checker_prompt),
            "harness_sha256": file_digest(Path(cr.__file__)),
        },
        "complete": False,
        "cases": [],
    }
    write_object(output, record)
    for case in manifest["cases"]:
        case_result: dict[str, Any] = {
            "case_id": case["id"], "head": case["head"], "base": case["base"],
        }
        try:
            with tempfile.TemporaryDirectory(prefix="connected-review-replay-case-") as temporary:
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
                shutil.copytree((export_root / case["diff"]).parent, input_dir)
                diff_path = input_dir / "pull-request.diff"
                rules_path = input_dir / "repository-rules.md"
                diff_text = diff_path.read_text(encoding="utf-8", errors="replace")
                rules_text = rules_path.read_text(encoding="utf-8", errors="replace")
                finder_value, finder_usage, finder_trace = cr.run_pass(
                    executable, case_root / "finder", snapshot,
                    cr._pass_prompt(finder_text, snapshot, diff_text, rules_text),
                    cr.FINDER_SCHEMA, token,
                    effort=cr.FINDER_EFFORT,
                )
                lines = cr.changed_lines(diff_text)
                candidates = cr.validate_candidates(finder_value, lines)
                checker_value, checker_usage, checker_trace = cr.run_pass(
                    executable, case_root / "checker", snapshot,
                    cr._pass_prompt(
                        checker_text, snapshot, diff_text, rules_text, candidates,
                    ),
                    cr.CHECKER_SCHEMA, token,
                    effort=cr.CHECKER_EFFORT,
                )
                survivors = cr.validate_decisions(checker_value, candidates, lines)
                leaks = _outside_trace_reads(finder_trace + checker_trace, snapshot)
                case_result.update({
                    "status": "invalid-leak" if leaks else "completed",
                    "survivors": survivors,
                    "finder_usage": finder_usage,
                    "checker_usage": checker_usage,
                    "finder_trace": finder_trace,
                    "checker_trace": checker_trace,
                    "outside_reads": leaks,
                    "canaries": canary_record,
                })
        except (ReplayError, cr.ReviewError, OSError) as exc:
            case_result.update({"status": "error", "error": str(exc)})
        record["cases"].append(case_result)
        record["complete"] = (
            len(record["cases"]) == len(record["manifest_cases"])
            and all(case.get("status") == "completed" for case in record["cases"])
        )
        write_object(output, record)
    return record


def _outside_trace_reads(trace: list[dict[str, Any]], snapshot: Path) -> list[str]:
    outside = []
    snapshot = snapshot.resolve()
    for event in trace:
        tool = event.get("tool")
        inputs = event.get("input")
        if tool not in {"Read", "Glob", "Grep"} or not isinstance(inputs, dict):
            continue
        for key in ("file_path", "path"):
            raw = inputs.get(key)
            if not isinstance(raw, str) or not raw:
                continue
            path = Path(raw)
            resolved = path.resolve() if path.is_absolute() else path.resolve()
            try:
                resolved.relative_to(snapshot)
            except ValueError:
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
    grade = commands.add_parser("grade")
    grade.add_argument("--results", required=True, type=Path)
    grade.add_argument("--answer-key", required=True, type=Path)
    grade.add_argument("--decisions", required=True, type=Path)
    grade.add_argument("--output", required=True, type=Path)
    return cli


def main(argv: Iterable[str] | None = None) -> int:
    utf8_stdio()
    args = parser().parse_args(argv)
    try:
        if args.command == "export":
            result = export_replay(args.manifest, args.output)
        elif args.command == "run":
            executable = cr.resolve_command("claude", args.claude)
            result = run_replay(
                args.export, args.output, args.finder_prompt, args.checker_prompt,
                executable, args.claude_version, args.revision,
            )
        else:
            result = grade_replay(args.results, args.answer_key, args.decisions)
            write_object(args.output, result)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0
    except (ReplayError, cr.ReviewError, cr.CliError, OSError) as exc:
        print(json.dumps({"status": "failed", "cause": str(exc)}, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
