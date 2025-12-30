"""Pydantic schemas for metrics data."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class WorkflowRunRecord(BaseModel):
    """Record of a single step execution (triage, analyze, or fix)."""

    # Identification
    repo: str
    issue_number: int
    workflow_type: Literal["triage", "analyze", "fix"]

    # Timestamps
    issue_created_at: Optional[datetime] = None
    workflow_started_at: datetime = Field(default_factory=datetime.utcnow)
    workflow_completed_at: Optional[datetime] = None

    # Triage results
    triage_decision: Optional[
        Literal["valid", "invalid", "duplicate", "needs_info"]
    ] = None
    triage_reason: Optional[str] = None
    duplicate_of: Optional[int] = None

    # Analyze results
    fix_decision: Optional[
        Literal["auto_eligible", "manual_required", "comment_only"]
    ] = None
    priority: Optional[Literal["P0", "P1", "P2"]] = None
    story_points: Optional[int] = None
    assignee: Optional[str] = None

    # Fix results
    fix_success: Optional[bool] = None
    pr_url: Optional[str] = None
    fix_error: Optional[str] = None

    # Token usage
    input_tokens: int = 0
    output_tokens: int = 0

    def to_supabase_dict(self) -> dict:
        """Convert to dict for Supabase insert."""
        return self.model_dump(mode="json")
