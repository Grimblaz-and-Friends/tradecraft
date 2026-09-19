#!/usr/bin/env python3
"""Run the five portable substrate guards against one repository."""
from __future__ import annotations

import argparse
import ast
import os
import re
import subprocess
import sys
import traceback
import unicodedata
from collections.abc import Iterable
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))
from winio import utf8_stdio  # noqa: E402


_HARNESS_NAMES = (
    "CLAUDE_PLUGIN_ROOT|CLAUDE_PLUGIN_DATA|CLAUDE_PROJECT_DIR|"
    "CLAUDE_SKILL_DIR|CLAUDE_CONFIG_DIR|CLAUDE_WORKING_DIR|"
    "PLUGIN_ROOT|PLUGIN_DATA|CODEX_HOME"
)
HARNESS_TOKENS = re.compile(
    rf"\$\{{(?:{_HARNESS_NAMES})\}}"
    rf"|\$(?:{_HARNESS_NAMES})(?!\w)"
    rf"|(?i:\$env:(?:{_HARNESS_NAMES}))(?!\w)"
    rf"|(?i:%(?:{_HARNESS_NAMES})%)"
)


def _read_text(path: Path) -> str | None:
    """Return decoded text, or None for binary and unreadable files."""
    text, _ = _read_text_result(path)
    return text


def _read_text_result(path: Path) -> tuple[str | None, OSError | None]:
    """Return decoded text plus the read error, if an OS error prevented it."""
    try:
        data = path.read_bytes()
    except OSError as error:
        return None, error
    if b"\0" in data[:1024]:
        return None, None
    return data.decode("utf-8-sig", errors="replace"), None


def _iter_files(base: Path):
    """Yield every ordinary file below base in a stable order."""
    paths = []
    for parent, directories, filenames in os.walk(base):
        directories[:] = [name for name in directories if name != ".git"]
        paths.extend(Path(parent, name) for name in filenames)
    yield from sorted(path for path in paths if path.is_file())


def _python_files(base: Path):
    """Yield every Python file below base in a stable order."""
    paths = []
    for parent, directories, filenames in os.walk(base):
        directories[:] = [name for name in directories if name != ".git"]
        paths.extend(Path(parent, name) for name in filenames if name.endswith(".py"))
    yield from sorted(path for path in paths if path.is_file())


# One invocation asks git each distinct question once. Keyed on the exact path
# list rather than on `root`, because the callers ask three different questions
# -- every .py file, that set without tests, and (in the repository wrapper) the
# prose files -- and a root-keyed answer would hand one caller the ignored-set
# computed for another's population, changing what the lint finds. Cleared at
# the top of `run()` rather than held for the process: a caller drives the lint
# in-process many times over trees it mutates between runs, and a `functools`
# cache would answer the second run from the first. [#649]
_IGNORED_MEMO: dict[tuple[str, tuple[str, ...]], set[Path]] = {}


def reset_ignored_memo() -> None:
    """Drop the per-invocation ignored-set memo. `run()` calls this first."""
    _IGNORED_MEMO.clear()


