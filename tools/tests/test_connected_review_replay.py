from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import connected_review_replay as replay  # noqa: E402


HEAD = "a" * 40
BASE = "b" * 40


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def source_manifest(cases=1) -> dict:
    return {
        "schema_version": 1,
        "repository": "owner/repo",
        "cases": [
            {"id": f"pr-{index}", "number": index, "head": str(index) * 40, "base": BASE}
            for index in range(1, cases + 1)
        ],
    }


def archive(filename="app.py") -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as output:
        info = tarfile.TarInfo(f"repo-sha/{filename}")
        data = b"print('new')\n"
        info.size = len(data)
        output.addfile(info, io.BytesIO(data))
    return stream.getvalue()


def test_source_manifest_refuses_answer_keys_and_record_fields():
    manifest = source_manifest()
    manifest["answer_key"] = {"defect": "leak"}
    with pytest.raises(replay.ReplayError, match="may contain only"):
        replay.validate_source_manifest(manifest)
    manifest = source_manifest()
    manifest["cases"][0]["expected"] = "finding"
    with pytest.raises(replay.ReplayError, match="only id"):
        replay.validate_source_manifest(manifest)


def test_export_contains_only_snapshot_diff_rules_and_hashes(tmp_path, monkeypatch):
    source = tmp_path / "source.json"
    output = tmp_path / "export"
    write(source, source_manifest())

    def gh(endpoint, **_kwargs):
        if "/tarball/" in endpoint:
            return archive()
        if "/compare/" in endpoint:
            return b"diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+new\n"
        raise AssertionError(endpoint)

    monkeypatch.setattr(replay.cr, "gh_bytes", gh)
    monkeypatch.setattr(
        replay.cr, "repository_review_rules",
        lambda *_: "## Code Review Rules\n\nRepository rule.\n",
    )
    result = replay.export_replay(source, output)
    assert result["repository"] == "owner/repo"
    assert (output / "cases/pr-1/snapshot/app.py").is_file()
    assert set(result["cases"][0]) == {
        "id", "number", "head", "base", "snapshot", "diff", "rules",
        "snapshot_sha256", "diff_sha256", "rules_sha256",
    }
    assert "answer" not in json.dumps(result).lower()
    assert replay.validate_export(output) == result


def test_export_validation_detects_changed_bytes(tmp_path, monkeypatch):
    source = tmp_path / "source.json"
    output = tmp_path / "export"
    write(source, source_manifest())
    monkeypatch.setattr(
        replay.cr, "gh_bytes",
        lambda endpoint, **_kwargs: archive() if "/tarball/" in endpoint else b"diff",
    )
    monkeypatch.setattr(replay.cr, "repository_review_rules", lambda *_: "No rules.")
    replay.export_replay(source, output)
    (output / "cases/pr-1/snapshot/app.py").write_text("changed", encoding="utf-8")
    with pytest.raises(replay.ReplayError, match="no longer matches"):
        replay.validate_export(output)


def build_export(root: Path, cases=2) -> Path:
    records = []
    for index in range(1, cases + 1):
        case_root = root / "cases" / f"pr-{index}"
        snapshot = case_root / "snapshot"
        inputs = case_root / "input"
        snapshot.mkdir(parents=True)
        inputs.mkdir()
        (snapshot / f"only-{index}.py").write_text("value = 1\n", encoding="utf-8")
        diff = inputs / "pull-request.diff"
        rules = inputs / "repository-rules.md"
        diff.write_text(
            f"diff --git a/only-{index}.py b/only-{index}.py\n"
            f"--- a/only-{index}.py\n+++ b/only-{index}.py\n@@ -1 +1 @@\n-old\n+new\n",
            encoding="utf-8",
        )
        rules.write_text("## Code Review Rules\n\nLocal.\n", encoding="utf-8")
        records.append({
            "id": f"pr-{index}", "number": str(index), "head": str(index) * 40,
            "base": BASE, "snapshot": f"cases/pr-{index}/snapshot",
            "diff": f"cases/pr-{index}/input/pull-request.diff",
            "rules": f"cases/pr-{index}/input/repository-rules.md",
            "snapshot_sha256": replay.tree_digest(snapshot),
            "diff_sha256": replay.file_digest(diff),
            "rules_sha256": replay.file_digest(rules),
        })
    write(root / "manifest.json", {
        "schema_version": 1, "repository": "owner/repo", "cases": records,
    })
    return root


