"""Fix node implementation using Claude Code."""

import os
import subprocess
import tempfile
from pathlib import Path

from langsmith import traceable

from beneissue.graph.state import IssueState

# Load prompt from file
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "fix.md"
FIX_PROMPT = PROMPT_PATH.read_text()

# Timeout for Claude Code execution (5 minutes)
CLAUDE_CODE_TIMEOUT = 300


def _clone_repo(repo: str, target_dir: str) -> bool:
    """Clone a repository to a target directory."""
    token = os.environ.get("BENEISSUE_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        repo_url = f"https://x-access-token:{token}@github.com/{repo}.git"
    else:
        repo_url = f"https://github.com/{repo}.git"

    result = subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, target_dir],
        capture_output=True,
        timeout=60,
    )
    return result.returncode == 0


def _build_fix_prompt(state: IssueState) -> str:
    """Build the fix prompt for Claude Code."""
    affected_files = state.get("affected_files", [])
    affected_files_str = (
        "\n".join(f"- {f}" for f in affected_files)
        if affected_files
        else "No specific files identified"
    )

    return FIX_PROMPT.format(
        issue_number=state["issue_number"],
        issue_title=state["issue_title"],
        analysis_summary=state.get("analysis_summary", "No analysis available"),
        affected_files=affected_files_str,
    )


def _run_git(repo_path: str, *args: str) -> subprocess.CompletedProcess:
    """Run a git command in the repo directory."""
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        cwd=repo_path,
        timeout=60,
    )


def _create_pr(repo_path: str, state: IssueState) -> str | None:
    """Create a PR using gh CLI and return the PR URL."""
    issue_number = state["issue_number"]
    issue_title = state["issue_title"]
    analysis_summary = state.get("analysis_summary", "No analysis available")

    # Get changed files
    diff_result = _run_git(repo_path, "diff", "--name-only", "HEAD")
    changed_files = diff_result.stdout.decode().strip()

    # Build PR body
    pr_body = f"""## Summary

Automated fix for #{issue_number}: **{issue_title}**

## Analysis

{analysis_summary}

## Changed Files

```
{changed_files}
```

## Test Plan

- [ ] Tests pass
- [ ] Build succeeds
- [ ] Manual verification

---
Closes #{issue_number}
"""

    # Create PR using gh CLI
    result = subprocess.run(
        [
            "gh",
            "pr",
            "create",
            "--title",
            f"Fix #{issue_number}: {issue_title}",
            "--body",
            pr_body,
            "--base",
            "main",
        ],
        capture_output=True,
        cwd=repo_path,
        timeout=60,
        env={
            **os.environ,
            "GH_TOKEN": os.environ.get("BENEISSUE_TOKEN")
            or os.environ.get("GITHUB_TOKEN", ""),
        },
    )

    if result.returncode == 0:
        # gh pr create outputs the PR URL
        return result.stdout.decode().strip()
    return None


@traceable(name="claude_code_fix", run_type="chain")
def fix_node(state: IssueState) -> dict:
    """Execute fix using Claude Code CLI."""
    prompt = _build_fix_prompt(state)
    issue_number = state["issue_number"]

    # Create temporary directory for the repo
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = os.path.join(temp_dir, "repo")

        # Clone the repository
        if not _clone_repo(state["repo"], repo_path):
            return {
                "fix_success": False,
                "fix_error": "Failed to clone repository",
                "labels_to_add": ["fix/failed"],
            }

        try:
            # Run Claude Code (code changes only, no PR)
            result = subprocess.run(
                [
                    "claude",
                    "-p",
                    prompt,
                    "--allowedTools",
                    "Read,Glob,Grep,Edit,Write,Bash",
                    "--output-format",
                    "text",
                ],
                capture_output=True,
                timeout=CLAUDE_CODE_TIMEOUT,
                cwd=repo_path,
                env={
                    **os.environ,
                    "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
                },
            )

            if result.returncode != 0:
                stderr = result.stderr.decode() if result.stderr else "Unknown error"
                return {
                    "fix_success": False,
                    "fix_error": stderr[:500],
                    "labels_to_add": ["fix/manual-required"],
                }

            # Check if there are changes
            status_result = _run_git(repo_path, "status", "--porcelain")
            if not status_result.stdout.decode().strip():
                return {
                    "fix_success": False,
                    "fix_error": "No changes were made",
                    "labels_to_add": ["fix/manual-required"],
                }

            # Create branch
            branch_name = f"fix/issue-{issue_number}"
            _run_git(repo_path, "checkout", "-b", branch_name)

            # Commit changes
            _run_git(repo_path, "add", "-A")
            _run_git(
                repo_path,
                "commit",
                "-m",
                f"fix: resolve issue #{issue_number}\n\nCo-Authored-By: Claude <noreply@anthropic.com>",
            )

            # Push branch
            push_result = _run_git(repo_path, "push", "-u", "origin", branch_name)
            if push_result.returncode != 0:
                return {
                    "fix_success": False,
                    "fix_error": f"Failed to push: {push_result.stderr.decode()[:200]}",
                    "labels_to_add": ["fix/manual-required"],
                }

            # Create PR
            pr_url = _create_pr(repo_path, state)

            if pr_url:
                return {
                    "fix_success": True,
                    "pr_url": pr_url,
                    "labels_to_remove": ["fix/auto-eligible"],
                    "labels_to_add": ["fix/completed"],
                }
            else:
                return {
                    "fix_success": False,
                    "fix_error": "Failed to create PR",
                    "labels_to_add": ["fix/manual-required"],
                }

        except subprocess.TimeoutExpired:
            return {
                "fix_success": False,
                "fix_error": f"Timeout after {CLAUDE_CODE_TIMEOUT} seconds",
                "labels_to_add": ["fix/manual-required"],
            }
        except FileNotFoundError:
            return {
                "fix_success": False,
                "fix_error": "Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code",
                "labels_to_add": ["fix/manual-required"],
            }
        except Exception as e:
            return {
                "fix_success": False,
                "fix_error": str(e)[:500],
                "labels_to_add": ["fix/manual-required"],
            }
