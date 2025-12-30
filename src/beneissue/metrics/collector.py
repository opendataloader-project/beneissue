"""Metrics collector for workflow runs."""

import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from beneissue.graph.state import IssueState
from beneissue.metrics.schemas import WorkflowRunRecord
from beneissue.metrics.storage import get_storage

logger = logging.getLogger("beneissue.metrics")

StepType = Literal["triage", "analyze", "fix"]


class MetricsCollector:
    """Collects and stores workflow metrics."""

    def record_step(
        self, state: IssueState, step_type: StepType
    ) -> Optional[str]:
        """Record a completed step to storage.

        Args:
            state: Current workflow state after step completion
            step_type: Which step completed (triage, analyze, or fix)

        Returns:
            Record ID if saved successfully, None otherwise
        """
        storage = get_storage()
        if not storage.is_configured:
            logger.debug("Metrics storage not configured, skipping")
            return None

        record = self._state_to_record(state, step_type)
        return storage.save_run(record)

    def _state_to_record(
        self, state: IssueState, step_type: StepType
    ) -> WorkflowRunRecord:
        """Convert IssueState to WorkflowRunRecord for a specific step."""
        now = datetime.now(timezone.utc)

        return WorkflowRunRecord(
            # Identification
            repo=state.get("repo", ""),
            issue_number=state.get("issue_number", 0),
            workflow_type=step_type,
            # Timestamps
            issue_created_at=state.get("issue_created_at"),
            workflow_started_at=state.get("workflow_started_at", now),
            workflow_completed_at=now,
            # Triage results (only populated for triage step)
            triage_decision=state.get("triage_decision") if step_type == "triage" else None,
            triage_reason=state.get("triage_reason") if step_type == "triage" else None,
            duplicate_of=state.get("duplicate_of") if step_type == "triage" else None,
            # Analyze results (only populated for analyze step)
            fix_decision=state.get("fix_decision") if step_type == "analyze" else None,
            priority=state.get("priority") if step_type == "analyze" else None,
            story_points=state.get("story_points") if step_type == "analyze" else None,
            assignee=state.get("assignee") if step_type == "analyze" else None,
            # Fix results (only populated for fix step)
            fix_success=state.get("fix_success") if step_type == "fix" else None,
            pr_url=state.get("pr_url") if step_type == "fix" else None,
            fix_error=state.get("fix_error") if step_type == "fix" else None,
            # Token usage (extracted from usage_metadata)
            **self._extract_token_fields(state),
        )

    def _extract_token_fields(self, state: IssueState) -> dict:
        """Extract token fields from usage_metadata for DB storage."""
        usage = state.get("usage_metadata", {})
        result = {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        }
        logger.debug(
            "Extracted token fields: %s from usage_metadata: %s",
            result,
            usage if usage else "EMPTY",
        )
        return result


# Global instance
_collector: Optional[MetricsCollector] = None


def get_collector() -> MetricsCollector:
    """Get the global collector instance."""
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector


def _record_step(state: IssueState, step_type: StepType) -> dict:
    """Internal helper to record a step's metrics."""
    if state.get("dry_run"):
        logger.debug("Dry run mode, skipping metrics for %s", step_type)
        return {}

    usage = state.get("usage_metadata", {})
    logger.debug(
        "Recording %s metrics: in_tokens=%d, out_tokens=%d",
        step_type,
        usage.get("input_tokens", 0),
        usage.get("output_tokens", 0),
    )

    collector = get_collector()
    record_id = collector.record_step(state, step_type)

    if record_id:
        logger.info("Recorded %s metrics: %s", step_type, record_id)

    # Clear usage_metadata after recording so next step starts fresh
    return {"usage_metadata": {}}


def record_triage_metrics_node(state: IssueState) -> dict:
    """LangGraph node to record triage step metrics."""
    return _record_step(state, "triage")


def record_analyze_metrics_node(state: IssueState) -> dict:
    """LangGraph node to record analyze step metrics."""
    return _record_step(state, "analyze")


def record_fix_metrics_node(state: IssueState) -> dict:
    """LangGraph node to record fix step metrics."""
    return _record_step(state, "fix")
