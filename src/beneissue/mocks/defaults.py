"""Default mock data for dry-run mode."""

from typing import Any

DEFAULT_TRIAGE: dict[str, Any] = {
    "decision": "valid",
    "reason": "[DRY-RUN] Mock triage result - issue marked as valid for testing",
    "duplicate_of": None,
    "questions": None,
}

DEFAULT_ANALYZE: dict[str, Any] = {
    "summary": "[DRY-RUN] Mock analysis result for testing GitHub integration",
    "affected_files": [],
    "fix_decision": "comment_only",
    "reason": "[DRY-RUN] Mock mode - no actual analysis performed",
    "priority": "P2",
    "story_points": 1,
    "labels": [],
    "assignee": None,
    "comment_draft": None,
}

DEFAULT_FIX: dict[str, Any] = {
    "success": True,
    "title": "[DRY-RUN] Mock fix",
    "description": "[DRY-RUN] No actual changes made - testing GitHub integration",
    "error": None,
}
