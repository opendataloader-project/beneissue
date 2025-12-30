"""CLI entry point using Typer."""

import json
import shutil
import subprocess
import time
from importlib.metadata import version as get_version
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv

# Load .env file for local development (Supabase credentials, etc.)
load_dotenv()


def _get_beneissue_version() -> str:
    """Get beneissue version from package metadata."""
    try:
        return get_version("beneissue")
    except Exception:
        return "unknown"

from beneissue.config import setup_langsmith, setup_logging
from beneissue.graph.workflow import analyze_graph, fix_graph, full_graph, triage_graph
from beneissue.labels import LABELS

app = typer.Typer(
    name="beneissue",
    help="AI-powered GitHub issue automation",
)


@app.command()
def triage(
    repo: str = typer.Argument(..., help="Repository in owner/repo format"),
    issue: int = typer.Option(..., "--issue", "-i", help="Issue number to triage"),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="Use mock LLM data (skip API calls)"
    ),
    no_action: bool = typer.Option(
        False, "--no-action", help="Skip GitHub actions (use with --dry-run)"
    ),
) -> None:
    """Triage a GitHub issue (classify only, no analysis or fix)."""
    setup_logging()
    setup_langsmith()

    if dry_run:
        typer.echo(f"[DRY-RUN] Triaging issue #{issue} in {repo}...")
    else:
        typer.echo(f"Triaging issue #{issue} in {repo}...")

    result = triage_graph.invoke(
        {
            "repo": repo,
            "issue_number": issue,
            "command": "triage",
            "dry_run": dry_run,
            "no_action": no_action,
        }
    )

    if result.get("daily_limit_exceeded"):
        typer.echo(f"\nDaily limit exceeded ({result.get('daily_run_count', 0)} runs today).")
        typer.echo("Skipping triage. Try again tomorrow.")
        return

    typer.echo(f"\nDecision: {result['triage_decision']}")
    typer.echo(f"Reason: {result['triage_reason']}")
    if result.get("duplicate_of"):
        typer.echo(f"Duplicate of: #{result['duplicate_of']}")

    if no_action:
        typer.echo(f"\nLabels to add: {result.get('labels_to_add', [])}")
        typer.echo("\n[DRY-RUN] No actions taken on GitHub.")
    else:
        typer.echo(f"\nLabels applied: {result.get('labels_to_add', [])}")


@app.command()
def analyze(
    repo: str = typer.Argument(..., help="Repository in owner/repo format"),
    issue: int = typer.Option(..., "--issue", "-i", help="Issue number to analyze"),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="Use mock LLM data (skip API calls)"
    ),
    no_action: bool = typer.Option(
        False, "--no-action", help="Skip GitHub actions (use with --dry-run)"
    ),
) -> None:
    """Analyze a GitHub issue (no triage, no fix)."""
    setup_logging()
    setup_langsmith()

    if dry_run:
        typer.echo(f"[DRY-RUN] Analyzing issue #{issue} in {repo}...")
    else:
        typer.echo(f"Analyzing issue #{issue} in {repo}...")

    result = analyze_graph.invoke(
        {
            "repo": repo,
            "issue_number": issue,
            "command": "analyze",
            "dry_run": dry_run,
            "no_action": no_action,
        }
    )

    if result.get("daily_limit_exceeded"):
        typer.echo(f"\nDaily limit exceeded ({result.get('daily_run_count', 0)} runs today).")
        typer.echo("Skipping analysis. Try again tomorrow.")
        return

    typer.echo(f"\nSummary: {result['analysis_summary']}")
    typer.echo(f"Affected files: {result.get('affected_files', [])}")
    typer.echo(f"Fix decision: {result['fix_decision']}")
    typer.echo(f"Reason: {result.get('fix_reason', '')}")
    typer.echo(f"Assignee: {result.get('assignee', 'None')}")

    if no_action:
        typer.echo(f"\nLabels to add: {result.get('labels_to_add', [])}")
        typer.echo("\n[DRY-RUN] No actions taken on GitHub.")
    else:
        typer.echo(f"\nLabels applied: {result.get('labels_to_add', [])}")


