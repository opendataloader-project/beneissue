"""Tests for Pydantic schemas."""

import pytest
from pydantic import ValidationError

from beneissue.nodes.schemas import AnalyzeResult, ScoreBreakdown, TriageResult


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


class TestScoreBreakdown:
    """Tests for ScoreBreakdown schema."""

    def test_valid_scores(self):
        score = ScoreBreakdown(
            total=85, scope=25, risk=25, verifiability=20, clarity=15
        )
        assert score.total == 85

    def test_auto_fix_threshold(self):
        """Score >= 80 should be auto-fix eligible."""
        high_score = ScoreBreakdown(
            total=85, scope=25, risk=25, verifiability=20, clarity=15
        )
        low_score = ScoreBreakdown(
            total=60, scope=15, risk=15, verifiability=15, clarity=15
        )

        assert high_score.total >= 80
        assert low_score.total < 80


class TestAnalyzeResult:
    """Tests for AnalyzeResult schema."""

    def test_valid_result(self):
        result = AnalyzeResult(
            summary="Fix typo in README",
            affected_files=["README.md"],
            approach="Change 'teh' to 'the'",
            score=ScoreBreakdown(
                total=95, scope=30, risk=30, verifiability=25, clarity=10
            ),
            priority="P2",
            story_points=1,
            labels=["documentation"],
        )
        assert result.priority == "P2"
        assert result.story_points == 1

    def test_invalid_priority_rejected(self):
        with pytest.raises(ValidationError):
            AnalyzeResult(
                summary="test",
                affected_files=[],
                approach="test",
                score=ScoreBreakdown(
                    total=50, scope=10, risk=10, verifiability=10, clarity=10
                ),
                priority="P3",  # Invalid
                story_points=1,
                labels=[],
            )

    def test_invalid_story_points_rejected(self):
        with pytest.raises(ValidationError):
            AnalyzeResult(
                summary="test",
                affected_files=[],
                approach="test",
                score=ScoreBreakdown(
                    total=50, scope=10, risk=10, verifiability=10, clarity=10
                ),
                priority="P1",
                story_points=4,  # Invalid (not in 1,2,3,5,8)
                labels=[],
            )
