"""LangGraph workflow definition."""

from typing import Optional

from langgraph.cache.memory import InMemoryCache
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import CachePolicy

from beneissue.graph.routing import (
    route_after_analyze,
    route_after_fix,
    route_after_intake,
    route_after_triage,
    route_after_triage_test,
)
from beneissue.graph.state import IssueState
from beneissue.metrics.collector import (
    record_analyze_metrics_node,
    record_fix_metrics_node,
    record_triage_metrics_node,
)
from beneissue.nodes.actions import (
    apply_labels_node,
    limit_exceeded_node,
    post_comment_node,
)
from beneissue.nodes.analyze import analyze_node
from beneissue.nodes.fix import fix_node
from beneissue.nodes.intake import intake_node
from beneissue.nodes.load_preset import load_preset_node
from beneissue.nodes.triage import triage_node

# Cache policies for expensive LLM nodes
# TTL in seconds: 3600 = 1 hour, useful for development/testing
TRIAGE_CACHE_POLICY = CachePolicy(ttl=3600)
ANALYZE_CACHE_POLICY = CachePolicy(ttl=3600)


def _build_triage_graph(*, enable_cache: bool = False) -> StateGraph:
    """Build triage-only graph: intake → triage → record_triage_metrics → apply_labels."""
    workflow = StateGraph(IssueState)

    workflow.add_node("intake", intake_node)
    workflow.add_node("limit_exceeded", limit_exceeded_node)
    workflow.add_node(
        "triage",
        triage_node,
        cache_policy=TRIAGE_CACHE_POLICY if enable_cache else None,
    )
    workflow.add_node("record_triage_metrics", record_triage_metrics_node)
    workflow.add_node("apply_labels", apply_labels_node)

    workflow.set_entry_point("intake")

    # Check daily limit after intake
    workflow.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "limit_exceeded": "limit_exceeded",
            "continue": "triage",
        },
    )

    workflow.add_edge("limit_exceeded", END)
    workflow.add_edge("triage", "record_triage_metrics")
    workflow.add_edge("record_triage_metrics", "apply_labels")
    workflow.add_edge("apply_labels", END)

    return workflow


def create_triage_workflow(
    checkpointer: Optional[BaseCheckpointSaver] = None,
    *,
    enable_cache: bool = False,
) -> StateGraph:
    """Create triage-only workflow with optional checkpointing and caching.

    Args:
        checkpointer: Optional checkpoint saver for state persistence.
        enable_cache: Enable node-level caching for triage (reduces API costs).
    """
    graph = _build_triage_graph(enable_cache=enable_cache)
    cache = InMemoryCache() if enable_cache else None
    return graph.compile(checkpointer=checkpointer, cache=cache)


def _build_analyze_graph(*, enable_cache: bool = False) -> StateGraph:
    """Build analyze-only graph: intake → analyze → record_analyze_metrics → post_comment → apply_labels."""
    workflow = StateGraph(IssueState)

    workflow.add_node("intake", intake_node)
    workflow.add_node("limit_exceeded", limit_exceeded_node)
    workflow.add_node(
        "analyze",
        analyze_node,
        cache_policy=ANALYZE_CACHE_POLICY if enable_cache else None,
    )
    workflow.add_node("record_analyze_metrics", record_analyze_metrics_node)
    workflow.add_node("post_comment", post_comment_node)
    workflow.add_node("apply_labels", apply_labels_node)

    workflow.set_entry_point("intake")

    # Check daily limit after intake
    workflow.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "limit_exceeded": "limit_exceeded",
            "continue": "analyze",
        },
    )

    workflow.add_edge("limit_exceeded", END)

    # Record metrics right after analyze, then post comment
    workflow.add_edge("analyze", "record_analyze_metrics")
    workflow.add_edge("record_analyze_metrics", "post_comment")
    workflow.add_edge("post_comment", "apply_labels")
    workflow.add_edge("apply_labels", END)

    return workflow


