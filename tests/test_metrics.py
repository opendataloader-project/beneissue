"""Tests for metrics collection and storage."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from beneissue.metrics.collector import MetricsCollector, record_metrics_node
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

    def test_full_record(self):
        """Test creating a record with all fields."""
        now = datetime.now(timezone.utc)
        record = WorkflowRunRecord(
            repo="owner/repo",
            issue_number=123,
            workflow_type="full",
            issue_created_at=now,
            workflow_started_at=now,
            workflow_completed_at=now,
            triage_decision="valid",
            triage_reason="Valid bug report",
            duplicate_of=None,
            fix_decision="auto_eligible",
            priority="P1",
            story_points=2,
            assignee="dev1",
            fix_success=True,
            pr_url="https://github.com/owner/repo/pull/456",
            fix_error=None,
            input_tokens=1000,
            output_tokens=500,
            input_cost=0.003,
            output_cost=0.025,
        )
        assert record.triage_decision == "valid"
        assert record.fix_success is True
        assert record.input_cost == pytest.approx(0.003)
        assert record.output_cost == pytest.approx(0.025)

    def test_to_supabase_dict(self):
        """Test conversion to Supabase-compatible dict."""
        now = datetime.now(timezone.utc)
        record = WorkflowRunRecord(
            repo="owner/repo",
            issue_number=123,
            workflow_type="analyze",
            workflow_started_at=now,
            workflow_completed_at=now,
            input_cost=0.003,
            output_cost=0.025,
        )
        data = record.to_supabase_dict()

        assert data["repo"] == "owner/repo"
        assert data["issue_number"] == 123
        assert data["workflow_type"] == "analyze"
        # Costs should be floats
        assert isinstance(data["input_cost"], float)
        assert isinstance(data["output_cost"], float)
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

    def test_detect_workflow_type_from_command(self):
        """Test workflow type detection from command field."""
        collector = MetricsCollector()

        state = {"command": "triage"}
        assert collector._detect_workflow_type(state) == "triage"

        state = {"command": "analyze"}
        assert collector._detect_workflow_type(state) == "analyze"

        state = {"command": "fix"}
        assert collector._detect_workflow_type(state) == "fix"

    def test_detect_workflow_type_from_state(self):
        """Test workflow type detection from state contents."""
        collector = MetricsCollector()

        # Triage only
        state = {"triage_decision": "valid"}
        assert collector._detect_workflow_type(state) == "triage"

        # Analyze (has fix_decision)
        state = {"triage_decision": "valid", "fix_decision": "auto_eligible"}
        assert collector._detect_workflow_type(state) == "analyze"

        # Fix only
        state = {"fix_success": True}
        assert collector._detect_workflow_type(state) == "fix"

        # Full (all present)
        state = {
            "triage_decision": "valid",
            "fix_decision": "auto_eligible",
            "fix_success": True,
        }
        assert collector._detect_workflow_type(state) == "full"

    def test_state_to_record(self):
        """Test conversion of IssueState to WorkflowRunRecord."""
        collector = MetricsCollector()
        now = datetime.now(timezone.utc)

        state = {
            "repo": "owner/repo",
            "issue_number": 123,
            "command": "triage",
            "workflow_started_at": now,
            "triage_decision": "valid",
            "triage_reason": "Valid bug report",
            "usage_metadata": {
                "input_tokens": 1000,
                "output_tokens": 500,
                "total_tokens": 1500,
                "input_cost": 0.003,
                "output_cost": 0.025,
            },
        }

        record = collector._state_to_record(state)

        assert record.repo == "owner/repo"
        assert record.issue_number == 123
        assert record.workflow_type == "triage"
        assert record.triage_decision == "valid"
        assert record.input_tokens == 1000
        assert record.output_tokens == 500
        assert record.input_cost == pytest.approx(0.003)
        assert record.output_cost == pytest.approx(0.025)


class TestRecordMetricsNode:
    """Tests for record_metrics_node LangGraph node."""

    def test_skips_on_dry_run(self):
        """Test node skips recording on dry_run mode."""
        state = {"dry_run": True, "repo": "owner/repo", "issue_number": 123}
        result = record_metrics_node(state)
        assert result == {}

    def test_records_on_no_action(self):
        """Test node still records metrics on no_action mode (no_action only skips GitHub actions)."""
        with patch("beneissue.metrics.collector.get_collector") as mock_get_collector:
            mock_collector = MagicMock()
            mock_collector.record_workflow.return_value = "test-uuid"
            mock_get_collector.return_value = mock_collector

            state = {"no_action": True, "repo": "owner/repo", "issue_number": 123}
            result = record_metrics_node(state)

            assert result == {}
            mock_collector.record_workflow.assert_called_once_with(state)

    @patch("beneissue.metrics.collector.get_collector")
    def test_records_metrics(self, mock_get_collector):
        """Test node records metrics when configured."""
        mock_collector = MagicMock()
        mock_collector.record_workflow.return_value = "test-uuid"
        mock_get_collector.return_value = mock_collector

        state = {
            "repo": "owner/repo",
            "issue_number": 123,
            "triage_decision": "valid",
        }
        result = record_metrics_node(state)

        assert result == {}
        mock_collector.record_workflow.assert_called_once_with(state)


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
