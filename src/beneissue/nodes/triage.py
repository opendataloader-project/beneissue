"""Triage node implementation."""

from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from beneissue.config import DEFAULT_TRIAGE_MODEL
from beneissue.graph.state import IssueState
from beneissue.integrations.github import format_existing_issues
from beneissue.labels import get_triage_labels
from beneissue.nodes.schemas import TriageResult
from beneissue.observability import log_node_event, traced_node
from beneissue.prompts import load_prompt


def _build_triage_prompt(state: IssueState) -> str:
    """Build the triage prompt with context."""
    # Read README from project root (default: cwd)
    project_root = state.get("project_root", Path.cwd())
    readme_path = project_root / "README.md"
    if readme_path.exists():
        readme_content = readme_path.read_text()
    else:
        readme_content = f"Repository: {state['repo']}\n\nNo README.md found."

    # Format existing issues for duplicate detection
    existing = state.get("existing_issues", [])
    existing_issues = (
        format_existing_issues(existing) if existing else "No existing issues loaded."
    )

    return load_prompt("triage").format(
        readme_content=readme_content,
        existing_issues=existing_issues,
    )


@traced_node("triage", run_type="chain", log_output=True)
def triage_node(state: IssueState) -> dict:
    """Classify an issue using Claude."""
    llm = ChatAnthropic(model=DEFAULT_TRIAGE_MODEL)

    system_prompt = _build_triage_prompt(state)

    response = llm.with_structured_output(TriageResult).invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=f"Title: {state['issue_title']}\n\n{state['issue_body']}"
            ),
        ]
    )

    # Log decision details
    log_node_event(
        "triage",
        f"decision={response.decision}",
        "success" if response.decision == "valid" else "warning",
        duplicate_of=response.duplicate_of if response.duplicate_of else None,
    )

    return {
        "triage_decision": response.decision,
        "triage_reason": response.reason,
        "duplicate_of": response.duplicate_of,
        "triage_questions": response.questions,
        "labels_to_add": get_triage_labels().get(response.decision, []),
    }
