"""Analyze node implementation using Claude Code."""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from langsmith import traceable

from beneissue.graph.state import IssueState
from beneissue.integrations.github import clone_repo
from beneissue.nodes.schemas import AnalyzeResult

# Load prompt from file
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "analyze.md"
ANALYZE_PROMPT = PROMPT_PATH.read_text()

# Timeout for Claude Code execution (3 minutes for analysis)
CLAUDE_CODE_TIMEOUT = 180


def _build_analyze_prompt(state: IssueState) -> str:
    """Build the analyze prompt for Claude Code."""
    return ANALYZE_PROMPT.format(
        issue_title=state["issue_title"],
        issue_body=state["issue_body"],
    )


def _parse_analyze_response(output: str) -> AnalyzeResult | None:
    """Parse Claude Code output to extract AnalyzeResult."""
    # Try to extract JSON from code blocks (greedy match for complete JSON)
    json_match = re.search(r"```(?:json)?\s*\n?(\{.*\})\s*\n?```", output, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            return AnalyzeResult(**data)
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    # Try to find any JSON object that starts with { and contains "summary"
    # Use a more robust approach: find all { and try to parse from each
    for match in re.finditer(r'\{', output):
        start_idx = match.start()
        # Try to find matching closing brace by counting braces
        brace_count = 0
        end_idx = start_idx
        for i, char in enumerate(output[start_idx:], start=start_idx):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break

        if end_idx > start_idx:
            candidate = output[start_idx:end_idx]
            if '"summary"' in candidate:
                try:
                    data = json.loads(candidate)
                    return AnalyzeResult(**data)
                except (json.JSONDecodeError, ValueError, TypeError):
                    continue

    # Try parsing entire output as JSON
    try:
        data = json.loads(output)
        return AnalyzeResult(**data)
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    return None


def _run_analysis(repo_path: str, prompt: str, *, verbose: bool = False) -> dict:
    """Run Claude Code analysis on a repository path."""
    try:
        cmd = [
            "claude",
            "-p",
            prompt,
            "--allowedTools",
            "Read,Glob,Grep",
        ]
        if verbose:
            cmd.append("--verbose")

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=CLAUDE_CODE_TIMEOUT,
            cwd=repo_path,
            env={
                **os.environ,
                "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
            },
        )

        stdout = result.stdout.decode() if result.stdout else ""

        response = _parse_analyze_response(stdout)

        if response:
            return _build_result(response)
        else:
            return _fallback_analyze(f"Failed to parse analysis output: {stdout[:200]}")

    except subprocess.TimeoutExpired:
        return _fallback_analyze(
            f"Analysis timeout after {CLAUDE_CODE_TIMEOUT} seconds"
        )
    except FileNotFoundError:
        return _fallback_analyze(
            "Claude Code CLI not installed. Run: npm install -g @anthropic-ai/claude-code"
        )
    except Exception as e:
        return _fallback_analyze(str(e)[:200])


@traceable(name="claude_code_analyze", run_type="chain")
def analyze_node(state: IssueState) -> dict:
    """Analyze an issue using Claude Code CLI."""
    prompt = _build_analyze_prompt(state)
    verbose = state.get("verbose", False)

    # Use project_root if provided (for testing), otherwise clone
    if state.get("project_root"):
        return _run_analysis(str(state["project_root"]), prompt, verbose=verbose)

    # Create temporary directory for the repo
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = os.path.join(temp_dir, "repo")

        # Clone the repository
        if not clone_repo(state["repo"], repo_path):
            return _fallback_analyze("Failed to clone repository")

        return _run_analysis(repo_path, prompt, verbose=verbose)


def _build_result(response: AnalyzeResult) -> dict:
    """Build the result dict from AnalyzeResult."""
    return {
        "analysis_summary": response.summary,
        "affected_files": response.affected_files,
        "fix_decision": response.fix_decision,
        "fix_reason": response.reason,
        "priority": response.priority,
        "story_points": response.story_points,
        "comment_draft": response.comment_draft,
        "assignee": response.assignee,
        "labels_to_add": [f"fix/{response.fix_decision.replace('_', '-')}"],
    }


def _fallback_analyze(error: str) -> dict:
    """Return a fallback analysis when Claude Code fails."""
    return {
        "analysis_summary": f"Analysis incomplete: {error}",
        "affected_files": [],
        "fix_decision": "manual_required",
        "fix_reason": f"Analysis failed: {error}",
        "comment_draft": f"Automated analysis encountered an issue: {error}\n\nPlease investigate manually.",
        "assignee": None,
        "labels_to_add": ["fix/manual-required"],
    }
