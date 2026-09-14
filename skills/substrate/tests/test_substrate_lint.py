"""Traveling proofs for the portable substrate lint."""
from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "skills" / "substrate" / "scripts" / "lint.py"
SHIPPED_DIRS = ("skills", "lib", "commands", "agents", "hooks", ".claude-plugin")


def _load_script(path: Path = SCRIPT):
    spec = importlib.util.spec_from_file_location("shipped_substrate_lint", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


lint = _load_script()


def _clean_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(("CLAUDE_", "CODEX_")) or key in {"PLUGIN_ROOT", "PLUGIN_DATA"}:
            del env[key]
    return env


def _run(script: Path, target: Path, *, cwd: Path) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, str(script), str(target)],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        cwd=cwd,
        env=_clean_env(),
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _copy_shipped_zone(destination: Path) -> Path:
    for dirname in SHIPPED_DIRS:
        source = ROOT / dirname
        if source.is_dir():
            shutil.copytree(source, destination / dirname)
    for dirname in ("docs", "tools", ".github"):
        assert not (destination / dirname).exists()
    return destination / "skills" / "substrate" / "scripts" / "lint.py"


def _assert_ascii(result: subprocess.CompletedProcess[bytes]) -> str:
    assert result.stderr.decode("ascii") == ""
    return result.stdout.decode("ascii")


def test_clean_target_is_clean(tmp_path):
    target = tmp_path / "clean"
    _write(target / "src" / "app.py", "VALUE = 'plain ASCII'\n")

    result = _run(SCRIPT, target, cwd=tmp_path)

    assert result.returncode == 0
    assert _assert_ascii(result).endswith("lint: 0 finding(s)\n")


def test_every_guard_reports_a_planted_violation_and_leaves_a_lawful_sibling(tmp_path):
    target = tmp_path / "target"
    dash = chr(0x2014)
    token = "$" + "{CLAUDE_" + "PLUGIN_ROOT}"
    _write(
        target / "src" / "violations.py",
        "import argparse\n"
        "import subprocess\n"
        "MESSAGE = '" + dash + "'\n"
        "argparse.ArgumentParser(description=__doc__)\n"
        "def main():\n"
        "    print('unwired')\n"
        "subprocess.run(['x'], capture_output=True)\n"
        "TOKEN = '" + token + "'\n",
    )
    _write(
        target / "src" / "lawful.py",
        "from local import utf8_stdio\n"
        "import argparse\n"
        "import subprocess\n"
        "argparse.ArgumentParser(description='ASCII help')\n"
        "def main():\n"
        "    utf8_stdio()\n"
        "subprocess.run(['x'], stdin=subprocess.DEVNULL, capture_output=True)\n",
    )

    result = _run(SCRIPT, target, cwd=tmp_path)

    assert result.returncode == 1
    output = _assert_ascii(result)
    for prefix in (
        "emitted-ascii:",
        "docstring-piped:",
        "stdio-unwired:",
        "subprocess-streams:",
        "harness-token:",
    ):
        assert prefix in output
    assert "lawful.py" not in output


def test_help_is_ascii_and_does_not_pipe_the_module_docstring(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        cwd=tmp_path,
        env=_clean_env(),
    )

    assert result.returncode == 0
    output = _assert_ascii(result)
    assert "Run portable substrate guards" in output


def test_relocated_shipped_zone_runs_from_an_unrelated_directory(tmp_path):
    installed = tmp_path / "installed"
    relocated_script = _copy_shipped_zone(installed)
    target = tmp_path / "target"
    _write(target / "src" / "app.py", "VALUE = 'plain ASCII'\n")
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()

    result = _run(relocated_script, target, cwd=unrelated)

    assert result.returncode == 0
    assert _assert_ascii(result).endswith("lint: 0 finding(s)\n")


def test_no_python_target_leaves_the_python_checks_inert(tmp_path):
    target = tmp_path / "notes"
    _write(target / "README.md", "No source files here.\n")

    result = _run(SCRIPT, target, cwd=tmp_path)

    assert result.returncode == 0
    output = _assert_ascii(result)
    for prefix in ("emitted-ascii:", "docstring-piped:", "stdio-unwired:", "subprocess-streams:"):
        assert prefix not in output


