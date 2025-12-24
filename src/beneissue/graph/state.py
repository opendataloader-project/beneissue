"""IssueState schema for LangGraph workflow."""

from typing import Literal, Optional, TypedDict


class IssueState(TypedDict, total=False):
    """State schema for the issue processing workflow."""

    # === Input ===
    repo: str  # owner/repo
    issue_number: int
    issue_title: str
    issue_body: str
    issue_labels: list[str]
    issue_author: str

    # === Triage 결과 ===
    triage_decision: Literal["valid", "invalid", "duplicate", "needs_info"]
    triage_reason: str
    duplicate_of: Optional[int]
    triage_questions: Optional[list[str]]  # Questions for needs_info

    # === Analyze 결과 ===
    analysis_summary: str
    affected_files: list[str]
    fix_approach: str
    score: dict
    fix_decision: Literal["auto_eligible", "manual_required", "comment_only"]
    comment_draft: Optional[str]  # Comment for manual-required or comment-only

    # === Fix 결과 ===
    fix_success: bool
    pr_url: Optional[str]
    fix_error: Optional[str]

    # === 메타데이터 ===
    labels_to_add: list[str]
    labels_to_remove: list[str]
    comment_to_post: Optional[str]
