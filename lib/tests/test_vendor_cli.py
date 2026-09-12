from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vendor_cli as cli


def file(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fixture")
    return path.resolve()


def test_codex_discovery_priorities_and_invalid_explicit(tmp_path):
    explicit = file(tmp_path / "explicit.exe")
    on_path = file(tmp_path / "path.exe")
    bundled = file(tmp_path / "OpenAI/Codex/bin/build/codex.exe")
    opts = dict(env={"LOCALAPPDATA": str(tmp_path)}, platform="nt")
    assert cli.resolve_codex(str(explicit), path_lookup=lambda _: str(on_path), **opts) == explicit
    assert cli.resolve_codex(None, path_lookup=lambda _: str(on_path), **opts) == on_path
    assert cli.resolve_codex(None, path_lookup=lambda _: None, **opts) == bundled
    with pytest.raises(cli.CliError, match="does not name a file") as caught:
        cli.resolve_codex(str(tmp_path / "missing"), **opts)
    assert not isinstance(caught.value, cli.CliNotFound)


def test_missing_is_unavailable_but_not_a_broken_override(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.shutil, "which", lambda _: None)
    with pytest.raises(cli.CliNotFound):
        cli.resolve_codex(None, env={}, platform="posix", path_lookup=lambda _: None)
    with pytest.raises(cli.CliNotFound):
        cli.resolve_claude(None)
    with pytest.raises(cli.CliError, match="does not name a file"):
        cli.resolve_claude(str(tmp_path / "missing"))


def test_claude_explicit_and_path(tmp_path, monkeypatch):
    chosen = file(tmp_path / "claude.exe")
    monkeypatch.setattr(cli.shutil, "which", lambda _: str(chosen))
    assert cli.resolve_claude(None) == chosen
    assert cli.resolve_claude(str(chosen)) == chosen


@pytest.mark.parametrize("suffix", [".cmd", ".ps1", ".bat"])
def test_windows_npm_shim_launches_native_payload_without_shell(tmp_path, suffix):
    shim = file(tmp_path / ("claude" + suffix))
    native = file(tmp_path / "node_modules/@anthropic-ai/claude-code/bin/claude.exe")
    assert cli.executable_command("claude", shim, platform="nt") == [str(native)]


@pytest.mark.parametrize("vendor,relative", [("codex", "@openai/codex/bin/codex.js"), ("claude", "@anthropic-ai/claude-code/cli.js")])
def test_windows_legacy_npm_uses_node_without_shell(tmp_path, vendor, relative):
    shim = file(tmp_path / f"{vendor}.cmd")
    script = file(tmp_path / "node_modules" / relative)
    node = file(tmp_path / "node.exe")
    assert cli.executable_command(vendor, shim, platform="nt") == [str(node), str(script)]


def test_unknown_windows_shim_refused_and_posix_launcher_untouched(tmp_path):
    path = file(tmp_path / "claude.cmd")
    with pytest.raises(cli.CliError, match="native executable"):
        cli.executable_command("claude", path, platform="nt")
    assert cli.executable_command("claude", path, platform="posix") == [str(path)]
