"""Analyze node implementation using Claude Code."""

import os
import sys
import tempfile
from pathlib import Path

from langsmith import traceable

from beneissue.graph.state import IssueState
from beneissue.integrations.claude_code import parse_json_from_output, run_claude_code
from beneissue.integrations.github import clone_repo
from beneissue.nodes.schemas import AnalyzeResult


def _log(message: str, level: str = "info") -> None:
    """Log message to stderr for GitHub Actions visibility."""
    prefix = {"info": "ℹ️", "success": "✅", "error": "❌", "warning": "⚠️"}.get(level, "")
    print(f"{prefix} [analyze] {message}", file=sys.stderr, flush=True)


# Load prompt from file
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "analyze.md"
ANALYZE_PROMPT = PROMPT_PATH.read_text()

# Timeout for Claude Code execution (3 minutes for analysis)
CLAUDE_CODE_TIMEOUT = 180


def _build_analyze_prompt(state: IssueState) -> str:
    """Build the analyze prompt for Claude Code."""
    repo = state.get("repo", "")
    repo_owner = repo.split("/")[0] if "/" in repo else "unknown"

    return ANALYZE_PROMPT.format(
        issue_title=state["issue_title"],
        issue_body=state["issue_body"],
        repo_owner=repo_owner,
    )


def _parse_analyze_response(output: str) -> AnalyzeResult | None:
    """Parse Claude Code output to extract AnalyzeResult."""
    data = parse_json_from_output(output, required_key="summary")
    if data:
        try:
            return AnalyzeResult(**data)
        except (ValueError, TypeError):
            pass
    return None


def _run_analysis(
    repo_path: str, prompt: str, *, verbose: bool = False, repo_owner: str | None = None
) -> dict:
    """Run Claude Code analysis on a repository path."""
    _log("Running Claude Code to analyze issue...")

    result = run_claude_code(
        prompt=prompt,
        cwd=repo_path,
        allowed_tools=["Read", "Glob", "Grep"],
        timeout=CLAUDE_CODE_TIMEOUT,
        verbose=verbose,
    )

    if result.stdout:
        _log("=== Claude Code Output ===")
        print(result.stdout, file=sys.stderr, flush=True)
        _log("=== End Claude Code Output ===")

    if result.error:
        _log(f"Analysis error: {result.error}", "error")
        return _fallback_analyze(result.error, repo_owner=repo_owner)

    if not result.success:
        error_msg = result.stderr[:200] if result.stderr else "Unknown error"
        _log(f"Analysis failed: {error_msg}", "error")
        return _fallback_analyze(error_msg, repo_owner=repo_owner)

    response = _parse_analyze_response(result.stdout)

    if response:
        _log(
            f"Analysis complete: fix_decision={response.fix_decision}, priority={response.priority}",
            "success",
        )
        return _build_result(response, repo_owner=repo_owner)

    _log(f"Failed to parse analysis output: {result.stdout[:200]}", "error")
    return _fallback_analyze(
        f"Failed to parse analysis output: {result.stdout[:200]}", repo_owner=repo_owner
    )


@traceable(name="claude_code_analyze", run_type="chain")
def analyze_node(state: IssueState) -> dict:
    """Analyze an issue using Claude Code CLI."""
    prompt = _build_analyze_prompt(state)
    verbose = state.get("verbose", False)

    _log(f"Starting analysis for issue: {state.get('issue_title', 'Unknown')}")

    repo = state.get("repo", "")
    repo_owner = repo.split("/")[0] if "/" in repo else None

    # Use project_root if provided (for testing), otherwise clone
    if state.get("project_root"):
        _log(f"Using local project root: {state['project_root']}")
        return _run_analysis(
            str(state["project_root"]), prompt, verbose=verbose, repo_owner=repo_owner
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = os.path.join(temp_dir, "repo")

        _log(f"Cloning repository {repo}...")
        if not clone_repo(state["repo"], repo_path):
            _log("Failed to clone repository", "error")
            return _fallback_analyze("Failed to clone repository", repo_owner=repo_owner)

        return _run_analysis(repo_path, prompt, verbose=verbose, repo_owner=repo_owner)


def _build_result(response: AnalyzeResult, repo_owner: str | None = None) -> dict:
    """Build the result dict from AnalyzeResult."""
    assignee = response.assignee if response.assignee else repo_owner

    return {
        "analysis_summary": response.summary,
        "affected_files": response.affected_files,
        "fix_decision": response.fix_decision,
        "fix_reason": response.reason,
        "priority": response.priority,
        "story_points": response.story_points,
        "comment_draft": response.comment_draft,
        "assignee": assignee,
        "labels_to_add": [f"fix/{response.fix_decision.replace('_', '-')}"],
    }


def _fallback_analyze(error: str, repo_owner: str | None = None) -> dict:
    """Return a fallback analysis when Claude Code fails."""
    return {
        "analysis_summary": f"Analysis incomplete: {error}",
        "affected_files": [],
        "fix_decision": "manual_required",
        "fix_reason": f"Analysis failed: {error}",
        "comment_draft": f"Automated analysis encountered an issue: {error}\n\nPlease investigate manually.",
        "assignee": repo_owner,
        "labels_to_add": ["fix/manual-required"],
    }
