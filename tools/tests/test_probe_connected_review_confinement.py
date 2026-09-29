from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import probe_connected_review_confinement as probe  # noqa: E402


def test_probe_plants_boundary_canaries_and_reports_real_launch_trace(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth")
    seen = {}

    def run(executable, run_root, snapshot, prompt, schema, token, *, effort):
        seen.update({
            "executable": executable, "run_root": run_root, "snapshot": snapshot,
            "prompt": prompt, "schema": schema, "token": token,
            "effort": effort,
            "settings": json.loads((snapshot / ".claude/settings.json").read_text()),
            "readme": (snapshot / "README.md").read_text(),
        })
        return {"candidates": []}, {"input_tokens": 1}, [
            {"tool": "Read", "input": {"file_path": str(snapshot / "README.md")}},
        ]

    monkeypatch.setattr(probe.cr, "run_pass", run)
    output = tmp_path / "probe.json"
    result = probe.run_probe(["claude.cmd"], output)
    assert seen["executable"] == ["claude.cmd"]
    assert seen["snapshot"] != seen["run_root"]
    assert seen["effort"] == probe.cr.LIVE_FINDER_EFFORT
    assert "hooks" in seen["settings"]
    hook_command = seen["settings"]["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert hook_command.startswith(f'"{sys.executable}" -c ')
    assert "outside-canary.txt" in seen["readme"]
    assert probe.CANARY_NAME in seen["readme"]
    assert result == json.loads(output.read_text(encoding="utf-8"))
    assert result["hook_fired"] is False
    assert result["outside_path_read"] is False
    assert result["environment_canary_leaked"] is False
    assert result["outside_canary_leaked"] is False


def test_probe_counts_a_hook_trace_event_as_firing(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth")
    monkeypatch.setattr(
        probe.cr,
        "run_pass",
        lambda *_args, **_kwargs: (
            {"candidates": []}, {}, [{"event": "PreToolUseHook"}],
        ),
    )
    result = probe.run_probe(["claude.cmd"], tmp_path / "probe.json")
    assert result["hook_fired"] is True
