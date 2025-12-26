"""Git CLI integration."""

import subprocess
from dataclasses import dataclass


@dataclass
class GitResult:
    """Result of a git command."""

    returncode: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.returncode == 0


def run_git(repo_path: str, *args: str, timeout: int = 60) -> GitResult:
    """Run a git command in the repo directory.

    Args:
        repo_path: Path to the repository
        *args: Git command arguments
        timeout: Command timeout in seconds

    Returns:
        GitResult with returncode, stdout, stderr
    """
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        cwd=repo_path,
        timeout=timeout,
    )
    return GitResult(
        returncode=result.returncode,
        stdout=result.stdout.decode() if result.stdout else "",
        stderr=result.stderr.decode() if result.stderr else "",
    )


def git_status(repo_path: str) -> str:
    """Get git status --porcelain output."""
    result = run_git(repo_path, "status", "--porcelain")
    return result.stdout.strip()


def git_checkout_branch(repo_path: str, branch_name: str) -> GitResult:
    """Create and checkout a new branch."""
    return run_git(repo_path, "checkout", "-b", branch_name)


def git_add_all(repo_path: str) -> GitResult:
    """Stage all changes."""
    return run_git(repo_path, "add", "-A")


def git_commit(repo_path: str, message: str, *, allow_empty: bool = False) -> GitResult:
    """Commit staged changes."""
    if allow_empty:
        return run_git(repo_path, "commit", "--allow-empty", "-m", message)
    return run_git(repo_path, "commit", "-m", message)


def git_push(repo_path: str, branch_name: str) -> GitResult:
    """Push branch to origin."""
    return run_git(repo_path, "push", "-u", "origin", branch_name)


def git_config(repo_path: str, key: str, value: str) -> GitResult:
    """Set a git config value."""
    return run_git(repo_path, "config", key, value)


def configure_git_user(
    repo_path: str,
    name: str = "github-actions[bot]",
    email: str = "github-actions[bot]@users.noreply.github.com",
) -> None:
    """Configure git user for commits."""
    git_config(repo_path, "user.name", name)
    git_config(repo_path, "user.email", email)
