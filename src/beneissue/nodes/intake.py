"""Intake node - fetches issue from GitHub."""

import subprocess
from pathlib import Path

from beneissue.config import load_config
from beneissue.graph.state import IssueState
from beneissue.integrations.github import (
    get_daily_run_count,
    get_existing_issues,
    get_issue,
)


def intake_node(state: IssueState) -> dict:
    """Fetch issue details and context from GitHub API."""
    repo = state["repo"]
    issue_number = state["issue_number"]
    config = load_config()

    # Fetch issue details
    result = get_issue(repo, issue_number)

    # Fetch existing issues for duplicate detection
    try:
        existing = get_existing_issues(repo, limit=50, exclude_issue=issue_number)
        result["existing_issues"] = existing
    except Exception:
        result["existing_issues"] = []

    # Get codebase structure (if running in repo context)
    result["codebase_structure"] = get_codebase_structure()

    # Check daily rate limit using config
    daily_limit = config.policy.daily_limits.triage
    try:
        run_count = get_daily_run_count(repo, "beneissue-workflow.yml")
        result["daily_run_count"] = run_count
        result["daily_limit_exceeded"] = run_count >= daily_limit
    except Exception:
        result["daily_run_count"] = 0
        result["daily_limit_exceeded"] = False

    return result


def get_codebase_structure(max_depth: int = 3, max_files: int = 100) -> str:
    """Get codebase directory structure for context.

    Args:
        max_depth: Maximum directory depth to traverse
        max_files: Maximum number of files to include

    Returns:
        Formatted directory tree string
    """
    # Check if we're in a git repo
    if not Path(".git").exists():
        return "Codebase structure not available (not in git repository)."

    try:
        # Use git ls-files for tracked files only
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return "Codebase structure not available."

        files = result.stdout.strip().split("\n")[:max_files]

        # Build tree structure
        tree = _build_file_tree(files, max_depth)
        return tree

    except Exception as e:
        return f"Codebase structure not available: {e}"


def _build_file_tree(files: list[str], max_depth: int) -> str:
    """Build a tree representation from file paths."""
    if not files:
        return "Empty repository."

    # Group files by directory
    tree: dict = {}
    for filepath in files:
        parts = filepath.split("/")
        if len(parts) > max_depth:
            # Truncate deep paths
            parts = parts[:max_depth] + ["..."]

        current = tree
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        # Add file
        filename = parts[-1]
        current[filename] = None

    # Format tree
    lines = []
    _format_tree(tree, lines, "")

    return "\n".join(lines[:100])  # Limit output


def _format_tree(node: dict, lines: list[str], prefix: str) -> None:
    """Recursively format tree with indentation."""
    items = sorted(node.items(), key=lambda x: (x[1] is not None, x[0]))

    for i, (name, subtree) in enumerate(items):
        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{name}")

        if subtree is not None:  # It's a directory
            extension = "    " if is_last else "│   "
            _format_tree(subtree, lines, prefix + extension)
