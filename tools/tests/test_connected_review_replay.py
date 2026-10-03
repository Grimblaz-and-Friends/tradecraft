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
FIXTURES = ROOT / "lib/tests/fixtures"
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
    monkeypatch.setattr(replay.cr, "base_attribute_material", lambda _repo, base, paths=(): {"schema_version": 1, "base": base, "files": []})
    result = replay.export_replay(source, output)
    assert result["repository"] == "owner/repo"
    assert (output / "cases/pr-1/snapshot/app.py").is_file()
    assert set(result["cases"][0]) == {
        "id", "number", "head", "base", "snapshot", "diff", "rules",
        "snapshot_sha256", "diff_sha256", "rules_sha256",
        "base_attributes", "base_attributes_sha256",
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
    monkeypatch.setattr(replay.cr, "base_attribute_material", lambda _repo, base, paths=(): {"schema_version": 1, "base": base, "files": []})
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
        attributes = inputs / "base-attributes.json"
        replay.write_object(attributes, {"schema_version": 1, "base": BASE, "files": []})
        records.append({
            "id": f"pr-{index}", "number": str(index), "head": str(index) * 40,
            "base": BASE, "snapshot": f"cases/pr-{index}/snapshot",
            "diff": f"cases/pr-{index}/input/pull-request.diff",
            "rules": f"cases/pr-{index}/input/repository-rules.md",
            "snapshot_sha256": replay.tree_digest(snapshot),
            "diff_sha256": replay.file_digest(diff),
            "rules_sha256": replay.file_digest(rules),
            "base_attributes": f"cases/pr-{index}/input/base-attributes.json",
            "base_attributes_sha256": replay.file_digest(attributes),
        })
    write(root / "manifest.json", {
        "schema_version": 2, "repository": "owner/repo", "cases": records,
    })
    return root


def candidate(identifier: str, root_cause: str) -> dict:
    return {
        "id": identifier,
        "path": "only-1.py",
        "line": 1,
        "side": "RIGHT",
        "severity": "P1",
        "input": "value is one",
        "execution_path": "load -> use",
        "root_cause": root_cause,
        "wrong_result": "uses the wrong value",
        "evidence": "only-1.py:1",
        "proof_targets": [{
            "path": "only-1.py", "line": 1, "reason": "shows the changed value",
        }],
    }


def prepare_run(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth")
    monkeypatch.setattr(replay.cr, "verify_managed_settings", lambda: None)
    monkeypatch.setattr(replay.cr, "verify_claude_version", lambda *_: None)


@pytest.mark.parametrize("effort", [None, "medium"])
def test_replay_records_large_preloaded_finder_inputs_without_live_refusal(tmp_path, monkeypatch, effort):
    export = build_export(tmp_path / "export", cases=1)
    manifest = replay.read_object(export / "manifest.json")
    case = manifest["cases"][0]
    snapshot = export / case["snapshot"]
    (snapshot / "only-1.py").write_bytes(b"X" * replay.cr.DEFAULT_PRELOAD_BUDGET_BYTES)
    case["snapshot_sha256"] = replay.tree_digest(snapshot)
    replay.write_object(export / "manifest.json", manifest)
    finder = tmp_path / "finder.md"
    finder.write_bytes(b"finder")
    prepare_run(monkeypatch)
    inputs = []
    def run(*args, **kwargs):
        inputs.append(replay.cr.pass_input_bytes(args[3]))
        return {"candidates": []}, {}, []
    monkeypatch.setattr(replay.cr, "run_pass", run)
    result = replay.run_replay(export, tmp_path / "results.json", finder, None, "claude",
                               replay.cr.DEFAULT_CLAUDE_VERSION, HEAD, single_pass=True,
                               finder_effort=effort, preload_changed_files=True)
    assert result["complete"] and result["cases"][0]["status"] == "completed"
    assert len(inputs) == len(replay.cr.FINDER_PASSES)
    assert len(inputs[0]) > replay.cr.MAX_FINDER_PROMPT_BYTES
    assert result["cases"][0]["finder_input_utf8_bytes"] == {
        name: len(sent) for (name, _), sent in zip(replay.cr.FINDER_PASSES, inputs)
    }


def test_default_reviewer_identity_is_unchanged_without_measurement_options(tmp_path):
    finder = tmp_path / "finder.md"
    checker = tmp_path / "checker.md"
    finder.write_text("finder", encoding="utf-8")
    checker.write_text("checker", encoding="utf-8")
    settings = replay.cr.reviewer_settings(replay.cr.DEFAULT_CLAUDE_VERSION)
    assert replay.reviewer_record(
        finder, checker, replay.cr.DEFAULT_CLAUDE_VERSION, HEAD,
    ) == {
        "revision": HEAD,
        **settings,
        "settings_sha256": hashlib.sha256(replay.cr._json_bytes(settings)).hexdigest(),
        "finder_prompt_sha256": replay.file_digest(finder),
        "checker_prompt_sha256": replay.file_digest(checker),
        "harness_sha256": replay.harness_digest(),
    }


def test_single_pass_high_launches_only_finder_and_deduplicates_root_cause(
    tmp_path, monkeypatch,
):
    export = build_export(tmp_path / "export", cases=1)
    output = tmp_path / "results.json"
    finder = tmp_path / "finder.md"
    checker = tmp_path / "checker.md"
    finder.write_text("finder", encoding="utf-8")
    checker.write_text("checker", encoding="utf-8")
    prepare_run(monkeypatch)
    commands = []
    prompts = []

    def run(command, **kwargs):
        commands.append(command)
        prompts.append(kwargs["input_bytes"])
        rows = [candidate("first", "same root"), candidate("second", " SAME   ROOT ")]
        body = {
            "is_error": False,
            "structured_output": {"candidates": rows},
            "usage": {"input_tokens": 1},
        }
        return replay.cr.subprocess.CompletedProcess(
            command, 0, json.dumps(body).encode(), b"",
        )

    monkeypatch.setattr(replay.cr, "_run", run)
    result = replay.run_replay(
        export, output, finder, checker, ["claude.cmd"],
        replay.cr.DEFAULT_CLAUDE_VERSION, HEAD,
        single_pass=True, finder_effort="high",
    )
    assert len(commands) == 1
    assert b"<preloaded_changed_files>" not in prompts[0]
    assert commands[0][commands[0].index("--effort") + 1] == "high"
    assert [row["id"] for row in result["cases"][0]["survivors"]] == [
        "coverage:first",
    ]
    assert "checker_usage" not in result["cases"][0]
    assert "checker_trace" not in result["cases"][0]
    assert result["reviewer"] == {
        **replay.reviewer_record(
            finder, checker, replay.cr.DEFAULT_CLAUDE_VERSION, HEAD,
            single_pass=True, finder_effort="high",
        ),
    }
    assert result["reviewer"]["pass_structure"] == "single-pass"
    assert result["reviewer"]["finder_effort"] == "high"
    assert result["reviewer"]["checker_effort"] is None
    assert result["reviewer"]["overrides"] == {
        "single_pass": True, "finder_effort": "high",
    }


def test_preload_combines_with_single_pass_effort_and_reaches_the_launched_prompt(
    tmp_path, monkeypatch,
):
    export = build_export(tmp_path / "export", cases=1)
    output = tmp_path / "results.json"
    finder = tmp_path / "finder.md"
    checker = tmp_path / "checker.md"
    finder.write_text("finder", encoding="utf-8")
    checker.write_text("checker", encoding="utf-8")
    prepare_run(monkeypatch)
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs["input_bytes"].decode("utf-8")))
        body = {
            "is_error": False,
            "structured_output": {"candidates": []},
            "usage": {},
        }
        return replay.cr.subprocess.CompletedProcess(
            command, 0, json.dumps(body).encode(), b"",
        )

    monkeypatch.setattr(replay.cr, "_run", run)
    result = replay.run_replay(
        export, output, finder, checker, ["claude.cmd"],
        replay.cr.DEFAULT_CLAUDE_VERSION, HEAD,
        single_pass=True, finder_effort="medium", preload_changed_files=True,
    )
    assert len(calls) == 1
    assert calls[0][0][calls[0][0].index("--effort") + 1] == "medium"
    block = calls[0][1].split("\n<preloaded_changed_files>\n", 1)[1].split(
        "\n</preloaded_changed_files>\n", 1,
    )[0]
    preload = json.loads(block)
    assert preload["budget_bytes"] == replay.cr.DEFAULT_PRELOAD_BUDGET_BYTES
    assert preload["entries"][0]["content"].splitlines() == ["value = 1"]
    assert result["reviewer"]["preload_changed_files"] is True
    assert result["reviewer"]["preload_budget_bytes"] == 600000
    assert result["reviewer"]["overrides"] == {
        "single_pass": True,
        "finder_effort": "medium",
        "preload_changed_files": True,
    }


