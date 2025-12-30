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
    """Route after analyze node based on fix decision and command.

    Fix only runs when:
    1. fix_decision is "auto_eligible", AND
    2. command is "fix" (explicit @beneissue fix approval)

    This ensures auto-eligible issues still require human approval via @beneissue fix.
    """
    fix_decision = state.get("fix_decision")
    command = state.get("command")

    # Only proceed to fix if explicitly requested via @beneissue fix
    if fix_decision == "auto_eligible" and command == "fix":
        return "fix"

    # All other cases: post comment or apply labels
    if fix_decision in ("auto_eligible", "manual_required", "comment_only"):
        return "post_comment"

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