def test_git_ignored_violation_is_not_judged(tmp_path):
    target = tmp_path / "target"
    subprocess.run(["git", "init", "-q", str(target)], check=True)
    _write(target / ".gitignore", "ignored\n")
    dash = chr(0x2014)
    _write(target / "ignored" / "bad.py", "MESSAGE = '" + dash + "'\n")

    result = _run(SCRIPT, target, cwd=tmp_path)

    assert result.returncode == 0
    assert _assert_ascii(result).endswith("lint: 0 finding(s)\n")


@pytest.mark.parametrize(
    ("spelling", "expected"),
    [
        ("$" + "ENV:CLAUDE_" + "PLUGIN_ROOT", 1),
        ("$" + "eNv:CLAUDE_" + "PLUGIN_ROOT", 1),
        ("%claude_" + "plugin_root%", 1),
        ("$" + "{claude_" + "plugin_root}", 0),
        ("$" + "{CLAUDE_" + "CONFIG_DIR}", 1),
        ("$" + "CLAUDE_" + "WORKING_DIR", 1),
        ("$" + "CLAUDE_" + "PLUGIN_ROOT", 1),
        ("$" + "{PLUGIN_" + "ROOT}", 1),
        ("$" + "CODEX_" + "HOME", 1),
    ],
)
def test_harness_token_spellings_keep_their_polarities(tmp_path, spelling, expected):
    _write(tmp_path / "contract.md", "run " + spelling + "/script.py\n")

    findings = lint.check_harness_tokens(tmp_path)

    assert len(findings) == expected, findings


def test_git_ignore_filter_handles_unicode_paths_and_ordinary_paths(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    _write(tmp_path / ".gitignore", "skip\n")
    hidden = tmp_path / "skip" / "plain.py"
    _write(hidden, "x = 1\n")
    shown = tmp_path / "shown.py"
    _write(shown, "y = 2\n")
    exotic = tmp_path / (chr(20013) + ".py")
    _write(exotic, "z = 3\n")

    ignored = lint._git_ignored(tmp_path, [hidden, shown, exotic])

    assert hidden in ignored
    assert shown not in ignored and exotic not in ignored


def test_read_helper_answers_none_for_missing_files_and_emitted_ascii_reports_unreadable(
        tmp_path, monkeypatch):
    assert lint._read_text(tmp_path / "missing.md") is None
    source = tmp_path / "module.py"
    _write(source, "VALUE = 1\n")
    real_read_bytes = Path.read_bytes

    def denied(path, *args, **kwargs):
        if path == source:
            raise PermissionError(13, "Permission denied")
        return real_read_bytes(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", denied)
    findings = lint.check_emitted_ascii(tmp_path)
    assert len(findings) == 1
    assert "could not be read" in findings[0] and "module.py" in findings[0]


def test_traveling_tests_run_after_relocation(tmp_path):
    if os.environ.get("SUBSTRATE_LINT_RELOCATED_TEST") == "1":
        pytest.skip("the relocated run is the terminal proof")
    installed = tmp_path / "installed"
    _copy_shipped_zone(installed)
    environment = _clean_env()
    environment["SUBSTRATE_LINT_RELOCATED_TEST"] = "1"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "skills/substrate/tests/test_substrate_lint.py",
            "-q",
        ],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        cwd=installed,
        env=environment,
    )

    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")


# --- check_emitted_ascii ---------------------------------------------------
#
# Both polarities, because a guard that blocks lawful work fails as hard as one
# that passes unlawful work -- and here the lawful case is the interesting one:
# this repository's prose style is full of em dashes, and only the ones that
# can reach a stream are the rule's business.
#
# The fixtures build their non-ASCII character with chr() rather than writing
# it, so this file stays lawful under the check it is testing.

EM_DASH = chr(0x2014)


def _py(root: Path, name: str, body: str) -> None:
    (root / name).write_text(body, encoding="utf-8")


def test_emitted_ascii_catches_a_message_that_cannot_survive_capture(tmp_path):
    """The failing case from #147: a guard's own message, garbled when piped."""
    _py(tmp_path, "guard.py",
        "def fail():" + chr(10)
        + "    print('version-bump: 1 file changed " + EM_DASH + " bump the version')" + chr(10))
    findings = [f for f in lint.check_emitted_ascii(tmp_path) if "emitted-ascii" in f]
    assert len(findings) == 1, findings
    assert "guard.py:2" in findings[0]
    assert "U+2014" in findings[0] and "EM DASH" in findings[0]
    assert findings[0].isascii(), "the finding cannot itself carry what it forbids"


