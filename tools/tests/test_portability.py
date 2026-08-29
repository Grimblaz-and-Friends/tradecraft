"""The shipped zone runs from wherever it is installed, not only from here.

A consumer install puts the shipped zone under a plugin cache with no
repository around it. Shipped scripts once named a harness-owned plugin root,
so the contract held in one runtime and was dead in another. These tests keep
runtime-owned path tokens out of the portable calling contract.

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

# What makes a contract survive relocation is that it resolves against the
# directory of the file that names it and lands inside the cell -- the rule
# #156 landed. That is checked by resolving, not by listing lawful prefixes:
# an enumerated list is only correct at one depth, and the first `references/`
# file shipped a bare `scripts/figures.py` -- lawful from the cell root, one
# directory too high from `references/` -- while this guard read SKILL.md
# alone and stayed green. A repo-rooted `skills/<name>/scripts/...` and a
# harness token both fail by not resolving. A backslash is rejected outright
# rather than by resolution, because it resolves on Windows and is dead on
# POSIX, in a guard whose whole subject is one line working in both places.
BACKSLASH_IS_DEAD_ON_POSIX = "\\"

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
    # version guard came to be blind to new shipped directories after they were
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
def test_skill_names_its_scripts_relative_to_the_naming_file(skill: Path, installed: Path):
    """*Every* mention of a script, in *every* file of the cell, resolves.

    Every mention, not some: against the revision that introduced this guard
    both shipped skills go red, `persist-changes` because its only mention was
    `${CLAUDE_PLUGIN_ROOT}/skills/persist-changes/scripts/persist.py`, and
    `authoring` because its unlawful invocation sat in the same sentence as a
    lawful prose mention -- which the first version of this guard accepted, and
    which is why it checks all mentions rather than finding one.

    Every file, not SKILL.md alone: depth-shedding into `references/` means a
    contract can be written from a file one directory down, where the spelling
    lawful at the cell root resolves one directory too high. The first
    `references/` file shipped exactly that, and this guard was blind to it
    because it read SKILL.md and stopped.
    """
    relocated = (installed / "skills" / skill.name).resolve()

    named, mentions_found = set(), False
    for doc in sorted(relocated.rglob("*.md")):
        where = f"{skill.name}/{doc.relative_to(relocated).as_posix()}"
        for match in SCRIPT_MENTION.finditer(doc.read_text(encoding="utf-8")):
            mentions_found = True
            ref = match.group(0)
            assert BACKSLASH_IS_DEAD_ON_POSIX not in ref, (
                f"{where} names '{ref}' with a backslash, which resolves on "
                f"Windows and is dead on POSIX"
            )
            target = (doc.parent / ref).resolve()
            assert target.is_file() and relocated in target.parents, (
                f"{where} names '{ref}', which does not resolve to a file "
                f"inside the cell once installed. A script is named by a path "
                f"relative to the directory of the file naming it, so the one "
                f"line works in the source repository and in an installed "
                f"plugin alike."
            )
            named.add(target.relative_to(relocated).as_posix())

    assert mentions_found, f"{skill.name} carries scripts but names none"
    expected = {f"scripts/{s.name}" for s in _scripts_of(skill)}
    assert expected <= named, (
        f"{skill.name} carries {sorted(expected)} but its prose names "
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
    # Bytes, not text. With text=True this assertion was structurally unable
    # to see the defect it should have caught: on a cp1252 machine Python
    # decodes the locale byte 0x97 straight back to the em dash, so a --help
    # that piped a module docstring round-tripped losslessly and the test
    # stayed green while every captured byte was wrong.
    result = subprocess.run(
        [sys.executable, str(relocated), "--help"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        env=_clean_env(),
        cwd=str(installed),
    )
    stderr = result.stderr.decode("utf-8", "replace")
    assert result.returncode == 0, (
        f"{script.name} exited {result.returncode} from its installed location"
        f" -- stderr: {stderr}"
    )
    assert "Traceback" not in stderr
    for name, stream in (("stdout", result.stdout), ("stderr", result.stderr)):
        try:
            stream.decode("ascii")
        except UnicodeDecodeError as exc:
            raise AssertionError(
                f"{script.name} put a non-ASCII byte on {name} at offset "
                f"{exc.start} -- a consumer capturing this reads it garbled, "
                f"and which byte it becomes depends on their code page"
            ) from None


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
