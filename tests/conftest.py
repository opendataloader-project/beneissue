"""Pytest configuration and fixtures."""

import os
from pathlib import Path


def _load_env_file():
    """Load .env file from project root if it exists."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            # Parse KEY="VALUE" or KEY=VALUE
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # Remove surrounding quotes
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                # Only set if not already in environment
                if key not in os.environ:
                    os.environ[key] = value


# Load .env before tests run
_load_env_file()