def test_effort_overrides_reach_finder_and_checker_command_lines(tmp_path, monkeypatch):
    export = build_export(tmp_path / "export", cases=1)
    output = tmp_path / "results.json"
    finder = tmp_path / "finder.md"
    checker = tmp_path / "checker.md"
    finder.write_text("finder", encoding="utf-8")
    checker.write_text("checker", encoding="utf-8")
    prepare_run(monkeypatch)
    commands = []

    def run(command, **_kwargs):
        commands.append(command)
        schema = json.loads(command[command.index("--json-schema") + 1])
        structured = (
            {"candidates": []}
            if "candidates" in schema["properties"] else {"decisions": []}
        )
        body = {"is_error": False, "structured_output": structured, "usage": {}}
        return replay.cr.subprocess.CompletedProcess(
            command, 0, json.dumps(body).encode(), b"",
        )

    monkeypatch.setattr(replay.cr, "_run", run)
    result = replay.run_replay(
        export, output, finder, checker, ["claude.cmd"],
        replay.cr.DEFAULT_CLAUDE_VERSION, HEAD,
        finder_effort="medium", checker_effort="low",
    )
    assert [command[command.index("--effort") + 1] for command in commands] == [
        "medium", "low",
    ]
    assert result["reviewer"]["pass_structure"] == "finder-checker"
    assert result["reviewer"]["finder_effort"] == "medium"
    assert result["reviewer"]["checker_effort"] == "low"
    assert result["reviewer"]["overrides"] == {
        "finder_effort": "medium", "checker_effort": "low",
    }


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
        if calls == 4:
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
    assert snapshots == [
        ["only-1.py"], ["only-1.py"], ["only-2.py"], ["only-2.py"],
    ]
    assert efforts == [
        replay.cr.FINDER_EFFORT, replay.cr.CHECKER_EFFORT,
        replay.cr.FINDER_EFFORT, replay.cr.CHECKER_EFFORT,
    ]
    assert result["reviewer"]["finder_effort"] == "xhigh"
    assert result["reviewer"]["checker_effort"] == "xhigh"
    settings = replay.cr.reviewer_settings(replay.cr.DEFAULT_CLAUDE_VERSION)
    assert result["reviewer"]["settings_sha256"] == hashlib.sha256(
        replay.cr._json_bytes(settings)
    ).hexdigest()
    assert [len(record["cases"]) for record in writes] == [0, 1, 2]
    assert result["cases"][0]["status"] == "completed"
    assert result["cases"][1] == {
        "case_id": "pr-2", "head": "2" * 40, "base": BASE,
        "status": "error", "error": "case-specific failure", "excluded_files": [],
        "finder_input_utf8_bytes": result["cases"][1]["finder_input_utf8_bytes"],
    }
    assert all(size > 0 for size in result["cases"][1]["finder_input_utf8_bytes"].values())
    assert result["complete"] is False


