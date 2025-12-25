"""Claude Code CLI integration."""

import json
import os
import re
import subprocess
from dataclasses import dataclass, field


@dataclass
class ClaudeCodeResult:
    """Result of a Claude Code execution."""

    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.returncode == 0 and not self.timed_out


# Default timeout for Claude Code execution (3 minutes)
DEFAULT_TIMEOUT = 180


def run_claude_code(
    prompt: str,
    cwd: str,
    allowed_tools: list[str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    verbose: bool = False,
) -> ClaudeCodeResult:
    """Run Claude Code CLI with a prompt.

    Args:
        prompt: The prompt to send to Claude Code
        cwd: Working directory (repository path)
        allowed_tools: List of allowed tools (e.g., ["Read", "Glob", "Grep"])
        timeout: Command timeout in seconds
        verbose: Enable verbose output

    Returns:
        ClaudeCodeResult with output and status
    """
    if allowed_tools is None:
        allowed_tools = ["Read", "Glob", "Grep"]

    cmd = [
        "npx",
        "-y",
        "@anthropic-ai/claude-code",
        "-p",
        prompt,
        "--allowedTools",
        ",".join(allowed_tools),
    ]
    if verbose:
        cmd.append("--verbose")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            cwd=cwd,
            env={
                **os.environ,
                "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
            },
        )
        return ClaudeCodeResult(
            returncode=result.returncode,
            stdout=result.stdout.decode() if result.stdout else "",
            stderr=result.stderr.decode() if result.stderr else "",
        )
    except subprocess.TimeoutExpired:
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
            error="npx not found. Ensure Node.js is installed.",
        )
    except Exception as e:
        return ClaudeCodeResult(
            returncode=-1,
            stdout="",
            stderr="",
            error=str(e)[:500],
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
