"""CLI entry point using Typer."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import typer

from beneissue.config import setup_langsmith
from beneissue.graph.workflow import full_graph, triage_graph
from beneissue.labels import LABELS

app = typer.Typer(
    name="beneissue",
    help="AI-powered GitHub issue automation",
)


@app.command()
def triage(
    repo: str = typer.Argument(..., help="Repository in owner/repo format"),
    issue: int = typer.Option(..., "--issue", "-i", help="Issue number to triage"),
) -> None:
    """Triage a GitHub issue (classification only, no GitHub actions)."""
    setup_langsmith()

    typer.echo(f"Triaging issue #{issue} in {repo}...")

    result = triage_graph.invoke(
        {
            "repo": repo,
            "issue_number": issue,
        }
    )

    typer.echo(f"\nDecision: {result['triage_decision']}")
    typer.echo(f"Reason: {result['triage_reason']}")
    if result.get("duplicate_of"):
        typer.echo(f"Duplicate of: #{result['duplicate_of']}")
    typer.echo(f"Labels to add: {result.get('labels_to_add', [])}")


@app.command()
def analyze(
    repo: str = typer.Argument(..., help="Repository in owner/repo format"),
    issue: int = typer.Option(..., "--issue", "-i", help="Issue number to analyze"),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="Don't apply labels or post comments"
    ),
) -> None:
    """Analyze a GitHub issue (triage + analysis + actions)."""
    setup_langsmith()

    typer.echo(f"Analyzing issue #{issue} in {repo}...")

    if dry_run:
        # Use triage-only graph for dry run, then analyze separately
        from beneissue.nodes.analyze import analyze_node
        from beneissue.nodes.intake import intake_node
        from beneissue.nodes.triage import triage_node

        state = {"repo": repo, "issue_number": issue}
        state.update(intake_node(state))
        state.update(triage_node(state))

        typer.echo("\n--- Triage ---")
        typer.echo(f"Decision: {state['triage_decision']}")
        typer.echo(f"Reason: {state['triage_reason']}")

        if state["triage_decision"] == "valid":
            state.update(analyze_node(state))
            typer.echo("\n--- Analysis ---")
            typer.echo(f"Summary: {state['analysis_summary']}")
            typer.echo(f"Affected files: {state['affected_files']}")
            typer.echo(f"Approach: {state['fix_approach']}")
            typer.echo(f"Score: {state['score']}")
            typer.echo(f"Fix decision: {state['fix_decision']}")

        typer.echo(f"\nLabels to add: {state.get('labels_to_add', [])}")
        typer.echo("\n[DRY RUN] No actions taken on GitHub.")
    else:
        result = full_graph.invoke(
            {
                "repo": repo,
                "issue_number": issue,
            }
        )

        typer.echo("\n--- Triage ---")
        typer.echo(f"Decision: {result['triage_decision']}")
        typer.echo(f"Reason: {result['triage_reason']}")

        if result.get("analysis_summary"):
            typer.echo("\n--- Analysis ---")
            typer.echo(f"Summary: {result['analysis_summary']}")
            typer.echo(f"Fix decision: {result['fix_decision']}")

        if result.get("fix_success") is not None:
            typer.echo("\n--- Fix ---")
            if result["fix_success"]:
                typer.echo("Fix successful!")
                if result.get("pr_url"):
                    typer.echo(f"PR: {result['pr_url']}")
            else:
                typer.echo(f"Fix failed: {result.get('fix_error', 'Unknown error')}")

        typer.echo(f"\nLabels applied: {result.get('labels_to_add', [])}")
        typer.echo("Actions completed on GitHub.")


@app.command()
def fix(
    repo: str = typer.Argument(..., help="Repository in owner/repo format"),
    issue: int = typer.Option(..., "--issue", "-i", help="Issue number to fix"),
) -> None:
    """Attempt to automatically fix a GitHub issue."""
    setup_langsmith()

    typer.echo(f"Attempting to fix issue #{issue} in {repo}...")
    typer.echo("This will: triage → analyze → fix (if eligible) → apply labels")

    result = full_graph.invoke(
        {
            "repo": repo,
            "issue_number": issue,
        }
    )

    typer.echo("\n--- Triage ---")
    typer.echo(f"Decision: {result['triage_decision']}")

    if result["triage_decision"] != "valid":
        typer.echo(f"Reason: {result['triage_reason']}")
        typer.echo("\nIssue not eligible for fix.")
        return

    typer.echo("\n--- Analysis ---")
    typer.echo(f"Summary: {result['analysis_summary']}")
    typer.echo(f"Fix decision: {result['fix_decision']}")

    if result.get("fix_success") is not None:
        typer.echo("\n--- Fix ---")
        if result["fix_success"]:
            typer.echo("Fix successful!")
            if result.get("pr_url"):
                typer.echo(f"PR created: {result['pr_url']}")
        else:
            typer.echo(f"Fix failed: {result.get('fix_error', 'Unknown error')}")
    elif result["fix_decision"] != "auto_eligible":
        typer.echo("\nIssue not eligible for auto-fix.")
        typer.echo(f"Score: {result.get('score', {}).get('total', 'N/A')}/100")

    typer.echo(f"\nLabels: {result.get('labels_to_add', [])}")




@app.command()
def init(
    skip_labels: bool = typer.Option(
        False, "--skip-labels", help="Skip creating GitHub labels"
    ),
    skip_workflow: bool = typer.Option(
        False, "--skip-workflow", help="Skip creating workflow file"
    ),
    skip_skill: bool = typer.Option(
        False, "--skip-skill", help="Skip creating Claude skill files"
    ),
) -> None:
    """Initialize beneissue in the current repository.

    Creates:
    - .github/workflows/beneissue-workflow.yml (GitHub Action workflow)
    - .claude/skills/beneissue/ (Claude skill directory)
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

    typer.echo("Initializing beneissue...\n")

    # Create workflow file
    if not skip_workflow:
        workflow_dir = Path(".github/workflows")
        workflow_dir.mkdir(parents=True, exist_ok=True)
        workflow_file = workflow_dir / "beneissue-workflow.yml"
        _write_template_file(workflow_file, ".github/workflows/beneissue-workflow.yml", "workflow")

    # Create Claude skill directory
    if not skip_skill:
        skill_dir = Path(".claude/skills/beneissue")
        skill_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (skill_dir / "prompts").mkdir(exist_ok=True)
        cases_dir = skill_dir / "tests" / "cases"
        cases_dir.mkdir(parents=True, exist_ok=True)

        # Write skill files
        _write_template_file(skill_dir / "SKILL.md", ".claude/skills/SKILL.md", "skill definition")
        _write_template_file(
            skill_dir / "beneissue-config.yml", ".claude/skills/beneissue-config.yml", "skill config"
        )

        # Write example test cases
        test_case_templates = Path(__file__).parent / "templates" / ".claude" / "skills" / "tests" / "cases"
        if test_case_templates.exists():
            for case_file in test_case_templates.glob("*.json"):
                dest_file = cases_dir / case_file.name
                if not dest_file.exists():
                    dest_file.write_text(case_file.read_text())
                    typer.echo(f"Created: {dest_file}")

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

    typer.echo("\n" + "=" * 50)
    typer.echo("Setup complete!")
    typer.echo("=" * 50)
    typer.echo("\nNext steps:")
    typer.echo("1. Add secrets to your repository:")
    typer.echo("   - ANTHROPIC_API_KEY (required)")
    typer.echo("   - LANGCHAIN_API_KEY (optional, for LangSmith tracing)")
    typer.echo("\n2. Commit and push the files:")
    typer.echo("   git add .github/workflows/beneissue-workflow.yml .claude/")
    typer.echo("   git commit -m 'Add beneissue automation'")
    typer.echo("   git push")
    typer.echo("\n3. Create an issue to test!")


