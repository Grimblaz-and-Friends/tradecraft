"""Build and validate neutral recipient repositories from committed bytes."""
from __future__ import annotations

from io import BytesIO
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile


class RecipientTreeError(RuntimeError):
    """A recipient tree cannot be proved against its committed source."""


def metadata_path(output: Path) -> Path:
    return output.with_name(output.name + ".tradecraft-tree.json")


def _run(command: list[str], *, cwd: Path | None = None,
         input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command, cwd=cwd, input=input_bytes, stdin=(None if input_bytes is not None
                                                     else subprocess.DEVNULL),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
    )


def _git(root: Path, *arguments: str, input_bytes: bytes | None = None) -> bytes:
    result = _run(["git", "-C", str(root), *arguments], input_bytes=input_bytes)
    if result.returncode:
        diagnostic = result.stderr.decode("utf-8", errors="backslashreplace").strip()
        raise RecipientTreeError(
            f"git {' '.join(arguments)} failed: {diagnostic or result.returncode}"
        )
    return result.stdout


def _text(root: Path, *arguments: str) -> str:
    return _git(root, *arguments).decode("utf-8", errors="backslashreplace").strip()


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.resolve())) == os.path.normcase(str(right.resolve()))


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _source_path(value: str) -> str:
    normalized = value.replace("\\", "/").strip("/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts:
        raise RecipientTreeError(f"recipient path must be repository-relative: {value}")
    return path.as_posix()


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(_source_path(value) for value in values))


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _digest(value: dict[str, object]) -> str:
    unsigned = dict(value)
    unsigned.pop("metadata_sha256", None)
    return hashlib.sha256(_json_bytes(unsigned)).hexdigest()


def _blob_oid(source: Path, content: bytes) -> str:
    algorithm = _text(source, "rev-parse", "--show-object-format")
    if algorithm not in {"sha1", "sha256"}:
        raise RecipientTreeError(f"unsupported Git object format: {algorithm}")
    framed = b"blob " + str(len(content)).encode("ascii") + b"\0" + content
    return hashlib.new(algorithm, framed).hexdigest()


def _tree_files(root: Path, revision: str,
                requested: list[str] | None = None) -> dict[str, dict[str, str]]:
    arguments = ["ls-tree", "-r", "-z", revision]
    if requested:
        arguments.extend(("--", *requested))
    found: dict[str, dict[str, str]] = {}
    for entry in _git(root, *arguments).split(b"\0"):
        if not entry:
            continue
        header, separator, raw_name = entry.partition(b"\t")
        fields = header.split()
        if not separator or len(fields) != 3:
            raise RecipientTreeError("cannot parse committed recipient entry")
        mode, kind, oid = (field.decode("ascii") for field in fields)
        name = raw_name.decode("utf-8")
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise RecipientTreeError(f"recipient path is not a regular Git file: {name}")
        found[name] = {"mode": mode, "oid": oid}
    return found


def _required_files(source: Path, revision: str, requested: list[str],
                    exclusions: list[str]) -> dict[str, dict[str, str]]:
    available = _tree_files(source, revision, requested)
    for required in requested:
        if not any(name == required or name.startswith(required.rstrip("/") + "/")
                   for name in available):
            raise RecipientTreeError(f"required source path is absent: {required}")
    selected = {
        name: claim for name, claim in available.items()
        if not any(fnmatch.fnmatchcase(name, pattern) for pattern in exclusions)
    }
    for required in requested:
        if not any(name == required or name.startswith(required.rstrip("/") + "/")
                   for name in selected):
            raise RecipientTreeError(f"required source path was excluded: {required}")
    return dict(sorted(selected.items()))


