"""Load preset node for test workflows."""

import json
from pathlib import Path

from langchain_core.runnables import RunnableConfig

from beneissue.graph.state import IssueState

# Default project path for testing
DEFAULT_PROJECT_PATH = Path(__file__).parent.parent.parent.parent / "examples" / "calculator"


def load_preset_node(state: IssueState, config: RunnableConfig) -> IssueState:
    """Load preset from JSON file based on configurable preset_name.

    Reads preset_name from config["configurable"]["preset_name"] and loads
    the corresponding JSON file from the test cases directory.

    Args:
        state: Current workflow state (usually empty for test workflows).
        config: RunnableConfig containing configurable parameters.

    Returns:
        Updated state with issue_title, issue_body, project_root, and no_action set.

    Raises:
        ValueError: If preset_name is not provided in configurable.
        FileNotFoundError: If preset JSON file doesn't exist.
    """
    configurable = config.get("configurable", {})
    # Default to analyze-auto-eligible-typo if not specified
    preset_name = configurable.get("preset_name", "analyze-auto-eligible-typo")

    # Build path to preset JSON file
    project_root = DEFAULT_PROJECT_PATH
    preset_path = (
        project_root
        / ".claude"
        / "skills"
        / "beneissue"
        / "tests"
        / "cases"
        / f"{preset_name}.json"
    )

    if not preset_path.exists():
        available = list(preset_path.parent.glob("*.json"))
        available_names = [f.stem for f in available]
        raise FileNotFoundError(
            f"Preset '{preset_name}' not found at {preset_path}. "
            f"Available presets: {available_names}"
        )

    # Load preset JSON
    with open(preset_path) as f:
        preset_data = json.load(f)

    # Extract input data
    input_data = preset_data.get("input", {})
    issue_title = input_data.get("title", "")
    issue_body = input_data.get("body", "")

    return {
        "issue_title": issue_title,
        "issue_body": issue_body,
        "project_root": project_root,
        "no_action": True,  # Skip GitHub actions for testing
        "repo": "test/calculator",  # Dummy repo for testing
        "issue_number": 0,  # Dummy issue number
        "existing_issues": [],  # No existing issues for duplicate check
    }