def test_emitted_ascii_leaves_docstrings_and_comments_alone(tmp_path):
    """Neither reaches a stream, so the house style is free in both."""
    _py(tmp_path, "prose.py",
        '"""A module docstring ' + EM_DASH + ' with an em dash."""' + chr(10)
        + "# A comment " + EM_DASH + " also with one." + chr(10)
        + "def f():" + chr(10)
        + '    """A function docstring ' + EM_DASH + ' and another."""' + chr(10)
        + "    return 1" + chr(10))
    assert lint.check_emitted_ascii(tmp_path) == []


def test_emitted_ascii_catches_the_escaped_form(tmp_path):
    """The check reads decoded values, so writing the escape does not evade it.

    This is not hypothetical: one of the messages this change rewrote was
    written as the six-character escape and was invisible to a search for the
    character, while reaching the stream as the character all the same.
    """
    _py(tmp_path, "escaped.py",
        "print('decision-index: no row " + chr(92) + "u2014 unreachable')" + chr(10))
    findings = lint.check_emitted_ascii(tmp_path)
    assert len(findings) == 1, findings
    assert "U+2014" in findings[0]


def test_emitted_ascii_ignores_a_directory_named_like_a_module(tmp_path):
    """`rglob('*.py')` matches directories too, and reading one raises.

    Found by an unrelated delivery test that creates exactly this shape. A
    guard that crashes on a tree is worse than one that misses a finding: it
    takes every other check down with it.
    """
    (tmp_path / "notamodule.py").mkdir()
    assert lint.check_emitted_ascii(tmp_path) == []


# --- check_docstring_not_piped, check_stdio_wired ---------------------------
#
# Both polarities again, and for check 12 the lawful polarity that was missing
# the first time: a non-docstring string that is data rather than output. Its
# absence is not a hypothetical gap -- it is why a fixture got rewritten wrong
# and a regression test went inert while the suite stayed green.


