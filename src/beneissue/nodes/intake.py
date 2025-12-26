"""Intake node - fetches issue from GitHub."""

from beneissue.config import load_config
from beneissue.graph.state import IssueState
from beneissue.integrations.github import (
    get_daily_run_count,
    get_existing_issues,
    get_issue,
)
from beneissue.observability import log_node_event, traced_node


@traced_node("intake", run_type="tool", log_output=True)
def intake_node(state: IssueState) -> dict:
    """Fetch issue details and context from GitHub API."""
    repo = state["repo"]
    issue_number = state["issue_number"]
    config = load_config()

    log_node_event("intake", f"Fetching issue #{issue_number} from {repo}")

    # Fetch issue details
    result = get_issue(repo, issue_number)

    # Fetch existing issues for duplicate detection
    try:
        existing = get_existing_issues(repo, limit=50, exclude_issue=issue_number)
        result["existing_issues"] = existing
        log_node_event("intake", f"Found {len(existing)} existing issues for duplicate detection")
    except Exception:
        result["existing_issues"] = []

    # Check daily rate limit using config based on command type
    command = state.get("command", "run")
    match command:
        case "triage":
            daily_limit = config.limits.daily.triage
        case "analyze":
            daily_limit = config.limits.daily.analyze
        case "fix":
            daily_limit = config.limits.daily.fix
        case _:  # "run" uses the most restrictive (fix) limit
            daily_limit = config.limits.daily.fix

    try:
        run_count = get_daily_run_count(repo, "beneissue-workflow.yml")
        result["daily_run_count"] = run_count
        result["daily_limit_exceeded"] = run_count >= daily_limit
        if result["daily_limit_exceeded"]:
            log_node_event(
                "intake",
                f"Daily limit exceeded for {command}: {run_count}/{daily_limit}",
                "warning",
            )
    except Exception:
        result["daily_run_count"] = 0
        result["daily_limit_exceeded"] = False

    return result