def test_run_copies_only_the_two_manifest_hashed_input_files(tmp_path, monkeypatch):
    export = build_export(tmp_path / "export", cases=1)
    manifest_path = export / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    case = manifest["cases"][0]
    default_inputs = export / "cases/pr-1/input"
    (default_inputs / "unverified-neighbour.txt").write_text(
        "must not be copied", encoding="utf-8",
    )
    (default_inputs / "repository-rules.md").write_text(
        "wrong neighbouring rules", encoding="utf-8",
    )
    selected_rules = export / "cases/pr-1/selected/rules.md"
    selected_rules.parent.mkdir()
    selected_rules.write_text("selected rules", encoding="utf-8")
    case["rules"] = "cases/pr-1/selected/rules.md"
    case["rules_sha256"] = replay.file_digest(selected_rules)
    write(manifest_path, manifest)
    finder = tmp_path / "finder.md"
    finder.write_text("finder", encoding="utf-8")
    output = tmp_path / "results.json"
    prepare_run(monkeypatch)

    def run(_executable, run_root, _snapshot, prompt, _schema, _token, *, effort):
        assert effort == replay.cr.LIVE_FINDER_EFFORT
        inputs = run_root.parent / "input"
        assert sorted(path.name for path in inputs.iterdir()) == [
            "pull-request.diff", "repository-rules.md",
        ]
        assert "selected rules" in prompt
        assert "wrong neighbouring rules" not in prompt
        return {"candidates": []}, {}, []

    monkeypatch.setattr(replay.cr, "run_pass", run)
    result = replay.run_replay(
        export, output, finder, None, ["claude.cmd"],
        replay.cr.DEFAULT_CLAUDE_VERSION, HEAD,
        single_pass=True, finder_effort=replay.cr.LIVE_FINDER_EFFORT,
    )
    assert result["complete"] is True


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


