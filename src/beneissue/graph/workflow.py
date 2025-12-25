"""LangGraph workflow definition."""

from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
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


def _build_triage_graph() -> StateGraph:
    """Build triage-only graph: intake → triage → apply_labels."""
    workflow = StateGraph(IssueState)

    workflow.add_node("intake", intake_node)
    workflow.add_node("triage", triage_node)
    workflow.add_node("apply_labels", apply_labels_node)

    workflow.set_entry_point("intake")
    workflow.add_edge("intake", "triage")
    workflow.add_edge("triage", "apply_labels")
    workflow.add_edge("apply_labels", END)

    return workflow


def create_triage_workflow(
    checkpointer: Optional[BaseCheckpointSaver] = None,
) -> StateGraph:
    """Create triage-only workflow with optional checkpointing."""
    return _build_triage_graph().compile(checkpointer=checkpointer)


def _build_analyze_graph() -> StateGraph:
    """Build analyze-only graph: intake → analyze → post_comment → apply_labels."""
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

    return workflow


def create_analyze_workflow(
    checkpointer: Optional[BaseCheckpointSaver] = None,
) -> StateGraph:
    """Create analyze-only workflow with optional checkpointing."""
    return _build_analyze_graph().compile(checkpointer=checkpointer)


def _build_fix_graph() -> StateGraph:
    """Build fix-only graph: intake → fix → post_comment/apply_labels."""
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

    return workflow


def create_fix_workflow(
    checkpointer: Optional[BaseCheckpointSaver] = None,
) -> StateGraph:
    """Create fix-only workflow with optional checkpointing."""
    return _build_fix_graph().compile(checkpointer=checkpointer)


def _build_full_graph() -> StateGraph:
    """Build the full graph with triage, analyze, fix, and actions."""
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

    return workflow


def create_full_workflow(
    checkpointer: Optional[BaseCheckpointSaver] = None,
) -> StateGraph:
    """Create the full workflow with optional checkpointing.

    Args:
        checkpointer: Optional checkpoint saver for state persistence.
            Use MemorySaver() for in-memory checkpointing or
            SqliteSaver for persistent storage.

    Returns:
        Compiled workflow graph.
    """
    return _build_full_graph().compile(checkpointer=checkpointer)


# Compiled workflow instances (without checkpointing for backward compatibility)
triage_graph = create_triage_workflow()
analyze_graph = create_analyze_workflow()
fix_graph = create_fix_workflow()
full_graph = create_full_workflow()


def get_thread_id(repo: str, issue_number: int) -> str:
    """Generate a unique thread ID for checkpointing.

    Args:
        repo: Repository in owner/repo format.
        issue_number: Issue number.

    Returns:
        Thread ID in format "repo:issue_number".
    """
    return f"{repo}:{issue_number}"


def create_checkpointed_workflow(
    workflow_type: str = "full",
) -> tuple[StateGraph, MemorySaver]:
    """Create a workflow with MemorySaver checkpointing.

    Args:
        workflow_type: One of "triage", "analyze", "fix", or "full".

    Returns:
        Tuple of (compiled workflow, checkpointer).

    Example:
        graph, checkpointer = create_checkpointed_workflow("full")
        thread_id = get_thread_id("owner/repo", 123)
        result = graph.invoke(
            {"repo": "owner/repo", "issue_number": 123},
            config={"configurable": {"thread_id": thread_id}},
        )
    """
    checkpointer = MemorySaver()
    creators = {
        "triage": create_triage_workflow,
        "analyze": create_analyze_workflow,
        "fix": create_fix_workflow,
        "full": create_full_workflow,
    }
    creator = creators.get(workflow_type, create_full_workflow)
    return creator(checkpointer=checkpointer), checkpointer
