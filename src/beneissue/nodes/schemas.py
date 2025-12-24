"""Pydantic schemas for LLM structured output."""

from typing import Literal, Optional

from pydantic import BaseModel


class TriageResult(BaseModel):
    """Triage node output schema."""

    decision: Literal["valid", "invalid", "duplicate", "needs_info"]
    reason: str
    duplicate_of: Optional[int] = None


class ScoreBreakdown(BaseModel):
    """Score breakdown for auto-fix eligibility."""

    total: int  # 0-100
    scope: int  # 0-30: How localized is the change?
    risk: int  # 0-30: How risky is the change?
    verifiability: int  # 0-25: Can we verify the fix?
    clarity: int  # 0-15: How clear are the requirements?


class AnalyzeResult(BaseModel):
    """Analyze node output schema."""

    summary: str
    affected_files: list[str]
    approach: str
    score: ScoreBreakdown
    priority: Literal["P0", "P1", "P2"]
    story_points: Literal[1, 2, 3, 5, 8]
    labels: list[str]
