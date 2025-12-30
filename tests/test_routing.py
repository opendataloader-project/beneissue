"""Tests for routing logic."""

import pytest

from beneissue.graph.routing import (
    route_after_analyze,
    route_after_fix,
    route_after_intake,
    route_after_triage,
    route_after_triage_test,
)


class TestRouteAfterIntake:
    """Tests for route_after_intake function (daily limit check)."""

    def test_limit_exceeded_goes_to_limit_exceeded(self):
        state = {"daily_limit_exceeded": True}
        assert route_after_intake(state) == "limit_exceeded"

    def test_limit_not_exceeded_continues(self):
        state = {"daily_limit_exceeded": False}
        assert route_after_intake(state) == "continue"

    def test_missing_limit_flag_continues(self):
        state = {}
        assert route_after_intake(state) == "continue"


class TestRouteAfterTriage:
    """Tests for route_after_triage function."""

    def test_valid_goes_to_analyze(self):
        state = {"triage_decision": "valid"}
        assert route_after_triage(state) == "analyze"

    def test_invalid_goes_to_apply_labels(self):
        state = {"triage_decision": "invalid"}
        assert route_after_triage(state) == "apply_labels"

    def test_duplicate_goes_to_apply_labels(self):
        state = {"triage_decision": "duplicate"}
        assert route_after_triage(state) == "apply_labels"

    def test_needs_info_goes_to_apply_labels(self):
        state = {"triage_decision": "needs_info"}
        assert route_after_triage(state) == "apply_labels"

    def test_unknown_goes_to_apply_labels(self):
        state = {"triage_decision": "unknown"}
        assert route_after_triage(state) == "apply_labels"

    def test_missing_decision_goes_to_apply_labels(self):
        state = {}
        assert route_after_triage(state) == "apply_labels"


class TestRouteAfterAnalyze:
    """Tests for route_after_analyze function."""

    def test_auto_eligible_with_fix_command_goes_to_fix(self):
        """auto_eligible + command=fix → fix (explicit approval)"""
        state = {"fix_decision": "auto_eligible", "command": "fix"}
        assert route_after_analyze(state) == "fix"

    def test_auto_eligible_without_fix_command_goes_to_post_comment(self):
        """auto_eligible without command=fix → post_comment (awaiting approval)"""
        state = {"fix_decision": "auto_eligible", "command": "run"}
        assert route_after_analyze(state) == "post_comment"

    def test_auto_eligible_with_no_command_goes_to_post_comment(self):
        """auto_eligible with no command → post_comment"""
        state = {"fix_decision": "auto_eligible"}
        assert route_after_analyze(state) == "post_comment"

    def test_manual_required_goes_to_post_comment(self):
        state = {"fix_decision": "manual_required"}
        assert route_after_analyze(state) == "post_comment"

    def test_comment_only_goes_to_post_comment(self):
        state = {"fix_decision": "comment_only"}
        assert route_after_analyze(state) == "post_comment"

    def test_unknown_goes_to_apply_labels(self):
        state = {"fix_decision": "unknown"}
        assert route_after_analyze(state) == "apply_labels"

    def test_missing_decision_goes_to_apply_labels(self):
        state = {}
        assert route_after_analyze(state) == "apply_labels"


class TestRouteAfterFix:
    """Tests for route_after_fix function."""

    def test_success_goes_to_apply_labels(self):
        state = {"fix_success": True}
        assert route_after_fix(state) == "apply_labels"

    def test_failure_goes_to_post_comment(self):
        state = {"fix_success": False}
        assert route_after_fix(state) == "post_comment"

    def test_missing_goes_to_post_comment(self):
        state = {}
        assert route_after_fix(state) == "post_comment"


class TestRouteAfterTriageTest:
    """Tests for route_after_triage_test function (test workflow)."""

    def test_valid_goes_to_analyze(self):
        state = {"triage_decision": "valid"}
        assert route_after_triage_test(state) == "analyze"

    def test_invalid_goes_to_end(self):
        state = {"triage_decision": "invalid"}
        assert route_after_triage_test(state) == "__end__"

    def test_duplicate_goes_to_end(self):
        state = {"triage_decision": "duplicate"}
        assert route_after_triage_test(state) == "__end__"

    def test_needs_info_goes_to_end(self):
        state = {"triage_decision": "needs_info"}
        assert route_after_triage_test(state) == "__end__"

    def test_missing_decision_goes_to_end(self):
        state = {}
        assert route_after_triage_test(state) == "__end__"
