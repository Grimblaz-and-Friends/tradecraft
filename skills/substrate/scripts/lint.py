#!/usr/bin/env python3
"""Run the five portable substrate guards against one repository."""
from __future__ import annotations

import argparse
import ast
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
    "CLAUDE_" "PLUGIN_ROOT|CLAUDE_" "PLUGIN_DATA|CLAUDE_" "PROJECT_DIR"
    "|CLAUDE_" "SKILL_DIR|CLAUDE_" "CONFIG_DIR|CLAUDE_" "WORKING_DIR"
    "|PLUGIN_" "ROOT|PLUGIN_" "DATA|CODEX_" "HOME"
)
HARNESS_TOKENS = re.compile(
    rf"\$\{{?(?:{_HARNESS_NAMES})\}}?"
    rf"|(?i:\$env:(?:{_HARNESS_NAMES}))"
    rf"|(?i:%(?:{_HARNESS_NAMES})%)"
)


def _read_text(path: Path) -> str | None:
    """Return decoded text, or None for binary and unreadable files."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:1024]:
        return None
    return data.decode("utf-8", errors="replace")


def _iter_files(base: Path):
    """Yield every ordinary file below base in a stable order."""
    for path in sorted(base.rglob("*")):
        if path.is_file():
            yield path


def _python_files(base: Path):
    """Yield every Python file below base in a stable order."""
    for path in sorted(base.rglob("*.py")):
        if path.is_file():
            yield path


def _git_ignored(root: Path, paths: list[Path]) -> set[Path]:
    """Return paths ignored by git, or none when git cannot answer."""
    if not paths:
        return set()
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
        return set()
    if proc.returncode not in (0, 1):
        return set()
    return {Path(name) for name in proc.stdout.split("\0") if name}


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
            at = f":{exc.lineno}" if exc.lineno is not None else ""
            findings.append(
                f"emitted-ascii: {rel_file}{at} does not parse ({exc.msg}) "
                f"-- an unparseable file is not checked, and a check that skips in "
                f"silence cannot be told apart from a clean tree"
            )
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
                f"string is data rather than output, it still stays ASCII "
                f"here: build the character with chr() as the fixtures do"
            )
    return findings


def check_docstring_not_piped(root: Path) -> list[str]:
    """Report argparse help that uses a module docstring."""
    findings = []
    for path in _target_python_files(root):
        text = _read_text(path)
        if text is None:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        rel_file = path.relative_to(root).as_posix()
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


def check_stdio_wired(root: Path) -> list[str]:
    """Report scripts whose main does not wire UTF-8 streams first."""
    findings = []
    for path in _target_python_files(root, include_tests=False):
        text = _read_text(path)
        if text is None:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        main = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
        if main is None:
            continue
        rel_file = path.relative_to(root).as_posix()
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
        if not called or not imported:
            missing = "does not call it first" if imported else (
                "calls it first but never imports it" if called else "neither imports nor calls it first"
            )
            findings.append(
                f"stdio-unwired: {rel_file}:{main.lineno} defines main() and "
                f"{missing} -- runtime data the target repository did not write "
                f"reaches the stream unprotected, and a call placed later is "
                f"one that --help has outrun. Import utf8_stdio from lib/winio.py, "
                f"resolving lib/ against this file's own directory rather than "
                f"the working directory, and call it as the first statement"
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
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        modules = {name: "subprocess" for name in _module_aliases(tree, "subprocess")}
        modules.update({name: "os" for name in _module_aliases(tree, "os")})
        bare = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in ("subprocess", "os"):
                for alias in node.names:
                    bare[alias.asname or alias.name] = (node.module, alias.name)
        rel_file = path.relative_to(root).as_posix()
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
    """Report harness-owned path tokens in calling-contract material."""
    if contract_roots is None:
        candidates = [path for path in _iter_files(root) if ".git" not in path.parts]
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
        text = _read_text(path)
        if text is None:
            continue
        try:
            rel_file = path.relative_to(root).as_posix()
        except ValueError:
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


def _where(root: Path, exc: BaseException) -> str:
    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
        try:
            return Path(frame.filename).resolve().relative_to(root).as_posix() + f":{frame.lineno}"
        except (ValueError, OSError):
            continue
    return "no frame inside the target repository"


def run(root: Path) -> list[str]:
    """Run every guard independently and return findings in report order."""
    findings: list[str] = []
    for check in CHECKS:
        try:
            findings.extend(check(root))
        except Exception as exc:  # noqa: BLE001 -- a failed guard is a finding
            findings.append(
                f"check-raised: {check.__name__} raised {type(exc).__name__} "
                f"at {_where(root, exc)} ({exc}) -- that check reported nothing, "
                f"so what it covers is unchecked and this run does not say the "
                f"tree is clean. Every other check's findings stand and are listed "
                f"with this one"
            )
    return findings


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Run portable substrate guards against a repository."
    )
    parser.add_argument("repository_root", metavar="repository-root")
    args = parser.parse_args(argv)
    findings = run(Path(args.repository_root).resolve())
    for finding in findings:
        print(finding)
    print(f"lint: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