def _zoned(root: Path, rel: str, body: str) -> None:
    """Write a module inside a zone the zone-scoped checks actually walk."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_docstring_piped_to_argparse_is_caught(tmp_path):
    """--help writes __doc__ to stdout before any stream setup can run."""
    _zoned(tmp_path, "src/script.py",
           '"""Module prose."""' + chr(10)
           + "import argparse" + chr(10)
           + "def main():" + chr(10)
           + "    utf8_stdio()" + chr(10)
           + "    argparse.ArgumentParser(description=__doc__)" + chr(10))
    findings = lint.check_docstring_not_piped(tmp_path)
    assert len(findings) == 1, findings
    assert "src/script.py" in findings[0] and "docstring-piped" in findings[0]


def test_an_explicit_description_is_left_alone(tmp_path):
    """The lawful form: help text written as help text."""
    _zoned(tmp_path, "src/script.py",
           '"""Module prose."""' + chr(10)
           + "import argparse" + chr(10)
           + "def main():" + chr(10)
           + "    utf8_stdio()" + chr(10)
           + '    argparse.ArgumentParser(description="What it does.")' + chr(10))
    assert lint.check_docstring_not_piped(tmp_path) == []


def test_stdio_unwired_main_is_caught(tmp_path):
    """A script whose entry point never sets its streams up."""
    _zoned(tmp_path, "src/script.py",
           "def main():" + chr(10) + "    print('x')" + chr(10))
    findings = lint.check_stdio_wired(tmp_path)
    assert len(findings) == 1, findings
    assert "stdio-unwired" in findings[0]


def test_stdio_wired_late_is_still_unwired(tmp_path):
    """Ordering is the point: --help exits inside parse_args.

    A call placed after argument parsing is a call the help path never reaches,
    which is exactly how one script here kept a helper and leaked anyway.
    """
    _zoned(tmp_path, "src/script.py",
           "def main():" + chr(10)
           + "    args = parse()" + chr(10)
           + "    utf8_stdio()" + chr(10))
    findings = lint.check_stdio_wired(tmp_path)
    assert len(findings) == 1, findings


def test_stdio_wired_first_is_left_alone(tmp_path):
    """The lawful form, including past a docstring."""
    _zoned(tmp_path, "src/script.py",
           "from winio import utf8_stdio" + chr(10)
           + "def main():" + chr(10)
           + '    """What it does."""' + chr(10)
           + "    utf8_stdio()" + chr(10)
           + "    print('x')" + chr(10))
    assert lint.check_stdio_wired(tmp_path) == []


def test_a_module_without_main_is_not_asked(tmp_path):
    """Not every module is a script, and a library owes no stream setup."""
    _zoned(tmp_path, "src/helper.py", "def helper():" + chr(10) + "    return 1" + chr(10))
    assert lint.check_stdio_wired(tmp_path) == []


# --- check_subprocess_streams -----------------------------------------------
#
# The rule is *redirect nothing, or name all three*, and the first version of
# this check asked only for stdin -- which flagged immune launches and
# prescribed the edit that breaks them (PR #232 review, M1). So the polarities
# here are three, not two: the partial redirect caught, the bare launch left
# alone, and the fully-named launch left alone. Every spelling below that
# escaped the first version is pinned, because each was found by a seat or an
# external reviewer rather than anticipated: the module alias, `stdin=None`,
# `input=None`, and the `getoutput` family. [D-232]


def _streams(root):
    return lint.check_subprocess_streams(root)


def test_a_partial_redirect_is_caught(tmp_path):
    """The shape #229 actually measured: stdout and stderr redirected, stdin
    left to resolve through a std-handle table that may name a closed handle."""
    _zoned(tmp_path, "src/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.run(["git", "status"], capture_output=True)' + chr(10))
    findings = _streams(tmp_path)
    assert len(findings) == 1, findings
    assert "subprocess-streams" in findings[0]
    assert "src/script.py:2" in findings[0]
    assert "stdin unnamed" in findings[0]


def test_a_launch_that_redirects_nothing_is_left_alone(tmp_path):
    """The polarity the first version got wrong, and the reason it mattered.

    `_get_handles` returns early when all three are None, so this launch never
    asks `GetStdHandle` anything. Requiring `stdin=` here reddened a call that
    could not fail and prescribed the one edit that makes it fail -- 0/20
    against 20/20 under real pytest capture. A guard that blocks lawful work
    fails as hard as one that passes unlawful work."""
    _zoned(tmp_path, "src/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.run(["git", "add", "-A"], check=True)' + chr(10))
    assert _streams(tmp_path) == []


def test_all_three_named_is_left_alone(tmp_path):
    """The compliant form every launch in this repository uses."""
    _zoned(tmp_path, "src/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.run(["git"], stdin=subprocess.DEVNULL,' + chr(10)
           + "               capture_output=True)" + chr(10))
    assert _streams(tmp_path) == []


def test_an_arbitrary_target_path_is_walked(tmp_path):
    """A target need not use this repository's directory names."""
    _zoned(tmp_path, "features/thing.py",
           "import subprocess" + chr(10)
           + 'subprocess.Popen(["git"], stdout=subprocess.PIPE)' + chr(10))
    findings = _streams(tmp_path)
    assert len(findings) == 1, findings
    assert "features/thing.py" in findings[0]


def test_the_module_alias_is_caught(tmp_path):
    """`import subprocess as sp` -- the hole the first version shipped.

    Three seats and both external reviewers found it independently, which is
    what makes it worth a pin rather than a line in a bounds list."""
    _zoned(tmp_path, "src/script.py",
           "import subprocess as sp" + chr(10)
           + 'sp.run(["git", "status"], capture_output=True)' + chr(10))
    findings = _streams(tmp_path)
    assert len(findings) == 1, findings
    assert "sp.run" in findings[0]


def test_the_bare_imported_name_is_caught(tmp_path):
    """`from subprocess import run` binds a name no attribute match reaches."""
    _zoned(tmp_path, "src/script.py",
           "from subprocess import run" + chr(10)
           + 'run(["git", "status"], capture_output=True)' + chr(10))
    findings = _streams(tmp_path)
    assert len(findings) == 1, findings
    assert "calls run redirecting" in findings[0]