def test_run_records_each_case_error_incrementally_and_isolates_other_trees(tmp_path, monkeypatch):
    export = build_export(tmp_path / "export")
    output = tmp_path / "results.json"
    finder = tmp_path / "finder.md"
    checker = tmp_path / "checker.md"
    finder.write_text("finder", encoding="utf-8")
    checker.write_text("checker", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth")
    monkeypatch.setattr(replay.cr, "verify_managed_settings", lambda: None)
    monkeypatch.setattr(replay.cr, "verify_claude_version", lambda *_: None)
    snapshots = []
    efforts = []
    calls = 0

    def run(_executable, _root, snapshot, _prompt, schema, _token, *, effort):
        nonlocal calls
        calls += 1
        snapshots.append(sorted(path.name for path in snapshot.iterdir()))
        efforts.append(effort)
        if calls == 3:
            raise replay.cr.ReviewError("case-specific failure")
        if schema is replay.cr.FINDER_SCHEMA:
            return {"candidates": []}, {"input_tokens": 1}, []
        return {"decisions": []}, {"input_tokens": 2}, []

    monkeypatch.setattr(replay.cr, "run_pass", run)
    actual_write = replay.write_object
    writes = []

    def capture(path, value):
        writes.append(copy.deepcopy(value))
        actual_write(path, value)

    monkeypatch.setattr(replay, "write_object", capture)
    result = replay.run_replay(
        export, output, finder, checker, ["claude.cmd"],
        replay.cr.DEFAULT_CLAUDE_VERSION, HEAD,
    )
    assert snapshots == [["only-1.py"], ["only-1.py"], ["only-2.py"]]
    assert efforts == [
        replay.cr.FINDER_EFFORT, replay.cr.CHECKER_EFFORT, replay.cr.FINDER_EFFORT,
    ]
    assert result["reviewer"]["finder_effort"] == "max"
    assert result["reviewer"]["checker_effort"] == "high"
    settings = replay.cr.reviewer_settings(replay.cr.DEFAULT_CLAUDE_VERSION)
    assert result["reviewer"]["settings_sha256"] == hashlib.sha256(
        replay.cr._json_bytes(settings)
    ).hexdigest()
    assert [len(record["cases"]) for record in writes] == [0, 1, 2]
    assert result["cases"][0]["status"] == "completed"
    assert result["cases"][1] == {
        "case_id": "pr-2", "head": "2" * 40, "base": BASE,
        "status": "error", "error": "case-specific failure",
    }
    assert result["complete"] is False


def test_run_records_canaries_tool_trace_and_invalidates_outside_read(tmp_path, monkeypatch):
    export = build_export(tmp_path / "export", cases=1)
    output = tmp_path / "results.json"
    finder = tmp_path / "finder.md"
    checker = tmp_path / "checker.md"
    finder.write_text("finder", encoding="utf-8")
    checker.write_text("checker", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth")
    monkeypatch.setattr(replay.cr, "verify_managed_settings", lambda: None)
    monkeypatch.setattr(replay.cr, "verify_claude_version", lambda *_: None)

    def run(_executable, _root, snapshot, _prompt, schema, _token, *, effort):
        expected = (
            replay.cr.FINDER_EFFORT
            if schema is replay.cr.FINDER_SCHEMA else replay.cr.CHECKER_EFFORT
        )
        assert effort == expected
        if schema is replay.cr.FINDER_SCHEMA:
            trace = [{"tool": "Read", "input": {"file_path": str(snapshot / "only-1.py")}}]
            return {"candidates": []}, {}, trace
        return {"decisions": []}, {}, [
            {"tool": "Read", "input": {"file_path": str(tmp_path / "outside.txt")}},
        ]

    monkeypatch.setattr(replay.cr, "run_pass", run)
    result = replay.run_replay(
        export, output, finder, checker, "claude",
        replay.cr.DEFAULT_CLAUDE_VERSION, HEAD,
    )
    case = result["cases"][0]
    assert case["status"] == "invalid-leak"
    assert case["outside_reads"] == [str((tmp_path / "outside.txt").resolve())]
    assert set(case["canaries"]) == {"answer-key", "pull-request-thread", "later-commit"}
    assert case["finder_trace"] and case["checker_trace"]
    assert result["complete"] is False


def result_record(survivors: list[dict], *, complete=True, include_case=True) -> dict:
    cases = [{
        "case_id": "pr-1", "head": HEAD, "base": BASE,
        "status": "completed", "survivors": survivors,
    }] if include_case else []
    return {
        "schema_version": 1,
        "repository": "owner/repo",
        "manifest_cases": [{"case_id": "pr-1", "head": HEAD, "base": BASE}],
        "reviewer": {"revision": HEAD},
        "complete": complete,
        "cases": cases,
    }


def tradecraft_key() -> dict:
    defects = [
        {"id": f"f{index}", "categories": ["fixed", "unique"] if index < 10 else ["fixed"]}
        for index in range(17)
    ]
    defects.extend({"id": f"h{index}", "categories": ["harmful"]} for index in range(4))
    return {
        "repository": "owner/repo",
        "profile": "tradecraft",
        "thresholds": {
            "minimum_fixed": 12,
            "minimum_unique": 7,
            "maximum_harmful": 0,
            "maximum_noise_fraction": {"numerator": 1, "denominator": 20},
        },
        "defects": defects,
    }


def classifications(count: int) -> list[dict]:
    return [{
        "case_id": "pr-1", "candidate_id": f"candidate-{index}",
        "defect_id": f"f{index}", "noise": False, "reason": "same defect and place",
    } for index in range(count)]


def grade_files(tmp_path, results, key, rows):
    result_path = tmp_path / "results.json"
    key_path = tmp_path / "key.json"
    decisions_path = tmp_path / "decisions.json"
    write(result_path, results)
    write(key_path, key)
    write(decisions_path, {"classifications": rows})
    return replay.grade_replay(result_path, key_path, decisions_path)


def test_tradecraft_grade_requires_every_affirmed_bar_and_population(tmp_path):
    survivors = [{"id": f"candidate-{index}"} for index in range(12)]
    score = grade_files(tmp_path, result_record(survivors), tradecraft_key(), classifications(12))
    assert score["status"] == "scored" and score["pass"] is True
    key = tradecraft_key()
    del key["thresholds"]["maximum_harmful"]
    score = grade_files(tmp_path, result_record(survivors), key, classifications(12))
    assert score["status"] == "unscorable" and score["pass"] is False


def test_grade_requires_every_frozen_manifest_case(tmp_path):
    score = grade_files(
        tmp_path, result_record([], complete=False, include_case=False), tradecraft_key(), [],
    )
    assert score["status"] == "unscorable"
    assert "every frozen manifest case" in score["reason"]


def test_grade_requires_independent_classification_for_every_survivor(tmp_path):
    with pytest.raises(replay.ReplayError, match="every survivor"):
        grade_files(
            tmp_path, result_record([{"id": "candidate-0"}]), tradecraft_key(), [],
        )


def test_product_key_requires_recall_and_own_greptile_noise_baseline(tmp_path):
    key = {
        "repository": "owner/repo",
        "profile": "product",
        "thresholds": {
            "minimum_recall_fraction": {"numerator": 7, "denominator": 10},
            "maximum_noise_fraction": {"numerator": 0, "denominator": 1},
        },
        "defects": [{"id": f"f{index}", "categories": ["fixed"]} for index in range(10)],
    }
    score = grade_files(
        tmp_path, result_record([{"id": "candidate-0"}]), key, classifications(1),
    )
    assert score["status"] == "scored" and score["checks"]["recall"] is False
    del key["thresholds"]["maximum_noise_fraction"]
    score = grade_files(
        tmp_path, result_record([{"id": "candidate-0"}]), key, classifications(1),
    )
    assert score["status"] == "unscorable"


def test_change_proof_remains_unscorable_until_owner_sets_bar(tmp_path):
    key = {"repository": "owner/repo", "profile": "change-proof"}
    score = grade_files(tmp_path, result_record([]), key, [])
    assert score["status"] == "unscorable" and score["pass"] is False
    assert "owner-set" in score["reason"]
