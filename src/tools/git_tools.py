"""Git integration tools for AI Code Review Agent."""

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


class GitToolError(Exception):
    """Custom exception for Git operation failures."""
    pass


def get_git_diff(
    repo_path: str,
    base_ref: str = "HEAD~1",
    head_ref: str = "HEAD",
) -> str:
    """
    Safely retrieve a unified Git diff between two refs in a local repository.
    
    Args:
        repo_path: Absolute or relative path to the git repository.
        base_ref: Git reference (branch, tag, or commit) to compare against.
        head_ref: Git reference (branch, tag, or commit) to compare.
        
    Returns:
        Unified git diff string.
        
    Raises:
        GitToolError: When repository path is invalid or git command fails.
        ValueError: When inputs fail safety checks.
    """
    if not repo_path or not repo_path.strip():
        raise ValueError("Repository path cannot be empty.")

    resolved_path = Path(repo_path).resolve()
    if not resolved_path.exists():
        raise GitToolError(f"Repository directory does not exist: {resolved_path}")
    if not resolved_path.is_dir():
        raise GitToolError(f"Path is not a directory: {resolved_path}")

    # Guard against command injection in git references
    ref_pattern = re.compile(r"^[A-Za-z0-9_\-\.\/\^~@]+$")
    if not ref_pattern.match(base_ref):
        raise ValueError(f"Invalid characters in base_ref: {base_ref}")
    if head_ref and not ref_pattern.match(head_ref):
        raise ValueError(f"Invalid characters in head_ref: {head_ref}")

    # Verify that the path is actually a Git repository
    if not (resolved_path / ".git").exists():
        try:
            check_top = subprocess.run(
                ["git", "-C", str(resolved_path), "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            top_path = Path(check_top.stdout.strip()).resolve()
            if top_path != resolved_path:
                raise GitToolError(f"Not a valid Git repository: {resolved_path}")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise GitToolError(f"Not a valid Git repository or Git is not installed: {resolved_path}") from e

    # Build the diff command safely as an argument list (no shell=True)
    cmd = ["git", "-C", str(resolved_path), "diff"]
    if head_ref:
        cmd.extend([base_ref, head_ref])
    else:
        cmd.append(base_ref)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        stderr_msg = e.stderr.strip() if e.stderr else str(e)
        raise GitToolError(f"Git diff failed between '{base_ref}' and '{head_ref}': {stderr_msg}") from e


def get_changed_files(diff: str) -> List[Dict[str, Any]]:
    """
    Parse a unified Git diff and extract metadata for all changed files.
    
    Args:
        diff: Raw unified diff string.
        
    Returns:
        List of dictionaries containing file_path, status, changed_lines, and hunks.
    """
    if not diff or not diff.strip():
        return []

    files_info: List[Dict[str, Any]] = []
    current_file: Optional[Dict[str, Any]] = None

    # Regex patterns for git diff parsing
    diff_header_re = re.compile(r"^diff --git a/(.*?) b/(.*?)$")
    new_file_re = re.compile(r"^new file mode")
    deleted_file_re = re.compile(r"^deleted file mode")
    hunk_header_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")

    lines = diff.splitlines()
    for line in lines:
        header_match = diff_header_re.match(line)
        if header_match:
            if current_file:
                files_info.append(current_file)
            current_file = {
                "file_path": header_match.group(2),
                "old_path": header_match.group(1),
                "status": "modified",
                "added_lines": [],    # List of (line_num, line_text)
                "deleted_lines": [],  # List of (line_num, line_text)
                "hunk_ranges": [],    # List of (start_line, count)
                "patch_snippet": [],
            }
            continue

        if current_file is None:
            continue

        if new_file_re.match(line):
            current_file["status"] = "added"
        elif deleted_file_re.match(line):
            current_file["status"] = "deleted"

        hunk_match = hunk_header_re.match(line)
        if hunk_match:
            new_start = int(hunk_match.group(3))
            new_count = int(hunk_match.group(4)) if hunk_match.group(4) else 1
            current_file["hunk_ranges"].append((new_start, new_count))
            current_file["_current_new_line"] = new_start
            current_file["patch_snippet"].append(line)
            continue

        if "_current_new_line" in current_file:
            current_file["patch_snippet"].append(line)
            if line.startswith("+") and not line.startswith("+++"):
                line_no = current_file["_current_new_line"]
                current_file["added_lines"].append((line_no, line[1:]))
                current_file["_current_new_line"] += 1
            elif line.startswith("-") and not line.startswith("---"):
                current_file["deleted_lines"].append(line[1:])
            else:
                # Context line
                current_file["_current_new_line"] += 1

    if current_file:
        files_info.append(current_file)

    # Clean up temporary state keys
    for info in files_info:
        info.pop("_current_new_line", None)
        info["snippet"] = "\n".join(info.pop("patch_snippet", []))

    return files_info


def get_file_context(
    repo_path: Optional[str],
    changed_files: List[str],
    max_lines: int = 150,
) -> Dict[str, str]:
    """
    Retrieve surrounding source code and corresponding test files for changed files.
    
    Args:
        repo_path: Optional repository root path on disk.
        changed_files: List of file paths relative to repo root.
        max_lines: Limit context per file to avoid token bloat.
        
    Returns:
        Dict mapping filename to contextual source code content.
    """
    context: Dict[str, str] = {}
    if not repo_path:
        return context

    resolved_repo = Path(repo_path).resolve()
    if not resolved_repo.exists() or not resolved_repo.is_dir():
        return context

    for rel_path in changed_files:
        clean_rel = rel_path.strip().lstrip("/\\")
        src_path = (resolved_repo / clean_rel).resolve()

        # Guard against path traversal outside repository
        if not str(src_path).startswith(str(resolved_repo)):
            continue

        if src_path.exists() and src_path.is_file():
            try:
                with open(src_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = [f.readline() for _ in range(max_lines)]
                content = "".join(lines)
                if len(lines) >= max_lines:
                    content += f"\n... [Context truncated at {max_lines} lines]"
                context[rel_path] = content
            except Exception:
                pass

        # Also search for corresponding unit tests
        p = Path(clean_rel)
        stem = p.stem
        candidate_test_paths = [
            resolved_repo / "tests" / f"test_{p.name}",
            resolved_repo / "tests" / f"test_{stem}.py",
            resolved_repo / p.parent / f"test_{p.name}",
            resolved_repo / p.parent / f"{stem}_test.py",
        ]

        for test_path in candidate_test_paths:
            if test_path.exists() and test_path.is_file():
                test_rel = str(test_path.relative_to(resolved_repo)).replace("\\", "/")
                if test_rel not in context:
                    try:
                        with open(test_path, "r", encoding="utf-8", errors="replace") as f:
                            t_lines = [f.readline() for _ in range(max_lines)]
                        context[f"test::{test_rel}"] = "".join(t_lines)
                    except Exception:
                        pass
                break

    return context