def create_analyze_workflow(
    checkpointer: Optional[BaseCheckpointSaver] = None,
    *,
    enable_cache: bool = False,
) -> StateGraph:
    """Create analyze-only workflow with optional checkpointing and caching.

    Args:
        checkpointer: Optional checkpoint saver for state persistence.
        enable_cache: Enable node-level caching for analyze (reduces API costs).
    """
    graph = _build_analyze_graph(enable_cache=enable_cache)
    cache = InMemoryCache() if enable_cache else None
    return graph.compile(checkpointer=checkpointer, cache=cache)


def _build_fix_graph() -> StateGraph:
    """Build fix-only graph: intake → fix → record_fix_metrics → post_comment/apply_labels."""
    workflow = StateGraph(IssueState)

    workflow.add_node("intake", intake_node)
    workflow.add_node("limit_exceeded", limit_exceeded_node)
    workflow.add_node("fix", fix_node)
    workflow.add_node("record_fix_metrics", record_fix_metrics_node)
    workflow.add_node("post_comment", post_comment_node)
    workflow.add_node("apply_labels", apply_labels_node)

    workflow.set_entry_point("intake")

    # Check daily limit after intake
    workflow.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "limit_exceeded": "limit_exceeded",
            "continue": "fix",
        },
    )

    workflow.add_edge("limit_exceeded", END)

    # Record metrics right after fix
    workflow.add_edge("fix", "record_fix_metrics")

    workflow.add_conditional_edges(
        "record_fix_metrics",
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
    """Create fix-only workflow with optional checkpointing.

    Args:
        checkpointer: Optional checkpoint saver for state persistence.
    """
    return _build_fix_graph().compile(checkpointer=checkpointer)


def _build_full_graph(*, enable_cache: bool = False) -> StateGraph:
    """Build the full graph with triage, analyze, fix, and actions.

    Each step records its own metrics immediately after completion.
    """
    workflow = StateGraph(IssueState)

    # Add all nodes (with optional caching for expensive LLM nodes)
    workflow.add_node("intake", intake_node)
    workflow.add_node("limit_exceeded", limit_exceeded_node)
    workflow.add_node(
        "triage",
        triage_node,
        cache_policy=TRIAGE_CACHE_POLICY if enable_cache else None,
    )
    workflow.add_node("record_triage_metrics", record_triage_metrics_node)
    workflow.add_node(
        "analyze",
        analyze_node,
        cache_policy=ANALYZE_CACHE_POLICY if enable_cache else None,
    )
    workflow.add_node("record_analyze_metrics", record_analyze_metrics_node)
    workflow.add_node("fix", fix_node)
    workflow.add_node("record_fix_metrics", record_fix_metrics_node)
    workflow.add_node("apply_labels", apply_labels_node)
    workflow.add_node("post_comment", post_comment_node)

    # Define edges
    workflow.set_entry_point("intake")

    # Check daily limit after intake
    workflow.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "limit_exceeded": "limit_exceeded",
            "continue": "triage",
        },
    )

    workflow.add_edge("limit_exceeded", END)

    # Record triage metrics immediately after triage
    workflow.add_edge("triage", "record_triage_metrics")

    # Conditional routing after triage metrics
    workflow.add_conditional_edges(
        "record_triage_metrics",
        route_after_triage,
        {
            "analyze": "analyze",
            "apply_labels": "apply_labels",
        },
    )

    # Record analyze metrics immediately after analyze
    workflow.add_edge("analyze", "record_analyze_metrics")

    # Conditional routing after analyze metrics
    workflow.add_conditional_edges(
        "record_analyze_metrics",
        route_after_analyze,
        {
            "fix": "fix",
            "apply_labels": "apply_labels",
            "post_comment": "post_comment",
        },
    )

    # Record fix metrics immediately after fix
    workflow.add_edge("fix", "record_fix_metrics")

    # Conditional routing after fix metrics
    workflow.add_conditional_edges(
        "record_fix_metrics",
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
    *,
    enable_cache: bool = False,
) -> StateGraph:
    """Create the full workflow with optional checkpointing and caching.

    Args:
        checkpointer: Optional checkpoint saver for state persistence.
            Use MemorySaver() for in-memory checkpointing or
            SqliteSaver for persistent storage.
        enable_cache: Enable node-level caching for triage/analyze nodes.
            Useful for development and testing to reduce API costs.

    Returns:
        Compiled workflow graph.
    """
    graph = _build_full_graph(enable_cache=enable_cache)
    cache = InMemoryCache() if enable_cache else None
    return graph.compile(checkpointer=checkpointer, cache=cache)


