"""LangGraph workflow definition."""

from langgraph.graph import END, StateGraph

from beneissue.graph.routing import (
    route_after_analyze,
    route_after_fix,
    route_after_triage,
)
from beneissue.graph.state import IssueState
from beneissue.nodes.actions import apply_labels_node, post_comment_node
from beneissue.nodes.analyze import analyze_node
from beneissue.nodes.fix import fix_node
from beneissue.nodes.intake import intake_node
from beneissue.nodes.triage import triage_node


def create_triage_workflow() -> StateGraph:
    """Create triage-only workflow: intake → triage → apply_labels."""
    workflow = StateGraph(IssueState)

    workflow.add_node("intake", intake_node)
    workflow.add_node("triage", triage_node)
    workflow.add_node("apply_labels", apply_labels_node)

    workflow.set_entry_point("intake")
    workflow.add_edge("intake", "triage")
    workflow.add_edge("triage", "apply_labels")
    workflow.add_edge("apply_labels", END)

    return workflow.compile()


def create_analyze_workflow() -> StateGraph:
    """Create analyze-only workflow: intake → analyze → post_comment → apply_labels."""
    workflow = StateGraph(IssueState)

    workflow.add_node("intake", intake_node)
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("apply_labels", apply_labels_node)
    workflow.add_node("post_comment", post_comment_node)

    workflow.set_entry_point("intake")
    workflow.add_edge("intake", "analyze")

    # Always post comment after analyze
    workflow.add_edge("analyze", "post_comment")
    workflow.add_edge("post_comment", "apply_labels")
    workflow.add_edge("apply_labels", END)

    return workflow.compile()


def create_fix_workflow() -> StateGraph:
    """Create fix-only workflow: intake → fix → post_comment/apply_labels."""
    workflow = StateGraph(IssueState)

    workflow.add_node("intake", intake_node)
    workflow.add_node("fix", fix_node)
    workflow.add_node("apply_labels", apply_labels_node)
    workflow.add_node("post_comment", post_comment_node)

    workflow.set_entry_point("intake")
    workflow.add_edge("intake", "fix")

    workflow.add_conditional_edges(
        "fix",
        route_after_fix,
        {
            "apply_labels": "apply_labels",
            "post_comment": "post_comment",
        },
    )

    workflow.add_edge("post_comment", "apply_labels")
    workflow.add_edge("apply_labels", END)

    return workflow.compile()


def create_full_workflow() -> StateGraph:
    """Create the full workflow with triage, analyze, fix, and actions."""
    workflow = StateGraph(IssueState)

    # Add all nodes
    workflow.add_node("intake", intake_node)
    workflow.add_node("triage", triage_node)
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("fix", fix_node)
    workflow.add_node("apply_labels", apply_labels_node)
    workflow.add_node("post_comment", post_comment_node)

    # Define edges
    workflow.set_entry_point("intake")
    workflow.add_edge("intake", "triage")

    # Conditional routing after triage
    workflow.add_conditional_edges(
        "triage",
        route_after_triage,
        {
            "analyze": "analyze",
            "apply_labels": "apply_labels",
        },
    )

    # Conditional routing after analyze
    workflow.add_conditional_edges(
        "analyze",
        route_after_analyze,
        {
            "fix": "fix",
            "apply_labels": "apply_labels",
            "post_comment": "post_comment",
        },
    )

    # Conditional routing after fix
    workflow.add_conditional_edges(
        "fix",
        route_after_fix,
        {
            "apply_labels": "apply_labels",
            "post_comment": "post_comment",
        },
    )

    # Terminal edges
    workflow.add_edge("apply_labels", END)
    workflow.add_edge("post_comment", "apply_labels")

    return workflow.compile()


# Compiled workflow instances
triage_graph = create_triage_workflow()
analyze_graph = create_analyze_workflow()
fix_graph = create_fix_workflow()
full_graph = create_full_workflow()
