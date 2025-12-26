"""Conditional routing functions for LangGraph workflow."""

from beneissue.graph.state import IssueState


def route_after_intake(state: IssueState) -> str:
    """Route after intake node - check daily limit before proceeding."""
    if state.get("daily_limit_exceeded"):
        return "limit_exceeded"
    return "continue"


def route_after_triage(state: IssueState) -> str:
    """Route after triage node based on decision."""
    match state.get("triage_decision"):
        case "valid":
            return "analyze"
        case "invalid" | "duplicate" | "needs_info":
            return "apply_labels"
        case _:
            return "apply_labels"


def route_after_analyze(state: IssueState) -> str:
    """Route after analyze node based on fix decision."""
    match state.get("fix_decision"):
        case "auto_eligible":
            return "fix"
        case "manual_required" | "comment_only":
            return "post_comment"
        case _:
            return "apply_labels"


def route_after_fix(state: IssueState) -> str:
    """Route after fix node based on success."""
    if state.get("fix_success"):
        return "apply_labels"
    else:
        return "post_comment"


def route_after_triage_test(state: IssueState) -> str:
    """Route after triage for test workflow (no apply_labels).

    Routes to analyze if valid, otherwise ends the workflow.
    Used by test_full_graph for LangSmith Studio testing.
    """
    if state.get("triage_decision") == "valid":
        return "analyze"
    return "__end__"
