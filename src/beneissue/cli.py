"""CLI entry point using Typer."""

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

        typer.echo(f"\nLabels applied: {result.get('labels_to_add', [])}")
        typer.echo("Actions completed on GitHub.")


if __name__ == "__main__":
    app()