def test_tool_result_spill_is_pass_local_but_canary_and_sibling_reads_leak(tmp_path):
    snapshot = tmp_path / "case" / "snapshot"
    inputs = tmp_path / "case" / "input"
    pass_root = tmp_path / "case" / "finder"
    snapshot.mkdir(parents=True)
    inputs.mkdir()
    spill = (
        pass_root / "profile/claude/projects/project/session/tool-results/toolu_123.txt"
    )
    spill.parent.mkdir(parents=True)
    spill.write_text("large tool result", encoding="utf-8")
    canary = tmp_path / "prohibited" / "answer-key.txt"
    sibling = tmp_path / "sibling-case/finder/profile/claude/projects/p/s/tool-results/x.txt"
    nearby = pass_root / "profile/claude/projects/project/session/other/x.txt"
    canary.parent.mkdir()
    sibling.parent.mkdir(parents=True)
    nearby.parent.mkdir(parents=True)
    canary.write_text("canary", encoding="utf-8")
    sibling.write_text("sibling", encoding="utf-8")
    nearby.write_text("not a tool-result spill", encoding="utf-8")
    trace = [
        {"tool": "Read", "input": {"file_path": str(spill)}},
        {"tool": "Read", "input": {"file_path": str(canary)}},
        {"tool": "Read", "input": {"file_path": str(sibling)}},
        {"tool": "Read", "input": {"file_path": str(nearby)}},
    ]
    assert replay._outside_trace_reads(trace, snapshot, inputs, pass_root) == sorted([
        str(canary.resolve()), str(sibling.resolve()), str(nearby.resolve()),
    ])


