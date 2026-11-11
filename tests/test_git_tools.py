"""Unit tests for Git tools."""

import tempfile
from pathlib import Path
import pytest

from sample_data.synthetic_repo_builder import create_synthetic_buggy_repo
from src.tools.git_tools import (
    GitToolError,
    get_changed_files,
    get_file_context,
    get_git_diff,
)

SAMPLE_DIFF = """diff --git a/app/main.py b/app/main.py
index e69de29..49b6b77 100644
--- a/app/main.py
+++ b/app/main.py
@@ -1,3 +1,5 @@
+import os
+API_KEY = "12345"
 def hello():
-    return "old"
+    return "new"
"""


def test_get_changed_files_empty():
    assert get_changed_files("") == []
    assert get_changed_files("   \n  ") == []


def test_get_changed_files_parsing():
    files = get_changed_files(SAMPLE_DIFF)
    assert len(files) == 1
    info = files[0]
    assert info["file_path"] == "app/main.py"
    assert info["status"] == "modified"
    assert len(info["hunk_ranges"]) == 1
    # Added lines should contain line numbers
    added_lines_dict = dict(info["added_lines"])
    assert 1 in added_lines_dict
    assert "import os" in added_lines_dict[1]


def test_get_git_diff_synthetic_repo(tmp_path):
    repo_dir = create_synthetic_buggy_repo(tmp_path / "test_repo")
    diff = get_git_diff(str(repo_dir), base_ref="HEAD~1", head_ref="HEAD")
    assert "user_service.py" in diff
    assert "cursor.execute" in diff


def test_get_git_diff_invalid_path():
    with pytest.raises(GitToolError, match="does not exist"):
        get_git_diff("non_existent_directory_12345_xyz")

    with pytest.raises(ValueError, match="cannot be empty"):
        get_git_diff("")


def test_get_git_diff_non_git_dir(tmp_path):
    non_git = tmp_path / "empty_dir"
    non_git.mkdir()
    with pytest.raises(GitToolError, match="Not a valid Git repository"):
        get_git_diff(str(non_git))


def test_get_git_diff_malicious_ref(tmp_path):
    repo_dir = create_synthetic_buggy_repo(tmp_path / "test_repo_ref")
    with pytest.raises(ValueError, match="Invalid characters"):
        get_git_diff(str(repo_dir), base_ref="HEAD; rm -rf /")


def test_get_file_context(tmp_path):
    repo_dir = create_synthetic_buggy_repo(tmp_path / "test_repo_ctx")
    context = get_file_context(
        repo_path=str(repo_dir),
        changed_files=["app/calculator.py"],
        max_lines=50,
    )
    assert "app/calculator.py" in context
    assert "def add" in context["app/calculator.py"]
    # Should also auto-discover the test file
    test_key = [k for k in context if "test_calculator" in k]
    assert len(test_key) > 0


def test_get_file_context_path_traversal_guard(tmp_path):
    repo_dir = create_synthetic_buggy_repo(tmp_path / "test_repo_ctx_guard")
    # Attempting to read outside the repo
    context = get_file_context(
        repo_path=str(repo_dir),
        changed_files=["../../some_external_file.txt"],
    )
    assert len(context) == 0
