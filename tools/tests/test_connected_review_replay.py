from __future__ import annotations

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


def source_manifest() -> dict:
    return {
        "schema_version": 1,
        "repository": "owner/repo",
        "cases": [{"id": "pr-1", "number": 1, "head": HEAD, "base": BASE}],
    }


def archive() -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as output:
        info = tarfile.TarInfo("repo-sha/app.py")
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
            return b"diff --git a/app.py b/app.py\n+++ b/app.py\n@@ -1 +1 @@\n+print('new')\n"
        raise AssertionError(endpoint)

    monkeypatch.setattr(replay.cr, "gh_bytes", gh)
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
        replay.cr,
        "gh_bytes",
        lambda endpoint, **_kwargs: archive() if "/tarball/" in endpoint else b"diff",
    )
    replay.export_replay(source, output)
    (output / "cases/pr-1/snapshot/app.py").write_text("changed", encoding="utf-8")
    with pytest.raises(replay.ReplayError, match="no longer matches"):
        replay.validate_export(output)


def result_record(survivors: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "repository": "owner/repo",
        "reviewer": {"revision": HEAD},
        "cases": [{"case_id": "pr-1", "survivors": survivors}],
    }


def answer_key() -> dict:
    return {
        "repository": "owner/repo",
        "thresholds": {
            "minimum_fixed": 1,
            "minimum_unique": 1,
            "maximum_noise_fraction": {"numerator": 1, "denominator": 20},
        },
        "defects": [
            {"id": "d1", "categories": ["fixed", "unique"]},
            {"id": "harm", "categories": ["harmful"]},
        ],
    }


def test_grade_requires_independent_classification_for_every_survivor(tmp_path):
    results = tmp_path / "results.json"
    key = tmp_path / "key.json"
    decisions = tmp_path / "decisions.json"
    write(results, result_record([{"id": "candidate"}]))
    write(key, answer_key())
    write(decisions, {"classifications": []})
    with pytest.raises(replay.ReplayError, match="every survivor"):
        replay.grade_replay(results, key, decisions)


def test_grade_recomputes_catches_harmful_and_exact_noise_fraction(tmp_path):
    results = tmp_path / "results.json"
    key = tmp_path / "key.json"
    decisions = tmp_path / "decisions.json"
    write(results, result_record([{"id": "candidate"}]))
    write(key, answer_key())
    write(decisions, {"classifications": [{
        "case_id": "pr-1",
        "candidate_id": "candidate",
        "defect_id": "d1",
        "noise": False,
        "reason": "same defect and place",
    }]})
    score = replay.grade_replay(results, key, decisions)
    assert score["pass"] is True
    assert score["caught"] == {"fixed": 1, "unique": 1, "harmful": 0}
    write(decisions, {"classifications": [{
        "case_id": "pr-1",
        "candidate_id": "candidate",
        "defect_id": "harm",
        "noise": True,
        "reason": "the harmful recommendation reappeared",
    }]})
    score = replay.grade_replay(results, key, decisions)
    assert score["pass"] is False
    assert score["checks"]["harmful"] is False
    assert score["checks"]["noise"] is False


def test_product_recall_uses_repository_specific_denominator(tmp_path):
    results = tmp_path / "results.json"
    key = tmp_path / "key.json"
    decisions = tmp_path / "decisions.json"
    write(results, result_record([{"id": "candidate"}]))
    write(key, {
        "repository": "owner/repo",
        "thresholds": {
            "minimum_recall_fraction": {"numerator": 7, "denominator": 10},
            "maximum_noise_fraction": {"numerator": 0, "denominator": 1},
        },
        "defects": [
            {"id": "d1", "categories": ["fixed"]},
            {"id": "d2", "categories": ["fixed"]},
        ],
    })
    write(decisions, {"classifications": [{
        "case_id": "pr-1", "candidate_id": "candidate", "defect_id": "d1",
        "noise": False, "reason": "same defect",
    }]})
    score = replay.grade_replay(results, key, decisions)
    assert score["checks"]["recall"] is False
    assert score["pass"] is False