@app.command()
def fix(
    repo: str = typer.Argument(..., help="Repository in owner/repo format"),
    issue: int = typer.Option(..., "--issue", "-i", help="Issue number to fix"),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="Use mock LLM data (skip API calls, no PR created)"
    ),
    no_action: bool = typer.Option(
        False, "--no-action", help="Skip GitHub actions (use with --dry-run)"
    ),
) -> None:
    """Attempt to fix a GitHub issue (no triage, no analysis)."""
    setup_logging()
    setup_langsmith()

    if dry_run:
        typer.echo(f"[DRY-RUN] Attempting to fix issue #{issue} in {repo}...")
    else:
        typer.echo(f"Attempting to fix issue #{issue} in {repo}...")

    result = fix_graph.invoke(
        {
            "repo": repo,
            "issue_number": issue,
            "command": "fix",
            "dry_run": dry_run,
            "no_action": no_action,
        }
    )

    if result.get("daily_limit_exceeded"):
        typer.echo(f"\nDaily limit exceeded ({result.get('daily_run_count', 0)} runs today).")
        typer.echo("Skipping fix. Try again tomorrow.")
        return

    if result.get("fix_success") is not None:
        if result["fix_success"]:
            typer.echo("\nFix successful!")
            if result.get("pr_url"):
                typer.echo(f"PR created: {result['pr_url']}")
            elif dry_run:
                typer.echo("[DRY-RUN] No PR created in dry-run mode")
        else:
            typer.echo(f"\nFix failed: {result.get('fix_error', 'Unknown error')}")

    if no_action:
        typer.echo(f"\nLabels to add: {result.get('labels_to_add', [])}")
        typer.echo("\n[DRY-RUN] No actions taken on GitHub.")
    else:
        typer.echo(f"\nLabels applied: {result.get('labels_to_add', [])}")


@app.command()
def run(
    repo: str = typer.Argument(..., help="Repository in owner/repo format"),
    issue: int = typer.Option(..., "--issue", "-i", help="Issue number to process"),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="Use mock LLM data (skip API calls)"
    ),
    no_action: bool = typer.Option(
        False, "--no-action", help="Skip GitHub actions (use with --dry-run)"
    ),
) -> None:
    """Run full workflow: triage → analyze → fix → apply labels."""
    setup_logging()
    setup_langsmith()

    if dry_run:
        typer.echo(f"[DRY-RUN] Running full workflow for issue #{issue} in {repo}...")
    else:
        typer.echo(f"Running full workflow for issue #{issue} in {repo}...")

    result = full_graph.invoke(
        {
            "repo": repo,
            "issue_number": issue,
            "command": "run",
            "dry_run": dry_run,
            "no_action": no_action,
        }
    )

    if result.get("daily_limit_exceeded"):
        typer.echo(f"\nDaily limit exceeded ({result.get('daily_run_count', 0)} runs today).")
        typer.echo("Skipping workflow. Try again tomorrow.")
        return

    typer.echo("\n--- Triage ---")
    typer.echo(f"Decision: {result['triage_decision']}")
    typer.echo(f"Reason: {result['triage_reason']}")

    if result["triage_decision"] != "valid":
        typer.echo("\nIssue not valid, stopping.")
        if no_action:
            typer.echo(f"Labels to add: {result.get('labels_to_add', [])}")
        else:
            typer.echo(f"Labels applied: {result.get('labels_to_add', [])}")
        return

    if result.get("analysis_summary"):
        typer.echo("\n--- Analysis ---")
        typer.echo(f"Summary: {result['analysis_summary']}")
        typer.echo(f"Fix decision: {result['fix_decision']}")

    if result.get("fix_success") is not None:
        typer.echo("\n--- Fix ---")
        if result["fix_success"]:
            typer.echo("Fix successful!")
            if result.get("pr_url"):
                typer.echo(f"PR created: {result['pr_url']}")
            elif dry_run:
                typer.echo("[DRY-RUN] No PR created in dry-run mode")
        else:
            typer.echo(f"Fix failed: {result.get('fix_error', 'Unknown error')}")

    if no_action:
        typer.echo(f"\nLabels to add: {result.get('labels_to_add', [])}")
        typer.echo("\n[DRY-RUN] No actions taken on GitHub.")
    else:
        typer.echo(f"\nLabels applied: {result.get('labels_to_add', [])}")




