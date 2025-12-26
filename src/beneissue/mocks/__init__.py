"""Mock data module for dry-run mode."""

from beneissue.mocks.defaults import DEFAULT_ANALYZE, DEFAULT_FIX, DEFAULT_TRIAGE
from beneissue.mocks.loader import load_mock

__all__ = ["DEFAULT_TRIAGE", "DEFAULT_ANALYZE", "DEFAULT_FIX", "load_mock"]
