"""Intake node - fetches issue from GitHub."""

from beneissue.graph.state import IssueState
from beneissue.integrations.github import get_issue


def intake_node(state: IssueState) -> dict:
    """Fetch issue details from GitHub API."""
    return get_issue(state["repo"], state["issue_number"])
