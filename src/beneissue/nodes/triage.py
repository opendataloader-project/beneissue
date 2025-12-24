"""Triage node implementation."""

from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from beneissue.config import load_config
from beneissue.graph.state import IssueState
from beneissue.nodes.schemas import TriageResult

# Load prompt from file
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "triage.md"
TRIAGE_PROMPT = PROMPT_PATH.read_text()

# Label mapping for triage decisions
TRIAGE_LABELS = {
    "valid": ["triage/valid"],
    "invalid": ["triage/invalid"],
    "duplicate": ["triage/duplicate"],
    "needs_info": ["triage/needs-info"],
}


def triage_node(state: IssueState) -> dict:
    """Classify an issue using Claude."""
    config = load_config()
    llm = ChatAnthropic(model=config.models.triage)

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
