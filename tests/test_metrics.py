"""Tests for metrics collection and storage."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from beneissue.metrics.collector import (
    MetricsCollector,
    record_analyze_metrics_node,
    record_fix_metrics_node,
    record_triage_metrics_node,
)
from beneissue.metrics.schemas import WorkflowRunRecord
from beneissue.metrics.storage import MetricsStorage


class TestWorkflowRunRecord:
    """Tests for WorkflowRunRecord schema."""

    def test_minimal_record(self):
        """Test creating a record with minimal fields."""
        record = WorkflowRunRecord(
            repo="owner/repo",
            issue_number=123,
            workflow_type="triage",
            workflow_started_at=datetime.now(timezone.utc),
            workflow_completed_at=datetime.now(timezone.utc),
        )
        assert record.repo == "owner/repo"
        assert record.issue_number == 123
        assert record.workflow_type == "triage"

    def test_triage_record_with_all_fields(self):
        """Test creating a triage record with all fields."""
        now = datetime.now(timezone.utc)
        record = WorkflowRunRecord(
            repo="owner/repo",
            issue_number=123,
            workflow_type="triage",
            issue_created_at=now,
            workflow_started_at=now,
            workflow_completed_at=now,
            triage_decision="valid",
            triage_reason="Valid bug report",
            duplicate_of=None,
            input_tokens=1000,
            output_tokens=500,
        )
        assert record.triage_decision == "valid"

    def test_fix_record_with_all_fields(self):
        """Test creating a fix record with all fields."""
        now = datetime.now(timezone.utc)
        record = WorkflowRunRecord(
            repo="owner/repo",
            issue_number=123,
            workflow_type="fix",
            issue_created_at=now,
            workflow_started_at=now,
            workflow_completed_at=now,
            fix_success=True,
            pr_url="https://github.com/owner/repo/pull/456",
            fix_error=None,
            input_tokens=5000,
            output_tokens=2000,
        )
        assert record.fix_success is True
        assert record.pr_url == "https://github.com/owner/repo/pull/456"

    def test_to_supabase_dict(self):
        """Test conversion to Supabase-compatible dict."""
        now = datetime.now(timezone.utc)
        record = WorkflowRunRecord(
            repo="owner/repo",
            issue_number=123,
            workflow_type="analyze",
            workflow_started_at=now,
            workflow_completed_at=now,
        )
        data = record.to_supabase_dict()

        assert data["repo"] == "owner/repo"
        assert data["issue_number"] == 123
        assert data["workflow_type"] == "analyze"
        # Timestamps should be ISO format strings
        assert isinstance(data["workflow_started_at"], str)
        assert isinstance(data["workflow_completed_at"], str)


class TestMetricsStorage:
    """Tests for MetricsStorage."""

    def test_is_configured_false_without_env(self):
        """Test is_configured returns False without env vars."""
        with patch.dict("os.environ", {}, clear=True):
            storage = MetricsStorage()
            assert storage.is_configured is False

    def test_is_configured_true_with_env(self):
        """Test is_configured returns True with env vars."""
        with patch.dict(
            "os.environ",
            {
                "SUPABASE_URL": "https://test.supabase.co",
                "SUPABASE_SERVICE_KEY": "test-key",
            },
        ):
            storage = MetricsStorage()
            assert storage.is_configured is True

    def test_client_returns_none_without_env(self):
        """Test client returns None without env vars."""
        with patch.dict("os.environ", {}, clear=True):
            storage = MetricsStorage()
            assert storage.client is None

    def test_save_run_skips_without_config(self):
        """Test save_run returns None without config."""
        with patch.dict("os.environ", {}, clear=True):
            storage = MetricsStorage()
            record = WorkflowRunRecord(
                repo="owner/repo",
                issue_number=123,
                workflow_type="triage",
                workflow_started_at=datetime.now(timezone.utc),
                workflow_completed_at=datetime.now(timezone.utc),
            )
            result = storage.save_run(record)
            assert result is None

    @patch("supabase.create_client")
    def test_save_run_success(self, mock_create_client):
        """Test successful save_run."""
        # Setup mock
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()

        mock_create_client.return_value = mock_client
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock(
            data=[{"id": "test-uuid-123"}]
        )

        with patch.dict(
            "os.environ",
            {
                "SUPABASE_URL": "https://test.supabase.co",
                "SUPABASE_SERVICE_KEY": "test-key",
            },
        ):
            storage = MetricsStorage()
            record = WorkflowRunRecord(
                repo="owner/repo",
                issue_number=123,
                workflow_type="triage",
                workflow_started_at=datetime.now(timezone.utc),
                workflow_completed_at=datetime.now(timezone.utc),
            )
            result = storage.save_run(record)

            assert result == "test-uuid-123"
            mock_client.table.assert_called_once_with("workflow_runs")


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    def test_state_to_record_triage(self):
        """Test conversion of IssueState to WorkflowRunRecord for triage step."""
        collector = MetricsCollector()
        now = datetime.now(timezone.utc)

        state = {
            "repo": "owner/repo",
            "issue_number": 123,
            "workflow_started_at": now,
            "triage_decision": "valid",
            "triage_reason": "Valid bug report",
            "usage_metadata": {
                "input_tokens": 1000,
                "output_tokens": 500,
                "total_tokens": 1500,
            },
        }

        record = collector._state_to_record(state, "triage")

        assert record.repo == "owner/repo"
        assert record.issue_number == 123
        assert record.workflow_type == "triage"
        assert record.triage_decision == "valid"
        assert record.input_tokens == 1000
        assert record.output_tokens == 500
        # Analyze/fix fields should be None for triage step
        assert record.fix_decision is None
        assert record.fix_success is None

    def test_state_to_record_analyze(self):
        """Test conversion of IssueState to WorkflowRunRecord for analyze step."""
        collector = MetricsCollector()
        now = datetime.now(timezone.utc)

        state = {
            "repo": "owner/repo",
            "issue_number": 123,
            "workflow_started_at": now,
            "triage_decision": "valid",  # From earlier triage step
            "fix_decision": "auto_eligible",
            "priority": "P1",
            "story_points": 2,
            "assignee": "dev1",
            "usage_metadata": {
                "input_tokens": 5000,
                "output_tokens": 1000,
            },
        }

        record = collector._state_to_record(state, "analyze")

        assert record.workflow_type == "analyze"
        assert record.fix_decision == "auto_eligible"
        assert record.priority == "P1"
        # Triage fields should be None for analyze step
        assert record.triage_decision is None
        # Fix fields should be None for analyze step
        assert record.fix_success is None

    def test_state_to_record_fix(self):
        """Test conversion of IssueState to WorkflowRunRecord for fix step."""
        collector = MetricsCollector()
        now = datetime.now(timezone.utc)

        state = {
            "repo": "owner/repo",
            "issue_number": 123,
            "workflow_started_at": now,
            "fix_success": True,
            "pr_url": "https://github.com/owner/repo/pull/456",
            "usage_metadata": {
                "input_tokens": 10000,
                "output_tokens": 3000,
            },
        }

        record = collector._state_to_record(state, "fix")

        assert record.workflow_type == "fix"
        assert record.fix_success is True
        assert record.pr_url == "https://github.com/owner/repo/pull/456"
        # Triage/analyze fields should be None for fix step
        assert record.triage_decision is None
        assert record.fix_decision is None


class TestRecordMetricsNodes:
    """Tests for step-level record metrics nodes."""

    def test_triage_skips_on_dry_run(self):
        """Test triage node skips recording on dry_run mode."""
        state = {"dry_run": True, "repo": "owner/repo", "issue_number": 123}
        result = record_triage_metrics_node(state)
        assert result == {}

    def test_analyze_skips_on_dry_run(self):
        """Test analyze node skips recording on dry_run mode."""
        state = {"dry_run": True, "repo": "owner/repo", "issue_number": 123}
        result = record_analyze_metrics_node(state)
        assert result == {}

    def test_fix_skips_on_dry_run(self):
        """Test fix node skips recording on dry_run mode."""
        state = {"dry_run": True, "repo": "owner/repo", "issue_number": 123}
        result = record_fix_metrics_node(state)
        assert result == {}

    def test_records_on_no_action(self):
        """Test node still records metrics on no_action mode (no_action only skips GitHub actions)."""
        with patch("beneissue.metrics.collector.get_collector") as mock_get_collector:
            mock_collector = MagicMock()
            mock_collector.record_step.return_value = "test-uuid"
            mock_get_collector.return_value = mock_collector

            state = {"no_action": True, "repo": "owner/repo", "issue_number": 123}
            result = record_triage_metrics_node(state)

            # Returns empty usage_metadata to clear for next step
            assert result == {"usage_metadata": {}}
            mock_collector.record_step.assert_called_once_with(state, "triage")

    @patch("beneissue.metrics.collector.get_collector")
    def test_records_triage_metrics(self, mock_get_collector):
        """Test triage node records metrics when configured."""
        mock_collector = MagicMock()
        mock_collector.record_step.return_value = "test-uuid"
        mock_get_collector.return_value = mock_collector

        state = {
            "repo": "owner/repo",
            "issue_number": 123,
            "triage_decision": "valid",
        }
        result = record_triage_metrics_node(state)

        assert result == {"usage_metadata": {}}
        mock_collector.record_step.assert_called_once_with(state, "triage")

    @patch("beneissue.metrics.collector.get_collector")
    def test_records_analyze_metrics(self, mock_get_collector):
        """Test analyze node records metrics when configured."""
        mock_collector = MagicMock()
        mock_collector.record_step.return_value = "test-uuid"
        mock_get_collector.return_value = mock_collector

        state = {
            "repo": "owner/repo",
            "issue_number": 123,
            "fix_decision": "auto_eligible",
        }
        result = record_analyze_metrics_node(state)

        assert result == {"usage_metadata": {}}
        mock_collector.record_step.assert_called_once_with(state, "analyze")

    @patch("beneissue.metrics.collector.get_collector")
    def test_records_fix_metrics(self, mock_get_collector):
        """Test fix node records metrics when configured."""
        mock_collector = MagicMock()
        mock_collector.record_step.return_value = "test-uuid"
        mock_get_collector.return_value = mock_collector

        state = {
            "repo": "owner/repo",
            "issue_number": 123,
            "fix_success": True,
        }
        result = record_fix_metrics_node(state)

        assert result == {"usage_metadata": {}}
        mock_collector.record_step.assert_called_once_with(state, "fix")


def _is_supabase_configured() -> bool:
    """Check if Supabase env vars are available."""
    import os

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get(
        "SUPABASE_SERVICE_ROLE_KEY"
    )
    return bool(url and key)


# Integration test marker - requires real Supabase
@pytest.mark.skipif(
    not _is_supabase_configured(),
    reason="Requires SUPABASE_URL and SUPABASE_SERVICE_KEY/SUPABASE_SERVICE_ROLE_KEY",
)
class TestMetricsIntegration:
    """Integration tests with real Supabase.

    To run these tests:
    1. Set SUPABASE_URL and SUPABASE_SERVICE_KEY (or SUPABASE_SERVICE_ROLE_KEY)
    2. Run: pytest tests/test_metrics.py::TestMetricsIntegration -v

    Or load from .env file:
        source .env && pytest tests/test_metrics.py::TestMetricsIntegration -v
    """

    def test_save_and_read_record(self):
        """Test saving and reading a record from Supabase."""
        from beneissue.metrics.storage import MetricsStorage

        # Create fresh storage instance to avoid cached state
        storage = MetricsStorage()
        assert storage.is_configured, "Supabase not configured"

        # Create test record
        now = datetime.now(timezone.utc)
        record = WorkflowRunRecord(
            repo="test/integration-test",
            issue_number=99999,
            workflow_type="triage",
            workflow_started_at=now,
            workflow_completed_at=now,
            triage_decision="valid",
            triage_reason="Integration test",
        )

        # Save
        record_id = storage.save_run(record)
        assert record_id is not None, "Failed to save record"

        # Read back
        result = (
            storage.client.table("workflow_runs")
            .select("*")
            .eq("id", record_id)
            .execute()
        )
        assert len(result.data) == 1
        assert result.data[0]["repo"] == "test/integration-test"
        assert result.data[0]["issue_number"] == 99999

        # Cleanup
        storage.client.table("workflow_runs").delete().eq(
            "id", record_id
        ).execute()
        print(f"Integration test passed. Record ID: {record_id}")
