"""Analyze node implementation using Claude Code."""

import os
import tempfile

from langsmith import traceable

from beneissue.graph.state import IssueState
from beneissue.integrations.claude_code import UsageInfo, run_claude_code
from beneissue.integrations.github import clone_repo
from beneissue.mocks import load_mock
from beneissue.nodes.schemas import AnalyzeResult
from beneissue.nodes.utils import extract_repo_owner, parse_result
from beneissue.observability import get_node_logger
from beneissue.prompts import load_prompt

logger = get_node_logger("analyze")

# Timeout for Claude Code execution (3 minutes for analysis)
CLAUDE_CODE_TIMEOUT = 180


def _build_analyze_prompt(state: IssueState) -> str:
    """Build the analyze prompt for Claude Code."""
    repo = state.get("repo", "")
    repo_owner = extract_repo_owner(repo) or "unknown"

    return load_prompt("analyze").format(
        issue_title=state["issue_title"],
        issue_body=state["issue_body"],
        repo_owner=repo_owner,
    )


def _parse_analyze_response(output: str) -> AnalyzeResult | None:
    """Parse Claude Code output to extract AnalyzeResult."""
    return parse_result(output, AnalyzeResult, required_key="summary")


def _run_analysis(
    repo_path: str, prompt: str, *, repo_owner: str | None = None
) -> tuple[dict, UsageInfo]:
    """Run Claude Code analysis on a repository path.

    Returns:
        Tuple of (result_dict, usage_info)
    """
    logger.info("Running Claude Code to analyze issue...")

    result = run_claude_code(
        prompt=prompt,
        cwd=repo_path,
        allowed_tools=["Read", "Glob", "Grep"],
        timeout=CLAUDE_CODE_TIMEOUT,
    )

    usage = result.usage
    usage.log_summary(logger)

    if result.stdout:
        logger.info("Claude Code Output:\n%s", result.stdout)

    if result.error:
        logger.error("Analysis error: %s", result.error)
        return _fallback_analyze(result.error, repo_owner=repo_owner), usage

    if not result.success:
        error_msg = result.stderr[:200] if result.stderr else "Unknown error"
        logger.error("Analysis failed: %s", error_msg)
        return _fallback_analyze(error_msg, repo_owner=repo_owner), usage

    response = _parse_analyze_response(result.stdout)

    if response:
        logger.info(
            "Analysis complete: fix_decision=%s, priority=%s",
            response.fix_decision,
            response.priority,
        )
        return _build_result(response, repo_owner=repo_owner), usage

    logger.error("Failed to parse analysis output: %s", result.stdout[:200])
    return _fallback_analyze(
        f"Failed to parse analysis output: {result.stdout[:200]}", repo_owner=repo_owner
    ), usage


@traceable(
    name="claude_code_analyze",
    run_type="llm",
    metadata={"ls_provider": "anthropic", "ls_model_name": "claude-sonnet-4-5"},
)
def analyze_node(state: IssueState) -> dict:
    """Analyze an issue using Claude Code CLI."""
    # Dry-run mode: return mock data
    if state.get("dry_run"):
        mock = load_mock("analyze", state.get("project_root"))
        repo = state.get("repo", "")
        repo_owner = extract_repo_owner(repo)
        logger.info("[DRY-RUN] Returning mock analysis result")

        fix_decision = mock.get("fix_decision", "comment_only")
        if fix_decision == "comment_only":
            labels = ["fix/comment-only", "fix/completed"]
        else:
            labels = [f"fix/{fix_decision.replace('_', '-')}"]

        return {
            "analysis_summary": mock.get("summary", "[DRY-RUN] Mock analysis"),
            "affected_files": mock.get("affected_files", []),
            "fix_decision": fix_decision,
            "fix_reason": mock.get("reason", "[DRY-RUN] Mock mode"),
            "priority": mock.get("priority", "P2"),
            "story_points": mock.get("story_points", 1),
            "comment_draft": mock.get("comment_draft"),
            "assignee": mock.get("assignee") or repo_owner,
            "labels_to_add": labels,
            **UsageInfo().to_state_dict(),
        }

    prompt = _build_analyze_prompt(state)

    logger.info("Starting analysis for issue: %s", state.get("issue_title", "Unknown"))

    repo = state.get("repo", "")
    repo_owner = extract_repo_owner(repo)

    # Use project_root if provided (for testing), otherwise clone
    if state.get("project_root"):
        logger.info("Using local project root: %s", state["project_root"])
        result, usage = _run_analysis(
            str(state["project_root"]), prompt, repo_owner=repo_owner
        )
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = os.path.join(temp_dir, "repo")

            logger.info("Cloning repository %s...", repo)
            if not clone_repo(state["repo"], repo_path):
                logger.error("Failed to clone repository")
                fallback = _fallback_analyze("Failed to clone repository", repo_owner=repo_owner)
                return {**fallback, **UsageInfo().to_state_dict()}

            result, usage = _run_analysis(repo_path, prompt, repo_owner=repo_owner)

    # Add token usage to result for state storage
    state_dict = usage.to_state_dict()
    logger.info(
        "[METRICS DEBUG] analyze_node returning usage_metadata: in_tokens=%d, out_tokens=%d",
        state_dict.get("usage_metadata", {}).get("input_tokens", 0),
        state_dict.get("usage_metadata", {}).get("output_tokens", 0),
    )
    return {**result, **state_dict}


def _build_result(response: AnalyzeResult, repo_owner: str | None = None) -> dict:
    """Build the result dict from AnalyzeResult."""
    assignee = response.assignee if response.assignee else repo_owner

    # comment_only is a successful resolution (no code change needed)
    if response.fix_decision == "comment_only":
        labels = ["fix/comment-only", "fix/completed"]
    else:
        labels = [f"fix/{response.fix_decision.replace('_', '-')}"]

    return {
        "analysis_summary": response.summary,
        "affected_files": response.affected_files,
        "fix_decision": response.fix_decision,
        "fix_reason": response.reason,
        "priority": response.priority,
        "story_points": response.story_points,
        "comment_draft": response.comment_draft,
        "assignee": assignee,
        "labels_to_add": labels,
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
