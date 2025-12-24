"""Analyze node implementation."""

from pathlib import Path
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from beneissue.graph.state import IssueState
from beneissue.nodes.schemas import AnalyzeResult

# Load prompt from file
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "analyze.md"
ANALYZE_PROMPT = PROMPT_PATH.read_text()

# Auto-fix eligibility threshold
AUTO_FIX_THRESHOLD = 80


def analyze_node(state: IssueState) -> dict:
    """Analyze an issue using Claude Sonnet."""
    llm = ChatAnthropic(model="claude-sonnet-4-5")

    response = llm.with_structured_output(AnalyzeResult).invoke(
        [
            SystemMessage(content=ANALYZE_PROMPT),
            HumanMessage(
                content=f"""Issue: {state['issue_title']}

{state['issue_body']}

Repository: {state['repo']}
"""
            ),
        ]
    )

    # Determine fix decision based on score
    fix_decision: Literal["auto_eligible", "manual_required", "comment_only"]
    if response.score.total >= AUTO_FIX_THRESHOLD:
        fix_decision = "auto_eligible"
    elif response.score.total >= 50:
        fix_decision = "manual_required"
    else:
        fix_decision = "comment_only"

    return {
        "analysis_summary": response.summary,
        "affected_files": response.affected_files,
        "fix_approach": response.approach,
        "score": response.score.model_dump(),
        "fix_decision": fix_decision,
        "labels_to_add": [
            f"priority/{response.priority.lower()}",
            f"sp/{response.story_points}",
            f"fix/{fix_decision.replace('_', '-')}",
            *response.labels,
        ],
    }
