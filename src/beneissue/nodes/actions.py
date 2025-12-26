"""Action nodes for GitHub operations."""

from beneissue.graph.state import IssueState
from beneissue.integrations.github import ANALYSIS_MARKER, get_github_client
from beneissue.observability import get_node_logger

logger = get_node_logger("actions")


def limit_exceeded_node(state: IssueState) -> dict:
    """Handle daily limit exceeded - post comment and skip processing."""
    daily_run_count = state.get("daily_run_count", 0)

    # No-action mode: skip GitHub operations
    if state.get("no_action"):
        logger.info(
            "[DRY-RUN] Would post limit exceeded comment (count=%d)",
            daily_run_count,
        )
        return {}

    gh = get_github_client()
    repo = gh.get_repo(state["repo"])
    issue = repo.get_issue(state["issue_number"])

    comment = (
        f"⚠️ **Daily limit exceeded**\n\n"
        f"This issue cannot be processed at this time. "
        f"The daily automation limit has been reached ({daily_run_count} runs today).\n\n"
        f"Please try again tomorrow or process this issue manually.\n\n"
        f"---\n🤖 *beneissue automation*"
    )
    issue.create_comment(comment)

    return {}


def apply_labels_node(state: IssueState) -> dict:
    """Apply labels and assignee to the issue on GitHub."""
    # No-action mode: skip GitHub operations
    if state.get("no_action"):
        labels_to_add = state.get("labels_to_add", [])
        labels_to_remove = state.get("labels_to_remove", [])
        assignee = state.get("assignee")
        logger.info("[DRY-RUN] Would apply labels: %s", labels_to_add)
        if labels_to_remove:
            logger.info("[DRY-RUN] Would remove labels: %s", labels_to_remove)
        if assignee:
            logger.info("[DRY-RUN] Would assign to: %s", assignee)
        return {}

    gh = get_github_client()
    repo = gh.get_repo(state["repo"])
    issue = repo.get_issue(state["issue_number"])

    # Add labels
    labels_to_add = state.get("labels_to_add", [])
    if labels_to_add:
        for label in labels_to_add:
            try:
                issue.add_to_labels(label)
            except Exception as e:
                logger.warning("Failed to add label '%s': %s", label, e)

    # Remove labels
    labels_to_remove = state.get("labels_to_remove", [])
    if labels_to_remove:
        for label in labels_to_remove:
            try:
                issue.remove_from_labels(label)
            except Exception as e:
                logger.warning("Failed to remove label '%s': %s", label, e)

    # Assign issue
    assignee = state.get("assignee")
    if assignee:
        try:
            issue.add_to_assignees(assignee)
        except Exception as e:
            logger.warning("Failed to assign '%s': %s", assignee, e)

    return {}


def post_comment_node(state: IssueState) -> dict:
    """Post a comment on the issue summarizing the analysis."""
    # No-action mode: skip GitHub operations
    if state.get("no_action"):
        logger.info("[DRY-RUN] Would post comment (analysis_summary=%s...)",
                    state.get("analysis_summary", "")[:50])
        return {}

    gh = get_github_client()
    repo = gh.get_repo(state["repo"])
    issue = repo.get_issue(state["issue_number"])

    # Build comment based on state
    comment_parts = []

    # Add triage info if invalid/duplicate/needs_info
    triage_decision = state.get("triage_decision")
    if triage_decision and triage_decision != "valid":
        comment_parts.append(f"**Triage Decision:** {triage_decision}")
        comment_parts.append(f"**Reason:** {state.get('triage_reason', 'N/A')}")
        if state.get("duplicate_of"):
            comment_parts.append(f"**Duplicate of:** #{state['duplicate_of']}")

    # Add analysis summary if available
    if state.get("analysis_summary"):
        comment_parts.append(ANALYSIS_MARKER)
        comment_parts.append("## 🤖 Analysis")
        comment_parts.append(state["analysis_summary"])

        # Priority and effort estimation
        priority = state.get("priority")
        story_points = state.get("story_points")
        if priority or story_points:
            comment_parts.append("")
            if priority:
                priority_desc = {"P0": "Critical", "P1": "High", "P2": "Normal"}.get(
                    priority, priority
                )
                comment_parts.append(f"**Priority:** {priority} ({priority_desc})")
            if story_points:
                sp_desc = {
                    1: "< 1 day",
                    2: "1-2 days",
                    3: "3-5 days",
                    5: "6-10 days",
                    8: "10+ days",
                }.get(story_points, f"{story_points} points")
                comment_parts.append(f"**Estimated Effort:** {story_points} SP ({sp_desc})")

        if state.get("affected_files"):
            comment_parts.append("\n**Affected Files:**")
            for f in state["affected_files"]:
                comment_parts.append(f"- `{f}`")

        if state.get("assignee"):
            comment_parts.append(f"\n**Assigned to:** @{state['assignee']}")

        if state.get("fix_decision"):
            comment_parts.append(f"\n**Decision:** {state.get('fix_decision')}")

    # Add custom comment if provided
    if state.get("comment_to_post"):
        comment_parts.append("---")
        comment_parts.append(state["comment_to_post"])

    # Post comment if we have content
    if comment_parts:
        comment_body = "\n".join(comment_parts)
        comment_body += "\n\n---\n🤖 *This was generated by AI and may be inaccurate or inappropriate. Please review carefully!*"
        issue.create_comment(comment_body)

    return {}
