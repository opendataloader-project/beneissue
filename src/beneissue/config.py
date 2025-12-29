"""Configuration and LangSmith setup."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


def setup_logging() -> None:
    """Configure logging for beneissue.

    Log level is determined by BENEISSUE_LOG_LEVEL environment variable.
    Defaults to DEBUG for detailed logging during early development.

    Supported levels: DEBUG, INFO, WARNING, ERROR
    """
    level_name = os.environ.get("BENEISSUE_LOG_LEVEL", "DEBUG").upper()
    level = getattr(logging, level_name, logging.DEBUG)

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Also set for beneissue namespace specifically
    logging.getLogger("beneissue").setLevel(level)


# Default values
DEFAULT_TRIAGE_MODEL = "claude-haiku-4-5"
DEFAULT_CLAUDE_CODE_MODEL = "claude-sonnet-4-5"
DEFAULT_SCORE_THRESHOLD = 80

# Daily limits (cost control)
DEFAULT_DAILY_LIMIT_TRIAGE = 50
DEFAULT_DAILY_LIMIT_ANALYZE = 20
DEFAULT_DAILY_LIMIT_FIX = 5

# Config file path
CONFIG_PATH = ".claude/skills/beneissue/beneissue-config.yml"


@dataclass
class ScoringCriteria:
    """Scoring criteria weights."""

    scope: int = 30
    risk: int = 30
    verifiability: int = 25
    clarity: int = 15


@dataclass
class ScoringConfig:
    """Auto-fix scoring configuration."""

    threshold: int = DEFAULT_SCORE_THRESHOLD
    criteria: ScoringCriteria = field(default_factory=ScoringCriteria)


@dataclass
class TeamMember:
    """Team member for assignee recommendation."""

    github_id: str = ""
    available: bool = True
    specialties: list[str] = field(default_factory=list)


@dataclass
class DailyLimitsConfig:
    """Daily rate limits for cost control."""

    triage: int = DEFAULT_DAILY_LIMIT_TRIAGE
    analyze: int = DEFAULT_DAILY_LIMIT_ANALYZE
    fix: int = DEFAULT_DAILY_LIMIT_FIX


# Default LangSmith project name (used when LANGCHAIN_PROJECT env var is not set)
DEFAULT_LANGSMITH_PROJECT = "beneissue"


@dataclass
class LabelDef:
    """Label definition."""

    name: str
    color: str = ""
    description: str = ""


@dataclass
class LabelsConfig:
    """Labels configuration."""

    action: list[LabelDef] = field(default_factory=list)
    triage: list[LabelDef] = field(default_factory=list)
    type: list[LabelDef] = field(default_factory=list)
    priority: list[LabelDef] = field(default_factory=list)
    story_points: list[LabelDef] = field(default_factory=list)
    contribution: list[LabelDef] = field(default_factory=list)


@dataclass
class LimitsConfig:
    """Limits configuration."""

    daily: DailyLimitsConfig = field(default_factory=DailyLimitsConfig)


@dataclass
class BeneissueConfig:
    """Main configuration class."""

    version: str = "1.0"
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    team: list[TeamMember] = field(default_factory=list)
    limits: LimitsConfig = field(default_factory=LimitsConfig)
    labels: LabelsConfig = field(default_factory=LabelsConfig)


def _parse_team(data: list[dict]) -> list[TeamMember]:
    """Parse team configuration."""
    team = []
    for member in data:
        if member.get("github_id"):  # Skip empty entries
            team.append(
                TeamMember(
                    github_id=member.get("github_id", ""),
                    available=member.get("available", True),
                    specialties=member.get("specialties", []),
                )
            )
    return team


def _parse_labels(data: list[dict]) -> list[LabelDef]:
    """Parse label definitions."""
    return [
        LabelDef(
            name=label.get("name", ""),
            color=label.get("color", ""),
            description=label.get("description", ""),
        )
        for label in data
        if label.get("name")
    ]


def load_config(repo_path: Optional[Path] = None) -> BeneissueConfig:
    """Load beneissue configuration.

    Priority (highest to lowest):
    1. Environment variables (BENEISSUE_MODEL_TRIAGE, etc.)
    2. Repo config file (.claude/skills/beneissue/beneissue-config.yml)
    3. Package defaults

    Args:
        repo_path: Path to repository root. Defaults to current directory.

    Returns:
        BeneissueConfig instance
    """
    config = BeneissueConfig()

    # Load from config file if exists
    if repo_path is None:
        repo_path = Path.cwd()

    config_file = repo_path / CONFIG_PATH
    if config_file.exists():
        with open(config_file) as f:
            data = yaml.safe_load(f) or {}

        # Parse scoring
        if "scoring" in data:
            config.scoring.threshold = data["scoring"].get(
                "threshold", DEFAULT_SCORE_THRESHOLD
            )
            if "criteria" in data["scoring"]:
                criteria = data["scoring"]["criteria"]
                config.scoring.criteria.scope = criteria.get("scope", {}).get(
                    "weight", 30
                )
                config.scoring.criteria.risk = criteria.get("risk", {}).get(
                    "weight", 30
                )
                config.scoring.criteria.verifiability = criteria.get(
                    "verifiability", {}
                ).get("weight", 25)
                config.scoring.criteria.clarity = criteria.get("clarity", {}).get(
                    "weight", 15
                )

        # Parse team
        if "team" in data and isinstance(data["team"], list):
            config.team = _parse_team(data["team"])

        # Parse limits
        if "limits" in data and "daily" in data["limits"]:
            daily = data["limits"]["daily"]
            config.limits.daily.triage = daily.get("triage", DEFAULT_DAILY_LIMIT_TRIAGE)
            config.limits.daily.analyze = daily.get(
                "analyze", DEFAULT_DAILY_LIMIT_ANALYZE
            )
            config.limits.daily.fix = daily.get("fix", DEFAULT_DAILY_LIMIT_FIX)

        # Parse labels
        if "labels" in data:
            labels_data = data["labels"]
            if "action" in labels_data:
                config.labels.action = _parse_labels(labels_data["action"])
            if "triage" in labels_data:
                config.labels.triage = _parse_labels(labels_data["triage"])
            if "type" in labels_data:
                config.labels.type = _parse_labels(labels_data["type"])
            if "priority" in labels_data:
                config.labels.priority = _parse_labels(labels_data["priority"])
            if "story_points" in labels_data:
                config.labels.story_points = _parse_labels(labels_data["story_points"])
            if "contribution" in labels_data:
                config.labels.contribution = _parse_labels(labels_data["contribution"])

    # Override with environment variables
    if env_threshold := os.environ.get("BENEISSUE_SCORE_THRESHOLD"):
        config.scoring.threshold = int(env_threshold)

    return config


def get_available_assignee(
    config: BeneissueConfig, specialties: list[str] | None = None
) -> str | None:
    """Get an available team member for assignment.

    Args:
        config: Beneissue configuration
        specialties: Optional list of required specialties

    Returns:
        GitHub ID of available member, or None if no match
    """
    for member in config.team:
        if not member.available:
            continue
        if not member.github_id:
            continue
        if specialties:
            # Check if member has any matching specialty
            if not any(s in member.specialties for s in specialties):
                continue
        return member.github_id
    return None


def setup_langsmith() -> bool:
    """Configure LangSmith tracing if API key is available.

    LangSmith project name is determined by:
    1. LANGCHAIN_PROJECT environment variable (if set)
    2. Default: "beneissue"

    Returns:
        True if LangSmith is enabled, False otherwise.
    """
    # Check if API key is set
    if not os.environ.get("LANGCHAIN_API_KEY"):
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        return False

    # Enable tracing with defaults
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", DEFAULT_LANGSMITH_PROJECT)
    return True
