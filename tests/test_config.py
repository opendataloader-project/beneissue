"""Tests for configuration loading."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from beneissue.config import (
    DEFAULT_ANALYZE_MODEL,
    DEFAULT_AUTO_FIX_MIN_SCORE,
    DEFAULT_FIX_MODEL,
    DEFAULT_TRIAGE_MODEL,
    BeneissueConfig,
    load_config,
)


class TestLoadConfig:
    """Tests for load_config function."""

    def test_defaults_when_no_config(self):
        """Should return defaults when no config file exists."""
        with TemporaryDirectory() as tmpdir:
            config = load_config(Path(tmpdir))

            assert config.models.triage == DEFAULT_TRIAGE_MODEL
            assert config.models.analyze == DEFAULT_ANALYZE_MODEL
            assert config.models.fix == DEFAULT_FIX_MODEL
            assert config.policy.auto_fix.enabled is True
            assert config.policy.auto_fix.min_score == DEFAULT_AUTO_FIX_MIN_SCORE

    def test_load_from_file(self):
        """Should load config from file."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".claude" / "skills" / "beneissue"
            config_dir.mkdir(parents=True)

            config_file = config_dir / "beneissue.yml"
            config_file.write_text("""
version: "1.0"
project:
  name: "test-project"
  description: "Test description"
models:
  triage: claude-sonnet-4
  analyze: claude-opus-4
policy:
  auto_fix:
    enabled: false
    min_score: 90
""")

            config = load_config(Path(tmpdir))

            assert config.project.name == "test-project"
            assert config.project.description == "Test description"
            assert config.models.triage == "claude-sonnet-4"
            assert config.models.analyze == "claude-opus-4"
            assert config.models.fix == DEFAULT_FIX_MODEL  # Not set in file
            assert config.policy.auto_fix.enabled is False
            assert config.policy.auto_fix.min_score == 90

    def test_env_override(self, monkeypatch):
        """Environment variables should override config file."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".claude" / "skills" / "beneissue"
            config_dir.mkdir(parents=True)

            config_file = config_dir / "beneissue.yml"
            config_file.write_text("""
version: "1.0"
models:
  triage: claude-haiku-4-5
""")

            # Set environment variable
            monkeypatch.setenv("BENEISSUE_MODEL_TRIAGE", "claude-sonnet-4")
            monkeypatch.setenv("BENEISSUE_AUTO_FIX_MIN_SCORE", "75")

            config = load_config(Path(tmpdir))

            # Env should override file
            assert config.models.triage == "claude-sonnet-4"
            assert config.policy.auto_fix.min_score == 75

    def test_minimal_config(self):
        """Should handle minimal config file."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".claude" / "skills" / "beneissue"
            config_dir.mkdir(parents=True)

            config_file = config_dir / "beneissue.yml"
            config_file.write_text("""
version: "1.0"
project:
  name: "minimal"
""")

            config = load_config(Path(tmpdir))

            assert config.project.name == "minimal"
            # Defaults should apply
            assert config.models.triage == DEFAULT_TRIAGE_MODEL
