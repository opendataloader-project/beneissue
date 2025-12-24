"""CLI entry point using Typer."""

import os
import shutil
import subprocess
from importlib import resources
from pathlib import Path

import typer

from beneissue.config import setup_langsmith
from beneissue.graph.workflow import full_graph, triage_graph

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


# Labels that beneissue uses
BENEISSUE_LABELS = [
    ("triage/valid", "0E8A16", "Valid issue"),
    ("triage/invalid", "D93F0B", "Invalid issue"),
    ("triage/duplicate", "FBCA04", "Duplicate issue"),
    ("triage/needs-info", "5319E7", "Needs more information"),
    ("fix/auto-eligible", "1D76DB", "Eligible for auto-fix"),
    ("fix/manual-required", "E99695", "Manual fix required"),
    ("fix/completed", "0E8A16", "Fix completed"),
    ("fix/failed", "D93F0B", "Fix failed"),
]


@app.command()
def init(
    skip_labels: bool = typer.Option(
        False, "--skip-labels", help="Skip creating GitHub labels"
    ),
    skip_workflow: bool = typer.Option(
        False, "--skip-workflow", help="Skip creating workflow file"
    ),
) -> None:
    """Initialize beneissue in the current repository.

    Creates:
    - .github/workflows/beneissue.yml (GitHub Action workflow)
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
        workflow_file = workflow_dir / "beneissue.yml"

        if workflow_file.exists():
            overwrite = typer.confirm(
                f"{workflow_file} already exists. Overwrite?", default=False
            )
            if not overwrite:
                typer.echo("Skipping workflow file.")
            else:
                _write_workflow_file(workflow_file)
        else:
            _write_workflow_file(workflow_file)

    # Create labels
    if not skip_labels:
        typer.echo("\nCreating GitHub labels...")
        for label_name, color, description in BENEISSUE_LABELS:
            result = subprocess.run(
                [
                    "gh",
                    "label",
                    "create",
                    label_name,
                    "--color",
                    color,
                    "--description",
                    description,
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
    typer.echo("\n2. Commit and push the workflow file:")
    typer.echo("   git add .github/workflows/beneissue.yml")
    typer.echo("   git commit -m 'Add beneissue workflow'")
    typer.echo("   git push")
    typer.echo("\n3. Create an issue to test!")


def _write_workflow_file(workflow_file: Path) -> None:
    """Write the beneissue workflow template to the specified file."""
    # Read template from package
    template_path = Path(__file__).parent.parent.parent.parent / "templates" / "beneissue.yml"

    if template_path.exists():
        content = template_path.read_text()
    else:
        # Fallback: embedded template
        content = '''# beneissue - AI-powered GitHub issue automation
# Generated by: beneissue init

name: beneissue

on:
  issues:
    types: [opened, reopened]
  issue_comment:
    types: [created]

jobs:
  analyze:
    if: github.event_name == 'issues'
    runs-on: ubuntu-latest
    steps:
      - uses: opendataloader-project/beneissue@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
          langchain-api-key: ${{ secrets.LANGCHAIN_API_KEY }}
          command: analyze

  on-command:
    if: |
      github.event_name == 'issue_comment' &&
      contains(github.event.comment.body, '@beneissue')
    runs-on: ubuntu-latest
    steps:
      - name: Parse command
        id: parse
        run: |
          COMMENT="${{ github.event.comment.body }}"
          if [[ "$COMMENT" == *"@beneissue triage"* ]]; then
            echo "command=triage" >> $GITHUB_OUTPUT
          elif [[ "$COMMENT" == *"@beneissue fix"* ]]; then
            echo "command=fix" >> $GITHUB_OUTPUT
          elif [[ "$COMMENT" == *"@beneissue analyze"* ]]; then
            echo "command=analyze" >> $GITHUB_OUTPUT
          else
            echo "command=analyze" >> $GITHUB_OUTPUT
          fi

      - uses: opendataloader-project/beneissue@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
          langchain-api-key: ${{ secrets.LANGCHAIN_API_KEY }}
          command: ${{ steps.parse.outputs.command }}
'''

    workflow_file.write_text(content)
    typer.echo(f"Created: {workflow_file}")


if __name__ == "__main__":
    app()