def _git_ignored(root: Path, paths: list[Path]) -> set[Path]:
    """Return ignored paths, or none when git cannot answer; UTF-8 input avoids
    a locale-encoded write timing out at 60 seconds and treating every path as unignored.
    """
    if not paths:
        return set()
    key = (str(root), tuple(str(path) for path in paths))
    if key in _IGNORED_MEMO:
        # Copied out, so a caller mutating what it gets back cannot poison the
        # answer the next caller receives.
        return set(_IGNORED_MEMO[key])
    try:
        proc = subprocess.run(
            ["git", "check-ignore", "--stdin", "-z"],
            input="\0".join(str(path) for path in paths),
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=root,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        result: set[Path] = set()
    else:
        result = (
            {Path(name) for name in proc.stdout.split("\0") if name}
            if proc.returncode in (0, 1) else set()
        )
    # The degradation is memoised with the answer. Asking again inside one
    # invocation would fail the same way, and one invocation giving two callers
    # two different answers about the same paths is the worse outcome.
    _IGNORED_MEMO[key] = result
    return set(result)


def _target_python_files(root: Path, *, include_tests: bool = True) -> list[Path]:
    candidates = [
        path for path in _python_files(root)
        if ".git" not in path.parts and (include_tests or "tests" not in path.parts)
    ]
    ignored = _git_ignored(root, candidates)
    return [path for path in candidates if path not in ignored]


def _docstring_constants(tree: ast.AST) -> set[int]:
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if isinstance(first.value.value, str):
                found.add(id(first.value))
    return found


def _true_lineno(text: str, node: ast.Constant, char: str) -> int:
    lines = text.splitlines()
    first = node.lineno - 1
    last = min(node.end_lineno or node.lineno, len(lines))
    for offset in range(first, last):
        if char in lines[offset]:
            return offset + 1
    return node.lineno


def _unparseable_finding(check: str, rel_file: str, exc: SyntaxError) -> str:
    at = f":{exc.lineno}" if exc.lineno is not None else ""
    return (
        f"{check}: {rel_file}{at} does not parse ({exc.msg}) -- an unparseable "
        f"file is not checked, and a check that skips in silence cannot be told "
        f"apart from a clean tree"
    )


def check_emitted_ascii(root: Path) -> list[str]:
    """Report non-ASCII Python string constants outside docstrings."""
    findings = []
    for path in _target_python_files(root):
        rel_file = path.relative_to(root).as_posix()
        try:
            raw = path.read_bytes()
        except OSError as exc:
            findings.append(
                f"emitted-ascii: {rel_file} could not be read ({exc.strerror}) "
                f"-- it is unchecked, and a check that skips in silence cannot "
                f"be told apart from a clean tree"
            )
            continue
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            findings.append(
                f"emitted-ascii: {rel_file} is not valid UTF-8 ({exc.reason} at "
                f"byte {exc.start}) -- the substrate reads UTF-8, and a file it "
                f"cannot decode cannot be checked for what it states"
            )
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            findings.append(_unparseable_finding("emitted-ascii", rel_file, exc))
            continue
        docstrings = _docstring_constants(tree)
        seen = set()
        per_file = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if id(node) in docstrings:
                continue
            for char in node.value:
                if ord(char) < 128:
                    continue
                lineno = _true_lineno(text, node, char)
                if (lineno, ord(char)) not in seen:
                    seen.add((lineno, ord(char)))
                    per_file.append((lineno, ord(char), char))
        for lineno, _codepoint, char in sorted(per_file):
            findings.append(
                f"emitted-ascii: {rel_file}:{lineno} states "
                f"U+{ord(char):04X} ({unicodedata.name(char, 'unnamed')}) "
                f"in a non-docstring string constant -- machine-read output "
                f"stays ASCII, because Windows encodes it to the locale "
                f"codepage and a captured non-ASCII byte garbles. If this "
                f"string is data rather than output, build its non-ASCII "
                f"character at runtime rather than storing it in a string constant"
            )
    return findings


def check_docstring_not_piped(root: Path) -> list[str]:
    """Report argparse help that uses a module docstring."""
    findings = []
    for path in _target_python_files(root):
        text = _read_text(path)
        if text is None:
            continue
        rel_file = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            findings.append(_unparseable_finding("docstring-piped", rel_file, exc))
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg not in ("description", "epilog"):
                    continue
                if isinstance(keyword.value, ast.Name) and keyword.value.id == "__doc__":
                    findings.append(
                        f"docstring-piped: {rel_file}:{node.lineno} passes "
                        f"__doc__ as an argparse {keyword.arg} -- --help writes "
                        f"it to stdout, so a docstring becomes output and the "
                        f"exemption that lets it carry any character stops being "
                        f"true. Write the help text as its own ASCII string"
                    )
    return findings


def _imported_stream_names(tree: ast.AST) -> tuple[set[str], dict[str, str]]:
    modules, streams = set(), {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sys":
                    modules.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "sys":
            for alias in node.names:
                if alias.name in ("stdout", "stderr"):
                    streams[alias.asname or alias.name] = alias.name
    return modules, streams


def _configured_stream(
        statement: ast.stmt, modules: set[str], streams: dict[str, str]) -> str | None:
    if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
        return None
    call = statement.value
    if not isinstance(call.func, ast.Attribute) or call.func.attr != "reconfigure":
        return None
    receiver = call.func.value
    if isinstance(receiver, ast.Attribute) and isinstance(receiver.value, ast.Name):
        stream = receiver.attr if receiver.value.id in modules else None
    elif isinstance(receiver, ast.Name):
        stream = streams.get(receiver.id)
    else:
        stream = None
    options = {
        keyword.arg: keyword.value.value
        for keyword in call.keywords
        if keyword.arg is not None and isinstance(keyword.value, ast.Constant)
    }
    encoding = options.get("encoding")
    if stream not in ("stdout", "stderr"):
        return None
    if not isinstance(encoding, str) or encoding.casefold() != "utf-8":
        return None
    if options.get("newline") != "":
        return None
    return stream


def _manually_wired(body: list[ast.stmt], tree: ast.AST) -> bool:
    modules, streams = _imported_stream_names(tree)
    configured = {_configured_stream(statement, modules, streams) for statement in body[:2]}
    if configured == {"stdout", "stderr"}:
        return True
    if not body or not isinstance(body[0], ast.For) or not isinstance(body[0].target, ast.Name):
        return False
    loop = body[0]
    if not isinstance(loop.iter, (ast.List, ast.Tuple)) or not loop.body:
        return False
    loop_streams = set()
    for member in loop.iter.elts:
        if isinstance(member, ast.Attribute) and isinstance(member.value, ast.Name):
            stream = member.attr if member.value.id in modules else None
        elif isinstance(member, ast.Name):
            stream = streams.get(member.id)
        else:
            stream = None
        loop_streams.add(stream)
    call = loop.body[0].value if isinstance(loop.body[0], ast.Expr) else None
    if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
        return False
    if not isinstance(call.func.value, ast.Name) or call.func.value.id != loop.target.id:
        return False
    options = {
        keyword.arg: keyword.value.value
        for keyword in call.keywords
        if keyword.arg is not None and isinstance(keyword.value, ast.Constant)
    }
    return (
        call.func.attr == "reconfigure"
        and isinstance(options.get("encoding"), str)
        and options["encoding"].casefold() == "utf-8"
        and options.get("newline") == ""
        and loop_streams == {"stdout", "stderr"}
    )


def check_stdio_wired(root: Path) -> list[str]:
    """Report scripts whose main does not wire UTF-8 streams first."""
    findings = []
    for path in _target_python_files(root, include_tests=False):
        text = _read_text(path)
        if text is None:
            continue
        rel_file = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            findings.append(_unparseable_finding("stdio-unwired", rel_file, exc))
            continue
        main = next(
            (
                node for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "main"
            ),
            None,
        )
        if main is None:
            continue
        body = list(main.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            body = body[1:]
        first = body[0] if body else None
        called = (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Call)
            and isinstance(first.value.func, ast.Name)
            and first.value.func.id == "utf8_stdio"
        )
        imported = any(
            isinstance(node, ast.ImportFrom)
            and any(
                alias.asname == "utf8_stdio"
                or (alias.asname is None and alias.name == "utf8_stdio")
                for alias in node.names
            )
            for node in ast.walk(tree)
        )
        manual = _manually_wired(body, tree)
        if not (called and imported) and not manual:
            missing = "calls utf8_stdio first but never imports it" if called else (
                "neither calls an imported utf8_stdio first nor configures both streams first"
            )
            findings.append(
                f"stdio-unwired: {rel_file}:{main.lineno} defines main() and "
                f"{missing} -- runtime data the target repository did not write "
                f"reaches the stream unprotected, and a call placed later is "
                f"one that --help has outrun. Either import a repository-local "
                f"utf8_stdio and call it as the first statement, or make main's "
                f"first work configure both stdout and stderr with encoding UTF-8 "
                f"and newline=''"
            )
    return findings


_LAUNCHERS = ("run", "Popen", "call", "check_call", "check_output")
_NO_STDIN = {
    ("subprocess", "getoutput"),
    ("subprocess", "getstatusoutput"),
    ("os", "popen"),
}
_STREAMS = ("stdin", "stdout", "stderr")
_IMPLICIT = {"check_output": frozenset({"stdout"})}
_TAKES_CAPTURE_OUTPUT = frozenset({"run"})
_TAKES_INPUT = frozenset({"run", "check_output"})


def _module_aliases(tree: ast.AST, module: str) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Import):
            continue
        for alias in node.names:
            if alias.asname:
                if alias.name == module:
                    names.add(alias.asname)
            elif alias.name == module or alias.name.startswith(module + "."):
                names.add(module)
    return names


def _is_none(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _redirected(call: ast.Call, launcher: str) -> set[str] | None:
    if len(call.args) > 1 or any(isinstance(arg, ast.Starred) for arg in call.args):
        return None
    covered = set(_IMPLICIT.get(launcher, ()))
    for keyword in call.keywords:
        if keyword.arg is None:
            return None
        if keyword.arg in _STREAMS and not _is_none(keyword.value):
            covered.add(keyword.arg)
        elif keyword.arg == "input" and launcher in _TAKES_INPUT:
            if launcher == "check_output" or not _is_none(keyword.value):
                covered.add("stdin")
        elif keyword.arg == "capture_output" and launcher in _TAKES_CAPTURE_OUTPUT:
            if not isinstance(keyword.value, ast.Constant):
                return None
            if keyword.value.value:
                covered.update(("stdout", "stderr"))
    return covered


def check_subprocess_streams(root: Path) -> list[str]:
    """Report launches that redirect only some standard streams."""
    findings = []
    for path in _target_python_files(root):
        text = _read_text(path)
        if text is None:
            continue
        rel_file = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            findings.append(_unparseable_finding("subprocess-streams", rel_file, exc))
            continue
        modules = {name: "subprocess" for name in _module_aliases(tree, "subprocess")}
        modules.update({name: "os" for name in _module_aliases(tree, "os")})
        bare = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in ("subprocess", "os"):
                for alias in node.names:
                    bare[alias.asname or alias.name] = (node.module, alias.name)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id in modules:
                module, attr = modules[func.value.id], func.attr
                shown = f"{func.value.id}.{attr}"
            elif isinstance(func, ast.Name) and func.id in bare:
                module, attr = bare[func.id]
                shown = func.id
            else:
                continue
            if (module, attr) in _NO_STDIN:
                findings.append(
                    f"subprocess-streams: {rel_file}:{node.lineno} calls "
                    f"{shown}, which redirects a stream and takes no stdin "
                    f"argument, so it can never name all three -- on Windows "
                    f"it fails with WinError 6 wherever the std-handle table "
                    f"has gone stale. Use subprocess.run(..., "
                    f"stdin=DEVNULL, capture_output=True) instead"
                )
                continue
            if module != "subprocess" or attr not in _LAUNCHERS:
                continue
            covered = _redirected(node, attr)
            if covered is None or not covered or len(covered) == 3:
                continue
            missing = [stream for stream in _STREAMS if stream not in covered]
            devnull = (
                f"{func.value.id}.DEVNULL"
                if isinstance(func, ast.Attribute)
                else "DEVNULL, which this file must import from subprocess"
            )
            escape = "" if attr in _IMPLICIT else ", or redirect none of them"
            findings.append(
                f"subprocess-streams: {rel_file}:{node.lineno} calls {shown} "
                f"redirecting some streams and leaving {', '.join(missing)} "
                f"unnamed -- on Windows an unnamed stream resolves through a "
                f"std-handle table that can still name a closed handle, so the "
                f"launch fails with WinError 6 intermittently and for a reason "
                f"that is not the command's. Name {' and '.join(missing)} "
                f"({devnull} for a program given nothing to read){escape}"
            )
    return findings


def check_harness_tokens(root: Path, contract_roots: Iterable[Path] | None = None) -> list[str]:
    """Report harness-owned tokens in portable contracts, not native `.claude` config."""
    if contract_roots is None:
        candidates = [
            path for path in _iter_files(root)
            if ".claude" not in path.relative_to(root).parts
        ]
        ignored = _git_ignored(root, candidates)
        paths = [path for path in candidates if path not in ignored]
    else:
        paths = []
        for candidate in contract_roots:
            if candidate.is_file():
                paths.append(candidate)
            elif candidate.is_dir():
                paths.extend(_iter_files(candidate))
    findings = []
    for path in paths:
        try:
            rel_file = path.relative_to(root).as_posix()
        except ValueError:
            continue
        text, error = _read_text_result(path)
        if error is not None:
            findings.append(
                f"harness-token: {rel_file} could not be read ({error}) -- it is unchecked, "
                f"and a check that skips in silence cannot be told apart from a clean tree"
            )
            continue
        if text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for match in HARNESS_TOKENS.finditer(line):
                findings.append(
                    f"harness-token: {rel_file}:{lineno} names '{match.group(0)}' "
                    f"-- a calling contract read in both runtimes resolves against "
                    f"the directory of the file naming it"
                )
    return findings


CHECKS = (
    check_emitted_ascii,
    check_docstring_not_piped,
    check_stdio_wired,
    check_subprocess_streams,
    check_harness_tokens,
)


def _where(exc: BaseException) -> str:
    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
        try:
            return Path(frame.filename).resolve().relative_to(PLUGIN_ROOT).as_posix() + f":{frame.lineno}"
        except (ValueError, OSError):
            continue
    return "no frame inside the shipped guard"


def run(root: Path) -> list[str]:
    """Run every guard independently and return findings in report order."""
    reset_ignored_memo()
    findings: list[str] = []
    for check in CHECKS:
        try:
            findings.extend(check(root))
        except Exception as exc:  # noqa: BLE001 -- a failed guard is a finding
            findings.append(
                f"check-raised: {check.__name__} raised {type(exc).__name__} "
                f"at {_where(exc)} ({exc}) -- that check reported nothing, "
                f"so what it covers is unchecked and this run does not say the "
                f"tree is clean. Every other check's findings stand and are listed "
                f"with this one"
            )
    return findings


def _repository_root(value: str) -> Path:
    root = Path(value)
    if not root.is_dir():
        raise argparse.ArgumentTypeError(
            "repository-root must name an existing directory; no tree was checked"
        )
    return root.resolve()


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Run portable substrate guards against a repository."
    )
    parser.add_argument("repository_root", metavar="repository-root", type=_repository_root)
    args = parser.parse_args(argv)
    findings = run(args.repository_root)
    for finding in findings:
        print(finding)
    print(f"lint: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