def _build_test_full_graph(*, enable_cache: bool = False) -> StateGraph:
    """Build test graph: load_preset → triage → record_triage_metrics → analyze → record_analyze_metrics → END.

    This graph is designed for LangSmith Studio testing without GitHub dependencies.
    Uses configurable preset_name to load test cases from JSON files.
    """
    workflow = StateGraph(IssueState)

    # Add nodes
    workflow.add_node("load_preset", load_preset_node)
    workflow.add_node(
        "triage",
        triage_node,
        cache_policy=TRIAGE_CACHE_POLICY if enable_cache else None,
    )
    workflow.add_node("record_triage_metrics", record_triage_metrics_node)
    workflow.add_node(
        "analyze",
        analyze_node,
        cache_policy=ANALYZE_CACHE_POLICY if enable_cache else None,
    )
    workflow.add_node("record_analyze_metrics", record_analyze_metrics_node)

    # Define edges
    workflow.set_entry_point("load_preset")
    workflow.add_edge("load_preset", "triage")
    workflow.add_edge("triage", "record_triage_metrics")

    # Conditional routing: valid → analyze, else → END
    workflow.add_conditional_edges(
        "record_triage_metrics",
        route_after_triage_test,
        {
            "analyze": "analyze",
            END: END,
        },
    )

    workflow.add_edge("analyze", "record_analyze_metrics")
    workflow.add_edge("record_analyze_metrics", END)

    return workflow


def create_test_full_workflow(
    checkpointer: Optional[BaseCheckpointSaver] = None,
    *,
    enable_cache: bool = False,
) -> StateGraph:
    """Create test workflow for LangSmith Studio.

    Args:
        checkpointer: Optional checkpoint saver for state persistence.
        enable_cache: Enable node-level caching for triage/analyze (reduces API costs).

    Usage in LangSmith Studio:
        Set configurable preset_name to one of:
        - analyze-auto-eligible-typo
        - analyze-comment-only-question
        - analyze-manual-overflow
    """
    graph = _build_test_full_graph(enable_cache=enable_cache)
    cache = InMemoryCache() if enable_cache else None
    return graph.compile(checkpointer=checkpointer, cache=cache)


# Compiled workflow instances (without checkpointing for backward compatibility)
triage_graph = create_triage_workflow()
analyze_graph = create_analyze_workflow()
fix_graph = create_fix_workflow()
full_graph = create_full_workflow()
test_full_graph = create_test_full_workflow()


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
    *,
    enable_cache: bool = False,
) -> tuple[StateGraph, MemorySaver]:
    """Create a workflow with MemorySaver checkpointing and optional caching.

    Args:
        workflow_type: One of "triage", "analyze", "fix", or "full".
        enable_cache: Enable node-level caching to reduce API costs.

    Returns:
        Tuple of (compiled workflow, checkpointer).

    Example:
        # For development with caching enabled
        graph, checkpointer = create_checkpointed_workflow("full", enable_cache=True)
        thread_id = get_thread_id("owner/repo", 123)
        result = graph.invoke(
            {"repo": "owner/repo", "issue_number": 123},
            config={"configurable": {"thread_id": thread_id}},
        )
    """
    checkpointer = MemorySaver()

    if workflow_type == "triage":
        return create_triage_workflow(
            checkpointer=checkpointer,
            enable_cache=enable_cache,
        ), checkpointer
    elif workflow_type == "analyze":
        return create_analyze_workflow(
            checkpointer=checkpointer,
            enable_cache=enable_cache,
        ), checkpointer
    elif workflow_type == "fix":
        return create_fix_workflow(checkpointer=checkpointer), checkpointer
    else:  # full
        return create_full_workflow(
            checkpointer=checkpointer,
            enable_cache=enable_cache,
        ), checkpointer
