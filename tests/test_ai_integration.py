"""AI Integration tests for triage and analyze nodes.

These tests verify that the AI agent produces consistent, expected results
for a fixed set of test cases against a mock codebase.

Run with: pytest tests/test_ai_integration.py --run-ai -v
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from beneissue.nodes.schemas import AnalyzeResult, TriageResult

from .conftest import (
    AnalyzeResultValidator,
    TriageResultValidator,
    get_analyze_cases,
    get_triage_cases,
)


# === Triage Tests ===


@pytest.mark.ai
@pytest.mark.triage
class TestTriageAI:
    """AI integration tests for triage node."""

    @pytest.fixture(autouse=True)
    def setup(self, require_anthropic_api_key, mock_readme, existing_issues):
        """Setup for triage tests."""
        self.mock_readme = mock_readme
        self.existing_issues = existing_issues

    @pytest.mark.parametrize(
        "case",
        get_triage_cases(),
        ids=lambda c: c.get("name", c.get("_file", "unknown")),
    )
    def test_triage_case(self, case, make_issue_state, triage_validator, mock_codebase_dir):
        """Test triage node against a test case."""
        from beneissue.nodes.triage import triage_node

        # Create state from case input
        input_data = case["input"]
        state = make_issue_state(
            title=input_data["title"],
            body=input_data["body"],
        )

        # Mock the README path to use mock codebase
        with patch("beneissue.nodes.triage.Path") as mock_path:
            # Make Path.cwd() / "README.md" return mock codebase readme
            mock_cwd = mock_path.cwd.return_value
            mock_readme_path = mock_cwd.__truediv__.return_value
            mock_readme_path.exists.return_value = True
            mock_readme_path.read_text.return_value = self.mock_readme

            # Run triage
            result = triage_node(state)

        # Validate result
        expected = case["expected"]
        validator = triage_validator(expected)
        passed, errors = validator.validate(result)

        # Report
        if not passed:
            pytest.fail(
                f"Test case '{case['name']}' failed:\n"
                f"  Input: {input_data['title']}\n"
                f"  Errors: {errors}\n"
                f"  Result: {result}"
            )


# === Analyze Tests ===


@pytest.mark.ai
@pytest.mark.analyze
class TestAnalyzeAI:
    """AI integration tests for analyze node."""

    @pytest.fixture(autouse=True)
    def setup(self, require_anthropic_api_key, mock_codebase_dir):
        """Setup for analyze tests."""
        self.mock_codebase_dir = mock_codebase_dir

    @pytest.mark.parametrize(
        "case",
        get_analyze_cases(),
        ids=lambda c: c.get("name", c.get("_file", "unknown")),
    )
    def test_analyze_case(self, case, make_issue_state, analyze_validator):
        """Test analyze node against a test case."""
        from beneissue.nodes.analyze import analyze_node, _clone_repo, _build_analyze_prompt

        # Create state from case input
        input_data = case["input"]
        state = make_issue_state(
            title=input_data["title"],
            body=input_data["body"],
        )

        # Mock _clone_repo to use mock codebase instead of actual clone
        def mock_clone(repo: str, target_dir: str) -> bool:
            """Copy mock codebase to target directory."""
            import shutil
            shutil.copytree(self.mock_codebase_dir, target_dir)
            return True

        with patch("beneissue.nodes.analyze._clone_repo", side_effect=mock_clone):
            result = analyze_node(state)

        # Validate result
        expected = case["expected"]
        validator = analyze_validator(expected)
        passed, errors = validator.validate(result)

        # Report
        if not passed:
            pytest.fail(
                f"Test case '{case['name']}' failed:\n"
                f"  Input: {input_data['title']}\n"
                f"  Errors: {errors}\n"
                f"  Result: {result}"
            )


# === Snapshot Tests ===


@pytest.mark.ai
class TestAISnapshot:
    """Snapshot tests to detect AI behavior drift.

    These tests save successful results and compare against them
    in future runs to detect unexpected changes in AI behavior.
    """

    SNAPSHOT_DIR = Path(__file__).parent / "snapshots"

    @pytest.fixture(autouse=True)
    def setup(self, require_anthropic_api_key):
        """Ensure snapshot directory exists."""
        self.SNAPSHOT_DIR.mkdir(exist_ok=True)

    def _get_snapshot_path(self, name: str) -> Path:
        """Get path for a named snapshot."""
        return self.SNAPSHOT_DIR / f"{name}.json"

    def _save_snapshot(self, name: str, data: dict):
        """Save a snapshot."""
        import json
        snapshot_path = self._get_snapshot_path(name)
        snapshot_path.write_text(json.dumps(data, indent=2))

    def _load_snapshot(self, name: str) -> dict | None:
        """Load a snapshot, or None if not exists."""
        import json
        snapshot_path = self._get_snapshot_path(name)
        if snapshot_path.exists():
            return json.loads(snapshot_path.read_text())
        return None

    @pytest.mark.parametrize(
        "case",
        get_triage_cases()[:3],  # Only test first 3 for snapshots
        ids=lambda c: c.get("name", "unknown"),
    )
    def test_triage_snapshot(self, case, make_issue_state, mock_readme, existing_issues, mock_codebase_dir):
        """Compare triage results against saved snapshots."""
        from beneissue.nodes.triage import triage_node

        input_data = case["input"]
        state = make_issue_state(
            title=input_data["title"],
            body=input_data["body"],
        )

        with patch("beneissue.nodes.triage.Path") as mock_path:
            mock_cwd = mock_path.cwd.return_value
            mock_readme_path = mock_cwd.__truediv__.return_value
            mock_readme_path.exists.return_value = True
            mock_readme_path.read_text.return_value = mock_readme

            result = triage_node(state)

        snapshot_name = f"triage_{case['name']}"
        existing_snapshot = self._load_snapshot(snapshot_name)

        if existing_snapshot is None:
            # First run - save snapshot
            self._save_snapshot(snapshot_name, result)
            pytest.skip(f"Snapshot created for {snapshot_name}")
        else:
            # Compare key fields (allow reason to vary)
            assert result["triage_decision"] == existing_snapshot["triage_decision"], (
                f"Decision changed from '{existing_snapshot['triage_decision']}' "
                f"to '{result['triage_decision']}'"
            )
            assert result.get("duplicate_of") == existing_snapshot.get("duplicate_of"), (
                f"duplicate_of changed from {existing_snapshot.get('duplicate_of')} "
                f"to {result.get('duplicate_of')}"
            )


# === Batch Test Runner ===


@pytest.mark.ai
class TestBatchRun:
    """Run all test cases in batch and produce a summary report."""

    def test_run_all_triage_cases(
        self, make_issue_state, triage_validator, mock_readme, existing_issues, mock_codebase_dir, capsys
    ):
        """Run all triage cases and report summary."""
        from beneissue.nodes.triage import triage_node

        cases = get_triage_cases()
        if not cases:
            pytest.skip("No triage test cases found")

        results = []
        for case in cases:
            input_data = case["input"]
            state = make_issue_state(
                title=input_data["title"],
                body=input_data["body"],
            )

            with patch("beneissue.nodes.triage.Path") as mock_path:
                mock_cwd = mock_path.cwd.return_value
                mock_readme_path = mock_cwd.__truediv__.return_value
                mock_readme_path.exists.return_value = True
                mock_readme_path.read_text.return_value = mock_readme

                try:
                    result = triage_node(state)
                    validator = triage_validator(case["expected"])
                    passed, errors = validator.validate(result)
                    results.append({
                        "name": case["name"],
                        "passed": passed,
                        "errors": errors,
                        "result": result,
                    })
                except Exception as e:
                    results.append({
                        "name": case["name"],
                        "passed": False,
                        "errors": [str(e)],
                        "result": None,
                    })

        # Print summary
        passed = sum(1 for r in results if r["passed"])
        total = len(results)

        print(f"\n{'=' * 50}")
        print(f"Triage Test Summary: {passed}/{total} passed")
        print(f"{'=' * 50}")

        for r in results:
            status = "PASS" if r["passed"] else "FAIL"
            print(f"  [{status}] {r['name']}")
            if not r["passed"]:
                for err in r["errors"]:
                    print(f"         - {err}")

        # Assert all passed
        assert passed == total, f"{total - passed} triage tests failed"

    def test_run_all_analyze_cases(
        self, make_issue_state, analyze_validator, mock_codebase_dir, capsys
    ):
        """Run all analyze cases and report summary."""
        from beneissue.nodes.analyze import analyze_node

        cases = get_analyze_cases()
        if not cases:
            pytest.skip("No analyze test cases found")

        def mock_clone(repo: str, target_dir: str) -> bool:
            import shutil
            shutil.copytree(mock_codebase_dir, target_dir)
            return True

        results = []
        for case in cases:
            input_data = case["input"]
            state = make_issue_state(
                title=input_data["title"],
                body=input_data["body"],
            )

            with patch("beneissue.nodes.analyze._clone_repo", side_effect=mock_clone):
                try:
                    result = analyze_node(state)
                    validator = analyze_validator(case["expected"])
                    passed, errors = validator.validate(result)
                    results.append({
                        "name": case["name"],
                        "passed": passed,
                        "errors": errors,
                        "result": result,
                    })
                except Exception as e:
                    results.append({
                        "name": case["name"],
                        "passed": False,
                        "errors": [str(e)],
                        "result": None,
                    })

        # Print summary
        passed = sum(1 for r in results if r["passed"])
        total = len(results)

        print(f"\n{'=' * 50}")
        print(f"Analyze Test Summary: {passed}/{total} passed")
        print(f"{'=' * 50}")

        for r in results:
            status = "PASS" if r["passed"] else "FAIL"
            print(f"  [{status}] {r['name']}")
            if not r["passed"]:
                for err in r["errors"]:
                    print(f"         - {err}")

        # Assert all passed
        assert passed == total, f"{total - passed} analyze tests failed"
