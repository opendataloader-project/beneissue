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

from beneissue.config import DEFAULT_CLAUDE_CODE_MODEL

def estimate_cost_split(
    total_cost_usd: float, input_tokens: int, output_tokens: int
) -> tuple[float, float]:
    """Estimate input/output cost split from total cost.

    Claude Code SDK only provides total_cost, so we estimate the split
    based on Anthropic's typical pricing ratio (~5:1 output:input for Sonnet).

    Formula: total = input_tokens * P_in + output_tokens * P_out
    With P_out = 5 * P_in: total = P_in * (input_tokens + 5 * output_tokens)

    Args:
        total_cost_usd: Total cost from Claude Code SDK
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Tuple of (input_cost_usd, output_cost_usd)
    """
    total_weighted = input_tokens + 5 * output_tokens
    if total_weighted > 0 and total_cost_usd > 0:
        cost_per_weighted = total_cost_usd / total_weighted
        input_cost = input_tokens * cost_per_weighted
        output_cost = output_tokens * 5 * cost_per_weighted
    else:
        input_cost = 0.0
        output_cost = 0.0
    return input_cost, output_cost


@dataclass
class UsageInfo:
    """Token and cost usage information."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    model: str = ""

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def total_cost_usd(self) -> float:
        return self.input_cost_usd + self.output_cost_usd

    def to_dict(self) -> dict:
        """Convert to dictionary for internal use."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "total_tokens": self.total_tokens,
            "input_cost": self.input_cost_usd,
            "output_cost": self.output_cost_usd,
            "model": self.model,
        }

    def to_langsmith_metadata(self) -> dict:
        """Convert to LangSmith usage_metadata format for token tracking.

        LangSmith expects input_cost/output_cost for proper cost attribution.
        Without these, costs appear as "Other" in the dashboard.

        Note: Only includes keys allowed by LangSmith's validate_extracted_usage_metadata:
        input_tokens, output_tokens, total_tokens, input_cost, output_cost, total_cost,
        input_token_details, output_token_details, input_cost_details, output_cost_details.
        """
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "input_cost": self.input_cost_usd,
            "output_cost": self.output_cost_usd,
        }

    def log_summary(self, logger) -> None:
        """Log usage summary."""
        logger.info(
            "Claude Code usage: in=%d out=%d tokens, in=$%.4f out=$%.4f",
            self.input_tokens,
            self.output_tokens,
            self.input_cost_usd,
            self.output_cost_usd,
        )

    def with_metadata(self, result: dict) -> dict:
        """Add usage_metadata to a result dict and return it."""
        result["usage_metadata"] = self.to_langsmith_metadata()
        return result

    def to_state_dict(self) -> dict:
        """Convert to IssueState usage_metadata for DB storage and LangSmith tracking."""
        return {"usage_metadata": self.to_langsmith_metadata()}

    def with_state(self, result: dict) -> dict:
        """Add usage_metadata to a result dict and return it.

        DEPRECATED: This method previously called set_on_run_tree() which caused
        cost duplication in LangSmith. Use to_state_dict() directly instead:
            return {**result, **usage.to_state_dict()}
        """
        # NOTE: Do NOT call set_on_run_tree() - it causes cost duplication
        # LangSmith automatically aggregates child costs to parent spans
        return {**result, **self.to_state_dict()}

    def set_on_run_tree(self) -> None:
        """Set usage metadata directly on the current LangSmith run tree.

        DEPRECATED: Do not use this method - it causes cost duplication in LangSmith.
        LangSmith automatically aggregates child span costs to parent spans.
        When you set usage on a run_type="llm" span that's wrapped by chain spans,
        the cost gets counted multiple times (once per parent level).

        Instead, just return usage_metadata in the state dict for DB storage.
        """
        # Intentionally disabled to prevent cost duplication
        # run_tree = get_current_run_tree()
        # if run_tree:
        #     run_tree.set(usage_metadata=self.to_langsmith_metadata())
        pass


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
    model: str | None = None,
) -> ClaudeCodeResult:
    """Run Claude Code SDK with a prompt asynchronously.

    Args:
        prompt: The prompt to send to Claude Code
        cwd: Working directory (repository path)
        allowed_tools: List of allowed tools (e.g., ["Read", "Glob", "Grep"])
        timeout: Command timeout in seconds
        verbose: Enable verbose output (currently unused with SDK)
        model: Model to use (e.g., "claude-sonnet-4.5"). Defaults to DEFAULT_CLAUDE_CODE_MODEL.

    Returns:
        ClaudeCodeResult with output, status, and usage info
    """
    if allowed_tools is None:
        allowed_tools = ["Read", "Glob", "Grep"]

    if model is None:
        model = DEFAULT_CLAUDE_CODE_MODEL

    options = ClaudeAgentOptions(
        allowed_tools=allowed_tools,
        cwd=cwd,
        permission_mode="bypassPermissions",
        max_turns=50,
        model=model,
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

                    # Extract usage from ResultMessage (cumulative totals)
                    usage_info.model = model

                    if message.usage:
                        # Note: input_tokens is only non-cached tokens
                        # Total input = input_tokens + cache_creation + cache_read
                        cache_creation = message.usage.get(
                            "cache_creation_input_tokens", 0
                        )
                        cache_read = message.usage.get("cache_read_input_tokens", 0)
                        base_input = message.usage.get("input_tokens", 0)

                        usage_info.input_tokens = base_input + cache_creation + cache_read
                        usage_info.output_tokens = message.usage.get("output_tokens", 0)
                        usage_info.cache_creation_tokens = cache_creation
                        usage_info.cache_read_tokens = cache_read

                    # Estimate cost split from total_cost_usd
                    total_cost = message.total_cost_usd or 0.0
                    input_cost, output_cost = estimate_cost_split(
                        total_cost, usage_info.input_tokens, usage_info.output_tokens
                    )
                    usage_info.input_cost_usd = input_cost
                    usage_info.output_cost_usd = output_cost

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
    model: str | None = None,
) -> ClaudeCodeResult:
    """Run Claude Code SDK with a prompt (sync wrapper).

    Args:
        prompt: The prompt to send to Claude Code
        cwd: Working directory (repository path)
        allowed_tools: List of allowed tools (e.g., ["Read", "Glob", "Grep"])
        model: Model to use (e.g., "claude-sonnet-4.5"). Defaults to DEFAULT_CLAUDE_CODE_MODEL.
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
            model=model,
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