def _extract_archive(source: Path, revision: str, files: dict[str, dict[str, str]],
                     destination: Path, deny_texts: list[str]) -> dict[str, dict[str, str]]:
    archive = _git(source, "archive", "--format=tar", revision, "--", *files)
    extracted: set[str] = set()
    claims: dict[str, dict[str, str]] = {}
    with tarfile.open(fileobj=BytesIO(archive), mode="r:") as stream:
        for member in stream.getmembers():
            name = _source_path(member.name)
            target = destination / Path(*PurePosixPath(name).parts)
            if not _inside(target, destination):
                raise RecipientTreeError(f"archive member escapes recipient root: {name}")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise RecipientTreeError(f"archive contains an unsupported entry: {name}")
            reader = stream.extractfile(member)
            if reader is None:
                raise RecipientTreeError(f"archive entry has no bytes: {name}")
            content = reader.read()
            for probe in deny_texts:
                if probe.encode("utf-8") in content:
                    raise RecipientTreeError(f"denied text found in recipient path: {name}")
            expected = files.get(name)
            if expected is None:
                raise RecipientTreeError(f"archive contains an undeclared file: {name}")
            source_oid = expected["oid"]
            extracted_oid = _blob_oid(source, content)
            if extracted_oid != source_oid:
                raise RecipientTreeError(
                    f"archive transformed committed bytes: {name}; "
                    f"source={source_oid}; archive={extracted_oid}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            target.chmod(0o755 if expected["mode"] == "100755" else 0o644)
            extracted.add(name)
            claims[name] = dict(expected)
    missing = sorted(set(files) - extracted)
    if missing:
        raise RecipientTreeError(
            "git archive omitted required committed paths: " + ", ".join(missing)
        )
    return claims


def _initialize_neutral_repository(root: Path, files: dict[str, dict[str, str]]) -> None:
    _run_checked = lambda *args: _git(root, *args)
    _run_checked("init", "--quiet")
    for key, value in (
        ("user.name", "Tradecraft recipient"),
        ("user.email", "recipient@tradecraft.invalid"),
        ("commit.gpgsign", "false"),
        ("core.autocrlf", "false"),
        ("core.longpaths", "true"),
    ):
        _run_checked("config", key, value)
    _run_checked("add", "-f", "--all")
    for name, claim in files.items():
        executable = "+x" if claim["mode"] == "100755" else "-x"
        _run_checked("update-index", f"--chmod={executable}", "--", name)
    _run_checked("commit", "--quiet", "-m", "Neutral recipient snapshot")
    _run_checked("checkout", "--quiet", "--detach", "HEAD")
    if _tree_files(root, "HEAD") != files:
        raise RecipientTreeError("neutral commit modes or object ids do not match the source")


def _prove_neutral_repository(root: Path, source: Path) -> None:
    if not _same_path(Path(_text(root, "rev-parse", "--show-toplevel")), root):
        raise RecipientTreeError("recipient root is not its Git top level")
    attached = _run(["git", "-C", str(root), "symbolic-ref", "-q", "HEAD"])
    if attached.returncode not in {0, 1}:
        raise RecipientTreeError("cannot inspect recipient HEAD")
    if attached.returncode == 0:
        raise RecipientTreeError("recipient root is not detached")
    if _text(root, "rev-list", "--count", "HEAD") != "1":
        raise RecipientTreeError("recipient root does not have one neutral commit")
    if _text(root, "remote"):
        raise RecipientTreeError("recipient root unexpectedly has a remote")
    recipient_common = Path(_text(root, "rev-parse", "--git-common-dir"))
    if not recipient_common.is_absolute():
        recipient_common = root / recipient_common
    source_common = Path(_text(source, "rev-parse", "--git-common-dir"))
    if not source_common.is_absolute():
        source_common = source / source_common
    if _same_path(recipient_common, source_common):
        raise RecipientTreeError("recipient root shares source Git history")


def create_consumer_tree(
    *, source: Path, output: Path, work: str, producer_version: str, mode: str,
    paths: list[str], loading_surfaces: list[str], front_page: str | None,
    root_instructions: str | None, directed_paths: list[str],
    exclusions: list[str], deny_texts: list[str], source_revision: str | None = None,
    registration_used: bool = True,
) -> Path:
    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    if output.exists() or output.is_symlink() or metadata_path(output).exists():
        raise RecipientTreeError(f"refusing existing recipient output: {output}")
    if _inside(output, source):
        raise RecipientTreeError("recipient output must be outside the source repository")
    if not _same_path(Path(_text(source, "rev-parse", "--show-toplevel")), source):
        raise RecipientTreeError("source root is not its Git top level")
    if _text(source, "status", "--porcelain"):
        raise RecipientTreeError("source root must be clean")
    revision = _text(
        source, "rev-parse", "--verify", f"{source_revision or 'HEAD'}^{{commit}}"
    )
    job_paths = _unique(paths)
    if not job_paths:
        raise RecipientTreeError("tree requires at least one --path")
    if mode == "adopter":
        if not loading_surfaces:
            raise RecipientTreeError("adopter mode requires --loading-surface")
        surfaces = _unique(loading_surfaces)
    elif mode == "repository-session":
        if not front_page or not root_instructions:
            raise RecipientTreeError(
                "repository-session mode requires --front-page and --root-instructions"
            )
        surfaces = _unique([front_page, root_instructions, *directed_paths])
    else:
        raise RecipientTreeError(f"unsupported recipient mode: {mode}")
    normalized_exclusions = _unique(exclusions) if exclusions else []
    requested = _unique([*job_paths, *surfaces])
    files = _required_files(source, revision, requested, normalized_exclusions)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".tradecraft-tree-", dir=output.parent) as temporary:
        staged = Path(temporary) / "recipient"
        staged.mkdir()
        file_claims = _extract_archive(source, revision, files, staged, deny_texts)
        _initialize_neutral_repository(staged, file_claims)
        _prove_neutral_repository(staged, source)
        staged.replace(output)
    value: dict[str, object] = {
        "schema_version": 1,
        "work": work,
        "producer_version": producer_version,
        "tree_root": str(output),
        "source_root": str(source),
        "source_revision": revision,
        "registration_used": registration_used,
        "mode": mode,
        "job_paths": job_paths,
        "carried_surfaces": surfaces,
        "exclusions": normalized_exclusions,
        "files": file_claims,
        "verification": "raw-object-ids-match",
    }
    value["metadata_sha256"] = _digest(value)
    try:
        metadata_path(output).write_bytes(_json_bytes(value))
    except OSError:
        shutil.rmtree(output, ignore_errors=True)
        raise
    return metadata_path(output)