def test_relative_trace_paths_resolve_from_the_pass_working_directory(tmp_path):
    case = tmp_path / "case"
    snapshot = case / "snapshot"
    inputs = case / "input"
    pass_root = case / "finder"
    snapshot.mkdir(parents=True)
    inputs.mkdir()
    (pass_root / "work").mkdir(parents=True)
    source = snapshot / "app.py"
    source.write_text("value = 1\n", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    trace = [
        {"tool": "Read", "input": {"file_path": "../../snapshot/app.py"}},
        {"tool": "Read", "input": {"file_path": "../../../outside.txt"}},
    ]
    assert replay._outside_trace_reads(trace, snapshot, inputs, pass_root) == [
        str(outside.resolve()),
    ]


def test_recorded_usage_limit_becomes_replay_case_error(tmp_path, monkeypatch):
    export = build_export(tmp_path / "export", cases=1)
    output = tmp_path / "results.json"
    finder = tmp_path / "finder.md"
    checker = tmp_path / "checker.md"
    finder.write_text("finder", encoding="utf-8")
    checker.write_text("checker", encoding="utf-8")
    recorded = json.loads(
        (FIXTURES / "connected_review_claude_usage_limit.json").read_text(encoding="utf-8")
    )
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth")
    monkeypatch.setattr(replay.cr, "verify_managed_settings", lambda: None)
    monkeypatch.setattr(replay.cr, "verify_claude_version", lambda *_: None)

    def run(command, **_kwargs):
        stdout = "\n".join(json.dumps(event) for event in recorded["events"]).encode()
        return replay.cr.subprocess.CompletedProcess(
            command, recorded["returncode"], stdout, recorded["stderr"].encode(),
        )

    monkeypatch.setattr(replay.cr, "_run", run)
    result = replay.run_replay(
        export, output, finder, checker, "claude",
        replay.cr.DEFAULT_CLAUDE_VERSION, HEAD,
    )
    assert result["complete"] is False
    assert result["cases"][0]["status"] == "error"
    assert "usage limit" in result["cases"][0]["error"].lower()
    assert "api_error_status=429" in result["cases"][0]["error"]


def test_resume_reruns_only_incomplete_cases_and_preserves_completed_case(tmp_path, monkeypatch):
    export = build_export(tmp_path / "export", cases=3)
    source = tmp_path / "partial-results.json"
    output = tmp_path / "resumed-results.json"
    finder = tmp_path / "finder.md"
    checker = tmp_path / "checker.md"
    finder.write_text("finder", encoding="utf-8")
    checker.write_text("checker", encoding="utf-8")
    reviewer = replay.reviewer_record(
        finder, checker, replay.cr.DEFAULT_CLAUDE_VERSION, HEAD,
    )
    reviewer["harness_sha256"] = "0" * 64
    completed = {
        "case_id": "pr-1", "head": "1" * 40, "base": BASE,
        "status": "completed", "survivors": [{"id": "kept-byte-for-byte"}],
        "finder_usage": {"input_tokens": 1}, "checker_usage": {"input_tokens": 2},
        "finder_trace": [], "checker_trace": [], "outside_reads": [], "canaries": {},
    }
    previous = {
        "schema_version": 1,
        "repository": "owner/repo",
        "manifest_cases": [
            {"case_id": f"pr-{index}", "head": str(index) * 40, "base": BASE}
            for index in range(1, 4)
        ],
        "reviewer": reviewer,
        "base_attribute_sources": {case["id"]: case["base_attributes_sha256"] for case in replay.validate_export(export)["cases"]},
        "complete": False,
        "cases": [
            completed,
            {"case_id": "pr-2", "head": "2" * 40, "base": BASE,
             "status": "invalid-leak", "outside_reads": ["old-false-positive"]},
            {"case_id": "pr-3", "head": "3" * 40, "base": BASE,
             "status": "error", "error": "usage limit"},
        ],
    }
    write(source, previous)
    source_bytes = source.read_bytes()
    completed_bytes = replay.cr._json_bytes(completed)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth")
    monkeypatch.setattr(replay.cr, "verify_managed_settings", lambda: None)
    monkeypatch.setattr(replay.cr, "verify_claude_version", lambda *_: None)
    visited = []

    def run(_executable, _root, snapshot, _prompt, schema, _token, *, effort):
        visited.append((next(snapshot.iterdir()).name, schema, effort))
        if schema is replay.cr.FINDER_SCHEMA:
            return {"candidates": []}, {}, []
        return {"decisions": []}, {}, []

    monkeypatch.setattr(replay.cr, "run_pass", run)
    result = replay.run_replay(
        export, output, finder, checker, "claude",
        replay.cr.DEFAULT_CLAUDE_VERSION, HEAD, source,
    )
    assert [name for name, _schema, _effort in visited] == [
        "only-2.py", "only-2.py",
        "only-3.py", "only-3.py",
    ]
    assert result["resumed_cases"] == ["pr-2", "pr-3"]
    assert replay.cr._json_bytes(result["cases"][0]) == completed_bytes
    assert source.read_bytes() == source_bytes
    current_harness = replay.harness_digest()
    assert result["case_harness_sha256"] == {
        "pr-1": "0" * 64, "pr-2": current_harness, "pr-3": current_harness,
    }
    assert result["complete"] is True
    assert output.is_file() and output != source


@pytest.mark.parametrize(
    "field",
    [
        "revision", "model", "finder_effort", "checker_effort",
        "claude_cli_version", "finder_prompt_sha256", "checker_prompt_sha256",
        "settings_sha256",
    ],
)
def test_resume_refuses_changed_reviewer_identity(tmp_path, field):
    export = build_export(tmp_path / "export", cases=1)
    source = tmp_path / "partial-results.json"
    finder = tmp_path / "finder.md"
    checker = tmp_path / "checker.md"
    finder.write_text("finder", encoding="utf-8")
    checker.write_text("checker", encoding="utf-8")
    reviewer = replay.reviewer_record(
        finder, checker, replay.cr.DEFAULT_CLAUDE_VERSION, HEAD,
    )
    reviewer[field] = "different"
    write(source, {
        "schema_version": 1,
        "repository": "owner/repo",
        "manifest_cases": [{"case_id": "pr-1", "head": "1" * 40, "base": BASE}],
        "reviewer": reviewer,
        "complete": False,
        "cases": [],
    })
    with pytest.raises(replay.ReplayError, match=field):
        replay.run_replay(
            export, tmp_path / "new-results.json", finder, checker, "claude",
            replay.cr.DEFAULT_CLAUDE_VERSION, HEAD, source,
        )


@pytest.mark.parametrize("level", replay.EFFORT_LEVELS)
def test_run_parser_accepts_every_supported_effort(level):
    args = replay.parser().parse_args([
        "run", "--export", "export", "--output", "results.json",
        "--finder-prompt", "finder.md", "--checker-prompt", "checker.md",
        "--revision", HEAD, "--finder-effort", level, "--checker-effort", level,
    ])
    assert args.finder_effort == level
    assert args.checker_effort == level


def test_single_pass_parser_keeps_existing_checker_prompt_argument():
    args = replay.parser().parse_args([
        "run", "--export", "export", "--output", "results.json",
        "--finder-prompt", "finder.md", "--checker-prompt", "checker.md",
        "--revision", HEAD,
        "--single-pass", "--finder-effort", "medium",
    ])
    assert args.single_pass is True
    assert args.checker_prompt == Path("checker.md")


def test_run_parser_accepts_changed_file_preload_with_measurement_options():
    args = replay.parser().parse_args([
        "run", "--export", "export", "--output", "results.json",
        "--finder-prompt", "finder.md", "--checker-prompt", "checker.md",
        "--revision", HEAD, "--single-pass", "--finder-effort", "low",
        "--preload-changed-files",
    ])
    assert args.single_pass is True
    assert args.finder_effort == "low"
    assert args.preload_changed_files is True


def test_single_pass_refuses_unused_checker_effort(tmp_path):
    with pytest.raises(replay.ReplayError, match="cannot be used"):
        replay.run_replay(
            tmp_path / "export", tmp_path / "results.json", tmp_path / "finder.md",
            tmp_path / "checker.md", "claude", replay.cr.DEFAULT_CLAUDE_VERSION, HEAD,
            single_pass=True, checker_effort="low",
        )


@pytest.mark.parametrize(
    ("stored_options", "current_options", "difference"),
    [
        (
            {"single_pass": True, "finder_effort": "high"},
            {"single_pass": True, "finder_effort": "medium"},
            "finder_effort",
        ),
        (
            {"finder_effort": "high", "checker_effort": "medium"},
            {"finder_effort": "high", "checker_effort": "low"},
            "checker_effort",
        ),
        (
            {"single_pass": True, "finder_effort": "xhigh"},
            {"finder_effort": "xhigh"},
            "pass_structure",
        ),
        (
            {"single_pass": True, "finder_effort": "high",
             "preload_changed_files": True},
            {"single_pass": True, "finder_effort": "high"},
            "preload_changed_files",
        ),
        (
            {"preload_changed_files": True, "preload_budget_bytes": 599999},
            {"preload_changed_files": True},
            "preload_budget_bytes",
        ),
    ],
)
def test_resume_refuses_changed_measurement_configuration(
    tmp_path, stored_options, current_options, difference,
):
    export = build_export(tmp_path / "export", cases=1)
    source = tmp_path / "partial-results.json"
    finder = tmp_path / "finder.md"
    checker = tmp_path / "checker.md"
    finder.write_text("finder", encoding="utf-8")
    checker.write_text("checker", encoding="utf-8")
    reviewer = replay.reviewer_record(
        finder, checker, replay.cr.DEFAULT_CLAUDE_VERSION, HEAD,
        **stored_options,
    )
    write(source, {
        "schema_version": 1,
        "repository": "owner/repo",
        "manifest_cases": [{"case_id": "pr-1", "head": "1" * 40, "base": BASE}],
        "reviewer": reviewer,
        "complete": False,
        "cases": [],
    })
    with pytest.raises(replay.ReplayError, match=difference):
        replay.run_replay(
            export, tmp_path / "new-results.json", finder, checker, "claude",
            replay.cr.DEFAULT_CLAUDE_VERSION, HEAD, source,
            **current_options,
        )


def test_run_parser_accepts_resume_results_path():
    args = replay.parser().parse_args([
        "run", "--export", "export", "--output", "new.json",
        "--finder-prompt", "finder.md", "--checker-prompt", "checker.md",
        "--revision", HEAD, "--resume", "partial.json",
    ])
    assert args.resume == Path("partial.json")


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


def test_grade_carries_measurement_identity_through(tmp_path):
    reviewer = {
        "revision": HEAD,
        "model": replay.cr.DEFAULT_MODEL,
        "pass_structure": "single-pass",
        "finder_effort": "high",
        "checker_effort": None,
        "overrides": {"single_pass": True, "finder_effort": "high"},
    }
    results = result_record(
        [{"id": f"candidate-{index}"} for index in range(12)],
    )
    results["reviewer"] = reviewer
    score = grade_files(tmp_path, results, tradecraft_key(), classifications(12))
    assert score["reviewer"] == reviewer


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


@pytest.mark.parametrize("effort", [None, "high"])
@pytest.mark.parametrize("preload", [False, True])
def test_replay_uses_offline_base_policy_for_all_prompt_paths(tmp_path, monkeypatch, effort, preload):
    from test_connected_review import attribute_material, file_diff
    export = build_export(tmp_path / "export", cases=1)
    manifest = replay.read_object(export / "manifest.json")
    case = manifest["cases"][0]
    snapshot = export / case["snapshot"]
    (snapshot / ".gitattributes").write_bytes(b"* linguist-generated\n")
    (snapshot / "package-lock.json").write_bytes(b"LOCK_SECRET" * 100)
    (snapshot / "generated.json").write_bytes(b"GEN_SECRET" * 100)
    (snapshot / "only-1.py").write_bytes(b"SOURCE_CONTROL")
    (export / case["diff"]).write_bytes((file_diff("package-lock.json", "LOCK_SECRET") + file_diff("generated.json", "GEN_SECRET") + file_diff("only-1.py")).encode())
    replay.write_object(export / case["base_attributes"], attribute_material({".gitattributes": b"generated.json linguist-generated\n"}))
    for field in ["diff", "base_attributes"]:
        case[field + "_sha256"] = replay.file_digest(export / case[field])
    case["snapshot_sha256"] = replay.tree_digest(snapshot)
    replay.write_object(export / "manifest.json", manifest)
    prepare_run(monkeypatch)
    monkeypatch.setattr(replay.cr, "gh_json", lambda *_args, **_kwargs: pytest.fail("must be offline"))
    monkeypatch.setattr(replay.cr, "gh_bytes", lambda *_args, **_kwargs: pytest.fail("must be offline"))
    prompts = []
    def run(_exe, _root, _snapshot, prompt, schema, _token, **kwargs):
        prompts.append(prompt)
        assert (_snapshot / "package-lock.json").read_bytes().startswith(b"LOCK_SECRET")
        return ({"candidates": []} if schema == replay.cr.FINDER_SCHEMA else {"decisions": []}), {}, []
    monkeypatch.setattr(replay.cr, "run_pass", run)
    finder = tmp_path / "finder.md"; finder.write_bytes(b"finder")
    checker = tmp_path / "checker.md"; checker.write_bytes(b"checker")
    result = replay.run_replay(export, tmp_path / "results.json", finder, checker, "claude", replay.cr.DEFAULT_CLAUDE_VERSION, HEAD,
                               finder_effort=effort, checker_effort=effort, preload_changed_files=preload, preload_budget_bytes=14)
    assert result["complete"] and len(prompts) == 2
    assert result["cases"][0]["excluded_files"] == [
        {"path": "package-lock.json", "reason": "lockfile"}, {"path": "generated.json", "reason": "generated"},
    ]
    for prompt in prompts:
        assert "LOCK_SECRET" not in prompt and "GEN_SECRET" not in prompt
        assert "SOURCE_CONTROL" in prompt and "package-lock.json" in prompt and "generated.json" in prompt
        if preload:
            assert '"preloaded_bytes": 14' in prompt


@pytest.mark.parametrize("rehash_manifest", [False, True])
def test_replay_refuses_modified_base_attributes_before_launch(tmp_path, monkeypatch, rehash_manifest):
    export = build_export(tmp_path / "export", cases=1)
    manifest = replay.read_object(export / "manifest.json")
    case = manifest["cases"][0]
    material_path = export / case["base_attributes"]
    from test_connected_review import attribute_material
    material = attribute_material({".gitattributes": b"* linguist-generated\n"})
    material["files"][0]["sha256"] = "0" * 64
    replay.write_object(material_path, material)
    if rehash_manifest:
        case["base_attributes_sha256"] = replay.file_digest(material_path)
        replay.write_object(export / "manifest.json", manifest)
    monkeypatch.setattr(replay.cr, "run_pass", lambda *_args, **_kwargs: pytest.fail("must not launch"))
    with pytest.raises(replay.ReplayError, match="no longer match"):
        replay.run_replay(export, tmp_path / "results.json", tmp_path / "unused", None, "claude", replay.cr.DEFAULT_CLAUDE_VERSION, HEAD, single_pass=True)


def test_older_export_remains_readable_but_new_run_names_exact_recovery(tmp_path):
    export = build_export(tmp_path / "export", cases=1)
    manifest = replay.read_object(export / "manifest.json")
    manifest["schema_version"] = 1
    case = manifest["cases"][0]
    del case["base_attributes"]
    del case["base_attributes_sha256"]
    replay.write_object(export / "manifest.json", manifest)
    assert replay.validate_export(export) == manifest
    with pytest.raises(replay.ReplayError, match="re-export into a new directory") as raised:
        replay.run_replay(export, tmp_path / "results.json", tmp_path / "unused", None, "claude", replay.cr.DEFAULT_CLAUDE_VERSION, HEAD, single_pass=True)
    for required in ["owner/repo", "pr-1", BASE, "1" * 40, '"number": 1', "SOURCE.json", "NEW_DIRECTORY"]:
        assert required in str(raised.value)


def test_resume_cannot_mix_coverage_policy_or_budget(tmp_path):
    export = build_export(tmp_path / "export", cases=1)
    finder = tmp_path / "finder.md"; finder.write_bytes(b"finder")
    current = replay.reviewer_record(finder, None, replay.cr.DEFAULT_CLAUDE_VERSION, HEAD, single_pass=True)
    manifest = replay.validate_export(export)
    for field in ["coverage_policy_version", "max_finder_prompt_bytes"]:
        changed = {**current, field: current[field] + 1}
        results = {"repository": "owner/repo", "manifest_cases": [{"case_id": "pr-1", "head": "1" * 40, "base": BASE}], "reviewer": changed}
        path = tmp_path / "old-results.json"; replay.write_object(path, results)
        with pytest.raises(replay.ReplayError, match=field):
            replay._resume_cases(path, manifest, current)


def test_resume_compares_captured_base_attribute_source_hashes(tmp_path):
    export = build_export(tmp_path / "export", cases=1)
    manifest = replay.validate_export(export)
    finder = tmp_path / "finder.md"
    finder.write_bytes(b"finder")
    reviewer = replay.reviewer_record(finder, None, replay.cr.DEFAULT_CLAUDE_VERSION, HEAD, single_pass=True)
    record = {
        "repository": "owner/repo",
        "manifest_cases": [{"case_id": "pr-1", "head": "1" * 40, "base": BASE}],
        "reviewer": reviewer, "cases": [],
        "base_attribute_sources": {"pr-1": manifest["cases"][0]["base_attributes_sha256"]},
    }
    results = tmp_path / "results.json"
    replay.write_object(results, record)
    assert replay._resume_cases(results, manifest, reviewer)[1] == ["pr-1"]
    record["base_attribute_sources"]["pr-1"] = "0" * 64
    replay.write_object(results, record)
    with pytest.raises(replay.ReplayError, match="base attribute source hashes differ"):
        replay._resume_cases(results, manifest, reviewer)