def test_the_bare_name_remedy_does_not_name_a_module_it_lacks(tmp_path):
    """The message must not prescribe `subprocess.DEVNULL` into a file with no
    `subprocess` binding.

    It did: the remedied file passed the lint and raised `NameError` on its
    first call, so a green lint positively confirmed a broken edit. [PR #232
    review, M15]"""
    _zoned(tmp_path, "src/script.py",
           "from subprocess import run" + chr(10)
           + 'run(["git"], capture_output=True)' + chr(10))
    finding = _streams(tmp_path)[0]
    assert "subprocess.DEVNULL" not in finding
    assert "import from subprocess" in finding


def test_an_alias_remedy_names_the_alias(tmp_path):
    """The other half of the same rule: where the module is bound, the message
    names the binding the file actually has."""
    _zoned(tmp_path, "src/script.py",
           "import subprocess as sp" + chr(10)
           + 'sp.run(["git"], capture_output=True)' + chr(10))
    assert "sp.DEVNULL" in _streams(tmp_path)[0]


def test_stdin_none_does_not_satisfy_it(tmp_path):
    """`stdin=None` is the default spelled out; it redirects nothing.

    Read as merely *named*, it satisfied the first version while meaning
    inherit -- 10/10 failures under a stale table. [PR #232 review, M3]"""
    _zoned(tmp_path, "src/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.run(["git"], stdin=None, capture_output=True)' + chr(10))
    assert len(_streams(tmp_path)) == 1


def test_input_none_does_not_satisfy_it(tmp_path):
    """`input=None` never reaches `run`'s `if input is not None`, so no PIPE.

    An external reviewer contested this with a cited answer saying `input=None`
    behaves as `input=b''`. `subprocess.run`'s own source says otherwise, and
    the probes agree at 10/10 -- so this pins the source, not the answer."""
    _zoned(tmp_path, "src/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.run(["git"], input=None, capture_output=True)' + chr(10))
    assert len(_streams(tmp_path)) == 1


def test_a_real_input_covers_stdin(tmp_path):
    """`input=` with something to read implies `stdin=PIPE`.

    Not an accommodation: `check_ignored` in `src/lint.py` feeds
    `git check-ignore --stdin` exactly this way, and it is one of the sites
    #229 never saw fail."""
    _zoned(tmp_path, "src/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.run(["git"], input="x", capture_output=True)' + chr(10))
    assert _streams(tmp_path) == []


def test_capture_output_false_redirects_nothing(tmp_path):
    """The literal is read, not merely the keyword: `capture_output=False`
    leaves stdout and stderr inherited, so this launch redirects nothing."""
    _zoned(tmp_path, "src/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.run(["git"], capture_output=False)' + chr(10))
    assert _streams(tmp_path) == []


def test_the_no_stdin_wrappers_are_named(tmp_path):
    """`getoutput`, `getstatusoutput` and `os.popen` redirect a stream and take
    no stdin argument, so the rule has no compliant form for them.

    Silence there read as permission, and the cell's rule was unsatisfiable
    rather than merely unenforced. [PR #232 review, M4]"""
    _zoned(tmp_path, "src/script.py",
           "import subprocess" + chr(10)
           + "import os" + chr(10)
           + 'subprocess.getoutput("git rev-parse HEAD")' + chr(10)
           + 'subprocess.getstatusoutput("git status")' + chr(10)
           + 'os.popen("git status").read()' + chr(10))
    findings = _streams(tmp_path)
    assert len(findings) == 3, findings
    assert all("takes no stdin argument" in f for f in findings)


def test_every_launcher_name_is_reached(tmp_path):
    """All five, not the two the first version's fixtures exercised.

    Narrowing `_LAUNCHERS` to `("run", "Popen")` left the whole suite green,
    so the coverage the docstring claimed was asserted and not held. [PR #232
    review, M12]"""
    body = "import subprocess" + chr(10)
    for name in ("run", "Popen", "call", "check_call", "check_output"):
        body += f'subprocess.{name}(["git"], stdout=subprocess.PIPE)' + chr(10)
    _zoned(tmp_path, "src/script.py", body)
    findings = _streams(tmp_path)
    assert len(findings) == 5, findings
    for name in ("run", "Popen", "call", "check_call", "check_output"):
        assert any(f"subprocess.{name}" in f for f in findings), name


def test_the_message_offers_input_to_nobody_that_rejects_it(tmp_path):
    """`Popen`, `call` and `check_call` take no `input` argument.

    The first version's message offered it to all five, and D-232 rejects an
    alternative design on exactly that ground -- a remedy raising `TypeError`.
    [PR #232 review, M14]"""
    body = "import subprocess" + chr(10)
    for name in ("Popen", "call", "check_call"):
        body += f'subprocess.{name}(["git"], stdout=subprocess.PIPE)' + chr(10)
    _zoned(tmp_path, "src/script.py", body)
    for finding in _streams(tmp_path):
        assert "input=" not in finding, finding


def test_a_kwargs_forwarder_is_left_alone(tmp_path):
    """The guard's stated bound, held as a test rather than left to the prose.

    Whether a stream is redirected cannot be read off the call, and a guard
    that reddened here would block lawful work -- the polarity the substrate
    cell says fails as hard as the other."""
    _zoned(tmp_path, "src/script.py",
           "import subprocess" + chr(10)
           + "def launch(cmd, **kwargs):" + chr(10)
           + "    return subprocess.run(cmd, **kwargs)" + chr(10))
    assert _streams(tmp_path) == []


def test_an_unreadable_capture_output_is_left_alone(tmp_path):
    """The bound's other half: a non-literal `capture_output` leaves the guard
    unable to say whether two streams are redirected, and unreadable is
    silence."""
    _zoned(tmp_path, "src/script.py",
           "import subprocess" + chr(10)
           + "def launch(cmd, quiet):" + chr(10)
           + "    return subprocess.run(cmd, capture_output=quiet)" + chr(10))
    assert _streams(tmp_path) == []


def test_something_else_named_run_is_not_a_launch(tmp_path):
    """`lint.run` exists in this repository and redirects nothing."""
    _zoned(tmp_path, "src/script.py",
           "import other" + chr(10)
           + "other.run(1, capture_output=True)" + chr(10)
           + "run(2, capture_output=True)" + chr(10))
    assert _streams(tmp_path) == []


def test_check_output_bare_is_partial_not_bare(tmp_path):
    """`check_output` is `run(*popenargs, stdout=PIPE, ...)`, so it redirects a
    stream before any keyword is read.

    The cycle-one guard read "redirects nothing" off the keywords and certified
    this call, which measures 20/20 failures under real capture -- the shape
    the shipped cell calls lawful, reproduced inside the batch that closed the
    class. [PR #232 post-fix, P1]"""
    _zoned(tmp_path, "src/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.check_output(["git", "rev-parse", "HEAD"])' + chr(10))
    findings = _streams(tmp_path)
    assert len(findings) == 1, findings
    assert "stdin, stderr unnamed" in findings[0]


def test_check_output_naming_the_other_two_is_left_alone(tmp_path):
    """Its compliant form, measured 0/20 -- and the polarity that disproved the
    remedy of flagging `check_output` unconditionally."""
    _zoned(tmp_path, "src/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.check_output(["git"], stdin=subprocess.DEVNULL,' + chr(10)
           + "                        stderr=subprocess.DEVNULL)" + chr(10))
    assert _streams(tmp_path) == []


def test_check_output_is_never_told_to_name_all_three(tmp_path):
    """Naming `stdout` on `check_output` raises `ValueError`, and offering to
    redirect none of them is not on offer either."""
    _zoned(tmp_path, "src/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.check_output(["git"])' + chr(10))
    finding = _streams(tmp_path)[0]
    assert "redirect none of them" not in finding
    assert "stdout" not in finding.split("--")[0]


def test_input_none_pipes_on_check_output_but_not_on_run(tmp_path):
    """`check_output` rewrites `input=None` to `b''` before calling `run`, so
    unlike `run` it pipes stdin either way.

    Read uniformly, this reddened a call measured safe at 0/20. [PR #232
    post-fix, D1]"""
    _zoned(tmp_path, "src/co.py",
           "import subprocess" + chr(10)
           + 'subprocess.check_output(["git"], input=None,' + chr(10)
           + "                        stderr=subprocess.DEVNULL)" + chr(10))
    assert _streams(tmp_path) == []
    _zoned(tmp_path, "src/r.py",
           "import subprocess" + chr(10)
           + 'subprocess.run(["git"], input=None, capture_output=True)' + chr(10))
    findings = [f for f in _streams(tmp_path) if "src/r.py" in f]
    assert len(findings) == 1, findings


def test_capture_output_is_credited_on_run_alone(tmp_path):
    """`Popen`, `call` and `check_call` reject `capture_output` with a
    `TypeError`, so crediting it there certified a call that cannot run.
    [PR #232 post-fix, P3]"""
    body = "import subprocess" + chr(10)
    for name in ("Popen", "call", "check_call"):
        body += (f'subprocess.{name}(["git"], stdin=subprocess.DEVNULL,'
                 + " capture_output=True)" + chr(10))
    _zoned(tmp_path, "src/script.py", body)
    findings = _streams(tmp_path)
    assert len(findings) == 3, findings


def test_a_positional_stream_is_unread_rather_than_absent(tmp_path):
    """`_redirected` reads keywords, so a positionally-passed stream is unread.

    Silence here is the deliberate kind, and the fixture is chosen so the two
    versions of the guard disagree: with a keyword alongside the positional
    streams, the old predicate saw one covered stream and reported a partial
    redirect, having read none of the positional ones. It reached the right
    verdict on the fixture without them only by luck -- `Popen(cmd, -1, None,
    DEVNULL)` measured 20/20 failures with the guard silent.

    **The trade is stated rather than hidden**: this call is genuinely unsafe
    and the guard now says nothing about it, where before it said something
    accidentally. Silence is the ruled remedy because the alternative reddens
    calls whose redirection cannot be read. [PR #232 post-fix, P2]"""
    _zoned(tmp_path, "src/script.py",
           "import subprocess" + chr(10)
           + 'subprocess.run(["git"], -1, None, None, subprocess.PIPE,' + chr(10)
           + "               stdin=subprocess.DEVNULL)" + chr(10))
    assert _streams(tmp_path) == []


def test_a_splatted_argument_list_is_unread(tmp_path):
    """The other half of the same criterion."""
    _zoned(tmp_path, "src/script.py",
           "import subprocess" + chr(10)
           + "def launch(args):" + chr(10)
           + "    return subprocess.run(*args, capture_output=True)" + chr(10))
    assert _streams(tmp_path) == []


def test_os_popen_is_caught_through_every_import_spelling(tmp_path):
    """`from os import popen` and `import os.path` both bind names the cycle-one
    resolution missed -- M2's class, on code the cycle-one fix added.
    [PR #232 post-fix, P2]"""
    _zoned(tmp_path, "src/a.py",
           "from os import popen" + chr(10) + 'popen("git status")' + chr(10))
    _zoned(tmp_path, "src/b.py",
           "import os.path" + chr(10) + 'os.popen("git status")' + chr(10))
    findings = _streams(tmp_path)
    assert len(findings) == 2, findings
    assert all("takes no stdin argument" in f for f in findings)


def test_this_repository_names_its_streams_at_every_launch():
    """The tree this exists for, not a restatement of the guard.

    The guard proves the shape; this proves the shipped and repo-only trees are
    in it -- which is the claim #229 found false and nothing was checking."""
    assert lint.check_subprocess_streams(ROOT) == []


def test_emitted_ascii_reports_the_line_carrying_the_character(tmp_path):
    """Not the line the constant opens on.

    CPython folds implicit concatenation into one node, which is the shape of
    nearly every message here. Reporting the opening line sent a reader to a
    line with nothing wrong on it -- 12 of the 44 findings on the tree that
    motivated this check.
    """
    _py(tmp_path, "wrapped.py",
        "MSG = (" + chr(10)
        + '    "first line is clean "' + chr(10)
        + '    "second line has ' + EM_DASH + ' one"' + chr(10)
        + ")" + chr(10))
    findings = lint.check_emitted_ascii(tmp_path)
    assert len(findings) == 1, findings
    assert "wrapped.py:3" in findings[0], findings[0]


def test_emitted_ascii_reports_in_line_order(tmp_path):
    """`ast.walk` is breadth-first, so depth beat line and output was unsorted."""
    _py(tmp_path, "many.py",
        "A = " + repr("one " + EM_DASH) + chr(10)
        + "B = [" + repr("two " + EM_DASH) + "]" + chr(10)
        + "C = {'k': [" + repr("three " + EM_DASH) + "]}" + chr(10))
    # Not f.split(":")[1] -- that yields the filename, and on Windows an
    # absolute path would yield the drive letter. The cold consumer who
    # first used this check made exactly that mistake reading its output.
    findings = lint.check_emitted_ascii(tmp_path)
    lines = [int(re.search(r"many\.py:(\d+) ", f).group(1)) for f in findings]
    assert lines == sorted(lines), lines


def test_emitted_ascii_leaves_a_non_emitting_data_string_flagged_but_says_so(tmp_path):
    """The lawful-polarity case the first version of this check never probed.

    A filename fixture cannot reach a stream, and the check flags it anyway --
    it reads literals, not reachability. That is allowed to be true; what is
    not allowed is the message claiming otherwise, because a session that
    believes it reasons about the wrong thing and rewrites the wrong code.
    """
    _py(tmp_path, "data.py", "NAME = " + repr("caf" + chr(0xE9) + ".md") + chr(10))
    findings = lint.check_emitted_ascii(tmp_path)
    assert len(findings) == 1, findings
    assert "non-docstring string constant" in findings[0]
    assert "reach a stream" not in findings[0], (
        "the message must not claim a reachability property the check never computes"
    )


def test_emitted_ascii_reports_a_file_it_cannot_parse(tmp_path):
    """A silent skip is indistinguishable from a clean tree."""
    _py(tmp_path, "broken.py", "def (:" + chr(10))
    findings = lint.check_emitted_ascii(tmp_path)
    assert len(findings) == 1 and "does not parse" in findings[0], findings


def test_emitted_ascii_sees_through_a_utf8_bom(tmp_path):
    """A BOM made `ast.parse` raise, and the file was skipped in silence.

    The compensating control claimed at the time -- that the suite fails on a
    module it cannot import -- was false: CPython strips the BOM when reading
    from disk, so the module ran and emitted the byte.
    """
    (tmp_path / "bommed.py").write_bytes(
        chr(0xFEFF).encode("utf-8") + ("X = " + repr("a " + EM_DASH) + chr(10)).encode("utf-8"))
    findings = lint.check_emitted_ascii(tmp_path)
    assert len(findings) == 1 and "U+2014" in findings[0], findings


def test_emitted_ascii_reports_a_file_that_is_not_utf8(tmp_path):
    """Reported as undecodable, not as stating U+FFFD.

    `errors="replace"` made the check name a character that appears nowhere in
    the file, so the reader had nothing to search for.
    """
    (tmp_path / "latin.py").write_bytes(
        b"# -*- coding: latin-1 -*-" + chr(10).encode() + b"X = 'caf\xe9'" + chr(10).encode())
    findings = lint.check_emitted_ascii(tmp_path)
    assert len(findings) == 1, findings
    assert "not valid UTF-8" in findings[0] and "FFFD" not in findings[0]

def test_a_local_utf8_stdio_does_not_satisfy_the_wiring_check(tmp_path):
    """Position was exact; identity was not, and the prose claimed both.

    A module defining its own no-op utf8_stdio satisfied the call site while
    setting nothing up -- so the guard reported green on precisely the tree it
    exists to catch, and the likeliest route to writing that stub is a reader
    who could not work out the import from the finding message.
    """
    _zoned(tmp_path, "src/impostor.py",
           "def utf8_stdio():" + chr(10)
           + "    pass" + chr(10)
           + "def main():" + chr(10)
           + "    utf8_stdio()" + chr(10))
    findings = lint.check_stdio_wired(tmp_path)
    assert len(findings) == 1, findings
    assert "never imports it" in findings[0], findings[0]


def test_epilog_piped_to_argparse_is_caught(tmp_path):
    """argparse writes epilog to stdout exactly as it writes description.

    It is also the conventional home for the long-form prose a module
    docstring holds, so it is the compliant-looking route to the same defect.
    """
    _zoned(tmp_path, "src/script.py",
           '"""Module prose."""' + chr(10)
           + "import argparse" + chr(10)
           + "def main():" + chr(10)
           + "    utf8_stdio()" + chr(10)
           + "    argparse.ArgumentParser(epilog=__doc__)" + chr(10))
    findings = lint.check_docstring_not_piped(tmp_path)
    assert len(findings) == 1, findings
    assert "epilog" in findings[0], findings[0]
