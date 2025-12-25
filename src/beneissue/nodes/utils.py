"""Utility functions for node implementations."""

from typing import TypeVar

from pydantic import BaseModel

from beneissue.integrations.claude_code import parse_json_from_output

T = TypeVar("T", bound=BaseModel)


def extract_repo_owner(repo: str) -> str | None:
    """Extract owner from repo string (owner/repo format).

    Args:
        repo: Repository in "owner/repo" format

    Returns:
        Owner string, or None if not parseable
    """
    if "/" in repo:
        return repo.split("/")[0]
    return None


def parse_result(output: str, schema: type[T], required_key: str) -> T | None:
    """Parse Claude Code output into a Pydantic schema.

    Args:
        output: Raw output from Claude Code
        schema: Pydantic model class to parse into
        required_key: Key that must be present in JSON for validation

    Returns:
        Parsed schema instance, or None if parsing fails
    """
    data = parse_json_from_output(output, required_key=required_key)
    if data:
        try:
            return schema(**data)
        except (ValueError, TypeError):
            pass
    return None
