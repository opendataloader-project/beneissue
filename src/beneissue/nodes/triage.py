"""Triage node implementation."""

from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from beneissue.config import load_config
from beneissue.graph.state import IssueState
from beneissue.integrations.github import format_existing_issues
from beneissue.labels import get_triage_labels
from beneissue.nodes.schemas import TriageResult

# Load prompt from file
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "triage.md"
TRIAGE_PROMPT = PROMPT_PATH.read_text()


def _build_triage_prompt(state: IssueState) -> str:
    """Build the triage prompt with context."""
    # Read README from repo root
    readme_path = Path.cwd() / "README.md"
    if readme_path.exists():
        readme_content = readme_path.read_text()
    else:
        readme_content = f"Repository: {state['repo']}\n\nNo README.md found."

    # Format existing issues for duplicate detection
    existing = state.get("existing_issues", [])
    existing_issues = (
        format_existing_issues(existing) if existing else "No existing issues loaded."
    )

    return TRIAGE_PROMPT.format(
        readme_content=readme_content,
        existing_issues=existing_issues,
    )


def triage_node(state: IssueState) -> dict:
    """Classify an issue using Claude."""
    config = load_config()
    llm = ChatAnthropic(model=config.models.triage)

    system_prompt = _build_triage_prompt(state)

    response = llm.with_structured_output(TriageResult).invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=f"Title: {state['issue_title']}\n\n{state['issue_body']}"
            ),
        ]
    )

    return {
        "triage_decision": response.decision,
        "triage_reason": response.reason,
        "duplicate_of": response.duplicate_of,
        "triage_questions": response.questions,
        "labels_to_add": get_triage_labels().get(response.decision, []),
    }
