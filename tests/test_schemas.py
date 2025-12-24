"""Tests for Pydantic schemas."""

import pytest
from pydantic import ValidationError

from beneissue.nodes.schemas import AnalyzeResult, TriageResult


class TestTriageResult:
    """Tests for TriageResult schema."""

    def test_valid_decision(self):
        result = TriageResult(decision="valid", reason="This is a valid bug report")
        assert result.decision == "valid"
        assert result.duplicate_of is None

    def test_duplicate_with_issue_number(self):
        result = TriageResult(
            decision="duplicate", reason="Duplicate of #42", duplicate_of=42
        )
        assert result.decision == "duplicate"
        assert result.duplicate_of == 42

    def test_invalid_decision_rejected(self):
        with pytest.raises(ValidationError):
            TriageResult(decision="unknown", reason="test")


class TestAnalyzeResult:
    """Tests for AnalyzeResult schema."""

    def test_valid_result(self):
        result = AnalyzeResult(
            summary="Fix typo in README",
            affected_files=["README.md"],
            fix_decision="auto_eligible",
            reason="Simple typo fix with clear solution",
            priority="P2",
            story_points=1,
            labels=["documentation"],
        )
        assert result.priority == "P2"
        assert result.story_points == 1
        assert result.fix_decision == "auto_eligible"

    def test_invalid_priority_rejected(self):
        with pytest.raises(ValidationError):
            AnalyzeResult(
                summary="test",
                affected_files=[],
                fix_decision="auto_eligible",
                reason="test reason",
                priority="P3",  # Invalid
                story_points=1,
                labels=[],
            )

    def test_invalid_story_points_rejected(self):
        with pytest.raises(ValidationError):
            AnalyzeResult(
                summary="test",
                affected_files=[],
                fix_decision="auto_eligible",
                reason="test reason",
                priority="P1",
                story_points=4,  # Invalid (not in 1,2,3,5,8)
                labels=[],
            )

    def test_assignee_optional(self):
        result = AnalyzeResult(
            summary="Fix bug",
            affected_files=["src/main.py"],
            fix_decision="manual_required",
            reason="Complex fix requiring review",
            priority="P1",
            story_points=3,
            labels=["bug"],
            assignee="dev-john",
        )
        assert result.assignee == "dev-john"
