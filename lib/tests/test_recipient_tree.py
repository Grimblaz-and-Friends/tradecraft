import json
from pathlib import Path
import subprocess
import sys

import pytest

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
import recipient_tree


def git(root, *arguments, check=True):
    return subprocess.run(
        ["git", "-C", str(root), *arguments], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check,
    )


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    git(root, "init")
    files = {
        ".gitattributes": b"* text=auto eol=lf\n",
        "job/job.md": b"run the consumer\n",
        "job/run.sh": b"#!/bin/sh\nprintf 'ran\\n'\n",
        "skill/SKILL.md": b"loading surface\n",
        "README.md": b"front page\n",
        "AGENTS.md": b"root instructions\n",
        "directed.md": b"directed instructions\n",
        "record.txt": b"SECRET-RECORD\n",
    }
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    git(root, "add", "--all")
    git(root, "update-index", "--chmod=+x", "--", "job/run.sh")
    git(root, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-m", "fixture")
    return root.resolve()


def test_adopter_tree_carries_committed_bytes_and_adjacent_metadata(source, tmp_path):
    output = tmp_path / "adopter"
    metadata = recipient_tree.create_consumer_tree(
        source=source, output=output, work="acme/widget#7", producer_version="0.151.0",
        mode="adopter", paths=["job"], loading_surfaces=["skill/SKILL.md"],
        front_page=None, root_instructions=None, directed_paths=[],
        exclusions=["record.txt"], deny_texts=["SECRET-RECORD"],
    )
    assert metadata == recipient_tree.metadata_path(output)
    assert (output / "job/job.md").read_bytes() == b"run the consumer\n"
    assert (output / "skill/SKILL.md").read_bytes() == b"loading surface\n"
    assert not (output / "record.txt").exists()
    assert git(output, "symbolic-ref", "-q", "HEAD", check=False).returncode == 1
    assert git(output, "rev-list", "--count", "HEAD").stdout.strip() == b"1"
    assert git(output, "remote").stdout.strip() == b""
    value = json.loads(metadata.read_bytes())
    assert value["work"] == "acme/widget#7"
    assert value["source_revision"] == git(source, "rev-parse", "HEAD").stdout.decode().strip()
    assert value["verification"] == "raw-object-ids-match"
    source_mode = git(source, "ls-tree", "HEAD", "--", "job/run.sh").stdout.split()[0]
    recipient_mode = git(output, "ls-tree", "HEAD", "--", "job/run.sh").stdout.split()[0]
    assert source_mode == recipient_mode == b"100755"
    assert value["files"]["job/run.sh"]["mode"] == "100755"
    assert recipient_tree.validate_consumer_tree(
        metadata, work="acme/widget#7", source=source
    ) == output.resolve()


def test_repository_session_mode_carries_every_declared_surface(source, tmp_path):
    output = tmp_path / "repository-session"
    metadata = recipient_tree.create_consumer_tree(
        source=source, output=output, work="acme/widget#7", producer_version="0.151.0",
        mode="repository-session", paths=["job/job.md"], loading_surfaces=[],
        front_page="README.md", root_instructions="AGENTS.md",
        directed_paths=["directed.md"], exclusions=[], deny_texts=[],
    )
    value = json.loads(metadata.read_bytes())
    assert value["carried_surfaces"] == ["README.md", "AGENTS.md", "directed.md"]
    for name in ("job/job.md", "README.md", "AGENTS.md", "directed.md"):
        assert (output / name).is_file()
    assert not (output / "skill/SKILL.md").exists()


@pytest.mark.parametrize("missing", ["front", "instructions"])
def test_repository_session_refuses_each_missing_required_surface(source, tmp_path, missing):
    with pytest.raises(recipient_tree.RecipientTreeError, match="requires"):
        recipient_tree.create_consumer_tree(
            source=source, output=tmp_path / missing, work="acme/widget#7",
            producer_version="0.151.0", mode="repository-session",
            paths=["job/job.md"], loading_surfaces=[],
            front_page=None if missing == "front" else "README.md",
            root_instructions=None if missing == "instructions" else "AGENTS.md",
            directed_paths=[], exclusions=[], deny_texts=[],
        )


def test_tree_refuses_export_omission_archive_transformation_and_leak(source, tmp_path):
    attributes = source / ".gitattributes"
    attributes.write_bytes(b"* text=auto eol=lf\nskill/SKILL.md export-ignore\n")
    git(source, "add", ".gitattributes")
    git(source, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-m", "ignore")
    with pytest.raises(recipient_tree.RecipientTreeError, match="omitted"):
        recipient_tree.create_consumer_tree(
            source=source, output=tmp_path / "omitted", work="acme/widget#7",
            producer_version="0.151.0", mode="adopter", paths=["job/job.md"],
            loading_surfaces=["skill/SKILL.md"], front_page=None,
            root_instructions=None, directed_paths=[], exclusions=[], deny_texts=[],
        )
    attributes.write_bytes(b"* text=auto eol=lf\njob/job.md export-subst\n")
    (source / "job/job.md").write_bytes(b"revision $Format:%H$\n")
    git(source, "add", ".gitattributes", "job/job.md")
    git(source, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-m", "transform")
    with pytest.raises(recipient_tree.RecipientTreeError, match="transformed"):
        recipient_tree.create_consumer_tree(
            source=source, output=tmp_path / "transformed", work="acme/widget#7",
            producer_version="0.151.0", mode="adopter", paths=["job/job.md"],
            loading_surfaces=["skill/SKILL.md"], front_page=None,
            root_instructions=None, directed_paths=[], exclusions=[], deny_texts=[],
        )
    attributes.write_bytes(b"* text=auto eol=lf\n")
    git(source, "add", ".gitattributes")
    git(source, "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
        "commit", "-m", "plain")
    with pytest.raises(recipient_tree.RecipientTreeError, match="denied text"):
        recipient_tree.create_consumer_tree(
            source=source, output=tmp_path / "leak", work="acme/widget#7",
            producer_version="0.151.0", mode="adopter", paths=["record.txt"],
            loading_surfaces=["skill/SKILL.md"], front_page=None,
            root_instructions=None, directed_paths=[], exclusions=[],
            deny_texts=["SECRET-RECORD"],
        )


def test_tree_refuses_source_output_and_altered_metadata(source, tmp_path):
    with pytest.raises(recipient_tree.RecipientTreeError, match="outside"):
        recipient_tree.create_consumer_tree(
            source=source, output=source / "recipient", work="acme/widget#7",
            producer_version="0.151.0", mode="adopter", paths=["job/job.md"],
            loading_surfaces=["skill/SKILL.md"], front_page=None,
            root_instructions=None, directed_paths=[], exclusions=[], deny_texts=[],
        )
    output = tmp_path / "valid"
    metadata = recipient_tree.create_consumer_tree(
        source=source, output=output, work="acme/widget#7", producer_version="0.151.0",
        mode="adopter", paths=["job/job.md"], loading_surfaces=["skill/SKILL.md"],
        front_page=None, root_instructions=None, directed_paths=[], exclusions=[], deny_texts=[],
    )
    value = json.loads(metadata.read_bytes())
    value["mode"] = "repository-session"
    metadata.write_bytes((json.dumps(value) + "\n").encode())
    with pytest.raises(recipient_tree.RecipientTreeError, match="digest"):
        recipient_tree.validate_consumer_tree(metadata, work="acme/widget#7", source=source)


def _consumer_tree(source, tmp_path, name):
    output = tmp_path / name
    metadata = recipient_tree.create_consumer_tree(
        source=source, output=output, work="acme/widget#7", producer_version="0.151.0",
        mode="adopter", paths=["job"], loading_surfaces=["skill/SKILL.md"],
        front_page=None, root_instructions=None, directed_paths=[], exclusions=[], deny_texts=[],
    )
    return output, metadata


def test_validation_refuses_an_extra_tracked_file_absent_from_manifest(source, tmp_path):
    output, metadata = _consumer_tree(source, tmp_path, "tracked-extra")
    (output / "undeclared.txt").write_bytes(b"not in metadata\n")
    git(output, "add", "undeclared.txt")
    git(output, "commit", "--amend", "--no-edit")

    with pytest.raises(recipient_tree.RecipientTreeError, match="manifest"):
        recipient_tree.validate_consumer_tree(metadata, work="acme/widget#7", source=source)


@pytest.mark.parametrize("kind", ["untracked", "ignored"])
def test_validation_refuses_untracked_and_ignored_entries(source, tmp_path, kind):
    output, metadata = _consumer_tree(source, tmp_path, kind)
    extra = output / f"{kind}.cache"
    if kind == "ignored":
        exclude = output / ".git" / "info" / "exclude"
        exclude.write_bytes(exclude.read_bytes() + b"*.cache\n")
    extra.write_bytes(b"undeclared\n")

    with pytest.raises(recipient_tree.RecipientTreeError, match="undeclared"):
        recipient_tree.validate_consumer_tree(metadata, work="acme/widget#7", source=source)
