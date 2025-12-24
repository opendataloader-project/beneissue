"""Triage node implementation."""

from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from beneissue.graph.state import IssueState
from beneissue.nodes.schemas import TriageResult

# Load prompt from file
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "triage.md"
TRIAGE_PROMPT = PROMPT_PATH.read_text()

# Label mapping for triage decisions
TRIAGE_LABELS = {
    "valid": ["triage/valid"],
    "invalid": ["wontfix"],
    "duplicate": ["duplicate"],
    "needs_info": ["question"],
}


def triage_node(state: IssueState) -> dict:
    """Classify an issue using Claude Haiku."""
    llm = ChatAnthropic(model="claude-haiku-4-5")

    response = llm.with_structured_output(TriageResult).invoke(
        [
            SystemMessage(content=TRIAGE_PROMPT),
            HumanMessage(
                content=f"Title: {state['issue_title']}\n\n{state['issue_body']}"
            ),
        ]
    )

    return {
        "triage_decision": response.decision,
        "triage_reason": response.reason,
        "duplicate_of": response.duplicate_of,
        "labels_to_add": TRIAGE_LABELS.get(response.decision, []),
    }
