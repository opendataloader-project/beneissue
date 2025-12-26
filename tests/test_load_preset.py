"""Tests for load_preset node."""

import pytest

from beneissue.nodes.load_preset import load_preset_node, DEFAULT_PROJECT_PATH


class TestLoadPresetNode:
    """Tests for load_preset_node function."""

    def test_loads_preset_successfully(self):
        """Test loading a valid preset."""
        config = {"configurable": {"preset_name": "analyze-auto-eligible-typo"}}
        result = load_preset_node({}, config)

        assert result["issue_title"] == "Typo in add.py: 'teh' should be 'the'"
        assert "typos in the docstring" in result["issue_body"]
        assert result["project_root"] == DEFAULT_PROJECT_PATH
        assert result["no_action"] is True
        assert result["repo"] == "test/calculator"
        assert result["issue_number"] == 0
        assert result["existing_issues"] == []

    def test_uses_default_when_no_preset_name(self):
        """Test default preset is used when preset_name is missing."""
        config = {"configurable": {}}
        result = load_preset_node({}, config)
        # Should use default: analyze-auto-eligible-typo
        assert result["issue_title"] == "Typo in add.py: 'teh' should be 'the'"

    def test_raises_error_when_preset_not_found(self):
        """Test error when preset file doesn't exist."""
        config = {"configurable": {"preset_name": "nonexistent-preset"}}
        with pytest.raises(FileNotFoundError, match="not found"):
            load_preset_node({}, config)

    def test_lists_available_presets_on_error(self):
        """Test that error message includes available presets."""
        config = {"configurable": {"preset_name": "nonexistent-preset"}}
        with pytest.raises(FileNotFoundError, match="Available presets"):
            load_preset_node({}, config)