def _write_template_file(
    dest_file: Path, template_name: str, file_type: str
) -> None:
    """Write a template file to the destination, with overwrite confirmation."""
    if dest_file.exists():
        overwrite = typer.confirm(
            f"{dest_file} already exists. Overwrite?", default=False
        )
        if not overwrite:
            typer.echo(f"Skipping {file_type} file.")
            return

    # Read template from package (templates/ is inside src/beneissue/)
    template_path = Path(__file__).parent / "templates" / template_name

    if template_path.exists():
        content = template_path.read_text()
    else:
        typer.echo(f"Warning: Template {template_name} not found, skipping.")
        return

    dest_file.write_text(content)
    typer.echo(f"Created: {dest_file}")


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
        import json

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


# Default test cases directory
TEST_CASES_DIR = ".claude/skills/beneissue/tests/cases"


@app.command()
def test(
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
    """
    setup_langsmith()

    cases_dir = Path(TEST_CASES_DIR)
    if not cases_dir.exists():
        typer.echo(f"Error: Test cases directory not found: {cases_dir}")
        typer.echo("\nCreate test cases in JSON format:")
        typer.echo(f"  mkdir -p {TEST_CASES_DIR}")
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

    typer.echo(f"Found {len(case_files)} test case(s)\n")

    passed = 0
    failed = 0

    for case_file in case_files:
        try:
            test_case = json.loads(case_file.read_text())
        except json.JSONDecodeError as e:
            typer.echo(f"SKIP {case_file.name}: Invalid JSON - {e}")
            failed += 1
            continue

        # Filter by stage if specified
        if stage and test_case.get("stage") != stage:
            continue

        test_name = test_case.get("name", case_file.stem)

        if dry_run:
            typer.echo(f"VALID {case_file.name}: {test_name}")
            passed += 1
            continue

        typer.echo(f"RUN  {case_file.name}: {test_name}")

        # Run the test
        result = _run_test_case(test_case)

        if result["passed"]:
            typer.echo(f"PASS {case_file.name}")
            passed += 1
        else:
            typer.echo(f"FAIL {case_file.name}: {result['reason']}")
            failed += 1

    typer.echo(f"\n{'=' * 50}")
    typer.echo(f"Results: {passed} passed, {failed} failed")

    if failed > 0:
        raise typer.Exit(1)


def _run_test_case(test_case: dict) -> dict:
    """Run a single test case and return result."""
    from beneissue.nodes.analyze import analyze_node
    from beneissue.nodes.triage import triage_node

    stage = test_case.get("stage", "triage")
    input_data = test_case.get("input", {})
    expected = test_case.get("expected", {})

    # Build mock state
    state = {
        "repo": "test/repo",
        "issue_number": 1,
        "issue_title": input_data.get("title", ""),
        "issue_body": input_data.get("body", ""),
        "issue_labels": [],
        "issue_author": "test-user",
    }

    try:
        # Run triage
        triage_result = triage_node(state)
        state.update(triage_result)

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

        # Run analyze if needed
        if stage == "analyze" and state.get("triage_decision") == "valid":
            analyze_result = analyze_node(state)
            state.update(analyze_result)

            if "fix_decision" in expected:
                if state.get("fix_decision") != expected["fix_decision"]:
                    return {
                        "passed": False,
                        "reason": f"Expected fix_decision '{expected['fix_decision']}', got '{state.get('fix_decision')}'",
                    }

            if "min_score" in expected:
                score = state.get("score", {}).get("total", 0)
                if score < expected["min_score"]:
                    return {
                        "passed": False,
                        "reason": f"Score {score} below minimum {expected['min_score']}",
                    }

            if "max_score" in expected:
                score = state.get("score", {}).get("total", 0)
                if score > expected["max_score"]:
                    return {
                        "passed": False,
                        "reason": f"Score {score} above maximum {expected['max_score']}",
                    }

        return {"passed": True, "reason": ""}

    except Exception as e:
        return {"passed": False, "reason": str(e)}


if __name__ == "__main__":
    app()
