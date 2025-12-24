"""Tests for configuration loading."""

from pathlib import Path
from tempfile import TemporaryDirectory

from beneissue.config import (
    DEFAULT_ANALYZE_MODEL,
    DEFAULT_FIX_MODEL,
    DEFAULT_SCORE_THRESHOLD,
    DEFAULT_TRIAGE_MODEL,
    get_available_assignee,
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
            assert config.scoring.threshold == DEFAULT_SCORE_THRESHOLD

    def test_load_from_file(self):
        """Should load config from file."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".claude" / "skills" / "beneissue"
            config_dir.mkdir(parents=True)

            config_file = config_dir / "beneissue-config.yml"
            config_file.write_text("""
version: "1.0"
project:
  name: "test-project"
  description: "Test description"
models:
  triage: claude-sonnet-4
  analyze: claude-opus-4
scoring:
  threshold: 90
  criteria:
    scope: { weight: 25 }
    risk: { weight: 25 }
""")

            config = load_config(Path(tmpdir))

            assert config.project.name == "test-project"
            assert config.project.description == "Test description"
            assert config.models.triage == "claude-sonnet-4"
            assert config.models.analyze == "claude-opus-4"
            assert config.models.fix == DEFAULT_FIX_MODEL  # Not set in file
            assert config.scoring.threshold == 90
            assert config.scoring.criteria.scope == 25
            assert config.scoring.criteria.risk == 25

    def test_env_override(self, monkeypatch):
        """Environment variables should override config file."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".claude" / "skills" / "beneissue"
            config_dir.mkdir(parents=True)

            config_file = config_dir / "beneissue-config.yml"
            config_file.write_text("""
version: "1.0"
models:
  triage: claude-haiku-4-5
scoring:
  threshold: 80
""")

            # Set environment variable
            monkeypatch.setenv("BENEISSUE_MODEL_TRIAGE", "claude-sonnet-4")
            monkeypatch.setenv("BENEISSUE_SCORE_THRESHOLD", "75")

            config = load_config(Path(tmpdir))

            # Env should override file
            assert config.models.triage == "claude-sonnet-4"
            assert config.scoring.threshold == 75

    def test_minimal_config(self):
        """Should handle minimal config file."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".claude" / "skills" / "beneissue"
            config_dir.mkdir(parents=True)

            config_file = config_dir / "beneissue-config.yml"
            config_file.write_text("""
version: "1.0"
project:
  name: "minimal"
""")

            config = load_config(Path(tmpdir))

            assert config.project.name == "minimal"
            # Defaults should apply
            assert config.models.triage == DEFAULT_TRIAGE_MODEL

    def test_team_config(self):
        """Should parse team configuration."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".claude" / "skills" / "beneissue"
            config_dir.mkdir(parents=True)

            config_file = config_dir / "beneissue-config.yml"
            config_file.write_text("""
version: "1.0"
team:
  - github_id: "alice"
    available: true
    specialties: ["frontend", "react"]
  - github_id: "bob"
    available: false
    specialties: ["backend"]
  - github_id: ""
    available: true
""")

            config = load_config(Path(tmpdir))

            # Empty github_id should be filtered out
            assert len(config.team) == 2
            assert config.team[0].github_id == "alice"
            assert config.team[0].available is True
            assert config.team[0].specialties == ["frontend", "react"]
            assert config.team[1].github_id == "bob"
            assert config.team[1].available is False

    def test_labels_config(self):
        """Should parse labels configuration."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".claude" / "skills" / "beneissue"
            config_dir.mkdir(parents=True)

            config_file = config_dir / "beneissue-config.yml"
            config_file.write_text("""
version: "1.0"
labels:
  action:
    - name: "fix/auto-eligible"
      color: "0E8A16"
      description: "AI auto-fix eligible"
  priority:
    - name: "P0"
      color: "B60205"
""")

            config = load_config(Path(tmpdir))

            assert len(config.labels.action) == 1
            assert config.labels.action[0].name == "fix/auto-eligible"
            assert config.labels.action[0].color == "0E8A16"
            assert len(config.labels.priority) == 1
            assert config.labels.priority[0].name == "P0"


class TestGetAvailableAssignee:
    """Tests for get_available_assignee function."""

    def test_returns_available_member(self):
        """Should return first available member."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".claude" / "skills" / "beneissue"
            config_dir.mkdir(parents=True)

            config_file = config_dir / "beneissue-config.yml"
            config_file.write_text("""
version: "1.0"
team:
  - github_id: "alice"
    available: true
  - github_id: "bob"
    available: true
""")

            config = load_config(Path(tmpdir))
            assignee = get_available_assignee(config)

            assert assignee == "alice"

    def test_skips_unavailable_members(self):
        """Should skip unavailable members."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".claude" / "skills" / "beneissue"
            config_dir.mkdir(parents=True)

            config_file = config_dir / "beneissue-config.yml"
            config_file.write_text("""
version: "1.0"
team:
  - github_id: "alice"
    available: false
  - github_id: "bob"
    available: true
""")

            config = load_config(Path(tmpdir))
            assignee = get_available_assignee(config)

            assert assignee == "bob"

    def test_filters_by_specialty(self):
        """Should filter by specialty when provided."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".claude" / "skills" / "beneissue"
            config_dir.mkdir(parents=True)

            config_file = config_dir / "beneissue-config.yml"
            config_file.write_text("""
version: "1.0"
team:
  - github_id: "alice"
    available: true
    specialties: ["frontend"]
  - github_id: "bob"
    available: true
    specialties: ["backend", "python"]
""")

            config = load_config(Path(tmpdir))
            assignee = get_available_assignee(config, specialties=["backend"])

            assert assignee == "bob"

    def test_returns_none_when_no_match(self):
        """Should return None when no matching member."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".claude" / "skills" / "beneissue"
            config_dir.mkdir(parents=True)

            config_file = config_dir / "beneissue-config.yml"
            config_file.write_text("""
version: "1.0"
team:
  - github_id: "alice"
    available: false
""")

            config = load_config(Path(tmpdir))
            assignee = get_available_assignee(config)

            assert assignee is None

    def test_returns_none_when_no_team(self):
        """Should return None when no team configured."""
        with TemporaryDirectory() as tmpdir:
            config = load_config(Path(tmpdir))
            assignee = get_available_assignee(config)

            assert assignee is None
