"""Entrance-owned, independent artifact checkouts and their bundle lifecycle."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid

import dispatch_record as records
import run_lifecycle as lifecycle
from seat_process import run_process
from winio import utf8_stdio

MECHANISM_VERSION = "0.186.0"
GIT_BINDINGS = frozenset({
    "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_QUARANTINE_PATH", "GIT_SHALLOW_FILE", "GIT_NAMESPACE", "GIT_PREFIX",
    "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT",
})


class ArtifactTreeError(RuntimeError):
    """Copy evidence cannot authorize an author or recursive disposal."""


def _binding(key):
    key = key.upper()
    return key in GIT_BINDINGS or key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))


def environment():
    return {key: value for key, value in os.environ.items() if not _binding(key)}


@contextmanager
def isolated_git_environment():
    """Sanitize entrance/launcher probes too, without changing other stages."""
    saved = {key: value for key, value in os.environ.items() if _binding(key)}
    for key in saved:
        del os.environ[key]
    try:
        yield
    finally:
        os.environ.update(saved)


def git(root, *args, trust=()):
    command = ["git"]
    for path in trust:
        command.extend(("-c", f"safe.directory={path}"))
    command.extend(("-C", str(root), *args))
    result = run_process(command, input=b"", cwd=Path.cwd(), env=environment(),
                         timeout=lifecycle.probe_timeout(120), on_tick=lambda: None,
                         cleanup_deadline=lifecycle.cleanup_deadline())
    if getattr(result, "cleanup_proven", True) is False:
        error = ArtifactTreeError("artifact Git process cleanup is unproved")
        error.cleanup_proven = False
        raise error
    if result.returncode:
        raise ArtifactTreeError(result.stderr.decode("utf-8", "backslashreplace").strip())
    return result.stdout.decode("utf-8").strip()


def source(holder):
    holder = Path(holder).expanduser().resolve()
    top = Path(git(holder, "rev-parse", "--show-toplevel")).resolve()
    if holder != top:
        raise ArtifactTreeError(f"artifact source must be the holder repository top level: {top}")
    commit = git(holder, "rev-parse", "HEAD")
    if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit) is None:
        raise ArtifactTreeError("artifact source commit is invalid")
    return holder, commit


def _identity(root):
    stat = root.lstat()
    return {"device": stat.st_dev, "inode": stat.st_ino}


def _linked(path):
    return path.is_symlink() or path.is_junction()


def _inside(path, root):
    return path == root or root in path.parents


def _protect(root, holder, forbidden):
    protected = [Path(holder).resolve(), *(Path(p).resolve() for p in forbidden)]
    if any(_inside(root, p) or _inside(p, root) for p in protected):
        raise ArtifactTreeError(f"artifact allocation overlaps a holder or implementation tree: {root}")


def validate_allocation(copy, *, forbidden=()):
    root = Path(copy["root"])
    parent = Path(copy["temporary_parent"])
    if (not root.is_absolute() or not parent.is_absolute() or root.parent != parent
            or root.name != "tradecraft-artifact-" + copy["allocation_id"]
            or parent.resolve() != parent or root.resolve() != root
            or _linked(root) or not root.is_dir() or _identity(root) != copy["directory_identity"]):
        raise ArtifactTreeError(f"artifact allocation is missing or substituted: {root}")
    _protect(root, copy["holder_root"], forbidden)
    return root


def _working_root(root):
    if Path(git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise ArtifactTreeError(f"artifact copy has an external working tree: {root}")


def prove(copy, *, fresh=False, forbidden=()):
    root = validate_allocation(copy, forbidden=forbidden)
    _working_root(root)
    if _linked(root / ".git") or not (root / ".git").is_dir():
        raise ArtifactTreeError(f"artifact copy has linked Git metadata: {root}")
    for option in ("--absolute-git-dir", "--git-common-dir"):
        directory = Path(git(root, "rev-parse", "--path-format=absolute", option)).resolve()
        if directory != root / ".git":
            raise ArtifactTreeError(f"artifact copy has external Git metadata: {directory}")
    objects = root / ".git" / "objects"
    if (objects / "info" / "alternates").exists():
        raise ArtifactTreeError(f"artifact copy borrows objects: {root}")
    if (root / ".git" / "worktrees").exists():
        raise ArtifactTreeError(f"artifact copy has worktree links: {root}")
    for directory, dirs, files in os.walk(root / ".git", followlinks=False):
        if lifecycle.current_deadline() is not None:
            lifecycle.current_deadline().remaining()
        if any(_linked(Path(directory) / name) for name in [*dirs, *files]):
            raise ArtifactTreeError(f"artifact copy has linked Git storage: {root}")
    if git(root, "remote"):
        raise ArtifactTreeError(f"artifact copy has configured remotes: {root}")
    if fresh:
        git(root, "cat-file", "-e", copy["source_commit"] + "^{commit}")
        if (git(root, "rev-parse", "HEAD") != copy["source_commit"]
                or git(root, "status", "--porcelain=v1", "--untracked-files=all")):
            raise ArtifactTreeError(f"artifact copy is not the clean captured commit: {root}")
    return root


def _read(path):
    try:
        value = json.loads(Path(path).read_bytes())
    except (OSError, ValueError) as exc:
        raise ArtifactTreeError(f"artifact lifecycle is unreadable: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ArtifactTreeError(f"artifact lifecycle is not an object: {path}")
    return value


def provenance(request, bundle, *, holder=None, work=None, instalment=None):
    copy = request.get("artifact_copy")
    if copy is None:
        version = request.get("producer_version", "")
        core = version.split("-", 1)[0].split("+", 1)[0] if isinstance(version, str) else ""
        if re.fullmatch(r"\d+\.\d+\.\d+", core) and tuple(map(int, core.split("."))) < (0, 186, 0):
            return None
        raise ArtifactTreeError(f"copy-capable bundle lacks artifact provenance: {bundle}")
    required = {"schema_version", "root", "holder_root", "source_commit", "committed_only", "remotes",
                "lifecycle_record", "allocation_id", "temporary_parent", "directory_identity", "handover_root"}
    if (not isinstance(copy, dict) or set(copy) != required or copy["schema_version"] != 1
            or copy["committed_only"] is not True or copy["remotes"] != []
            or re.fullmatch(r"[0-9a-f]{32}", str(copy["allocation_id"])) is None
            or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", str(copy["source_commit"])) is None
            or any(not isinstance(copy[key], str) or not Path(copy[key]).is_absolute()
                   for key in ("root", "holder_root", "lifecycle_record", "temporary_parent", "handover_root"))
            or not isinstance(copy["directory_identity"], dict)
            or set(copy["directory_identity"]) != {"device", "inode"}
            or any(not isinstance(value, int) for value in copy["directory_identity"].values())
            or request.get("root") != copy["root"]):
        raise ArtifactTreeError(f"conflicting artifact copy provenance: {bundle}")
    expected_record = Path(str(bundle).removesuffix(".run.json") + ".artifact-copy.json")
    if Path(copy["lifecycle_record"]) != expected_record:
        raise ArtifactTreeError(f"artifact lifecycle belongs to a different bundle: {bundle}")
    record = _read(expected_record)
    if (record.get("schema_version") != 1 or record.get("artifact_copy") != copy
            or record.get("bundle") != str(bundle) or record.get("work") != request.get("work")
            or record.get("instalment") != request.get("instalment")
            or record.get("holder_session_id") != request.get("holder_session_id")
            or (holder is not None and Path(copy["holder_root"]).resolve() != Path(holder).resolve())
            or (work is not None and record.get("work") != work)
            or (instalment is not None and record.get("instalment") != instalment)):
        raise ArtifactTreeError(f"artifact lifecycle conflicts with work or holder: {bundle}; copy {copy['root']}")
    return copy


def accepted(run):
    result = run.get("result") or {}
    validation = result.get("return_validation") if isinstance(result, dict) else None
    return (run.get("schema_version") == records.SCHEMA_VERSION and run.get("lifecycle") == "completed"
            and bool(run.get("completed_at")) and run.get("outcome") in {"success", "success_uncontinuable"}
            and isinstance(validation, dict) and validation.get("status") == "pass"
            and bool(result.get("published_output")))


def validate_resume(request, run, bundle, **kwargs):
    copy = provenance(request, bundle, **kwargs)
    if copy is not None and not accepted(run):
        record = _read(copy["lifecycle_record"])
        if record.get("state") not in {"running", "retained"}:
            raise ArtifactTreeError(f"failed author has no retained copy: {bundle}; copy {copy['root']}")
        prove(copy)
    return copy


def _atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".tradecraft-copy-record-", dir=path.parent) as temporary:
        staged = Path(temporary) / "record.json"
        staged.write_bytes(records.json_bytes(value))
        os.replace(staged, path)


def dispose(copy, *, forbidden=()):
    """Bound removal in a contained helper; never elevate or traverse a linked root."""
    try:
        record = _read(copy["lifecycle_record"])
        if record.get("schema_version") != 1 or record.get("artifact_copy") != copy:
            raise ArtifactTreeError(f"disposal has no matching entrance authority: {copy['root']}")
        root = validate_allocation(copy, forbidden=forbidden)
        result = run_process([sys.executable, str(Path(__file__).resolve()), "--dispose"],
                             input=records.json_bytes(copy), cwd=Path.cwd(), env=environment(),
                             timeout=lifecycle.probe_timeout(10, cleanup=True), on_tick=lambda: None,
                             cleanup_deadline=lifecycle.cleanup_deadline())
        if getattr(result, "cleanup_proven", True) is False:
            raise ArtifactTreeError("artifact disposal process cleanup is unproved")
        if result.returncode or root.exists():
            raise ArtifactTreeError(result.stderr.decode("utf-8", "backslashreplace").strip() or "copy remains after disposal")
    except (OSError, ValueError, KeyError, ArtifactTreeError, TimeoutError, subprocess.TimeoutExpired) as exc:
        return {"state": "removal_failed", "remaining_path": copy["root"], "reason": str(exc)}
    return {"state": "removed", "remaining_path": None, "reason": None}


def finish(copy, output, *, invoked, unused=False, forbidden=()):
    result = {"state": "retained", "remaining_path": copy["root"], "reason": "author return was not proved accepted and stopped"}
    try:
        record = _read(copy["lifecycle_record"])
    except ArtifactTreeError as exc:
        if not invoked and unused:
            result = dispose(copy, forbidden=forbidden)
        return {**result, "lifecycle_record_error": str(exc)}
    if not invoked and unused:
        result = dispose(copy, forbidden=forbidden)
    else:
        try:
            request = _read(records.sidecar(output, ".request.json"))
            run = _read(records.sidecar(output, ".run.json"))
            provenance(request, records.sidecar(output, ".run.json"))
            returned = run.get("result") or {}
            if (request.get("artifact_copy") == copy and request.get("dispatch_id") == run.get("dispatch_id")
                    and accepted(run) and run.get("cleanup_proven") is True
                    and not run.get("launch_unresolved") and not run.get("session_identity_error")
                    and returned.get("published_output") == str(output)
                    and output.read_bytes().strip()
                    and output.read_bytes() == Path(returned["source_output"]).read_bytes()):
                result = dispose(copy, forbidden=forbidden)
        except (OSError, ValueError, KeyError, ArtifactTreeError):
            pass  # Unfinished or unproved evidence retains the draft.
    record.update(result)
    try:
        _atomic(Path(copy["lifecycle_record"]), record)
    except OSError as exc:
        result["lifecycle_record_error"] = str(exc)
    return result


@contextmanager
def checkout(holder, output, *, work, instalment, holder_session_id, predecessor=None, forbidden=()):
    """Write authority before launch and keep interrupted runs resumable."""
    prior = None
    try:
        records.require_output_outside_root(output, Path(holder))
        for protected in forbidden:
            records.require_output_outside_root(output, Path(protected))
    except records.RecordError as exc:
        raise ArtifactTreeError(str(exc)) from exc
    if predecessor is not None:
        prior = validate_resume(predecessor.request, predecessor.run, predecessor.path,
                                holder=holder, work=work, instalment=instalment)
    reuse = prior is not None and not accepted(predecessor.run)
    lifecycle_path = records.sidecar(output, ".artifact-copy.json")
    if lifecycle_path.exists() or lifecycle_path.is_symlink():
        raise ArtifactTreeError(f"artifact lifecycle already exists: {lifecycle_path}")
    if reuse:
        copy = {**prior, "lifecycle_record": str(lifecycle_path)}
    else:
        holder, commit = source(holder)
        allocation = uuid.uuid4().hex
        parent = Path(tempfile.gettempdir()).resolve()
        root = parent / ("tradecraft-artifact-" + allocation)
        _protect(root, holder, forbidden)
        root.mkdir()
        copy = {"schema_version": 1, "allocation_id": allocation, "root": str(root),
                "temporary_parent": str(parent), "directory_identity": _identity(root),
                "holder_root": str(holder), "source_commit": commit, "committed_only": True,
                "remotes": [], "lifecycle_record": str(lifecycle_path),
                "handover_root": (prior["handover_root"] if prior else
                    str(Path(predecessor.request.get("root") or holder).resolve()) if predecessor else str(root))}
    record = {"schema_version": 1, "artifact_copy": copy, "work": work, "instalment": instalment,
              "holder_session_id": holder_session_id, "bundle": str(records.sidecar(output, ".run.json")),
              "predecessor_bundle": predecessor.path if predecessor else None, "state": "running",
              "selection": "retained" if reuse else "fresh",
              "legacy_recovery": predecessor is not None and prior is None}
    if prior and not reuse and Path(prior["root"]).exists():
        record["predecessor_residue"] = prior["root"]
    residues = []
    if prior:
        prior_record = _read(prior["lifecycle_record"])
        residues = [path for path in prior_record.get("residues", [])
                    if isinstance(path, str) and Path(path).exists()]
    if record.get("predecessor_residue") and record["predecessor_residue"] not in residues:
        residues.append(record["predecessor_residue"])
    record["residues"] = residues
    invoked = {"value": False}
    try:
        _atomic(lifecycle_path, record)
        if not reuse:
            clone = ("clone", "--no-hardlinks", "--dissociate", "--no-checkout",
                     "-c", "core.longpaths=true", "--", str(holder), copy["root"])
            try:
                git(holder, *clone)
            except ArtifactTreeError as exc:
                if "detected dubious ownership" not in str(exc):
                    raise
                git_dir = Path(git(holder, "rev-parse", "--absolute-git-dir")).resolve()
                git(holder, *clone, trust=(holder.as_posix(), git_dir.as_posix()))
            for remote in git(Path(copy["root"]), "remote").splitlines():
                git(Path(copy["root"]), "remote", "remove", remote)
            # Check the effective tree before checkout can write any files.
            _working_root(Path(copy["root"]))
            git(Path(copy["root"]), "checkout", "--detach", copy["source_commit"])
        prove(copy, fresh=not reuse, forbidden=forbidden)
        yield copy, invoked, record
    except (subprocess.TimeoutExpired, OSError, ArtifactTreeError) as exc:
        if getattr(exc, "cleanup_proven", True) is False:
            # A still-unproved clone subprocess may own files in the allocation.
            invoked["value"] = True
        raise
    finally:
        result = finish(copy, output, invoked=invoked["value"], unused=not reuse, forbidden=forbidden)
        print("artifact-copy: " + json.dumps({"root": copy["root"], **result}, ensure_ascii=True), flush=True)


def main():
    utf8_stdio()
    parser = argparse.ArgumentParser(description="Remove one proved entrance-owned artifact allocation.")
    parser.add_argument("--dispose", action="store_true", required=True)
    parser.parse_args()
    copy = json.loads(sys.stdin.buffer.read())
    root = validate_allocation(copy)
    # Python's rmtree unlinks symlinks and removes Windows junctions without
    # traversing their targets. The root identity and resolved parent are proved above.
    def readonly(function, path, error):
        target = Path(path)
        if (os.name != "nt" or not isinstance(error, PermissionError)
                or not _inside(target.resolve(), root) or _linked(target)
                or target.stat().st_mode & stat.S_IWRITE):
            raise error
        # Git objects are normally read-only on Windows. Clear that local file
        # attribute only; an ACL refusal still reports residue without elevation.
        target.chmod(target.stat().st_mode | stat.S_IWRITE)
        function(path)
    shutil.rmtree(root, onexc=readonly)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
