"""Claude Code SDK integration."""

import asyncio
import json
import re
from dataclasses import dataclass, field

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    query,
)


@dataclass
class UsageInfo:
    """Token and cost usage information."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    total_cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict:
        """Convert to dictionary for LangSmith usage_metadata."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost_usd,
            "ls_provider": "claude-code",
        }


@dataclass
class ClaudeCodeResult:
    """Result of a Claude Code execution."""

    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    error: str | None = None
    usage: UsageInfo = field(default_factory=UsageInfo)

    @property
    def success(self) -> bool:
        return self.returncode == 0 and not self.timed_out


# Default timeout for Claude Code execution (3 minutes)
DEFAULT_TIMEOUT = 180


async def run_claude_code_async(
    prompt: str,
    cwd: str,
    allowed_tools: list[str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    verbose: bool = False,
) -> ClaudeCodeResult:
    """Run Claude Code SDK with a prompt asynchronously.

    Args:
        prompt: The prompt to send to Claude Code
        cwd: Working directory (repository path)
        allowed_tools: List of allowed tools (e.g., ["Read", "Glob", "Grep"])
        timeout: Command timeout in seconds
        verbose: Enable verbose output (currently unused with SDK)

    Returns:
        ClaudeCodeResult with output, status, and usage info
    """
    if allowed_tools is None:
        allowed_tools = ["Read", "Glob", "Grep"]

    options = ClaudeAgentOptions(
        allowed_tools=allowed_tools,
        cwd=cwd,
        permission_mode="bypassPermissions",
        max_turns=50,
    )

    collected_output: list[str] = []
    usage_info = UsageInfo()

    try:
        async with asyncio.timeout(timeout):
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, ResultMessage):
                    # Extract result text
                    if message.result:
                        collected_output.append(message.result)

                    # Extract usage information
                    usage_info.total_cost_usd = message.total_cost_usd or 0.0

                    if message.usage:
                        usage_info.input_tokens = message.usage.get("input_tokens", 0)
                        usage_info.output_tokens = message.usage.get("output_tokens", 0)
                        usage_info.cache_creation_tokens = message.usage.get(
                            "cache_creation_input_tokens", 0
                        )
                        usage_info.cache_read_tokens = message.usage.get(
                            "cache_read_input_tokens", 0
                        )

        stdout = "\n".join(collected_output)
        return ClaudeCodeResult(
            returncode=0,
            stdout=stdout,
            stderr="",
            usage=usage_info,
        )

    except asyncio.TimeoutError:
        return ClaudeCodeResult(
            returncode=-1,
            stdout="",
            stderr="",
            timed_out=True,
            error=f"Timeout after {timeout} seconds",
        )
    except FileNotFoundError:
        return ClaudeCodeResult(
            returncode=-1,
            stdout="",
            stderr="",
            error="Claude Code CLI not found. Ensure it is installed.",
        )
    except Exception as e:
        return ClaudeCodeResult(
            returncode=-1,
            stdout="",
            stderr="",
            error=str(e)[:500],
        )


def run_claude_code(
    prompt: str,
    cwd: str,
    allowed_tools: list[str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    verbose: bool = False,
) -> ClaudeCodeResult:
    """Run Claude Code SDK with a prompt (sync wrapper).

    Args:
        prompt: The prompt to send to Claude Code
        cwd: Working directory (repository path)
        allowed_tools: List of allowed tools (e.g., ["Read", "Glob", "Grep"])
        timeout: Command timeout in seconds
        verbose: Enable verbose output

    Returns:
        ClaudeCodeResult with output, status, and usage info
    """
    return asyncio.run(
        run_claude_code_async(
            prompt=prompt,
            cwd=cwd,
            allowed_tools=allowed_tools,
            timeout=timeout,
            verbose=verbose,
        )
    )


def parse_json_from_output(output: str, required_key: str | None = None) -> dict | None:
    """Parse JSON from Claude Code output.

    Tries multiple strategies:
    1. Markdown code block with json
    2. Raw JSON object with required key
    3. Brace-matching for nested JSON

    Args:
        output: Claude Code stdout
        required_key: A key that must be present in the JSON (e.g., "summary", "success")

    Returns:
        Parsed dict or None if parsing fails
    """
    # Try markdown code block first
    json_match = re.search(r"```(?:json)?\s*\n?(\{.*\})\s*\n?```", output, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            if required_key is None or required_key in data:
                return data
        except json.JSONDecodeError:
            pass

    # Try to find JSON by brace matching
    for match in re.finditer(r"\{", output):
        start_idx = match.start()
        brace_count = 0
        end_idx = start_idx

        for i, char in enumerate(output[start_idx:], start=start_idx):
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break

        if end_idx > start_idx:
            candidate = output[start_idx:end_idx]
            if required_key is None or f'"{required_key}"' in candidate:
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue

    # Try parsing entire output as JSON
    try:
        data = json.loads(output)
        if required_key is None or required_key in data:
            return data
    except json.JSONDecodeError:
        pass

    return None
