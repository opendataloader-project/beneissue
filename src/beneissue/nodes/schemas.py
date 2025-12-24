"""Pydantic schemas for LLM structured output."""

from typing import Literal, Optional

from pydantic import BaseModel


class TriageResult(BaseModel):
    """Triage node output schema."""

    decision: Literal["valid", "invalid", "duplicate", "needs_info"]
    reason: str
    duplicate_of: Optional[int] = None
    questions: Optional[list[str]] = None  # Questions to ask when needs_info


class AnalyzeResult(BaseModel):
    """Analyze node output schema."""

    summary: str  # 2-3 sentences: what, why, how
    affected_files: list[str]
    fix_decision: Literal["auto_eligible", "manual_required", "comment_only"]
    reason: str  # 1-sentence justification for fix_decision
    priority: Literal["P0", "P1", "P2"]
    story_points: Literal[1, 2, 3, 5, 8]
    labels: list[str]  # bug, enhancement, documentation
    assignee: Optional[str] = None  # GitHub username from team config
    comment_draft: Optional[str] = None  # Required if comment_only


class FixResult(BaseModel):
    """Fix node output schema from Claude Code."""

    success: bool
    title: str  # Commit message title (50 chars max, imperative mood)
    description: str  # What was changed and why
    error: Optional[str] = None  # Error message if success is false
