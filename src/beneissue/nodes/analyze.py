"""Analyze node implementation."""

from pathlib import Path
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from beneissue.config import load_config
from beneissue.graph.state import IssueState
from beneissue.nodes.schemas import AnalyzeResult

# Load prompt from file
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "analyze.md"
ANALYZE_PROMPT = PROMPT_PATH.read_text()


def _build_analyze_prompt(state: IssueState) -> str:
    """Build the analyze prompt with context."""
    config = load_config()
    project_desc = config.project.description or f"Repository: {state['repo']}"

    # TODO: Add codebase structure exploration
    codebase_structure = "Codebase structure not loaded."

    return ANALYZE_PROMPT.format(
        project_description=project_desc,
        codebase_structure=codebase_structure,
    )


def analyze_node(state: IssueState) -> dict:
    """Analyze an issue using Claude."""
    config = load_config()
    llm = ChatAnthropic(model=config.models.analyze)

    system_prompt = _build_analyze_prompt(state)

    response = llm.with_structured_output(AnalyzeResult).invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=f"""Issue: {state['issue_title']}

{state['issue_body']}

Repository: {state['repo']}
"""
            ),
        ]
    )

    # Determine fix decision based on score and config threshold
    min_score = config.policy.auto_fix.min_score
    fix_decision: Literal["auto_eligible", "manual_required", "comment_only"]
    if config.policy.auto_fix.enabled and response.score.total >= min_score:
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
        "comment_draft": response.comment_draft,
        "labels_to_add": [
            f"priority/{response.priority.lower()}",
            f"sp/{response.story_points}",
            f"fix/{fix_decision.replace('_', '-')}",
            *response.labels,
        ],
    }
