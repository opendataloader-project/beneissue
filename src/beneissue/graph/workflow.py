"""LangGraph workflow definition."""

from langgraph.graph import END, StateGraph

from beneissue.graph.state import IssueState
from beneissue.nodes.intake import intake_node
from beneissue.nodes.triage import triage_node


def create_triage_workflow() -> StateGraph:
    """Create the PoC triage workflow (intake -> triage only)."""
    workflow = StateGraph(IssueState)

    # Add nodes
    workflow.add_node("intake", intake_node)
    workflow.add_node("triage", triage_node)

    # Define edges
    workflow.set_entry_point("intake")
    workflow.add_edge("intake", "triage")
    workflow.add_edge("triage", END)

    return workflow.compile()


# Compiled workflow instance
triage_graph = create_triage_workflow()
