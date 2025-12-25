"""Prompt loading utilities."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

PROMPTS_DIR = Path(__file__).parent

PromptName = Literal["triage", "analyze", "fix"]


@lru_cache(maxsize=None)
def load_prompt(name: PromptName) -> str:
    """Load a prompt template by name.

    Args:
        name: Name of the prompt (triage, analyze, or fix)

    Returns:
        Prompt template content as string

    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    prompt_path = PROMPTS_DIR / f"{name}.md"
    return prompt_path.read_text()
