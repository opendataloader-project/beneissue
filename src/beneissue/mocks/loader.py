"""Mock data loader for dry-run mode."""

import json
from pathlib import Path
from typing import Any, Literal

from beneissue.mocks.defaults import DEFAULT_ANALYZE, DEFAULT_FIX, DEFAULT_TRIAGE

DEFAULTS: dict[str, dict[str, Any]] = {
    "triage": DEFAULT_TRIAGE,
    "analyze": DEFAULT_ANALYZE,
    "fix": DEFAULT_FIX,
}


def load_mock(
    stage: Literal["triage", "analyze", "fix"],
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Load mock data for a given stage.

    Checks for user-defined mock file first, falls back to defaults.

    Args:
        stage: The workflow stage (triage, analyze, fix)
        project_root: Optional project root to look for custom mocks

    Returns:
        Mock data dictionary
    """
    # Check for user-defined mock file
    if project_root:
        mock_file = project_root / ".claude" / "skills" / "beneissue" / "mocks" / f"{stage}.json"
        if mock_file.exists():
            try:
                return json.loads(mock_file.read_text())
            except json.JSONDecodeError:
                pass  # Fall back to defaults

    return DEFAULTS.get(stage, {})
