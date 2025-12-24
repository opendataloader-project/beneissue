"""GitHub API integration."""

import os

from github import Github


def get_github_client() -> Github:
    """Get authenticated GitHub client."""
    token = os.environ.get("BENEISSUE_TOKEN")
    if not token:
        raise ValueError("BENEISSUE_TOKEN environment variable is required")
    return Github(token)


def get_issue(repo: str, issue_number: int) -> dict:
    """Fetch issue details from GitHub."""
    gh = get_github_client()
    repository = gh.get_repo(repo)
    issue = repository.get_issue(issue_number)

    return {
        "issue_title": issue.title,
        "issue_body": issue.body or "",
        "issue_labels": [label.name for label in issue.labels],
        "issue_author": issue.user.login,
    }