def load_consumer_tree_metadata(metadata: Path, *, work: str) -> dict[str, object]:
    """Authenticate adjacent metadata before a caller trusts its source claim."""
    metadata = metadata.expanduser().resolve()
    try:
        value = json.loads(metadata.read_bytes())
    except (OSError, UnicodeError, ValueError) as exc:
        raise RecipientTreeError(f"cannot read consumer-tree metadata: {metadata}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise RecipientTreeError("consumer-tree metadata has an unsupported shape")
    if value.get("metadata_sha256") != _digest(value):
        raise RecipientTreeError("consumer-tree metadata digest does not match")
    if value.get("work") != work:
        raise RecipientTreeError("consumer-tree metadata names another work item")
    if not isinstance(value.get("registration_used", True), bool):
        raise RecipientTreeError("consumer-tree metadata has an invalid registration claim")
    return value


def validate_consumer_tree(
    metadata: Path, *, work: str, source: Path,
    claim: dict[str, object] | None = None,
) -> Path:
    metadata = metadata.expanduser().resolve()
    value = claim if claim is not None else load_consumer_tree_metadata(metadata, work=work)
    if value.get("metadata_sha256") != _digest(value) or value.get("work") != work:
        raise RecipientTreeError("consumer-tree metadata claim is not authenticated")
    root_value = value.get("tree_root")
    files = value.get("files")
    if not isinstance(root_value, str) or not isinstance(files, dict):
        raise RecipientTreeError("consumer-tree metadata lacks its root or files")
    root = Path(root_value).expanduser().resolve()
    source = source.expanduser().resolve()
    if not root.is_dir() or metadata != metadata_path(root):
        raise RecipientTreeError("consumer-tree metadata is not adjacent to its tree")
    revision = value.get("source_revision")
    if not isinstance(revision, str):
        raise RecipientTreeError("consumer-tree metadata lacks its source revision")
    try:
        resolved_revision = _text(source, "rev-parse", "--verify", f"{revision}^{{commit}}")
    except RecipientTreeError as exc:
        raise RecipientTreeError("consumer-tree source revision is absent") from exc
    if resolved_revision != revision:
        raise RecipientTreeError("consumer-tree source revision is not canonical")
    if value.get("registration_used", True) and revision != _text(source, "rev-parse", "HEAD"):
        raise RecipientTreeError("consumer tree does not match the registered revision")
    if value.get("source_root") != str(source):
        raise RecipientTreeError("consumer-tree metadata names another source root")
    if _text(source, "status", "--porcelain"):
        raise RecipientTreeError("registered source root is dirty")
    _prove_neutral_repository(root, source)
    status = _git(
        root, "status", "--porcelain=v1", "--ignored", "--untracked-files=all", "-z"
    )
    if status:
        raise RecipientTreeError("consumer tree contains changed or undeclared entries")
    manifest: dict[str, dict[str, str]] = {}
    for name, expected in files.items():
        if (not isinstance(name, str) or _source_path(name) != name
                or not isinstance(expected, dict)
                or set(expected) != {"mode", "oid"}
                or expected.get("mode") not in {"100644", "100755"}
                or not isinstance(expected.get("oid"), str)):
            raise RecipientTreeError("consumer-tree metadata has an invalid file claim")
        manifest[name] = {"mode": expected["mode"], "oid": expected["oid"]}
    if _tree_files(root, "HEAD") != manifest:
        raise RecipientTreeError("consumer-tree committed paths do not match the manifest")
    source_files = _tree_files(source, revision, list(manifest))
    if source_files != manifest:
        raise RecipientTreeError("consumer-tree manifest does not match the source revision")
    for name, expected in manifest.items():
        path = root / Path(*PurePosixPath(name).parts)
        if not path.is_file():
            raise RecipientTreeError(f"consumer tree is missing a carried file: {name}")
        actual = _blob_oid(source, path.read_bytes())
        if actual != expected["oid"]:
            raise RecipientTreeError(f"consumer-tree bytes do not match source: {name}")
    return root


def neutral_judging_root(source: Path):
    """Return a context manager yielding one empty, detached neutral repository."""
    return _NeutralRoot(source)


class _NeutralRoot:
    def __init__(self, source: Path):
        self.source = source.expanduser().resolve()
        self.temporary: tempfile.TemporaryDirectory[str] | None = None

    def __enter__(self) -> Path:
        self.temporary = tempfile.TemporaryDirectory(prefix="tradecraft-neutral-")
        root = Path(self.temporary.name).resolve()
        _git(root, "init", "--quiet")
        for key, value in (
            ("user.name", "Tradecraft recipient"),
            ("user.email", "recipient@tradecraft.invalid"),
            ("commit.gpgsign", "false"),
            ("core.autocrlf", "false"),
            ("core.longpaths", "true"),
        ):
            _git(root, "config", key, value)
        _git(root, "commit", "--quiet", "--allow-empty", "-m", "Neutral recipient root")
        _git(root, "checkout", "--quiet", "--detach", "HEAD")
        _prove_neutral_repository(root, self.source)
        return root

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self.temporary is not None:
            self.temporary.cleanup()
