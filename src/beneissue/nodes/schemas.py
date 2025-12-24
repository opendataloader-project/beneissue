"""Pydantic schemas for LLM structured output."""

from typing import Literal, Optional

from pydantic import BaseModel


class TriageResult(BaseModel):
    """Triage node output schema."""

    decision: Literal["valid", "invalid", "duplicate", "needs_info"]
    reason: str
    duplicate_of: Optional[int] = None
