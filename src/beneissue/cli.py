"""CLI entry point using Typer."""

import typer

from beneissue.config import setup_langsmith
from beneissue.graph.workflow import triage_graph

app = typer.Typer(
    name="beneissue",
    help="AI-powered GitHub issue automation",
)


@app.command()
def triage(
    repo: str = typer.Argument(..., help="Repository in owner/repo format"),
    issue: int = typer.Option(..., "--issue", "-i", help="Issue number to triage"),
) -> None:
    """Triage a GitHub issue."""
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


if __name__ == "__main__":
    app()