@app.command()
def check(
    repo: str = typer.Argument(..., help="Repository in owner/repo format"),
) -> None:
    """Check beneissue setup and permissions (dry-run test).

    Verifies:
    - GitHub token has required permissions (issues, contents, pull-requests)
    - Anthropic API key is set
    - gh CLI is available and authenticated
    - Repository is accessible
    """
    import os
    import sys

    typer.echo(f"Checking beneissue setup for {repo}...\n")

    all_passed = True

    def check_item(name: str, passed: bool, detail: str = "") -> None:
        nonlocal all_passed
        status = "✅" if passed else "❌"
        msg = f"{status} {name}"
        if detail:
            msg += f": {detail}"
        typer.echo(msg)
        if not passed:
            all_passed = False

    # Check environment variables
    typer.echo("--- Environment ---")
    check_item(
        "ANTHROPIC_API_KEY",
        bool(os.environ.get("ANTHROPIC_API_KEY")),
        "set" if os.environ.get("ANTHROPIC_API_KEY") else "not set"
    )
    check_item(
        "GITHUB_TOKEN",
        bool(os.environ.get("GITHUB_TOKEN")),
        "set" if os.environ.get("GITHUB_TOKEN") else "not set"
    )

    # Check gh CLI
    typer.echo("\n--- GitHub CLI ---")
    gh_available = shutil.which("gh") is not None
    check_item("gh CLI installed", gh_available)

    if gh_available:
        # Check gh auth status
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
        )
        check_item("gh CLI authenticated", result.returncode == 0)

        # Check repository access
        typer.echo(f"\n--- Repository: {repo} ---")
        result = subprocess.run(
            ["gh", "repo", "view", repo, "--json", "name"],
            capture_output=True,
            text=True,
            env={**os.environ, "GH_TOKEN": os.environ.get("GITHUB_TOKEN", "")},
        )
        check_item("Repository accessible", result.returncode == 0)

        # Check permissions by trying to list issues
        result = subprocess.run(
            ["gh", "issue", "list", "-R", repo, "--limit", "1"],
            capture_output=True,
            text=True,
            env={**os.environ, "GH_TOKEN": os.environ.get("GITHUB_TOKEN", "")},
        )
        check_item("Issues permission", result.returncode == 0)

        # Check PR creation permission (dry check - list PRs)
        result = subprocess.run(
            ["gh", "pr", "list", "-R", repo, "--limit", "1"],
            capture_output=True,
            text=True,
            env={**os.environ, "GH_TOKEN": os.environ.get("GITHUB_TOKEN", "")},
        )
        check_item("Pull requests permission", result.returncode == 0)

        # Check contents permission (can we see branches?)
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/branches", "--jq", ".[0].name"],
            capture_output=True,
            text=True,
            env={**os.environ, "GH_TOKEN": os.environ.get("GITHUB_TOKEN", "")},
        )
        check_item("Contents permission", result.returncode == 0)

    # Check Node.js / npx
    typer.echo("\n--- Node.js ---")
    npx_available = shutil.which("npx") is not None
    check_item("npx available", npx_available)

    # Summary
    typer.echo("\n" + "=" * 40)
    if all_passed:
        typer.echo("✅ All checks passed! beneissue is ready.")
    else:
        typer.echo("❌ Some checks failed. Please fix the issues above.")
        sys.exit(1)


