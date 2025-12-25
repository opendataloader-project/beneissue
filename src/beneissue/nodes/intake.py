"""Intake node - fetches issue from GitHub."""

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

    # Check daily rate limit using config
    daily_limit = config.limits.daily.triage
    try:
        run_count = get_daily_run_count(repo, "beneissue-workflow.yml")
        result["daily_run_count"] = run_count
        result["daily_limit_exceeded"] = run_count >= daily_limit
    except Exception:
        result["daily_run_count"] = 0
        result["daily_limit_exceeded"] = False

    return result
