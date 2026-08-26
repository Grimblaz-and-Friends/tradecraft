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

import json
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


def _hook_env(plugin_root: Path) -> dict:
    """A runtime's hook environment, which is not a consumer's shell.

    `_clean_env()` is right for a shipped script: it must not depend on the
    harness, so the harness is taken away. It is backwards here. A hook command
    runs *inside* the harness by definition, and both runtimes supply the plugin
    root to it -- Claude Code by substituting the placeholder into the command
    string, Codex by inserting `CLAUDE_PLUGIN_ROOT` into the hook's environment
    (`codex-rs/hooks/src/engine/discovery.rs`, "For OOTB compat with existing
    plugins that use this env var"). Stripping it failed an emitter that reads
    the variable and delivers the charter byte-identically -- the shape Codex
    is built to serve, and the shape this guard exists to permit.

    This models the *union* of what the two runtimes supply, so a pass certifies
    delivery in at least one runtime. It is not cross-runtime coverage: no
    single command string serves both a textual placeholder and a `%VAR%`-style
    variable, which is why Codex on Windows gets nothing and why that is
    disclosed rather than guarded.
    """
    env = _clean_env()
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
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


def _declared_hook_commands(root: Path) -> list[str]:
    """The SessionStart commands `hooks/hooks.json` actually declares."""
    config = json.loads((root / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    return [
        hook["command"]
        for entry in config["hooks"]["SessionStart"]
        for hook in entry["hooks"]
        if hook.get("type") == "command" and hook.get("command")
    ]


@pytest.fixture(scope="module")
def bracketed(tmp_path_factory) -> Path:
    """An installed root whose path contains `[`.

    Not decoration: the first shape of this hook used `cat`, whose PowerShell
    alias resolves `-Path` as a wildcard, so a bracket anywhere in the plugin
    cache path made the read fail -- at exit 0 with empty stdout, which the
    runtime contract renders indistinguishable from a deliberate silence.
    """
    dest = tmp_path_factory.mktemp("cache") / "tradecraft[0.34.0]"
    for name in lint.SHIPPED_DIRS:
        source = ROOT / name
        if source.is_dir():
            shutil.copytree(source, dest / name)
    return dest


def test_the_declared_hook_command_delivers_the_charter(bracketed: Path, tmp_path: Path):
    """Run the command the plugin actually declares, and compare what it emits.

    This is the guard for the delivery path, and it is written as an execution
    check rather than as a static one on purpose. `hooks.json` names the
    emitter, the emitter names the charter, and a guard that resolved that
    second reference would still have to resolve a third if the emitter ever
    computed its path -- while failing an emitter that legitimately does. Every
    static rung fails one of those two ways. Running the command answers both
    questions at once: it catches a typo'd charter name, an emptied emitter, a
    syntax error, an emitter that exits 0 with nothing, and an emitter that
    emits the wrong file.

    What it certifies, stated as narrowly as it is true: run under the plugin
    root the runtime supplies, from a working directory that is not the plugin
    root, the declared command emits exactly the charter. It does not certify
    that every conceivable delivering emitter passes -- an earlier draft of this
    docstring said so and a probe falsified it in one cycle, because the fixture
    was stripping the variable a lawful emitter reads.

    Identity, not non-emptiness. Non-emptiness passes an emitter that prints
    the README. Line endings are normalized first, so a CRLF-only difference is
    not a failure; nothing else is forgiven.
    """
    commands = _declared_hook_commands(bracketed)
    assert commands, "hooks/hooks.json declares no SessionStart command"
    # The body, not the file: the hook strips the cell's frontmatter, which
    # is addressed to the runtime's skill index rather than to a reader.
    charter = lint._frontmatterless(
        (bracketed / lint.CHARTER).read_text(encoding="utf-8")
    )

    for command in commands:
        # Claude Code's half of the contract: it substitutes the placeholder
        # into the command string before any shell sees it. Codex performs no
        # substitution at all -- it supplies the same value through the
        # environment, which `_hook_env` sets. Modelling both is what lets a
        # lawful emitter of either shape pass. `check_delivery`'s
        # PLUGIN_ROOT_REF makes the same substitution assumption, so the two
        # guards drift together or not at all.
        expanded = command.replace("${CLAUDE_PLUGIN_ROOT}", bracketed.as_posix())
        result = subprocess.run(
            expanded,
            shell=True,
            capture_output=True,
            env=_hook_env(bracketed),
            # Never the plugin root: that is the one directory a runtime is
            # guaranteed not to hand a SessionStart hook, and running there
            # silently blesses a cwd-relative command that dies on every
            # real install.
            cwd=str(tmp_path),
        )
        assert result.returncode == 0, (
            f"the declared hook command exited {result.returncode}\n"
            f"command: {expanded}\nstderr: {result.stderr.decode(errors='replace')}"
        )
        emitted = result.stdout.decode("utf-8").replace("\r\n", "\n")
        assert emitted == charter, (
            "the declared hook command did not emit the charter: got "
            f"{len(emitted)} chars, expected {len(charter)}"
        )
