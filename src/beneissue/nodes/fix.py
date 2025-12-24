"""Fix node implementation using Claude Code."""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from langsmith import traceable

from beneissue.graph.state import IssueState

# Regex pattern for GitHub PR URLs
PR_URL_PATTERN = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/pull/\d+")

# Load prompt from file
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "fix.md"
FIX_PROMPT = PROMPT_PATH.read_text()

# Timeout for Claude Code execution (5 minutes)
CLAUDE_CODE_TIMEOUT = 300


def _extract_pr_url(output: str) -> str | None:
    """Extract PR URL from Claude Code output.

    Tries multiple strategies:
    1. Parse as JSON and look for pr_url field
    2. Search for GitHub PR URL pattern in text
    """
    # Try JSON parsing first
    try:
        data = json.loads(output)
        if isinstance(data, dict) and data.get("pr_url"):
            return data["pr_url"]
    except json.JSONDecodeError:
        pass

    # Search for PR URL pattern in output
    match = PR_URL_PATTERN.search(output)
    if match:
        return match.group(0)

    return None


def _clone_repo(repo: str, target_dir: str) -> bool:
    """Clone a repository to a target directory."""
    token = os.environ.get("BENEISSUE_TOKEN")
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
        repo=state["repo"],
        analysis_summary=state.get("analysis_summary", "No analysis available"),
        affected_files=affected_files_str,
    )


@traceable(name="claude_code_fix", run_type="chain")
def fix_node(state: IssueState) -> dict:
    """Execute fix using Claude Code CLI."""
    prompt = _build_fix_prompt(state)

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
            # Run Claude Code
            result = subprocess.run(
                ["claude", "-p", prompt, "--output-format", "json"],
                capture_output=True,
                timeout=CLAUDE_CODE_TIMEOUT,
                cwd=repo_path,
                env={
                    **os.environ,
                    "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
                },
            )

            if result.returncode == 0:
                stdout = result.stdout.decode()
                pr_url = _extract_pr_url(stdout)

                return {
                    "fix_success": True,
                    "pr_url": pr_url,
                    "labels_to_remove": ["fix/auto-eligible"],
                    "labels_to_add": ["fix/completed"],
                }
            else:
                stderr = result.stderr.decode() if result.stderr else "Unknown error"
                return {
                    "fix_success": False,
                    "fix_error": stderr[:500],  # Truncate long errors
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
