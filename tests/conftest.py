"""Pytest configuration and shared fixtures for beneissue tests."""

import json
import os
from pathlib import Path
from typing import Any

import pytest

# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"
CASES_DIR = FIXTURES_DIR / "cases"
MOCK_CODEBASE_DIR = FIXTURES_DIR / "mock-codebase"


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "ai: marks tests that require AI API calls (may be slow/costly)"
    )
    config.addinivalue_line(
        "markers", "triage: marks triage-related tests"
    )
    config.addinivalue_line(
        "markers", "analyze: marks analyze-related tests"
    )


def pytest_collection_modifyitems(config, items):
    """Skip AI tests unless --run-ai flag is passed."""
    if config.getoption("--run-ai", default=False):
        return

    skip_ai = pytest.mark.skip(reason="need --run-ai option to run AI tests")
    for item in items:
        if "ai" in item.keywords:
            item.add_marker(skip_ai)


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-ai",
        action="store_true",
        default=False,
        help="Run tests that require AI API calls",
    )
    parser.addoption(
        "--case",
        action="store",
        default=None,
        help="Run only test cases matching this pattern",
    )


# === Fixtures ===


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the fixtures directory path."""
    return FIXTURES_DIR


@pytest.fixture
def mock_codebase_dir() -> Path:
    """Return the mock codebase directory path."""
    return MOCK_CODEBASE_DIR


@pytest.fixture
def existing_issues() -> list[dict]:
    """Load existing issues fixture for duplicate detection."""
    issues_file = FIXTURES_DIR / "existing_issues.json"
    return json.loads(issues_file.read_text())


@pytest.fixture
def mock_readme() -> str:
    """Load mock README content."""
    readme_file = MOCK_CODEBASE_DIR / "README.md"
    return readme_file.read_text()


def load_test_cases(stage: str) -> list[dict[str, Any]]:
    """Load all test cases for a given stage."""
    cases_path = CASES_DIR / stage
    if not cases_path.exists():
        return []

    cases = []
    for case_file in sorted(cases_path.glob("*.json")):
        case_data = json.loads(case_file.read_text())
        case_data["_file"] = case_file.name
        cases.append(case_data)
    return cases


def get_triage_cases() -> list[dict[str, Any]]:
    """Get all triage test cases."""
    return load_test_cases("triage")


def get_analyze_cases() -> list[dict[str, Any]]:
    """Get all analyze test cases."""
    return load_test_cases("analyze")


@pytest.fixture
def triage_cases() -> list[dict[str, Any]]:
    """Return all triage test cases."""
    return get_triage_cases()


@pytest.fixture
def analyze_cases() -> list[dict[str, Any]]:
    """Return all analyze test cases."""
    return get_analyze_cases()


# === Base test state factory ===


@pytest.fixture
def make_issue_state(existing_issues):
    """Factory to create IssueState for testing."""

    def _make_state(
        title: str,
        body: str,
        repo: str = "test/mock-repo",
        issue_number: int = 999,
        labels: list[str] | None = None,
    ) -> dict:
        return {
            "repo": repo,
            "issue_number": issue_number,
            "issue_title": title,
            "issue_body": body,
            "issue_labels": labels or [],
            "issue_author": "test-user",
            "existing_issues": existing_issues,
        }

    return _make_state


# === API key check ===


@pytest.fixture
def require_anthropic_api_key():
    """Skip test if ANTHROPIC_API_KEY is not set."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")


# === Test result validators ===


class TriageResultValidator:
    """Validator for triage test results."""

    def __init__(self, expected: dict):
        self.expected = expected

    def validate(self, result: dict) -> tuple[bool, list[str]]:
        """Validate result against expected values. Returns (passed, errors)."""
        errors = []

        actual_decision = result.get("triage_decision")

        # Check decision - supports both exact match and acceptable_decisions list
        expected_decision = self.expected.get("decision")
        acceptable_decisions = self.expected.get("acceptable_decisions", [])

        if acceptable_decisions:
            # Flexible matching: any of the acceptable decisions
            if actual_decision not in acceptable_decisions:
                errors.append(
                    f"Decision mismatch: expected one of {acceptable_decisions}, got '{actual_decision}'"
                )
        elif expected_decision and actual_decision != expected_decision:
            errors.append(
                f"Decision mismatch: expected '{expected_decision}', got '{actual_decision}'"
            )

        # Check duplicate_of (only if expected and decision is duplicate)
        expected_dup = self.expected.get("duplicate_of")
        if expected_dup is not None and actual_decision == "duplicate":
            actual_dup = result.get("duplicate_of")
            if actual_dup != expected_dup:
                errors.append(
                    f"duplicate_of mismatch: expected {expected_dup}, got {actual_dup}"
                )

        # Check that reason mentions expected issue number (for duplicate detection)
        expected_mentions_issue = self.expected.get("reason_mentions_issue")
        if expected_mentions_issue:
            reason = result.get("triage_reason", "")
            if f"#{expected_mentions_issue}" not in reason:
                errors.append(
                    f"reason should mention issue #{expected_mentions_issue}"
                )

        return len(errors) == 0, errors


class AnalyzeResultValidator:
    """Validator for analyze test results."""

    def __init__(self, expected: dict):
        self.expected = expected

    def validate(self, result: dict) -> tuple[bool, list[str]]:
        """Validate result against expected values. Returns (passed, errors)."""
        errors = []

        actual_decision = result.get("fix_decision")

        # Check fix_decision - supports exact match or acceptable list
        expected_decision = self.expected.get("fix_decision")
        acceptable_decisions = self.expected.get("acceptable_decisions", [])

        if acceptable_decisions:
            if actual_decision not in acceptable_decisions:
                errors.append(
                    f"fix_decision mismatch: expected one of {acceptable_decisions}, got '{actual_decision}'"
                )
        elif expected_decision and actual_decision != expected_decision:
            errors.append(
                f"fix_decision mismatch: expected '{expected_decision}', got '{actual_decision}'"
            )

        # Check priority (in list)
        priority_in = self.expected.get("priority_in")
        if priority_in:
            actual_priority = result.get("priority")
            if actual_priority and actual_priority not in priority_in:
                errors.append(
                    f"priority mismatch: expected one of {priority_in}, got '{actual_priority}'"
                )

        # Check score bounds (only if score was successfully parsed)
        score = result.get("score", {})
        if score.get("total", 0) > 0:  # Only validate if score was parsed
            score_min = self.expected.get("score_min")
            if score_min is not None and score.get("total", 0) < score_min:
                errors.append(
                    f"score too low: expected >= {score_min}, got {score.get('total')}"
                )

            score_max = self.expected.get("score_max")
            if score_max is not None and score.get("total", 100) > score_max:
                errors.append(
                    f"score too high: expected <= {score_max}, got {score.get('total')}"
                )

        # Check that affected files were identified (for successful analysis)
        if self.expected.get("requires_affected_files", False):
            if not result.get("affected_files"):
                errors.append("expected affected_files to be identified")

        # Check summary contains keywords
        summary_contains = self.expected.get("summary_contains", [])
        summary = result.get("analysis_summary", "").lower()
        for keyword in summary_contains:
            if keyword.lower() not in summary:
                errors.append(f"summary should contain '{keyword}'")

        return len(errors) == 0, errors


@pytest.fixture
def triage_validator():
    """Factory for TriageResultValidator."""
    return lambda expected: TriageResultValidator(expected)


@pytest.fixture
def analyze_validator():
    """Factory for AnalyzeResultValidator."""
    return lambda expected: AnalyzeResultValidator(expected)