@app.command()
def init(
    skip_labels: bool = typer.Option(
        False, "--skip-labels", help="Skip creating GitHub labels"
    ),
) -> None:
    """Initialize beneissue in the current repository.

    Copies template files from the package to the current repository:
    - .github/workflows/beneissue-workflow.yml (GitHub Action workflow)
    - .github/workflows/beneissue-test.yml (Test workflow for metrics/policy)
    - .claude/skills/beneissue/ (Claude skill directory with config and test cases)
    - GitHub labels for triage and fix status
    """
    # Check if we're in a git repo
    if not Path(".git").exists():
        typer.echo("Error: Not a git repository. Run this command from the repo root.")
        raise typer.Exit(1)

    # Check if gh CLI is available
    if not shutil.which("gh"):
        typer.echo("Warning: GitHub CLI (gh) not found. Labels will not be created.")
        typer.echo("Install: https://cli.github.com/")
        skip_labels = True

    version = _get_beneissue_version()
    typer.echo(f"Initializing beneissue v{version}...\n")

    # Get template directory from package
    template_dir = Path(__file__).parent / "template"
    if not template_dir.exists():
        typer.echo(f"Error: Template directory not found: {template_dir}")
        raise typer.Exit(1)

    # Copy only config directories (.claude/ and .github/) to current directory
    created_files: list[Path] = []
    for config_dir in [".claude", ".github"]:
        src_dir = template_dir / config_dir
        if src_dir.exists():
            created_files.extend(_copy_template_tree(src_dir, Path(".") / config_dir))

    # Create labels
    if not skip_labels:
        typer.echo("\nCreating GitHub labels...")
        for label_name, label_def in LABELS.items():
            result = subprocess.run(
                [
                    "gh",
                    "label",
                    "create",
                    label_name,
                    "--color",
                    label_def.color,
                    "--description",
                    label_def.description,
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                typer.echo(f"  Created: {label_name}")
            elif "already exists" in result.stderr:
                typer.echo(f"  Exists:  {label_name}")
            else:
                typer.echo(f"  Failed:  {label_name} - {result.stderr.strip()}")

    # Git add and commit created files
    if created_files:
        typer.echo("\nCommitting files to git...")
        file_paths = [str(f) for f in created_files]
        result = subprocess.run(
            ["git", "add"] + file_paths,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            commit_message = (
                f"chore: initialize beneissue v{version}\n\n"
                "Set up beneissue for automated issue triage, analysis, and fixes.\n"
                "- GitHub Actions workflow for issue event handling\n"
                "- Configuration and test cases in .claude/skills/beneissue/"
            )
            result = subprocess.run(
                [
                    "git",
                    "commit",
                    "-m",
                    commit_message,
                    "--author",
                    "beneissue[bot] <beneissue[bot]@users.noreply.github.com>",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                typer.echo("Committed: Add AI-powered GitHub issue automation workflow")
            elif "nothing to commit" in result.stdout + result.stderr:
                typer.echo("No changes to commit.")
            else:
                typer.echo(f"Commit failed: {result.stderr.strip()}")
        else:
            typer.echo(f"Git add failed: {result.stderr.strip()}")

    typer.echo("\n" + "=" * 50)
    typer.echo(f"beneissue v{version} setup complete!")
    typer.echo("=" * 50)
    typer.echo("\nNext steps:")
    typer.echo("1. Add secrets to your repository:")
    typer.echo("   - ANTHROPIC_API_KEY (required)")
    typer.echo("   - LANGCHAIN_API_KEY (optional, for LangSmith tracing)")
    typer.echo("\n2. Push and create an issue to test:")
    typer.echo("   git push")


def _copy_template_tree(src_dir: Path, dest_dir: Path) -> list[Path]:
    """Recursively copy template directory to destination, with overwrite confirmation.

    Returns list of created/updated file paths.
    """
    created_files = []
    for src_path in src_dir.rglob("*"):
        if src_path.is_dir():
            continue

        # Calculate relative path and destination
        rel_path = src_path.relative_to(src_dir)
        dest_path = dest_dir / rel_path

        # Check if file exists and ask for confirmation
        if dest_path.exists():
            overwrite = typer.confirm(
                f"{dest_path} already exists. Overwrite?", default=False
            )
            if not overwrite:
                typer.echo(f"Skipped: {dest_path}")
                continue

        # Create parent directories if needed
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy file
        dest_path.write_bytes(src_path.read_bytes())
        typer.echo(f"Created: {dest_path}")
        created_files.append(dest_path)

    return created_files


@app.command("labels")
def labels_sync(
    delete_unused: bool = typer.Option(
        False, "--delete-unused", help="Delete beneissue labels not in standard set"
    ),
) -> None:
    """Sync beneissue labels to the repository.

    Creates missing labels and updates existing ones with correct colors.
    Use --delete-unused to remove old beneissue labels.
    """
    # Check if gh CLI is available
    if not shutil.which("gh"):
        typer.echo("Error: GitHub CLI (gh) not found.")
        typer.echo("Install: https://cli.github.com/")
        raise typer.Exit(1)

    # Check if we're in a git repo
    if not Path(".git").exists():
        typer.echo("Error: Not a git repository.")
        raise typer.Exit(1)

    typer.echo("Syncing beneissue labels...\n")

    # Get existing labels
    result = subprocess.run(
        ["gh", "label", "list", "--json", "name,color,description"],
        capture_output=True,
        text=True,
    )

    existing_labels = {}
    if result.returncode == 0:
        for label in json.loads(result.stdout):
            existing_labels[label["name"]] = label

    # Create or update labels
    for label_name, label_def in LABELS.items():
        if label_name in existing_labels:
            existing = existing_labels[label_name]
            # Check if update needed
            if existing["color"].lower() != label_def.color.lower():
                result = subprocess.run(
                    [
                        "gh",
                        "label",
                        "edit",
                        label_name,
                        "--color",
                        label_def.color,
                        "--description",
                        label_def.description,
                    ],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    typer.echo(f"  Updated: {label_name}")
                else:
                    typer.echo(f"  Failed to update: {label_name}")
            else:
                typer.echo(f"  OK:      {label_name}")
        else:
            result = subprocess.run(
                [
                    "gh",
                    "label",
                    "create",
                    label_name,
                    "--color",
                    label_def.color,
                    "--description",
                    label_def.description,
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                typer.echo(f"  Created: {label_name}")
            else:
                typer.echo(f"  Failed:  {label_name} - {result.stderr.strip()}")

    # Delete unused beneissue labels
    if delete_unused:
        typer.echo("\nChecking for unused beneissue labels...")
        for name in existing_labels:
            # Only consider labels that look like beneissue labels
            if name.startswith(("triage/", "fix/", "sp/", "P")) and name not in LABELS:
                result = subprocess.run(
                    ["gh", "label", "delete", name, "--yes"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    typer.echo(f"  Deleted: {name}")
                else:
                    typer.echo(f"  Failed to delete: {name}")

    typer.echo("\nLabels synced.")


# Default test cases directory (relative to project root)
TEST_CASES_SUBDIR = ".claude/skills/beneissue/tests/cases"


@app.command()
def test(
    path: Optional[str] = typer.Option(
        None, "--path", "-p", help="Project root path (default: current directory)"
    ),
    case: Optional[str] = typer.Option(
        None, "--case", "-c", help="Run specific test case by name"
    ),
    stage: Optional[str] = typer.Option(
        None, "--stage", "-s", help="Run only tests for specific stage (triage/analyze)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="Validate test cases without running AI"
    ),
) -> None:
    """Run policy tests from test cases in the repository.

    Test cases should be JSON files in .claude/skills/beneissue/tests/cases/

    Examples:
        beneissue test                           # Run tests in current directory
        beneissue test --path examples/calculator  # Run tests in example project
    """
    setup_logging()
    setup_langsmith()

    project_root = Path(path) if path else Path(".")
    cases_dir = project_root / TEST_CASES_SUBDIR
    if not cases_dir.exists():
        typer.echo(f"Error: Test cases directory not found: {cases_dir}")
        typer.echo("\nCreate test cases in JSON format:")
        typer.echo(f"  mkdir -p {TEST_CASES_SUBDIR}")
        typer.echo("  # Add JSON files like triage-valid-bug.json")
        raise typer.Exit(1)

    # Find test case files
    case_files = list(cases_dir.glob("*.json"))
    if not case_files:
        typer.echo(f"No test cases found in {cases_dir}")
        raise typer.Exit(1)

    # Filter by case name if specified
    if case:
        case_files = [f for f in case_files if case in f.stem]
        if not case_files:
            typer.echo(f"No test cases matching '{case}'")
            raise typer.Exit(1)

    typer.secho(f"Found {len(case_files)} test case(s)\n", fg=typer.colors.CYAN)

    passed = 0
    failed = 0
    skipped = 0
    total_time = 0.0

    for case_file in case_files:
        try:
            test_case = json.loads(case_file.read_text())
        except json.JSONDecodeError as e:
            typer.secho("  SKIP  ", fg=typer.colors.YELLOW, nl=False)
            typer.echo(f"{case_file.name}: Invalid JSON - {e}")
            skipped += 1
            continue

        # Filter by stage if specified
        if stage and test_case.get("stage") != stage:
            skipped += 1
            continue

        test_name = test_case.get("name", case_file.stem)

        if dry_run:
            typer.secho("  VALID ", fg=typer.colors.GREEN, nl=False)
            typer.secho(f"{case_file.name}", fg=typer.colors.WHITE, bold=True, nl=False)
            typer.echo(f": {test_name}")
            passed += 1
            continue

        typer.secho("  RUN   ", fg=typer.colors.BLUE, nl=False)
        typer.secho(f"{case_file.name}", fg=typer.colors.WHITE, bold=True, nl=False)
        typer.echo(f": {test_name}")

        # Run the test with timing
        start_time = time.perf_counter()
        result = _run_test_case(test_case, project_root)
        elapsed = time.perf_counter() - start_time
        total_time += elapsed

        # Format elapsed time
        time_str = f"({elapsed:.2f}s)" if elapsed >= 1 else f"({elapsed * 1000:.0f}ms)"

        if result["passed"]:
            typer.secho("  PASS  ", fg=typer.colors.GREEN, bold=True, nl=False)
            typer.echo(f"{case_file.name} ", nl=False)
            typer.secho(time_str, fg=typer.colors.BRIGHT_BLACK)
            passed += 1
        else:
            typer.secho("  FAIL  ", fg=typer.colors.RED, bold=True, nl=False)
            typer.secho(f"{case_file.name} ", nl=False)
            typer.secho(time_str, fg=typer.colors.BRIGHT_BLACK, nl=False)
            typer.secho(f": {result['reason']}", fg=typer.colors.RED)
            failed += 1

    # Summary
    typer.echo()
    typer.secho("=" * 50, fg=typer.colors.CYAN)

    # Build colored summary
    typer.echo("Results: ", nl=False)
    typer.secho(f"{passed} passed", fg=typer.colors.GREEN, bold=True, nl=False)
    typer.echo(", ", nl=False)
    if failed > 0:
        typer.secho(f"{failed} failed", fg=typer.colors.RED, bold=True, nl=False)
    else:
        typer.secho(f"{failed} failed", fg=typer.colors.WHITE, nl=False)
    if skipped > 0:
        typer.echo(", ", nl=False)
        typer.secho(f"{skipped} skipped", fg=typer.colors.YELLOW, nl=False)
    if total_time > 0:
        time_summary = f" in {total_time:.2f}s" if total_time >= 1 else f" in {total_time * 1000:.0f}ms"
        typer.secho(time_summary, fg=typer.colors.BRIGHT_BLACK)
    else:
        typer.echo()

    if failed > 0:
        raise typer.Exit(1)


def _run_test_case(test_case: dict, project_root: Path) -> dict:
    """Run a single test case and return result."""
    import logging

    from beneissue.metrics.collector import (
        record_analyze_metrics_node,
        record_triage_metrics_node,
    )
    from beneissue.nodes.analyze import analyze_node
    from beneissue.nodes.triage import triage_node

    logger = logging.getLogger("beneissue.test")

    stage = test_case.get("stage", "triage")
    input_data = test_case.get("input", {})
    expected = test_case.get("expected", {})

    # Build mock state
    state = {
        "repo": "test/repo",
        "issue_number": 1,
        "project_root": project_root.resolve(),
        "issue_title": input_data.get("title", ""),
        "issue_body": input_data.get("body", ""),
        "issue_labels": [],
        "issue_author": "test-user",
        "existing_issues": input_data.get("existing_issues", []),
    }

    try:
        # Run triage (skip for analyze-only tests)
        if stage == "triage":
            triage_result = triage_node(state)
            state.update(triage_result)

            logger.debug(
                "Triage result: decision=%s, reason=%s",
                state.get("triage_decision"),
                state.get("triage_reason", "")[:100],
            )

            # Check triage expectations
            if "decision" in expected:
                if state.get("triage_decision") != expected["decision"]:
                    return {
                        "passed": False,
                        "reason": f"Expected decision '{expected['decision']}', got '{state.get('triage_decision')}'",
                    }

            if "reason_contains" in expected:
                reason = state.get("triage_reason", "")
                for keyword in expected["reason_contains"]:
                    if keyword.lower() not in reason.lower():
                        return {
                            "passed": False,
                            "reason": f"Reason missing keyword '{keyword}'",
                        }

            if "duplicate_of" in expected:
                if state.get("duplicate_of") != expected["duplicate_of"]:
                    return {
                        "passed": False,
                        "reason": f"Expected duplicate_of {expected['duplicate_of']}, got {state.get('duplicate_of')}",
                    }

        # Run analyze if needed
        if stage == "analyze":
            analyze_result = analyze_node(state)
            state.update(analyze_result)

            logger.debug(
                "Analyze result: fix_decision=%s, assignee=%s, summary=%s, affected_files=%s",
                state.get("fix_decision"),
                state.get("assignee"),
                state.get("analysis_summary", "")[:150],
                state.get("affected_files", []),
            )

            # Check for CLI errors
            summary = state.get("analysis_summary", "")
            if "Claude Code CLI not installed" in summary:
                return {
                    "passed": False,
                    "reason": "Claude Code CLI not installed. Run: npm install -g @anthropic-ai/claude-code",
                }
            if summary.startswith("Analysis incomplete:"):
                return {
                    "passed": False,
                    "reason": summary,
                }

            if "fix_decision" in expected:
                if state.get("fix_decision") != expected["fix_decision"]:
                    return {
                        "passed": False,
                        "reason": f"Expected fix_decision '{expected['fix_decision']}', got '{state.get('fix_decision')}'",
                    }

            # Check assignee expectations
            if "assignee" in expected:
                actual_assignee = state.get("assignee")
                if actual_assignee != expected["assignee"]:
                    return {
                        "passed": False,
                        "reason": f"Expected assignee '{expected['assignee']}', got '{actual_assignee}'",
                    }

            if "assignee_one_of" in expected:
                actual_assignee = state.get("assignee")
                if actual_assignee not in expected["assignee_one_of"]:
                    return {
                        "passed": False,
                        "reason": f"Expected assignee one of {expected['assignee_one_of']}, got '{actual_assignee}'",
                    }

        # Record metrics to Supabase (no_action mode is fine, we still record)
        if stage == "triage":
            record_triage_metrics_node(state)
        elif stage == "analyze":
            record_analyze_metrics_node(state)

        return {"passed": True, "reason": ""}

    except Exception as e:
        return {"passed": False, "reason": str(e)}


if __name__ == "__main__":
    app()
