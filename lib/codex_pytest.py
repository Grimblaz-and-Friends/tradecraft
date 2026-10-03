"""Keep pytest caches out of Codex worktrees without changing the caller's environment."""
from __future__ import annotations

import json
import os


def pytest_addopts_override() -> str:
    """Return one Codex config argument preserving inherited pytest options verbatim."""
    inherited = os.environ.get("PYTEST_ADDOPTS", "")
    value = f"{inherited} -p no:cacheprovider" if inherited else "-p no:cacheprovider"
    # JSON string escapes also work in TOML, except raw DEL. Keep Unicode
    # literal so supplementary characters do not become TOML-invalid surrogates.
    literal = json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007f")
    return f"shell_environment_policy.set.PYTEST_ADDOPTS={literal}"
