"""Supabase storage for metrics."""

import logging
import os
from typing import Optional

from beneissue.metrics.schemas import WorkflowRunRecord

logger = logging.getLogger("beneissue.metrics")


class MetricsStorage:
    """Supabase storage for workflow metrics."""

    def __init__(self) -> None:
        self._client = None

    @property
    def client(self):
        """Lazy-load Supabase client."""
        if self._client is None:
            url = os.environ.get("SUPABASE_URL")
            # Support both naming conventions
            key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get(
                "SUPABASE_SERVICE_ROLE_KEY"
            )

            if not url or not key:
                logger.warning(
                    "SUPABASE_URL or SUPABASE_SERVICE_KEY not set, metrics disabled"
                )
                return None

            from supabase import ClientOptions, create_client

            # Support SSL verification bypass for corporate proxies
            ssl_verify = os.environ.get("SUPABASE_SSL_VERIFY", "true").lower()
            if ssl_verify in ("false", "0", "no"):
                import httpx

                options = ClientOptions(httpx_client=httpx.Client(verify=False))
                self._client = create_client(url, key, options=options)
            else:
                self._client = create_client(url, key)

        return self._client

    def save_run(self, record: WorkflowRunRecord) -> Optional[str]:
        """Save a workflow run record.

        Returns the record ID if successful, None otherwise.
        """
        if self.client is None:
            logger.debug("Metrics storage not configured, skipping save")
            return None

        try:
            supabase_dict = record.to_supabase_dict()
            logger.debug(
                "Inserting record with tokens: in=%d, out=%d",
                supabase_dict.get("input_tokens", 0),
                supabase_dict.get("output_tokens", 0),
            )
            result = (
                self.client.table("workflow_runs")
                .insert(supabase_dict)
                .execute()
            )
            record_id = result.data[0]["id"] if result.data else None
            logger.info(f"Saved workflow run: {record_id}")
            return record_id
        except Exception as e:
            logger.error(f"Failed to save workflow run: {e}")
            return None

    @property
    def is_configured(self) -> bool:
        """Check if storage is configured."""
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get(
            "SUPABASE_SERVICE_ROLE_KEY"
        )
        # Check for non-empty values (not just not None)
        return bool(url) and bool(key)


# Global instance
_storage: Optional[MetricsStorage] = None


def get_storage() -> MetricsStorage:
    """Get the global storage instance."""
    global _storage
    if _storage is None:
        _storage = MetricsStorage()
    return _storage
