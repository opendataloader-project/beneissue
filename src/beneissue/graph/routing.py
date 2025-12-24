"""Conditional routing functions for LangGraph workflow."""

from beneissue.graph.state import IssueState


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
            # TODO: Route to fix node when implemented
            return "apply_labels"
        case "manual_required" | "comment_only":
            return "post_comment"
        case _:
            return "apply_labels"
