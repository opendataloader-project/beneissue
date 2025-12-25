"""External integrations for beneissue."""

from beneissue.integrations.claude_code import (
    ClaudeCodeResult,
    parse_json_from_output,
    run_claude_code,
)
from beneissue.integrations.git import (
    GitResult,
    configure_git_user,
    git_add_all,
    git_checkout_branch,
    git_commit,
    git_config,
    git_push,
    git_status,
    run_git,
)
from beneissue.integrations.github import (
    PullRequestResult,
    add_labels,
    clone_repo,
    close_issue,
    create_pull_request,
    format_existing_issues,
    get_daily_run_count,
    get_existing_issues,
    get_github_client,
    get_issue,
    post_comment,
    remove_labels,
)

__all__ = [
    # claude_code
    "ClaudeCodeResult",
    "parse_json_from_output",
    "run_claude_code",
    # git
    "GitResult",
    "configure_git_user",
    "git_add_all",
    "git_checkout_branch",
    "git_commit",
    "git_config",
    "git_push",
    "git_status",
    "run_git",
    # github
    "PullRequestResult",
    "add_labels",
    "clone_repo",
    "close_issue",
    "create_pull_request",
    "format_existing_issues",
    "get_daily_run_count",
    "get_existing_issues",
    "get_github_client",
    "get_issue",
    "post_comment",
    "remove_labels",
]
