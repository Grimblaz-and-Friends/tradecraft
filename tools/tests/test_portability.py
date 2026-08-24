"""The shipped zone runs from wherever it is installed, not only from here.

A consumer install puts the shipped zone under a plugin cache with no
repository around it. Both shipped scripts named `${CLAUDE_PLUGIN_ROOT}/...`,
which Claude Code substitutes into a skill's body but Codex does not -- Codex
sets the root as an environment variable for hook commands and performs no
textual substitution anywhere else. So the old contract held in one runtime and
was dead in the other, which is the failure these tests exist to keep out.

These tests relocate the shipped zone and exercise the property that failure
violated: every script a skill names is reachable by resolving that name against
the skill's own directory, and runs there with no harness variable set and no
repo-only directory in reach.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lint  # noqa: E402  -- the shipped-zone declaration, read not duplicated

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"

# Every mention of one of a skill's scripts, however it is spelled, with
# whatever precedes it captured. Written this way round on purpose: the first
# shape of this guard looked for a lawful mention and passed as soon as it found
# one, so a SKILL.md could name its script correctly in prose and incorrectly in
# the line a session actually copies -- which is exactly what shipped.
SCRIPT_MENTION = re.compile(r"(?P<prefix>[^\s`\"']*)scripts[/\\][\w.-]+\.py")

# A prefix is what makes a contract depend on where the skill sits. Only two
# spellings survive relocation: bare, and explicitly-relative. `../` is not
# among them -- it reaches outside the cell, which is the thing self-containment
# forbids -- and neither is a repo-rooted `skills/<name>/scripts/...`, which is
# as dead on a consumer install as a harness token is.
LAWFUL_PREFIXES = ("", "./", ".\\")

# Present in the source tree, absent from a consumer install. A script reaching
# for one of these would pass here and fail there, so the relocated root has
# none of them.
REPO_ONLY = ("docs", "tools", ".github")


def _skills_with_scripts():
    if not SKILLS.is_dir():
        return []
    return sorted(p for p in SKILLS.iterdir() if (p / "scripts").is_dir())


def _scripts_of(skill: Path):
    return sorted((skill / "scripts").glob("*.py"))


@pytest.fixture(scope="module")
def installed(tmp_path_factory) -> Path:
    """The shipped zone alone, at a path unrelated to this repository."""
    dest = tmp_path_factory.mktemp("plugin-root")
    # Built from the declared zone, not a hand-list: a hand-list is how the
    # version guard came to be blind to `charter/` and `hooks/` after they were
    # added to the zone everywhere else.
    for name in lint.SHIPPED_DIRS:
        source = ROOT / name
        if source.is_dir():
            shutil.copytree(source, dest / name)
    assert (dest / "skills").is_dir(), "the relocated root carries no skills"
    for name in REPO_ONLY:
        assert not (dest / name).exists(), f"relocated root leaked {name}/"
    return dest


def _clean_env() -> dict:
    """A consumer's shell: no harness variable, whatever the local one holds."""
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(("CLAUDE_", "CODEX_")) or key in {"PLUGIN_ROOT", "PLUGIN_DATA"}:
            del env[key]
    return env


@pytest.mark.parametrize("skill", _skills_with_scripts(), ids=lambda p: p.name)
def test_skill_names_its_scripts_relative_to_itself(skill: Path, installed: Path):
    """*Every* mention of a script resolves against the skill's own directory.

    Every, not some. Against the pre-change revision both shipped skills go red
    here: `persist-changes` because its only mention was
    `${CLAUDE_PLUGIN_ROOT}/skills/persist-changes/scripts/persist.py`, and
    `authoring` because its unlawful invocation sat in the same sentence as a
    lawful prose mention -- which the first version of this guard accepted, and
    which is why it is written to check all mentions rather than to find one.
    """
    relocated = installed / "skills" / skill.name
    text = (relocated / "SKILL.md").read_text(encoding="utf-8")

    mentions = list(SCRIPT_MENTION.finditer(text))
    assert mentions, f"{skill.name}/SKILL.md carries scripts but names none"

    named = set()
    for match in mentions:
        prefix, ref = match.group("prefix"), match.group(0)
        assert prefix in LAWFUL_PREFIXES, (
            f"{skill.name}/SKILL.md names '{ref}'. A script is named by a path "
            f"relative to the skill's own directory -- 'scripts/{ref.rsplit('/', 1)[-1]}' "
            f"-- so the one line works in the source repository and in an "
            f"installed plugin alike. The prefix '{prefix}' ties it to a location."
        )
        tail = ref[len(prefix):].replace("\\", "/")
        named.add(tail)
        assert (relocated / tail).is_file(), (
            f"{skill.name}/SKILL.md names '{ref}', which does not resolve "
            f"against the skill's own directory once installed"
        )

    expected = {f"scripts/{s.name}" for s in _scripts_of(skill)}
    assert expected <= named, (
        f"{skill.name} carries {sorted(expected)} but its SKILL.md names "
        f"{sorted(named)}"
    )


@pytest.mark.parametrize(
    "script",
    [s for skill in _skills_with_scripts() for s in _scripts_of(skill)],
    ids=lambda p: f"{p.parents[1].name}/{p.name}",
)
def test_script_runs_from_the_relocated_root(script: Path, installed: Path):
    """Each script starts where it is installed, with no harness variable set."""
    relocated = installed / "skills" / script.parents[1].name / "scripts" / script.name
    assert relocated.is_file()
    result = subprocess.run(
        [sys.executable, str(relocated), "--help"],
        capture_output=True,
        text=True,
        env=_clean_env(),
        cwd=str(installed),
    )
    assert result.returncode == 0, (
        f"{script.name} exited {result.returncode} from its installed location\n"
        f"stderr: {result.stderr}"
    )
    assert "Traceback" not in result.stderr


def test_no_shipped_skill_names_a_harness_token(installed: Path):
    """The contract that broke, stated where a reader of the tests will see it."""
    token = lint.HARNESS_TOKENS
    offenders = []
    for path in sorted((installed / "skills").rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if token.search(line):
                rel = path.relative_to(installed).as_posix()
                offenders.append(f"{rel}:{lineno}")
    assert not offenders, f"harness token in shipped skills: {offenders}"
