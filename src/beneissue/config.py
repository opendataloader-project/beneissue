"""Configuration and LangSmith setup."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


# Default values
DEFAULT_TRIAGE_MODEL = "claude-haiku-4-5"
DEFAULT_ANALYZE_MODEL = "claude-sonnet-4"
DEFAULT_FIX_MODEL = "claude-sonnet-4"
DEFAULT_AUTO_FIX_MIN_SCORE = 80

# Daily limits (cost control)
DEFAULT_DAILY_LIMIT_TRIAGE = 20  # ~$0.02/call with Haiku
DEFAULT_DAILY_LIMIT_ANALYZE = 10  # ~$0.10-0.50/call with Sonnet
DEFAULT_DAILY_LIMIT_FIX = 3  # ~$1-5/call with Claude Code

# Config file path
CONFIG_PATH = ".claude/skills/beneissue/beneissue-config.yml"


@dataclass
class ModelsConfig:
    """Model configuration."""

    triage: str = DEFAULT_TRIAGE_MODEL
    analyze: str = DEFAULT_ANALYZE_MODEL
    fix: str = DEFAULT_FIX_MODEL


@dataclass
class AutoFixConfig:
    """Auto-fix policy configuration."""

    enabled: bool = True
    min_score: int = DEFAULT_AUTO_FIX_MIN_SCORE


@dataclass
class DailyLimitsConfig:
    """Daily rate limits for cost control."""

    triage: int = DEFAULT_DAILY_LIMIT_TRIAGE
    analyze: int = DEFAULT_DAILY_LIMIT_ANALYZE
    fix: int = DEFAULT_DAILY_LIMIT_FIX


@dataclass
class PolicyConfig:
    """Policy configuration."""

    auto_fix: AutoFixConfig = field(default_factory=AutoFixConfig)
    daily_limits: DailyLimitsConfig = field(default_factory=DailyLimitsConfig)


@dataclass
class ProjectConfig:
    """Project metadata."""

    name: str = ""
    description: str = ""


@dataclass
class BeneissueConfig:
    """Main configuration class."""

    version: str = "1.0"
    project: ProjectConfig = field(default_factory=ProjectConfig)
    models: ModelsConfig = field(default_factory=ModelsConfig)
    policy: PolicyConfig = field(default_factory=PolicyConfig)


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

        # Parse project
        if "project" in data:
            config.project.name = data["project"].get("name", "")
            config.project.description = data["project"].get("description", "")

        # Parse models
        if "models" in data:
            config.models.triage = data["models"].get("triage", DEFAULT_TRIAGE_MODEL)
            config.models.analyze = data["models"].get("analyze", DEFAULT_ANALYZE_MODEL)
            config.models.fix = data["models"].get("fix", DEFAULT_FIX_MODEL)

        # Parse policy
        if "policy" in data:
            if "auto_fix" in data["policy"]:
                auto_fix = data["policy"]["auto_fix"]
                config.policy.auto_fix.enabled = auto_fix.get("enabled", True)
                config.policy.auto_fix.min_score = auto_fix.get(
                    "min_score", DEFAULT_AUTO_FIX_MIN_SCORE
                )

            if "daily_limits" in data["policy"]:
                limits = data["policy"]["daily_limits"]
                config.policy.daily_limits.triage = limits.get(
                    "triage", DEFAULT_DAILY_LIMIT_TRIAGE
                )
                config.policy.daily_limits.analyze = limits.get(
                    "analyze", DEFAULT_DAILY_LIMIT_ANALYZE
                )
                config.policy.daily_limits.fix = limits.get(
                    "fix", DEFAULT_DAILY_LIMIT_FIX
                )

    # Override with environment variables
    if env_triage := os.environ.get("BENEISSUE_MODEL_TRIAGE"):
        config.models.triage = env_triage
    if env_analyze := os.environ.get("BENEISSUE_MODEL_ANALYZE"):
        config.models.analyze = env_analyze
    if env_fix := os.environ.get("BENEISSUE_MODEL_FIX"):
        config.models.fix = env_fix
    if env_min_score := os.environ.get("BENEISSUE_AUTO_FIX_MIN_SCORE"):
        config.policy.auto_fix.min_score = int(env_min_score)

    return config


def setup_langsmith() -> bool:
    """Configure LangSmith tracing if API key is available.

    Returns:
        True if LangSmith is enabled, False otherwise.
    """
    # Check if API key is set
    if not os.environ.get("LANGCHAIN_API_KEY"):
        # Disable tracing if no API key
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        return False

    # Enable tracing
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "beneissue")
    return True
