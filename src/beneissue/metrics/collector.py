"""Metrics collector for workflow runs."""

import logging
from datetime import datetime, timezone
from typing import Optional

from beneissue.graph.state import IssueState
from beneissue.metrics.schemas import WorkflowRunRecord
from beneissue.metrics.storage import get_storage

logger = logging.getLogger("beneissue.metrics")


class MetricsCollector:
    """Collects and stores workflow metrics."""

    def record_workflow(self, state: IssueState) -> Optional[str]:
        """Record a completed workflow run to storage.

        Args:
            state: Final workflow state after completion

        Returns:
            Record ID if saved successfully, None otherwise
        """
        storage = get_storage()
        if not storage.is_configured:
            logger.debug("Metrics storage not configured, skipping")
            return None

        record = self._state_to_record(state)
        return storage.save_run(record)

    def _state_to_record(self, state: IssueState) -> WorkflowRunRecord:
        """Convert IssueState to WorkflowRunRecord."""
        now = datetime.now(timezone.utc)

        # Detect workflow type from state
        workflow_type = self._detect_workflow_type(state)

        return WorkflowRunRecord(
            # Identification
            repo=state.get("repo", ""),
            issue_number=state.get("issue_number", 0),
            workflow_type=workflow_type,
            # Timestamps
            issue_created_at=state.get("issue_created_at"),
            workflow_started_at=state.get("workflow_started_at", now),
            workflow_completed_at=now,
            # Triage results
            triage_decision=state.get("triage_decision"),
            triage_reason=state.get("triage_reason"),
            duplicate_of=state.get("duplicate_of"),
            # Analyze results
            fix_decision=state.get("fix_decision"),
            priority=state.get("priority"),
            story_points=state.get("story_points"),
            assignee=state.get("assignee"),
            # Fix results
            fix_success=state.get("fix_success"),
            pr_url=state.get("pr_url"),
            fix_error=state.get("fix_error"),
            # Token usage (directly from state)
            input_tokens=state.get("input_tokens", 0),
            output_tokens=state.get("output_tokens", 0),
            input_cost=state.get("input_cost", 0.0),
            output_cost=state.get("output_cost", 0.0),
        )

    def _detect_workflow_type(self, state: IssueState) -> str:
        """Detect workflow type from state contents."""
        command = state.get("command")
        if command and command != "run":
            return command

        # Infer from what results are present
        has_triage = state.get("triage_decision") is not None
        has_analyze = state.get("fix_decision") is not None
        has_fix = state.get("fix_success") is not None

        if has_triage and has_analyze and has_fix:
            return "full"
        elif has_fix:
            return "fix"
        elif has_analyze:
            return "analyze"
        return "triage"


# Global instance
_collector: Optional[MetricsCollector] = None


def get_collector() -> MetricsCollector:
    """Get the global collector instance."""
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector


def record_metrics_node(state: IssueState) -> dict:
    """LangGraph node to record workflow metrics.

    This node should be added before END in workflow graphs.
    """
    # Skip if dry run mode (no_action still records metrics)
    if state.get("dry_run"):
        logger.debug("Dry run mode, skipping metrics")
        return {}

    collector = get_collector()
    record_id = collector.record_workflow(state)

    if record_id:
        logger.info(f"Recorded metrics: {record_id}")

    return {}
