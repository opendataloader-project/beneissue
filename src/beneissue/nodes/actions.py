"""Action nodes for GitHub operations."""

from beneissue.graph.state import IssueState
from beneissue.integrations.github import get_github_client


def apply_labels_node(state: IssueState) -> dict:
    """Apply labels to the issue on GitHub."""
    gh = get_github_client()
    repo = gh.get_repo(state["repo"])
    issue = repo.get_issue(state["issue_number"])

    # Add labels
    labels_to_add = state.get("labels_to_add", [])
    if labels_to_add:
        for label in labels_to_add:
            try:
                issue.add_to_labels(label)
            except Exception:
                # Label might not exist, skip
                pass

    # Remove labels
    labels_to_remove = state.get("labels_to_remove", [])
    if labels_to_remove:
        for label in labels_to_remove:
            try:
                issue.remove_from_labels(label)
            except Exception:
                # Label might not be on issue, skip
                pass

    return {}


def post_comment_node(state: IssueState) -> dict:
    """Post a comment on the issue summarizing the analysis."""
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
        comment_parts.append("---")
        comment_parts.append("## Analysis Summary")
        comment_parts.append(state["analysis_summary"])

        if state.get("affected_files"):
            comment_parts.append("\n**Affected Files:**")
            for f in state["affected_files"]:
                comment_parts.append(f"- `{f}`")

        if state.get("fix_approach"):
            comment_parts.append(f"\n**Recommended Approach:**\n{state['fix_approach']}")

        if state.get("score"):
            score = state["score"]
            comment_parts.append(f"\n**Auto-fix Score:** {score.get('total', 'N/A')}/100")
            comment_parts.append(f"**Decision:** {state.get('fix_decision', 'N/A')}")

    # Add custom comment if provided
    if state.get("comment_to_post"):
        comment_parts.append("---")
        comment_parts.append(state["comment_to_post"])

    # Post comment if we have content
    if comment_parts:
        comment_body = "\n".join(comment_parts)
        comment_body += "\n\n---\n*🤖 Analyzed by [beneissue](https://github.com/opendataloader-project/beneissue)*"
        issue.create_comment(comment_body)

    return {}
