"""Fix node implementation using Claude Code."""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from langsmith import traceable

from beneissue.graph.state import IssueState
from beneissue.integrations.github import clone_repo
from beneissue.nodes.schemas import FixResult

# Load prompt from file
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "fix.md"
FIX_PROMPT = PROMPT_PATH.read_text()

# Timeout for Claude Code execution (5 minutes)
CLAUDE_CODE_TIMEOUT = 300


def _parse_fix_output(output: str) -> FixResult | None:
    """Parse Claude Code output for FixResult JSON."""
    # Try markdown code block first, then raw JSON
    patterns = [
        r"```json\s*(\{[^`]*\})\s*```",  # ```json {...} ```
        r'(\{\s*"success"\s*:[^}]*\})',  # Raw JSON with "success" key
    ]

    for pattern in patterns:
        match = re.search(pattern, output, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                return FixResult(**data)
            except (json.JSONDecodeError, ValueError):
                continue

    return None


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


def _create_pr(
    repo_path: str, state: IssueState, fix_result: FixResult | None
) -> str | None:
    """Create a PR using gh CLI and return the PR URL."""
    issue_number = state["issue_number"]

    # Use fix result or fall back to defaults
    pr_title = (
        fix_result.title
        if fix_result and fix_result.title
        else f"Fix #{issue_number}: {state['issue_title']}"
    )
    pr_description = (
        fix_result.description
        if fix_result and fix_result.description
        else state.get("analysis_summary", "No analysis available")
    )
    pr_body = f"{pr_description}\n\n---\nCloses #{issue_number}"

    # Create PR using gh CLI
    result = subprocess.run(
        [
            "gh",
            "pr",
            "create",
            "--title",
            pr_title,
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
            "GH_TOKEN": os.environ.get("GITHUB_TOKEN", ""),
        },
    )

    if result.returncode == 0:
        # gh pr create outputs the PR URL
        return result.stdout.decode().strip()
    # Return error message for debugging
    stderr = result.stderr.decode() if result.stderr else "Unknown error"
    return f"ERROR:{stderr[:200]}"


@traceable(name="claude_code_fix", run_type="chain")
def fix_node(state: IssueState) -> dict:
    """Execute fix using Claude Code CLI."""
    prompt = _build_fix_prompt(state)
    issue_number = state["issue_number"]

    # Create temporary directory for the repo
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = os.path.join(temp_dir, "repo")

        # Clone the repository
        if not clone_repo(state["repo"], repo_path):
            return {
                "fix_success": False,
                "fix_error": "Failed to clone repository",
                "labels_to_add": ["fix/failed"],
            }

        try:
            # Run Claude Code using npx (no global installation required)
            result = subprocess.run(
                [
                    "npx",
                    "-y",
                    "@anthropic-ai/claude-code",
                    "-p",
                    prompt,
                    "--allowedTools",
                    "Read,Glob,Grep,Edit,Write,Bash"
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

            # Parse fix output
            output = result.stdout.decode() if result.stdout else ""
            fix_result = _parse_fix_output(output)

            # Check if fix reported failure
            if fix_result and not fix_result.success:
                return {
                    "fix_success": False,
                    "fix_error": fix_result.error or "Fix reported failure",
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

            # Build commit message from fix result or fallback
            commit_title = (
                fix_result.title
                if fix_result and fix_result.title
                else f"fix: resolve issue #{issue_number}"
            )
            commit_body = (
                f"{fix_result.description}\n\n" if fix_result and fix_result.description else ""
            )
            commit_msg = f"{commit_title}\n\n{commit_body}Closes #{issue_number}\nCo-Authored-By: Claude <noreply@anthropic.com>"

            # Commit changes
            _run_git(repo_path, "add", "-A")
            _run_git(repo_path, "commit", "-m", commit_msg)

            # Push branch
            push_result = _run_git(repo_path, "push", "-u", "origin", branch_name)
            if push_result.returncode != 0:
                return {
                    "fix_success": False,
                    "fix_error": f"Failed to push: {push_result.stderr.decode()[:200]}",
                    "labels_to_add": ["fix/manual-required"],
                }

            # Create PR
            pr_url = _create_pr(repo_path, state, fix_result)

            if pr_url and not pr_url.startswith("ERROR:"):
                return {
                    "fix_success": True,
                    "pr_url": pr_url,
                    "labels_to_remove": ["fix/auto-eligible"],
                    "labels_to_add": ["fix/completed"],
                }
            else:
                error_msg = pr_url[6:] if pr_url and pr_url.startswith("ERROR:") else "Failed to create PR"
                return {
                    "fix_success": False,
                    "fix_error": error_msg,
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
                "fix_error": "npx not found. Ensure Node.js is installed.",
                "labels_to_add": ["fix/manual-required"],
            }
        except Exception as e:
            return {
                "fix_success": False,
                "fix_error": str(e)[:500],
                "labels_to_add": ["fix/manual-required"],
            }
