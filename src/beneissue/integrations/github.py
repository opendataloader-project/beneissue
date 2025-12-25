"""GitHub API integration."""

import os
import subprocess
from datetime import datetime, timezone
from typing import Optional

from github import Github


def clone_repo(repo: str, target_dir: str) -> bool:
    """Clone a repository to a target directory.

    Args:
        repo: Repository in owner/repo format
        target_dir: Directory to clone into

    Returns:
        True if clone succeeded, False otherwise
    """
    token = os.environ.get("GITHUB_TOKEN")
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


def get_github_client() -> Github:
    """Get authenticated GitHub client."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable is required")
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


def get_existing_issues(
    repo: str,
    limit: int = 50,
    exclude_issue: Optional[int] = None,
) -> list[dict]:
    """Fetch existing issues for duplicate detection.

    Args:
        repo: Repository in owner/repo format
        limit: Maximum number of issues to fetch
        exclude_issue: Issue number to exclude (current issue)

    Returns:
        List of issues with number, title, state, labels
    """
    gh = get_github_client()
    repository = gh.get_repo(repo)

    issues = []
    for issue in repository.get_issues(state="all", sort="created", direction="desc"):
        if len(issues) >= limit:
            break
        if exclude_issue and issue.number == exclude_issue:
            continue
        if issue.pull_request:
            continue  # Skip PRs

        issues.append(
            {
                "number": issue.number,
                "title": issue.title,
                "state": issue.state,
                "labels": [label.name for label in issue.labels],
            }
        )

    return issues


def format_existing_issues(issues: list[dict]) -> str:
    """Format existing issues for LLM prompt context.

    Args:
        issues: List of issue dicts from get_existing_issues()

    Returns:
        Formatted string for prompt context
    """
    if not issues:
        return "No existing issues found."

    lines = []
    for issue in issues:
        state = "open" if issue.get("state") == "open" else "closed"
        labels = ", ".join(issue.get("labels", [])) if issue.get("labels") else ""
        label_str = f" [{labels}]" if labels else ""
        lines.append(f"#{issue['number']} ({state}){label_str}: {issue['title']}")

    return "\n".join(lines)


def get_daily_run_count(repo: str, workflow_name: str) -> int:
    """Get today's successful workflow run count.

    Args:
        repo: Repository in owner/repo format
        workflow_name: Name of the workflow file (e.g., "beneissue-workflow.yml")

    Returns:
        Number of successful runs today
    """
    gh = get_github_client()
    repository = gh.get_repo(repo)

    today = datetime.now(timezone.utc).date()
    count = 0

    try:
        workflow = repository.get_workflow(workflow_name)
        runs = workflow.get_runs(status="success")

        for run in runs:
            if run.created_at.date() == today:
                count += 1
            elif run.created_at.date() < today:
                break  # Runs are sorted by date, stop when we hit yesterday
    except Exception:
        # Workflow might not exist yet
        pass

    return count


def add_labels(repo: str, issue_number: int, labels: list[str]) -> None:
    """Add labels to an issue."""
    if not labels:
        return

    gh = get_github_client()
    repository = gh.get_repo(repo)
    issue = repository.get_issue(issue_number)
    issue.add_to_labels(*labels)


def remove_labels(repo: str, issue_number: int, labels: list[str]) -> None:
    """Remove labels from an issue."""
    if not labels:
        return

    gh = get_github_client()
    repository = gh.get_repo(repo)
    issue = repository.get_issue(issue_number)

    for label in labels:
        try:
            issue.remove_from_labels(label)
        except Exception:
            pass  # Label might not exist


def post_comment(repo: str, issue_number: int, body: str) -> None:
    """Post a comment on an issue."""
    gh = get_github_client()
    repository = gh.get_repo(repo)
    issue = repository.get_issue(issue_number)
    issue.create_comment(body)


def close_issue(repo: str, issue_number: int, reason: str = "not_planned") -> None:
    """Close an issue with a reason."""
    gh = get_github_client()
    repository = gh.get_repo(repo)
    issue = repository.get_issue(issue_number)
    issue.edit(state="closed", state_reason=reason)


class PullRequestResult:
    """Result of creating a pull request."""

    def __init__(
        self,
        success: bool,
        url: str | None = None,
        error: str | None = None,
    ):
        self.success = success
        self.url = url
        self.error = error


def create_pull_request(
    repo: str,
    branch_name: str,
    title: str,
    body: str,
    base: str = "main",
) -> PullRequestResult:
    """Create a pull request using PyGithub.

    Args:
        repo: Repository in owner/repo format
        branch_name: Head branch name
        title: PR title
        body: PR body/description
        base: Base branch (default: main)

    Returns:
        PullRequestResult with success status and URL or error
    """
    try:
        gh = get_github_client()
        repository = gh.get_repo(repo)
        pr = repository.create_pull(
            title=title,
            body=body,
            head=branch_name,
            base=base,
        )
        return PullRequestResult(success=True, url=pr.html_url)
    except Exception as e:
        error_msg = str(e)[:200] if str(e) else "Unknown error"
        return PullRequestResult(success=False, error=error_msg)
