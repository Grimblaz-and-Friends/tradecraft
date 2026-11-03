from __future__ import annotations

import hashlib
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import measure_connected_review_prompt as measure  # noqa: E402


def deleted(path: str, line: str) -> bytes:
    return (
        f"diff --git a/{path} b/{path}\ndeleted file mode 100644\nindex 1111111..0000000\n"
        f"--- a/{path}\n+++ /dev/null\n@@ -1 +0,0 @@\n-{line}\n"
    ).encode("utf-8")


def blob(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\0" + content).hexdigest()


def test_folder_comparison_separates_matches_mismatches_and_paths_a_truncated_tree_omitted(monkeypatch):
    raw = deleted("same.py", "kept") + deleted("changed.py", "new") + deleted("omitted.py", "gone")
    summarised = [{"path": path, "deleted_lines": 1} for path in ("same.py", "changed.py", "omitted.py")]
    trees = {
        "repos/owner/repo/compare/b...h?per_page=1": {"merge_base_commit": {"sha": "m" * 40}},
        "repos/owner/repo/git/trees/" + "m" * 40 + "?recursive=1": {"truncated": True, "tree": [
            {"path": "same.py", "type": "blob", "sha": blob(b"kept\n")},
            {"path": "changed.py", "type": "blob", "sha": blob(b"old\n")},
        ]},
    }
    monkeypatch.setattr(measure.cr, "gh_json", lambda endpoint, **_kwargs: trees[endpoint])
    result = measure.folder_blob_matches("owner/repo", "b", "h", raw, summarised)
    assert result == {
        "merge_base": "m" * 40, "tree_truncated": True, "folder_files": 3,
        "folder_blob_matches": 1, "folder_blob_mismatches": ["changed.py"],
        "folder_blob_unverified": ["omitted.py"],
    }
