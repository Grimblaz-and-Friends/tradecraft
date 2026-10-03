"""Keep pytest caches out of Codex worktrees without changing the caller's environment."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tomllib


def pytest_addopts_override() -> str:
    """Return one Codex config argument preserving inherited pytest options verbatim."""
    return _addopts_override(os.environ.get("PYTEST_ADDOPTS", ""))


def _toml_literal(value) -> str:
    # JSON string escapes also work in TOML, except raw DEL. Keep Unicode
    # literal so supplementary characters do not become TOML-invalid surrogates.
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007f")


def _addopts_override(base: str) -> str:
    value = f"{base} -p no:cacheprovider" if base else "-p no:cacheprovider"
    return f"shell_environment_policy.set.PYTEST_ADDOPTS={_toml_literal(value)}"


def _user_shell_policy() -> dict:
    """Mirror the seat's user-config discovery; Codex owns config diagnostics."""
    try:
        codex_home = os.environ.get("CODEX_HOME")
        if codex_home:
            home = Path(codex_home)
            if not home.is_absolute():
                return {}
        else:
            home = Path.home() / ".codex"
        raw = (home / "config.toml").resolve().read_bytes()
        policy = tomllib.loads(raw.decode("utf-8")).get("shell_environment_policy", {})
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        return {}
    return policy if isinstance(policy, dict) else {}


def _matches_addopts(patterns) -> bool:
    """Codex patterns support only case-insensitive '*' and '?' wildcards."""
    return any(
        isinstance(pattern, str) and re.fullmatch(
            re.escape(pattern).replace(r"\*", ".*").replace(r"\?", "."),
            "PYTEST_ADDOPTS", re.IGNORECASE,
        ) is not None
        for pattern in patterns
    )


def implementer_pytest_overrides() -> list[str]:
    """Preserve user-policy pytest options and admit the override through its allowlist."""
    policy = _user_shell_policy()
    filters = policy.get("filters")
    if isinstance(filters, dict):
        excludes = [pattern for pattern, action in filters.items() if action == "exclude"]
        includes = [pattern for pattern, action in filters.items() if action == "include"]
    else:
        excludes = policy.get("exclude", [])
        includes = policy.get("include_only", [])
        excludes = excludes if isinstance(excludes, list) else []
        includes = includes if isinstance(includes, list) else []

    base = ""
    # PYTEST_ADDOPTS contains none of Codex's automatically excluded name tokens.
    if policy.get("inherit") not in ("none", "core") and not _matches_addopts(excludes):
        base = os.environ.get("PYTEST_ADDOPTS", "")
    configured = policy.get("set", {})
    if isinstance(configured, dict) and isinstance(configured.get("PYTEST_ADDOPTS"), str):
        base = configured["PYTEST_ADDOPTS"]

    overrides = [_addopts_override(base)]
    if includes and not _matches_addopts(includes):
        if isinstance(filters, dict):
            overrides.append('shell_environment_policy.filters.PYTEST_ADDOPTS="include"')
        else:
            overrides.append(
                f"shell_environment_policy.include_only={_toml_literal([*includes, 'PYTEST_ADDOPTS'])}"
            )
    return overrides
